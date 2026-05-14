"""Alert API schemas for AutoSRE V2.

Defines request/response models for alert management endpoints.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert lifecycle status."""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class AlertBase(BaseModel):
    """Base alert fields for creation and updates."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "HighCPUUsage",
                "severity": "high",
                "source": "prometheus",
                "description": "CPU usage above 90% for 5 minutes",
                "service": "api-gateway",
                "namespace": "production",
                "labels": {"team": "platform", "tier": "1"},
                "annotations": {"runbook_url": "https://wiki.example.com/runbooks/cpu"},
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Alert name/rule name",
        json_schema_extra={"example": "HighCPUUsage"},
    )
    severity: AlertSeverity = Field(
        default=AlertSeverity.MEDIUM,
        description="Alert severity level",
        json_schema_extra={"example": "high"},
    )
    source: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Alert source system (e.g., prometheus, datadog)",
        json_schema_extra={"example": "prometheus"},
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="Human-readable alert description",
        json_schema_extra={"example": "CPU usage above 90% for 5 minutes"},
    )
    service: str | None = Field(
        default=None,
        max_length=200,
        description="Affected service name",
        json_schema_extra={"example": "api-gateway"},
    )
    namespace: str | None = Field(
        default=None,
        max_length=100,
        description="Kubernetes namespace or environment",
        json_schema_extra={"example": "production"},
    )
    cluster: str | None = Field(
        default=None,
        max_length=100,
        description="Cluster identifier",
        json_schema_extra={"example": "prod-us-east-1"},
    )
    instance: str | None = Field(
        default=None,
        max_length=200,
        description="Specific instance or pod identifier",
        json_schema_extra={"example": "api-gateway-7d8f9c6b5d-abc12"},
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Alert labels for categorization and routing",
        json_schema_extra={"example": {"team": "platform", "tier": "1"}},
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata and links",
        json_schema_extra={"example": {"runbook_url": "https://wiki.example.com/runbooks/cpu"}},
    )


class AlertCreate(AlertBase):
    """Schema for creating a new alert."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "HighCPUUsage",
                "severity": "high",
                "source": "prometheus",
                "description": "CPU usage above 90% for 5 minutes",
                "service": "api-gateway",
                "namespace": "production",
                "labels": {"team": "platform"},
                "annotations": {},
                "fingerprint": "abc123def456",
                "started_at": "2024-01-15T10:30:00Z",
            }
        },
    )

    fingerprint: str | None = Field(
        default=None,
        max_length=64,
        description="Unique fingerprint for deduplication (auto-generated if not provided)",
        json_schema_extra={"example": "abc123def456"},
    )
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="Alert start time (defaults to now)",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"},
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        alias="rawData",
        description="Original alert payload from source system",
    )


class AlertUpdate(BaseModel):
    """Schema for updating an existing alert."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    severity: AlertSeverity | None = Field(
        default=None,
        description="Updated severity level",
    )
    status: AlertStatus | None = Field(
        default=None,
        description="Updated status",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Updated description",
    )
    labels: dict[str, str] | None = Field(
        default=None,
        description="Updated labels (replaces existing)",
    )
    annotations: dict[str, str] | None = Field(
        default=None,
        description="Updated annotations (replaces existing)",
    )


class AlertResponse(AlertBase):
    """Full alert response including all fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "alert_abc123def456",
                "name": "HighCPUUsage",
                "severity": "high",
                "status": "firing",
                "source": "prometheus",
                "description": "CPU usage above 90% for 5 minutes",
                "service": "api-gateway",
                "namespace": "production",
                "cluster": "prod-us-east-1",
                "instance": "api-gateway-7d8f9c6b5d-abc12",
                "labels": {"team": "platform", "tier": "1"},
                "annotations": {"runbook_url": "https://wiki.example.com/runbooks/cpu"},
                "fingerprint": "abc123def456",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "started_at": "2024-01-15T10:30:00Z",
                "ended_at": None,
                "investigation_id": "inv_xyz789",
                "acknowledged_by": None,
                "acknowledged_at": None,
                "duration_seconds": 300.5,
            }
        },
    )

    id: str = Field(
        ...,
        description="Unique alert identifier",
        json_schema_extra={"example": "alert_abc123def456"},
    )
    status: AlertStatus = Field(
        ...,
        description="Current alert status",
        json_schema_extra={"example": "firing"},
    )
    fingerprint: str = Field(
        ...,
        description="Alert fingerprint for deduplication",
        json_schema_extra={"example": "abc123def456"},
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="When the alert was first received",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"},
    )
    updated_at: datetime = Field(
        ...,
        alias="updatedAt",
        description="When the alert was last updated",
        json_schema_extra={"example": "2024-01-15T10:35:00Z"},
    )
    started_at: datetime = Field(
        ...,
        alias="startedAt",
        description="When the alert condition started",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"},
    )
    ended_at: datetime | None = Field(
        default=None,
        alias="endedAt",
        description="When the alert was resolved (null if still active)",
    )
    investigation_id: str | None = Field(
        default=None,
        alias="investigationId",
        description="Associated investigation ID if any",
        json_schema_extra={"example": "inv_xyz789"},
    )
    acknowledged_by: str | None = Field(
        default=None,
        alias="acknowledgedBy",
        description="User who acknowledged the alert",
    )
    acknowledged_at: datetime | None = Field(
        default=None,
        alias="acknowledgedAt",
        description="When the alert was acknowledged",
    )
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Alert duration in seconds",
        json_schema_extra={"example": 300.5},
    )

    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status in (AlertStatus.FIRING, AlertStatus.INVESTIGATING)


class AlertSummary(BaseModel):
    """Condensed alert view for lists and summaries."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "alert_abc123",
                "name": "HighCPUUsage",
                "severity": "high",
                "status": "firing",
                "service": "api-gateway",
                "started_at": "2024-01-15T10:30:00Z",
                "duration_seconds": 300.5,
            }
        },
    )

    id: str = Field(..., description="Alert ID")
    name: str = Field(..., description="Alert name")
    severity: AlertSeverity = Field(..., description="Severity level")
    status: AlertStatus = Field(..., description="Current status")
    service: str | None = Field(default=None, description="Affected service")
    started_at: datetime = Field(..., alias="startedAt", description="Start time")
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Duration in seconds",
    )


class AlertList(BaseModel):
    """Paginated list of alerts."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "alert_abc123",
                        "name": "HighCPUUsage",
                        "severity": "high",
                        "status": "firing",
                        "source": "prometheus",
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                ],
                "total": 42,
                "page": 1,
                "per_page": 20,
                "pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        },
    )

    items: list[AlertResponse] = Field(..., description="List of alerts")
    total: int = Field(..., ge=0, description="Total number of alerts")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, alias="perPage", description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., alias="hasNext", description="Has next page")
    has_prev: bool = Field(..., alias="hasPrev", description="Has previous page")

    @classmethod
    def create(
        cls,
        items: list[AlertResponse],
        total: int,
        page: int,
        per_page: int,
    ) -> AlertList:
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


class AlertAcknowledge(BaseModel):
    """Request to acknowledge an alert."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "acknowledged_by": "oncall-engineer",
                "comment": "Looking into this now",
            }
        },
    )

    acknowledged_by: str = Field(
        ...,
        alias="acknowledgedBy",
        min_length=1,
        max_length=100,
        description="User or system acknowledging the alert",
        json_schema_extra={"example": "oncall-engineer"},
    )
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional acknowledgement comment",
        json_schema_extra={"example": "Looking into this now"},
    )


class AlertResolve(BaseModel):
    """Request to resolve an alert."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "resolved_by": "oncall-engineer",
                "resolution": "Scaled up replicas to handle increased load",
            }
        },
    )

    resolved_by: str | None = Field(
        default=None,
        alias="resolvedBy",
        max_length=100,
        description="User or system resolving the alert",
        json_schema_extra={"example": "oncall-engineer"},
    )
    resolution: str | None = Field(
        default=None,
        max_length=2000,
        description="Resolution summary",
        json_schema_extra={"example": "Scaled up replicas to handle increased load"},
    )


class AlertFilter(BaseModel):
    """Alert filtering parameters for list endpoints."""

    model_config = ConfigDict(
        populate_by_name=True,
    )

    severity: list[AlertSeverity] | None = Field(
        default=None,
        description="Filter by severity levels",
    )
    status: list[AlertStatus] | None = Field(
        default=None,
        description="Filter by status values",
    )
    source: list[str] | None = Field(
        default=None,
        description="Filter by alert sources",
    )
    service: list[str] | None = Field(
        default=None,
        description="Filter by affected services",
    )
    namespace: str | None = Field(
        default=None,
        description="Filter by namespace",
    )
    cluster: str | None = Field(
        default=None,
        description="Filter by cluster",
    )
    labels: dict[str, str] | None = Field(
        default=None,
        description="Filter by label key-value pairs",
    )
    started_after: datetime | None = Field(
        default=None,
        alias="startedAfter",
        description="Filter alerts starting after this time",
    )
    started_before: datetime | None = Field(
        default=None,
        alias="startedBefore",
        description="Filter alerts starting before this time",
    )
    search: str | None = Field(
        default=None,
        max_length=200,
        description="Full-text search in alert name and description",
    )
    has_investigation: bool | None = Field(
        default=None,
        alias="hasInvestigation",
        description="Filter by whether alert has an associated investigation",
    )

    @field_validator("severity", "status", mode="before")
    @classmethod
    def split_comma_separated(cls, v: Any) -> list | None:
        """Allow comma-separated strings for list fields."""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class AlertStats(BaseModel):
    """Alert statistics summary."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "total": 150,
                "by_severity": {
                    "critical": 5,
                    "high": 20,
                    "medium": 75,
                    "low": 40,
                    "info": 10,
                },
                "by_status": {
                    "firing": 25,
                    "acknowledged": 10,
                    "resolved": 115,
                },
                "active_count": 35,
                "mean_time_to_acknowledge_seconds": 120.5,
                "mean_time_to_resolve_seconds": 3600.0,
            }
        },
    )

    total: int = Field(..., description="Total number of alerts")
    by_severity: dict[str, int] = Field(
        ...,
        alias="bySeverity",
        description="Count by severity level",
    )
    by_status: dict[str, int] = Field(
        ...,
        alias="byStatus",
        description="Count by status",
    )
    active_count: int = Field(
        ...,
        alias="activeCount",
        description="Number of currently active alerts",
    )
    mean_time_to_acknowledge_seconds: float | None = Field(
        default=None,
        alias="meanTimeToAcknowledgeSeconds",
        description="Average time to acknowledge in seconds",
    )
    mean_time_to_resolve_seconds: float | None = Field(
        default=None,
        alias="meanTimeToResolveSeconds",
        description="Average time to resolve in seconds",
    )
