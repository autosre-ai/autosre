"""
Real-time Metrics Aggregation

Provides aggregated metrics for the dashboard including:
- Investigation statistics
- System health metrics
- Performance metrics
- Resource utilization
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InvestigationMetrics:
    """Metrics about investigations."""
    active_count: int = 0
    completed_today: int = 0
    completed_week: int = 0
    avg_duration_seconds: float = 0.0
    success_rate: float = 0.0
    by_status: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System health metrics."""
    uptime_seconds: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    active_connections: int = 0
    pending_approvals: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics."""
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    requests_per_minute: float = 0.0
    error_rate: float = 0.0


@dataclass
class IntegrationMetrics:
    """Integration health metrics."""
    prometheus: dict[str, Any] = field(default_factory=dict)
    kubernetes: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    slack: dict[str, Any] = field(default_factory=dict)
    pagerduty: dict[str, Any] = field(default_factory=dict)


class MetricsAggregator:
    """
    Aggregates metrics from various sources for dashboard display.
    
    Features:
    - Periodic collection from multiple sources
    - Caching to reduce load
    - Historical data tracking
    - Real-time updates via WebSocket
    """

    def __init__(self, cache_ttl_seconds: int = 5):
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, Any] = {}
        self._cache_time: float = 0
        self._start_time = time.time()
        self._response_times: list[float] = []
        self._max_response_times = 1000
        self._lock = asyncio.Lock()
        
        # Metric counters
        self._requests_count = 0
        self._errors_count = 0
        self._last_minute_requests = 0
        self._last_minute_time = time.time()

    async def get_current_metrics(self) -> dict[str, Any]:
        """
        Get current aggregated metrics.
        
        Returns cached data if still valid, otherwise refreshes.
        """
        async with self._lock:
            now = time.time()
            if now - self._cache_time < self._cache_ttl and self._cache:
                return self._cache
            
            metrics = await self._collect_metrics()
            self._cache = metrics
            self._cache_time = now
            return metrics

    async def _collect_metrics(self) -> dict[str, Any]:
        """Collect metrics from all sources."""
        investigation_metrics = await self._get_investigation_metrics()
        system_metrics = await self._get_system_metrics()
        performance_metrics = await self._get_performance_metrics()
        integration_metrics = await self._get_integration_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "investigations": {
                "active": investigation_metrics.active_count,
                "completed_today": investigation_metrics.completed_today,
                "completed_week": investigation_metrics.completed_week,
                "avg_duration_seconds": investigation_metrics.avg_duration_seconds,
                "success_rate": investigation_metrics.success_rate,
                "by_status": investigation_metrics.by_status,
                "by_severity": investigation_metrics.by_severity,
            },
            "system": {
                "uptime_seconds": system_metrics.uptime_seconds,
                "memory_mb": system_metrics.memory_mb,
                "cpu_percent": system_metrics.cpu_percent,
                "active_connections": system_metrics.active_connections,
                "pending_approvals": system_metrics.pending_approvals,
            },
            "performance": {
                "avg_response_time_ms": performance_metrics.avg_response_time_ms,
                "p95_response_time_ms": performance_metrics.p95_response_time_ms,
                "p99_response_time_ms": performance_metrics.p99_response_time_ms,
                "requests_per_minute": performance_metrics.requests_per_minute,
                "error_rate": performance_metrics.error_rate,
            },
            "integrations": {
                "prometheus": integration_metrics.prometheus,
                "kubernetes": integration_metrics.kubernetes,
                "llm": integration_metrics.llm,
                "slack": integration_metrics.slack,
                "pagerduty": integration_metrics.pagerduty,
            },
        }

    async def _get_investigation_metrics(self) -> InvestigationMetrics:
        """Get investigation-related metrics."""
        metrics = InvestigationMetrics()
        
        try:
            from autosre.streaming import get_stream_manager
            stream_manager = get_stream_manager()
            active = await stream_manager.list_active()
            metrics.active_count = len(active)
        except Exception as e:
            logger.debug(f"Could not get investigation metrics: {e}")
        
        return metrics

    async def _get_system_metrics(self) -> SystemMetrics:
        """Get system health metrics."""
        metrics = SystemMetrics()
        metrics.uptime_seconds = time.time() - self._start_time
        
        try:
            import psutil
            process = psutil.Process()
            metrics.memory_mb = process.memory_info().rss / (1024 * 1024)
            metrics.cpu_percent = process.cpu_percent()
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            logger.debug(f"Could not get system metrics: {e}")
        
        try:
            from autosre.api.websocket import get_connection_manager
            manager = get_connection_manager()
            metrics.active_connections = manager.active_connections
        except Exception:
            pass
        
        return metrics

    async def _get_performance_metrics(self) -> PerformanceMetrics:
        """Get performance metrics."""
        metrics = PerformanceMetrics()
        
        if self._response_times:
            sorted_times = sorted(self._response_times)
            metrics.avg_response_time_ms = sum(sorted_times) / len(sorted_times)
            
            p95_idx = int(len(sorted_times) * 0.95)
            p99_idx = int(len(sorted_times) * 0.99)
            metrics.p95_response_time_ms = sorted_times[min(p95_idx, len(sorted_times) - 1)]
            metrics.p99_response_time_ms = sorted_times[min(p99_idx, len(sorted_times) - 1)]
        
        # Calculate requests per minute
        now = time.time()
        elapsed = now - self._last_minute_time
        if elapsed > 0:
            metrics.requests_per_minute = (self._requests_count - self._last_minute_requests) * 60 / elapsed
        
        # Calculate error rate
        if self._requests_count > 0:
            metrics.error_rate = self._errors_count / self._requests_count
        
        return metrics

    async def _get_integration_metrics(self) -> IntegrationMetrics:
        """Get integration health metrics."""
        metrics = IntegrationMetrics()
        
        # Check integrations asynchronously
        async def check_integration(name: str, checker_func) -> tuple[str, dict]:
            try:
                result = await asyncio.wait_for(checker_func(), timeout=5.0)
                return name, {"status": "connected", **result}
            except asyncio.TimeoutError:
                return name, {"status": "timeout"}
            except Exception as e:
                return name, {"status": "error", "error": str(e)}
        
        # We'll check integrations in parallel for speed
        # For now, return default status
        metrics.prometheus = {"status": "unknown"}
        metrics.kubernetes = {"status": "unknown"}
        metrics.llm = {"status": "unknown"}
        metrics.slack = {"status": "unknown"}
        metrics.pagerduty = {"status": "unknown"}
        
        return metrics

    def record_request(self, response_time_ms: float, is_error: bool = False):
        """Record a request for metrics."""
        self._requests_count += 1
        if is_error:
            self._errors_count += 1
        
        self._response_times.append(response_time_ms)
        if len(self._response_times) > self._max_response_times:
            self._response_times = self._response_times[-self._max_response_times:]

    async def get_historical_metrics(
        self,
        metric_name: str,
        duration: timedelta = timedelta(hours=1),
        resolution: timedelta = timedelta(minutes=1),
    ) -> list[dict[str, Any]]:
        """
        Get historical metrics data points.
        
        Args:
            metric_name: Name of the metric to retrieve
            duration: How far back to look
            resolution: Time resolution for data points
            
        Returns:
            List of data points with timestamp and value
        """
        # This would typically query a time-series database
        # For now, return empty list
        return []


# Global metrics aggregator instance
_metrics_aggregator: MetricsAggregator | None = None


def get_metrics_aggregator() -> MetricsAggregator:
    """Get or create the global metrics aggregator."""
    global _metrics_aggregator
    if _metrics_aggregator is None:
        _metrics_aggregator = MetricsAggregator()
    return _metrics_aggregator
