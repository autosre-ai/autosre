"""Runbook API schemas for AutoSRE V2.

Defines request/response models for runbook management,
execution, and history tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunbookStatus(str, Enum):
    """Runbook lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ExecutionStatus(str, Enum):
    """Runbook execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """Risk level for runbooks and steps."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Runbook Step Schemas
# =============================================================================


class RunbookStepBase(BaseModel):
    """Base runbook step fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Check current CPU usage",
                "description": "Query Prometheus for current CPU metrics",
                "tool": "prometheus",
                "command": None,
                "script": None,
                "parameters": {"query": "rate(process_cpu_seconds_total[5m])"},
                "timeout_seconds": 300,
                "continue_on_failure": False,
                "requires_approval": False,
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Step name",
        json_schema_extra={"example": "Check current CPU usage"},
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Step description",
        json_schema_extra={"example": "Query Prometheus for current CPU metrics"},
    )
    tool: str | None = Field(
        default=None,
        max_length=100,
        description="Tool or plugin to use",
        json_schema_extra={"example": "prometheus"},
    )
    command: str | None = Field(
        default=None,
        max_length=5000,
        description="Shell command to execute",
        json_schema_extra={"example": "kubectl get pods -n production"},
    )
    script: str | None = Field(
        default=None,
        max_length=50000,
        description="Script content to execute",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Step parameters",
        json_schema_extra={"example": {"query": "rate(process_cpu_seconds_total[5m])"}},
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        alias="timeoutSeconds",
        description="Step timeout in seconds",
        json_schema_extra={"example": 300},
    )
    continue_on_failure: bool = Field(
        default=False,
        alias="continueOnFailure",
        description="Whether to continue execution if this step fails",
    )
    requires_approval: bool = Field(
        default=False,
        alias="requiresApproval",
        description="Whether this step requires human approval",
    )


class RunbookStepCreate(RunbookStepBase):
    """Schema for creating a runbook step."""
    pass


class RunbookStepResponse(RunbookStepBase):
    """Full runbook step response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "step_abc123",
                "name": "Check current CPU usage",
                "description": "Query Prometheus for current CPU metrics",
                "tool": "prometheus",
                "parameters": {"query": "rate(process_cpu_seconds_total[5m])"},
                "timeout_seconds": 300,
                "continue_on_failure": False,
                "requires_approval": False,
                "order": 1,
            }
        },
    )

    id: str = Field(
        ...,
        description="Step ID",
        json_schema_extra={"example": "step_abc123"},
    )
    order: int = Field(
        default=0,
        ge=0,
        description="Step execution order (0-indexed)",
        json_schema_extra={"example": 1},
    )


# =============================================================================
# Runbook Schemas
# =============================================================================


class RunbookBase(BaseModel):
    """Base runbook fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "High CPU Investigation",
                "description": "Investigate and mitigate high CPU usage",
                "tags": ["cpu", "performance", "investigation"],
                "services": ["api-gateway", "user-service"],
                "alert_names": ["HighCPUUsage", "CPUThrottling"],
                "requires_approval": True,
                "risk_level": "low",
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Runbook name",
        json_schema_extra={"example": "High CPU Investigation"},
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="Runbook description",
        json_schema_extra={"example": "Investigate and mitigate high CPU usage"},
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        json_schema_extra={"example": ["cpu", "performance"]},
    )
    services: list[str] = Field(
        default_factory=list,
        description="Services this runbook applies to (* for all)",
        json_schema_extra={"example": ["api-gateway", "user-service"]},
    )
    alert_names: list[str] = Field(
        default_factory=list,
        alias="alertNames",
        description="Alert names this runbook can handle",
        json_schema_extra={"example": ["HighCPUUsage", "CPUThrottling"]},
    )
    requires_approval: bool = Field(
        default=True,
        alias="requiresApproval",
        description="Whether execution requires human approval",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        alias="riskLevel",
        description="Overall risk level",
        json_schema_extra={"example": "low"},
    )


class RunbookParameterDefinition(BaseModel):
    """Definition of a runbook parameter."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "string",
                "required": True,
                "default": None,
                "description": "Target service name",
                "enum": None,
            }
        },
    )

    type: str = Field(
        default="string",
        description="Parameter type (string, number, boolean, array)",
        json_schema_extra={"example": "string"},
    )
    required: bool = Field(
        default=False,
        description="Whether the parameter is required",
    )
    default: Any | None = Field(
        default=None,
        description="Default value",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Parameter description",
    )
    enum: list[Any] | None = Field(
        default=None,
        description="Allowed values (for enums)",
    )


class RunbookCreate(RunbookBase):
    """Schema for creating a new runbook."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "High CPU Investigation",
                "description": "Investigate and mitigate high CPU usage",
                "tags": ["cpu", "performance"],
                "services": ["api-gateway"],
                "alert_names": ["HighCPUUsage"],
                "steps": [
                    {
                        "name": "Check CPU usage",
                        "description": "Query current CPU metrics",
                        "tool": "prometheus",
                        "parameters": {"query": "cpu_usage"},
                    }
                ],
                "parameters": {
                    "service": {"type": "string", "required": True},
                },
                "requires_approval": True,
                "risk_level": "low",
            }
        },
    )

    steps: list[RunbookStepCreate] = Field(
        default_factory=list,
        description="List of steps to execute",
    )
    parameters: dict[str, RunbookParameterDefinition] = Field(
        default_factory=dict,
        description="Parameter definitions",
    )
    author: str = Field(
        default="unknown",
        max_length=100,
        description="Runbook author",
        json_schema_extra={"example": "sre-team"},
    )


class RunbookUpdate(BaseModel):
    """Schema for updating a runbook."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated name",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Updated description",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Updated tags",
    )
    services: list[str] | None = Field(
        default=None,
        description="Updated services",
    )
    alert_names: list[str] | None = Field(
        default=None,
        alias="alertNames",
        description="Updated alert names",
    )
    steps: list[RunbookStepCreate] | None = Field(
        default=None,
        description="Updated steps",
    )
    parameters: dict[str, RunbookParameterDefinition] | None = Field(
        default=None,
        description="Updated parameters",
    )
    status: RunbookStatus | None = Field(
        default=None,
        description="Updated status",
    )
    requires_approval: bool | None = Field(
        default=None,
        alias="requiresApproval",
        description="Updated approval requirement",
    )
    risk_level: RiskLevel | None = Field(
        default=None,
        alias="riskLevel",
        description="Updated risk level",
    )


class RunbookResponse(RunbookBase):
    """Full runbook response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "rb_abc123",
                "name": "High CPU Investigation",
                "description": "Investigate and mitigate high CPU usage",
                "version": "1.2.0",
                "status": "active",
                "tags": ["cpu", "performance"],
                "services": ["api-gateway"],
                "alert_names": ["HighCPUUsage"],
                "steps": [],
                "parameters": {},
                "author": "sre-team",
                "requires_approval": True,
                "risk_level": "low",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "execution_count": 42,
                "success_rate": 0.95,
            }
        },
    )

    id: str = Field(
        ...,
        description="Runbook ID",
        json_schema_extra={"example": "rb_abc123"},
    )
    version: str = Field(
        default="1.0.0",
        description="Runbook version",
        json_schema_extra={"example": "1.2.0"},
    )
    status: RunbookStatus = Field(
        default=RunbookStatus.DRAFT,
        description="Runbook status",
        json_schema_extra={"example": "active"},
    )
    steps: list[RunbookStepResponse] = Field(
        default_factory=list,
        description="Runbook steps",
    )
    parameters: dict[str, RunbookParameterDefinition] = Field(
        default_factory=dict,
        description="Parameter definitions",
    )
    author: str = Field(
        default="unknown",
        description="Runbook author",
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        alias="updatedAt",
        description="Last update timestamp",
    )
    execution_count: int = Field(
        default=0,
        alias="executionCount",
        ge=0,
        description="Number of times executed",
    )
    success_rate: float | None = Field(
        default=None,
        alias="successRate",
        ge=0,
        le=1,
        description="Historical success rate (0-1)",
    )


class RunbookSummary(BaseModel):
    """Condensed runbook view for lists."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    id: str = Field(..., description="Runbook ID")
    name: str = Field(..., description="Runbook name")
    description: str = Field(default="", description="Description")
    status: RunbookStatus = Field(..., description="Status")
    tags: list[str] = Field(default_factory=list, description="Tags")
    risk_level: RiskLevel = Field(..., alias="riskLevel", description="Risk level")
    step_count: int = Field(default=0, alias="stepCount", description="Number of steps")
    updated_at: datetime = Field(..., alias="updatedAt", description="Last update")


class RunbookList(BaseModel):
    """Paginated list of runbooks."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "items": [],
                "total": 25,
                "page": 1,
                "per_page": 20,
                "pages": 2,
                "has_next": True,
                "has_prev": False,
            }
        },
    )

    items: list[RunbookResponse] = Field(..., description="List of runbooks")
    total: int = Field(..., ge=0, description="Total number of runbooks")
    page: int = Field(..., ge=1, description="Current page")
    per_page: int = Field(..., ge=1, alias="perPage", description="Items per page")
    pages: int = Field(..., ge=0, description="Total pages")
    has_next: bool = Field(..., alias="hasNext", description="Has next page")
    has_prev: bool = Field(..., alias="hasPrev", description="Has previous page")

    @classmethod
    def create(
        cls,
        items: list[RunbookResponse],
        total: int,
        page: int,
        per_page: int,
    ) -> RunbookList:
        """Create paginated response with computed fields."""
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class RunbookSearchParams(BaseModel):
    """Runbook search/filter parameters."""

    model_config = ConfigDict(populate_by_name=True)

    status: RunbookStatus | None = Field(
        default=None,
        description="Filter by status",
    )
    service: str | None = Field(
        default=None,
        description="Filter by applicable service",
    )
    tag: str | None = Field(
        default=None,
        description="Filter by tag",
    )
    alert_name: str | None = Field(
        default=None,
        alias="alertName",
        description="Filter by alert name match",
    )
    risk_level: RiskLevel | None = Field(
        default=None,
        alias="riskLevel",
        description="Filter by risk level",
    )
    search: str | None = Field(
        default=None,
        max_length=200,
        description="Full-text search in name and description",
    )


# =============================================================================
# Execution Schemas
# =============================================================================


class RunbookExecutionRequest(BaseModel):
    """Request to execute a runbook."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "parameters": {"service": "api-gateway"},
                "triggered_by": "oncall-engineer",
                "alert_id": "alert_abc123",
                "investigation_id": "inv_xyz789",
                "dry_run": False,
            }
        },
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values for execution",
        json_schema_extra={"example": {"service": "api-gateway"}},
    )
    triggered_by: str = Field(
        default="api",
        alias="triggeredBy",
        max_length=100,
        description="Who/what triggered the execution",
        json_schema_extra={"example": "oncall-engineer"},
    )
    alert_id: str | None = Field(
        default=None,
        alias="alertId",
        description="Associated alert ID",
    )
    investigation_id: str | None = Field(
        default=None,
        alias="investigationId",
        description="Associated investigation ID",
    )
    dry_run: bool = Field(
        default=False,
        alias="dryRun",
        description="If true, validate but don't execute",
    )


class StepExecutionResponse(BaseModel):
    """Execution result of a single step."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "step_id": "step_abc123",
                "step_name": "Check CPU usage",
                "order": 1,
                "status": "completed",
                "started_at": "2024-01-15T10:40:00Z",
                "completed_at": "2024-01-15T10:40:05Z",
                "duration_seconds": 5.2,
                "output": "CPU usage: 95%",
                "error": None,
            }
        },
    )

    step_id: str = Field(
        ...,
        alias="stepId",
        description="Step ID",
    )
    step_name: str = Field(
        ...,
        alias="stepName",
        description="Step name",
    )
    order: int = Field(
        default=0,
        ge=0,
        description="Step order",
    )
    status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="Step execution status",
    )
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="When step execution started",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="When step execution completed",
    )
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Step duration in seconds",
    )
    output: str | None = Field(
        default=None,
        description="Step output",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )


class RunbookExecutionResponse(BaseModel):
    """Full runbook execution response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "exec_abc123",
                "runbook_id": "rb_xyz789",
                "runbook_name": "High CPU Investigation",
                "runbook_version": "1.2.0",
                "status": "completed",
                "current_step": 3,
                "step_results": [],
                "parameters": {"service": "api-gateway"},
                "triggered_by": "oncall-engineer",
                "alert_id": "alert_abc123",
                "investigation_id": "inv_xyz789",
                "started_at": "2024-01-15T10:40:00Z",
                "completed_at": "2024-01-15T10:45:00Z",
                "duration_seconds": 300.0,
                "output": "Investigation complete. Root cause identified.",
                "error": None,
            }
        },
    )

    id: str = Field(..., description="Execution ID")
    runbook_id: str = Field(..., alias="runbookId", description="Runbook ID")
    runbook_name: str = Field(..., alias="runbookName", description="Runbook name")
    runbook_version: str = Field(..., alias="runbookVersion", description="Runbook version")
    status: ExecutionStatus = Field(..., description="Execution status")
    current_step: int = Field(
        default=0,
        alias="currentStep",
        ge=0,
        description="Current step index (0-indexed)",
    )
    step_results: list[StepExecutionResponse] = Field(
        default_factory=list,
        alias="stepResults",
        description="Results for each step",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution parameters",
    )
    triggered_by: str = Field(
        default="api",
        alias="triggeredBy",
        description="Who/what triggered execution",
    )
    alert_id: str | None = Field(
        default=None,
        alias="alertId",
        description="Associated alert ID",
    )
    investigation_id: str | None = Field(
        default=None,
        alias="investigationId",
        description="Associated investigation ID",
    )
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="Execution start time",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="Execution completion time",
    )
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Total execution duration",
    )
    output: str | None = Field(
        default=None,
        description="Execution output/summary",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )


class RunbookExecutionSummary(BaseModel):
    """Condensed execution view for lists."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    id: str = Field(..., description="Execution ID")
    runbook_id: str = Field(..., alias="runbookId", description="Runbook ID")
    runbook_name: str = Field(..., alias="runbookName", description="Runbook name")
    status: ExecutionStatus = Field(..., description="Status")
    triggered_by: str = Field(..., alias="triggeredBy", description="Triggered by")
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="Start time",
    )
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Duration",
    )


class RunbookExecutionList(BaseModel):
    """Paginated list of executions."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "per_page": 20,
            }
        },
    )

    items: list[RunbookExecutionResponse] = Field(..., description="List of executions")
    total: int = Field(..., ge=0, description="Total number of executions")
    page: int = Field(default=1, ge=1, description="Current page")
    per_page: int = Field(default=20, ge=1, alias="perPage", description="Items per page")

    @classmethod
    def create(
        cls,
        items: list[RunbookExecutionResponse],
        total: int,
        page: int = 1,
        per_page: int = 20,
    ) -> RunbookExecutionList:
        """Create list response."""
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )


class CancelExecutionRequest(BaseModel):
    """Request to cancel an execution."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "cancelled_by": "oncall-engineer",
                "reason": "False alarm, no longer needed",
            }
        },
    )

    cancelled_by: str = Field(
        ...,
        alias="cancelledBy",
        min_length=1,
        max_length=100,
        description="User cancelling the execution",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason for cancellation",
    )


class ApproveStepRequest(BaseModel):
    """Request to approve a step requiring approval."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "approved_by": "oncall-engineer",
                "comment": "Approved - safe to proceed",
            }
        },
    )

    approved_by: str = Field(
        ...,
        alias="approvedBy",
        min_length=1,
        max_length=100,
        description="User approving the step",
    )
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description="Approval comment",
    )
