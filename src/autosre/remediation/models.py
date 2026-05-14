"""
Remediation data models.

Defines all data structures used in the remediation framework.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class RiskLevel(str, Enum):
    """Risk level for remediation actions."""
    
    NONE = "none"           # Read-only, no risk
    LOW = "low"             # Minor impact, easily reversible
    MEDIUM = "medium"       # Moderate impact, reversible with effort
    HIGH = "high"           # Significant impact, complex rollback
    CRITICAL = "critical"   # Major impact, requires approval


class ActionType(str, Enum):
    """Types of remediation actions."""
    
    DIAGNOSTIC = "diagnostic"           # Information gathering
    RESTART = "restart"                 # Restart services/pods
    SCALE = "scale"                     # Scale resources
    ROLLBACK = "rollback"               # Rollback deployments
    CONFIG_CHANGE = "config_change"     # Configuration changes
    RESOURCE_ADJUST = "resource_adjust" # CPU/memory adjustment
    NETWORK = "network"                 # Network-related changes
    DRAIN = "drain"                     # Node draining
    CUSTOM = "custom"                   # Custom action


class RemediationStatus(str, Enum):
    """Status of a remediation action or plan."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class RollbackStrategy(str, Enum):
    """Strategy for rollback on failure."""
    
    NONE = "none"                       # No rollback
    AUTOMATIC = "automatic"             # Auto-rollback on failure
    MANUAL = "manual"                   # Manual intervention required
    CHECKPOINT = "checkpoint"           # Rollback to last checkpoint


class ApprovalStatus(str, Enum):
    """Approval status for actions requiring human approval."""
    
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SafetyCheckType(str, Enum):
    """Types of safety checks."""
    
    PRE_FLIGHT = "pre_flight"           # Before execution
    DURING = "during"                   # During execution
    POST_EXECUTION = "post_execution"   # After execution
    CONTINUOUS = "continuous"           # Continuous monitoring


class ActionParameter(BaseModel):
    """Definition of an action parameter."""
    
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (str, int, bool, etc)")
    required: bool = Field(True, description="Whether parameter is required")
    default: Any = Field(None, description="Default value if not provided")
    description: str = Field("", description="Parameter description")
    validation_pattern: str | None = Field(None, description="Regex for validation")
    allowed_values: list[Any] | None = Field(None, description="List of allowed values")
    min_value: float | None = Field(None, description="Minimum value for numeric params")
    max_value: float | None = Field(None, description="Maximum value for numeric params")
    
    def validate_value(self, value: Any) -> tuple[bool, str | None]:
        """
        Validate a parameter value.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        import re
        
        if value is None:
            if self.required and self.default is None:
                return False, f"Parameter '{self.name}' is required"
            return True, None
        
        # Type validation
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "bool": bool,
            "boolean": bool,
            "list": list,
            "dict": dict,
        }
        
        expected_type = type_map.get(self.type.lower())
        if expected_type and not isinstance(value, expected_type):
            return False, f"Parameter '{self.name}' must be of type {self.type}"
        
        # Pattern validation
        if self.validation_pattern and isinstance(value, str):
            if not re.match(self.validation_pattern, value):
                return False, f"Parameter '{self.name}' does not match pattern {self.validation_pattern}"
        
        # Allowed values
        if self.allowed_values is not None:
            if value not in self.allowed_values:
                return False, f"Parameter '{self.name}' must be one of {self.allowed_values}"
        
        # Range validation
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"
        
        return True, None


class ActionDefinition(BaseModel):
    """Definition of a remediation action."""
    
    name: str = Field(..., description="Action name/identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this action does")
    action_type: ActionType = Field(..., description="Type of action")
    
    # Risk and safety
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM, description="Risk level")
    is_destructive: bool = Field(False, description="Whether action is destructive")
    is_reversible: bool = Field(True, description="Whether action can be undone")
    
    # Parameters
    parameters: list[ActionParameter] = Field(default_factory=list)
    
    # Rollback
    rollback_strategy: RollbackStrategy = Field(RollbackStrategy.AUTOMATIC)
    rollback_action: str | None = Field(None, description="Name of rollback action")
    
    # Timing
    estimated_duration_seconds: int = Field(60, description="Estimated execution time")
    timeout_seconds: int = Field(300, description="Maximum execution time")
    cooldown_seconds: int = Field(60, description="Minimum time between executions")
    
    # Targeting
    target_types: list[str] = Field(
        default_factory=list,
        description="Types of resources this action can target (pod, deployment, node, etc)"
    )
    
    # Approval
    requires_approval: bool = Field(False, description="Whether action requires approval")
    approval_roles: list[str] = Field(
        default_factory=list,
        description="Roles that can approve this action"
    )
    
    # Safety checks
    pre_flight_checks: list[str] = Field(
        default_factory=list,
        description="Safety checks to run before execution"
    )
    post_checks: list[str] = Field(
        default_factory=list,
        description="Validation checks after execution"
    )
    
    # Metadata
    tags: list[str] = Field(default_factory=list)
    documentation_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field("1.0.0")
    
    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """
        Validate all parameters.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        for param_def in self.parameters:
            value = params.get(param_def.name, param_def.default)
            is_valid, error = param_def.validate_value(value)
            if not is_valid and error:
                errors.append(error)
        
        # Check for unknown parameters (ignore internal params starting with _)
        known_params = {p.name for p in self.parameters}
        for key in params:
            if not key.startswith("_") and key not in known_params:
                errors.append(f"Unknown parameter: {key}")
        
        return errors


class BlastRadius(BaseModel):
    """Assessment of potential impact from an action."""
    
    affected_pods: int = Field(0, description="Number of pods affected")
    affected_nodes: int = Field(0, description="Number of nodes affected")
    affected_services: list[str] = Field(default_factory=list)
    affected_namespaces: list[str] = Field(default_factory=list)
    affected_users_estimate: int | None = Field(None, description="Estimated user impact")
    
    # Impact assessment
    downtime_risk: float = Field(0.0, ge=0, le=1, description="Risk of downtime")
    data_loss_risk: float = Field(0.0, ge=0, le=1, description="Risk of data loss")
    cascading_failure_risk: float = Field(0.0, ge=0, le=1, description="Risk of cascading failure")
    
    # Dependencies
    upstream_dependencies: list[str] = Field(default_factory=list)
    downstream_dependencies: list[str] = Field(default_factory=list)
    
    # Traffic impact
    traffic_percentage_affected: float = Field(0.0, ge=0, le=100)
    
    @property
    def overall_risk_score(self) -> float:
        """Calculate overall risk score (0-1)."""
        base_score = (
            self.downtime_risk * 0.4 +
            self.data_loss_risk * 0.35 +
            self.cascading_failure_risk * 0.25
        )
        
        # Adjust for scale
        scale_factor = min(1.0, (
            self.affected_pods / 100 +
            self.affected_nodes / 10 +
            len(self.affected_services) / 20
        ) / 3)
        
        return min(1.0, base_score + scale_factor * 0.2)
    
    @property
    def is_safe(self) -> bool:
        """Check if action is within safe limits."""
        return (
            self.overall_risk_score < 0.3 and
            self.data_loss_risk == 0 and
            self.cascading_failure_risk < 0.2
        )


class SafetyCheckResult(BaseModel):
    """Result of a safety check."""
    
    check_type: SafetyCheckType
    check_name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    
    # Severity if failed
    severity: RiskLevel = Field(RiskLevel.LOW)
    is_blocking: bool = Field(False, description="Whether failure blocks execution")
    
    # Recommendations
    recommendations: list[str] = Field(default_factory=list)
    
    # Timing
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float = Field(0.0)


class ApprovalRequest(BaseModel):
    """Request for human approval of an action."""
    
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    action_name: str
    
    # Context
    reason: str = Field(..., description="Why this action needs to be taken")
    context: dict[str, Any] = Field(default_factory=dict)
    blast_radius: BlastRadius | None = None
    safety_checks: list[SafetyCheckResult] = Field(default_factory=list)
    
    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    
    # Request details
    requested_by: str = Field("autosre", description="Who requested the action")
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=4)
    )
    
    # Approval details
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    
    # Notification
    notification_channels: list[str] = Field(default_factory=list)
    escalation_chain: list[str] = Field(default_factory=list)
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def time_remaining_seconds(self) -> float:
        """Get time remaining until expiration."""
        return max(0, (self.expires_at - datetime.utcnow()).total_seconds())


class RemediationAction(BaseModel):
    """A single remediation action instance."""
    
    id: UUID = Field(default_factory=uuid4)
    definition_name: str = Field(..., description="Name of the action definition")
    
    # Target
    target_type: str = Field(..., description="Type of target (pod, deployment, etc)")
    target_name: str = Field(..., description="Name of the target resource")
    target_namespace: str | None = Field(None, description="Kubernetes namespace")
    target_cluster: str | None = Field(None, description="Cluster name")
    
    # Parameters
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Status
    status: RemediationStatus = RemediationStatus.PENDING
    progress_percent: float = Field(0.0, ge=0, le=100)
    status_message: str = ""
    
    # Safety
    dry_run: bool = Field(False, description="Whether this is a dry run")
    safety_checks: list[SafetyCheckResult] = Field(default_factory=list)
    blast_radius: BlastRadius | None = None
    
    # Approval
    approval_request: ApprovalRequest | None = None
    
    # Rollback
    rollback_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Data needed for rollback"
    )
    can_rollback: bool = Field(True)
    rollback_action_id: UUID | None = None
    
    # Result
    result: dict[str, Any] | None = None
    error: str | None = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Metadata
    triggered_by: str = Field("autosre")
    investigation_id: UUID | None = None
    incident_id: str | None = None
    correlation_id: UUID | None = None
    
    @property
    def duration_seconds(self) -> float | None:
        """Get action duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None
    
    @property
    def is_terminal(self) -> bool:
        """Check if action is in a terminal state."""
        return self.status in (
            RemediationStatus.COMPLETED,
            RemediationStatus.FAILED,
            RemediationStatus.CANCELLED,
            RemediationStatus.REJECTED,
        )
    
    def to_context_string(self) -> str:
        """Format action for LLM context."""
        lines = [
            f"Action: {self.definition_name}",
            f"Target: {self.target_type}/{self.target_namespace}/{self.target_name}",
            f"Status: {self.status.value}",
        ]
        if self.dry_run:
            lines.append("Mode: DRY RUN")
        if self.status_message:
            lines.append(f"Message: {self.status_message}")
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.duration_seconds:
            lines.append(f"Duration: {self.duration_seconds:.1f}s")
        return "\n".join(lines)


class RemediationPlan(BaseModel):
    """A plan containing multiple remediation actions."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Plan name")
    description: str = Field(..., description="What this plan does")
    
    # Actions
    actions: list[RemediationAction] = Field(default_factory=list)
    execution_order: list[UUID] = Field(
        default_factory=list,
        description="Order in which to execute actions"
    )
    
    # Execution mode
    parallel: bool = Field(False, description="Execute actions in parallel")
    stop_on_failure: bool = Field(True, description="Stop execution on first failure")
    
    # Status
    status: RemediationStatus = RemediationStatus.PENDING
    current_action_index: int = Field(0)
    progress_percent: float = Field(0.0, ge=0, le=100)
    
    # Context
    incident_id: str | None = None
    investigation_id: UUID | None = None
    alert_ids: list[UUID] = Field(default_factory=list)
    
    # Safety
    overall_risk_level: RiskLevel = Field(RiskLevel.MEDIUM)
    total_blast_radius: BlastRadius | None = None
    requires_approval: bool = Field(False)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_duration_seconds: int = Field(0)
    
    # Creator
    created_by: str = Field("autosre")
    approved_by: str | None = None
    
    @property
    def completed_actions(self) -> int:
        """Count of completed actions."""
        return sum(1 for a in self.actions if a.status == RemediationStatus.COMPLETED)
    
    @property
    def failed_actions(self) -> int:
        """Count of failed actions."""
        return sum(1 for a in self.actions if a.status == RemediationStatus.FAILED)
    
    @property
    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return all(a.is_terminal for a in self.actions)
    
    def get_next_action(self) -> RemediationAction | None:
        """Get the next action to execute."""
        if self.execution_order:
            for action_id in self.execution_order:
                action = next((a for a in self.actions if a.id == action_id), None)
                if action and action.status == RemediationStatus.PENDING:
                    return action
        else:
            for action in self.actions:
                if action.status == RemediationStatus.PENDING:
                    return action
        return None
    
    def calculate_risk_level(self) -> RiskLevel:
        """Calculate overall risk level from actions."""
        risk_order = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        
        max_risk = RiskLevel.NONE
        for action in self.actions:
            # This would need the action definition to be looked up
            # For now, we'll use a simple heuristic
            if action.blast_radius:
                score = action.blast_radius.overall_risk_score
                if score > 0.7:
                    max_risk = max(max_risk, RiskLevel.CRITICAL, key=lambda x: risk_order.index(x))
                elif score > 0.5:
                    max_risk = max(max_risk, RiskLevel.HIGH, key=lambda x: risk_order.index(x))
                elif score > 0.3:
                    max_risk = max(max_risk, RiskLevel.MEDIUM, key=lambda x: risk_order.index(x))
                else:
                    max_risk = max(max_risk, RiskLevel.LOW, key=lambda x: risk_order.index(x))
        
        return max_risk


class RemediationResult(BaseModel):
    """Result of a remediation action or plan execution."""
    
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID | None = None
    plan_id: UUID | None = None
    
    # Outcome
    success: bool
    status: RemediationStatus
    message: str = ""
    
    # Details
    result_data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    stack_trace: str | None = None
    
    # Rollback info
    was_rolled_back: bool = Field(False)
    rollback_success: bool | None = None
    rollback_error: str | None = None
    
    # Metrics
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    retries: int = Field(0)
    
    # Impact
    resources_modified: list[str] = Field(default_factory=list)
    actual_blast_radius: BlastRadius | None = None
    
    @property
    def duration_seconds(self) -> float:
        """Get execution duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_summary(self) -> str:
        """Generate a summary of the result."""
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        lines = [
            f"{status}: {self.message}",
            f"Duration: {self.duration_seconds:.1f}s",
        ]
        if self.retries:
            lines.append(f"Retries: {self.retries}")
        if self.was_rolled_back:
            rb_status = "✅" if self.rollback_success else "❌"
            lines.append(f"Rollback: {rb_status}")
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.resources_modified:
            lines.append(f"Modified: {', '.join(self.resources_modified[:5])}")
            if len(self.resources_modified) > 5:
                lines.append(f"  ... and {len(self.resources_modified) - 5} more")
        return "\n".join(lines)
