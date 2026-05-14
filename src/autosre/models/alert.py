"""Alert models for incident management."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now


class AlertSeverity(str, Enum):
    """Severity level of an alert."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Current status of an alert."""
    FIRING = "firing"
    PENDING = "pending"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


class Alert(BaseModel):
    """Represents an alert from a monitoring system."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Alert name/title")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(default=AlertStatus.FIRING, description="Current alert status")
    source: str = Field(..., min_length=1, description="Source system (e.g., prometheus, datadog)")
    labels: dict[str, str] = Field(default_factory=dict, description="Alert labels for filtering/grouping")
    annotations: dict[str, str] = Field(default_factory=dict, description="Additional context and descriptions")
    started_at: datetime = Field(default_factory=utc_now, description="When the alert started firing")
    ended_at: Optional[datetime] = Field(default=None, description="When the alert was resolved")
    fingerprint: str = Field(..., min_length=1, description="Unique identifier for deduplication")
    
    @field_validator("name", "source", "fingerprint")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from string fields."""
        return v.strip()
    
    @field_validator("ended_at")
    @classmethod
    def validate_ended_at(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Ensure ended_at is after started_at if both are set."""
        if v is not None and info.data.get("started_at"):
            if v < info.data["started_at"]:
                raise ValueError("ended_at must be after started_at")
        return v
    
    def is_active(self) -> bool:
        """Check if the alert is currently active."""
        return self.status in (AlertStatus.FIRING, AlertStatus.PENDING)
    
    def duration_seconds(self) -> float | None:
        """Get alert duration in seconds, or None if still active."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class AlertGroup(BaseModel):
    """A group of related alerts."""
    model_config = ConfigDict(validate_assignment=True)
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1)
    alerts: list[Alert] = Field(default_factory=list)
    common_labels: dict[str, str] = Field(default_factory=dict)
    
    def severity(self) -> AlertSeverity:
        """Get the highest severity among grouped alerts."""
        if not self.alerts:
            return AlertSeverity.INFO
        severity_order = [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.MEDIUM, AlertSeverity.LOW, AlertSeverity.INFO]
        for sev in severity_order:
            if any(a.severity == sev for a in self.alerts):
                return sev
        return AlertSeverity.INFO
