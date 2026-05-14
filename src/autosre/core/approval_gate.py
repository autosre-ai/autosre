"""
Human Approval Gate for AutoSRE.

MANDATORY human approval for ALL actions - no auto-execution ever.

Flow:
1. AI analyzes alert + runbooks
2. AI proposes action with confidence + reasoning
3. Posts to notification channel for approval
4. Human approves/rejects/modifies
5. Only then execute
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.core.audit import AuditEventType, audit, get_audit_trail
from autosre.core.confidence import ConfidenceScore
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class ApprovalState(str, Enum):
    """State machine for approval workflow."""
    
    PENDING = "pending"          # Awaiting human decision
    APPROVED = "approved"        # Human approved
    REJECTED = "rejected"        # Human rejected  
    MODIFIED = "modified"        # Human modified then approved
    TIMEOUT = "timeout"          # No response within timeout
    ESCALATED = "escalated"      # Escalated to higher authority
    EXECUTED = "executed"        # Action was executed
    SKIPPED = "skipped"          # Action was skipped


class NotificationChannel(str, Enum):
    """Channels for sending approval requests."""
    
    SLACK = "slack"
    TELEGRAM = "telegram"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CLI = "cli"  # For CLI-based approval


@dataclass
class ApprovalConfig:
    """Configuration for approval workflow."""
    
    # Timeout settings
    initial_timeout_minutes: int = 30
    escalation_timeout_minutes: int = 15
    max_escalations: int = 3
    
    # Notification settings  
    notification_channels: list[NotificationChannel] = None
    slack_channel: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None
    
    # Escalation chain
    escalation_contacts: list[str] = None  # Contact IDs in order
    
    # Behavior
    require_reason_on_reject: bool = True
    allow_modification: bool = True
    auto_escalate_critical: bool = True
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = [NotificationChannel.CLI]
        if self.escalation_contacts is None:
            self.escalation_contacts = []


class ProposedAction(BaseModel):
    """An action proposed by AI awaiting human approval."""
    
    id: UUID = Field(default_factory=uuid4)
    
    # What's being proposed
    action_type: str = Field(..., description="Type of action (restart, scale, etc)")
    action_name: str = Field(..., description="Human-readable action name")
    action_description: str = Field(..., description="What this action will do")
    
    # Target
    target_type: str = Field(..., description="Target resource type")
    target_name: str = Field(..., description="Target resource name")
    target_namespace: str | None = None
    target_cluster: str | None = None
    
    # Parameters
    parameters: dict[str, Any] = Field(default_factory=dict)
    original_parameters: dict[str, Any] = Field(default_factory=dict)  # Before modification
    
    # Context
    alert_id: UUID | None = None
    alert_name: str | None = None
    investigation_id: UUID | None = None
    
    # AI Decision Details
    confidence: ConfidenceScore | None = None
    
    # Runbook reference
    runbook_id: str | None = None
    runbook_name: str | None = None
    runbook_step: str | None = None
    
    # Risk assessment
    risk_level: str = "medium"
    blast_radius_summary: str | None = None
    estimated_impact: str | None = None
    rollback_available: bool = True
    
    # State
    state: ApprovalState = ApprovalState.PENDING
    
    # Approval details
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    modification_notes: str | None = None
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    escalation_count: int = 0
    
    # Execution
    executed_at: datetime | None = None
    execution_result: str | None = None
    
    @property
    def is_pending(self) -> bool:
        return self.state == ApprovalState.PENDING
    
    @property
    def is_decided(self) -> bool:
        return self.state in [
            ApprovalState.APPROVED, 
            ApprovalState.REJECTED,
            ApprovalState.MODIFIED,
            ApprovalState.TIMEOUT,
        ]
    
    @property
    def can_execute(self) -> bool:
        return self.state in [ApprovalState.APPROVED, ApprovalState.MODIFIED]
    
    @property
    def time_remaining_seconds(self) -> float:
        if not self.expires_at:
            return float("inf")
        return max(0, (self.expires_at - datetime.now(timezone.utc)).total_seconds())
    
    def format_for_notification(self) -> str:
        """Format action for human-readable notification."""
        lines = [
            "🚨 **ACTION REQUIRES APPROVAL**",
            "",
            f"**Action:** {self.action_name}",
            f"**Target:** {self.target_type}/{self.target_namespace or 'default'}/{self.target_name}",
            "",
            f"**Description:** {self.action_description}",
            "",
        ]
        
        if self.confidence:
            lines.extend([
                f"**AI Confidence:** {self.confidence.score:.1f}% ({self.confidence.level.value})",
                "",
                "**Reasoning:**",
                self.confidence.reasoning,
                "",
            ])
        
        if self.alert_name:
            lines.append(f"**Triggered by alert:** {self.alert_name}")
        
        if self.runbook_name:
            lines.append(f"**From runbook:** {self.runbook_name}")
        
        lines.extend([
            "",
            f"**Risk Level:** {self.risk_level.upper()}",
        ])
        
        if self.blast_radius_summary:
            lines.append(f"**Blast Radius:** {self.blast_radius_summary}")
        
        if self.estimated_impact:
            lines.append(f"**Estimated Impact:** {self.estimated_impact}")
        
        lines.extend([
            "",
            f"**Rollback Available:** {'✅ Yes' if self.rollback_available else '❌ No'}",
            "",
            f"⏰ Expires in: {int(self.time_remaining_seconds / 60)} minutes",
            "",
            "---",
            f"ID: `{str(self.id)[:8]}`",
            "",
            "Reply with:",
            "• `approve {id}` - Approve this action",
            "• `reject {id} <reason>` - Reject with reason", 
            "• `modify {id} <changes>` - Modify and approve",
        ])
        
        return "\n".join(lines)


# Type for notification sender
NotificationSender = Callable[[str, str, dict[str, Any]], Awaitable[bool]]

# Type for approval callback
ApprovalCallback = Callable[[ProposedAction], Awaitable[None]]


class HumanApprovalGate:
    """
    Human-in-the-loop approval gate.
    
    ALL actions MUST go through this gate. No auto-execution ever.
    
    Example:
        >>> gate = HumanApprovalGate(config)
        >>> 
        >>> # Propose an action
        >>> proposal = await gate.propose_action(
        ...     action_type="restart",
        ...     action_name="Restart payment-service",
        ...     action_description="Restart all pods in payment-service deployment",
        ...     target_type="deployment",
        ...     target_name="payment-service",
        ...     confidence=confidence_score,
        ...     alert_id=alert.id,
        ... )
        >>> 
        >>> # Wait for human decision
        >>> await gate.wait_for_decision(proposal.id, timeout_minutes=30)
        >>> 
        >>> # Check result
        >>> if proposal.can_execute:
        ...     await execute_action(proposal)
    """
    
    def __init__(self, config: ApprovalConfig | None = None):
        self.config = config or ApprovalConfig()
        
        # State
        self._pending: dict[UUID, ProposedAction] = {}
        self._history: list[ProposedAction] = []
        
        # Notification handlers
        self._notifiers: dict[NotificationChannel, NotificationSender] = {}
        
        # Callbacks
        self._on_approved: list[ApprovalCallback] = []
        self._on_rejected: list[ApprovalCallback] = []
        
        # Escalation tasks
        self._escalation_tasks: dict[UUID, asyncio.Task] = {}
        
        self._lock = asyncio.Lock()
    
    def register_notifier(
        self,
        channel: NotificationChannel,
        sender: NotificationSender,
    ) -> None:
        """Register a notification sender for a channel."""
        self._notifiers[channel] = sender
        logger.info(f"Registered notifier for {channel.value}")
    
    def on_approved(self, callback: ApprovalCallback) -> None:
        """Register callback for when action is approved."""
        self._on_approved.append(callback)
    
    def on_rejected(self, callback: ApprovalCallback) -> None:
        """Register callback for when action is rejected."""
        self._on_rejected.append(callback)
    
    async def propose_action(
        self,
        action_type: str,
        action_name: str,
        action_description: str,
        target_type: str,
        target_name: str,
        target_namespace: str | None = None,
        target_cluster: str | None = None,
        parameters: dict[str, Any] | None = None,
        alert_id: UUID | None = None,
        alert_name: str | None = None,
        investigation_id: UUID | None = None,
        confidence: ConfidenceScore | None = None,
        runbook_id: str | None = None,
        runbook_name: str | None = None,
        runbook_step: str | None = None,
        risk_level: str = "medium",
        blast_radius_summary: str | None = None,
        estimated_impact: str | None = None,
        rollback_available: bool = True,
        timeout_minutes: int | None = None,
    ) -> ProposedAction:
        """
        Propose an action for human approval.
        
        This is the ONLY way to get an action executed.
        
        Args:
            action_type: Type of action
            action_name: Human-readable name
            action_description: What the action will do
            target_type: Type of target resource
            target_name: Name of target
            target_namespace: Kubernetes namespace
            target_cluster: Cluster name
            parameters: Action parameters
            alert_id: Associated alert
            alert_name: Alert name
            investigation_id: Associated investigation
            confidence: AI confidence score
            runbook_id: Source runbook ID
            runbook_name: Source runbook name
            runbook_step: Specific runbook step
            risk_level: Risk level (low/medium/high/critical)
            blast_radius_summary: Blast radius description
            estimated_impact: Estimated impact
            rollback_available: Whether rollback is available
            timeout_minutes: Override timeout
            
        Returns:
            ProposedAction instance
        """
        timeout = timeout_minutes or self.config.initial_timeout_minutes
        
        proposal = ProposedAction(
            action_type=action_type,
            action_name=action_name,
            action_description=action_description,
            target_type=target_type,
            target_name=target_name,
            target_namespace=target_namespace,
            target_cluster=target_cluster,
            parameters=parameters or {},
            original_parameters=parameters.copy() if parameters else {},
            alert_id=alert_id,
            alert_name=alert_name,
            investigation_id=investigation_id,
            confidence=confidence,
            runbook_id=runbook_id,
            runbook_name=runbook_name,
            runbook_step=runbook_step,
            risk_level=risk_level,
            blast_radius_summary=blast_radius_summary,
            estimated_impact=estimated_impact,
            rollback_available=rollback_available,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=timeout),
        )
        
        async with self._lock:
            self._pending[proposal.id] = proposal
        
        # Audit
        audit(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            summary=f"Approval requested: {action_name}",
            alert_id=alert_id,
            investigation_id=investigation_id,
            action_id=proposal.id,
            confidence_score=confidence.score if confidence else None,
            confidence_level=confidence.level.value if confidence else None,
            reasoning=confidence.reasoning if confidence else None,
            details={
                "action_type": action_type,
                "target": f"{target_type}/{target_namespace}/{target_name}",
                "risk_level": risk_level,
                "timeout_minutes": timeout,
            },
        )
        
        logger.info(
            f"Action proposed for approval: {action_name} "
            f"(confidence: {confidence.score:.1f}% if confidence else 'N/A'})"
        )
        
        # Send notifications
        await self._send_notifications(proposal)
        
        # Start escalation timer
        self._start_escalation_timer(proposal)
        
        return proposal
    
    async def _send_notifications(self, proposal: ProposedAction) -> None:
        """Send notifications to all configured channels."""
        message = proposal.format_for_notification()
        
        for channel in self.config.notification_channels:
            sender = self._notifiers.get(channel)
            if sender:
                try:
                    success = await sender(
                        str(proposal.id),
                        message,
                        {
                            "alert_id": str(proposal.alert_id) if proposal.alert_id else None,
                            "risk_level": proposal.risk_level,
                            "confidence": proposal.confidence.score if proposal.confidence else None,
                        },
                    )
                    if success:
                        logger.info(f"Sent approval request to {channel.value}")
                    else:
                        logger.warning(f"Failed to send to {channel.value}")
                except Exception as e:
                    logger.error(f"Error sending to {channel.value}: {e}")
            else:
                # CLI fallback
                if channel == NotificationChannel.CLI:
                    logger.info(f"\n{message}\n")
    
    def _start_escalation_timer(self, proposal: ProposedAction) -> None:
        """Start escalation timer."""
        async def escalate():
            await asyncio.sleep(self.config.escalation_timeout_minutes * 60)
            
            if proposal.is_pending:
                await self._escalate(proposal)
        
        task = asyncio.create_task(escalate())
        self._escalation_tasks[proposal.id] = task
    
    async def _escalate(self, proposal: ProposedAction) -> None:
        """Escalate to next contact in chain."""
        if proposal.escalation_count >= self.config.max_escalations:
            # Max escalations reached - timeout
            await self._handle_timeout(proposal)
            return
        
        proposal.escalation_count += 1
        proposal.state = ApprovalState.ESCALATED
        
        # Extend timeout
        proposal.expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.config.escalation_timeout_minutes
        )
        
        audit(
            event_type=AuditEventType.APPROVAL_ESCALATED,
            summary=f"Escalated: {proposal.action_name} (level {proposal.escalation_count})",
            action_id=proposal.id,
            alert_id=proposal.alert_id,
            details={
                "escalation_level": proposal.escalation_count,
                "max_escalations": self.config.max_escalations,
            },
        )
        
        logger.warning(
            f"Escalating approval request {proposal.id} "
            f"(level {proposal.escalation_count})"
        )
        
        # Reset to pending and re-notify
        proposal.state = ApprovalState.PENDING
        await self._send_notifications(proposal)
        
        # Start new escalation timer
        self._start_escalation_timer(proposal)
    
    async def _handle_timeout(self, proposal: ProposedAction) -> None:
        """Handle timeout - no approval received."""
        proposal.state = ApprovalState.TIMEOUT
        
        async with self._lock:
            self._pending.pop(proposal.id, None)
            self._history.append(proposal)
        
        audit(
            event_type=AuditEventType.APPROVAL_EXPIRED,
            summary=f"Approval timeout: {proposal.action_name}",
            action_id=proposal.id,
            alert_id=proposal.alert_id,
            severity=AuditSeverity.WARNING,
            details={
                "escalation_count": proposal.escalation_count,
            },
        )
        
        logger.warning(f"Approval request {proposal.id} timed out")
    
    async def approve(
        self,
        proposal_id: UUID | str,
        approved_by: str,
        notes: str | None = None,
    ) -> bool:
        """
        Approve a proposed action.
        
        Args:
            proposal_id: Proposal ID
            approved_by: Who is approving (user ID/name)
            notes: Optional approval notes
            
        Returns:
            True if approval was recorded
        """
        if isinstance(proposal_id, str):
            # Handle short ID
            proposal_id = self._find_by_short_id(proposal_id)
            if not proposal_id:
                logger.warning(f"Proposal not found: {proposal_id}")
                return False
        
        async with self._lock:
            proposal = self._pending.get(proposal_id)
            if not proposal:
                logger.warning(f"Proposal {proposal_id} not found or already decided")
                return False
            
            if not proposal.is_pending:
                logger.warning(f"Proposal {proposal_id} already in state {proposal.state}")
                return False
            
            proposal.state = ApprovalState.APPROVED
            proposal.approved_by = approved_by
            proposal.approved_at = datetime.now(timezone.utc)
            proposal.modification_notes = notes
            
            self._pending.pop(proposal_id, None)
            self._history.append(proposal)
        
        # Cancel escalation
        if proposal_id in self._escalation_tasks:
            self._escalation_tasks[proposal_id].cancel()
            del self._escalation_tasks[proposal_id]
        
        audit(
            event_type=AuditEventType.APPROVAL_GRANTED,
            summary=f"Approved: {proposal.action_name}",
            action_id=proposal.id,
            alert_id=proposal.alert_id,
            actor=approved_by,
            actor_type="user",
            confidence_score=proposal.confidence.score if proposal.confidence else None,
            details={
                "notes": notes,
                "time_to_approval_seconds": (
                    proposal.approved_at - proposal.created_at
                ).total_seconds(),
            },
        )
        
        logger.info(f"Action approved: {proposal.action_name} by {approved_by}")
        
        # Invoke callbacks
        for callback in self._on_approved:
            try:
                await callback(proposal)
            except Exception as e:
                logger.error(f"Error in approval callback: {e}")
        
        return True
    
    async def reject(
        self,
        proposal_id: UUID | str,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """
        Reject a proposed action.
        
        Args:
            proposal_id: Proposal ID
            rejected_by: Who is rejecting
            reason: Rejection reason (required)
            
        Returns:
            True if rejection was recorded
        """
        if isinstance(proposal_id, str):
            proposal_id = self._find_by_short_id(proposal_id)
            if not proposal_id:
                return False
        
        if self.config.require_reason_on_reject and not reason:
            logger.warning("Rejection reason required")
            return False
        
        async with self._lock:
            proposal = self._pending.get(proposal_id)
            if not proposal or not proposal.is_pending:
                return False
            
            proposal.state = ApprovalState.REJECTED
            proposal.approved_by = rejected_by  # Track who decided
            proposal.rejection_reason = reason
            
            self._pending.pop(proposal_id, None)
            self._history.append(proposal)
        
        # Cancel escalation
        if proposal_id in self._escalation_tasks:
            self._escalation_tasks[proposal_id].cancel()
            del self._escalation_tasks[proposal_id]
        
        audit(
            event_type=AuditEventType.APPROVAL_DENIED,
            summary=f"Rejected: {proposal.action_name}",
            action_id=proposal.id,
            alert_id=proposal.alert_id,
            actor=rejected_by,
            actor_type="user",
            details={
                "reason": reason,
            },
        )
        
        logger.info(f"Action rejected: {proposal.action_name} by {rejected_by} - {reason}")
        
        # Invoke callbacks
        for callback in self._on_rejected:
            try:
                await callback(proposal)
            except Exception as e:
                logger.error(f"Error in rejection callback: {e}")
        
        return True
    
    async def modify_and_approve(
        self,
        proposal_id: UUID | str,
        approved_by: str,
        modifications: dict[str, Any],
        notes: str | None = None,
    ) -> bool:
        """
        Modify parameters and approve.
        
        Args:
            proposal_id: Proposal ID
            approved_by: Who is approving
            modifications: Parameter modifications
            notes: Optional notes
            
        Returns:
            True if successful
        """
        if not self.config.allow_modification:
            logger.warning("Modification not allowed")
            return False
        
        if isinstance(proposal_id, str):
            proposal_id = self._find_by_short_id(proposal_id)
            if not proposal_id:
                return False
        
        async with self._lock:
            proposal = self._pending.get(proposal_id)
            if not proposal or not proposal.is_pending:
                return False
            
            # Apply modifications
            proposal.original_parameters = proposal.parameters.copy()
            proposal.parameters.update(modifications)
            
            proposal.state = ApprovalState.MODIFIED
            proposal.approved_by = approved_by
            proposal.approved_at = datetime.now(timezone.utc)
            proposal.modification_notes = notes
            
            self._pending.pop(proposal_id, None)
            self._history.append(proposal)
        
        # Cancel escalation
        if proposal_id in self._escalation_tasks:
            self._escalation_tasks[proposal_id].cancel()
            del self._escalation_tasks[proposal_id]
        
        audit(
            event_type=AuditEventType.APPROVAL_GRANTED,
            summary=f"Modified and approved: {proposal.action_name}",
            action_id=proposal.id,
            alert_id=proposal.alert_id,
            actor=approved_by,
            actor_type="user",
            details={
                "original_parameters": proposal.original_parameters,
                "modified_parameters": modifications,
                "notes": notes,
            },
        )
        
        logger.info(
            f"Action modified and approved: {proposal.action_name} "
            f"by {approved_by} with modifications: {modifications}"
        )
        
        # Invoke callbacks
        for callback in self._on_approved:
            try:
                await callback(proposal)
            except Exception as e:
                logger.error(f"Error in approval callback: {e}")
        
        return True
    
    def _find_by_short_id(self, short_id: str) -> UUID | None:
        """Find proposal by short ID prefix."""
        for proposal_id in self._pending:
            if str(proposal_id).startswith(short_id):
                return proposal_id
        return None
    
    async def wait_for_decision(
        self,
        proposal_id: UUID,
        timeout_seconds: float | None = None,
    ) -> ApprovalState:
        """
        Wait for a decision on a proposal.
        
        Args:
            proposal_id: Proposal ID
            timeout_seconds: Optional timeout override
            
        Returns:
            Final state
        """
        proposal = self._pending.get(proposal_id)
        if not proposal:
            # Check history
            for p in self._history:
                if p.id == proposal_id:
                    return p.state
            raise ValueError(f"Proposal {proposal_id} not found")
        
        if timeout_seconds is None:
            timeout_seconds = proposal.time_remaining_seconds
        
        start = datetime.now(timezone.utc)
        poll_interval = 1.0
        
        while True:
            await asyncio.sleep(poll_interval)
            
            # Check if decided
            proposal = self._pending.get(proposal_id)
            if not proposal:
                # Must be in history
                for p in self._history:
                    if p.id == proposal_id:
                        return p.state
                return ApprovalState.TIMEOUT
            
            if proposal.is_decided:
                return proposal.state
            
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed >= timeout_seconds:
                return proposal.state
    
    async def get_pending(self) -> list[ProposedAction]:
        """Get all pending proposals."""
        return list(self._pending.values())
    
    async def get_history(
        self,
        limit: int = 50,
        state_filter: ApprovalState | None = None,
    ) -> list[ProposedAction]:
        """Get historical proposals."""
        history = self._history.copy()
        if state_filter:
            history = [p for p in history if p.state == state_filter]
        return history[-limit:]
    
    def get_stats(self) -> dict[str, Any]:
        """Get approval statistics."""
        total = len(self._history)
        approved = sum(1 for p in self._history if p.state == ApprovalState.APPROVED)
        rejected = sum(1 for p in self._history if p.state == ApprovalState.REJECTED)
        modified = sum(1 for p in self._history if p.state == ApprovalState.MODIFIED)
        timeout = sum(1 for p in self._history if p.state == ApprovalState.TIMEOUT)
        
        # Average time to decision
        decision_times = []
        for p in self._history:
            if p.approved_at:
                delta = (p.approved_at - p.created_at).total_seconds()
                decision_times.append(delta)
        
        avg_decision_time = sum(decision_times) / len(decision_times) if decision_times else 0
        
        return {
            "pending": len(self._pending),
            "total_decisions": total,
            "approved": approved,
            "rejected": rejected,
            "modified": modified,
            "timeout": timeout,
            "approval_rate": approved / total if total > 0 else 0,
            "avg_decision_time_seconds": avg_decision_time,
        }


# Singleton instance
_approval_gate: HumanApprovalGate | None = None


def get_approval_gate(config: ApprovalConfig | None = None) -> HumanApprovalGate:
    """Get or create the approval gate."""
    global _approval_gate
    if _approval_gate is None:
        _approval_gate = HumanApprovalGate(config)
    return _approval_gate


# Import AuditSeverity for the audit call
from autosre.core.audit import AuditSeverity
