"""
Human Approval Workflow for AI Actions

Provides human-in-the-loop approval workflows for high-risk AI actions:
- Multi-level approval chains
- Time-based escalation
- Approval policies and strategies
- Notification integration
"""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    
    PENDING = "pending"           # Awaiting approval
    APPROVED = "approved"         # Approved by required approvers
    DENIED = "denied"             # Denied by an approver
    EXPIRED = "expired"           # Timed out without decision
    CANCELLED = "cancelled"       # Cancelled by requester
    ESCALATED = "escalated"       # Escalated to higher level


class ApprovalLevel(str, Enum):
    """Levels of approval required."""
    
    NONE = "none"                 # No approval needed
    TEAM_MEMBER = "team_member"   # Any team member
    TEAM_LEAD = "team_lead"       # Team lead required
    MANAGER = "manager"           # Manager required
    DIRECTOR = "director"         # Director required
    EXECUTIVE = "executive"       # Executive required
    MULTI_PARTY = "multi_party"   # Multiple approvers required


class ApprovalStrategy(str, Enum):
    """Strategy for handling approvals."""
    
    ANY = "any"                   # Any approver can approve
    ALL = "all"                   # All approvers must approve
    MAJORITY = "majority"         # Majority must approve
    QUORUM = "quorum"             # Minimum number must approve
    SEQUENTIAL = "sequential"     # Must be approved in order


class Approver(BaseModel):
    """An individual approver."""
    
    id: str
    name: str
    email: str
    
    # Role and permissions
    role: str = "team_member"
    approval_level: ApprovalLevel = ApprovalLevel.TEAM_MEMBER
    
    # Preferences
    preferred_channel: str = "email"
    timezone: str = "UTC"
    
    # Availability
    available: bool = True
    out_of_office_until: Optional[datetime] = None
    delegate_to: Optional[str] = None
    
    # Metadata
    department: str = ""
    team: str = ""


class ApproverGroup(BaseModel):
    """A group of approvers."""
    
    id: str
    name: str
    description: str = ""
    
    # Members
    members: list[str] = Field(default_factory=list)  # Approver IDs
    
    # Strategy
    strategy: ApprovalStrategy = ApprovalStrategy.ANY
    required_count: int = Field(default=1, ge=1)
    
    # Level
    approval_level: ApprovalLevel = ApprovalLevel.TEAM_MEMBER
    
    # Metadata
    owner: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EscalationRule(BaseModel):
    """Rule for escalating approval requests."""
    
    id: str
    name: str
    enabled: bool = True
    
    # Trigger conditions
    timeout_minutes: int = Field(default=60, ge=1)
    no_response_threshold: int = Field(default=30, ge=1)
    
    # Escalation target
    escalate_to: ApprovalLevel
    escalate_to_group: Optional[str] = None
    
    # Notification
    notify_original_approvers: bool = True
    notify_requester: bool = True
    
    # Repeat
    max_escalations: int = Field(default=3, ge=1)
    
    # Metadata
    description: str = ""


class EscalationConfig(BaseModel):
    """Configuration for approval escalation."""
    
    enabled: bool = True
    
    # Rules
    rules: list[EscalationRule] = Field(default_factory=list)
    
    # Default timeouts
    default_timeout_minutes: int = Field(default=60, ge=1)
    urgent_timeout_minutes: int = Field(default=15, ge=1)
    
    # After-hours handling
    after_hours_escalate: bool = True
    business_hours: tuple[int, int] = Field(default=(9, 17))
    
    # Final escalation
    final_escalation_level: ApprovalLevel = ApprovalLevel.MANAGER


class ApprovalPolicy(BaseModel):
    """Policy governing approval requirements."""
    
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    
    # Requirements
    minimum_level: ApprovalLevel = ApprovalLevel.TEAM_MEMBER
    required_groups: list[str] = Field(default_factory=list)
    
    # Strategy
    strategy: ApprovalStrategy = ApprovalStrategy.ANY
    quorum_size: int = Field(default=1, ge=1)
    
    # Conditions
    applies_to_actions: list[str] = Field(default_factory=list)
    applies_to_targets: list[str] = Field(default_factory=list)
    applies_to_environments: list[str] = Field(
        default_factory=lambda: ["production"]
    )
    
    # Risk-based
    risk_threshold: str = "high"  # Apply when risk >= threshold
    
    # Timeouts
    timeout_minutes: int = Field(default=60, ge=1)
    expiry_action: str = "deny"  # deny, escalate, auto_approve
    
    # Metadata
    owner: str = ""
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationConfig(BaseModel):
    """Configuration for approval notifications."""
    
    # Channels
    email_enabled: bool = True
    slack_enabled: bool = True
    pagerduty_enabled: bool = False
    webhook_enabled: bool = False
    
    # Endpoints
    slack_webhook: Optional[str] = None
    pagerduty_key: Optional[str] = None
    custom_webhook: Optional[str] = None
    
    # Templates
    email_template: str = "approval_request"
    slack_template: str = "approval_request_slack"
    
    # Preferences
    reminder_enabled: bool = True
    reminder_interval_minutes: int = Field(default=30, ge=5)
    max_reminders: int = Field(default=3, ge=1)
    
    # Escalation notifications
    notify_on_escalation: bool = True
    notify_on_approval: bool = True
    notify_on_denial: bool = True


@dataclass
class ApprovalDecision:
    """A decision made by an approver."""
    
    approver_id: str
    approver_name: str
    decision: ApprovalStatus
    
    # Details
    comment: str = ""
    conditions: list[str] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Verification
    signature: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "approver_id": self.approver_id,
            "approver_name": self.approver_name,
            "decision": self.decision.value,
            "comment": self.comment,
            "conditions": self.conditions,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
        }


@dataclass
class ApprovalRequest:
    """A request for approval."""
    
    # Required fields (no defaults) - must come first
    id: str
    action: str
    target: str
    justification: str
    risk_level: str
    risk_score: float
    requester_id: str
    requester_name: str
    
    # Optional fields with defaults
    risk_factors: list[str] = field(default_factory=list)
    requester_team: str = ""
    
    # Approval requirements
    required_level: ApprovalLevel = ApprovalLevel.TEAM_MEMBER
    required_approvers: list[str] = field(default_factory=list)
    required_groups: list[str] = field(default_factory=list)
    strategy: ApprovalStrategy = ApprovalStrategy.ANY
    quorum_size: int = 1
    
    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    decisions: list[ApprovalDecision] = field(default_factory=list)
    
    # Timeline
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Escalation
    escalation_count: int = 0
    escalated_to: Optional[str] = None
    
    # Context
    context: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    priority: str = "normal"  # low, normal, high, urgent
    tags: list[str] = field(default_factory=list)
    
    def add_decision(self, decision: ApprovalDecision) -> None:
        """Add a decision to the request."""
        self.decisions.append(decision)
        self.updated_at = datetime.utcnow()
        self._evaluate_status()
    
    def _evaluate_status(self) -> None:
        """Evaluate overall status based on decisions."""
        if not self.decisions:
            return
        
        approvals = [d for d in self.decisions if d.decision == ApprovalStatus.APPROVED]
        denials = [d for d in self.decisions if d.decision == ApprovalStatus.DENIED]
        
        # Any denial means denied
        if denials:
            self.status = ApprovalStatus.DENIED
            self.resolved_at = datetime.utcnow()
            return
        
        # Check if enough approvals based on strategy
        if self.strategy == ApprovalStrategy.ANY:
            if approvals:
                self.status = ApprovalStatus.APPROVED
                self.resolved_at = datetime.utcnow()
        
        elif self.strategy == ApprovalStrategy.ALL:
            required = len(self.required_approvers) if self.required_approvers else self.quorum_size
            if len(approvals) >= required:
                self.status = ApprovalStatus.APPROVED
                self.resolved_at = datetime.utcnow()
        
        elif self.strategy == ApprovalStrategy.MAJORITY:
            required = len(self.required_approvers) if self.required_approvers else self.quorum_size
            if len(approvals) > required // 2:
                self.status = ApprovalStatus.APPROVED
                self.resolved_at = datetime.utcnow()
        
        elif self.strategy == ApprovalStrategy.QUORUM:
            if len(approvals) >= self.quorum_size:
                self.status = ApprovalStatus.APPROVED
                self.resolved_at = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "target": self.target,
            "justification": self.justification,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "requester_id": self.requester_id,
            "requester_name": self.requester_name,
            "required_level": self.required_level.value,
            "status": self.status.value,
            "decisions": [d.to_dict() for d in self.decisions],
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "escalation_count": self.escalation_count,
            "priority": self.priority,
        }


class ApprovalNotifier:
    """Sends notifications for approval workflows."""
    
    def __init__(
        self,
        config: NotificationConfig,
        approver_registry: Optional[dict[str, Approver]] = None,
    ):
        self.config = config
        self.approver_registry = approver_registry or {}
        
        # Notification handlers
        self._handlers: dict[str, Callable] = {}
    
    def register_handler(self, channel: str, handler: Callable) -> None:
        """Register a notification handler for a channel."""
        self._handlers[channel] = handler
    
    async def send_approval_request(
        self,
        request: ApprovalRequest,
        approver_ids: list[str],
    ) -> dict[str, bool]:
        """Send approval request notifications.
        
        Returns dict of approver_id -> success.
        """
        results: dict[str, bool] = {}
        
        for approver_id in approver_ids:
            approver = self.approver_registry.get(approver_id)
            if not approver:
                results[approver_id] = False
                continue
            
            # Check availability
            if not approver.available:
                if approver.delegate_to:
                    # Redirect to delegate
                    delegate = self.approver_registry.get(approver.delegate_to)
                    if delegate:
                        approver = delegate
                else:
                    results[approver_id] = False
                    continue
            
            # Send notification
            success = await self._send_notification(
                approver=approver,
                request=request,
                notification_type="approval_request",
            )
            results[approver_id] = success
        
        return results
    
    async def send_decision_notification(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> bool:
        """Send notification about a decision."""
        # Notify requester
        if self.config.notify_on_approval and decision.decision == ApprovalStatus.APPROVED:
            await self._send_to_requester(request, "approved", decision)
        elif self.config.notify_on_denial and decision.decision == ApprovalStatus.DENIED:
            await self._send_to_requester(request, "denied", decision)
        
        return True
    
    async def send_escalation_notification(
        self,
        request: ApprovalRequest,
        new_approvers: list[str],
    ) -> dict[str, bool]:
        """Send escalation notifications."""
        results: dict[str, bool] = {}
        
        if self.config.notify_on_escalation:
            for approver_id in new_approvers:
                approver = self.approver_registry.get(approver_id)
                if approver:
                    success = await self._send_notification(
                        approver=approver,
                        request=request,
                        notification_type="escalation",
                    )
                    results[approver_id] = success
        
        return results
    
    async def send_reminder(
        self,
        request: ApprovalRequest,
        pending_approvers: list[str],
    ) -> dict[str, bool]:
        """Send reminder notifications."""
        results: dict[str, bool] = {}
        
        if not self.config.reminder_enabled:
            return results
        
        for approver_id in pending_approvers:
            approver = self.approver_registry.get(approver_id)
            if approver:
                success = await self._send_notification(
                    approver=approver,
                    request=request,
                    notification_type="reminder",
                )
                results[approver_id] = success
        
        return results
    
    async def _send_notification(
        self,
        approver: Approver,
        request: ApprovalRequest,
        notification_type: str,
    ) -> bool:
        """Send a notification to an approver."""
        channel = approver.preferred_channel
        handler = self._handlers.get(channel)
        
        if handler:
            try:
                await handler(
                    recipient=approver,
                    request=request,
                    notification_type=notification_type,
                )
                return True
            except Exception:
                return False
        
        return False
    
    async def _send_to_requester(
        self,
        request: ApprovalRequest,
        status: str,
        decision: ApprovalDecision,
    ) -> bool:
        """Send notification to the requester."""
        # In real implementation, look up requester and send notification
        return True


class ApprovalWorkflow:
    """Manages human approval workflows."""
    
    def __init__(
        self,
        policy: Optional[ApprovalPolicy] = None,
        escalation_config: Optional[EscalationConfig] = None,
        notifier: Optional[ApprovalNotifier] = None,
    ):
        self.policy = policy or ApprovalPolicy(id="default", name="Default Policy")
        self.escalation_config = escalation_config or EscalationConfig()
        self.notifier = notifier
        
        # Request storage (in-memory, replace with persistent storage)
        self._requests: dict[str, ApprovalRequest] = {}
        
        # Approver registry
        self._approvers: dict[str, Approver] = {}
        self._groups: dict[str, ApproverGroup] = {}
        
        # Callbacks
        self._on_approved: Optional[Callable[[ApprovalRequest], Any]] = None
        self._on_denied: Optional[Callable[[ApprovalRequest], Any]] = None
        self._on_expired: Optional[Callable[[ApprovalRequest], Any]] = None
    
    def register_approver(self, approver: Approver) -> None:
        """Register an approver."""
        self._approvers[approver.id] = approver
        if self.notifier:
            self.notifier.approver_registry[approver.id] = approver
    
    def register_group(self, group: ApproverGroup) -> None:
        """Register an approver group."""
        self._groups[group.id] = group
    
    def set_callbacks(
        self,
        on_approved: Optional[Callable[[ApprovalRequest], Any]] = None,
        on_denied: Optional[Callable[[ApprovalRequest], Any]] = None,
        on_expired: Optional[Callable[[ApprovalRequest], Any]] = None,
    ) -> None:
        """Set callback functions for workflow events."""
        self._on_approved = on_approved
        self._on_denied = on_denied
        self._on_expired = on_expired
    
    async def request_approval(
        self,
        action: str,
        target: str,
        justification: str,
        requester_id: str,
        requester_name: str,
        risk_level: str = "medium",
        risk_score: float = 0.5,
        risk_factors: Optional[list[str]] = None,
        context: Optional[dict] = None,
        priority: str = "normal",
    ) -> ApprovalRequest:
        """Create a new approval request."""
        request_id = self._generate_request_id()
        
        # Determine required level and approvers
        required_level, approvers = self._determine_requirements(
            action=action,
            target=target,
            risk_level=risk_level,
            risk_score=risk_score,
        )
        
        # Calculate expiry
        timeout = self.policy.timeout_minutes
        if priority == "urgent":
            timeout = self.escalation_config.urgent_timeout_minutes
        
        request = ApprovalRequest(
            id=request_id,
            action=action,
            target=target,
            justification=justification,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors or [],
            requester_id=requester_id,
            requester_name=requester_name,
            required_level=required_level,
            required_approvers=approvers,
            required_groups=self.policy.required_groups,
            strategy=self.policy.strategy,
            quorum_size=self.policy.quorum_size,
            expires_at=datetime.utcnow() + timedelta(minutes=timeout),
            context=context or {},
            priority=priority,
        )
        
        self._requests[request_id] = request
        
        # Send notifications
        if self.notifier and approvers:
            await self.notifier.send_approval_request(request, approvers)
        
        return request
    
    async def submit_decision(
        self,
        request_id: str,
        approver_id: str,
        decision: ApprovalStatus,
        comment: str = "",
        conditions: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        """Submit an approval decision.
        
        Returns (success, message).
        """
        request = self._requests.get(request_id)
        if not request:
            return False, "Request not found"
        
        # Check if already resolved
        if request.status in (ApprovalStatus.APPROVED, ApprovalStatus.DENIED, ApprovalStatus.EXPIRED):
            return False, f"Request already {request.status.value}"
        
        # Check if expired
        if request.is_expired():
            request.status = ApprovalStatus.EXPIRED
            return False, "Request has expired"
        
        # Verify approver
        approver = self._approvers.get(approver_id)
        if not approver:
            return False, "Approver not found"
        
        # Check if approver is authorized
        if not self._is_authorized_approver(approver, request):
            return False, "Not authorized to approve this request"
        
        # Check if already decided
        existing = [d for d in request.decisions if d.approver_id == approver_id]
        if existing:
            return False, "Already submitted a decision"
        
        # Create decision
        approval_decision = ApprovalDecision(
            approver_id=approver_id,
            approver_name=approver.name,
            decision=decision,
            comment=comment,
            conditions=conditions or [],
            signature=self._sign_decision(request_id, approver_id, decision),
        )
        
        request.add_decision(approval_decision)
        
        # Send notification
        if self.notifier:
            await self.notifier.send_decision_notification(request, approval_decision)
        
        # Trigger callbacks
        if request.status == ApprovalStatus.APPROVED and self._on_approved:
            await self._on_approved(request)
        elif request.status == ApprovalStatus.DENIED and self._on_denied:
            await self._on_denied(request)
        
        return True, f"Decision recorded: {decision.value}"
    
    async def escalate(self, request_id: str, reason: str = "") -> tuple[bool, str]:
        """Escalate an approval request."""
        request = self._requests.get(request_id)
        if not request:
            return False, "Request not found"
        
        if request.status != ApprovalStatus.PENDING:
            return False, f"Cannot escalate request in {request.status.value} status"
        
        # Check escalation limit
        max_escalations = self.escalation_config.rules[0].max_escalations if self.escalation_config.rules else 3
        if request.escalation_count >= max_escalations:
            return False, "Maximum escalations reached"
        
        # Determine next level
        next_level = self._get_next_level(request.required_level)
        
        # Find approvers at next level
        new_approvers = self._find_approvers_at_level(next_level)
        
        if not new_approvers:
            return False, f"No approvers found at level {next_level.value}"
        
        # Update request
        request.required_level = next_level
        request.required_approvers = new_approvers
        request.escalation_count += 1
        request.escalated_to = next_level.value
        request.status = ApprovalStatus.ESCALATED
        request.updated_at = datetime.utcnow()
        
        # Extend expiry
        request.expires_at = datetime.utcnow() + timedelta(
            minutes=self.policy.timeout_minutes
        )
        
        # Send notifications
        if self.notifier:
            await self.notifier.send_escalation_notification(request, new_approvers)
        
        # Reset status to pending for new approvers
        request.status = ApprovalStatus.PENDING
        
        return True, f"Escalated to {next_level.value}"
    
    async def cancel(self, request_id: str, canceller_id: str) -> tuple[bool, str]:
        """Cancel an approval request."""
        request = self._requests.get(request_id)
        if not request:
            return False, "Request not found"
        
        # Only requester can cancel
        if request.requester_id != canceller_id:
            return False, "Only requester can cancel"
        
        if request.status != ApprovalStatus.PENDING:
            return False, f"Cannot cancel request in {request.status.value} status"
        
        request.status = ApprovalStatus.CANCELLED
        request.resolved_at = datetime.utcnow()
        request.updated_at = datetime.utcnow()
        
        return True, "Request cancelled"
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)
    
    def get_pending_requests(
        self,
        approver_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        pending = [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]
        
        if approver_id:
            pending = [
                r for r in pending
                if approver_id in r.required_approvers
            ]
        
        # Sort by priority and creation time
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        pending.sort(key=lambda r: (priority_order.get(r.priority, 2), r.created_at))
        
        return pending[:limit]
    
    async def check_expired(self) -> list[ApprovalRequest]:
        """Check and mark expired requests."""
        expired: list[ApprovalRequest] = []
        
        for request in self._requests.values():
            if request.status == ApprovalStatus.PENDING and request.is_expired():
                request.status = ApprovalStatus.EXPIRED
                request.resolved_at = datetime.utcnow()
                expired.append(request)
                
                if self._on_expired:
                    await self._on_expired(request)
        
        return expired
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = secrets.token_hex(4)
        return f"AR-{timestamp}-{random_part}"
    
    def _determine_requirements(
        self,
        action: str,
        target: str,
        risk_level: str,
        risk_score: float,
    ) -> tuple[ApprovalLevel, list[str]]:
        """Determine approval requirements."""
        # Start with policy minimum
        level = self.policy.minimum_level
        
        # Increase based on risk
        if risk_score >= 0.8 or risk_level == "critical":
            level = ApprovalLevel.MANAGER
        elif risk_score >= 0.6 or risk_level == "high":
            level = ApprovalLevel.TEAM_LEAD
        
        # Check action-specific requirements
        if action in ["delete", "deploy"]:
            level = max(level, ApprovalLevel.TEAM_LEAD, key=self._level_priority)
        
        # Find approvers
        approvers = self._find_approvers_at_level(level)
        
        return level, approvers
    
    def _find_approvers_at_level(self, level: ApprovalLevel) -> list[str]:
        """Find approvers at or above a given level."""
        return [
            a.id for a in self._approvers.values()
            if self._level_priority(a.approval_level) >= self._level_priority(level)
            and a.available
        ]
    
    def _level_priority(self, level: ApprovalLevel) -> int:
        """Get numeric priority for approval level."""
        return {
            ApprovalLevel.NONE: 0,
            ApprovalLevel.TEAM_MEMBER: 1,
            ApprovalLevel.TEAM_LEAD: 2,
            ApprovalLevel.MANAGER: 3,
            ApprovalLevel.DIRECTOR: 4,
            ApprovalLevel.EXECUTIVE: 5,
            ApprovalLevel.MULTI_PARTY: 6,
        }.get(level, 0)
    
    def _get_next_level(self, current: ApprovalLevel) -> ApprovalLevel:
        """Get the next escalation level."""
        levels = [
            ApprovalLevel.TEAM_MEMBER,
            ApprovalLevel.TEAM_LEAD,
            ApprovalLevel.MANAGER,
            ApprovalLevel.DIRECTOR,
            ApprovalLevel.EXECUTIVE,
        ]
        
        try:
            idx = levels.index(current)
            if idx < len(levels) - 1:
                return levels[idx + 1]
        except ValueError:
            pass
        
        return self.escalation_config.final_escalation_level
    
    def _is_authorized_approver(self, approver: Approver, request: ApprovalRequest) -> bool:
        """Check if approver is authorized for request."""
        # Check if in required approvers list
        if request.required_approvers and approver.id in request.required_approvers:
            return True
        
        # Check if at required level
        if self._level_priority(approver.approval_level) >= self._level_priority(request.required_level):
            return True
        
        # Check group membership
        for group_id in request.required_groups:
            group = self._groups.get(group_id)
            if group and approver.id in group.members:
                return True
        
        return False
    
    def _sign_decision(
        self,
        request_id: str,
        approver_id: str,
        decision: ApprovalStatus,
    ) -> str:
        """Create a signature for the decision."""
        data = f"{request_id}:{approver_id}:{decision.value}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# Convenience function to create a simple approval workflow
def create_simple_workflow(
    approvers: list[dict],
    timeout_minutes: int = 60,
    strategy: ApprovalStrategy = ApprovalStrategy.ANY,
) -> ApprovalWorkflow:
    """Create a simple approval workflow with the given approvers."""
    
    policy = ApprovalPolicy(
        id="simple",
        name="Simple Approval Policy",
        strategy=strategy,
        timeout_minutes=timeout_minutes,
    )
    
    workflow = ApprovalWorkflow(
        policy=policy,
        notifier=ApprovalNotifier(
            config=NotificationConfig(),
        ),
    )
    
    for approver_data in approvers:
        approver = Approver(
            id=approver_data.get("id", approver_data.get("email", "")),
            name=approver_data.get("name", "Unknown"),
            email=approver_data.get("email", ""),
            approval_level=ApprovalLevel(approver_data.get("level", "team_member")),
        )
        workflow.register_approver(approver)
    
    return workflow
