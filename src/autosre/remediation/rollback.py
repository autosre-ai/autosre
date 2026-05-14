"""
Rollback Manager for remediation actions.

Handles automatic rollback of failed remediation actions,
including state capture, checkpoint management, and rollback execution.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

from .models import (
    RemediationAction,
    RemediationResult,
    RemediationStatus,
    RollbackStrategy,
)

logger = get_logger(__name__)


class RollbackState(str, Enum):
    """State of a rollback operation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_NEEDED = "not_needed"


class StateSnapshot(BaseModel):
    """Snapshot of resource state before modification."""
    
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    
    # Resource identification
    resource_type: str
    resource_name: str
    resource_namespace: str | None = None
    
    # State data
    state_data: dict[str, Any] = Field(default_factory=dict)
    state_hash: str | None = None
    
    # Metadata
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "kubernetes"  # Source system (kubernetes, configmap, etc)
    
    # Verification
    is_verified: bool = False
    verification_error: str | None = None


class RollbackCheckpoint(BaseModel):
    """A checkpoint in a multi-step remediation."""
    
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    
    # Checkpoint info
    name: str
    description: str = ""
    step_index: int = 0
    
    # State at checkpoint
    snapshots: list[StateSnapshot] = Field(default_factory=list)
    
    # Status
    is_valid: bool = True
    invalidation_reason: str | None = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=24)
    )
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class RollbackPlan(BaseModel):
    """Plan for rolling back an action."""
    
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    
    # Steps
    steps: list[dict[str, Any]] = Field(default_factory=list)
    current_step: int = 0
    
    # State
    state: RollbackState = RollbackState.PENDING
    
    # Checkpoints to restore
    checkpoint_ids: list[UUID] = Field(default_factory=list)
    
    # Results
    steps_completed: int = 0
    steps_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RollbackResult(BaseModel):
    """Result of a rollback operation."""
    
    action_id: UUID
    plan_id: UUID
    
    # Outcome
    success: bool
    state: RollbackState
    message: str = ""
    
    # Details
    steps_completed: int = 0
    steps_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    
    # Restored state
    restored_resources: list[str] = Field(default_factory=list)
    
    # Timing
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


RollbackHandler = Callable[[dict[str, Any]], Awaitable[bool]]


class RollbackManager:
    """
    Manages rollback operations for remediation actions.
    
    Features:
    - State snapshot capture before modifications
    - Checkpoint management for multi-step operations
    - Automatic rollback on failure
    - Manual rollback support
    - Rollback verification
    
    Example:
        manager = RollbackManager()
        
        # Capture state before action
        snapshot = await manager.capture_state(
            action_id=action.id,
            resource_type="deployment",
            resource_name="api-server",
            resource_namespace="production",
            state_data={"replicas": 3, "image": "v1.0"},
        )
        
        # Create checkpoint
        checkpoint = await manager.create_checkpoint(
            action_id=action.id,
            name="pre-scale",
            snapshots=[snapshot],
        )
        
        # If action fails, rollback
        if action_failed:
            result = await manager.rollback(action)
    """
    
    def __init__(
        self,
        max_checkpoint_age_hours: int = 24,
        max_snapshots_per_action: int = 100,
    ):
        self._snapshots: dict[UUID, list[StateSnapshot]] = {}  # action_id -> snapshots
        self._checkpoints: dict[UUID, list[RollbackCheckpoint]] = {}  # action_id -> checkpoints
        self._rollback_handlers: dict[str, RollbackHandler] = {}  # action_name -> handler
        self._rollback_plans: dict[UUID, RollbackPlan] = {}  # action_id -> plan
        
        self._max_checkpoint_age_hours = max_checkpoint_age_hours
        self._max_snapshots_per_action = max_snapshots_per_action
        
        self._lock = asyncio.Lock()
    
    def register_handler(
        self,
        action_name: str,
        handler: RollbackHandler,
    ) -> None:
        """
        Register a rollback handler for an action type.
        
        Args:
            action_name: Name of the action
            handler: Async function that performs rollback
        """
        self._rollback_handlers[action_name] = handler
        logger.info(f"Registered rollback handler for: {action_name}")
    
    async def capture_state(
        self,
        action_id: UUID,
        resource_type: str,
        resource_name: str,
        state_data: dict[str, Any],
        resource_namespace: str | None = None,
        source: str = "kubernetes",
    ) -> StateSnapshot:
        """
        Capture state of a resource before modification.
        
        Args:
            action_id: ID of the remediation action
            resource_type: Type of resource (deployment, pod, etc)
            resource_name: Name of the resource
            state_data: Current state data to capture
            resource_namespace: Kubernetes namespace
            source: Source system
            
        Returns:
            Created snapshot
        """
        import hashlib
        
        # Create hash of state for comparison
        state_json = json.dumps(state_data, sort_keys=True)
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()[:16]
        
        snapshot = StateSnapshot(
            action_id=action_id,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_namespace=resource_namespace,
            state_data=state_data,
            state_hash=state_hash,
            source=source,
        )
        
        async with self._lock:
            if action_id not in self._snapshots:
                self._snapshots[action_id] = []
            
            # Enforce max snapshots
            if len(self._snapshots[action_id]) >= self._max_snapshots_per_action:
                self._snapshots[action_id] = self._snapshots[action_id][1:]
            
            self._snapshots[action_id].append(snapshot)
        
        logger.debug(
            f"Captured state snapshot for {resource_type}/{resource_name} "
            f"(action={action_id}, hash={state_hash})"
        )
        
        return snapshot
    
    async def create_checkpoint(
        self,
        action_id: UUID,
        name: str,
        description: str = "",
        step_index: int = 0,
        snapshots: list[StateSnapshot] | None = None,
    ) -> RollbackCheckpoint:
        """
        Create a rollback checkpoint.
        
        Args:
            action_id: ID of the remediation action
            name: Checkpoint name
            description: Checkpoint description
            step_index: Step index in multi-step operation
            snapshots: Snapshots to include (defaults to all for action)
            
        Returns:
            Created checkpoint
        """
        if snapshots is None:
            snapshots = self._snapshots.get(action_id, [])
        
        checkpoint = RollbackCheckpoint(
            action_id=action_id,
            name=name,
            description=description,
            step_index=step_index,
            snapshots=list(snapshots),
            expires_at=datetime.utcnow() + timedelta(hours=self._max_checkpoint_age_hours),
        )
        
        async with self._lock:
            if action_id not in self._checkpoints:
                self._checkpoints[action_id] = []
            self._checkpoints[action_id].append(checkpoint)
        
        logger.info(
            f"Created checkpoint '{name}' for action {action_id} "
            f"with {len(snapshots)} snapshots"
        )
        
        return checkpoint
    
    async def get_latest_checkpoint(
        self,
        action_id: UUID,
    ) -> RollbackCheckpoint | None:
        """
        Get the latest valid checkpoint for an action.
        
        Args:
            action_id: ID of the remediation action
            
        Returns:
            Latest valid checkpoint or None
        """
        checkpoints = self._checkpoints.get(action_id, [])
        
        # Filter valid, non-expired checkpoints
        valid = [
            cp for cp in checkpoints
            if cp.is_valid and not cp.is_expired
        ]
        
        if not valid:
            return None
        
        # Return most recent
        return max(valid, key=lambda cp: cp.created_at)
    
    async def get_snapshots(
        self,
        action_id: UUID,
    ) -> list[StateSnapshot]:
        """
        Get all snapshots for an action.
        
        Args:
            action_id: ID of the remediation action
            
        Returns:
            List of snapshots
        """
        return list(self._snapshots.get(action_id, []))
    
    async def create_rollback_plan(
        self,
        action: RemediationAction,
    ) -> RollbackPlan:
        """
        Create a rollback plan for an action.
        
        Args:
            action: The remediation action to rollback
            
        Returns:
            Rollback plan
        """
        steps = []
        
        # Get checkpoints in reverse order
        checkpoints = self._checkpoints.get(action.id, [])
        valid_checkpoints = [
            cp for cp in reversed(checkpoints)
            if cp.is_valid and not cp.is_expired
        ]
        
        # Create steps from checkpoints
        for checkpoint in valid_checkpoints:
            for snapshot in checkpoint.snapshots:
                steps.append({
                    "type": "restore_state",
                    "checkpoint_id": str(checkpoint.id),
                    "snapshot_id": str(snapshot.id),
                    "resource_type": snapshot.resource_type,
                    "resource_name": snapshot.resource_name,
                    "resource_namespace": snapshot.resource_namespace,
                    "state_data": snapshot.state_data,
                })
        
        # If no checkpoints, try to use rollback data from action
        if not steps and action.rollback_data:
            steps.append({
                "type": "custom_rollback",
                "action_name": action.definition_name,
                "rollback_data": action.rollback_data,
            })
        
        plan = RollbackPlan(
            action_id=action.id,
            steps=steps,
            checkpoint_ids=[cp.id for cp in valid_checkpoints],
        )
        
        async with self._lock:
            self._rollback_plans[action.id] = plan
        
        logger.info(
            f"Created rollback plan for action {action.id} "
            f"with {len(steps)} steps"
        )
        
        return plan
    
    async def execute_rollback(
        self,
        action: RemediationAction,
        restore_handler: Callable[[str, str, str | None, dict], Awaitable[bool]] | None = None,
    ) -> RollbackResult:
        """
        Execute rollback for an action.
        
        Args:
            action: The remediation action to rollback
            restore_handler: Function to restore resource state
            
        Returns:
            Rollback result
        """
        start_time = datetime.utcnow()
        
        # Get or create plan
        plan = self._rollback_plans.get(action.id)
        if not plan:
            plan = await self.create_rollback_plan(action)
        
        if not plan.steps:
            logger.info(f"No rollback steps for action {action.id}")
            return RollbackResult(
                action_id=action.id,
                plan_id=plan.id,
                success=True,
                state=RollbackState.NOT_NEEDED,
                message="No rollback steps required",
                started_at=start_time,
            )
        
        plan.state = RollbackState.IN_PROGRESS
        plan.started_at = datetime.utcnow()
        
        errors = []
        steps_completed = 0
        steps_failed = 0
        restored_resources = []
        
        for i, step in enumerate(plan.steps):
            plan.current_step = i
            
            try:
                if step["type"] == "restore_state":
                    # Use provided handler or default
                    if restore_handler:
                        success = await restore_handler(
                            step["resource_type"],
                            step["resource_name"],
                            step.get("resource_namespace"),
                            step["state_data"],
                        )
                    else:
                        # No handler - mark as failed
                        success = False
                        logger.warning(
                            f"No restore handler for {step['resource_type']}/{step['resource_name']}"
                        )
                    
                    if success:
                        steps_completed += 1
                        resource_key = f"{step['resource_type']}/{step['resource_name']}"
                        if step.get("resource_namespace"):
                            resource_key = f"{step['resource_namespace']}/{resource_key}"
                        restored_resources.append(resource_key)
                    else:
                        steps_failed += 1
                        errors.append(
                            f"Failed to restore {step['resource_type']}/{step['resource_name']}"
                        )
                
                elif step["type"] == "custom_rollback":
                    action_name = step["action_name"]
                    handler = self._rollback_handlers.get(action_name)
                    
                    if handler:
                        success = await handler(step["rollback_data"])
                        if success:
                            steps_completed += 1
                        else:
                            steps_failed += 1
                            errors.append(f"Custom rollback failed for {action_name}")
                    else:
                        steps_failed += 1
                        errors.append(f"No rollback handler for {action_name}")
                
                else:
                    logger.warning(f"Unknown rollback step type: {step['type']}")
                    steps_failed += 1
                    errors.append(f"Unknown step type: {step['type']}")
                    
            except Exception as e:
                steps_failed += 1
                error_msg = f"Rollback step {i} failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        # Determine final state
        if steps_failed == 0:
            final_state = RollbackState.COMPLETED
            success = True
            message = f"Rollback completed successfully ({steps_completed} steps)"
        elif steps_completed > 0:
            final_state = RollbackState.COMPLETED
            success = False
            message = f"Rollback partially completed ({steps_completed}/{len(plan.steps)} steps)"
        else:
            final_state = RollbackState.FAILED
            success = False
            message = f"Rollback failed ({steps_failed} failures)"
        
        plan.state = final_state
        plan.steps_completed = steps_completed
        plan.steps_failed = steps_failed
        plan.errors = errors
        plan.completed_at = datetime.utcnow()
        
        result = RollbackResult(
            action_id=action.id,
            plan_id=plan.id,
            success=success,
            state=final_state,
            message=message,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            errors=errors,
            restored_resources=restored_resources,
            started_at=start_time,
        )
        
        logger.info(
            f"Rollback for action {action.id} {final_state.value}: {message}"
        )
        
        return result
    
    async def invalidate_checkpoints(
        self,
        action_id: UUID,
        reason: str = "Manual invalidation",
    ) -> int:
        """
        Invalidate all checkpoints for an action.
        
        Args:
            action_id: ID of the remediation action
            reason: Reason for invalidation
            
        Returns:
            Number of checkpoints invalidated
        """
        checkpoints = self._checkpoints.get(action_id, [])
        count = 0
        
        for checkpoint in checkpoints:
            if checkpoint.is_valid:
                checkpoint.is_valid = False
                checkpoint.invalidation_reason = reason
                count += 1
        
        if count:
            logger.info(f"Invalidated {count} checkpoints for action {action_id}: {reason}")
        
        return count
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired checkpoints and snapshots.
        
        Returns:
            Number of items cleaned up
        """
        count = 0
        now = datetime.utcnow()
        
        async with self._lock:
            # Clean up expired checkpoints
            for action_id in list(self._checkpoints.keys()):
                checkpoints = self._checkpoints[action_id]
                valid = [cp for cp in checkpoints if not cp.is_expired]
                count += len(checkpoints) - len(valid)
                
                if valid:
                    self._checkpoints[action_id] = valid
                else:
                    del self._checkpoints[action_id]
                    # Also clean up related snapshots
                    if action_id in self._snapshots:
                        count += len(self._snapshots[action_id])
                        del self._snapshots[action_id]
        
        if count:
            logger.info(f"Cleaned up {count} expired rollback items")
        
        return count
    
    def can_rollback(self, action: RemediationAction) -> tuple[bool, str]:
        """
        Check if an action can be rolled back.
        
        Args:
            action: The remediation action
            
        Returns:
            Tuple of (can_rollback, reason)
        """
        if not action.can_rollback:
            return False, "Action marked as not rollbackable"
        
        # Check for checkpoints
        checkpoints = self._checkpoints.get(action.id, [])
        valid_checkpoints = [cp for cp in checkpoints if cp.is_valid and not cp.is_expired]
        
        if valid_checkpoints:
            return True, f"{len(valid_checkpoints)} checkpoint(s) available"
        
        # Check for rollback data
        if action.rollback_data:
            action_name = action.definition_name
            if action_name in self._rollback_handlers:
                return True, "Rollback handler available"
            return False, "Rollback data exists but no handler"
        
        return False, "No checkpoints or rollback data available"
    
    def get_stats(self) -> dict[str, Any]:
        """Get rollback manager statistics."""
        total_snapshots = sum(len(s) for s in self._snapshots.values())
        total_checkpoints = sum(len(c) for c in self._checkpoints.values())
        
        valid_checkpoints = sum(
            1 for checkpoints in self._checkpoints.values()
            for cp in checkpoints
            if cp.is_valid and not cp.is_expired
        )
        
        return {
            "total_snapshots": total_snapshots,
            "total_checkpoints": total_checkpoints,
            "valid_checkpoints": valid_checkpoints,
            "registered_handlers": len(self._rollback_handlers),
            "active_plans": len(self._rollback_plans),
            "actions_with_snapshots": len(self._snapshots),
            "handler_names": list(self._rollback_handlers.keys()),
        }
