"""Runbook models for automated incident response."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now, ExecutionStatus
from .action import Action, ActionResult


class StepType(str, Enum):
    """Type of runbook step."""
    ACTION = "action"
    DECISION = "decision"
    PARALLEL = "parallel"
    WAIT = "wait"
    MANUAL = "manual"
    NOTIFICATION = "notification"
    CONDITION = "condition"


class RunbookStep(BaseModel):
    """A single step in a runbook."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Step name")
    description: str = Field(default="", description="Step description")
    type: StepType = Field(default=StepType.ACTION, description="Type of step")
    order: int = Field(default=0, ge=0, description="Execution order")
    
    # Action configuration
    action: Optional[Action] = Field(default=None, description="Action to execute for action steps")
    
    # Conditional execution
    condition: Optional[str] = Field(default=None, description="Condition expression for execution")
    skip_on_failure: bool = Field(default=False, description="Skip this step if previous steps failed")
    
    # Branching
    on_success: Optional[str] = Field(default=None, description="Step ID to go to on success")
    on_failure: Optional[str] = Field(default=None, description="Step ID to go to on failure")
    
    # Timing
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    wait_seconds: int = Field(default=0, ge=0, description="Wait time for wait steps")
    
    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class StepExecution(BaseModel):
    """Execution record for a runbook step."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    step_id: str = Field(..., description="ID of the step being executed")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)
    
    # Results
    action_result: Optional[ActionResult] = Field(default=None, description="Result if this was an action step")
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = Field(default=None)
    
    # Decision tracking
    decision_made: Optional[str] = Field(default=None, description="The decision taken for decision steps")
    skipped: bool = Field(default=False)
    skip_reason: Optional[str] = Field(default=None)
    
    def duration_seconds(self) -> float | None:
        """Get step execution duration in seconds."""
        if self.started_at is None or self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class Runbook(BaseModel):
    """A runbook defining automated incident response."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Runbook name")
    description: str = Field(default="", description="Runbook description")
    version: str = Field(default="1.0.0", description="Runbook version")
    
    # Steps
    steps: list[RunbookStep] = Field(default_factory=list, description="Steps in execution order")
    
    # Triggers
    trigger_alerts: list[str] = Field(default_factory=list, description="Alert names that trigger this runbook")
    trigger_labels: dict[str, str] = Field(default_factory=dict, description="Label matchers for triggering")
    
    # Configuration
    enabled: bool = Field(default=True, description="Whether the runbook is enabled")
    auto_execute: bool = Field(default=False, description="Whether to auto-execute on trigger")
    max_concurrent: int = Field(default=1, ge=1, le=10, description="Max concurrent executions")
    
    # Metadata
    author: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    def get_step(self, step_id: str) -> Optional[RunbookStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def ordered_steps(self) -> list[RunbookStep]:
        """Get steps in execution order."""
        return sorted(self.steps, key=lambda s: s.order)


class RunbookExecution(BaseModel):
    """An execution of a runbook."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    runbook_id: str = Field(..., description="ID of the runbook being executed")
    runbook_version: str = Field(default="1.0.0")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    
    # Trigger info
    triggered_by: str = Field(default="manual", description="What triggered this execution")
    alert_id: Optional[str] = Field(default=None, description="Alert that triggered execution")
    investigation_id: Optional[str] = Field(default=None, description="Related investigation")
    
    # Execution progress
    current_step_id: Optional[str] = Field(default=None, description="Currently executing step")
    step_executions: list[StepExecution] = Field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)
    
    # Results
    output: dict[str, Any] = Field(default_factory=dict, description="Final output/context")
    error: Optional[str] = Field(default=None)
    
    # Metadata
    executed_by: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_complete(self) -> bool:
        """Check if execution is complete."""
        return self.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED)
    
    def is_success(self) -> bool:
        """Check if execution completed successfully."""
        return self.status == ExecutionStatus.COMPLETED
    
    def duration_seconds(self) -> float | None:
        """Get total execution duration in seconds."""
        if self.started_at is None or self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()
    
    def progress(self) -> tuple[int, int]:
        """Get progress as (completed_steps, total_steps)."""
        completed = sum(1 for se in self.step_executions if se.status in (ExecutionStatus.COMPLETED, ExecutionStatus.SKIPPED))
        return (completed, len(self.step_executions))
    
    def get_step_execution(self, step_id: str) -> Optional[StepExecution]:
        """Get the execution record for a specific step."""
        for se in self.step_executions:
            if se.step_id == step_id:
                return se
        return None
