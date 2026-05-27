"""
Golden Signals Skill — Core SRE Monitoring.

From the Google SRE book: The Four Golden Signals cover most monitoring needs:
1. LATENCY - Time to service a request (p50, p90, p95, p99, p999)
2. TRAFFIC - Demand on the system (requests per second)
3. ERRORS - Rate of failed requests
4. SATURATION - System resource utilization

This skill:
- Always checks all four signals at investigation kickoff
- Uses histogram_quantile for latency (NEVER avg!)
- Alerts if any golden signal is missing for a service
- Supports both Prometheus and Datadog
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class SignalStatus(str, Enum):
    """Health status for a signal."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    MISSING = "missing"
    ERROR = "error"


@dataclass
class SignalResult:
    """Result for a single golden signal."""
    signal: str
    status: SignalStatus
    value: Optional[float] = None
    unit: str = ""
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    details: dict[str, Any] = field(default_factory=dict)
    query_used: str = ""
    error: Optional[str] = None
    
    def is_healthy(self) -> bool:
        return self.status == SignalStatus.HEALTHY
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "details": self.details,
            "query_used": self.query_used,
            "error": self.error,
        }


@dataclass
class GoldenSignalsResult:
    """Complete golden signals check result."""
    service: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    latency: Optional[SignalResult] = None
    traffic: Optional[SignalResult] = None
    errors: Optional[SignalResult] = None
    saturation: Optional[SignalResult] = None
    
    missing_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def overall_status(self) -> SignalStatus:
        """Get worst status across all signals."""
        statuses = []
        for signal in [self.latency, self.traffic, self.errors, self.saturation]:
            if signal:
                statuses.append(signal.status)
        
        if SignalStatus.CRITICAL in statuses:
            return SignalStatus.CRITICAL
        if SignalStatus.WARNING in statuses:
            return SignalStatus.WARNING
        if SignalStatus.MISSING in statuses:
            return SignalStatus.MISSING
        if SignalStatus.ERROR in statuses:
            return SignalStatus.ERROR
        if not statuses:
            return SignalStatus.MISSING
        return SignalStatus.HEALTHY
    
    def has_missing_signals(self) -> bool:
        """Check if any golden signal is missing."""
        return len(self.missing_signals) > 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status().value,
            "latency": self.latency.to_dict() if self.latency else None,
            "traffic": self.traffic.to_dict() if self.traffic else None,
            "errors": self.errors.to_dict() if self.errors else None,
            "saturation": self.saturation.to_dict() if self.saturation else None,
            "missing_signals": self.missing_signals,
            "warnings": self.warnings,
        }
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Golden Signals for {self.service} @ {self.timestamp.isoformat()}",
            f"Overall Status: {self.overall_status().value.upper()}",
            "",
        ]
        
        if self.latency:
            details = self.latency.details
            lines.append(f"📊 LATENCY: {self.latency.status.value}")
            if details:
                for pct, val in details.items():
                    if isinstance(val, (int, float)):
                        lines.append(f"   {pct}: {val:.3f}s")
        
        if self.traffic:
            lines.append(f"📈 TRAFFIC: {self.traffic.status.value}")
            if self.traffic.value is not None:
                lines.append(f"   Current: {self.traffic.value:.2f} {self.traffic.unit}")
        
        if self.errors:
            lines.append(f"❌ ERRORS: {self.errors.status.value}")
            if self.errors.value is not None:
                lines.append(f"   Rate: {self.errors.value:.2%}")
        
        if self.saturation:
            lines.append(f"⚡ SATURATION: {self.saturation.status.value}")
            if self.saturation.details:
                for resource, util in self.saturation.details.items():
                    if isinstance(util, (int, float)):
                        lines.append(f"   {resource}: {util:.1%}")
        
        if self.missing_signals:
            lines.append("")
            lines.append(f"⚠️ MISSING SIGNALS: {', '.join(self.missing_signals)}")
        
        if self.warnings:
            lines.append("")
            for warning in self.warnings:
                lines.append(f"⚠️ {warning}")
        
        return "\n".join(lines)


class MetricsBackend(ABC):
    """Abstract backend for metrics queries."""
    
    @abstractmethod
    async def query_instant(self, query: str) -> dict[str, Any]:
        """Execute instant query."""
        pass
    
    @abstractmethod
    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> dict[str, Any]:
        """Execute range query."""
        pass


class PrometheusBackend(MetricsBackend):
    """Prometheus/VictoriaMetrics backend."""
    
    def __init__(self, url: str = "http://prometheus:9090", timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.timeout = timeout
    
    async def query_instant(self, query: str) -> dict[str, Any]:
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.url, "/api/v1/query")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    params={"query": query},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> dict[str, Any]:
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.url, "/api/v1/query_range")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    params={
                        "query": query,
                        "start": start.isoformat() + "Z",
                        "end": end.isoformat() + "Z",
                        "step": step,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


class DatadogBackend(MetricsBackend):
    """Datadog backend."""
    
    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
    ):
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self.base_url = f"https://api.{site}"
    
    async def query_instant(self, query: str) -> dict[str, Any]:
        """Query Datadog metrics."""
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=5)
        
        url = f"{self.base_url}/api/v1/query"
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=headers,
                    params={
                        "query": query,
                        "from": int(start.timestamp()),
                        "to": int(now.timestamp()),
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> dict[str, Any]:
        """Query Datadog metrics over range."""
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = f"{self.base_url}/api/v1/query"
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=headers,
                    params={
                        "query": query,
                        "from": int(start.timestamp()),
                        "to": int(end.timestamp()),
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ============================================================================
# Prometheus Query Templates (histogram_quantile, NOT avg!)
# ============================================================================

PROMETHEUS_LATENCY_QUERIES = {
    "p50": 'histogram_quantile(0.50, sum(rate({metric}_bucket{{service="{service}"}}[{window}])) by (le))',
    "p90": 'histogram_quantile(0.90, sum(rate({metric}_bucket{{service="{service}"}}[{window}])) by (le))',
    "p95": 'histogram_quantile(0.95, sum(rate({metric}_bucket{{service="{service}"}}[{window}])) by (le))',
    "p99": 'histogram_quantile(0.99, sum(rate({metric}_bucket{{service="{service}"}}[{window}])) by (le))',
    "p999": 'histogram_quantile(0.999, sum(rate({metric}_bucket{{service="{service}"}}[{window}])) by (le))',
}

PROMETHEUS_TRAFFIC_QUERY = 'sum(rate({metric}{{service="{service}"}}[{window}]))'

PROMETHEUS_ERROR_QUERY = '''
sum(rate({metric}{{service="{service}",status=~"5.."}}[{window}])) 
/ 
sum(rate({metric}{{service="{service}"}}[{window}]))
'''

PROMETHEUS_SATURATION_QUERIES = {
    "cpu": 'sum(rate(container_cpu_usage_seconds_total{{service="{service}"}}[{window}])) / sum(kube_pod_container_resource_limits{{service="{service}",resource="cpu"}})',
    "memory": 'sum(container_memory_usage_bytes{{service="{service}"}}) / sum(kube_pod_container_resource_limits{{service="{service}",resource="memory"}})',
}

# ============================================================================
# Datadog Query Templates
# ============================================================================

DATADOG_LATENCY_QUERIES = {
    "p50": 'percentile:trace.{service}.request.duration{{service:{service}}}',
    "p90": 'p90:trace.{service}.request.duration{{service:{service}}}',
    "p95": 'p95:trace.{service}.request.duration{{service:{service}}}',
    "p99": 'p99:trace.{service}.request.duration{{service:{service}}}',
}

DATADOG_TRAFFIC_QUERY = 'sum:trace.{service}.request.hits{{service:{service}}}.as_rate()'

DATADOG_ERROR_QUERY = 'sum:trace.{service}.request.errors{{service:{service}}}.as_rate() / sum:trace.{service}.request.hits{{service:{service}}}.as_rate()'

DATADOG_SATURATION_QUERIES = {
    "cpu": 'avg:kubernetes.cpu.usage.total{{service:{service}}} / avg:kubernetes.cpu.limits{{service:{service}}}',
    "memory": 'avg:kubernetes.memory.usage{{service:{service}}} / avg:kubernetes.memory.limits{{service:{service}}}',
}


class GoldenSignalsSkill:
    """
    Skill to check all four Golden Signals for a service.
    
    Usage:
        skill = GoldenSignalsSkill(
            backend=PrometheusBackend("http://prometheus:9090"),
        )
        result = await skill.check_all_signals("my-service")
        
        if result.has_missing_signals():
            print(f"WARNING: Missing metrics: {result.missing_signals}")
    """
    
    name = "golden_signals"
    version = "1.0.0"
    description = "Check the Four Golden Signals for a service"
    
    # Default thresholds
    DEFAULT_LATENCY_WARNING_MS = 500
    DEFAULT_LATENCY_CRITICAL_MS = 2000
    DEFAULT_ERROR_RATE_WARNING = 0.01  # 1%
    DEFAULT_ERROR_RATE_CRITICAL = 0.05  # 5%
    DEFAULT_SATURATION_WARNING = 0.70  # 70%
    DEFAULT_SATURATION_CRITICAL = 0.90  # 90%
    
    # Common metric names to try
    LATENCY_METRICS = [
        "http_request_duration_seconds",
        "http_server_request_duration_seconds",
        "request_duration_seconds",
        "http_request_latency_seconds",
    ]
    
    TRAFFIC_METRICS = [
        "http_requests_total",
        "http_server_requests_total",
        "requests_total",
    ]
    
    def __init__(
        self,
        backend: Optional[MetricsBackend] = None,
        prometheus_url: str = "http://prometheus:9090",
        latency_metric: Optional[str] = None,
        traffic_metric: Optional[str] = None,
        window: str = "5m",
        thresholds: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize golden signals skill.
        
        Args:
            backend: Metrics backend (Prometheus or Datadog)
            prometheus_url: Prometheus URL (used if backend not provided)
            latency_metric: Override latency metric name
            traffic_metric: Override traffic metric name
            window: Rate window for queries
            thresholds: Custom thresholds for alerting
        """
        self.backend = backend or PrometheusBackend(prometheus_url)
        self.latency_metric = latency_metric
        self.traffic_metric = traffic_metric
        self.window = window
        self.thresholds = thresholds or {}
        self._is_datadog = isinstance(self.backend, DatadogBackend)
    
    async def check_all_signals(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> GoldenSignalsResult:
        """
        Check all four Golden Signals for a service.
        
        This should be called at the START of every investigation.
        
        Args:
            service: Service name to check
            namespace: Optional Kubernetes namespace
            
        Returns:
            GoldenSignalsResult with all signals
        """
        logger.info(f"[GOLDEN_SIGNALS] Checking all signals for service: {service}")
        
        result = GoldenSignalsResult(service=service)
        
        # Check all signals (could parallelize, but sequential is clearer for debugging)
        result.latency = await self._check_latency(service, namespace)
        result.traffic = await self._check_traffic(service, namespace)
        result.errors = await self._check_errors(service, namespace)
        result.saturation = await self._check_saturation(service, namespace)
        
        # Track missing signals
        if result.latency and result.latency.status == SignalStatus.MISSING:
            result.missing_signals.append("latency")
            result.warnings.append(
                f"No latency histogram metrics found for {service}. "
                "Consider adding http_request_duration_seconds histogram."
            )
        
        if result.traffic and result.traffic.status == SignalStatus.MISSING:
            result.missing_signals.append("traffic")
            result.warnings.append(
                f"No traffic metrics found for {service}. "
                "Consider adding http_requests_total counter."
            )
        
        if result.errors and result.errors.status == SignalStatus.MISSING:
            result.missing_signals.append("errors")
        
        if result.saturation and result.saturation.status == SignalStatus.MISSING:
            result.missing_signals.append("saturation")
            result.warnings.append(
                f"No resource metrics found for {service}. "
                "Ensure Kubernetes metrics are being collected."
            )
        
        logger.info(
            f"[GOLDEN_SIGNALS] Complete: status={result.overall_status().value}, "
            f"missing={result.missing_signals}"
        )
        
        return result
    
    async def _check_latency(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> SignalResult:
        """
        Check latency signal using PERCENTILES (never avg!).
        
        Returns p50, p90, p95, p99, p999.
        """
        if self._is_datadog:
            return await self._check_latency_datadog(service)
        
        # Try each latency metric until one works
        metric = self.latency_metric
        if not metric:
            for m in self.LATENCY_METRICS:
                test_query = PROMETHEUS_LATENCY_QUERIES["p99"].format(
                    metric=m, service=service, window=self.window
                )
                result = await self.backend.query_instant(test_query)
                if self._has_data(result):
                    metric = m
                    break
        
        if not metric:
            return SignalResult(
                signal="latency",
                status=SignalStatus.MISSING,
                error="No histogram latency metrics found",
            )
        
        # Get all percentiles
        percentiles = {}
        queries_used = []
        
        for pct, query_template in PROMETHEUS_LATENCY_QUERIES.items():
            query = query_template.format(
                metric=metric, service=service, window=self.window
            )
            queries_used.append(query)
            
            result = await self.backend.query_instant(query)
            value = self._extract_value(result)
            
            if value is not None:
                percentiles[pct] = value
        
        if not percentiles:
            return SignalResult(
                signal="latency",
                status=SignalStatus.MISSING,
                query_used=queries_used[0] if queries_used else "",
                error="No latency data returned",
            )
        
        # Determine status based on p99
        p99 = percentiles.get("p99", 0)
        warning_threshold = self.thresholds.get(
            "latency_warning_ms", self.DEFAULT_LATENCY_WARNING_MS
        ) / 1000
        critical_threshold = self.thresholds.get(
            "latency_critical_ms", self.DEFAULT_LATENCY_CRITICAL_MS
        ) / 1000
        
        if p99 >= critical_threshold:
            status = SignalStatus.CRITICAL
        elif p99 >= warning_threshold:
            status = SignalStatus.WARNING
        else:
            status = SignalStatus.HEALTHY
        
        return SignalResult(
            signal="latency",
            status=status,
            value=p99,
            unit="seconds",
            threshold_warning=warning_threshold,
            threshold_critical=critical_threshold,
            details=percentiles,
            query_used=queries_used[-1],
        )
    
    async def _check_latency_datadog(self, service: str) -> SignalResult:
        """Check latency using Datadog."""
        percentiles = {}
        
        for pct, query_template in DATADOG_LATENCY_QUERIES.items():
            query = query_template.format(service=service)
            result = await self.backend.query_instant(query)
            
            # Parse Datadog response
            if result.get("series"):
                points = result["series"][0].get("pointlist", [])
                if points:
                    percentiles[pct] = points[-1][1] / 1e9  # ns to seconds
        
        if not percentiles:
            return SignalResult(
                signal="latency",
                status=SignalStatus.MISSING,
                error="No latency data from Datadog",
            )
        
        p99 = percentiles.get("p99", 0)
        warning_threshold = self.thresholds.get(
            "latency_warning_ms", self.DEFAULT_LATENCY_WARNING_MS
        ) / 1000
        critical_threshold = self.thresholds.get(
            "latency_critical_ms", self.DEFAULT_LATENCY_CRITICAL_MS
        ) / 1000
        
        if p99 >= critical_threshold:
            status = SignalStatus.CRITICAL
        elif p99 >= warning_threshold:
            status = SignalStatus.WARNING
        else:
            status = SignalStatus.HEALTHY
        
        return SignalResult(
            signal="latency",
            status=status,
            value=p99,
            unit="seconds",
            details=percentiles,
        )
    
    async def _check_traffic(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> SignalResult:
        """Check traffic signal (requests per second)."""
        if self._is_datadog:
            query = DATADOG_TRAFFIC_QUERY.format(service=service)
        else:
            metric = self.traffic_metric
            if not metric:
                for m in self.TRAFFIC_METRICS:
                    test_query = PROMETHEUS_TRAFFIC_QUERY.format(
                        metric=m, service=service, window=self.window
                    )
                    result = await self.backend.query_instant(test_query)
                    if self._has_data(result):
                        metric = m
                        break
            
            if not metric:
                return SignalResult(
                    signal="traffic",
                    status=SignalStatus.MISSING,
                    error="No traffic metrics found",
                )
            
            query = PROMETHEUS_TRAFFIC_QUERY.format(
                metric=metric, service=service, window=self.window
            )
        
        result = await self.backend.query_instant(query)
        value = self._extract_value(result)
        
        if value is None:
            return SignalResult(
                signal="traffic",
                status=SignalStatus.MISSING,
                query_used=query,
                error="No traffic data returned",
            )
        
        # Traffic doesn't have simple thresholds - anomaly detection would be better
        # For now, just report the value
        return SignalResult(
            signal="traffic",
            status=SignalStatus.HEALTHY,
            value=value,
            unit="req/s",
            query_used=query,
        )
    
    async def _check_errors(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> SignalResult:
        """Check error rate signal."""
        if self._is_datadog:
            query = DATADOG_ERROR_QUERY.format(service=service)
        else:
            metric = self.traffic_metric
            if not metric:
                for m in self.TRAFFIC_METRICS:
                    test_query = PROMETHEUS_TRAFFIC_QUERY.format(
                        metric=m, service=service, window=self.window
                    )
                    result = await self.backend.query_instant(test_query)
                    if self._has_data(result):
                        metric = m
                        break
            
            if not metric:
                return SignalResult(
                    signal="errors",
                    status=SignalStatus.MISSING,
                    error="No traffic metrics for error calculation",
                )
            
            query = PROMETHEUS_ERROR_QUERY.format(
                metric=metric, service=service, window=self.window
            )
        
        result = await self.backend.query_instant(query)
        value = self._extract_value(result)
        
        if value is None:
            # Could be 0 errors (NaN from division)
            return SignalResult(
                signal="errors",
                status=SignalStatus.HEALTHY,
                value=0.0,
                unit="rate",
                query_used=query,
            )
        
        warning_threshold = self.thresholds.get(
            "error_rate_warning", self.DEFAULT_ERROR_RATE_WARNING
        )
        critical_threshold = self.thresholds.get(
            "error_rate_critical", self.DEFAULT_ERROR_RATE_CRITICAL
        )
        
        if value >= critical_threshold:
            status = SignalStatus.CRITICAL
        elif value >= warning_threshold:
            status = SignalStatus.WARNING
        else:
            status = SignalStatus.HEALTHY
        
        return SignalResult(
            signal="errors",
            status=status,
            value=value,
            unit="rate",
            threshold_warning=warning_threshold,
            threshold_critical=critical_threshold,
            query_used=query,
        )
    
    async def _check_saturation(
        self,
        service: str,
        namespace: Optional[str] = None,
    ) -> SignalResult:
        """Check saturation signal (CPU/memory utilization)."""
        if self._is_datadog:
            queries = DATADOG_SATURATION_QUERIES
        else:
            queries = PROMETHEUS_SATURATION_QUERIES
        
        utilization = {}
        
        for resource, query_template in queries.items():
            query = query_template.format(service=service, window=self.window)
            result = await self.backend.query_instant(query)
            value = self._extract_value(result)
            
            if value is not None:
                utilization[resource] = value
        
        if not utilization:
            return SignalResult(
                signal="saturation",
                status=SignalStatus.MISSING,
                error="No resource metrics found",
            )
        
        # Use max utilization for status
        max_util = max(utilization.values())
        
        warning_threshold = self.thresholds.get(
            "saturation_warning", self.DEFAULT_SATURATION_WARNING
        )
        critical_threshold = self.thresholds.get(
            "saturation_critical", self.DEFAULT_SATURATION_CRITICAL
        )
        
        if max_util >= critical_threshold:
            status = SignalStatus.CRITICAL
        elif max_util >= warning_threshold:
            status = SignalStatus.WARNING
        else:
            status = SignalStatus.HEALTHY
        
        return SignalResult(
            signal="saturation",
            status=status,
            value=max_util,
            unit="ratio",
            threshold_warning=warning_threshold,
            threshold_critical=critical_threshold,
            details=utilization,
        )
    
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
        
        # Get value from first result
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


# Factory functions

def create_golden_signals_skill(
    prometheus_url: str = "http://prometheus:9090",
    **kwargs: Any,
) -> GoldenSignalsSkill:
    """Create a Golden Signals skill with Prometheus backend."""
    return GoldenSignalsSkill(
        backend=PrometheusBackend(prometheus_url),
        **kwargs,
    )


def create_datadog_golden_signals_skill(
    api_key: str,
    app_key: str,
    site: str = "datadoghq.com",
    **kwargs: Any,
) -> GoldenSignalsSkill:
    """Create a Golden Signals skill with Datadog backend."""
    return GoldenSignalsSkill(
        backend=DatadogBackend(api_key, app_key, site),
        **kwargs,
    )
