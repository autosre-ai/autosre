"""
Remediation Engine - Orchestrates remediation workflows.

The engine coordinates action execution, safety checks, approvals,
and rollback management for automated incident remediation.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

from .models import (
    RemediationAction,
    RemediationPlan,
    RemediationResult,
    RemediationStatus,
    ActionDefinition,
    RiskLevel,
    BlastRadius,
    ApprovalStatus,
)
from .registry import ActionRegistry, ActionNotFoundError, get_registry
from .rollback import RollbackManager, RollbackResult
from .safety import SafetyChecker, SafetyPolicy
from .approval import ApprovalWorkflow, ApprovalPolicy, NotificationChannel

logger = get_logger(__name__)


class ExecutionContext(BaseModel):
    """Context for action execution."""
    
    id: UUID = Field(default_factory=uuid4)
    action: RemediationAction
    definition: ActionDefinition
    
    # Execution state
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Options
    dry_run: bool = False
    skip_safety_checks: bool = False
    skip_approval: bool = False
    auto_rollback: bool = True
    
    # Results
    result: RemediationResult | None = None
    rollback_result: RollbackResult | None = None


class EngineConfig(BaseModel):
    """Configuration for the remediation engine."""
    
    # Safety
    enable_safety_checks: bool = True
    safety_policy: SafetyPolicy | None = None
    
    # Approvals
    enable_approvals: bool = True
    approval_policy: ApprovalPolicy | None = None
    
    # Rollback
    enable_auto_rollback: bool = True
    max_rollback_retries: int = 3
    
    # Execution
    default_timeout_seconds: int = 300
    max_concurrent_actions: int = 10
    
    # Notifications
    notification_channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.CONSOLE]
    )
    
    # Dry run
    force_dry_run: bool = False


# Type for execution hooks
PreExecutionHook = Callable[[ExecutionContext], Awaitable[bool]]
PostExecutionHook = Callable[[ExecutionContext, RemediationResult], Awaitable[None]]


class RemediationEngine:
    """
    Orchestrates remediation workflows.
    
    The engine provides:
    - Action registration and execution
    - Safety checks before execution
    - Human approval workflows
    - Automatic rollback on failure
    - Execution metrics and history
    
    Example:
        engine = RemediationEngine()
        
        # Create and execute an action
        action = engine.create_action(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-abc123",
            target_namespace="production",
            parameters={"grace_period": 30},
        )
        
        result = await engine.execute(action)
        
        if not result.success:
            # Auto-rollback happens automatically
            print(f"Failed: {result.error}")
    """
    
    def __init__(
        self,
        config: EngineConfig | None = None,
        registry: ActionRegistry | None = None,
    ):
        self._config = config or EngineConfig()
        self._registry = registry or get_registry()
        
        # Components
        self._safety_checker = SafetyChecker(
            policy=self._config.safety_policy or SafetyPolicy(name="default")
        )
        self._rollback_manager = RollbackManager()
        self._approval_workflow = ApprovalWorkflow(
            policy=self._config.approval_policy or ApprovalPolicy(name="default")
        )
        
        # Execution tracking
        self._active_executions: dict[UUID, ExecutionContext] = {}
        self._execution_history: list[RemediationResult] = []
        self._execution_semaphore = asyncio.Semaphore(
            self._config.max_concurrent_actions
        )
        
        # Hooks
        self._pre_hooks: list[PreExecutionHook] = []
        self._post_hooks: list[PostExecutionHook] = []
        
        self._lock = asyncio.Lock()
    
    @property
    def registry(self) -> ActionRegistry:
        return self._registry
    
    @property
    def safety_checker(self) -> SafetyChecker:
        return self._safety_checker
    
    @property
    def rollback_manager(self) -> RollbackManager:
        return self._rollback_manager
    
    @property
    def approval_workflow(self) -> ApprovalWorkflow:
        return self._approval_workflow
    
    def add_pre_hook(self, hook: PreExecutionHook) -> None:
        """Add a pre-execution hook."""
        self._pre_hooks.append(hook)
    
    def add_post_hook(self, hook: PostExecutionHook) -> None:
        """Add a post-execution hook."""
        self._post_hooks.append(hook)
    
    def create_action(
        self,
        definition_name: str,
        target_type: str,
        target_name: str,
        target_namespace: str | None = None,
        target_cluster: str | None = None,
        parameters: dict[str, Any] | None = None,
        dry_run: bool = False,
        triggered_by: str = "autosre",
        investigation_id: UUID | None = None,
        incident_id: str | None = None,
    ) -> RemediationAction:
        """
        Create a remediation action.
        
        Args:
            definition_name: Name of the action definition
            target_type: Type of target (pod, deployment, node, etc)
            target_name: Name of the target resource
            target_namespace: Kubernetes namespace
            target_cluster: Cluster name
            parameters: Action parameters
            dry_run: Whether to run in dry-run mode
            triggered_by: Who/what triggered this action
            investigation_id: Related investigation
            incident_id: Related incident
            
        Returns:
            Created remediation action
        """
        # Verify action exists
        if not self._registry.has_action(definition_name):
            raise ActionNotFoundError(definition_name)
        
        # Apply force dry run from config
        effective_dry_run = dry_run or self._config.force_dry_run
        
        action = RemediationAction(
            definition_name=definition_name,
            target_type=target_type,
            target_name=target_name,
            target_namespace=target_namespace,
            target_cluster=target_cluster,
            parameters=parameters or {},
            dry_run=effective_dry_run,
            triggered_by=triggered_by,
            investigation_id=investigation_id,
            incident_id=incident_id,
        )
        
        logger.info(
            f"Created action {action.id}: {definition_name} -> "
            f"{target_type}/{target_namespace}/{target_name}"
            + (" [DRY RUN]" if effective_dry_run else "")
        )
        
        return action
    
    async def execute(
        self,
        action: RemediationAction,
        skip_safety_checks: bool = False,
        skip_approval: bool = False,
        auto_rollback: bool = True,
        wait_for_approval: bool = True,
        approval_timeout_seconds: float | None = None,
    ) -> RemediationResult:
        """
        Execute a remediation action.
        
        Args:
            action: The action to execute
            skip_safety_checks: Skip safety checks (dangerous!)
            skip_approval: Skip approval workflow
            auto_rollback: Automatically rollback on failure
            wait_for_approval: Wait for approval if required
            approval_timeout_seconds: Timeout for approval wait
            
        Returns:
            Execution result
        """
        # Get definition
        definition = self._registry.get_definition(action.definition_name)
        
        # Create execution context
        ctx = ExecutionContext(
            action=action,
            definition=definition,
            dry_run=action.dry_run,
            skip_safety_checks=skip_safety_checks,
            skip_approval=skip_approval,
            auto_rollback=auto_rollback and self._config.enable_auto_rollback,
        )
        
        async with self._execution_semaphore:
            return await self._execute_with_context(
                ctx,
                wait_for_approval=wait_for_approval,
                approval_timeout_seconds=approval_timeout_seconds,
            )
    
    async def _execute_with_context(
        self,
        ctx: ExecutionContext,
        wait_for_approval: bool = True,
        approval_timeout_seconds: float | None = None,
    ) -> RemediationResult:
        """Execute action with full context."""
        action = ctx.action
        start_time = datetime.utcnow()
        
        try:
            # Track active execution
            async with self._lock:
                self._active_executions[ctx.id] = ctx
            
            # Update action status
            action.status = RemediationStatus.VALIDATING
            
            # Run pre-execution hooks
            for hook in self._pre_hooks:
                try:
                    should_continue = await hook(ctx)
                    if not should_continue:
                        return self._create_result(
                            action=action,
                            success=False,
                            status=RemediationStatus.CANCELLED,
                            message="Pre-execution hook cancelled execution",
                            started_at=start_time,
                        )
                except Exception as e:
                    logger.error(f"Pre-hook error: {e}")
            
            # Safety checks
            if self._config.enable_safety_checks and not ctx.skip_safety_checks:
                safety_results = await self._safety_checker.check_action(
                    action, ctx.definition
                )
                action.safety_checks = safety_results
                
                # Assess blast radius
                action.blast_radius = await self._safety_checker.assess_blast_radius(action)
                
                if not self._safety_checker.is_safe(safety_results):
                    violations = self._safety_checker.get_violations(safety_results)
                    return self._create_result(
                        action=action,
                        success=False,
                        status=RemediationStatus.FAILED,
                        message=f"Safety checks failed: {violations[0].message if violations else 'Unknown'}",
                        started_at=start_time,
                        error="Safety check violation",
                    )
            
            # Check if approval required
            if (
                self._config.enable_approvals
                and not ctx.skip_approval
                and not action.dry_run
            ):
                requires_approval, reason = self._safety_checker.requires_approval(
                    action, action.safety_checks
                )
                
                if requires_approval or ctx.definition.requires_approval:
                    action.status = RemediationStatus.WAITING_APPROVAL
                    
                    # Create approval request
                    approval_request = await self._approval_workflow.request_approval(
                        action=action,
                        reason=reason or f"Action {action.definition_name} requires approval",
                        blast_radius=action.blast_radius,
                        safety_checks=action.safety_checks,
                    )
                    
                    if wait_for_approval:
                        # Wait for approval decision
                        status = await self._approval_workflow.wait_for_decision(
                            approval_request.id,
                            timeout_seconds=approval_timeout_seconds,
                        )
                        
                        if status == ApprovalStatus.APPROVED:
                            action.status = RemediationStatus.APPROVED
                        elif status == ApprovalStatus.REJECTED:
                            action.status = RemediationStatus.REJECTED
                            return self._create_result(
                                action=action,
                                success=False,
                                status=RemediationStatus.REJECTED,
                                message=f"Action rejected: {approval_request.rejection_reason}",
                                started_at=start_time,
                            )
                        else:
                            return self._create_result(
                                action=action,
                                success=False,
                                status=RemediationStatus.CANCELLED,
                                message=f"Approval not received (status: {status.value})",
                                started_at=start_time,
                            )
                    else:
                        return self._create_result(
                            action=action,
                            success=False,
                            status=RemediationStatus.WAITING_APPROVAL,
                            message="Waiting for approval",
                            started_at=start_time,
                        )
            
            # Execute the action
            action.status = RemediationStatus.EXECUTING
            action.started_at = datetime.utcnow()
            ctx.started_at = action.started_at
            
            try:
                # Capture pre-execution state for rollback
                await self._capture_pre_state(action)
                
                # Execute via registry
                result_data = await self._registry.execute(
                    name=action.definition_name,
                    parameters=self._build_execution_params(action),
                    enforce_cooldown=True,
                    timeout=ctx.definition.timeout_seconds,
                )
                
                action.result = result_data
                action.status = RemediationStatus.COMPLETED
                action.completed_at = datetime.utcnow()
                
                # Record action for rate limiting
                await self._safety_checker.record_action(action)
                
                result = self._create_result(
                    action=action,
                    success=True,
                    status=RemediationStatus.COMPLETED,
                    message="Action completed successfully",
                    started_at=start_time,
                    result_data=result_data,
                )
                
            except Exception as e:
                action.status = RemediationStatus.FAILED
                action.error = str(e)
                action.completed_at = datetime.utcnow()
                
                logger.error(
                    f"Action {action.definition_name} failed: {e}",
                    exc_info=True,
                )
                
                # Auto-rollback on failure
                rollback_result = None
                if ctx.auto_rollback and not action.dry_run:
                    rollback_result = await self._attempt_rollback(action)
                
                result = self._create_result(
                    action=action,
                    success=False,
                    status=RemediationStatus.FAILED,
                    message=f"Action failed: {str(e)}",
                    started_at=start_time,
                    error=str(e),
                    error_type=type(e).__name__,
                    stack_trace=traceback.format_exc(),
                    was_rolled_back=rollback_result is not None and rollback_result.success,
                    rollback_success=rollback_result.success if rollback_result else None,
                    rollback_error="; ".join(rollback_result.errors) if rollback_result else None,
                )
            
            # Run post-execution hooks
            for hook in self._post_hooks:
                try:
                    await hook(ctx, result)
                except Exception as e:
                    logger.error(f"Post-hook error: {e}")
            
            # Store in history
            async with self._lock:
                self._execution_history.append(result)
            
            ctx.result = result
            return result
            
        finally:
            # Clean up active execution
            async with self._lock:
                self._active_executions.pop(ctx.id, None)
    
    async def execute_plan(
        self,
        plan: RemediationPlan,
        skip_safety_checks: bool = False,
        skip_approval: bool = False,
    ) -> list[RemediationResult]:
        """
        Execute a remediation plan.
        
        Args:
            plan: The plan to execute
            skip_safety_checks: Skip safety checks
            skip_approval: Skip approval workflow
            
        Returns:
            List of results for each action
        """
        results = []
        plan.status = RemediationStatus.EXECUTING
        plan.started_at = datetime.utcnow()
        
        logger.info(f"Executing remediation plan {plan.id} with {len(plan.actions)} actions")
        
        if plan.parallel:
            # Execute all actions in parallel
            tasks = [
                self.execute(
                    action,
                    skip_safety_checks=skip_safety_checks,
                    skip_approval=skip_approval,
                )
                for action in plan.actions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to results
            results = [
                r if isinstance(r, RemediationResult)
                else self._create_result(
                    action=plan.actions[i],
                    success=False,
                    status=RemediationStatus.FAILED,
                    message=str(r),
                    started_at=plan.started_at or datetime.utcnow(),
                    error=str(r),
                )
                for i, r in enumerate(results)
            ]
        else:
            # Execute sequentially
            for action in plan.actions:
                result = await self.execute(
                    action,
                    skip_safety_checks=skip_safety_checks,
                    skip_approval=skip_approval,
                )
                results.append(result)
                
                plan.current_action_index += 1
                plan.progress_percent = (plan.current_action_index / len(plan.actions)) * 100
                
                # Stop on failure if configured
                if not result.success and plan.stop_on_failure:
                    logger.warning(f"Plan {plan.id} stopping due to action failure")
                    break
        
        # Determine final plan status
        all_success = all(r.success for r in results)
        any_success = any(r.success for r in results)
        
        if all_success:
            plan.status = RemediationStatus.COMPLETED
        elif any_success:
            plan.status = RemediationStatus.PARTIALLY_COMPLETED
        else:
            plan.status = RemediationStatus.FAILED
        
        plan.completed_at = datetime.utcnow()
        
        logger.info(
            f"Plan {plan.id} completed: {plan.status.value} "
            f"({plan.completed_actions}/{len(plan.actions)} actions succeeded)"
        )
        
        return results
    
    async def _capture_pre_state(self, action: RemediationAction) -> None:
        """Capture resource state before modification."""
        # This would integrate with Kubernetes to capture actual state
        # For now, we store basic info in rollback_data
        
        action.rollback_data = {
            "target_type": action.target_type,
            "target_name": action.target_name,
            "target_namespace": action.target_namespace,
            "parameters": action.parameters,
            "captured_at": datetime.utcnow().isoformat(),
        }
        
        # Create checkpoint
        await self._rollback_manager.create_checkpoint(
            action_id=action.id,
            name=f"pre-{action.definition_name}",
            description=f"State before {action.definition_name}",
        )
    
    async def _attempt_rollback(
        self,
        action: RemediationAction,
    ) -> RollbackResult | None:
        """Attempt to rollback a failed action."""
        can_rollback, reason = self._rollback_manager.can_rollback(action)
        
        if not can_rollback:
            logger.warning(f"Cannot rollback action {action.id}: {reason}")
            return None
        
        logger.info(f"Attempting rollback for action {action.id}")
        
        # Define a restore handler that would integrate with Kubernetes
        async def restore_handler(
            resource_type: str,
            resource_name: str,
            namespace: str | None,
            state_data: dict,
        ) -> bool:
            # This would use the Kubernetes client to restore state
            logger.info(
                f"Would restore {resource_type}/{resource_name} "
                f"in {namespace} to previous state"
            )
            return True  # Placeholder
        
        return await self._rollback_manager.execute_rollback(
            action,
            restore_handler=restore_handler,
        )
    
    def _build_execution_params(self, action: RemediationAction) -> dict[str, Any]:
        """Build parameters for action execution."""
        params = dict(action.parameters)
        
        # Add standard context parameters
        params["_context"] = {
            "action_id": str(action.id),
            "target_type": action.target_type,
            "target_name": action.target_name,
            "target_namespace": action.target_namespace,
            "dry_run": action.dry_run,
        }
        
        return params
    
    def _create_result(
        self,
        action: RemediationAction,
        success: bool,
        status: RemediationStatus,
        message: str,
        started_at: datetime,
        result_data: dict[str, Any] | None = None,
        error: str | None = None,
        error_type: str | None = None,
        stack_trace: str | None = None,
        was_rolled_back: bool = False,
        rollback_success: bool | None = None,
        rollback_error: str | None = None,
    ) -> RemediationResult:
        """Create a remediation result."""
        return RemediationResult(
            action_id=action.id,
            success=success,
            status=status,
            message=message,
            result_data=result_data or {},
            error=error,
            error_type=error_type,
            stack_trace=stack_trace,
            was_rolled_back=was_rolled_back,
            rollback_success=rollback_success,
            rollback_error=rollback_error,
            started_at=started_at,
            resources_modified=[
                f"{action.target_namespace}/{action.target_type}/{action.target_name}"
            ] if action.target_namespace else [
                f"{action.target_type}/{action.target_name}"
            ],
            actual_blast_radius=action.blast_radius,
        )
    
    async def cancel(self, action_id: UUID) -> bool:
        """
        Cancel a pending or executing action.
        
        Args:
            action_id: Action ID
            
        Returns:
            True if cancellation was successful
        """
        async with self._lock:
            for ctx in self._active_executions.values():
                if ctx.action.id == action_id:
                    ctx.action.status = RemediationStatus.CANCELLED
                    logger.info(f"Cancelled action {action_id}")
                    return True
        
        logger.warning(f"Action {action_id} not found in active executions")
        return False
    
    async def rollback_action(self, action_id: UUID) -> RollbackResult | None:
        """
        Manually trigger rollback for an action.
        
        Args:
            action_id: Action ID
            
        Returns:
            Rollback result
        """
        # Find action in history
        for result in self._execution_history:
            if result.action_id == action_id:
                # Get original action (would need to be stored)
                logger.warning(f"Manual rollback for {action_id} - implementation needed")
                return None
        
        logger.warning(f"Action {action_id} not found in history")
        return None
    
    def get_active_executions(self) -> list[ExecutionContext]:
        """Get currently active executions."""
        return list(self._active_executions.values())
    
    def get_execution_history(
        self,
        limit: int = 100,
        success_only: bool = False,
        failed_only: bool = False,
    ) -> list[RemediationResult]:
        """Get execution history."""
        history = self._execution_history[-limit:]
        
        if success_only:
            history = [r for r in history if r.success]
        elif failed_only:
            history = [r for r in history if not r.success]
        
        return history
    
    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        total = len(self._execution_history)
        success = sum(1 for r in self._execution_history if r.success)
        failed = total - success
        rolled_back = sum(1 for r in self._execution_history if r.was_rolled_back)
        
        total_duration = sum(
            r.duration_seconds for r in self._execution_history
        )
        
        return {
            "total_executions": total,
            "successful": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0,
            "rolled_back": rolled_back,
            "rollback_rate": rolled_back / failed if failed > 0 else 0,
            "active_executions": len(self._active_executions),
            "total_duration_seconds": total_duration,
            "average_duration_seconds": total_duration / total if total > 0 else 0,
            "registry_stats": self._registry.get_metrics(),
            "safety_policy": self._safety_checker.policy.name,
            "approval_stats": self._approval_workflow.get_stats(),
            "rollback_stats": self._rollback_manager.get_stats(),
        }
