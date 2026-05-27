"""Investigation request/response models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class InvestigationState(str, Enum):
    """Investigation lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AlertData(BaseModel):
    """Incoming alert data from monitoring systems."""
    source: str = Field(..., description="Alert source (e.g., prometheus, datadog, pagerduty)")
    alert_id: str = Field(..., description="External alert identifier")
    title: str = Field(..., description="Alert title/summary")
    description: str | None = Field(default=None, description="Detailed alert description")
    severity: Severity = Field(..., description="Alert severity level")
    service: str = Field(..., description="Affected service name")
    team: str | None = Field(default=None, description="Responsible team")
    labels: dict[str, str] = Field(default_factory=dict, description="Alert labels/tags")
    annotations: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    started_at: datetime = Field(..., description="When the alert fired")
    raw_payload: dict[str, Any] | None = Field(
        default=None,
        description="Original alert payload for reference"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "prometheus",
                "alert_id": "alert-123",
                "title": "High Error Rate on api-gateway",
                "description": "Error rate exceeded 5% threshold for 5 minutes",
                "severity": "high",
                "service": "api-gateway",
                "team": "platform",
                "labels": {"env": "production", "region": "us-west-2"},
                "annotations": {"runbook": "https://wiki/runbooks/api-errors"},
                "started_at": "2024-01-15T10:25:00Z"
            }
        }
    }


class InvestigationCreate(BaseModel):
    """Request to start a new investigation."""
    alert: AlertData = Field(..., description="Alert data triggering the investigation")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context (recent changes, related incidents)"
    )
    auto_remediate: bool = Field(
        default=False,
        description="Allow automatic remediation if safe"
    )
    priority_override: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Override calculated priority (1=highest)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "alert": {
                    "source": "prometheus",
                    "alert_id": "alert-123",
                    "title": "High Error Rate",
                    "severity": "high",
                    "service": "api-gateway",
                    "started_at": "2024-01-15T10:25:00Z"
                },
                "auto_remediate": False
            }
        }
    }


class InvestigationStep(BaseModel):
    """A single step in the investigation process."""
    step_id: str = Field(..., description="Unique step identifier")
    action: str = Field(..., description="Action taken (e.g., query_metrics, check_logs)")
    description: str = Field(..., description="Human-readable description")
    started_at: datetime = Field(..., description="Step start time")
    completed_at: datetime | None = Field(default=None, description="Step completion time")
    result: dict[str, Any] | None = Field(default=None, description="Step results")
    error: str | None = Field(default=None, description="Error message if failed")


class InvestigationResponse(BaseModel):
    """Investigation details response."""
    investigation_id: str = Field(..., description="Unique investigation identifier")
    state: InvestigationState = Field(..., description="Current investigation state")
    alert: AlertData = Field(..., description="Original alert data")
    priority: int = Field(..., ge=1, le=10, description="Investigation priority")
    created_at: datetime = Field(..., description="Investigation creation time")
    updated_at: datetime = Field(..., description="Last update time")
    started_at: datetime | None = Field(default=None, description="When investigation began")
    completed_at: datetime | None = Field(default=None, description="When investigation ended")
    steps: list[InvestigationStep] = Field(
        default_factory=list,
        description="Investigation steps taken"
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Key findings discovered"
    )
    root_cause: str | None = Field(default=None, description="Identified root cause")
    remediation: str | None = Field(default=None, description="Suggested/applied remediation")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in diagnosis"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "investigation_id": "inv-abc123",
                "state": "running",
                "alert": {
                    "source": "prometheus",
                    "alert_id": "alert-123",
                    "title": "High Error Rate",
                    "severity": "high",
                    "service": "api-gateway",
                    "started_at": "2024-01-15T10:25:00Z"
                },
                "priority": 2,
                "created_at": "2024-01-15T10:26:00Z",
                "updated_at": "2024-01-15T10:28:00Z",
                "started_at": "2024-01-15T10:26:05Z",
                "steps": [
                    {
                        "step_id": "step-1",
                        "action": "query_metrics",
                        "description": "Fetching error rate metrics",
                        "started_at": "2024-01-15T10:26:05Z",
                        "completed_at": "2024-01-15T10:26:08Z",
                        "result": {"error_rate": 7.2}
                    }
                ],
                "findings": ["Error rate spike correlates with deployment at 10:20"],
                "confidence": 0.85
            }
        }
    }


class InvestigationStatus(BaseModel):
    """Lightweight status response."""
    investigation_id: str
    state: InvestigationState
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress percentage")
    current_step: str | None = Field(default=None, description="Current action being performed")
    eta_seconds: int | None = Field(default=None, description="Estimated time remaining")


class InvestigationFeedback(BaseModel):
    """Human feedback on investigation results."""
    rating: int = Field(..., ge=1, le=5, description="Quality rating (1-5)")
    accurate_diagnosis: bool = Field(..., description="Was the diagnosis correct?")
    helpful_remediation: bool | None = Field(
        default=None,
        description="Was the remediation suggestion helpful?"
    )
    comments: str | None = Field(default=None, max_length=2000, description="Free-form feedback")
    actual_root_cause: str | None = Field(
        default=None,
        max_length=1000,
        description="Correct root cause if different"
    )
    tags: list[str] = Field(default_factory=list, description="Feedback tags")

    model_config = {
        "json_schema_extra": {
            "example": {
                "rating": 4,
                "accurate_diagnosis": True,
                "helpful_remediation": True,
                "comments": "Good investigation, could have checked deployment logs sooner",
                "tags": ["deployment-related", "quick-resolution"]
            }
        }
    }


class EventType(str, Enum):
    """Investigation event types for SSE streaming."""
    STATE_CHANGE = "state_change"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    FINDING = "finding"
    HYPOTHESIS = "hypothesis"
    ERROR = "error"
    COMPLETE = "complete"


class InvestigationEvent(BaseModel):
    """SSE event for investigation updates."""
    event_type: EventType = Field(..., description="Type of event")
    investigation_id: str = Field(..., description="Investigation this event belongs to")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(..., description="Event-specific data")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "finding",
                "investigation_id": "inv-abc123",
                "timestamp": "2024-01-15T10:28:00Z",
                "data": {
                    "finding": "Memory usage increased 40% after deployment",
                    "confidence": 0.9,
                    "source": "prometheus_metrics"
                }
            }
        }
    }
