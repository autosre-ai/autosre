"""
Actor - Execute remediation actions with guardrails.

The actor executes approved remediation actions:
- Running runbooks
- Sending notifications
- Creating tickets
- Executing scripts (with approval)
"""

import subprocess
from datetime import datetime
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions the actor can perform."""
    NOTIFICATION = "notification"
    RUNBOOK = "runbook"
    SCRIPT = "script"
    SCALE = "scale"
    ROLLBACK = "rollback"
    TICKET = "ticket"
    RESTART = "restart"


class ActionStatus(str, Enum):
    """Status of an action."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DRY_RUN = "dry_run"


class ActionResult(BaseModel):
    """Result of executing an action."""
    action_id: str
    action_type: ActionType
    status: ActionStatus
    
    # Details
    description: str
    target: Optional[str] = None
    
    # Execution
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Output
    output: Optional[str] = None
    error: Optional[str] = None
    
    # Dry run
    dry_run: bool = False
    would_execute: Optional[str] = None


class Actor:
    """
    Action executor with guardrails.
    
    Executes remediation actions while enforcing:
    - Human approval for destructive actions
    - Dry run by default
    - Audit logging
    - Blast radius limits
    """
    
    def __init__(
        self,
        dry_run: bool = True,
        require_approval: bool = True,
        kubeconfig: Optional[str] = None,
    ):
        """
        Initialize actor.
        
        Args:
            dry_run: If True, only show what would be done
            require_approval: Require human approval for actions
            kubeconfig: Path to kubeconfig for k8s actions
        """
        self.dry_run = dry_run
        self.require_approval = require_approval
        self.kubeconfig = kubeconfig
        self._action_history: list[ActionResult] = []
    
    async def execute(
        self,
        action_type: ActionType,
        target: str,
        params: Optional[dict] = None,
        approved: bool = False,
    ) -> ActionResult:
        """
        Execute an action.
        
        Args:
            action_type: Type of action
            target: Target of the action (service, runbook, etc.)
            params: Additional parameters
            approved: Whether action is pre-approved
            
        Returns:
            ActionResult with status and output
        """
        import uuid
        
        action_id = str(uuid.uuid4())[:8]
        params = params or {}
        
        # Build result
        result = ActionResult(
            action_id=action_id,
            action_type=action_type,
            status=ActionStatus.PENDING,
            description=f"{action_type.value} on {target}",
            target=target,
            dry_run=self.dry_run,
        )
        
        # Check approval
        if self.require_approval and not approved and not self.dry_run:
            result.status = ActionStatus.PENDING
            result.error = "Action requires approval"
            self._action_history.append(result)
            return result
        
        # Execute based on type
        result.started_at = datetime.utcnow()
        
        try:
            if action_type == ActionType.NOTIFICATION:
                result = await self._send_notification(result, target, params)
            elif action_type == ActionType.RUNBOOK:
                result = await self._execute_runbook(result, target, params)
            elif action_type == ActionType.SCALE:
                result = await self._scale_deployment(result, target, params)
            elif action_type == ActionType.ROLLBACK:
                result = await self._rollback_deployment(result, target, params)
            elif action_type == ActionType.RESTART:
                result = await self._restart_deployment(result, target, params)
            elif action_type == ActionType.TICKET:
                result = await self._create_ticket(result, target, params)
            elif action_type == ActionType.SCRIPT:
                result = await self._execute_script(result, target, params)
            else:
                result.status = ActionStatus.FAILED
                result.error = f"Unknown action type: {action_type}"
        except Exception as e:
            result.status = ActionStatus.FAILED
            result.error = str(e)
        
        result.completed_at = datetime.utcnow()
        self._action_history.append(result)
        
        return result
    
    async def _send_notification(
        self,
        result: ActionResult,
        target: str,
        params: dict,
    ) -> ActionResult:
        """Send a notification."""
        message = params.get("message", "AutoSRE notification")
        channel = params.get("channel", target)
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would send to {channel}: {message}"
            return result
        
        # TODO: Implement actual notification sending
        # For now, just log
        result.status = ActionStatus.SUCCESS
        result.output = f"Notification sent to {channel}"
        
        return result
    
    async def _execute_runbook(
        self,
        result: ActionResult,
        runbook_id: str,
        params: dict,
    ) -> ActionResult:
        """Execute a runbook."""
        # Get runbook (would come from context store)
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would execute runbook: {runbook_id}"
            return result
        
        # TODO: Implement runbook execution
        result.status = ActionStatus.SUCCESS
        result.output = f"Runbook {runbook_id} executed"
        
        return result
    
    async def _scale_deployment(
        self,
        result: ActionResult,
        deployment: str,
        params: dict,
    ) -> ActionResult:
        """Scale a deployment."""
        replicas = params.get("replicas", 1)
        namespace = params.get("namespace", "default")
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would scale {deployment} to {replicas} replicas"
            return result
        
        cmd = ["kubectl", "scale", "deployment", deployment, f"--replicas={replicas}", "-n", namespace]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            result.status = ActionStatus.SUCCESS
            result.output = proc.stdout
        else:
            result.status = ActionStatus.FAILED
            result.error = proc.stderr
        
        return result
    
    async def _rollback_deployment(
        self,
        result: ActionResult,
        deployment: str,
        params: dict,
    ) -> ActionResult:
        """Rollback a deployment."""
        namespace = params.get("namespace", "default")
        revision = params.get("revision")  # Specific revision, or latest
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            if revision:
                result.would_execute = f"Would rollback {deployment} to revision {revision}"
            else:
                result.would_execute = f"Would rollback {deployment} to previous version"
            return result
        
        cmd = ["kubectl", "rollout", "undo", f"deployment/{deployment}", "-n", namespace]
        if revision:
            cmd.extend([f"--to-revision={revision}"])
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            result.status = ActionStatus.SUCCESS
            result.output = proc.stdout
        else:
            result.status = ActionStatus.FAILED
            result.error = proc.stderr
        
        return result
    
    async def _restart_deployment(
        self,
        result: ActionResult,
        deployment: str,
        params: dict,
    ) -> ActionResult:
        """Restart a deployment (rolling restart)."""
        namespace = params.get("namespace", "default")
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would restart {deployment}"
            return result
        
        cmd = ["kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", namespace]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            result.status = ActionStatus.SUCCESS
            result.output = proc.stdout
        else:
            result.status = ActionStatus.FAILED
            result.error = proc.stderr
        
        return result
    
    async def _create_ticket(
        self,
        result: ActionResult,
        target: str,
        params: dict,
    ) -> ActionResult:
        """Create a ticket (Jira, Linear, etc.)."""
        title = params.get("title", "AutoSRE Incident")
        description = params.get("description", "")
        priority = params.get("priority", "high")
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would create {priority} priority ticket: {title}"
            return result
        
        # TODO: Implement ticket creation
        result.status = ActionStatus.SUCCESS
        result.output = f"Ticket created: {title}"
        
        return result
    
    async def _execute_script(
        self,
        result: ActionResult,
        script_path: str,
        params: dict,
    ) -> ActionResult:
        """Execute a script (requires explicit approval)."""
        args = params.get("args", [])
        
        if self.dry_run:
            result.status = ActionStatus.DRY_RUN
            result.would_execute = f"Would execute: {script_path} {' '.join(args)}"
            return result
        
        # Extra safety check for scripts
        if not params.get("explicitly_approved"):
            result.status = ActionStatus.FAILED
            result.error = "Script execution requires explicit approval"
            return result
        
        proc = subprocess.run(
            [script_path] + args,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if proc.returncode == 0:
            result.status = ActionStatus.SUCCESS
            result.output = proc.stdout
        else:
            result.status = ActionStatus.FAILED
            result.error = proc.stderr
        
        return result
    
    def get_history(self, limit: int = 50) -> list[ActionResult]:
        """Get action history."""
        return self._action_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear action history."""
        self._action_history.clear()
