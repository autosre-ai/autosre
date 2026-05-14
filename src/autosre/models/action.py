"""Action models for automated remediation."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now, ExecutionStatus


class ActionType(str, Enum):
    """Type of action to be performed."""
    COMMAND = "command"
    API_CALL = "api_call"
    SCRIPT = "script"
    RUNBOOK = "runbook"
    NOTIFICATION = "notification"
    ESCALATION = "escalation"
    MANUAL = "manual"


class ActionRisk(str, Enum):
    """Risk level of an action."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(BaseModel):
    """An action to be performed during remediation."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Name of the action")
    description: str = Field(default="", description="Detailed description")
    type: ActionType = Field(..., description="Type of action")
    
    # Execution details
    target: str = Field(default="", description="Target system/service/host")
    command: Optional[str] = Field(default=None, description="Command to execute (for command type)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    # Risk and approval
    risk: ActionRisk = Field(default=ActionRisk.LOW, description="Risk level of this action")
    requires_approval: bool = Field(default=False, description="Whether this action requires human approval")
    approved_by: Optional[str] = Field(default=None, description="Who approved the action")
    approved_at: Optional[datetime] = Field(default=None)
    
    # Timing
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Execution timeout in seconds")
    retry_count: int = Field(default=0, ge=0, le=10, description="Number of retries on failure")
    retry_delay_seconds: int = Field(default=10, ge=1, le=300, description="Delay between retries")
    
    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    def is_approved(self) -> bool:
        """Check if action is approved (or doesn't need approval)."""
        if not self.requires_approval:
            return True
        return self.approved_by is not None


class ActionResult(BaseModel):
    """Result of executing an action."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    action_id: str = Field(..., description="ID of the action that was executed")
    status: ExecutionStatus = Field(..., description="Execution status")
    
    # Execution details
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: Optional[datetime] = Field(default=None)
    attempt: int = Field(default=1, ge=1, description="Which attempt this is (1-indexed)")
    
    # Output
    exit_code: Optional[int] = Field(default=None, description="Exit code if applicable")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    output: dict[str, Any] = Field(default_factory=dict, description="Structured output data")
    
    # Error handling
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_details: dict[str, Any] = Field(default_factory=dict, description="Detailed error information")
    
    # Metadata
    executed_by: Optional[str] = Field(default=None, description="Who/what executed this action")
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_success(self) -> bool:
        """Check if the action completed successfully."""
        return self.status == ExecutionStatus.COMPLETED
    
    def is_failure(self) -> bool:
        """Check if the action failed."""
        return self.status == ExecutionStatus.FAILED
    
    def duration_seconds(self) -> float | None:
        """Get execution duration in seconds."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class ActionPlan(BaseModel):
    """A plan consisting of multiple actions to execute."""
    model_config = ConfigDict(validate_assignment=True)
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Name of the action plan")
    description: str = Field(default="")
    actions: list[Action] = Field(default_factory=list)
    parallel: bool = Field(default=False, description="Whether actions can run in parallel")
    stop_on_failure: bool = Field(default=True, description="Whether to stop on first failure")
    created_at: datetime = Field(default_factory=utc_now)
    
    def total_risk(self) -> ActionRisk:
        """Get the highest risk level among all actions."""
        if not self.actions:
            return ActionRisk.NONE
        risk_order = [ActionRisk.CRITICAL, ActionRisk.HIGH, ActionRisk.MEDIUM, ActionRisk.LOW, ActionRisk.NONE]
        for risk in risk_order:
            if any(a.risk == risk for a in self.actions):
                return risk
        return ActionRisk.NONE
    
    def requires_approval(self) -> bool:
        """Check if any action requires approval."""
        return any(a.requires_approval for a in self.actions)
