"""Metrics models for telemetry data."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now, TimeRange


class MetricType(str, Enum):
    """Type of metric."""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AggregationType(str, Enum):
    """Aggregation function for metrics."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"


class MetricSample(BaseModel):
    """A single metric sample/data point."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    timestamp: datetime = Field(..., description="Sample timestamp")
    value: float = Field(..., description="Metric value")
    
    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        """Ensure value is finite."""
        if not isinstance(v, (int, float)):
            raise ValueError("Value must be numeric")
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Value must be finite")
        return float(v)


class MetricSeries(BaseModel):
    """A time series of metric samples."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    name: str = Field(..., min_length=1, description="Metric name")
    labels: dict[str, str] = Field(default_factory=dict, description="Metric labels")
    type: MetricType = Field(default=MetricType.GAUGE, description="Metric type")
    samples: list[MetricSample] = Field(default_factory=list, description="Time series samples")
    unit: str = Field(default="", description="Unit of measurement")
    
    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    def label_string(self) -> str:
        """Get labels as a Prometheus-style string."""
        if not self.labels:
            return ""
        pairs = [f'{k}="{v}"' for k, v in sorted(self.labels.items())]
        return "{" + ",".join(pairs) + "}"
    
    def full_name(self) -> str:
        """Get full metric name with labels."""
        return f"{self.name}{self.label_string()}"
    
    def latest(self) -> Optional[MetricSample]:
        """Get the most recent sample."""
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s.timestamp)
    
    def time_range(self) -> Optional[TimeRange]:
        """Get the time range covered by samples."""
        if not self.samples:
            return None
        sorted_samples = sorted(self.samples, key=lambda s: s.timestamp)
        return TimeRange(start=sorted_samples[0].timestamp, end=sorted_samples[-1].timestamp)


class MetricQuery(BaseModel):
    """A query for metrics data."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    
    # Query specification
    metric_name: str = Field(..., min_length=1, description="Metric name to query")
    labels: dict[str, str] = Field(default_factory=dict, description="Label filters")
    label_regex: dict[str, str] = Field(default_factory=dict, description="Label regex filters")
    
    # Time range
    start: datetime = Field(..., description="Query start time")
    end: datetime = Field(default_factory=utc_now, description="Query end time")
    step_seconds: int = Field(default=60, ge=1, le=86400, description="Query resolution step")
    
    # Aggregation
    aggregation: Optional[AggregationType] = Field(default=None, description="Aggregation function")
    group_by: list[str] = Field(default_factory=list, description="Labels to group by")
    
    # Source
    source: str = Field(default="prometheus", description="Metrics source")
    
    @field_validator("metric_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    @field_validator("end")
    @classmethod
    def validate_end(cls, v: datetime, info) -> datetime:
        """Ensure end is after start."""
        if info.data.get("start") and v < info.data["start"]:
            raise ValueError("end must be after start")
        return v
    
    def to_promql(self) -> str:
        """Convert to PromQL query string."""
        label_parts = []
        for k, v in self.labels.items():
            label_parts.append(f'{k}="{v}"')
        for k, v in self.label_regex.items():
            label_parts.append(f'{k}=~"{v}"')
        
        selector = f"{self.metric_name}"
        if label_parts:
            selector += "{" + ",".join(label_parts) + "}"
        
        if self.aggregation:
            if self.group_by:
                return f"{self.aggregation.value} by ({','.join(self.group_by)}) ({selector})"
            return f"{self.aggregation.value}({selector})"
        
        return selector


class MetricResult(BaseModel):
    """Result of a metric query."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    query_id: str = Field(..., description="ID of the query that produced this result")
    
    # Results
    series: list[MetricSeries] = Field(default_factory=list, description="Result time series")
    
    # Timing
    query_time_ms: int = Field(default=0, ge=0, description="Query execution time in milliseconds")
    fetched_at: datetime = Field(default_factory=utc_now)
    
    # Metadata
    source: str = Field(default="", description="Data source")
    warnings: list[str] = Field(default_factory=list, description="Query warnings")
    error: Optional[str] = Field(default=None, description="Error message if query failed")
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_empty(self) -> bool:
        """Check if result has no data."""
        return len(self.series) == 0
    
    def total_samples(self) -> int:
        """Get total number of samples across all series."""
        return sum(len(s.samples) for s in self.series)
    
    def is_error(self) -> bool:
        """Check if query resulted in an error."""
        return self.error is not None


class MetricThreshold(BaseModel):
    """A threshold for metric alerting."""
    model_config = ConfigDict(validate_assignment=True)
    
    metric_name: str = Field(..., min_length=1)
    operator: str = Field(..., description="Comparison operator (>, <, >=, <=, ==, !=)")
    value: float
    duration_seconds: int = Field(default=0, ge=0, description="How long condition must be true")
    labels: dict[str, str] = Field(default_factory=dict)
    
    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid = {">", "<", ">=", "<=", "==", "!="}
        if v not in valid:
            raise ValueError(f"operator must be one of {valid}")
        return v
    
    def evaluate(self, value: float) -> bool:
        """Evaluate the threshold against a value."""
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        return ops[self.operator](value, self.value)
