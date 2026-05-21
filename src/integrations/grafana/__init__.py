"""Grafana integration for AutoSRE."""

from .client import (
    GrafanaClient,
    GrafanaConfig,
    GrafanaError,
    GrafanaAuthError,
    GrafanaNotFoundError,
    GrafanaRateLimitError,
)
from .models import (
    # Enums
    DashboardType,
    AlertState,
    AnnotationType,
    # Datasource
    Datasource,
    DatasourceHealth,
    # Dashboard
    Dashboard,
    DashboardMeta,
    DashboardResponse,
    DashboardSearchResult,
    Panel,
    TemplateVariable,
    # Annotation
    Annotation,
    # Alert
    AlertNotification,
    AlertRule,
    # Query
    QueryTarget,
    QueryRequest,
    QueryResult,
    QueryResultFrame,
    QueryResponse,
    # Folder
    Folder,
    # User/Org
    User,
    Organization,
    # Render
    RenderOptions,
)
from .queries import (
    # Time ranges
    GrafanaTimeRange,
    QueryFormat,
    # Query builders
    PrometheusQuery,
    ElasticsearchQuery,
    LokiQuery,
    DashboardQuery,
    # Pre-built queries
    PrometheusQueries,
    LokiQueries,
    # Time helpers
    relative_time,
    time_range_from_duration,
    time_range_absolute,
)

__all__ = [
    # Client
    "GrafanaClient",
    "GrafanaConfig",
    "GrafanaError",
    "GrafanaAuthError",
    "GrafanaNotFoundError",
    "GrafanaRateLimitError",
    # Enums
    "DashboardType",
    "AlertState",
    "AnnotationType",
    # Datasource
    "Datasource",
    "DatasourceHealth",
    # Dashboard
    "Dashboard",
    "DashboardMeta",
    "DashboardResponse",
    "DashboardSearchResult",
    "Panel",
    "TemplateVariable",
    # Annotation
    "Annotation",
    # Alert
    "AlertNotification",
    "AlertRule",
    # Query
    "QueryTarget",
    "QueryRequest",
    "QueryResult",
    "QueryResultFrame",
    "QueryResponse",
    # Folder
    "Folder",
    # User/Org
    "User",
    "Organization",
    # Render
    "RenderOptions",
    # Time ranges
    "GrafanaTimeRange",
    "QueryFormat",
    # Query builders
    "PrometheusQuery",
    "ElasticsearchQuery",
    "LokiQuery",
    "DashboardQuery",
    # Pre-built queries
    "PrometheusQueries",
    "LokiQueries",
    # Time helpers
    "relative_time",
    "time_range_from_duration",
    "time_range_absolute",
]
