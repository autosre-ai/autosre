"""Pydantic models for Datadog entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    """Datadog metric types."""
    GAUGE = "gauge"
    COUNT = "count"
    RATE = "rate"
    DISTRIBUTION = "distribution"


class MonitorStatus(str, Enum):
    """Datadog monitor status."""
    OK = "OK"
    ALERT = "Alert"
    WARN = "Warn"
    NO_DATA = "No Data"
    UNKNOWN = "Unknown"
    IGNORED = "Ignored"
    SKIPPED = "Skipped"


class MonitorType(str, Enum):
    """Datadog monitor types."""
    METRIC = "metric alert"
    SERVICE_CHECK = "service check"
    EVENT_ALERT = "event alert"
    QUERY_ALERT = "query alert"
    COMPOSITE = "composite"
    LOG_ALERT = "log alert"
    TRACE_ANALYTICS = "trace-analytics alert"
    RUM_ALERT = "rum alert"
    PROCESS_ALERT = "process alert"
    NETWORK_PERFORMANCE = "network performance alert"
    APM_ALERT = "apm alert"
    SYNTHETICS = "synthetics alert"
    SLO_ALERT = "slo alert"
    ANOMALY = "anomaly"
    OUTLIER = "outlier"
    FORECAST = "forecast"


class LogStatus(str, Enum):
    """Datadog log status levels."""
    EMERGENCY = "emergency"
    ALERT = "alert"
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    WARN = "warn"
    NOTICE = "notice"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


class EventPriority(str, Enum):
    """Datadog event priority."""
    NORMAL = "normal"
    LOW = "low"


class EventAlertType(str, Enum):
    """Datadog event alert types."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"
    USER_UPDATE = "user_update"
    RECOMMENDATION = "recommendation"
    SNAPSHOT = "snapshot"


# Metric Models

class MetricPoint(BaseModel):
    """A single metric data point."""
    timestamp: datetime = Field(..., description="Timestamp of the data point")
    value: float = Field(..., description="Metric value")


class MetricSeries(BaseModel):
    """A metric time series."""
    metric: str = Field(..., description="Metric name")
    display_name: str | None = Field(default=None, description="Display name")
    unit: list[dict[str, Any]] | None = Field(default=None, description="Unit info")
    pointlist: list[list[float]] = Field(default_factory=list, description="Raw point list [[timestamp, value], ...]")
    scope: str | None = Field(default=None, description="Metric scope/tags")
    expression: str | None = Field(default=None, description="Query expression")
    tag_set: list[str] = Field(default_factory=list, description="Tags for this series")
    start: int | None = Field(default=None, description="Start timestamp")
    end: int | None = Field(default=None, description="End timestamp")
    interval: int | None = Field(default=None, description="Data interval in seconds")
    aggr: str | None = Field(default=None, description="Aggregation method")
    length: int | None = Field(default=None, description="Number of points")
    
    model_config = {"extra": "allow"}
    
    @property
    def points(self) -> list[MetricPoint]:
        """Convert pointlist to MetricPoint objects."""
        return [
            MetricPoint(
                timestamp=datetime.fromtimestamp(p[0] / 1000),
                value=p[1]
            )
            for p in self.pointlist
        ]
    
    @property
    def latest_value(self) -> float | None:
        """Get the most recent value."""
        if self.pointlist:
            return self.pointlist[-1][1]
        return None


class MetricQueryResult(BaseModel):
    """Result from a metric query."""
    status: str = Field(default="ok", description="Query status")
    res_type: str | None = Field(default=None, description="Result type")
    from_date: int | None = Field(default=None, description="Query start timestamp (ms)")
    to_date: int | None = Field(default=None, description="Query end timestamp (ms)")
    series: list[MetricSeries] = Field(default_factory=list, description="Time series data")
    query: str | None = Field(default=None, description="Original query")
    message: str | None = Field(default=None, description="Status message")
    group_by: list[str] = Field(default_factory=list, description="Group by dimensions")
    
    model_config = {"extra": "allow"}


# Log Models

class LogAttributes(BaseModel):
    """Attributes of a log entry."""
    host: str | None = Field(default=None, description="Host that generated the log")
    service: str | None = Field(default=None, description="Service name")
    status: LogStatus | str | None = Field(default=None, description="Log status/level")
    timestamp: datetime | None = Field(default=None, description="Log timestamp")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Custom attributes")
    tags: list[str] = Field(default_factory=list, description="Log tags")
    message: str | None = Field(default=None, description="Log message")
    
    model_config = {"extra": "allow"}


class Log(BaseModel):
    """A single log entry."""
    id: str = Field(..., description="Log ID")
    type: str = Field(default="log", description="Object type")
    attributes: LogAttributes = Field(..., description="Log attributes")
    
    model_config = {"extra": "allow"}
    
    @property
    def message(self) -> str | None:
        """Get the log message."""
        return self.attributes.message
    
    @property
    def service(self) -> str | None:
        """Get the service name."""
        return self.attributes.service
    
    @property
    def status(self) -> str | None:
        """Get the log status."""
        s = self.attributes.status
        return s.value if isinstance(s, LogStatus) else s


class LogQueryResult(BaseModel):
    """Result from a log query."""
    data: list[Log] = Field(default_factory=list, description="Log entries")
    meta: dict[str, Any] = Field(default_factory=dict, description="Query metadata")
    links: dict[str, str] = Field(default_factory=dict, description="Pagination links")
    
    model_config = {"extra": "allow"}
    
    @property
    def logs(self) -> list[Log]:
        """Alias for data."""
        return self.data
    
    @property
    def next_cursor(self) -> str | None:
        """Get cursor for next page."""
        return self.meta.get("page", {}).get("after")


# Event Models

class Event(BaseModel):
    """A Datadog event."""
    id: int | None = Field(default=None, description="Event ID")
    title: str = Field(..., description="Event title")
    text: str = Field(..., description="Event body text")
    date_happened: datetime | None = Field(default=None, description="When event occurred")
    priority: EventPriority = Field(default=EventPriority.NORMAL, description="Event priority")
    host: str | None = Field(default=None, description="Host associated with event")
    tags: list[str] = Field(default_factory=list, description="Event tags")
    alert_type: EventAlertType = Field(default=EventAlertType.INFO, description="Alert type")
    aggregation_key: str | None = Field(default=None, description="Aggregation key for grouping")
    source_type_name: str | None = Field(default=None, description="Source type")
    device_name: str | None = Field(default=None, description="Device name")
    url: str | None = Field(default=None, description="URL to event in Datadog")
    is_aggregate: bool = Field(default=False, description="Whether this is an aggregate")
    
    model_config = {"extra": "allow"}


class EventQueryResult(BaseModel):
    """Result from an event query."""
    events: list[Event] = Field(default_factory=list, description="Events")
    status: str = Field(default="ok", description="Query status")
    
    model_config = {"extra": "allow"}


# Monitor Models

class MonitorThresholds(BaseModel):
    """Monitor threshold configuration."""
    critical: float | None = Field(default=None, description="Critical threshold")
    critical_recovery: float | None = Field(default=None, description="Critical recovery threshold")
    warning: float | None = Field(default=None, description="Warning threshold")
    warning_recovery: float | None = Field(default=None, description="Warning recovery threshold")
    ok: float | None = Field(default=None, description="OK threshold")
    unknown: float | None = Field(default=None, description="Unknown threshold")
    
    model_config = {"extra": "allow"}


class MonitorOptions(BaseModel):
    """Monitor configuration options."""
    thresholds: MonitorThresholds | None = Field(default=None, description="Alert thresholds")
    notify_no_data: bool = Field(default=False, description="Notify on no data")
    no_data_timeframe: int | None = Field(default=None, description="No data timeout in minutes")
    notify_audit: bool = Field(default=False, description="Notify on audit events")
    timeout_h: int | None = Field(default=None, description="Auto-resolve timeout hours")
    renotify_interval: int | None = Field(default=None, description="Renotification interval minutes")
    escalation_message: str | None = Field(default=None, description="Escalation message")
    include_tags: bool = Field(default=True, description="Include tags in notifications")
    require_full_window: bool = Field(default=False, description="Require full evaluation window")
    new_host_delay: int | None = Field(default=None, description="New host delay seconds")
    evaluation_delay: int | None = Field(default=None, description="Evaluation delay seconds")
    silenced: dict[str, int | None] = Field(default_factory=dict, description="Silenced scopes")
    
    model_config = {"extra": "allow"}


class MonitorState(BaseModel):
    """State of a monitor for a specific group."""
    name: str | None = Field(default=None, description="Group name")
    status: MonitorStatus = Field(..., description="Current status")
    last_triggered_ts: int | None = Field(default=None, description="Last triggered timestamp")
    last_resolved_ts: int | None = Field(default=None, description="Last resolved timestamp")
    last_notified_ts: int | None = Field(default=None, description="Last notification timestamp")
    last_nodata_ts: int | None = Field(default=None, description="Last no-data timestamp")
    
    model_config = {"extra": "allow"}


class Monitor(BaseModel):
    """A Datadog monitor."""
    id: int = Field(..., description="Monitor ID")
    org_id: int | None = Field(default=None, description="Organization ID")
    type: MonitorType | str = Field(..., description="Monitor type")
    name: str = Field(..., description="Monitor name")
    query: str = Field(..., description="Monitor query")
    message: str = Field(default="", description="Notification message")
    tags: list[str] = Field(default_factory=list, description="Monitor tags")
    options: MonitorOptions | dict[str, Any] = Field(default_factory=dict, description="Monitor options")
    overall_state: MonitorStatus | None = Field(default=None, description="Overall status")
    overall_state_modified: datetime | None = Field(default=None, description="Last state change")
    created: datetime | None = Field(default=None, description="Creation time")
    created_by: dict[str, Any] | None = Field(default=None, description="Creator info")
    modified: datetime | None = Field(default=None, description="Last modification time")
    multi: bool = Field(default=False, description="Multi-alert monitor")
    priority: int | None = Field(default=None, description="Priority (1-5)")
    restricted_roles: list[str] = Field(default_factory=list, description="Restricted role IDs")
    state: dict[str, MonitorState] = Field(default_factory=dict, description="State by group")
    
    model_config = {"extra": "allow"}
    
    @property
    def is_alerting(self) -> bool:
        """Check if monitor is in alerting state."""
        return self.overall_state in (MonitorStatus.ALERT, MonitorStatus.WARN)
    
    @property
    def is_ok(self) -> bool:
        """Check if monitor is OK."""
        return self.overall_state == MonitorStatus.OK


class MonitorSearchResult(BaseModel):
    """Result from monitor search."""
    monitors: list[Monitor] = Field(default_factory=list, description="Monitors")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Search metadata")
    counts: dict[str, Any] = Field(default_factory=dict, description="Result counts")
    
    model_config = {"extra": "allow"}


# Host Models

class HostMetrics(BaseModel):
    """Host metric values."""
    cpu: float | None = Field(default=None, description="CPU usage percentage")
    iowait: float | None = Field(default=None, description="IO wait percentage")
    load: float | None = Field(default=None, description="System load")
    
    model_config = {"extra": "allow"}


class HostMeta(BaseModel):
    """Host metadata."""
    agent_version: str | None = Field(default=None, description="Agent version")
    cpu_cores: int | None = Field(default=None, description="Number of CPU cores")
    gohai: dict[str, Any] | None = Field(default=None, description="Gohai system info")
    machine: str | None = Field(default=None, description="Machine type")
    platform: str | None = Field(default=None, description="Platform/OS")
    processor: str | None = Field(default=None, description="Processor info")
    python_version: str | None = Field(default=None, description="Python version")
    socket_fqdn: str | None = Field(default=None, description="Socket FQDN")
    socket_hostname: str | None = Field(default=None, description="Socket hostname")
    
    model_config = {"extra": "allow"}


class Host(BaseModel):
    """A Datadog host."""
    id: int | None = Field(default=None, description="Host ID")
    name: str = Field(..., description="Host name")
    aliases: list[str] = Field(default_factory=list, description="Host aliases")
    apps: list[str] = Field(default_factory=list, description="Running applications")
    aws_name: str | None = Field(default=None, description="AWS instance name")
    host_name: str | None = Field(default=None, description="Canonical hostname")
    is_muted: bool = Field(default=False, description="Whether host is muted")
    last_reported_time: int | None = Field(default=None, description="Last report timestamp")
    meta: HostMeta | None = Field(default=None, description="Host metadata")
    metrics: HostMetrics | None = Field(default=None, description="Latest metrics")
    mute_timeout: int | None = Field(default=None, description="Mute timeout")
    sources: list[str] = Field(default_factory=list, description="Data sources")
    tags_by_source: dict[str, list[str]] = Field(default_factory=dict, description="Tags by source")
    up: bool = Field(default=True, description="Whether host is up")
    
    model_config = {"extra": "allow"}
    
    @property
    def all_tags(self) -> list[str]:
        """Get all tags from all sources."""
        tags = []
        for source_tags in self.tags_by_source.values():
            tags.extend(source_tags)
        return list(set(tags))


class HostListResult(BaseModel):
    """Result from host list query."""
    host_list: list[Host] = Field(default_factory=list, description="Hosts")
    total_matching: int = Field(default=0, description="Total matching hosts")
    total_returned: int = Field(default=0, description="Returned hosts count")
    
    model_config = {"extra": "allow"}


# Dashboard Models

class DashboardWidget(BaseModel):
    """A widget in a dashboard."""
    id: int | None = Field(default=None, description="Widget ID")
    definition: dict[str, Any] = Field(..., description="Widget definition")
    layout: dict[str, Any] | None = Field(default=None, description="Widget layout")
    
    model_config = {"extra": "allow"}


class Dashboard(BaseModel):
    """A Datadog dashboard."""
    id: str = Field(..., description="Dashboard ID")
    title: str = Field(..., description="Dashboard title")
    description: str | None = Field(default=None, description="Dashboard description")
    author_handle: str | None = Field(default=None, description="Author email/handle")
    author_name: str | None = Field(default=None, description="Author name")
    layout_type: str = Field(default="ordered", description="Layout type (ordered/free)")
    widgets: list[DashboardWidget] = Field(default_factory=list, description="Dashboard widgets")
    template_variables: list[dict[str, Any]] = Field(default_factory=list, description="Template variables")
    is_read_only: bool = Field(default=False, description="Read-only status")
    url: str | None = Field(default=None, description="Dashboard URL")
    created_at: datetime | None = Field(default=None, description="Creation time")
    modified_at: datetime | None = Field(default=None, description="Last modification time")
    
    model_config = {"extra": "allow"}


class DashboardSummary(BaseModel):
    """Summary of a dashboard for listing."""
    id: str = Field(..., description="Dashboard ID")
    title: str = Field(..., description="Dashboard title")
    description: str | None = Field(default=None, description="Dashboard description")
    author_handle: str | None = Field(default=None, description="Author handle")
    layout_type: str = Field(default="ordered", description="Layout type")
    url: str | None = Field(default=None, description="Dashboard URL")
    is_read_only: bool = Field(default=False, description="Read-only status")
    created_at: datetime | None = Field(default=None, description="Creation time")
    modified_at: datetime | None = Field(default=None, description="Last modification time")
    
    model_config = {"extra": "allow"}


class DashboardListResult(BaseModel):
    """Result from dashboard list query."""
    dashboards: list[DashboardSummary] = Field(default_factory=list, description="Dashboards")
    
    model_config = {"extra": "allow"}
