"""
Alert data models for AutoSRE V2.

Defines the canonical alert representation used throughout the system,
supporting multiple alert sources with consistent normalization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class AlertSeverity(str, Enum):
    """Alert severity levels following common SRE conventions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @classmethod
    def from_string(cls, value: str) -> AlertSeverity:
        """Parse severity from various string formats."""
        normalized = value.lower().strip()

        # Handle common variations
        severity_map = {
            "critical": cls.CRITICAL,
            "crit": cls.CRITICAL,
            "p1": cls.CRITICAL,
            "sev1": cls.CRITICAL,
            "high": cls.HIGH,
            "major": cls.HIGH,
            "p2": cls.HIGH,
            "sev2": cls.HIGH,
            "medium": cls.MEDIUM,
            "moderate": cls.MEDIUM,
            "warning": cls.MEDIUM,
            "warn": cls.MEDIUM,
            "p3": cls.MEDIUM,
            "sev3": cls.MEDIUM,
            "low": cls.LOW,
            "minor": cls.LOW,
            "p4": cls.LOW,
            "sev4": cls.LOW,
            "info": cls.INFO,
            "informational": cls.INFO,
            "debug": cls.INFO,
            "p5": cls.INFO,
        }

        return severity_map.get(normalized, cls.MEDIUM)

    @property
    def numeric_priority(self) -> int:
        """Get numeric priority (lower = more urgent)."""
        return {
            self.CRITICAL: 1,
            self.HIGH: 2,
            self.MEDIUM: 3,
            self.LOW: 4,
            self.INFO: 5,
        }[self]


class AlertStatus(str, Enum):
    """Alert lifecycle status."""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class AlertSource(str, Enum):
    """Supported alert sources."""

    PROMETHEUS = "prometheus"
    ALERTMANAGER = "alertmanager"
    DATADOG = "datadog"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    CLOUDWATCH = "cloudwatch"
    CUSTOM = "custom"


class AlertLabel(BaseModel):
    """A single alert label with normalization."""

    key: str
    value: str

    def __hash__(self) -> int:
        return hash((self.key, self.value))


class AlertAnnotation(BaseModel):
    """Alert annotation for additional context."""

    key: str
    value: str


class Alert(BaseModel):
    """
    Canonical alert representation.

    Normalizes alerts from various sources into a consistent format
    for investigation and analysis.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    fingerprint: str | None = Field(
        default=None,
        description="Unique fingerprint for deduplication",
    )

    # Core fields
    name: str = Field(..., description="Alert name/rule name")
    description: str = Field(default="", description="Human-readable description")
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    status: AlertStatus = Field(default=AlertStatus.FIRING)
    source: AlertSource = Field(default=AlertSource.CUSTOM)

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    last_received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Context
    service: str | None = Field(default=None, description="Affected service name")
    namespace: str | None = Field(default=None, description="K8s namespace or environment")
    cluster: str | None = Field(default=None, description="Cluster identifier")
    instance: str | None = Field(default=None, description="Specific instance/pod")

    # Labels and annotations
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)

    # Source-specific data
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Original alert data from source",
    )

    # Investigation tracking
    investigation_id: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def parse_severity(cls, v: Any) -> AlertSeverity:
        """Parse severity from various formats."""
        if isinstance(v, AlertSeverity):
            return v
        if isinstance(v, str):
            return AlertSeverity.from_string(v)
        return AlertSeverity.MEDIUM

    @model_validator(mode="after")
    def extract_common_labels(self) -> Alert:
        """Extract common fields from labels if not explicitly set."""
        if not self.service and "service" in self.labels:
            self.service = self.labels["service"]
        if not self.service and "job" in self.labels:
            self.service = self.labels["job"]

        if not self.namespace and "namespace" in self.labels:
            self.namespace = self.labels["namespace"]

        if not self.cluster and "cluster" in self.labels:
            self.cluster = self.labels["cluster"]

        if not self.instance and "instance" in self.labels:
            self.instance = self.labels["instance"]
        if not self.instance and "pod" in self.labels:
            self.instance = self.labels["pod"]

        return self

    @model_validator(mode="after")
    def generate_fingerprint(self) -> Alert:
        """Generate fingerprint if not provided."""
        if not self.fingerprint:
            import hashlib
            # Create fingerprint from stable fields
            parts = [
                self.name,
                self.service or "",
                self.namespace or "",
                self.cluster or "",
            ]
            # Add sorted labels for consistency
            for key in sorted(self.labels.keys()):
                if key not in ("alertname", "severity"):
                    parts.append(f"{key}={self.labels[key]}")

            content = "|".join(parts)
            self.fingerprint = hashlib.sha256(content.encode()).hexdigest()[:16]

        return self

    @property
    def duration(self) -> float | None:
        """Get alert duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status in (AlertStatus.FIRING, AlertStatus.INVESTIGATING)

    @property
    def summary(self) -> str:
        """Generate a concise summary for logging/display."""
        return (
            f"[{self.severity.value.upper()}] {self.name}"
            f"{f' in {self.service}' if self.service else ''}"
            f"{f' ({self.namespace})' if self.namespace else ''}"
        )

    def acknowledge(self, user: str) -> None:
        """Mark alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = user
        self.acknowledged_at = datetime.now(timezone.utc)

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.ended_at = datetime.now(timezone.utc)

    def to_prompt_context(self) -> str:
        """Format alert for LLM prompt context."""
        lines = [
            f"Alert: {self.name}",
            f"Severity: {self.severity.value}",
            f"Status: {self.status.value}",
        ]

        if self.description:
            lines.append(f"Description: {self.description}")

        if self.service:
            lines.append(f"Service: {self.service}")
        if self.namespace:
            lines.append(f"Namespace: {self.namespace}")
        if self.cluster:
            lines.append(f"Cluster: {self.cluster}")
        if self.instance:
            lines.append(f"Instance: {self.instance}")

        lines.append(f"Started: {self.started_at.isoformat()}")
        if self.duration:
            lines.append(f"Duration: {self.duration:.0f}s")

        if self.labels:
            lines.append("Labels:")
            for key, value in sorted(self.labels.items()):
                lines.append(f"  {key}: {value}")

        if self.annotations:
            lines.append("Annotations:")
            for key, value in sorted(self.annotations.items()):
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    @classmethod
    def from_alertmanager(cls, data: dict[str, Any]) -> Alert:
        """
        Create Alert from AlertManager webhook payload.

        Handles both single alert format and grouped alerts.
        """
        labels = data.get("labels", {})
        annotations = data.get("annotations", {})

        # Parse timestamps
        starts_at = data.get("startsAt")
        if starts_at:
            if isinstance(starts_at, str):
                starts_at = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        else:
            starts_at = datetime.now(timezone.utc)

        ends_at = data.get("endsAt")
        if ends_at:
            if isinstance(ends_at, str):
                ends_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                # AlertManager sends far-future date for active alerts
                if ends_at.year > 9000:
                    ends_at = None

        return cls(
            name=labels.get("alertname", "unknown"),
            description=annotations.get("description", annotations.get("summary", "")),
            severity=labels.get("severity", "medium"),
            status=AlertStatus.FIRING if data.get("status") == "firing" else AlertStatus.RESOLVED,
            source=AlertSource.ALERTMANAGER,
            started_at=starts_at,
            ended_at=ends_at,
            fingerprint=data.get("fingerprint"),
            labels=labels,
            annotations=annotations,
            raw_data=data,
        )

    @classmethod
    def from_prometheus(cls, data: dict[str, Any]) -> Alert:
        """Create Alert from Prometheus alert rule evaluation."""
        labels = data.get("labels", {})
        annotations = data.get("annotations", {})

        return cls(
            name=labels.get("alertname", data.get("name", "unknown")),
            description=annotations.get("description", annotations.get("summary", "")),
            severity=labels.get("severity", "medium"),
            status=AlertStatus.FIRING if data.get("state") == "firing" else AlertStatus.RESOLVED,
            source=AlertSource.PROMETHEUS,
            labels=labels,
            annotations=annotations,
            raw_data=data,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: AlertSource = AlertSource.CUSTOM) -> Alert:
        """
        Create Alert from generic dictionary.

        Attempts to normalize common field names.
        """
        # Try common field name variations
        name = (
            data.get("name")
            or data.get("alertname")
            or data.get("alert_name")
            or data.get("title")
            or "unknown"
        )

        description = (
            data.get("description")
            or data.get("message")
            or data.get("summary")
            or data.get("body")
            or ""
        )

        severity = (
            data.get("severity")
            or data.get("priority")
            or data.get("level")
            or "medium"
        )

        service = (
            data.get("service")
            or data.get("service_name")
            or data.get("job")
            or data.get("application")
        )

        return cls(
            name=name,
            description=description,
            severity=severity,
            service=service,
            source=source,
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            raw_data=data,
        )


class AlertGroup(BaseModel):
    """A group of related alerts for batch processing."""

    group_key: str
    alerts: list[Alert]
    common_labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def max_severity(self) -> AlertSeverity:
        """Get the highest severity in the group."""
        if not self.alerts:
            return AlertSeverity.INFO

        return min(
            (a.severity for a in self.alerts),
            key=lambda s: s.numeric_priority,
        )

    @property
    def active_count(self) -> int:
        """Count of active alerts in the group."""
        return sum(1 for a in self.alerts if a.is_active)

    @classmethod
    def from_alertmanager_group(cls, data: dict[str, Any]) -> AlertGroup:
        """Create from AlertManager group webhook."""
        alerts = [
            Alert.from_alertmanager(alert_data)
            for alert_data in data.get("alerts", [])
        ]

        return cls(
            group_key=data.get("groupKey", ""),
            alerts=alerts,
            common_labels=data.get("commonLabels", {}),
        )
