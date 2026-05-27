"""
Availability Calculator

Calculates availability based on request success rate, NOT uptime.
This is the correct way to measure availability for modern services.

Key insight: Availability = successful_requests / total_requests
- A service that's "up" but returning 50% errors is 50% available
- Traditional uptime metrics hide this reality
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class EndpointAvailability:
    """Availability metrics for a specific endpoint."""
    endpoint: str
    method: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    availability: float  # 0.0 to 1.0
    availability_percent: float  # 0.0 to 100.0
    
    # Error breakdown
    client_errors: int = 0  # 4xx
    server_errors: int = 0  # 5xx
    timeout_errors: int = 0
    
    # Latency (optional)
    p50_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "availability": self.availability,
            "availability_percent": f"{self.availability_percent:.2f}%",
            "client_errors": self.client_errors,
            "server_errors": self.server_errors,
            "timeout_errors": self.timeout_errors,
            "p50_latency_ms": self.p50_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
        }


@dataclass
class ServiceAvailability:
    """Availability metrics for an entire service."""
    service: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    availability: float  # 0.0 to 1.0
    availability_percent: float  # 0.0 to 100.0
    
    # Breakdown
    endpoints: list[EndpointAvailability] = field(default_factory=list)
    
    # Error distribution
    error_distribution: dict[str, int] = field(default_factory=dict)
    
    # Time window
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    window_duration: Optional[timedelta] = None
    
    # SLO comparison
    slo_target: Optional[float] = None
    slo_met: Optional[bool] = None
    slo_margin: Optional[float] = None  # How much above/below SLO
    
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "service": self.service,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "availability": self.availability,
            "availability_percent": f"{self.availability_percent:.3f}%",
            "error_distribution": self.error_distribution,
            "endpoints": [e.to_dict() for e in self.endpoints],
        }
        
        if self.slo_target:
            result["slo"] = {
                "target": self.slo_target,
                "target_percent": f"{self.slo_target * 100:.3f}%",
                "met": self.slo_met,
                "margin": self.slo_margin,
                "margin_percent": f"{(self.slo_margin or 0) * 100:.4f}%",
            }
        
        if self.window_start and self.window_end:
            result["window"] = {
                "start": self.window_start.isoformat(),
                "end": self.window_end.isoformat(),
                "duration_hours": (
                    self.window_duration.total_seconds() / 3600
                    if self.window_duration else None
                ),
            }
        
        return result
    
    @property
    def worst_endpoints(self) -> list[EndpointAvailability]:
        """Return endpoints sorted by availability (worst first)."""
        return sorted(self.endpoints, key=lambda e: e.availability)[:5]
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        status = "✅ Meeting SLO" if self.slo_met else "❌ Below SLO"
        
        lines = [
            f"Service: {self.service}",
            f"Availability: {self.availability_percent:.3f}%",
            f"Requests: {self.total_requests:,} total, {self.failed_requests:,} failed",
        ]
        
        if self.slo_target:
            lines.append(f"SLO Target: {self.slo_target * 100:.3f}% - {status}")
        
        if self.worst_endpoints:
            lines.append("\nWorst Endpoints:")
            for ep in self.worst_endpoints[:3]:
                lines.append(f"  - {ep.method} {ep.endpoint}: {ep.availability_percent:.2f}%")
        
        return "\n".join(lines)


class AvailabilityCalculator:
    """
    Calculates availability from metrics.
    
    Availability is defined as: successful_requests / total_requests
    
    This differs from "uptime" which only measures if a service is reachable.
    A service can be "up" but have 50% availability if half its requests fail.
    """
    
    # Prometheus queries
    QUERIES = {
        # Total requests by service
        "total_requests": 'sum(increase(http_requests_total{{service="{service}"}}[{window}]))',
        
        # Successful requests (2xx)
        "successful_requests": 'sum(increase(http_requests_total{{service="{service}",status=~"2.."}}[{window}]))',
        
        # Failed requests (5xx - server errors)
        "failed_requests": 'sum(increase(http_requests_total{{service="{service}",status=~"5.."}}[{window}]))',
        
        # By endpoint
        "requests_by_endpoint": 'sum by (endpoint, method) (increase(http_requests_total{{service="{service}"}}[{window}]))',
        
        # Error breakdown
        "errors_by_code": 'sum by (status) (increase(http_requests_total{{service="{service}",status!~"2.."}}[{window}]))',
        
        # Latency percentiles
        "p50_latency": 'histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket{{service="{service}"}}[{window}])))',
        "p99_latency": 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{{service="{service}"}}[{window}])))',
    }
    
    def __init__(self, prometheus_client: Any = None):
        """
        Initialize calculator.
        
        Args:
            prometheus_client: Prometheus client for querying metrics
        """
        self.prometheus = prometheus_client
    
    def calculate(
        self,
        service: str,
        total_requests: int,
        successful_requests: int,
        failed_requests: Optional[int] = None,
        slo_target: Optional[float] = None,
        endpoint_data: Optional[list[dict]] = None,
    ) -> ServiceAvailability:
        """
        Calculate service availability from request counts.
        
        Args:
            service: Service name
            total_requests: Total requests in window
            successful_requests: Successful requests (2xx)
            failed_requests: Failed requests (5xx), calculated if not provided
            slo_target: SLO target for comparison
            endpoint_data: Optional per-endpoint breakdown
        
        Returns:
            ServiceAvailability with calculated metrics
        """
        if total_requests == 0:
            availability = 1.0  # No requests = 100% available (no failures)
        else:
            availability = successful_requests / total_requests
        
        if failed_requests is None:
            failed_requests = total_requests - successful_requests
        
        # SLO comparison
        slo_met = None
        slo_margin = None
        if slo_target is not None:
            slo_met = availability >= slo_target
            slo_margin = availability - slo_target
        
        # Process endpoint data
        endpoints = []
        if endpoint_data:
            for ep in endpoint_data:
                ep_total = ep.get("total", 0)
                ep_success = ep.get("successful", 0)
                ep_failed = ep.get("failed", ep_total - ep_success)
                
                if ep_total > 0:
                    ep_availability = ep_success / ep_total
                else:
                    ep_availability = 1.0
                
                endpoints.append(EndpointAvailability(
                    endpoint=ep.get("endpoint", "unknown"),
                    method=ep.get("method", "GET"),
                    total_requests=ep_total,
                    successful_requests=ep_success,
                    failed_requests=ep_failed,
                    availability=ep_availability,
                    availability_percent=ep_availability * 100,
                    client_errors=ep.get("client_errors", 0),
                    server_errors=ep.get("server_errors", 0),
                    timeout_errors=ep.get("timeout_errors", 0),
                    p50_latency_ms=ep.get("p50_latency_ms"),
                    p99_latency_ms=ep.get("p99_latency_ms"),
                ))
        
        return ServiceAvailability(
            service=service,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            availability=availability,
            availability_percent=availability * 100,
            endpoints=endpoints,
            slo_target=slo_target,
            slo_met=slo_met,
            slo_margin=slo_margin,
        )
    
    async def calculate_from_prometheus(
        self,
        service: str,
        window: str = "1h",
        slo_target: Optional[float] = None,
        include_endpoints: bool = True,
    ) -> ServiceAvailability:
        """
        Calculate availability from Prometheus metrics.
        
        Args:
            service: Service name
            window: Prometheus time window
            slo_target: SLO target for comparison
            include_endpoints: Whether to include per-endpoint breakdown
        """
        if not self.prometheus:
            raise RuntimeError("Prometheus client not configured")
        
        # Query total and successful requests
        total_query = self.QUERIES["total_requests"].format(
            service=service, window=window
        )
        success_query = self.QUERIES["successful_requests"].format(
            service=service, window=window
        )
        failed_query = self.QUERIES["failed_requests"].format(
            service=service, window=window
        )
        
        total_result = await self.prometheus.query(total_query)
        success_result = await self.prometheus.query(success_query)
        failed_result = await self.prometheus.query(failed_query)
        
        total_requests = int(self._extract_value(total_result, 0))
        successful_requests = int(self._extract_value(success_result, 0))
        failed_requests = int(self._extract_value(failed_result, 0))
        
        # Query endpoint breakdown if requested
        endpoint_data = None
        if include_endpoints:
            endpoint_data = await self._query_endpoints(service, window)
        
        result = self.calculate(
            service=service,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            slo_target=slo_target,
            endpoint_data=endpoint_data,
        )
        
        # Add window info
        now = datetime.now(timezone.utc)
        window_duration = self._parse_window(window)
        result.window_end = now
        result.window_start = now - window_duration
        result.window_duration = window_duration
        
        return result
    
    async def _query_endpoints(
        self, service: str, window: str
    ) -> list[dict]:
        """Query per-endpoint metrics."""
        query = self.QUERIES["requests_by_endpoint"].format(
            service=service, window=window
        )
        result = await self.prometheus.query(query)
        
        endpoint_data = []
        try:
            if isinstance(result, dict) and "data" in result:
                for item in result["data"].get("result", []):
                    metric = item.get("metric", {})
                    value = float(item.get("value", [0, 0])[1])
                    
                    endpoint_data.append({
                        "endpoint": metric.get("endpoint", "unknown"),
                        "method": metric.get("method", "GET"),
                        "total": int(value),
                        # Would need additional queries for success/failed breakdown
                    })
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse endpoint data: {e}")
        
        return endpoint_data
    
    def get_prometheus_queries(self, service: str, window: str = "1h") -> dict[str, str]:
        """Get Prometheus queries for a service."""
        return {
            name: query.format(service=service, window=window)
            for name, query in self.QUERIES.items()
        }
    
    def _parse_window(self, window: str) -> timedelta:
        """Parse Prometheus window string to timedelta."""
        if window.endswith("d"):
            return timedelta(days=int(window[:-1]))
        elif window.endswith("h"):
            return timedelta(hours=int(window[:-1]))
        elif window.endswith("m"):
            return timedelta(minutes=int(window[:-1]))
        else:
            return timedelta(hours=1)
    
    def _extract_value(
        self, result: Any, default: Any = None
    ) -> float | None:
        """Extract scalar value from Prometheus result."""
        try:
            if isinstance(result, dict):
                if "data" in result and "result" in result["data"]:
                    data = result["data"]["result"]
                    if data and len(data) > 0:
                        return float(data[0]["value"][1])
            elif isinstance(result, (int, float)):
                return float(result)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        return default


class AvailabilityTracker:
    """
    Tracks availability over time for trend analysis.
    
    Useful for:
    - Detecting degradation trends
    - Historical comparison
    - SLO compliance reporting
    """
    
    def __init__(self):
        self._history: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        self._max_history = 1000  # Per service
    
    def record(self, service: str, availability: float) -> None:
        """Record an availability measurement."""
        history = self._history[service]
        history.append((datetime.now(timezone.utc), availability))
        
        # Trim old entries
        if len(history) > self._max_history:
            self._history[service] = history[-self._max_history:]
    
    def get_trend(
        self, service: str, hours: int = 24
    ) -> dict[str, Any]:
        """
        Get availability trend for a service.
        
        Returns average, min, max, and trend direction.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        history = [
            (ts, val) for ts, val in self._history.get(service, [])
            if ts >= cutoff
        ]
        
        if not history:
            return {"service": service, "data_points": 0}
        
        values = [val for _, val in history]
        
        # Calculate trend (simple linear regression slope)
        n = len(values)
        if n >= 2:
            # Normalize time to 0..1 range
            x_mean = (n - 1) / 2
            y_mean = sum(values) / n
            
            numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            trend = "improving" if slope > 0.001 else "degrading" if slope < -0.001 else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "service": service,
            "data_points": n,
            "average": sum(values) / n,
            "min": min(values),
            "max": max(values),
            "current": values[-1],
            "trend": trend,
            "hours": hours,
        }
