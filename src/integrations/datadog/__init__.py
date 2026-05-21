"""Datadog integration for AutoSRE."""

from .client import (
    DatadogClient,
    DatadogConfig,
    DatadogError,
    DatadogAuthError,
    DatadogNotFoundError,
    DatadogRateLimitError,
)
from .models import (
    # Enums
    MetricType,
    MonitorStatus,
    MonitorType,
    LogStatus,
    EventPriority,
    EventAlertType,
    # Metrics
    MetricPoint,
    MetricSeries,
    MetricQueryResult,
    # Logs
    Log,
    LogAttributes,
    LogQueryResult,
    # Events
    Event,
    EventQueryResult,
    # Monitors
    Monitor,
    MonitorOptions,
    MonitorThresholds,
    MonitorState,
    MonitorSearchResult,
    # Hosts
    Host,
    HostMetrics,
    HostMeta,
    HostListResult,
    # Dashboards
    Dashboard,
    DashboardWidget,
    DashboardSummary,
    DashboardListResult,
)
from .queries import (
    # Query builders
    MetricQuery,
    LogQuery,
    MonitorQuery,
    Aggregation,
    TimeWindow,
    # Pre-built queries
    SystemMetrics,
    ContainerMetrics,
    KubernetesMetrics,
    APMMetrics,
    DatabaseMetrics,
    CommonLogQueries,
    MonitorTemplates,
    # Time helpers
    time_range,
    last_hour,
    last_day,
    last_week,
)

__all__ = [
    # Client
    "DatadogClient",
    "DatadogConfig",
    "DatadogError",
    "DatadogAuthError",
    "DatadogNotFoundError",
    "DatadogRateLimitError",
    # Enums
    "MetricType",
    "MonitorStatus",
    "MonitorType",
    "LogStatus",
    "EventPriority",
    "EventAlertType",
    # Metrics
    "MetricPoint",
    "MetricSeries",
    "MetricQueryResult",
    # Logs
    "Log",
    "LogAttributes",
    "LogQueryResult",
    # Events
    "Event",
    "EventQueryResult",
    # Monitors
    "Monitor",
    "MonitorOptions",
    "MonitorThresholds",
    "MonitorState",
    "MonitorSearchResult",
    # Hosts
    "Host",
    "HostMetrics",
    "HostMeta",
    "HostListResult",
    # Dashboards
    "Dashboard",
    "DashboardWidget",
    "DashboardSummary",
    "DashboardListResult",
    # Query builders
    "MetricQuery",
    "LogQuery",
    "MonitorQuery",
    "Aggregation",
    "TimeWindow",
    # Pre-built queries
    "SystemMetrics",
    "ContainerMetrics",
    "KubernetesMetrics",
    "APMMetrics",
    "DatabaseMetrics",
    "CommonLogQueries",
    "MonitorTemplates",
    # Time helpers
    "time_range",
    "last_hour",
    "last_day",
    "last_week",
]
