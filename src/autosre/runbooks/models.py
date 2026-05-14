"""
Runbook data models.

Defines all data structures for runbook automation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepType(str, Enum):
    """Type of runbook step."""
    
    COMMAND = "command"           # Shell command
    KUBERNETES = "kubernetes"     # Kubernetes operation
    PROMETHEUS = "prometheus"     # Prometheus query
    HTTP = "http"                 # HTTP request
    WAIT = "wait"                 # Wait/sleep
    APPROVAL = "approval"         # Human approval
    CONDITION = "condition"       # Conditional branch
    PARALLEL = "parallel"         # Parallel steps
    SCRIPT = "script"             # Python/bash script
    NOTIFY = "notify"             # Send notification
    ESCALATE = "escalate"         # Escalate to oncall
    MANUAL = "manual"             # Manual instruction
    ROLLBACK = "rollback"         # Rollback operation


class ExecutionStatus(str, Enum):
    """Status of runbook execution."""
    
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class VariableType(str, Enum):
    """Type of runbook variable."""
    
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    SECRET = "secret"
    ENVIRONMENT = "environment"


class ConditionOperator(str, Enum):
    """Operators for conditions."""
    
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"           # Regex match
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    AND = "and"
    OR = "or"


class RunbookVariable(BaseModel):
    """Variable definition in a runbook."""
    
    name: str = Field(..., description="Variable name")
    type: VariableType = VariableType.STRING
    
    # Value
    default: Any = None
    value: Any = None
    
    # Constraints
    required: bool = False
    description: str = ""
    validation_pattern: str | None = None
    allowed_values: list[Any] | None = None
    
    # Secret handling
    from_secret: str | None = None
    from_env: str | None = None
    
    def resolve(self, context: dict[str, Any] | None = None) -> Any:
        """Resolve variable value."""
        context = context or {}
        
        # Check if provided in context
        if self.name in context:
            return context[self.name]
        
        # Check environment
        if self.from_env:
            import os
            env_val = os.environ.get(self.from_env)
            if env_val is not None:
                return env_val
        
        # Use value or default
        if self.value is not None:
            return self.value
        
        return self.default


class Condition(BaseModel):
    """Condition for conditional execution."""
    
    left: str = Field(..., description="Left operand (can be variable reference)")
    operator: ConditionOperator
    right: Any = Field(None, description="Right operand")
    
    # For compound conditions
    conditions: list["Condition"] = Field(default_factory=list)
    
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate the condition."""
        from autosre.runbooks.conditions import ConditionEvaluator
        evaluator = ConditionEvaluator()
        return evaluator.evaluate(self, context)


class StepResult(BaseModel):
    """Result of executing a runbook step."""
    
    step_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Output
    output: Any = None
    output_captured: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    
    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Retries
    attempts: int = 0
    
    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED


class RunbookStep(BaseModel):
    """A single step in a runbook."""
    
    id: str = Field(..., description="Unique step ID")
    name: str = Field(..., description="Step name")
    description: str = ""
    type: StepType
    
    # Execution config
    command: str | None = None
    script: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Flow control
    condition: Condition | None = None
    on_failure: str | None = Field(None, description="Step ID to jump to on failure")
    on_success: str | None = Field(None, description="Step ID to jump to on success")
    continue_on_failure: bool = False
    
    # Timing
    timeout_seconds: int = 300
    delay_seconds: int = 0
    
    # Retries
    max_retries: int = 0
    retry_delay_seconds: int = 5
    
    # Output capture
    output_variable: str | None = Field(None, description="Variable to store output")
    expected_output: str | None = None
    
    # Approval
    approvers: list[str] = Field(default_factory=list)
    approval_timeout_minutes: int = 60
    
    # Nested steps (for parallel/conditional)
    steps: list["RunbookStep"] = Field(default_factory=list)
    
    # Manual instructions
    instructions: str | None = None
    verification_steps: list[str] = Field(default_factory=list)
    
    # Tags and metadata
    tags: list[str] = Field(default_factory=list)
    annotations: dict[str, str] = Field(default_factory=dict)


class Runbook(BaseModel):
    """A runbook definition."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Runbook name")
    description: str = ""
    
    # Version
    version: str = "1.0.0"
    
    # Variables
    variables: list[RunbookVariable] = Field(default_factory=list)
    
    # Steps
    steps: list[RunbookStep] = Field(default_factory=list)
    
    # Triggers
    triggers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Conditions that trigger this runbook",
    )
    
    # Safety
    requires_approval: bool = False
    dry_run_by_default: bool = False
    max_concurrent_executions: int = 1
    
    # Targeting
    target_services: list[str] = Field(default_factory=list)
    target_namespaces: list[str] = Field(default_factory=list)
    
    # Metadata
    author: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)
    documentation_url: str | None = None
    
    # Execution settings
    default_timeout_seconds: int = 3600
    
    def get_step(self, step_id: str) -> RunbookStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
            # Check nested steps
            for nested in step.steps:
                if nested.id == step_id:
                    return nested
        return None
    
    def get_variable(self, name: str) -> RunbookVariable | None:
        """Get a variable by name."""
        return next((v for v in self.variables if v.name == name), None)


class RunbookExecution(BaseModel):
    """Execution of a runbook."""
    
    id: UUID = Field(default_factory=uuid4)
    runbook_id: str
    runbook_name: str
    
    # Context
    context: dict[str, Any] = Field(default_factory=dict)
    resolved_variables: dict[str, Any] = Field(default_factory=dict)
    
    # Status
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_step_id: str | None = None
    current_step_index: int = 0
    
    # Results
    step_results: dict[str, StepResult] = Field(default_factory=dict)
    
    # Output
    final_output: Any = None
    error: str | None = None
    
    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Execution options
    dry_run: bool = False
    pause_on_failure: bool = True
    
    # Triggered by
    triggered_by: str = "manual"
    incident_id: str | None = None
    investigation_id: UUID | None = None
    
    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def completed_steps(self) -> int:
        return sum(
            1 for r in self.step_results.values()
            if r.status in [ExecutionStatus.COMPLETED, ExecutionStatus.SKIPPED]
        )
    
    @property
    def failed_steps(self) -> int:
        return sum(
            1 for r in self.step_results.values()
            if r.status == ExecutionStatus.FAILED
        )
    
    @property
    def progress_percent(self) -> float:
        total = len(self.step_results)
        if total == 0:
            return 0
        completed = self.completed_steps
        return (completed / total) * 100
    
    def get_step_result(self, step_id: str) -> StepResult | None:
        """Get result for a specific step."""
        return self.step_results.get(step_id)
    
    def to_summary(self) -> str:
        """Generate execution summary."""
        status_icon = "✅" if self.status == ExecutionStatus.COMPLETED else "❌"
        lines = [
            f"{status_icon} Runbook: {self.runbook_name}",
            f"Status: {self.status.value}",
            f"Steps: {self.completed_steps}/{len(self.step_results)} completed",
        ]
        
        if self.failed_steps > 0:
            lines.append(f"Failed: {self.failed_steps} steps")
        
        if self.duration_seconds:
            lines.append(f"Duration: {self.duration_seconds:.1f}s")
        
        if self.error:
            lines.append(f"Error: {self.error}")
        
        return "\n".join(lines)
