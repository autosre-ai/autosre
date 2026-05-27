"""
Workflow Execution Engine

The core engine that executes workflows:
- Manages workflow lifecycle
- Handles step execution with retries
- Tracks execution state and history
- Supports checkpointing and recovery
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import asyncio
import logging
import traceback
import uuid

from autosre.workflows.steps import (
    Step,
    StepResult,
    StepStatus,
    WorkflowContext,
)
from autosre.workflows.dsl import WorkflowDefinition
from autosre.workflows.triggers import TriggerEvent

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class StepExecution:
    """Record of a step's execution."""
    step_id: str
    step_name: str
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt: int = 1
    result: Optional[StepResult] = None
    error: Optional[str] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "attempt": self.attempt,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "output": self.result.output if self.result else None,
        }


@dataclass
class WorkflowExecution:
    """
    Represents a single execution of a workflow.
    
    Tracks:
    - Execution state and progress
    - Step execution history
    - Context and variables
    - Timing information
    """
    id: str
    workflow_id: str
    workflow_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    trigger_event: Optional[TriggerEvent] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    context: Optional[WorkflowContext] = None
    step_executions: List[StepExecution] = field(default_factory=list)
    current_step_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    tenant_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate total execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "trigger_event": self.trigger_event.to_dict() if self.trigger_event else None,
            "inputs": self.inputs,
            "current_step_index": self.current_step_index,
            "step_executions": [s.to_dict() for s in self.step_executions],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "tenant_id": self.tenant_id,
            "parent_execution_id": self.parent_execution_id,
            "metadata": self.metadata,
        }


class WorkflowEngine:
    """
    Workflow execution engine.
    
    Features:
    - Async workflow execution
    - Step-level retries with backoff
    - Execution history and state management
    - Concurrent execution limits
    - Hooks for monitoring and customization
    """

    def __init__(
        self,
        max_concurrent_executions: int = 100,
        default_timeout_seconds: int = 3600,
        checkpoint_enabled: bool = True,
    ):
        self.max_concurrent_executions = max_concurrent_executions
        self.default_timeout_seconds = default_timeout_seconds
        self.checkpoint_enabled = checkpoint_enabled
        
        # Workflow registry
        self._workflows: Dict[str, WorkflowDefinition] = {}
        
        # Execution tracking
        self._executions: Dict[str, WorkflowExecution] = {}
        self._running_count = 0
        self._execution_semaphore = asyncio.Semaphore(max_concurrent_executions)
        
        # Action handlers (tool implementations)
        self._action_handlers: Dict[str, Callable] = {}
        
        # Lifecycle hooks
        self._hooks: Dict[str, List[Callable]] = {
            "on_execution_start": [],
            "on_execution_complete": [],
            "on_step_start": [],
            "on_step_complete": [],
            "on_error": [],
        }
        
        # Checkpoint storage (pluggable)
        self._checkpoint_store: Optional[Callable] = None

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition."""
        self._workflows[workflow.id] = workflow
        logger.info(f"Registered workflow: {workflow.id}")

    def unregister_workflow(self, workflow_id: str) -> None:
        """Unregister a workflow definition."""
        self._workflows.pop(workflow_id, None)

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get a workflow definition by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[WorkflowDefinition]:
        """List all registered workflows."""
        return list(self._workflows.values())

    def register_action_handler(
        self, action_type: str, handler: Callable
    ) -> None:
        """
        Register a handler for an action type.
        
        Handlers should have signature:
        async def handler(inputs: Dict[str, Any], context: WorkflowContext) -> Any
        """
        self._action_handlers[action_type] = handler

    def register_hook(
        self, event: str, callback: Callable
    ) -> None:
        """Register a lifecycle hook."""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def set_checkpoint_store(
        self, store: Callable[[str, Dict[str, Any]], None]
    ) -> None:
        """Set checkpoint storage implementation."""
        self._checkpoint_store = store

    async def execute(
        self,
        workflow_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        trigger_event: Optional[TriggerEvent] = None,
        tenant_id: Optional[str] = None,
        parent_execution_id: Optional[str] = None,
        wait: bool = True,
    ) -> WorkflowExecution:
        """
        Execute a workflow.
        
        Args:
            workflow_id: ID of the workflow to execute
            inputs: Input parameters
            trigger_event: Optional trigger event that started this execution
            tenant_id: Tenant ID for multi-tenant execution
            parent_execution_id: Parent execution ID if this is a sub-workflow
            wait: Whether to wait for completion
        
        Returns:
            WorkflowExecution record
        """
        # Get workflow definition
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"Workflow not found: {workflow_id}")
        
        # Validate inputs
        inputs = inputs or {}
        default_inputs = workflow.get_default_inputs()
        merged_inputs = {**default_inputs, **inputs}
        
        errors = workflow.validate_inputs(merged_inputs)
        if errors:
            raise WorkflowValidationError(f"Invalid inputs: {', '.join(errors)}")
        
        # Create execution record
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            status=ExecutionStatus.QUEUED,
            trigger_event=trigger_event,
            inputs=merged_inputs,
            tenant_id=tenant_id,
            parent_execution_id=parent_execution_id,
        )
        
        self._executions[execution_id] = execution
        
        if wait:
            # Execute synchronously
            return await self._execute_workflow(execution, workflow)
        else:
            # Execute in background
            asyncio.create_task(self._execute_workflow(execution, workflow))
            return execution

    async def _execute_workflow(
        self, execution: WorkflowExecution, workflow: WorkflowDefinition
    ) -> WorkflowExecution:
        """Execute a workflow (internal)."""
        async with self._execution_semaphore:
            self._running_count += 1
            
            try:
                return await self._run_workflow(execution, workflow)
            finally:
                self._running_count -= 1

    async def _run_workflow(
        self, execution: WorkflowExecution, workflow: WorkflowDefinition
    ) -> WorkflowExecution:
        """Run the workflow execution."""
        # Initialize context
        context = WorkflowContext(
            variables=execution.inputs.copy(),
            trigger_data=execution.trigger_event.payload if execution.trigger_event else {},
            tenant_id=execution.tenant_id,
            execution_id=execution.id,
        )
        
        # Register action handlers
        for action_type, handler in self._action_handlers.items():
            context.register_action_handler(action_type, handler)
        
        # Register sub-workflow executor
        context.register_action_handler(
            "execute_workflow",
            lambda inputs, ctx: self._execute_subworkflow(inputs, ctx),
        )
        
        execution.context = context
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)
        
        # Fire start hook
        await self._fire_hook("on_execution_start", execution)
        
        try:
            # Execute with timeout
            timeout = workflow.timeout_seconds or self.default_timeout_seconds
            
            try:
                await asyncio.wait_for(
                    self._execute_steps(execution, workflow.steps, context),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                execution.status = ExecutionStatus.TIMED_OUT
                execution.error = f"Workflow timed out after {timeout}s"
                await self._fire_hook("on_error", execution, execution.error)
                
                # Run on_failure handlers
                if workflow.on_failure:
                    await self._execute_steps(
                        execution, workflow.on_failure, context, is_handler=True
                    )
                
                return execution
            
            # Check final status
            failed_steps = [
                se for se in execution.step_executions
                if se.status == StepStatus.FAILED
            ]
            
            if failed_steps:
                execution.status = ExecutionStatus.FAILED
                execution.error = f"Steps failed: {[s.step_name for s in failed_steps]}"
                
                # Run on_failure handlers
                if workflow.on_failure:
                    await self._execute_steps(
                        execution, workflow.on_failure, context, is_handler=True
                    )
            else:
                execution.status = ExecutionStatus.COMPLETED
                
                # Run on_success handlers
                if workflow.on_success:
                    await self._execute_steps(
                        execution, workflow.on_success, context, is_handler=True
                    )
            
        except asyncio.CancelledError:
            execution.status = ExecutionStatus.CANCELLED
            execution.error = "Execution was cancelled"
            raise
        
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Workflow execution failed: {e}\n{traceback.format_exc()}")
            await self._fire_hook("on_error", execution, str(e))
            
            # Run on_failure handlers
            if workflow.on_failure:
                try:
                    await self._execute_steps(
                        execution, workflow.on_failure, context, is_handler=True
                    )
                except Exception:
                    pass  # Don't fail on handler errors
        
        finally:
            execution.completed_at = datetime.now(timezone.utc)
            await self._fire_hook("on_execution_complete", execution)
            
            if self.checkpoint_enabled and self._checkpoint_store:
                await self._save_checkpoint(execution)
        
        return execution

    async def _execute_steps(
        self,
        execution: WorkflowExecution,
        steps: List[Step],
        context: WorkflowContext,
        is_handler: bool = False,
    ) -> None:
        """Execute a list of steps."""
        for i, step in enumerate(steps):
            if not is_handler:
                execution.current_step_index = i
            
            # Check condition
            if not step.should_run(context):
                step_exec = StepExecution(
                    step_id=step.id,
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                execution.step_executions.append(step_exec)
                continue
            
            # Execute step with retries
            result = await self._execute_step_with_retry(
                execution, step, context
            )
            
            # Record result
            context.record_result(step.id, result)
            
            # Handle failure
            if not result.is_success and not step.continue_on_error:
                if not is_handler:  # Don't fail on handler errors
                    break

    async def _execute_step_with_retry(
        self,
        execution: WorkflowExecution,
        step: Step,
        context: WorkflowContext,
    ) -> StepResult:
        """Execute a step with retry logic."""
        attempt = 0
        last_result = None
        
        while attempt <= step.retry_count:
            attempt += 1
            
            step_exec = StepExecution(
                step_id=step.id,
                step_name=step.name,
                status=StepStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                attempt=attempt,
            )
            
            # Fire step start hook
            await self._fire_hook("on_step_start", execution, step, attempt)
            
            try:
                result = await step.execute(context)
                step_exec.result = result
                step_exec.status = result.status
                step_exec.completed_at = datetime.now(timezone.utc)
                
                if result.error:
                    step_exec.error = result.error
                
            except Exception as e:
                result = StepResult(
                    status=StepStatus.FAILED,
                    error=str(e),
                    started_at=step_exec.started_at,
                    completed_at=datetime.now(timezone.utc),
                )
                step_exec.result = result
                step_exec.status = StepStatus.FAILED
                step_exec.error = str(e)
                step_exec.completed_at = datetime.now(timezone.utc)
            
            execution.step_executions.append(step_exec)
            last_result = result
            
            # Fire step complete hook
            await self._fire_hook("on_step_complete", execution, step, result)
            
            # Checkpoint after each step
            if self.checkpoint_enabled and self._checkpoint_store:
                await self._save_checkpoint(execution)
            
            # If successful, break out of retry loop
            if result.is_success:
                break
            
            # Retry if not last attempt
            if attempt <= step.retry_count:
                logger.info(
                    f"Step '{step.name}' failed, retrying "
                    f"({attempt}/{step.retry_count + 1})..."
                )
                await asyncio.sleep(step.retry_delay_seconds)
        
        return last_result

    async def _execute_subworkflow(
        self, inputs: Dict[str, Any], context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute a sub-workflow."""
        workflow_id = inputs.get("workflow_id")
        sub_inputs = inputs.get("inputs", {})
        wait = inputs.get("wait", True)
        parent_id = inputs.get("parent_execution_id")
        
        try:
            execution = await self.execute(
                workflow_id=workflow_id,
                inputs=sub_inputs,
                tenant_id=context.tenant_id,
                parent_execution_id=parent_id,
                wait=wait,
            )
            
            return {
                "success": execution.status == ExecutionStatus.COMPLETED,
                "execution_id": execution.id,
                "status": execution.status.value,
                "error": execution.error,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _fire_hook(self, event: str, *args) -> None:
        """Fire lifecycle hooks."""
        for callback in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    callback(*args)
            except Exception as e:
                logger.error(f"Hook {event} failed: {e}")

    async def _save_checkpoint(self, execution: WorkflowExecution) -> None:
        """Save execution checkpoint."""
        if self._checkpoint_store:
            try:
                checkpoint_data = execution.to_dict()
                if asyncio.iscoroutinefunction(self._checkpoint_store):
                    await self._checkpoint_store(execution.id, checkpoint_data)
                else:
                    self._checkpoint_store(execution.id, checkpoint_data)
            except Exception as e:
                logger.error(f"Failed to save checkpoint: {e}")

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get an execution by ID."""
        return self._executions.get(execution_id)

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """List executions with optional filtering."""
        executions = list(self._executions.values())
        
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        
        if status:
            executions = [e for e in executions if e.status == status]
        
        if tenant_id:
            executions = [e for e in executions if e.tenant_id == tenant_id]
        
        # Sort by created_at descending
        executions.sort(key=lambda e: e.created_at, reverse=True)
        
        return executions[:limit]

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            return False
        
        if execution.is_terminal:
            return False
        
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now(timezone.utc)
        execution.error = "Cancelled by user"
        
        return True

    async def pause_execution(self, execution_id: str) -> bool:
        """Pause a running execution."""
        execution = self._executions.get(execution_id)
        if not execution or execution.status != ExecutionStatus.RUNNING:
            return False
        
        execution.status = ExecutionStatus.PAUSED
        return True

    async def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused execution."""
        execution = self._executions.get(execution_id)
        if not execution or execution.status != ExecutionStatus.PAUSED:
            return False
        
        workflow = self._workflows.get(execution.workflow_id)
        if not workflow:
            return False
        
        # Resume from current step
        execution.status = ExecutionStatus.RUNNING
        remaining_steps = workflow.steps[execution.current_step_index:]
        
        asyncio.create_task(
            self._execute_steps(execution, remaining_steps, execution.context)
        )
        
        return True

    @property
    def stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        executions = list(self._executions.values())
        
        status_counts = {}
        for status in ExecutionStatus:
            status_counts[status.value] = len(
                [e for e in executions if e.status == status]
            )
        
        return {
            "workflows_registered": len(self._workflows),
            "total_executions": len(executions),
            "running_executions": self._running_count,
            "max_concurrent": self.max_concurrent_executions,
            "action_handlers": list(self._action_handlers.keys()),
            "status_counts": status_counts,
        }


class WorkflowNotFoundError(Exception):
    """Exception raised when a workflow is not found."""
    pass


class WorkflowValidationError(Exception):
    """Exception raised when workflow validation fails."""
    pass
