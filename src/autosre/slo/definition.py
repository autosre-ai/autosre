"""
SLO Definition for AutoSRE V2.

Defines Service Level Indicators (SLIs) and Service Level Objectives (SLOs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class SLIType(str, Enum):
    """Type of Service Level Indicator."""
    
    AVAILABILITY = "availability"  # Success rate
    LATENCY = "latency"  # Response time percentile
    THROUGHPUT = "throughput"  # Requests per second
    ERROR_RATE = "error_rate"  # Error percentage
    SATURATION = "saturation"  # Resource utilization
    FRESHNESS = "freshness"  # Data staleness
    CORRECTNESS = "correctness"  # Data accuracy
    CUSTOM = "custom"


class SLOWindow(str, Enum):
    """SLO evaluation window."""
    
    ROLLING_7D = "7d"
    ROLLING_28D = "28d"
    ROLLING_30D = "30d"
    ROLLING_90D = "90d"
    CALENDAR_WEEK = "calendar_week"
    CALENDAR_MONTH = "calendar_month"
    CALENDAR_QUARTER = "calendar_quarter"


@dataclass
class SLIConfig:
    """Configuration for an SLI."""
    
    # Query configuration
    numerator_query: str  # PromQL for good events
    denominator_query: str  # PromQL for total events
    
    # Or use ratio query directly
    ratio_query: Optional[str] = None
    
    # Latency-specific
    threshold_ms: Optional[float] = None
    percentile: Optional[float] = None  # 0.95, 0.99, etc.
    
    # Time settings
    evaluation_interval: str = "1m"
    
    def to_promql(self) -> str:
        """Generate PromQL for the SLI."""
        if self.ratio_query:
            return self.ratio_query
        
        return f"({self.numerator_query}) / ({self.denominator_query})"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator_query": self.numerator_query,
            "denominator_query": self.denominator_query,
            "ratio_query": self.ratio_query,
            "threshold_ms": self.threshold_ms,
            "percentile": self.percentile,
        }


@dataclass
class SLOTarget:
    """SLO target specification."""
    
    target: float  # 0.999 = 99.9%
    window: SLOWindow = SLOWindow.ROLLING_30D
    
    @property
    def target_percent(self) -> float:
        """Get target as percentage."""
        return self.target * 100
    
    @property
    def error_budget(self) -> float:
        """Get error budget (1 - target)."""
        return 1 - self.target
    
    @property
    def error_budget_percent(self) -> float:
        """Get error budget as percentage."""
        return self.error_budget * 100
    
    @property
    def window_days(self) -> int:
        """Get window duration in days."""
        window_map = {
            SLOWindow.ROLLING_7D: 7,
            SLOWindow.ROLLING_28D: 28,
            SLOWindow.ROLLING_30D: 30,
            SLOWindow.ROLLING_90D: 90,
            SLOWindow.CALENDAR_WEEK: 7,
            SLOWindow.CALENDAR_MONTH: 30,
            SLOWindow.CALENDAR_QUARTER: 90,
        }
        return window_map.get(self.window, 30)
    
    @property
    def error_budget_minutes(self) -> float:
        """Get error budget in minutes for the window."""
        total_minutes = self.window_days * 24 * 60
        return total_minutes * self.error_budget
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_percent": self.target_percent,
            "window": self.window.value,
            "error_budget": self.error_budget,
            "error_budget_minutes": self.error_budget_minutes,
        }


class SLODefinition(BaseModel):
    """
    Complete SLO definition.
    
    Example:
        slo = SLODefinition(
            name="api-availability",
            service="api-gateway",
            sli_type=SLIType.AVAILABILITY,
            target=0.999,
            numerator_query='sum(rate(http_requests_total{status!~"5.."}[5m]))',
            denominator_query='sum(rate(http_requests_total[5m]))',
        )
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        use_enum_values=True,
    )
    
    # Identity
    name: str = Field(..., description="SLO name")
    description: str = Field(default="", description="SLO description")
    
    # Service context
    service: str = Field(..., description="Service name")
    feature: Optional[str] = Field(default=None, description="Feature/endpoint")
    
    # SLI configuration
    sli_type: SLIType = Field(default=SLIType.AVAILABILITY)
    numerator_query: str = Field(default="", description="Good events query")
    denominator_query: str = Field(default="", description="Total events query")
    ratio_query: Optional[str] = Field(default=None, description="Direct ratio query")
    
    # Latency-specific
    latency_threshold_ms: Optional[float] = Field(default=None)
    latency_percentile: Optional[float] = Field(default=None)
    
    # Target
    target: float = Field(default=0.99, ge=0, le=1, description="SLO target (0-1)")
    window: str = Field(default="30d", description="Evaluation window")
    
    # Metadata
    owner: Optional[str] = Field(default=None, description="Team/person owning this SLO")
    tags: list[str] = Field(default_factory=list)
    
    # Alert configuration
    page_on_burn: bool = Field(default=True, description="Page on high burn rate")
    ticket_on_budget_low: bool = Field(default=True, description="Create ticket on low budget")
    
    # Created/updated timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def sli_config(self) -> SLIConfig:
        """Get SLI configuration."""
        return SLIConfig(
            numerator_query=self.numerator_query,
            denominator_query=self.denominator_query,
            ratio_query=self.ratio_query,
            threshold_ms=self.latency_threshold_ms,
            percentile=self.latency_percentile,
        )
    
    @property
    def slo_target(self) -> SLOTarget:
        """Get SLO target."""
        window_map = {
            "7d": SLOWindow.ROLLING_7D,
            "28d": SLOWindow.ROLLING_28D,
            "30d": SLOWindow.ROLLING_30D,
            "90d": SLOWindow.ROLLING_90D,
        }
        return SLOTarget(
            target=self.target,
            window=window_map.get(self.window, SLOWindow.ROLLING_30D),
        )
    
    @property
    def error_budget(self) -> float:
        """Get error budget."""
        return 1 - self.target
    
    @property
    def error_budget_percent(self) -> float:
        """Get error budget as percentage."""
        return self.error_budget * 100
    
    def get_sli_query(self) -> str:
        """Get the SLI PromQL query."""
        return self.sli_config.to_promql()
    
    def get_error_rate_query(self) -> str:
        """Get error rate PromQL query (1 - SLI)."""
        sli = self.get_sli_query()
        return f"1 - ({sli})"
    
    def to_prometheus_rule(self) -> dict[str, Any]:
        """Generate Prometheus recording rule."""
        return {
            "record": f"slo:{self.name}:sli",
            "expr": self.get_sli_query(),
            "labels": {
                "slo": self.name,
                "service": self.service,
                "sli_type": self.sli_type,
            },
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "service": self.service,
            "feature": self.feature,
            "sli_type": self.sli_type,
            "sli_config": self.sli_config.to_dict(),
            "target": self.slo_target.to_dict(),
            "owner": self.owner,
            "tags": self.tags,
            "page_on_burn": self.page_on_burn,
            "ticket_on_budget_low": self.ticket_on_budget_low,
        }


# Convenience alias
ServiceLevelObjective = SLODefinition


def create_availability_slo(
    name: str,
    service: str,
    target: float = 0.999,
    success_query: Optional[str] = None,
    total_query: Optional[str] = None,
) -> SLODefinition:
    """Helper to create an availability SLO."""
    if success_query is None:
        success_query = f'sum(rate(http_requests_total{{service="{service}",status!~"5.."}}[5m]))'
    if total_query is None:
        total_query = f'sum(rate(http_requests_total{{service="{service}"}}[5m]))'
    
    return SLODefinition(
        name=name,
        service=service,
        sli_type=SLIType.AVAILABILITY,
        numerator_query=success_query,
        denominator_query=total_query,
        target=target,
    )


def create_latency_slo(
    name: str,
    service: str,
    target: float = 0.99,
    threshold_ms: float = 500,
    percentile: float = 0.99,
    histogram_query: Optional[str] = None,
) -> SLODefinition:
    """Helper to create a latency SLO."""
    if histogram_query is None:
        histogram_query = f'http_request_duration_seconds_bucket{{service="{service}"}}'
    
    threshold_sec = threshold_ms / 1000
    
    # Good events: requests under threshold
    numerator = f'sum(rate({histogram_query.replace("_bucket", "_bucket")}{{le="{threshold_sec}"}}[5m]))'
    denominator = f'sum(rate({histogram_query.replace("_bucket", "_count")}[5m]))'
    
    return SLODefinition(
        name=name,
        service=service,
        sli_type=SLIType.LATENCY,
        numerator_query=numerator,
        denominator_query=denominator,
        target=target,
        latency_threshold_ms=threshold_ms,
        latency_percentile=percentile,
    )
