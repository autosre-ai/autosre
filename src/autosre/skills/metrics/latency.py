"""
Latency Metrics Skill — Proper Percentile-Based Latency Measurement.

From Google SRE book:
- "Using averages for latency is almost always wrong"
- "The average hides the distribution of response times"
- "p99 tells you what 99% of your users are experiencing"

This skill:
1. NEVER uses avg() for latency queries
2. ALWAYS reports p50, p90, p95, p99, p999
3. Uses histogram_quantile() in Prometheus
4. Flags services missing histogram metrics
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


# Standard percentiles to always report
PERCENTILE_VALUES = {
    "p50": 0.50,   # Median
    "p90": 0.90,   # 90th percentile
    "p95": 0.95,   # 95th percentile
    "p99": 0.99,   # 99th percentile - most important for SLAs
    "p999": 0.999, # 99.9th percentile - tail latency
}


class LatencyStatus(str, Enum):
    """Latency health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    MISSING = "missing"
    ERROR = "error"


@dataclass
class LatencyPercentiles:
    """Latency percentile measurements."""
    p50: Optional[float] = None
    p90: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    p999: Optional[float] = None
    
    def to_dict(self) -> dict[str, Optional[float]]:
        return {
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
            "p999": self.p999,
        }
    
    def summary(self, unit: str = "s") -> str:
        """Human-readable summary."""
        parts = []
        for pct, val in self.to_dict().items():
            if val is not None:
                if unit == "ms":
                    parts.append(f"{pct}={val*1000:.1f}ms")
                else:
                    parts.append(f"{pct}={val:.3f}s")
        return " | ".join(parts) if parts else "No data"


@dataclass
class LatencyResult:
    """Complete latency measurement result."""
    service: str
    status: LatencyStatus
    percentiles: LatencyPercentiles
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Thresholds used
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    
    # Histogram availability
    has_histogram: bool = True
    histogram_metric: Optional[str] = None
    
    # Warnings
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "status": self.status.value,
            "percentiles": self.percentiles.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "has_histogram": self.has_histogram,
            "warnings": self.warnings,
            "error": self.error,
        }
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Latency for {self.service}: {self.status.value.upper()}",
            f"  {self.percentiles.summary()}",
        ]
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")
        return "\n".join(lines)


# Query validation - detect and reject avg() usage

AVG_PATTERNS = [
    r'\bavg\s*\(',
    r'\bavg_over_time\s*\(',
    r'avg\s+by\s*\(',
    r'avg\s+without\s*\(',
]


def validate_latency_query(query: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a latency query doesn't use avg().
    
    Returns:
        (is_valid, error_message)
    """
    query_lower = query.lower()
    
    for pattern in AVG_PATTERNS:
        if re.search(pattern, query_lower):
            return False, (
                f"Query uses avg() for latency. This is almost always wrong! "
                f"Use histogram_quantile() instead. "
                f"Pattern found: {pattern}"
            )
    
    return True, None


def fix_avg_latency_query(query: str, percentile: float = 0.99) -> str:
    """
    Attempt to fix a query that uses avg() for latency.
    
    This is best-effort - complex queries may not convert cleanly.
    """
    # Common pattern: avg(rate(metric_bucket[5m])) -> histogram_quantile
    # This is a simplified conversion
    
    # If already using histogram_quantile, return as-is
    if "histogram_quantile" in query.lower():
        return query
    
    logger.warning(
        f"Attempted to fix avg() query, but automatic conversion is unreliable. "
        f"Please manually rewrite using histogram_quantile(). Query: {query}"
    )
    
    return query


# Prometheus query templates - ALWAYS use histogram_quantile

PROMETHEUS_LATENCY_TEMPLATES = {
    "p50": 'histogram_quantile(0.50, sum(rate({metric}_bucket{{{filters}}}[{window}])) by (le{group_by}))',
    "p90": 'histogram_quantile(0.90, sum(rate({metric}_bucket{{{filters}}}[{window}])) by (le{group_by}))',
    "p95": 'histogram_quantile(0.95, sum(rate({metric}_bucket{{{filters}}}[{window}])) by (le{group_by}))',
    "p99": 'histogram_quantile(0.99, sum(rate({metric}_bucket{{{filters}}}[{window}])) by (le{group_by}))',
    "p999": 'histogram_quantile(0.999, sum(rate({metric}_bucket{{{filters}}}[{window}])) by (le{group_by}))',
}

# Common histogram metric names
HISTOGRAM_METRICS = [
    "http_request_duration_seconds",
    "http_server_request_duration_seconds", 
    "http_server_duration_seconds",
    "request_duration_seconds",
    "request_latency_seconds",
    "grpc_server_handling_seconds",
    "envoy_cluster_upstream_rq_time",
]


class LatencyMetricsSkill:
    """
    Skill for measuring service latency using proper percentiles.
    
    IMPORTANT: This skill NEVER uses avg() for latency.
    
    Usage:
        skill = LatencyMetricsSkill(prometheus_url="http://prometheus:9090")
        result = await skill.get_latency("my-service")
        
        # Always get all percentiles
        print(f"p50: {result.percentiles.p50}")
        print(f"p99: {result.percentiles.p99}")  # Most important for SLAs
        print(f"p999: {result.percentiles.p999}")  # Tail latency
    """
    
    name = "latency_metrics"
    version = "1.0.0"
    description = "Measure service latency using percentiles (never avg)"
    
    # Default thresholds (in seconds)
    DEFAULT_P99_WARNING = 0.5     # 500ms
    DEFAULT_P99_CRITICAL = 2.0   # 2 seconds
    
    def __init__(
        self,
        prometheus_url: str = "http://prometheus:9090",
        histogram_metric: Optional[str] = None,
        window: str = "5m",
        p99_warning: float = 0.5,
        p99_critical: float = 2.0,
    ):
        """
        Initialize latency skill.
        
        Args:
            prometheus_url: Prometheus API URL
            histogram_metric: Override histogram metric name (auto-detected if None)
            window: Rate window for queries
            p99_warning: p99 threshold for warning status (seconds)
            p99_critical: p99 threshold for critical status (seconds)
        """
        self.prometheus_url = prometheus_url.rstrip("/")
        self.histogram_metric = histogram_metric
        self.window = window
        self.p99_warning = p99_warning
        self.p99_critical = p99_critical
    
    async def get_latency(
        self,
        service: str,
        namespace: Optional[str] = None,
        additional_filters: Optional[dict[str, str]] = None,
        group_by: Optional[list[str]] = None,
    ) -> LatencyResult:
        """
        Get latency percentiles for a service.
        
        This method:
        1. Auto-detects histogram metric if not configured
        2. Queries all percentiles (p50, p90, p95, p99, p999)
        3. Returns structured result with status
        
        Args:
            service: Service name to query
            namespace: Kubernetes namespace filter
            additional_filters: Extra label filters
            group_by: Additional labels to group by
            
        Returns:
            LatencyResult with all percentiles
        """
        # Build filters
        filters = [f'service="{service}"']
        if namespace:
            filters.append(f'namespace="{namespace}"')
        if additional_filters:
            for k, v in additional_filters.items():
                filters.append(f'{k}="{v}"')
        filter_str = ",".join(filters)
        
        # Group by clause
        group_by_str = ""
        if group_by:
            group_by_str = "," + ",".join(group_by)
        
        # Detect histogram metric
        metric = self.histogram_metric
        if not metric:
            metric = await self._detect_histogram_metric(service, filter_str)
        
        if not metric:
            return LatencyResult(
                service=service,
                status=LatencyStatus.MISSING,
                percentiles=LatencyPercentiles(),
                has_histogram=False,
                warnings=[
                    f"No histogram latency metrics found for {service}. "
                    f"Service should expose one of: {', '.join(HISTOGRAM_METRICS)}"
                ],
            )
        
        # Query all percentiles
        percentiles = LatencyPercentiles()
        errors = []
        
        for pct_name, template in PROMETHEUS_LATENCY_TEMPLATES.items():
            query = template.format(
                metric=metric,
                filters=filter_str,
                window=self.window,
                group_by=group_by_str,
            )
            
            # Validate query doesn't use avg (should never happen with our templates)
            is_valid, error = validate_latency_query(query)
            if not is_valid:
                logger.error(f"Invalid latency query generated: {error}")
                continue
            
            result = await self._query_prometheus(query)
            value = self._extract_value(result)
            
            setattr(percentiles, pct_name, value)
        
        # Determine status based on p99
        status = LatencyStatus.HEALTHY
        warnings = []
        
        if percentiles.p99 is None:
            status = LatencyStatus.ERROR
            errors.append("Failed to retrieve p99 latency")
        elif percentiles.p99 >= self.p99_critical:
            status = LatencyStatus.CRITICAL
        elif percentiles.p99 >= self.p99_warning:
            status = LatencyStatus.WARNING
        
        # Check for missing percentiles
        for pct_name in ["p50", "p90", "p95", "p99", "p999"]:
            if getattr(percentiles, pct_name) is None:
                warnings.append(f"Missing {pct_name} percentile")
        
        return LatencyResult(
            service=service,
            status=status,
            percentiles=percentiles,
            warning_threshold=self.p99_warning,
            critical_threshold=self.p99_critical,
            has_histogram=True,
            histogram_metric=metric,
            warnings=warnings,
            error="; ".join(errors) if errors else None,
        )
    
    async def check_histogram_availability(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Check if a service has histogram latency metrics.
        
        This helps identify services that need instrumentation fixes.
        
        Returns:
            {
                "has_histogram": bool,
                "metric_name": str or None,
                "recommendation": str
            }
        """
        filters = f'service="{service}"'
        if namespace:
            filters += f',namespace="{namespace}"'
        
        metric = await self._detect_histogram_metric(service, filters)
        
        if metric:
            return {
                "has_histogram": True,
                "metric_name": metric,
                "recommendation": None,
            }
        
        return {
            "has_histogram": False,
            "metric_name": None,
            "recommendation": (
                f"Service {service} is missing histogram latency metrics. "
                f"Add instrumentation to expose one of: {', '.join(HISTOGRAM_METRICS[:3])}. "
                f"Without histograms, we cannot calculate accurate percentiles."
            ),
        }
    
    async def _detect_histogram_metric(
        self,
        service: str,
        filters: str,
    ) -> Optional[str]:
        """Detect which histogram metric exists for a service."""
        for metric in HISTOGRAM_METRICS:
            query = f'{metric}_bucket{{{filters}}}'
            result = await self._query_prometheus(query)
            
            if self._has_data(result):
                return metric
        
        return None
    
    async def _query_prometheus(self, query: str) -> dict[str, Any]:
        """Execute Prometheus query."""
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.prometheus_url, "/api/v1/query")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    params={"query": query},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _has_data(self, result: dict[str, Any]) -> bool:
        """Check if Prometheus result has data."""
        if result.get("status") != "success":
            return False
        data = result.get("data", {})
        results = data.get("result", [])
        return len(results) > 0
    
    def _extract_value(self, result: dict[str, Any]) -> Optional[float]:
        """Extract numeric value from Prometheus result."""
        if result.get("status") != "success":
            return None
        
        data = result.get("data", {})
        results = data.get("result", [])
        
        if not results:
            return None
        
        value = results[0].get("value", [None, None])
        if len(value) >= 2:
            try:
                v = float(value[1])
                if v != v:  # NaN check
                    return None
                return v
            except (ValueError, TypeError):
                return None
        
        return None


def create_latency_skill(
    prometheus_url: str = "http://prometheus:9090",
    **kwargs: Any,
) -> LatencyMetricsSkill:
    """Create a latency metrics skill."""
    return LatencyMetricsSkill(prometheus_url=prometheus_url, **kwargs)


# Utility function to scan existing queries for avg() usage

async def audit_latency_queries(
    queries: list[str],
) -> list[dict[str, Any]]:
    """
    Audit a list of queries for improper avg() usage on latency.
    
    Returns list of violations with recommendations.
    """
    violations = []
    
    latency_keywords = ["latency", "duration", "response_time", "request_time"]
    
    for query in queries:
        # Check if this looks like a latency query
        is_latency = any(kw in query.lower() for kw in latency_keywords)
        
        if is_latency:
            is_valid, error = validate_latency_query(query)
            if not is_valid:
                violations.append({
                    "query": query,
                    "issue": error,
                    "recommendation": (
                        "Replace avg() with histogram_quantile(). "
                        "Example: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))"
                    ),
                })
    
    return violations
