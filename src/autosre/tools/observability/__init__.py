"""Observability tools package for AutoSRE.

Provides tools for querying metrics, logs, dashboards, and monitoring systems:
- Prometheus metrics and alerts querying
- Grafana dashboards and annotations
- Datadog metrics, monitors, and incidents
- Log search and analysis (Loki backend)
"""

from .prometheus import PrometheusTool
from .grafana import GrafanaTool
from .datadog import DatadogTool
from .logs import LogsQueryTool

# Backward compatibility alias
PrometheusQueryTool = PrometheusTool

# Register tools with the global registry
from ..registry import get_registry

_registry = get_registry()
_registry.register(PrometheusTool(), category="observability")
_registry.register(GrafanaTool(), category="observability")
_registry.register(DatadogTool(), category="observability")
_registry.register(LogsQueryTool(), category="observability")

__all__ = [
    # Prometheus
    "PrometheusTool",
    "PrometheusQueryTool",  # Backward compatibility alias
    # Grafana
    "GrafanaTool",
    # Datadog
    "DatadogTool",
    # Logs
    "LogsQueryTool",
]
