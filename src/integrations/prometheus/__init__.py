"""Prometheus integration for AutoSRE."""

from .client import (
    PrometheusClient,
    PrometheusConfig,
    PrometheusError,
    PrometheusAuthError,
    PrometheusQueryError,
    PrometheusTimeoutError,
)
from .models import (
    # Enums
    ResultType,
    AlertState,
    TargetHealth,
    RuleType,
    RuleHealth,
    # Query results
    MetricLabels,
    Sample,
    VectorSample,
    RangeSample,
    VectorResult,
    MatrixResult,
    ScalarResult,
    QueryResponse,
    # Alerts
    Alert,
    AlertLabel,
    AlertAnnotation,
    AlertGroup,
    AlertRule,
    AlertsResponse,
    # Rules
    RecordingRule,
    RuleGroup,
    RulesResponse,
    # Targets
    Target,
    DroppedTarget,
    TargetDiscoveredLabels,
    TargetsResponse,
    # Metadata
    MetricMetadata,
    SeriesResult,
    LabelsResponse,
    BuildInfo,
    RuntimeInfo,
    StatusResponse,
)
from .queries import (
    # Query builder
    PromQLBuilder,
    LabelMatcher,
    MatchType,
    AggregationOp,
    BinaryOp,
    metric,
    query,
    # Pre-built queries
    SystemQueries,
    KubernetesQueries,
    HTTPQueries,
    GRPCQueries,
    # Duration helpers
    duration_string,
    parse_duration,
)

__all__ = [
    # Client
    "PrometheusClient",
    "PrometheusConfig",
    "PrometheusError",
    "PrometheusAuthError",
    "PrometheusQueryError",
    "PrometheusTimeoutError",
    # Enums
    "ResultType",
    "AlertState",
    "TargetHealth",
    "RuleType",
    "RuleHealth",
    # Query results
    "MetricLabels",
    "Sample",
    "VectorSample",
    "RangeSample",
    "VectorResult",
    "MatrixResult",
    "ScalarResult",
    "QueryResponse",
    # Alerts
    "Alert",
    "AlertLabel",
    "AlertAnnotation",
    "AlertGroup",
    "AlertRule",
    "AlertsResponse",
    # Rules
    "RecordingRule",
    "RuleGroup",
    "RulesResponse",
    # Targets
    "Target",
    "DroppedTarget",
    "TargetDiscoveredLabels",
    "TargetsResponse",
    # Metadata
    "MetricMetadata",
    "SeriesResult",
    "LabelsResponse",
    "BuildInfo",
    "RuntimeInfo",
    "StatusResponse",
    # Query builder
    "PromQLBuilder",
    "LabelMatcher",
    "MatchType",
    "AggregationOp",
    "BinaryOp",
    "metric",
    "query",
    # Pre-built queries
    "SystemQueries",
    "KubernetesQueries",
    "HTTPQueries",
    "GRPCQueries",
    # Duration helpers
    "duration_string",
    "parse_duration",
]
