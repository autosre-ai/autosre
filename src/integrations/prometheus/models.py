"""Pydantic models for Prometheus entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResultType(str, Enum):
    """Prometheus result types."""
    MATRIX = "matrix"
    VECTOR = "vector"
    SCALAR = "scalar"
    STRING = "string"


class AlertState(str, Enum):
    """Prometheus alert states."""
    FIRING = "firing"
    PENDING = "pending"
    INACTIVE = "inactive"


class TargetHealth(str, Enum):
    """Prometheus target health states."""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class RuleType(str, Enum):
    """Prometheus rule types."""
    ALERTING = "alerting"
    RECORDING = "recording"


class RuleHealth(str, Enum):
    """Rule health states."""
    OK = "ok"
    ERR = "err"
    UNKNOWN = "unknown"


# Query Result Models

class MetricLabels(BaseModel):
    """Labels for a metric."""
    metric_name: str | None = Field(default=None, alias="__name__", description="Metric name")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a label value."""
        return getattr(self, key, None) or self.model_extra.get(key, default)
    
    def items(self) -> list[tuple[str, str]]:
        """Get all labels as key-value pairs."""
        result = []
        for key, value in self.model_extra.items():
            result.append((key, value))
        if self.metric_name:
            result.append(("__name__", self.metric_name))
        return result
    
    def to_selector(self) -> str:
        """Convert labels to a PromQL selector."""
        parts = []
        for key, value in self.items():
            if key != "__name__":
                parts.append(f'{key}="{value}"')
        
        name = self.metric_name or ""
        return f"{name}{{{','.join(parts)}}}"


class Sample(BaseModel):
    """A single time series sample (timestamp, value)."""
    timestamp: float = Field(..., description="Unix timestamp")
    value: str = Field(..., description="Sample value as string")
    
    @property
    def datetime(self) -> datetime:
        """Get timestamp as datetime."""
        return datetime.fromtimestamp(self.timestamp)
    
    @property
    def float_value(self) -> float:
        """Get value as float."""
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return float("nan")


class VectorSample(BaseModel):
    """A sample from a vector (instant) query."""
    metric: MetricLabels = Field(..., description="Metric labels")
    value: tuple[float, str] = Field(..., description="[timestamp, value]")
    
    model_config = {"extra": "allow"}
    
    @property
    def timestamp(self) -> float:
        """Get sample timestamp."""
        return self.value[0]
    
    @property
    def sample_value(self) -> float:
        """Get sample value as float."""
        try:
            return float(self.value[1])
        except (ValueError, TypeError):
            return float("nan")
    
    @property
    def datetime(self) -> datetime:
        """Get timestamp as datetime."""
        return datetime.fromtimestamp(self.timestamp)


class RangeSample(BaseModel):
    """A sample range from a matrix (range) query."""
    metric: MetricLabels = Field(..., description="Metric labels")
    values: list[tuple[float, str]] = Field(default_factory=list, description="[[timestamp, value], ...]")
    
    model_config = {"extra": "allow"}
    
    @property
    def samples(self) -> list[Sample]:
        """Get samples as Sample objects."""
        return [
            Sample(timestamp=ts, value=val)
            for ts, val in self.values
        ]
    
    @property
    def latest_value(self) -> float | None:
        """Get the most recent value."""
        if self.values:
            try:
                return float(self.values[-1][1])
            except (ValueError, TypeError, IndexError):
                pass
        return None
    
    @property
    def earliest_value(self) -> float | None:
        """Get the earliest value."""
        if self.values:
            try:
                return float(self.values[0][1])
            except (ValueError, TypeError, IndexError):
                pass
        return None


class ScalarResult(BaseModel):
    """Result from a scalar query."""
    result_type: ResultType = Field(default=ResultType.SCALAR, alias="resultType")
    result: tuple[float, str] = Field(..., description="[timestamp, value]")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def timestamp(self) -> float:
        """Get timestamp."""
        return self.result[0]
    
    @property
    def value(self) -> float:
        """Get value as float."""
        try:
            return float(self.result[1])
        except (ValueError, TypeError):
            return float("nan")


class VectorResult(BaseModel):
    """Result from an instant (vector) query."""
    result_type: ResultType = Field(default=ResultType.VECTOR, alias="resultType")
    result: list[VectorSample] = Field(default_factory=list)
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    def __len__(self) -> int:
        return len(self.result)
    
    def __iter__(self):
        return iter(self.result)
    
    def __getitem__(self, index):
        return self.result[index]


class MatrixResult(BaseModel):
    """Result from a range (matrix) query."""
    result_type: ResultType = Field(default=ResultType.MATRIX, alias="resultType")
    result: list[RangeSample] = Field(default_factory=list)
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    def __len__(self) -> int:
        return len(self.result)
    
    def __iter__(self):
        return iter(self.result)
    
    def __getitem__(self, index):
        return self.result[index]


class QueryResponse(BaseModel):
    """Response from a Prometheus query."""
    status: str = Field(..., description="Response status (success/error)")
    data: VectorResult | MatrixResult | ScalarResult | dict[str, Any] = Field(..., description="Query result data")
    error_type: str | None = Field(default=None, alias="errorType", description="Error type if status is error")
    error: str | None = Field(default=None, description="Error message if status is error")
    warnings: list[str] = Field(default_factory=list, description="Query warnings")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def is_success(self) -> bool:
        """Check if query was successful."""
        return self.status == "success"
    
    @property
    def result_type(self) -> ResultType | None:
        """Get the result type."""
        if isinstance(self.data, dict):
            rt = self.data.get("resultType")
            return ResultType(rt) if rt else None
        return self.data.result_type


# Alert Models

class AlertLabel(BaseModel):
    """Alert labels."""
    alertname: str = Field(..., description="Alert name")
    severity: str | None = Field(default=None, description="Alert severity")
    
    model_config = {"extra": "allow"}


class AlertAnnotation(BaseModel):
    """Alert annotations."""
    summary: str | None = Field(default=None, description="Alert summary")
    description: str | None = Field(default=None, description="Alert description")
    runbook_url: str | None = Field(default=None, description="Runbook URL")
    
    model_config = {"extra": "allow"}


class Alert(BaseModel):
    """A Prometheus alert."""
    labels: AlertLabel | dict[str, str] = Field(..., description="Alert labels")
    annotations: AlertAnnotation | dict[str, str] = Field(default_factory=dict, description="Alert annotations")
    state: AlertState = Field(..., description="Alert state")
    active_at: datetime | None = Field(default=None, alias="activeAt", description="When alert became active")
    value: str | None = Field(default=None, description="Alert value")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def alertname(self) -> str:
        """Get alert name."""
        if isinstance(self.labels, AlertLabel):
            return self.labels.alertname
        return self.labels.get("alertname", "unknown")
    
    @property
    def severity(self) -> str | None:
        """Get alert severity."""
        if isinstance(self.labels, AlertLabel):
            return self.labels.severity
        return self.labels.get("severity")
    
    @property
    def summary(self) -> str | None:
        """Get alert summary."""
        if isinstance(self.annotations, AlertAnnotation):
            return self.annotations.summary
        return self.annotations.get("summary")


class AlertGroup(BaseModel):
    """A group of alerts from the same rule."""
    name: str = Field(..., description="Alert name")
    file: str = Field(default="", description="Rule file")
    rules: list["AlertRule"] = Field(default_factory=list, description="Alert rules")
    
    model_config = {"extra": "allow"}


class AlertRule(BaseModel):
    """An alerting rule."""
    name: str = Field(..., description="Rule name")
    query: str = Field(..., description="PromQL expression")
    duration: float = Field(default=0, description="For duration in seconds")
    labels: dict[str, str] = Field(default_factory=dict, description="Rule labels")
    annotations: dict[str, str] = Field(default_factory=dict, description="Rule annotations")
    state: AlertState = Field(default=AlertState.INACTIVE, description="Rule state")
    health: RuleHealth = Field(default=RuleHealth.OK, description="Rule health")
    alerts: list[Alert] = Field(default_factory=list, description="Active alerts")
    last_error: str | None = Field(default=None, alias="lastError", description="Last evaluation error")
    last_evaluation: datetime | None = Field(default=None, alias="lastEvaluation", description="Last evaluation time")
    evaluation_time: float = Field(default=0, alias="evaluationTime", description="Last evaluation duration")
    type: RuleType = Field(default=RuleType.ALERTING, description="Rule type")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class AlertsResponse(BaseModel):
    """Response from alerts API."""
    status: str = Field(..., description="Response status")
    data: dict[str, Any] = Field(default_factory=dict, description="Response data")
    
    model_config = {"extra": "allow"}
    
    @property
    def alerts(self) -> list[Alert]:
        """Get list of alerts."""
        alerts_data = self.data.get("alerts", [])
        return [Alert(**a) for a in alerts_data]


# Rules Models

class RecordingRule(BaseModel):
    """A recording rule."""
    name: str = Field(..., description="Rule name")
    query: str = Field(..., description="PromQL expression")
    labels: dict[str, str] = Field(default_factory=dict, description="Rule labels")
    health: RuleHealth = Field(default=RuleHealth.OK, description="Rule health")
    last_error: str | None = Field(default=None, alias="lastError", description="Last evaluation error")
    last_evaluation: datetime | None = Field(default=None, alias="lastEvaluation", description="Last evaluation time")
    evaluation_time: float = Field(default=0, alias="evaluationTime", description="Last evaluation duration")
    type: RuleType = Field(default=RuleType.RECORDING, description="Rule type")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class RuleGroup(BaseModel):
    """A group of rules."""
    name: str = Field(..., description="Group name")
    file: str = Field(default="", description="Rule file path")
    rules: list[AlertRule | RecordingRule | dict[str, Any]] = Field(default_factory=list, description="Rules")
    interval: float = Field(default=60, description="Evaluation interval in seconds")
    limit: int = Field(default=0, description="Rule limit")
    last_evaluation: datetime | None = Field(default=None, alias="lastEvaluation", description="Last evaluation time")
    evaluation_time: float = Field(default=0, alias="evaluationTime", description="Last evaluation duration")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class RulesResponse(BaseModel):
    """Response from rules API."""
    status: str = Field(..., description="Response status")
    data: dict[str, list[RuleGroup]] = Field(default_factory=dict, description="Response data")
    
    model_config = {"extra": "allow"}
    
    @property
    def groups(self) -> list[RuleGroup]:
        """Get rule groups."""
        return self.data.get("groups", [])


# Target Models

class TargetDiscoveredLabels(BaseModel):
    """Discovered labels for a target."""
    address: str | None = Field(default=None, alias="__address__", description="Target address")
    scheme: str | None = Field(default=None, alias="__scheme__", description="Scrape scheme")
    scrape_interval: str | None = Field(default=None, alias="__scrape_interval__", description="Scrape interval")
    scrape_timeout: str | None = Field(default=None, alias="__scrape_timeout__", description="Scrape timeout")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class Target(BaseModel):
    """A scrape target."""
    discovered_labels: TargetDiscoveredLabels | dict[str, str] = Field(
        default_factory=dict,
        alias="discoveredLabels",
        description="Discovered labels"
    )
    labels: dict[str, str] = Field(default_factory=dict, description="Target labels")
    scrape_pool: str = Field(default="", alias="scrapePool", description="Scrape pool name")
    scrape_url: str = Field(default="", alias="scrapeUrl", description="Scrape URL")
    global_url: str = Field(default="", alias="globalUrl", description="Global URL")
    last_error: str = Field(default="", alias="lastError", description="Last scrape error")
    last_scrape: datetime | None = Field(default=None, alias="lastScrape", description="Last scrape time")
    last_scrape_duration: float = Field(default=0, alias="lastScrapeDuration", description="Last scrape duration")
    health: TargetHealth = Field(default=TargetHealth.UNKNOWN, description="Target health")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def job(self) -> str:
        """Get job label."""
        return self.labels.get("job", "")
    
    @property
    def instance(self) -> str:
        """Get instance label."""
        return self.labels.get("instance", "")
    
    @property
    def is_up(self) -> bool:
        """Check if target is up."""
        return self.health == TargetHealth.UP


class DroppedTarget(BaseModel):
    """A dropped scrape target."""
    discovered_labels: TargetDiscoveredLabels | dict[str, str] = Field(
        default_factory=dict,
        alias="discoveredLabels",
        description="Discovered labels"
    )
    
    model_config = {"extra": "allow", "populate_by_name": True}


class TargetsResponse(BaseModel):
    """Response from targets API."""
    status: str = Field(..., description="Response status")
    data: dict[str, list[Target | DroppedTarget]] = Field(default_factory=dict, description="Response data")
    
    model_config = {"extra": "allow"}
    
    @property
    def active_targets(self) -> list[Target]:
        """Get active targets."""
        return [Target(**t) if isinstance(t, dict) else t for t in self.data.get("activeTargets", [])]
    
    @property
    def dropped_targets(self) -> list[DroppedTarget]:
        """Get dropped targets."""
        return [DroppedTarget(**t) if isinstance(t, dict) else t for t in self.data.get("droppedTargets", [])]


# Metadata Models

class MetricMetadata(BaseModel):
    """Metadata for a metric."""
    type: str = Field(..., description="Metric type (counter, gauge, histogram, summary)")
    help: str = Field(default="", description="Help text")
    unit: str = Field(default="", description="Unit")
    
    model_config = {"extra": "allow"}


class LabelValue(BaseModel):
    """A label value."""
    value: str = Field(..., description="Label value")


class SeriesResult(BaseModel):
    """Result from series API."""
    status: str = Field(..., description="Response status")
    data: list[dict[str, str]] = Field(default_factory=list, description="Series labels")
    
    model_config = {"extra": "allow"}


class LabelsResponse(BaseModel):
    """Response from labels API."""
    status: str = Field(..., description="Response status")
    data: list[str] = Field(default_factory=list, description="Label names or values")
    
    model_config = {"extra": "allow"}


class BuildInfo(BaseModel):
    """Prometheus build information."""
    version: str = Field(..., description="Prometheus version")
    revision: str = Field(default="", description="Git revision")
    branch: str = Field(default="", description="Git branch")
    build_user: str = Field(default="", alias="buildUser", description="Build user")
    build_date: str = Field(default="", alias="buildDate", description="Build date")
    go_version: str = Field(default="", alias="goVersion", description="Go version")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class RuntimeInfo(BaseModel):
    """Prometheus runtime information."""
    start_time: datetime | None = Field(default=None, alias="startTime", description="Start time")
    cwd: str = Field(default="", alias="CWD", description="Working directory")
    reload_config_success: bool = Field(default=True, alias="reloadConfigSuccess", description="Config reload success")
    last_config_time: datetime | None = Field(default=None, alias="lastConfigTime", description="Last config time")
    storage_retention: str = Field(default="", alias="storageRetention", description="Storage retention")
    goroutines: int = Field(default=0, alias="goroutineCount", description="Goroutine count")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class StatusResponse(BaseModel):
    """Response from status endpoints."""
    status: str = Field(..., description="Response status")
    data: BuildInfo | RuntimeInfo | dict[str, Any] = Field(default_factory=dict, description="Status data")
    
    model_config = {"extra": "allow"}
