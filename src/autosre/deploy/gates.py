"""
Deployment Gates Module

Provides deployment gate functionality for controlled rollouts:
- Approval gates (manual, automated, multi-approver)
- Metric gates (SLO-based, threshold-based)
- Time gates (time windows, freeze periods)
- Manual gates (explicit approval)
- Gate pipelines (chained gates)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    """Status of a deployment gate."""
    
    PENDING = "pending"
    EVALUATING = "evaluating"
    WAITING = "waiting"
    APPROVED = "approved"
    DENIED = "denied"
    BYPASSED = "bypassed"
    EXPIRED = "expired"
    ERROR = "error"


class GateType(str, Enum):
    """Type of deployment gate."""
    
    APPROVAL = "approval"
    METRIC = "metric"
    TIME = "time"
    MANUAL = "manual"
    AUTOMATED = "automated"
    CUSTOM = "custom"


class GateConfig(BaseModel):
    """Configuration for deployment gates."""
    
    # Basic settings
    name: str = "deployment-gate"
    description: str = ""
    
    # Gate behavior
    required: bool = True
    timeout_seconds: int = Field(default=3600, ge=60)  # 1 hour default
    allow_bypass: bool = False
    bypass_roles: list[str] = Field(default_factory=list)
    
    # Notification
    notify_on_pending: bool = True
    notify_on_result: bool = True
    notification_channels: list[str] = Field(default_factory=list)
    
    # Retry
    retry_on_error: bool = True
    max_retries: int = Field(default=3, ge=0)
    retry_interval_seconds: int = Field(default=30, ge=5)


class GatePolicy(BaseModel):
    """Policy for gate evaluation."""
    
    name: str = "default-policy"
    
    # Enforcement
    enforce_all_gates: bool = True
    min_gates_required: int = Field(default=1, ge=0)
    
    # Ordering
    sequential: bool = True  # Gates must pass in order
    
    # Approval settings
    require_different_approvers: bool = True
    min_approvers: int = Field(default=1, ge=1)
    
    # Time restrictions
    business_hours_only: bool = False
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    
    # Freeze periods
    freeze_periods: list[dict[str, str]] = Field(default_factory=list)
    
    # Auto-approval
    auto_approve_staging: bool = True
    auto_approve_on_metrics: bool = False


@dataclass
class GateResult:
    """Result of a gate evaluation."""
    
    gate_name: str
    gate_type: GateType
    status: GateStatus = GateStatus.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Details
    message: str = ""
    approver: Optional[str] = None
    reason: Optional[str] = None
    
    # Metrics (for metric gates)
    metric_values: dict[str, float] = field(default_factory=dict)
    threshold_met: bool = False
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def duration_seconds(self) -> Optional[float]:
        """Calculate gate duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gate_name": self.gate_name,
            "gate_type": self.gate_type.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds(),
            "message": self.message,
            "approver": self.approver,
            "reason": self.reason,
            "metric_values": self.metric_values,
            "threshold_met": self.threshold_met,
            "metadata": self.metadata,
        }


class GateEvaluator:
    """Base class for gate evaluation logic."""
    
    def __init__(self, config: GateConfig):
        self.config = config
    
    async def evaluate(self, context: dict[str, Any]) -> GateResult:
        """Evaluate the gate. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement evaluate()")
    
    async def wait_for_approval(
        self,
        result: GateResult,
        timeout_seconds: Optional[int] = None,
    ) -> GateResult:
        """Wait for external approval."""
        raise NotImplementedError("Subclasses must implement wait_for_approval()")


# ============================================================================
# Approval Gate
# ============================================================================

class ApprovalConfig(BaseModel):
    """Configuration for approval gates."""
    
    # Approvers
    approvers: list[str] = Field(default_factory=list)
    approver_groups: list[str] = Field(default_factory=list)
    
    # Requirements
    min_approvers: int = Field(default=1, ge=1)
    require_different_approvers: bool = True
    
    # Auto-approval
    auto_approve_conditions: list[str] = Field(default_factory=list)
    auto_approve_for_rollback: bool = True
    
    # Timeout
    approval_timeout_seconds: int = Field(default=3600, ge=60)
    
    # Escalation
    escalate_after_seconds: int = Field(default=1800, ge=0)
    escalation_approvers: list[str] = Field(default_factory=list)


@dataclass
class ApprovalRequest:
    """Request for deployment approval."""
    
    id: str
    deployment_name: str
    namespace: str
    
    # Requestor
    requested_by: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Details
    version: str = ""
    change_description: str = ""
    risk_level: str = "medium"  # low, medium, high, critical
    
    # Approvers
    required_approvers: list[str] = field(default_factory=list)
    current_approvers: list[str] = field(default_factory=list)
    
    # Status
    status: GateStatus = GateStatus.PENDING
    expires_at: Optional[datetime] = None
    
    # Links
    pr_link: Optional[str] = None
    diff_link: Optional[str] = None
    runbook_link: Optional[str] = None
    
    def is_approved(self, min_approvers: int = 1) -> bool:
        """Check if request has sufficient approvals."""
        return len(self.current_approvers) >= min_approvers
    
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False


@dataclass
class ApprovalDecision:
    """Decision on an approval request."""
    
    request_id: str
    approved: bool
    
    # Approver
    approver: str
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Details
    reason: str = ""
    conditions: list[str] = field(default_factory=list)
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalGate:
    """Gate requiring manual or automated approval."""
    
    def __init__(
        self,
        config: ApprovalConfig,
        gate_config: Optional[GateConfig] = None,
        approval_callback: Optional[Callable[[ApprovalRequest], None]] = None,
    ):
        self.config = config
        self.gate_config = gate_config or GateConfig(name="approval-gate")
        self.approval_callback = approval_callback
        
        # State
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, list[ApprovalDecision]] = {}
    
    async def request_approval(
        self,
        deployment_name: str,
        namespace: str,
        requested_by: str,
        version: str = "",
        change_description: str = "",
        risk_level: str = "medium",
    ) -> ApprovalRequest:
        """Create an approval request."""
        import uuid
        
        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            deployment_name=deployment_name,
            namespace=namespace,
            requested_by=requested_by,
            version=version,
            change_description=change_description,
            risk_level=risk_level,
            required_approvers=self.config.approvers.copy(),
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=self.config.approval_timeout_seconds
            ),
        )
        
        self._pending_requests[request.id] = request
        self._decisions[request.id] = []
        
        # Notify approvers
        if self.approval_callback:
            self.approval_callback(request)
        
        return request
    
    async def submit_decision(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        reason: str = "",
    ) -> ApprovalDecision:
        """Submit an approval decision."""
        request = self._pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.is_expired():
            raise ValueError(f"Request {request_id} has expired")
        
        # Check if approver is authorized
        if self.config.approvers and approver not in self.config.approvers:
            raise ValueError(f"Approver {approver} is not authorized")
        
        # Check for duplicate approval
        if self.config.require_different_approvers:
            if approver in request.current_approvers:
                raise ValueError(f"Approver {approver} has already approved this request")
        
        decision = ApprovalDecision(
            request_id=request_id,
            approved=approved,
            approver=approver,
            reason=reason,
        )
        
        self._decisions[request_id].append(decision)
        
        if approved:
            request.current_approvers.append(approver)
            
            # Check if fully approved
            if request.is_approved(self.config.min_approvers):
                request.status = GateStatus.APPROVED
        else:
            # Any denial fails the request
            request.status = GateStatus.DENIED
        
        return decision
    
    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate the approval gate."""
        result = GateResult(
            gate_name=self.gate_config.name,
            gate_type=GateType.APPROVAL,
            started_at=datetime.now(timezone.utc),
        )
        
        deployment_name = context.get("deployment_name", "")
        namespace = context.get("namespace", "default")
        requested_by = context.get("requested_by", "system")
        
        # Check for auto-approval conditions
        if await self._check_auto_approval(context):
            result.status = GateStatus.APPROVED
            result.message = "Auto-approved based on conditions"
            result.completed_at = datetime.now(timezone.utc)
            return result
        
        # Create approval request
        request = await self.request_approval(
            deployment_name=deployment_name,
            namespace=namespace,
            requested_by=requested_by,
            version=context.get("version", ""),
            change_description=context.get("change_description", ""),
            risk_level=context.get("risk_level", "medium"),
        )
        
        result.status = GateStatus.WAITING
        result.message = f"Waiting for approval from {self.config.min_approvers} approver(s)"
        result.metadata["request_id"] = request.id
        
        # Wait for approval
        timeout = self.config.approval_timeout_seconds
        deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout)
        
        while datetime.now(timezone.utc) < deadline:
            request = self._pending_requests.get(request.id)
            
            if request.status == GateStatus.APPROVED:
                result.status = GateStatus.APPROVED
                result.message = "Deployment approved"
                result.approver = ", ".join(request.current_approvers)
                break
            elif request.status == GateStatus.DENIED:
                result.status = GateStatus.DENIED
                decisions = self._decisions.get(request.id, [])
                denied_by = [d for d in decisions if not d.approved]
                if denied_by:
                    result.message = f"Denied by {denied_by[0].approver}: {denied_by[0].reason}"
                else:
                    result.message = "Deployment denied"
                break
            
            await asyncio.sleep(5)
        
        if result.status == GateStatus.WAITING:
            result.status = GateStatus.EXPIRED
            result.message = f"Approval timed out after {timeout} seconds"
        
        result.completed_at = datetime.now(timezone.utc)
        return result
    
    async def _check_auto_approval(self, context: dict[str, Any]) -> bool:
        """Check if auto-approval conditions are met."""
        # Auto-approve rollbacks if configured
        if self.config.auto_approve_for_rollback:
            if context.get("is_rollback", False):
                return True
        
        # Check custom conditions
        for condition in self.config.auto_approve_conditions:
            if condition == "staging" and context.get("environment") == "staging":
                return True
            if condition == "low_risk" and context.get("risk_level") == "low":
                return True
        
        return False
    
    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return [
            r for r in self._pending_requests.values()
            if r.status == GateStatus.PENDING or r.status == GateStatus.WAITING
        ]


# ============================================================================
# Metric Gate
# ============================================================================

class MetricCondition(BaseModel):
    """Condition for metric-based gate evaluation."""
    
    metric: str
    operator: str = ">="  # >=, <=, >, <, ==, !=
    threshold: float
    
    # Query
    query: str = ""
    aggregation: str = "avg"  # avg, sum, min, max, p50, p95, p99
    
    # Duration
    evaluation_window_seconds: int = Field(default=300, ge=60)
    
    # Weight
    weight: float = Field(default=1.0, ge=0.0)
    required: bool = True
    
    def evaluate(self, value: float) -> bool:
        """Evaluate if condition is met."""
        operators = {
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t,
        }
        return operators.get(self.operator, lambda v, t: False)(value, self.threshold)


class MetricGateConfig(BaseModel):
    """Configuration for metric-based gates."""
    
    # Conditions
    conditions: list[MetricCondition] = Field(default_factory=list)
    
    # Evaluation
    require_all_conditions: bool = True
    min_conditions_met: int = Field(default=1, ge=0)
    
    # Timing
    evaluation_interval_seconds: int = Field(default=30, ge=10)
    min_evaluation_duration_seconds: int = Field(default=300, ge=60)
    
    # Sample requirements
    min_samples: int = Field(default=100, ge=1)
    
    # Default SLO conditions
    max_error_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    max_latency_p99_ms: float = Field(default=1000.0, ge=0.0)
    min_success_rate: float = Field(default=0.99, ge=0.0, le=1.0)


class MetricGate:
    """Gate based on metric conditions (SLO-based)."""
    
    def __init__(
        self,
        config: MetricGateConfig,
        gate_config: Optional[GateConfig] = None,
        metrics_client: Optional[Any] = None,
    ):
        self.config = config
        self.gate_config = gate_config or GateConfig(name="metric-gate")
        self.metrics_client = metrics_client
        
        # Setup default conditions if none provided
        if not self.config.conditions:
            self._setup_default_conditions()
    
    def _setup_default_conditions(self) -> None:
        """Set up default SLO conditions."""
        self.config.conditions = [
            MetricCondition(
                metric="error_rate",
                operator="<=",
                threshold=self.config.max_error_rate,
                query='sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))',
                required=True,
            ),
            MetricCondition(
                metric="success_rate",
                operator=">=",
                threshold=self.config.min_success_rate,
                query='sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m]))',
                required=True,
            ),
            MetricCondition(
                metric="latency_p99",
                operator="<=",
                threshold=self.config.max_latency_p99_ms,
                query='histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) * 1000',
                required=False,
            ),
        ]
    
    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate the metric gate."""
        result = GateResult(
            gate_name=self.gate_config.name,
            gate_type=GateType.METRIC,
            started_at=datetime.now(timezone.utc),
        )
        
        deployment_name = context.get("deployment_name", "")
        namespace = context.get("namespace", "default")
        
        try:
            # Evaluate each condition
            conditions_met = 0
            failed_conditions: list[str] = []
            
            for condition in self.config.conditions:
                value = await self._query_metric(
                    condition,
                    deployment_name,
                    namespace,
                )
                
                if value is not None:
                    result.metric_values[condition.metric] = value
                    
                    if condition.evaluate(value):
                        conditions_met += 1
                    elif condition.required:
                        failed_conditions.append(
                            f"{condition.metric}: {value:.4f} {condition.operator} {condition.threshold}"
                        )
                else:
                    if condition.required:
                        failed_conditions.append(f"{condition.metric}: no data")
            
            # Determine result
            if self.config.require_all_conditions:
                required_conditions = [c for c in self.config.conditions if c.required]
                if conditions_met >= len(required_conditions):
                    result.status = GateStatus.APPROVED
                    result.message = f"All {conditions_met} metric conditions met"
                    result.threshold_met = True
                else:
                    result.status = GateStatus.DENIED
                    result.message = f"Metric conditions not met: {', '.join(failed_conditions)}"
            else:
                if conditions_met >= self.config.min_conditions_met:
                    result.status = GateStatus.APPROVED
                    result.message = f"{conditions_met}/{len(self.config.conditions)} conditions met"
                    result.threshold_met = True
                else:
                    result.status = GateStatus.DENIED
                    result.message = f"Only {conditions_met} conditions met, need {self.config.min_conditions_met}"
        
        except Exception as e:
            result.status = GateStatus.ERROR
            result.message = f"Metric evaluation error: {str(e)}"
        
        result.completed_at = datetime.now(timezone.utc)
        return result
    
    async def _query_metric(
        self,
        condition: MetricCondition,
        deployment_name: str,
        namespace: str,
    ) -> Optional[float]:
        """Query metric value."""
        if self.metrics_client:
            return await self.metrics_client.query(
                condition.query,
                {
                    "deployment": deployment_name,
                    "namespace": namespace,
                },
            )
        return None


# ============================================================================
# Time Gate
# ============================================================================

class TimeWindow(BaseModel):
    """Time window configuration."""
    
    # Days (0=Monday, 6=Sunday)
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    
    # Time range (24-hour format)
    start_time: str = "09:00"
    end_time: str = "17:00"
    
    # Timezone
    timezone: str = "UTC"


class TimeGateConfig(BaseModel):
    """Configuration for time-based gates."""
    
    # Allowed windows
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    
    # Freeze periods (no deployments allowed)
    freeze_periods: list[dict[str, str]] = Field(default_factory=list)
    
    # Default behavior
    allow_outside_windows: bool = False
    require_approval_outside_windows: bool = True
    
    # Business hours default
    enforce_business_hours: bool = True
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class TimeGate:
    """Gate based on time windows and freeze periods."""
    
    def __init__(
        self,
        config: TimeGateConfig,
        gate_config: Optional[GateConfig] = None,
    ):
        self.config = config
        self.gate_config = gate_config or GateConfig(name="time-gate")
    
    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate the time gate."""
        result = GateResult(
            gate_name=self.gate_config.name,
            gate_type=GateType.TIME,
            started_at=datetime.now(timezone.utc),
        )
        
        now = datetime.now(timezone.utc)
        current_day = now.weekday()
        current_time = now.time()
        
        try:
            # Check freeze periods
            for freeze in self.config.freeze_periods:
                freeze_start = datetime.fromisoformat(freeze.get("start", ""))
                freeze_end = datetime.fromisoformat(freeze.get("end", ""))
                
                if freeze_start <= now <= freeze_end:
                    result.status = GateStatus.DENIED
                    result.message = f"Deployment freeze in effect until {freeze_end.isoformat()}"
                    result.reason = freeze.get("reason", "Scheduled freeze period")
                    result.completed_at = datetime.now(timezone.utc)
                    return result
            
            # Check allowed windows
            if self.config.allowed_windows:
                in_window = False
                for window in self.config.allowed_windows:
                    if current_day in window.days:
                        start = time.fromisoformat(window.start_time)
                        end = time.fromisoformat(window.end_time)
                        
                        if start <= current_time <= end:
                            in_window = True
                            break
                
                if in_window:
                    result.status = GateStatus.APPROVED
                    result.message = "Within allowed deployment window"
                elif self.config.allow_outside_windows:
                    result.status = GateStatus.APPROVED
                    result.message = "Outside window but allowed"
                else:
                    result.status = GateStatus.DENIED
                    result.message = "Outside allowed deployment windows"
            
            # Check business hours if enforced
            elif self.config.enforce_business_hours:
                if current_day in self.config.business_days:
                    start = time.fromisoformat(self.config.business_hours_start)
                    end = time.fromisoformat(self.config.business_hours_end)
                    
                    if start <= current_time <= end:
                        result.status = GateStatus.APPROVED
                        result.message = "Within business hours"
                    else:
                        result.status = GateStatus.DENIED
                        result.message = f"Outside business hours ({self.config.business_hours_start}-{self.config.business_hours_end})"
                else:
                    result.status = GateStatus.DENIED
                    result.message = "Not a business day"
            else:
                result.status = GateStatus.APPROVED
                result.message = "No time restrictions configured"
        
        except Exception as e:
            result.status = GateStatus.ERROR
            result.message = f"Time gate evaluation error: {str(e)}"
        
        result.completed_at = datetime.now(timezone.utc)
        result.metadata["evaluated_at"] = now.isoformat()
        result.metadata["day_of_week"] = current_day
        result.metadata["time"] = current_time.isoformat()
        
        return result


# ============================================================================
# Manual Gate
# ============================================================================

class ManualGateConfig(BaseModel):
    """Configuration for manual gates."""
    
    # Prompt
    prompt_message: str = "Please confirm to proceed with deployment"
    
    # Confirmation
    require_confirmation_text: bool = False
    confirmation_text: str = "DEPLOY"
    
    # Instructions
    instructions: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    
    # Timeout
    timeout_seconds: int = Field(default=3600, ge=60)
    
    # Links
    runbook_url: Optional[str] = None
    dashboard_url: Optional[str] = None


class ManualGate:
    """Gate requiring explicit manual confirmation."""
    
    def __init__(
        self,
        config: ManualGateConfig,
        gate_config: Optional[GateConfig] = None,
        confirmation_callback: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.gate_config = gate_config or GateConfig(name="manual-gate")
        self.confirmation_callback = confirmation_callback
        
        # State
        self._waiting_confirmations: dict[str, dict[str, Any]] = {}
    
    async def request_confirmation(
        self,
        deployment_name: str,
        namespace: str,
    ) -> str:
        """Request manual confirmation."""
        import uuid
        
        confirmation_id = str(uuid.uuid4())
        self._waiting_confirmations[confirmation_id] = {
            "deployment_name": deployment_name,
            "namespace": namespace,
            "requested_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.config.timeout_seconds),
            "confirmed": False,
            "confirmation_text": None,
        }
        
        return confirmation_id
    
    async def confirm(
        self,
        confirmation_id: str,
        confirmation_text: Optional[str] = None,
    ) -> bool:
        """Submit confirmation."""
        if confirmation_id not in self._waiting_confirmations:
            raise ValueError(f"Confirmation {confirmation_id} not found")
        
        confirmation = self._waiting_confirmations[confirmation_id]
        
        if datetime.now(timezone.utc) > confirmation["expires_at"]:
            raise ValueError(f"Confirmation {confirmation_id} has expired")
        
        # Validate confirmation text if required
        if self.config.require_confirmation_text:
            if confirmation_text != self.config.confirmation_text:
                return False
        
        confirmation["confirmed"] = True
        confirmation["confirmation_text"] = confirmation_text
        confirmation["confirmed_at"] = datetime.now(timezone.utc)
        
        return True
    
    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate the manual gate."""
        result = GateResult(
            gate_name=self.gate_config.name,
            gate_type=GateType.MANUAL,
            started_at=datetime.now(timezone.utc),
        )
        
        deployment_name = context.get("deployment_name", "")
        namespace = context.get("namespace", "default")
        
        # Request confirmation
        confirmation_id = await self.request_confirmation(deployment_name, namespace)
        result.metadata["confirmation_id"] = confirmation_id
        result.status = GateStatus.WAITING
        result.message = self.config.prompt_message
        
        # If callback provided, use it
        if self.confirmation_callback:
            confirmed = self.confirmation_callback()
            if confirmed:
                result.status = GateStatus.APPROVED
                result.message = "Manual confirmation received"
            else:
                result.status = GateStatus.DENIED
                result.message = "Manual confirmation denied"
            result.completed_at = datetime.now(timezone.utc)
            return result
        
        # Wait for external confirmation
        deadline = datetime.now(timezone.utc) + timedelta(seconds=self.config.timeout_seconds)
        
        while datetime.now(timezone.utc) < deadline:
            confirmation = self._waiting_confirmations.get(confirmation_id)
            
            if confirmation and confirmation["confirmed"]:
                result.status = GateStatus.APPROVED
                result.message = "Manual confirmation received"
                break
            
            await asyncio.sleep(5)
        
        if result.status == GateStatus.WAITING:
            result.status = GateStatus.EXPIRED
            result.message = f"Manual confirmation timed out after {self.config.timeout_seconds} seconds"
        
        result.completed_at = datetime.now(timezone.utc)
        return result


# ============================================================================
# Deployment Gate (Composite)
# ============================================================================

class DeploymentGate:
    """Main deployment gate that can combine multiple gate types."""
    
    def __init__(
        self,
        config: GateConfig,
        gate_type: GateType = GateType.AUTOMATED,
    ):
        self.config = config
        self.gate_type = gate_type
        
        # Sub-gates
        self._approval_gate: Optional[ApprovalGate] = None
        self._metric_gate: Optional[MetricGate] = None
        self._time_gate: Optional[TimeGate] = None
        self._manual_gate: Optional[ManualGate] = None
    
    def set_approval_gate(self, gate: ApprovalGate) -> None:
        """Set the approval gate."""
        self._approval_gate = gate
    
    def set_metric_gate(self, gate: MetricGate) -> None:
        """Set the metric gate."""
        self._metric_gate = gate
    
    def set_time_gate(self, gate: TimeGate) -> None:
        """Set the time gate."""
        self._time_gate = gate
    
    def set_manual_gate(self, gate: ManualGate) -> None:
        """Set the manual gate."""
        self._manual_gate = gate
    
    async def evaluate(
        self,
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate all configured gates."""
        result = GateResult(
            gate_name=self.config.name,
            gate_type=self.gate_type,
            started_at=datetime.now(timezone.utc),
        )
        
        sub_results: list[GateResult] = []
        
        try:
            # Evaluate time gate first (quick check)
            if self._time_gate:
                time_result = await self._time_gate.evaluate(context)
                sub_results.append(time_result)
                
                if time_result.status == GateStatus.DENIED:
                    result.status = GateStatus.DENIED
                    result.message = f"Time gate: {time_result.message}"
                    result.completed_at = datetime.now(timezone.utc)
                    return result
            
            # Evaluate metric gate
            if self._metric_gate:
                metric_result = await self._metric_gate.evaluate(context)
                sub_results.append(metric_result)
                result.metric_values = metric_result.metric_values
                
                if metric_result.status == GateStatus.DENIED:
                    result.status = GateStatus.DENIED
                    result.message = f"Metric gate: {metric_result.message}"
                    result.completed_at = datetime.now(timezone.utc)
                    return result
            
            # Evaluate approval gate
            if self._approval_gate:
                approval_result = await self._approval_gate.evaluate(context)
                sub_results.append(approval_result)
                result.approver = approval_result.approver
                
                if approval_result.status not in [GateStatus.APPROVED]:
                    result.status = approval_result.status
                    result.message = f"Approval gate: {approval_result.message}"
                    result.completed_at = datetime.now(timezone.utc)
                    return result
            
            # Evaluate manual gate
            if self._manual_gate:
                manual_result = await self._manual_gate.evaluate(context)
                sub_results.append(manual_result)
                
                if manual_result.status not in [GateStatus.APPROVED]:
                    result.status = manual_result.status
                    result.message = f"Manual gate: {manual_result.message}"
                    result.completed_at = datetime.now(timezone.utc)
                    return result
            
            # All gates passed
            result.status = GateStatus.APPROVED
            result.message = f"All {len(sub_results)} gates passed"
            result.metadata["sub_results"] = [r.to_dict() for r in sub_results]
        
        except Exception as e:
            result.status = GateStatus.ERROR
            result.message = f"Gate evaluation error: {str(e)}"
        
        result.completed_at = datetime.now(timezone.utc)
        return result


# ============================================================================
# Gate Pipeline
# ============================================================================

@dataclass
class PipelineStage:
    """Stage in a gate pipeline."""
    
    name: str
    gate: DeploymentGate
    required: bool = True
    continue_on_failure: bool = False
    
    # Timing
    timeout_seconds: int = 3600
    
    # Dependencies
    depends_on: list[str] = field(default_factory=list)
    
    # Result
    result: Optional[GateResult] = None


@dataclass
class PipelineResult:
    """Result of a gate pipeline execution."""
    
    pipeline_name: str
    status: GateStatus = GateStatus.PENDING
    
    # Stages
    stage_results: list[GateResult] = field(default_factory=list)
    
    # Summary
    total_stages: int = 0
    passed_stages: int = 0
    failed_stages: int = 0
    skipped_stages: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Message
    message: str = ""
    
    def duration_seconds(self) -> Optional[float]:
        """Calculate pipeline duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "total_stages": self.total_stages,
            "passed_stages": self.passed_stages,
            "failed_stages": self.failed_stages,
            "skipped_stages": self.skipped_stages,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds(),
            "message": self.message,
            "stage_results": [r.to_dict() for r in self.stage_results],
        }


class GatePipeline:
    """Pipeline of deployment gates to execute in sequence."""
    
    def __init__(
        self,
        name: str,
        policy: Optional[GatePolicy] = None,
    ):
        self.name = name
        self.policy = policy or GatePolicy()
        
        # Stages
        self._stages: list[PipelineStage] = []
    
    def add_stage(
        self,
        name: str,
        gate: DeploymentGate,
        required: bool = True,
        depends_on: Optional[list[str]] = None,
    ) -> None:
        """Add a stage to the pipeline."""
        stage = PipelineStage(
            name=name,
            gate=gate,
            required=required,
            depends_on=depends_on or [],
        )
        self._stages.append(stage)
    
    async def execute(
        self,
        context: dict[str, Any],
    ) -> PipelineResult:
        """Execute the gate pipeline."""
        result = PipelineResult(
            pipeline_name=self.name,
            total_stages=len(self._stages),
            started_at=datetime.now(timezone.utc),
        )
        
        completed_stages: dict[str, GateResult] = {}
        
        try:
            for stage in self._stages:
                # Check dependencies
                deps_met = all(
                    dep in completed_stages and
                    completed_stages[dep].status == GateStatus.APPROVED
                    for dep in stage.depends_on
                )
                
                if not deps_met:
                    # Skip this stage
                    stage_result = GateResult(
                        gate_name=stage.name,
                        gate_type=GateType.CUSTOM,
                        status=GateStatus.BYPASSED,
                        message="Dependencies not met",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    result.stage_results.append(stage_result)
                    result.skipped_stages += 1
                    continue
                
                # Execute gate
                stage_result = await asyncio.wait_for(
                    stage.gate.evaluate(context),
                    timeout=stage.timeout_seconds,
                )
                
                stage.result = stage_result
                result.stage_results.append(stage_result)
                completed_stages[stage.name] = stage_result
                
                if stage_result.status == GateStatus.APPROVED:
                    result.passed_stages += 1
                elif stage_result.status in [GateStatus.DENIED, GateStatus.ERROR, GateStatus.EXPIRED]:
                    result.failed_stages += 1
                    
                    if stage.required and not stage.continue_on_failure:
                        # Pipeline failed
                        result.status = GateStatus.DENIED
                        result.message = f"Pipeline failed at stage '{stage.name}': {stage_result.message}"
                        break
                else:
                    result.skipped_stages += 1
            
            # Determine final status
            if result.status == GateStatus.PENDING:
                if self.policy.enforce_all_gates:
                    if result.failed_stages == 0:
                        result.status = GateStatus.APPROVED
                        result.message = f"All {result.passed_stages} stages passed"
                    else:
                        result.status = GateStatus.DENIED
                        result.message = f"{result.failed_stages} stage(s) failed"
                else:
                    if result.passed_stages >= self.policy.min_gates_required:
                        result.status = GateStatus.APPROVED
                        result.message = f"{result.passed_stages} stages passed (minimum: {self.policy.min_gates_required})"
                    else:
                        result.status = GateStatus.DENIED
                        result.message = f"Only {result.passed_stages} stages passed, need {self.policy.min_gates_required}"
        
        except asyncio.TimeoutError:
            result.status = GateStatus.EXPIRED
            result.message = "Pipeline execution timed out"
        except Exception as e:
            result.status = GateStatus.ERROR
            result.message = f"Pipeline execution error: {str(e)}"
        
        result.completed_at = datetime.now(timezone.utc)
        return result
    
    def get_stages(self) -> list[PipelineStage]:
        """Get all pipeline stages."""
        return self._stages.copy()
