"""Response Schemas.

Pydantic models for API response serialization.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class AlertList(BaseModel):
    """Alert summary for list views."""

    id: UUID
    alertname: str
    severity: str
    status: str
    summary: str
    source: str
    labels: dict[str, str]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AlertDetail(AlertList):
    """Full alert details including related data."""

    description: Optional[str] = None
    annotations: dict[str, str] = Field(default_factory=dict)
    external_url: Optional[str] = None
    assigned_to: Optional[str] = None
    investigation_id: Optional[UUID] = None
    investigation_status: Optional[str] = None
    related_alerts: list[UUID] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationSummary(BaseModel):
    """Investigation summary for quick reference."""

    id: UUID
    alert_id: UUID
    status: str = Field(
        ...,
        description="pending|running|completed|failed|cancelled",
    )
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class InvestigationList(InvestigationSummary):
    """Investigation list item with additional metadata."""

    alert_name: str
    alert_severity: str
    findings_count: int = 0
    actions_taken: int = 0


class InvestigationStep(BaseModel):
    """Single step in an investigation."""

    id: UUID
    investigation_id: UUID
    step_number: int
    step_type: str = Field(
        ...,
        description="gather_context|analyze|query|action|decision",
    )
    description: str
    status: str = Field(..., description="pending|running|completed|failed|skipped")
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class InvestigationDetail(InvestigationSummary):
    """Full investigation details."""

    alert: AlertList
    priority: str
    auto_remediate: bool
    context: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    root_cause: Optional[str] = None
    recommendations: list[str] = Field(default_factory=list)
    actions_taken: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[InvestigationStep] = Field(default_factory=list)
    duration_ms: Optional[int] = None
    tokens_used: Optional[int] = None


class ChatSession(BaseModel):
    """Chat session details."""

    id: UUID
    user_id: str
    investigation_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    title: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message in a session."""

    id: UUID
    session_id: UUID
    role: str = Field(..., description="user|assistant|system")
    content: str
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    tokens_used: Optional[int] = None


class ChatResponse(BaseModel):
    """Response to a chat message."""

    message: ChatMessage
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referenced data sources",
    )
    suggested_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested follow-up actions",
    )
    related_alerts: list[UUID] = Field(default_factory=list)
    related_runbooks: list[UUID] = Field(default_factory=list)


class RunbookList(BaseModel):
    """Runbook summary for list views."""

    id: UUID
    name: str
    description: Optional[str] = None
    category: str
    tags: list[str] = Field(default_factory=list)
    enabled: bool
    created_at: datetime
    updated_at: datetime
    execution_count: int = 0
    last_executed_at: Optional[datetime] = None


class RunbookDetail(RunbookList):
    """Full runbook details including steps and parameters."""

    trigger_conditions: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str
    updated_by: str
    version: int = 1


class RunbookExecution(BaseModel):
    """Runbook execution details."""

    id: UUID
    runbook_id: UUID
    runbook_name: str
    status: str = Field(
        ...,
        description="pending|running|completed|failed|cancelled",
    )
    dry_run: bool
    parameters: dict[str, Any] = Field(default_factory=dict)
    alert_id: Optional[UUID] = None
    investigation_id: Optional[UUID] = None
    executed_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    steps_completed: int = 0
    steps_total: int = 0
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class InvestigationTimeline(BaseModel):
    """Complete timeline of an investigation."""

    investigation_id: UUID
    events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological list of timeline events",
    )
    total_duration_ms: Optional[int] = None
    phases: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Investigation phases (gathering, analysis, action)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
                "events": [
                    {
                        "timestamp": "2024-01-15T10:30:00Z",
                        "type": "investigation_started",
                        "description": "Investigation triggered by alert",
                    },
                    {
                        "timestamp": "2024-01-15T10:30:05Z",
                        "type": "context_gathered",
                        "description": "Collected metrics from Prometheus",
                        "data": {"metrics_count": 15},
                    },
                ],
                "total_duration_ms": 45000,
                "phases": [
                    {"name": "gathering", "duration_ms": 5000},
                    {"name": "analysis", "duration_ms": 30000},
                    {"name": "action", "duration_ms": 10000},
                ],
            }
        }
    }


class ChatMessageResponse(BaseModel):
    """Response to a single chat message."""

    id: UUID
    role: str = Field(default="assistant", description="user|assistant|system")
    content: str
    created_at: datetime
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referenced data sources",
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tools used to generate response",
    )
    suggested_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested follow-up actions",
    )
    related_alerts: list[UUID] = Field(default_factory=list)
    related_runbooks: list[UUID] = Field(default_factory=list)
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None


class ChatHistoryMessage(BaseModel):
    """Chat message in history."""

    id: UUID
    role: str = Field(..., description="user|assistant|system")
    content: str
    created_at: datetime
    tokens_used: Optional[int] = None


class ChatHistoryResponse(BaseModel):
    """Chat history with pagination."""

    messages: list[ChatHistoryMessage] = Field(default_factory=list)
    has_more: bool = Field(default=False)
    next_cursor: Optional[str] = Field(
        None,
        description="Cursor for fetching next page of messages",
    )
    session_id: Optional[UUID] = None
    investigation_id: Optional[UUID] = None
