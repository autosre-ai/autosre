"""
AutoSRE V2 Integrations.

This module provides async clients for external services:
- PrometheusClient: Metrics queries and alert rules
- AlertManagerClient: Alert management and silences
- KubernetesClient: Kubernetes operations
- LokiClient: Log queries (LogQL)

All integrations share common patterns:
- Async HTTP with httpx
- Connection pooling
- Automatic retries with exponential backoff
- Consistent error handling
- Health checks
- Mock-friendly design

Example:
    from autosre.integrations import PrometheusClient

    async with PrometheusClient("http://prometheus:9090") as prom:
        result = await prom.query("up{job='api'}")
"""

# Import base classes first
from .base import (
    AuthenticatedIntegration,
    AuthenticationError,
    BaseIntegration,
    ConnectionConfig,
    ConnectionError,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
    RateLimitError,
    RetryConfig,
    ValidationError,
)

# Import from individual modules - use try/except for optional dependencies
__all__ = [
    "BaseIntegration",
    "AuthenticatedIntegration",
    "ConnectionConfig",
    "RetryConfig",
    "HealthCheckResult",
    "HealthStatus",
    "IntegrationError",
    "ConnectionError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
]

try:
    from .prometheus import (
        PrometheusClient,
    )
    __all__.extend(["PrometheusClient"])
except ImportError:
    pass

try:
    from .alertmanager import (
        AlertManagerClient,
        Silence,
        WebhookPayload,
    )
    __all__.extend(["AlertManagerClient", "Silence", "WebhookPayload"])
except ImportError:
    pass

try:
    from .kubernetes import (
        ContainerState,
        ContainerStatus,
        Deployment,
        Event,
        EventType,
        KubernetesClient,
        Node,
        Pod,
        PodPhase,
    )
    __all__.extend([
        "KubernetesClient", "Pod", "PodPhase", "ContainerStatus",
        "ContainerState", "Deployment", "Event", "EventType", "Node"
    ])
except ImportError:
    pass

try:
    from .loki import (
        Direction,
        LogEntry,
        LogStream,
        LokiClient,
        MetricSeries,
        MetricValue,
        QueryResult,
        ResultType,
    )
    __all__.extend([
        "LokiClient", "LogEntry", "LogStream", "QueryResult",
        "ResultType", "Direction", "MetricValue", "MetricSeries"
    ])
except ImportError:
    pass
