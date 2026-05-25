"""
AutoSRE Dashboard Module

Provides real-time dashboard functionality including:
- Metrics aggregation
- Event streaming
- WebSocket support for live updates
"""

from autosre.dashboard.metrics import MetricsAggregator, get_metrics_aggregator
from autosre.dashboard.events import EventStream, get_event_stream

__all__ = [
    "MetricsAggregator",
    "get_metrics_aggregator",
    "EventStream",
    "get_event_stream",
]
