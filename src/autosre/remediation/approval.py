"""
Approval Workflow for remediation actions.

Manages human-in-the-loop approval for high-risk or sensitive operations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

from .models import (
    RemediationAction,
    ApprovalStatus,
    ApprovalRequest,
    RiskLevel,
    BlastRadius,
    SafetyCheckResult,
)

logger = get_logger(__name__)


class NotificationChannel(str, Enum):
    """Channels for approval notifications."""
    
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class EscalationLevel(str, Enum):
    """Escalation levels for approval requests."""
    
    TEAM = "team"           # Team level approval
    LEAD = "lead"           # Team lead approval
    MANAGER = "manager"     # Engineering manager
    DIRECTOR = "director"   # Director level
    VP = "vp"               # VP/Exec level


class ApprovalPolicy(BaseModel):
    """Policy for requiring approvals."""
    
    name: str
    description: str = ""
    
    # Risk-based approval
    require_approval_above_risk: RiskLevel = RiskLevel.HIGH
    
    # Namespace-based
    require_approval_namespaces: list[str] = Field(
        default_factory=lambda: ["production", "prod"]
    )
    
    # Action-based
    require_approval_actions: list[str] = Field(
        default_factory=lambda: ["drain_node", "delete_deployment", "scale_to_zero"]
    )
    
    # Blast radius thresholds
    require_approval_pods_threshold: int = 20
    require_approval_nodes_threshold: int = 2
    
    # Approvers
    approver_roles: list[str] = Field(
        default_factory=lambda: ["sre", "oncall", "admin"]
    )
    
    # Escalation
    escalation_chain: list[EscalationLevel] = Field(
        default_factory=lambda: [
            EscalationLevel.TEAM,
            EscalationLevel.LEAD,
            EscalationLevel.MANAGER,
        ]
    )
    escalation_timeout_minutes: int = 15
    
    # Expiration
    request_expiry_hours: int = 4
    auto_reject_on_expiry: bool = True
    
    # Notification
    notification_channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.SLACK]
    )
    
    def check_requires_approval(
        self,
        action: RemediationAction,
        risk_level: RiskLevel,
    ) -> tuple[bool, str]:
        """
        Check if action requires approval.
        
        Returns:
            Tuple of (requires_approval, reason)
        """
        risk_order = list(RiskLevel)
        
        # Risk-based check
        if risk_order.index(risk_level) >= risk_order.index(self.require_approval_above_risk):
            return True, f"Risk level {risk_level.value} requires approval"
        
        # Namespace-based check
        if action.target_namespace in self.require_approval_namespaces:
            return True, f"Namespace {action.target_namespace} requires approval"
        
        # Action-based check
        if action.definition_name in self.require_approval_actions:
            return True, f"Action {action.definition_name} requires approval"
        
        # Blast radius check
        if action.blast_radius:
            if action.blast_radius.affected_pods >= self.require_approval_pods_threshold:
                return True, f"Affects {action.blast_radius.affected_pods} pods"
            if action.blast_radius.affected_nodes >= self.require_approval_nodes_threshold:
                return True, f"Affects {action.blast_radius.affected_nodes} nodes"
        
        return False, ""


# Type for notification handlers
NotificationHandler = Callable[[ApprovalRequest, NotificationChannel], Awaitable[bool]]

# Type for approval decision callbacks
ApprovalCallback = Callable[[ApprovalRequest, ApprovalStatus, str | None], Awaitable[None]]


class ApprovalDecision(BaseModel):
    """Record of an approval decision."""
    
    request_id: UUID
    status: ApprovalStatus
    decided_by: str
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str | None = None
    escalation_level: EscalationLevel = EscalationLevel.TEAM


class ApprovalWorkflow:
    """
    Manages approval workflows for remediation actions.
    
    Features:
    - Create and track approval requests
    - Multi-channel notifications
    - Escalation chains
    - Automatic expiration
    - Approval history
    
    Example:
        workflow = ApprovalWorkflow()
        
        # Request approval
        request = await workflow.request_approval(
            action=action,
            reason="High blast radius remediation",
            blast_radius=blast_radius,
        )
        
        # Check status
        if await workflow.is_approved(request.id):
            # Proceed with action
            ...
        
        # Or register callback
        workflow.on_decision(async def callback(req, status, reason):
            if status == ApprovalStatus.APPROVED:
                await engine.execute(action)
        )
    """
    
    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
    ):
        self._policy = policy or ApprovalPolicy(name="default")
        
        # State
        self._requests: dict[UUID, ApprovalRequest] = {}
        self._decisions: dict[UUID, ApprovalDecision] = {}
        self._pending_callbacks: dict[UUID, list[ApprovalCallback]] = {}
        
        # Notification handlers
        self._notification_handlers: dict[NotificationChannel, NotificationHandler] = {}
        
        # Escalation state
        self._escalation_tasks: dict[UUID, asyncio.Task] = {}
        
        self._lock = asyncio.Lock()
    
    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy
    
    def set_policy(self, policy: ApprovalPolicy) -> None:
        """Set approval policy."""
        self._policy = policy
        logger.info(f"Set approval policy: {policy.name}")
    
    def register_notification_handler(
        self,
        channel: NotificationChannel,
        handler: NotificationHandler,
    ) -> None:
        """
        Register a notification handler for a channel.
        
        Args:
            channel: Notification channel
            handler: Async function to send notification
        """
        self._notification_handlers[channel] = handler
        logger.info(f"Registered notification handler for: {channel.value}")
    
    async def request_approval(
        self,
        action: RemediationAction,
        reason: str,
        blast_radius: BlastRadius | None = None,
        safety_checks: list[SafetyCheckResult] | None = None,
        requested_by: str = "autosre",
        expiry_hours: int | None = None,
        notification_channels: list[NotificationChannel] | None = None,
    ) -> ApprovalRequest:
        """
        Create an approval request for an action.
        
        Args:
            action: The remediation action
            reason: Why this action needs to be taken
            blast_radius: Assessed blast radius
            safety_checks: Safety check results
            requested_by: Who is requesting
            expiry_hours: Override expiry time
            notification_channels: Override notification channels
            
        Returns:
            Created approval request
        """
        expiry = expiry_hours or self._policy.request_expiry_hours
        channels = notification_channels or self._policy.notification_channels
        
        request = ApprovalRequest(
            action_id=action.id,
            action_name=action.definition_name,
            reason=reason,
            context={
                "target_type": action.target_type,
                "target_name": action.target_name,
                "target_namespace": action.target_namespace,
                "parameters": action.parameters,
                "dry_run": action.dry_run,
            },
            blast_radius=blast_radius,
            safety_checks=safety_checks or [],
            requested_by=requested_by,
            expires_at=datetime.utcnow() + timedelta(hours=expiry),
            notification_channels=[c.value for c in channels],
            escalation_chain=[e.value for e in self._policy.escalation_chain],
        )
        
        async with self._lock:
            self._requests[request.id] = request
            action.approval_request = request
        
        logger.info(
            f"Created approval request {request.id} for action {action.definition_name}"
        )
        
        # Send notifications
        await self._send_notifications(request, channels)
        
        # Start escalation timer
        if self._policy.escalation_chain:
            self._start_escalation_timer(request)
        
        return request
    
    async def approve(
        self,
        request_id: UUID,
        approved_by: str,
        reason: str | None = None,
    ) -> bool:
        """
        Approve a request.
        
        Args:
            request_id: Request ID
            approved_by: Who is approving
            reason: Optional approval reason
            
        Returns:
            True if approval was recorded
        """
        return await self._record_decision(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            decided_by=approved_by,
            reason=reason,
        )
    
    async def reject(
        self,
        request_id: UUID,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """
        Reject a request.
        
        Args:
            request_id: Request ID
            rejected_by: Who is rejecting
            reason: Rejection reason
            
        Returns:
            True if rejection was recorded
        """
        return await self._record_decision(
            request_id=request_id,
            status=ApprovalStatus.REJECTED,
            decided_by=rejected_by,
            reason=reason,
        )
    
    async def _record_decision(
        self,
        request_id: UUID,
        status: ApprovalStatus,
        decided_by: str,
        reason: str | None,
    ) -> bool:
        """Record an approval decision."""
        async with self._lock:
            if request_id not in self._requests:
                logger.warning(f"Approval request {request_id} not found")
                return False
            
            request = self._requests[request_id]
            
            # Check if already decided
            if request.status not in [ApprovalStatus.PENDING, ApprovalStatus.NOT_REQUIRED]:
                logger.warning(f"Request {request_id} already decided: {request.status}")
                return False
            
            # Check expiry
            if request.is_expired:
                request.status = ApprovalStatus.EXPIRED
                logger.warning(f"Request {request_id} has expired")
                return False
            
            # Record decision
            request.status = status
            request.approved_by = decided_by if status == ApprovalStatus.APPROVED else None
            request.approved_at = datetime.utcnow() if status == ApprovalStatus.APPROVED else None
            request.rejection_reason = reason if status == ApprovalStatus.REJECTED else None
            
            decision = ApprovalDecision(
                request_id=request_id,
                status=status,
                decided_by=decided_by,
                reason=reason,
            )
            self._decisions[request_id] = decision
        
        logger.info(
            f"Approval request {request_id} {status.value} by {decided_by}"
            + (f": {reason}" if reason else "")
        )
        
        # Cancel escalation
        if request_id in self._escalation_tasks:
            self._escalation_tasks[request_id].cancel()
            del self._escalation_tasks[request_id]
        
        # Invoke callbacks
        await self._invoke_callbacks(request, status, reason)
        
        return True
    
    async def is_approved(self, request_id: UUID) -> bool:
        """Check if a request is approved."""
        request = self._requests.get(request_id)
        if not request:
            return False
        return request.status == ApprovalStatus.APPROVED
    
    async def is_rejected(self, request_id: UUID) -> bool:
        """Check if a request is rejected."""
        request = self._requests.get(request_id)
        if not request:
            return False
        return request.status == ApprovalStatus.REJECTED
    
    async def is_pending(self, request_id: UUID) -> bool:
        """Check if a request is still pending."""
        request = self._requests.get(request_id)
        if not request:
            return False
        return request.status == ApprovalStatus.PENDING and not request.is_expired
    
    async def get_request(self, request_id: UUID) -> ApprovalRequest | None:
        """Get an approval request."""
        return self._requests.get(request_id)
    
    async def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = []
        for request in self._requests.values():
            if request.status == ApprovalStatus.PENDING:
                if request.is_expired:
                    await self._handle_expiry(request)
                else:
                    pending.append(request)
        return pending
    
    def on_decision(
        self,
        request_id: UUID,
        callback: ApprovalCallback,
    ) -> None:
        """
        Register a callback for when a decision is made.
        
        Args:
            request_id: Request ID
            callback: Async function called with (request, status, reason)
        """
        if request_id not in self._pending_callbacks:
            self._pending_callbacks[request_id] = []
        self._pending_callbacks[request_id].append(callback)
    
    async def wait_for_decision(
        self,
        request_id: UUID,
        timeout_seconds: float | None = None,
    ) -> ApprovalStatus:
        """
        Wait for an approval decision.
        
        Args:
            request_id: Request ID
            timeout_seconds: Optional timeout
            
        Returns:
            Final approval status
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # If already decided, return immediately
        if request.status not in [ApprovalStatus.PENDING, ApprovalStatus.NOT_REQUIRED]:
            return request.status
        
        # Calculate effective timeout
        if timeout_seconds:
            effective_timeout = timeout_seconds
        else:
            effective_timeout = request.time_remaining_seconds
        
        # Poll for decision
        start = datetime.utcnow()
        poll_interval = 1.0
        
        while True:
            await asyncio.sleep(poll_interval)
            
            request = self._requests.get(request_id)
            if not request:
                raise ValueError(f"Request {request_id} disappeared")
            
            # Check if decided
            if request.status not in [ApprovalStatus.PENDING, ApprovalStatus.NOT_REQUIRED]:
                return request.status
            
            # Check expiry
            if request.is_expired:
                await self._handle_expiry(request)
                return request.status
            
            # Check timeout
            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed >= effective_timeout:
                return request.status
    
    async def _send_notifications(
        self,
        request: ApprovalRequest,
        channels: list[NotificationChannel],
    ) -> None:
        """Send notifications for an approval request."""
        for channel in channels:
            handler = self._notification_handlers.get(channel)
            if handler:
                try:
                    success = await handler(request, channel)
                    if success:
                        logger.info(f"Sent notification to {channel.value} for request {request.id}")
                    else:
                        logger.warning(f"Failed to send notification to {channel.value}")
                except Exception as e:
                    logger.error(f"Error sending notification to {channel.value}: {e}")
            else:
                # Log as console notification
                if channel == NotificationChannel.CONSOLE:
                    self._log_approval_request(request)
                else:
                    logger.warning(f"No handler for notification channel: {channel.value}")
    
    def _log_approval_request(self, request: ApprovalRequest) -> None:
        """Log approval request to console."""
        logger.info("=" * 60)
        logger.info("APPROVAL REQUIRED")
        logger.info("=" * 60)
        logger.info(f"Request ID: {request.id}")
        logger.info(f"Action: {request.action_name}")
        logger.info(f"Reason: {request.reason}")
        logger.info(f"Requested by: {request.requested_by}")
        logger.info(f"Expires at: {request.expires_at}")
        
        if request.blast_radius:
            logger.info(f"Blast Radius:")
            logger.info(f"  - Affected pods: {request.blast_radius.affected_pods}")
            logger.info(f"  - Affected nodes: {request.blast_radius.affected_nodes}")
            logger.info(f"  - Risk score: {request.blast_radius.overall_risk_score:.2f}")
        
        logger.info("=" * 60)
    
    def _start_escalation_timer(self, request: ApprovalRequest) -> None:
        """Start escalation timer for a request."""
        async def escalate():
            try:
                timeout = self._policy.escalation_timeout_minutes * 60
                await asyncio.sleep(timeout)
                
                # Check if still pending
                if request.status == ApprovalStatus.PENDING:
                    logger.info(f"Escalating approval request {request.id}")
                    await self._escalate_request(request)
                    
            except asyncio.CancelledError:
                pass
        
        task = asyncio.create_task(escalate())
        self._escalation_tasks[request.id] = task
    
    async def _escalate_request(self, request: ApprovalRequest) -> None:
        """Escalate an approval request."""
        # Find current escalation level
        current_level_index = 0
        for i, level in enumerate(self._policy.escalation_chain):
            if level.value in request.escalation_chain:
                current_level_index = i
                break
        
        # Move to next level
        next_index = current_level_index + 1
        if next_index < len(self._policy.escalation_chain):
            next_level = self._policy.escalation_chain[next_index]
            logger.info(
                f"Escalating request {request.id} to level: {next_level.value}"
            )
            
            # Re-send notifications with escalation context
            channels = [
                NotificationChannel(c) for c in request.notification_channels
                if c in NotificationChannel.__members__.values()
            ]
            await self._send_notifications(request, channels)
            
            # Start new escalation timer
            self._start_escalation_timer(request)
        else:
            logger.warning(
                f"Request {request.id} reached max escalation level"
            )
    
    async def _handle_expiry(self, request: ApprovalRequest) -> None:
        """Handle expiry of an approval request."""
        if request.status != ApprovalStatus.PENDING:
            return
        
        if self._policy.auto_reject_on_expiry:
            request.status = ApprovalStatus.EXPIRED
            logger.info(f"Approval request {request.id} expired and auto-rejected")
            
            # Record as rejection
            decision = ApprovalDecision(
                request_id=request.id,
                status=ApprovalStatus.EXPIRED,
                decided_by="system",
                reason="Request expired without approval",
            )
            self._decisions[request.id] = decision
            
            # Invoke callbacks
            await self._invoke_callbacks(
                request,
                ApprovalStatus.EXPIRED,
                "Request expired without approval",
            )
    
    async def _invoke_callbacks(
        self,
        request: ApprovalRequest,
        status: ApprovalStatus,
        reason: str | None,
    ) -> None:
        """Invoke registered callbacks for a request."""
        callbacks = self._pending_callbacks.pop(request.id, [])
        
        for callback in callbacks:
            try:
                await callback(request, status, reason)
            except Exception as e:
                logger.error(f"Error in approval callback: {e}", exc_info=True)
    
    async def cleanup_expired(self) -> int:
        """Clean up expired requests."""
        count = 0
        async with self._lock:
            for request in list(self._requests.values()):
                if request.is_expired and request.status == ApprovalStatus.PENDING:
                    await self._handle_expiry(request)
                    count += 1
        return count
    
    def get_stats(self) -> dict[str, Any]:
        """Get approval workflow statistics."""
        total = len(self._requests)
        pending = sum(
            1 for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        )
        approved = sum(
            1 for r in self._requests.values()
            if r.status == ApprovalStatus.APPROVED
        )
        rejected = sum(
            1 for r in self._requests.values()
            if r.status == ApprovalStatus.REJECTED
        )
        expired = sum(
            1 for r in self._requests.values()
            if r.status == ApprovalStatus.EXPIRED
        )
        
        return {
            "total_requests": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "approval_rate": approved / total if total > 0 else 0,
            "pending_escalations": len(self._escalation_tasks),
        }
