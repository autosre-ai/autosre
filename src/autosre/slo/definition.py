"""
SLO Definition Management for AutoSRE.

Provides comprehensive Service Level Objective (SLO) definitions including:
- SLI (Service Level Indicator) types and metrics
- SLO target specifications
- Rolling window calculations
- Multi-window multi-burn-rate alerting
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Union
import json

from pydantic import BaseModel, Field


class SLIType(str, Enum):
    """Types of Service Level Indicators."""
    
    AVAILABILITY = "availability"       # Uptime/availability percentage
    LATENCY = "latency"                 # Response time percentiles
    THROUGHPUT = "throughput"           # Requests per second
    ERROR_RATE = "error_rate"           # Error percentage
    SATURATION = "saturation"           # Resource utilization
    FRESHNESS = "freshness"             # Data freshness
    CORRECTNESS = "correctness"         # Data/response correctness
    QUALITY = "quality"                 # Custom quality metrics


class SLOPeriod(str, Enum):
    """SLO measurement periods."""
    
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ROLLING_7D = "rolling_7d"
    ROLLING_28D = "rolling_28d"
    ROLLING_30D = "rolling_30d"
    ROLLING_90D = "rolling_90d"


class AlertSeverity(str, Enum):
    """Alert severity levels for SLO violations."""
    
    PAGE = "page"           # Immediate page (PagerDuty, etc.)
    TICKET = "ticket"       # Create ticket for follow-up
    WARNING = "warning"     # Warning notification
    INFO = "info"           # Informational only


class ComplianceStatus(str, Enum):
    """SLO compliance status."""
    
    HEALTHY = "healthy"         # Meeting SLO with healthy budget
    WARNING = "warning"         # Budget is low but not violated
    CRITICAL = "critical"       # Budget nearly exhausted
    VIOLATED = "violated"       # SLO violated (budget exhausted)
    UNKNOWN = "unknown"         # Insufficient data


@dataclass
class LatencyThreshold:
    """Latency threshold configuration."""
    
    percentile: float           # e.g., 0.50, 0.95, 0.99
    threshold_ms: float         # Maximum acceptable latency in ms
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "percentile": self.percentile,
            "threshold_ms": self.threshold_ms,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "LatencyThreshold":
        """Create from dictionary."""
        return cls(
            percentile=data["percentile"],
            threshold_ms=data["threshold_ms"],
        )


class SLIMetric(BaseModel):
    """Defines how to measure a Service Level Indicator."""
    
    name: str
    sli_type: SLIType
    description: str = ""
    
    # Metric source configuration
    metric_source: str = "prometheus"   # prometheus, datadog, cloudwatch, custom
    good_events_query: str = ""         # Query for good events
    total_events_query: str = ""        # Query for total events
    
    # Or ratio-based
    numerator_query: str = ""           # Numerator query
    denominator_query: str = ""         # Denominator query
    
    # For latency SLIs
    latency_thresholds: list[dict] = Field(default_factory=list)
    
    # For threshold-based SLIs
    threshold_value: Optional[float] = None
    threshold_operator: str = "gte"     # gt, gte, lt, lte, eq
    
    # Metadata
    unit: str = ""                      # e.g., "ms", "%", "req/s"
    aggregation: str = "rate"           # rate, sum, avg, percentile
    
    def calculate_sli(
        self,
        good_events: float,
        total_events: float,
    ) -> float:
        """Calculate SLI from good/total events."""
        if total_events == 0:
            return 1.0  # No events = 100% success
        return good_events / total_events
    
    def is_latency_good(self, latency_ms: float, percentile: float) -> bool:
        """Check if latency meets threshold for given percentile."""
        for threshold_dict in self.latency_thresholds:
            threshold = LatencyThreshold.from_dict(threshold_dict)
            if threshold.percentile == percentile:
                return latency_ms <= threshold.threshold_ms
        return True


class BurnRateWindow(BaseModel):
    """Multi-window multi-burn-rate alert window."""
    
    name: str
    duration_hours: float
    burn_rate_threshold: float      # Multiple of acceptable burn rate
    
    # For multi-window alerting
    short_window_hours: Optional[float] = None
    short_window_threshold: Optional[float] = None


class AlertPolicy(BaseModel):
    """Alert policy for SLO violations."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    severity: AlertSeverity
    
    # Burn rate windows (for multi-window alerting)
    burn_rate_windows: list[BurnRateWindow] = Field(default_factory=list)
    
    # Simple threshold alerting
    budget_remaining_threshold: Optional[float] = None  # Alert when below X%
    
    # Notification targets
    notification_channels: list[str] = Field(default_factory=list)
    escalation_policy_id: Optional[str] = None
    
    # Suppression
    suppress_during_maintenance: bool = True
    suppress_duration_minutes: int = 0          # Cool-down period
    
    def should_alert(
        self,
        current_burn_rate: float,
        budget_remaining_pct: float,
    ) -> bool:
        """Determine if alert should fire."""
        # Check budget threshold
        if self.budget_remaining_threshold is not None:
            if budget_remaining_pct <= self.budget_remaining_threshold:
                return True
        
        # Check burn rate windows
        for window in self.burn_rate_windows:
            if current_burn_rate >= window.burn_rate_threshold:
                return True
        
        return False


class SLODefinition(BaseModel):
    """Complete SLO definition."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Service identification
    service_id: str
    service_name: str = ""
    owner_team: str = ""
    
    # SLI configuration
    sli: SLIMetric
    
    # SLO target
    target: float = Field(ge=0.0, le=1.0)       # e.g., 0.999 for 99.9%
    period: SLOPeriod = SLOPeriod.ROLLING_30D
    
    # Error budget configuration
    error_budget_policy: str = "standard"        # standard, aggressive, relaxed
    
    # Alert policies
    alert_policies: list[AlertPolicy] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    
    # Labels/tags
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Status
    is_active: bool = True
    
    @property
    def error_budget_fraction(self) -> float:
        """Calculate error budget as fraction (1 - target)."""
        return 1.0 - self.target
    
    @property
    def target_percentage(self) -> float:
        """Return target as percentage."""
        return self.target * 100
    
    @property
    def error_budget_percentage(self) -> float:
        """Return error budget as percentage."""
        return self.error_budget_fraction * 100
    
    def get_period_days(self) -> int:
        """Get the number of days in the SLO period."""
        period_days = {
            SLOPeriod.HOURLY: 1/24,
            SLOPeriod.DAILY: 1,
            SLOPeriod.WEEKLY: 7,
            SLOPeriod.MONTHLY: 30,
            SLOPeriod.QUARTERLY: 90,
            SLOPeriod.ROLLING_7D: 7,
            SLOPeriod.ROLLING_28D: 28,
            SLOPeriod.ROLLING_30D: 30,
            SLOPeriod.ROLLING_90D: 90,
        }
        return int(period_days.get(self.period, 30))
    
    def calculate_error_budget_minutes(self) -> float:
        """Calculate total error budget in minutes for the period."""
        period_minutes = self.get_period_days() * 24 * 60
        return period_minutes * self.error_budget_fraction
    
    def add_default_alert_policies(self) -> None:
        """Add default multi-window multi-burn-rate alert policies."""
        # Page-level alert: 2% of budget consumed in 1 hour
        # (36x burn rate sustained, 14.4x burn rate in 5min window)
        page_policy = AlertPolicy(
            name=f"{self.name} - Page",
            severity=AlertSeverity.PAGE,
            burn_rate_windows=[
                BurnRateWindow(
                    name="1h sustained",
                    duration_hours=1.0,
                    burn_rate_threshold=14.4,
                    short_window_hours=5/60,  # 5 minutes
                    short_window_threshold=14.4,
                ),
            ],
            budget_remaining_threshold=2.0,  # Page if < 2% budget
        )
        
        # Ticket-level alert: 5% of budget consumed in 6 hours
        ticket_policy = AlertPolicy(
            name=f"{self.name} - Ticket",
            severity=AlertSeverity.TICKET,
            burn_rate_windows=[
                BurnRateWindow(
                    name="6h sustained",
                    duration_hours=6.0,
                    burn_rate_threshold=6.0,
                    short_window_hours=0.5,  # 30 minutes
                    short_window_threshold=6.0,
                ),
            ],
            budget_remaining_threshold=10.0,  # Ticket if < 10% budget
        )
        
        # Warning: 10% of budget consumed in 3 days
        warning_policy = AlertPolicy(
            name=f"{self.name} - Warning",
            severity=AlertSeverity.WARNING,
            burn_rate_windows=[
                BurnRateWindow(
                    name="3d sustained",
                    duration_hours=72.0,
                    burn_rate_threshold=1.0,
                    short_window_hours=6.0,
                    short_window_threshold=1.0,
                ),
            ],
            budget_remaining_threshold=30.0,  # Warn if < 30% budget
        )
        
        self.alert_policies = [page_policy, ticket_policy, warning_policy]


class SLOGroup(BaseModel):
    """Group of related SLOs (e.g., for a service or team)."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Ownership
    owner_team: str = ""
    owner_email: str = ""
    
    # SLOs in this group
    slo_ids: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = Field(default_factory=dict)


class SLOManager:
    """Manager for SLO definitions."""
    
    def __init__(self):
        """Initialize the SLO manager."""
        self._slos: dict[str, SLODefinition] = {}
        self._groups: dict[str, SLOGroup] = {}
        self._service_slos: dict[str, list[str]] = {}  # service_id -> slo_ids
    
    def create_slo(
        self,
        name: str,
        service_id: str,
        sli: SLIMetric,
        target: float,
        period: SLOPeriod = SLOPeriod.ROLLING_30D,
        add_default_alerts: bool = True,
        **kwargs: Any,
    ) -> SLODefinition:
        """Create a new SLO definition."""
        slo = SLODefinition(
            name=name,
            service_id=service_id,
            sli=sli,
            target=target,
            period=period,
            **kwargs,
        )
        
        if add_default_alerts:
            slo.add_default_alert_policies()
        
        self._slos[slo.id] = slo
        
        # Track by service
        if service_id not in self._service_slos:
            self._service_slos[service_id] = []
        self._service_slos[service_id].append(slo.id)
        
        return slo
    
    def get_slo(self, slo_id: str) -> Optional[SLODefinition]:
        """Get an SLO by ID."""
        return self._slos.get(slo_id)
    
    def get_slos_for_service(self, service_id: str) -> list[SLODefinition]:
        """Get all SLOs for a service."""
        slo_ids = self._service_slos.get(service_id, [])
        return [self._slos[sid] for sid in slo_ids if sid in self._slos]
    
    def get_slos_for_team(self, team: str) -> list[SLODefinition]:
        """Get all SLOs owned by a team."""
        return [slo for slo in self._slos.values() if slo.owner_team == team]
    
    def list_slos(
        self,
        active_only: bool = True,
        labels: Optional[dict[str, str]] = None,
    ) -> list[SLODefinition]:
        """List all SLOs with optional filters."""
        results = list(self._slos.values())
        
        if active_only:
            results = [slo for slo in results if slo.is_active]
        
        if labels:
            results = [
                slo for slo in results
                if all(slo.labels.get(k) == v for k, v in labels.items())
            ]
        
        return results
    
    def update_slo(
        self,
        slo_id: str,
        **updates: Any,
    ) -> Optional[SLODefinition]:
        """Update an existing SLO."""
        slo = self._slos.get(slo_id)
        if not slo:
            return None
        
        for key, value in updates.items():
            if hasattr(slo, key):
                setattr(slo, key, value)
        
        slo.updated_at = datetime.now(timezone.utc)
        return slo
    
    def delete_slo(self, slo_id: str) -> bool:
        """Delete an SLO (soft delete by deactivating)."""
        slo = self._slos.get(slo_id)
        if not slo:
            return False
        
        slo.is_active = False
        slo.updated_at = datetime.now(timezone.utc)
        return True
    
    def create_group(
        self,
        name: str,
        owner_team: str = "",
        **kwargs: Any,
    ) -> SLOGroup:
        """Create a new SLO group."""
        group = SLOGroup(
            name=name,
            owner_team=owner_team,
            **kwargs,
        )
        self._groups[group.id] = group
        return group
    
    def add_slo_to_group(self, slo_id: str, group_id: str) -> bool:
        """Add an SLO to a group."""
        group = self._groups.get(group_id)
        if not group or slo_id not in self._slos:
            return False
        
        if slo_id not in group.slo_ids:
            group.slo_ids.append(slo_id)
        return True
    
    def get_group_slos(self, group_id: str) -> list[SLODefinition]:
        """Get all SLOs in a group."""
        group = self._groups.get(group_id)
        if not group:
            return []
        
        return [self._slos[sid] for sid in group.slo_ids if sid in self._slos]


# Convenience functions
def create_availability_slo(
    name: str,
    service_id: str,
    target: float = 0.999,
    good_events_query: str = "",
    total_events_query: str = "",
    period: SLOPeriod = SLOPeriod.ROLLING_30D,
) -> SLODefinition:
    """Create an availability SLO with sensible defaults."""
    sli = SLIMetric(
        name=f"{name}_availability",
        sli_type=SLIType.AVAILABILITY,
        description=f"Availability SLI for {name}",
        good_events_query=good_events_query or 'sum(rate(http_requests_total{status!~"5.."}[5m]))',
        total_events_query=total_events_query or 'sum(rate(http_requests_total[5m]))',
        unit="%",
    )
    
    slo = SLODefinition(
        name=name,
        service_id=service_id,
        sli=sli,
        target=target,
        period=period,
    )
    slo.add_default_alert_policies()
    return slo


def create_latency_slo(
    name: str,
    service_id: str,
    target: float = 0.99,
    p50_threshold_ms: float = 100.0,
    p95_threshold_ms: float = 250.0,
    p99_threshold_ms: float = 500.0,
    period: SLOPeriod = SLOPeriod.ROLLING_30D,
) -> SLODefinition:
    """Create a latency SLO with percentile thresholds."""
    sli = SLIMetric(
        name=f"{name}_latency",
        sli_type=SLIType.LATENCY,
        description=f"Latency SLI for {name}",
        latency_thresholds=[
            {"percentile": 0.50, "threshold_ms": p50_threshold_ms},
            {"percentile": 0.95, "threshold_ms": p95_threshold_ms},
            {"percentile": 0.99, "threshold_ms": p99_threshold_ms},
        ],
        good_events_query=f'sum(rate(http_request_duration_seconds_bucket{{le="{p99_threshold_ms/1000}"}}[5m]))',
        total_events_query='sum(rate(http_request_duration_seconds_count[5m]))',
        unit="ms",
    )
    
    slo = SLODefinition(
        name=name,
        service_id=service_id,
        sli=sli,
        target=target,
        period=period,
    )
    slo.add_default_alert_policies()
    return slo


def create_error_rate_slo(
    name: str,
    service_id: str,
    target: float = 0.999,
    error_query: str = "",
    total_query: str = "",
    period: SLOPeriod = SLOPeriod.ROLLING_30D,
) -> SLODefinition:
    """Create an error rate SLO."""
    sli = SLIMetric(
        name=f"{name}_error_rate",
        sli_type=SLIType.ERROR_RATE,
        description=f"Error rate SLI for {name}",
        # For error rate, good = total - errors
        good_events_query=total_query or 'sum(rate(http_requests_total[5m])) - ' + (
            error_query or 'sum(rate(http_requests_total{status=~"5.."}[5m]))'
        ),
        total_events_query=total_query or 'sum(rate(http_requests_total[5m]))',
        unit="%",
    )
    
    slo = SLODefinition(
        name=name,
        service_id=service_id,
        sli=sli,
        target=target,
        period=period,
    )
    slo.add_default_alert_policies()
    return slo
