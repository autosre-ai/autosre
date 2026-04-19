"""Intelligent auto-remediation with approval workflows."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from opensre_core.agents.act import Action, ActionRisk
from opensre_core.config import settings
from opensre_core.security.audit import EventType, get_audit_logger


class ActionStatus(Enum):
    """Status of a queued action."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class QueuedAction:
    """An action in the remediation queue."""
    id: str
    action: Action
    investigation_id: str
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    rollback_command: Optional[str] = None
    original_state: Optional[dict[str, Any]] = None  # For intelligent rollbacks

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "action": {
                "id": self.action.id,
                "description": self.action.description,
                "command": self.action.command,
                "risk": self.action.risk.value if hasattr(self.action.risk, 'value') else str(self.action.risk),
                "requires_approval": self.action.requires_approval,
                "rationale": self.action.rationale,
            },
            "investigation_id": self.investigation_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "rollback_command": self.rollback_command,
            "can_rollback": self.rollback_command is not None,
        }


class RemediationManager:
    """
    Manages action execution with approval workflows.

    Features:
    - Auto-approve low-risk actions (configurable)
    - Queue medium/high-risk actions for human approval
    - Track action history for audit
    - Generate rollback commands where possible
    - Learn from outcomes (future enhancement)
    """

    def __init__(
        self,
        auto_approve_low_risk: bool = True,
        approval_timeout_minutes: int = 30,
        persist_path: Optional[Path] = None,
    ):
        self.auto_approve_low_risk = auto_approve_low_risk
        self.approval_timeout_minutes = approval_timeout_minutes
        self.persist_path = persist_path or Path("data/remediation_history.jsonl")

        self.queue: dict[str, QueuedAction] = {}
        self.history: list[QueuedAction] = []
        self.audit = get_audit_logger()
        self._approval_callbacks: dict[str, asyncio.Future] = {}

        # Stats tracking
        self._stats = {
            "total_queued": 0,
            "auto_approved": 0,
            "manually_approved": 0,
            "rejected": 0,
            "executed": 0,
            "failed": 0,
            "rolled_back": 0,
        }

        # Load history if persistence is enabled
        self._load_history()

    def _load_history(self) -> None:
        """Load action history from disk."""
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path) as f:
                for _line in f:
                    # History is stored as JSON lines - skip for now
                    # Full implementation would reconstruct QueuedAction objects
                    pass
        except Exception:
            pass  # Ignore load errors, start fresh

    def _persist_action(self, action: QueuedAction) -> None:
        """Persist action to disk."""
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.persist_path, "a") as f:
            f.write(json.dumps(action.to_dict()) + "\n")

    async def queue_action(
        self,
        action: Action,
        investigation_id: str,
        user: str = "system",
    ) -> QueuedAction:
        """
        Queue an action for execution or approval.

        Args:
            action: The action to queue
            investigation_id: ID of the related investigation
            user: User who initiated the action

        Returns:
            The queued action
        """
        # Capture original state if possible (for rollback)
        original_state = await self._capture_state(action)

        queued = QueuedAction(
            id=str(uuid4()),
            action=action,
            investigation_id=investigation_id,
            rollback_command=self._generate_rollback(action),
            original_state=original_state,
        )

        self.queue[queued.id] = queued
        self._stats["total_queued"] += 1

        # Determine risk level
        risk = action.risk if hasattr(action.risk, 'value') else ActionRisk(action.risk)

        # Auto-approve low-risk actions if configured
        if self.auto_approve_low_risk and risk == ActionRisk.LOW:
            self._stats["auto_approved"] += 1
            await self.approve(queued.id, "system:auto-approve")
            await self.execute(queued.id)
        else:
            # Log that action requires approval
            self.audit.log(
                EventType.ACTION_PROPOSED,
                user=user,
                action=f"Queued action for approval: {queued.id}",
                details={
                    "action_id": queued.id,
                    "risk": risk.value,
                    "command": action.command,
                    "requires_approval": True,
                },
            )

        return queued

    async def approve(self, action_id: str, approved_by: str) -> QueuedAction:
        """
        Approve a queued action.

        Args:
            action_id: ID of the action to approve
            approved_by: Username of the approver

        Returns:
            The approved action

        Raises:
            ValueError: If action not found or not pending
        """
        if action_id not in self.queue:
            raise ValueError(f"Action {action_id} not found")

        queued = self.queue[action_id]

        if queued.status != ActionStatus.PENDING:
            raise ValueError(f"Action {action_id} is not pending (status: {queued.status.value})")

        queued.status = ActionStatus.APPROVED
        queued.approved_by = approved_by
        queued.approved_at = datetime.now()

        if approved_by != "system:auto-approve":
            self._stats["manually_approved"] += 1

        self.audit.log_action_approved(
            user=approved_by,
            action_id=action_id,
            command=queued.action.command,
            approved_by=approved_by,
        )

        # Resolve approval future if waiting
        if action_id in self._approval_callbacks:
            self._approval_callbacks[action_id].set_result(True)

        return queued

    async def reject(
        self,
        action_id: str,
        rejected_by: str,
        reason: str = "",
    ) -> QueuedAction:
        """
        Reject a queued action.

        Args:
            action_id: ID of the action to reject
            rejected_by: Username of the rejector
            reason: Reason for rejection

        Returns:
            The rejected action
        """
        if action_id not in self.queue:
            raise ValueError(f"Action {action_id} not found")

        queued = self.queue[action_id]
        queued.status = ActionStatus.REJECTED
        queued.error = f"Rejected by {rejected_by}: {reason}"
        queued.completed_at = datetime.now()

        self._stats["rejected"] += 1

        self.audit.log_action_rejected(
            user=rejected_by,
            action_id=action_id,
            reason=reason,
        )

        # Move to history
        self.history.append(queued)
        self._persist_action(queued)
        del self.queue[action_id]

        # Resolve approval future if waiting
        if action_id in self._approval_callbacks:
            future = self._approval_callbacks[action_id]
            if not future.done():
                future.set_result(False)

        return queued

    async def execute(self, action_id: str) -> QueuedAction:
        """
        Execute an approved action.

        Args:
            action_id: ID of the action to execute

        Returns:
            The executed action with results

        Raises:
            ValueError: If action not found or not approved
        """
        if action_id not in self.queue:
            raise ValueError(f"Action {action_id} not found")

        queued = self.queue[action_id]

        if queued.status != ActionStatus.APPROVED:
            raise ValueError(f"Action {action_id} is not approved (status: {queued.status.value})")

        queued.status = ActionStatus.EXECUTING
        queued.executed_at = datetime.now()

        try:
            result = await self._execute_command(queued.action.command)

            queued.status = ActionStatus.COMPLETED
            queued.completed_at = datetime.now()
            queued.result = result

            self._stats["executed"] += 1

            self.audit.log_action_executed(
                user=queued.approved_by or "system",
                action_id=action_id,
                command=queued.action.command,
                exit_code=0,
                approved_by=queued.approved_by or "system",
            )

        except Exception as e:
            queued.status = ActionStatus.FAILED
            queued.completed_at = datetime.now()
            queued.error = str(e)

            self._stats["failed"] += 1

            self.audit.log(
                EventType.ACTION_FAILED,
                user=queued.approved_by or "system",
                action=f"Failed to execute action: {action_id}",
                details={"action_id": action_id, "error": str(e)},
                result="failure",
            )

        # Move to history
        self.history.append(queued)
        self._persist_action(queued)
        del self.queue[action_id]

        return queued

    async def _execute_command(self, command: str) -> str:
        """
        Execute a kubectl command.

        Args:
            command: The kubectl command to execute

        Returns:
            Command output

        Raises:
            RuntimeError: If command fails
        """
        import asyncio

        # Security check - only kubectl commands allowed
        if not command.strip().startswith("kubectl"):
            raise ValueError("Only kubectl commands are supported")

        # Execute
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else f"Command failed with exit code {proc.returncode}"
            raise RuntimeError(error_msg)

        return stdout.decode() if stdout else ""

    async def rollback(self, action_id: str, user: str = "system") -> Optional[str]:
        """
        Rollback a completed action.

        Args:
            action_id: ID of the action to rollback
            user: User requesting the rollback

        Returns:
            Rollback command output, or None if rollback not available
        """
        # Find in history
        action = next((a for a in self.history if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action {action_id} not found in history")

        if not action.rollback_command:
            return None

        if action.status == ActionStatus.ROLLED_BACK:
            raise ValueError(f"Action {action_id} has already been rolled back")

        try:
            result = await self._execute_command(action.rollback_command)
            action.status = ActionStatus.ROLLED_BACK

            self._stats["rolled_back"] += 1

            self.audit.log(
                "action.rollback",
                user=user,
                action=f"Rolled back action: {action_id}",
                details={
                    "action_id": action_id,
                    "rollback_command": action.rollback_command,
                },
            )

            return result

        except Exception as e:
            self.audit.log(
                "action.rollback_failed",
                user=user,
                action=f"Failed to rollback action: {action_id}",
                details={"action_id": action_id, "error": str(e)},
                result="failure",
            )
            raise

    async def wait_for_approval(self, action_id: str, timeout: Optional[int] = None) -> bool:
        """
        Wait for action approval with timeout.

        Args:
            action_id: ID of the action to wait for
            timeout: Timeout in seconds (defaults to approval_timeout_minutes)

        Returns:
            True if approved, False if rejected or timed out
        """
        timeout = timeout or (self.approval_timeout_minutes * 60)

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._approval_callbacks[action_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            await self.reject(action_id, "system:timeout", "Approval timed out")
            return False
        finally:
            self._approval_callbacks.pop(action_id, None)

    async def _capture_state(self, action: Action) -> Optional[dict[str, Any]]:
        """
        Capture current state before action execution for rollback.

        Args:
            action: The action about to be executed

        Returns:
            State dictionary, or None if not applicable
        """
        cmd = action.command

        # Scale operations - capture current replicas
        if "scale" in cmd and "--replicas" in cmd:
            try:
                import re
                # Extract deployment name and namespace from command
                # kubectl scale deployment/NAME --replicas=N -n NAMESPACE
                deploy_match = re.search(r'deployment[/\s]+(\S+)', cmd)
                ns_match = re.search(r'-n[s]?\s+(\S+)|--namespace[=\s]+(\S+)', cmd)

                if deploy_match:
                    deployment = deploy_match.group(1)
                    namespace = ns_match.group(1) or ns_match.group(2) if ns_match else "default"

                    # Get current replicas
                    from opensre_core.adapters.kubernetes import KubernetesAdapter
                    k8s = KubernetesAdapter()
                    deploy_info = await k8s.get_deployment(deployment, namespace)

                    return {
                        "type": "scale",
                        "deployment": deployment,
                        "namespace": namespace,
                        "original_replicas": deploy_info.replicas,
                    }
            except Exception:
                pass  # State capture failed, continue without it

        return None

    def _generate_rollback(self, action: Action) -> Optional[str]:
        """
        Generate rollback command for an action.

        Args:
            action: The action to generate rollback for

        Returns:
            Rollback command string, or None if not possible
        """
        cmd = action.command

        # Rollout restart - can rollout undo
        if "rollout restart" in cmd:
            return cmd.replace("rollout restart", "rollout undo")

        # Scale operations - need original state (handled at execution time)
        if "scale" in cmd and "--replicas" in cmd:
            # Note: This will be updated with actual value if state capture succeeds
            return None

        # Delete pod - no rollback needed (controller will recreate)
        if "delete pod" in cmd:
            return None

        # Patch operations - would need to store original value
        if "patch" in cmd:
            return None  # TODO: Implement with state capture

        # Apply - would need to store original manifest
        if "apply" in cmd:
            return None  # TODO: Implement with state capture

        return None

    def get_pending(self) -> list[QueuedAction]:
        """Get all pending actions."""
        return [a for a in self.queue.values() if a.status == ActionStatus.PENDING]

    def get_by_investigation(self, investigation_id: str) -> list[QueuedAction]:
        """Get all actions for an investigation."""
        queued = [a for a in self.queue.values() if a.investigation_id == investigation_id]
        historical = [a for a in self.history if a.investigation_id == investigation_id]
        return queued + historical

    def get_stats(self) -> dict[str, Any]:
        """
        Get remediation statistics.

        Returns:
            Dictionary with stats
        """
        # Calculate from history for accuracy
        completed = sum(1 for a in self.history if a.status == ActionStatus.COMPLETED)
        failed = sum(1 for a in self.history if a.status == ActionStatus.FAILED)
        rejected = sum(1 for a in self.history if a.status == ActionStatus.REJECTED)
        rolled_back = sum(1 for a in self.history if a.status == ActionStatus.ROLLED_BACK)

        return {
            "pending": len(self.get_pending()),
            "in_queue": len(self.queue),
            "total_executed": completed,
            "total_failed": failed,
            "total_rejected": rejected,
            "total_rolled_back": rolled_back,
            "total_in_history": len(self.history),
            "success_rate": f"{completed / (completed + failed) * 100:.1f}%" if (completed + failed) > 0 else "N/A",
        }

    def get_action(self, action_id: str) -> Optional[QueuedAction]:
        """Get an action by ID (from queue or history)."""
        if action_id in self.queue:
            return self.queue[action_id]
        return next((a for a in self.history if a.id == action_id), None)

    def get_recent(self, limit: int = 20) -> list[QueuedAction]:
        """Get recent actions from history."""
        return self.history[-limit:][::-1]  # Most recent first


# Global instance (singleton pattern)
_manager: Optional[RemediationManager] = None


def get_remediation_manager() -> RemediationManager:
    """Get or create the global remediation manager."""
    global _manager
    if _manager is None:
        _manager = RemediationManager(
            auto_approve_low_risk=settings.auto_approve_low_risk if hasattr(settings, 'auto_approve_low_risk') else True,
            approval_timeout_minutes=30,
        )
    return _manager
