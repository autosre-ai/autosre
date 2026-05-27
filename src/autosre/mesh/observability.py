"""
Service Mesh Observability

Provides unified observability for service mesh:
- Service metrics (latency, success rate, throughput)
- Distributed tracing integration
- Service topology discovery
- Health checking and SLO compliance
- Golden signals monitoring
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class HealthCheckType(str, Enum):
    """Type of health check."""
    
    HTTP = "http"
    TCP = "tcp"
    GRPC = "grpc"
    EXEC = "exec"


class AlertSeverity(str, Enum):
    """Severity level for mesh alerts."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories of errors."""
    
    CLIENT_ERROR = "client_error"      # 4xx
    SERVER_ERROR = "server_error"      # 5xx
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER = "circuit_breaker"
    CONNECTION_ERROR = "connection_error"
    TLS_ERROR = "tls_error"
    RATE_LIMITED = "rate_limited"


# =============================================================================
# Configuration
# =============================================================================


class MeshObserverConfig(BaseModel):
    """Configuration for MeshObserver."""
    
    mesh_type: str = Field(default="istio", description="Mesh type: istio, linkerd")
    namespace: str = Field(default="default", description="Default namespace")
    
    # Metrics
    prometheus_url: Optional[str] = Field(default=None, description="Prometheus URL")
    metrics_interval_seconds: int = Field(default=30, description="Metrics scrape interval")
    
    # Tracing
    jaeger_url: Optional[str] = Field(default=None, description="Jaeger URL")
    zipkin_url: Optional[str] = Field(default=None, description="Zipkin URL")
    
    # Visualization
    kiali_url: Optional[str] = Field(default=None, description="Kiali URL (Istio)")
    grafana_url: Optional[str] = Field(default=None, description="Grafana URL")


# =============================================================================
# Metrics Models
# =============================================================================


@dataclass
class LatencyPercentile:
    """Latency at a specific percentile."""
    
    percentile: float  # e.g., 50, 90, 95, 99
    value_ms: float
    
    @property
    def label(self) -> str:
        return f"p{int(self.percentile)}"


@dataclass
class LatencyHistogram:
    """Latency distribution histogram."""
    
    p50: float
    p90: float
    p95: float
    p99: float
    p999: float
    mean: float
    min: float
    max: float
    
    @property
    def percentiles(self) -> list[LatencyPercentile]:
        """Get all percentiles as list."""
        return [
            LatencyPercentile(50, self.p50),
            LatencyPercentile(90, self.p90),
            LatencyPercentile(95, self.p95),
            LatencyPercentile(99, self.p99),
            LatencyPercentile(99.9, self.p999),
        ]


@dataclass
class LatencyMetrics:
    """Latency metrics for a service."""
    
    histogram: LatencyHistogram
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_seconds: int = 60


@dataclass
class ErrorMetrics:
    """Error metrics for a service."""
    
    total_errors: int
    error_rate: float  # 0.0 to 1.0
    
    # By category
    client_errors: int = 0
    server_errors: int = 0
    timeouts: int = 0
    connection_errors: int = 0
    
    # By status code
    errors_by_code: dict[int, int] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass 
class ErrorRateMetric:
    """Error rate metric over time."""
    
    service_name: str
    namespace: str
    error_rate: float
    category: ErrorCategory
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThroughputMetrics:
    """Throughput metrics for a service."""
    
    requests_per_second: float
    bytes_in_per_second: float
    bytes_out_per_second: float
    active_connections: int
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RequestMetrics:
    """Aggregated request metrics."""
    
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Breakdown
    by_method: dict[str, int] = field(default_factory=dict)
    by_path: dict[str, int] = field(default_factory=dict)
    by_status_code: dict[int, int] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ServiceMetrics:
    """Complete metrics for a service."""
    
    service_name: str
    namespace: str
    
    # Core metrics
    success_rate: float
    error_rate: float
    requests_per_second: float
    
    # Detailed metrics
    latency: LatencyMetrics
    errors: ErrorMetrics
    throughput: ThroughputMetrics
    requests: RequestMetrics
    
    # Metadata
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_seconds: int = 60


# =============================================================================
# Golden Signals
# =============================================================================


@dataclass
class GoldenSignals:
    """
    The four golden signals of monitoring.
    
    - Latency: Time to service a request
    - Traffic: Demand on the system
    - Errors: Rate of failed requests
    - Saturation: How full the system is
    """
    
    service_name: str
    namespace: str
    
    # Latency
    latency_p50_ms: float
    latency_p99_ms: float
    
    # Traffic
    requests_per_second: float
    
    # Errors
    error_rate: float
    
    # Saturation
    cpu_utilization: float  # 0.0 to 1.0
    memory_utilization: float
    connection_pool_utilization: float
    
    # Fields with defaults
    latency_trend: str = "stable"  # increasing, decreasing, stable
    traffic_trend: str = "stable"
    error_trend: str = "stable"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_healthy(
        self,
        latency_threshold_ms: float = 500.0,
        error_threshold: float = 0.01,
        saturation_threshold: float = 0.8,
    ) -> bool:
        """Check if signals indicate healthy service."""
        return (
            self.latency_p99_ms <= latency_threshold_ms
            and self.error_rate <= error_threshold
            and self.cpu_utilization <= saturation_threshold
            and self.memory_utilization <= saturation_threshold
        )


# =============================================================================
# SLO Compliance
# =============================================================================


@dataclass
class SLOCompliance:
    """SLO compliance tracking."""
    
    service_name: str
    namespace: str
    slo_name: str
    
    # Target
    target_percentage: float  # e.g., 99.9
    
    # Current
    current_percentage: float
    error_budget_remaining: float  # as percentage
    error_budget_consumed: float
    
    # Burn rate
    burn_rate: float  # Current consumption rate
    burn_rate_1h: float
    burn_rate_6h: float
    burn_rate_24h: float
    
    # Compliance
    is_compliant: bool
    time_until_budget_exhausted: Optional[timedelta] = None
    
    # Window
    window_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_end: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service": self.service_name,
            "namespace": self.namespace,
            "slo_name": self.slo_name,
            "target": f"{self.target_percentage}%",
            "current": f"{self.current_percentage:.3f}%",
            "error_budget_remaining": f"{self.error_budget_remaining:.2f}%",
            "is_compliant": self.is_compliant,
            "burn_rate": self.burn_rate,
        }


# =============================================================================
# Tracing
# =============================================================================


@dataclass
class TraceContext:
    """Trace context for distributed tracing."""
    
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    
    # Baggage
    baggage: dict[str, str] = field(default_factory=dict)


@dataclass
class TraceSpan:
    """A single span in a distributed trace."""
    
    span_id: str
    trace_id: str
    operation_name: str
    service_name: str
    
    # Timing
    start_time: datetime
    end_time: datetime
    duration_ms: float
    
    # Hierarchy
    parent_span_id: Optional[str] = None
    
    # Metadata
    tags: dict[str, str] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    
    # Status
    status_code: str = "OK"  # OK, ERROR
    error: Optional[str] = None


@dataclass
class RequestTrace:
    """Complete trace of a request across services."""
    
    trace_id: str
    root_service: str
    
    # Spans
    spans: list[TraceSpan] = field(default_factory=list)
    
    # Aggregates
    total_duration_ms: float = 0.0
    service_count: int = 0
    span_count: int = 0
    
    # Status
    has_errors: bool = False
    error_services: list[str] = field(default_factory=list)
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def get_critical_path(self) -> list[TraceSpan]:
        """Get the critical path (longest chain) of spans."""
        # Simple implementation - in production would use proper graph analysis
        sorted_spans = sorted(self.spans, key=lambda s: s.duration_ms, reverse=True)
        return sorted_spans[:5]  # Top 5 longest spans


# =============================================================================
# Service Topology
# =============================================================================


@dataclass
class ServiceNode:
    """A node in the service topology graph."""
    
    name: str
    namespace: str
    
    # Type
    service_type: str = "kubernetes"  # kubernetes, external, database
    protocol: str = "HTTP"
    
    # Metrics
    requests_per_second: float = 0.0
    success_rate: float = 0.0
    latency_p99_ms: float = 0.0
    
    # Status
    is_healthy: bool = True
    is_meshed: bool = True
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceEdge:
    """An edge between services in the topology."""
    
    source: str
    destination: str
    source_namespace: str = "default"
    destination_namespace: str = "default"
    
    # Metrics
    requests_per_second: float = 0.0
    success_rate: float = 0.0
    latency_p99_ms: float = 0.0
    
    # Protocol
    protocol: str = "HTTP"
    
    # Status
    is_healthy: bool = True


@dataclass
class ServiceTopology:
    """Service mesh topology graph."""
    
    nodes: list[ServiceNode] = field(default_factory=list)
    edges: list[ServiceEdge] = field(default_factory=list)
    
    # Metadata
    namespace: Optional[str] = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_upstream(self, service_name: str) -> list[str]:
        """Get services that call this service."""
        return [
            e.source for e in self.edges
            if e.destination == service_name
        ]
    
    def get_downstream(self, service_name: str) -> list[str]:
        """Get services this service calls."""
        return [
            e.destination for e in self.edges
            if e.source == service_name
        ]


@dataclass
class TopologySnapshot:
    """Snapshot of service topology at a point in time."""
    
    id: str
    topology: ServiceTopology
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""


# =============================================================================
# Health Checking
# =============================================================================


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    
    healthy: bool
    check_type: HealthCheckType
    
    # Details
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    message: str = ""
    
    # Timing
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Metadata
    endpoint: str = ""


@dataclass
class HealthCheck:
    """Health check configuration and status."""
    
    service_name: str
    namespace: str
    check_type: HealthCheckType
    
    # Configuration
    endpoint: str = "/health"
    interval_seconds: int = 30
    timeout_seconds: int = 5
    success_threshold: int = 1
    failure_threshold: int = 3
    
    # Status
    current_status: str = "unknown"  # healthy, unhealthy, unknown
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    
    # History
    last_check: Optional[HealthCheckResult] = None
    history: list[HealthCheckResult] = field(default_factory=list)


# =============================================================================
# Alerts
# =============================================================================


@dataclass
class AlertCondition:
    """Condition that triggers an alert."""
    
    metric: str
    operator: str  # gt, lt, eq, gte, lte
    threshold: float
    duration_seconds: int = 60


@dataclass
class MeshAlert:
    """Alert from the service mesh."""
    
    id: str
    name: str
    severity: AlertSeverity
    
    # Target
    service_name: str
    namespace: str
    
    # Condition
    condition: AlertCondition
    current_value: float
    
    # Status
    firing: bool
    started_at: datetime
    resolved_at: Optional[datetime] = None
    
    # Details
    message: str = ""
    runbook_url: Optional[str] = None
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Mesh Observer
# =============================================================================


class MeshObserver:
    """
    Unified observability for service mesh.
    
    Provides metrics collection, tracing, topology discovery,
    and health monitoring across Istio and Linkerd meshes.
    
    Usage:
        observer = MeshObserver(config=MeshObserverConfig(
            prometheus_url="http://prometheus:9090",
            jaeger_url="http://jaeger:16686",
        ))
        await observer.connect()
        
        # Get service metrics
        metrics = await observer.get_service_metrics("my-service", "production")
        
        # Get golden signals
        signals = await observer.get_golden_signals("my-service", "production")
        
        # Get service topology
        topology = await observer.get_topology(namespace="production")
    """
    
    def __init__(self, config: Optional[MeshObserverConfig] = None):
        """Initialize MeshObserver."""
        self.config = config or MeshObserverConfig()
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to observability backends."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect from backends."""
        self._connected = False
    
    # -------------------------------------------------------------------------
    # Service Metrics
    # -------------------------------------------------------------------------
    
    async def get_service_metrics(
        self,
        service_name: str,
        namespace: str,
        window_seconds: int = 60,
    ) -> ServiceMetrics:
        """
        Get comprehensive metrics for a service.
        
        Args:
            service_name: Service name
            namespace: Namespace
            window_seconds: Time window for metrics
        
        Returns:
            ServiceMetrics with latency, errors, throughput, etc.
        """
        # In production: query Prometheus for Istio/Linkerd metrics
        latency = LatencyMetrics(
            histogram=LatencyHistogram(
                p50=50.0,
                p90=100.0,
                p95=150.0,
                p99=200.0,
                p999=500.0,
                mean=75.0,
                min=10.0,
                max=1000.0,
            ),
            window_seconds=window_seconds,
        )
        
        errors = ErrorMetrics(
            total_errors=10,
            error_rate=0.01,
            client_errors=3,
            server_errors=7,
        )
        
        throughput = ThroughputMetrics(
            requests_per_second=100.0,
            bytes_in_per_second=50000.0,
            bytes_out_per_second=100000.0,
            active_connections=50,
        )
        
        requests = RequestMetrics(
            total_requests=6000,
            successful_requests=5940,
            failed_requests=60,
        )
        
        return ServiceMetrics(
            service_name=service_name,
            namespace=namespace,
            success_rate=0.99,
            error_rate=0.01,
            requests_per_second=100.0,
            latency=latency,
            errors=errors,
            throughput=throughput,
            requests=requests,
            window_seconds=window_seconds,
        )
    
    async def get_latency_histogram(
        self,
        service_name: str,
        namespace: str,
        window_seconds: int = 60,
    ) -> LatencyHistogram:
        """Get latency histogram for a service."""
        metrics = await self.get_service_metrics(
            service_name, namespace, window_seconds
        )
        return metrics.latency.histogram
    
    async def get_error_rate(
        self,
        service_name: str,
        namespace: str,
        window_seconds: int = 60,
    ) -> float:
        """Get error rate for a service."""
        metrics = await self.get_service_metrics(
            service_name, namespace, window_seconds
        )
        return metrics.error_rate
    
    async def get_success_rate(
        self,
        service_name: str,
        namespace: str,
        window_seconds: int = 60,
    ) -> float:
        """Get success rate for a service."""
        metrics = await self.get_service_metrics(
            service_name, namespace, window_seconds
        )
        return metrics.success_rate
    
    # -------------------------------------------------------------------------
    # Golden Signals
    # -------------------------------------------------------------------------
    
    async def get_golden_signals(
        self,
        service_name: str,
        namespace: str,
    ) -> GoldenSignals:
        """
        Get the four golden signals for a service.
        
        Returns:
            GoldenSignals with latency, traffic, errors, saturation
        """
        metrics = await self.get_service_metrics(service_name, namespace)
        
        return GoldenSignals(
            service_name=service_name,
            namespace=namespace,
            latency_p50_ms=metrics.latency.histogram.p50,
            latency_p99_ms=metrics.latency.histogram.p99,
            requests_per_second=metrics.throughput.requests_per_second,
            error_rate=metrics.error_rate,
            cpu_utilization=0.5,  # Would come from pod metrics
            memory_utilization=0.6,
            connection_pool_utilization=0.3,
        )
    
    # -------------------------------------------------------------------------
    # SLO Compliance
    # -------------------------------------------------------------------------
    
    async def get_slo_compliance(
        self,
        service_name: str,
        namespace: str,
        slo_name: str,
        target_percentage: float = 99.9,
        window_days: int = 30,
    ) -> SLOCompliance:
        """
        Get SLO compliance for a service.
        
        Args:
            service_name: Service name
            namespace: Namespace
            slo_name: Name of the SLO (e.g., "availability", "latency")
            target_percentage: Target SLO percentage
            window_days: Rolling window in days
        
        Returns:
            SLOCompliance with error budget and burn rate
        """
        # In production: compute from historical metrics
        error_budget = 100.0 - target_percentage  # e.g., 0.1% for 99.9%
        current = 99.85
        consumed = ((target_percentage - current) / error_budget) * 100
        
        return SLOCompliance(
            service_name=service_name,
            namespace=namespace,
            slo_name=slo_name,
            target_percentage=target_percentage,
            current_percentage=current,
            error_budget_remaining=100 - consumed,
            error_budget_consumed=consumed,
            burn_rate=1.2,
            burn_rate_1h=1.5,
            burn_rate_6h=1.3,
            burn_rate_24h=1.2,
            is_compliant=current >= target_percentage,
        )
    
    # -------------------------------------------------------------------------
    # Distributed Tracing
    # -------------------------------------------------------------------------
    
    async def get_trace(self, trace_id: str) -> Optional[RequestTrace]:
        """Get a specific trace by ID."""
        # In production: query Jaeger/Zipkin
        return None
    
    async def search_traces(
        self,
        service_name: str,
        namespace: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_duration_ms: Optional[float] = None,
        max_duration_ms: Optional[float] = None,
        has_error: Optional[bool] = None,
        limit: int = 20,
    ) -> list[RequestTrace]:
        """
        Search for traces matching criteria.
        
        Args:
            service_name: Service name
            namespace: Namespace
            start_time: Start of time range
            end_time: End of time range
            min_duration_ms: Minimum trace duration
            max_duration_ms: Maximum trace duration
            has_error: Filter by error status
            limit: Maximum results
        
        Returns:
            List of matching traces
        """
        # In production: query tracing backend
        return []
    
    async def get_trace_summary(
        self,
        service_name: str,
        namespace: str,
        window_minutes: int = 60,
    ) -> dict[str, Any]:
        """
        Get trace summary statistics.
        
        Returns:
            Summary with trace counts, error rates, latency distributions
        """
        return {
            "service": service_name,
            "namespace": namespace,
            "window_minutes": window_minutes,
            "total_traces": 0,
            "error_traces": 0,
            "avg_duration_ms": 0.0,
            "p99_duration_ms": 0.0,
        }
    
    # -------------------------------------------------------------------------
    # Service Topology
    # -------------------------------------------------------------------------
    
    async def get_topology(
        self,
        namespace: Optional[str] = None,
    ) -> ServiceTopology:
        """
        Get service topology graph.
        
        Args:
            namespace: Optional namespace filter
        
        Returns:
            ServiceTopology with nodes and edges
        """
        # In production: query Kiali or mesh APIs
        return ServiceTopology(
            namespace=namespace,
        )
    
    async def get_service_dependencies(
        self,
        service_name: str,
        namespace: str,
        depth: int = 2,
    ) -> ServiceTopology:
        """
        Get dependency graph for a service.
        
        Args:
            service_name: Service name
            namespace: Namespace
            depth: How many hops to follow
        
        Returns:
            ServiceTopology centered on the service
        """
        return ServiceTopology(namespace=namespace)
    
    async def get_upstream_services(
        self,
        service_name: str,
        namespace: str,
    ) -> list[ServiceNode]:
        """Get services that call this service."""
        topology = await self.get_topology(namespace)
        upstream_names = topology.get_upstream(service_name)
        return [n for n in topology.nodes if n.name in upstream_names]
    
    async def get_downstream_services(
        self,
        service_name: str,
        namespace: str,
    ) -> list[ServiceNode]:
        """Get services this service calls."""
        topology = await self.get_topology(namespace)
        downstream_names = topology.get_downstream(service_name)
        return [n for n in topology.nodes if n.name in downstream_names]
    
    # -------------------------------------------------------------------------
    # Health Checking
    # -------------------------------------------------------------------------
    
    async def check_health(
        self,
        service_name: str,
        namespace: str,
        check_type: HealthCheckType = HealthCheckType.HTTP,
        endpoint: str = "/health",
    ) -> HealthCheckResult:
        """
        Perform a health check on a service.
        
        Args:
            service_name: Service name
            namespace: Namespace
            check_type: Type of health check
            endpoint: Health endpoint (for HTTP)
        
        Returns:
            HealthCheckResult
        """
        # In production: actually perform the check
        return HealthCheckResult(
            healthy=True,
            check_type=check_type,
            status_code=200,
            response_time_ms=50.0,
            message="OK",
            endpoint=endpoint,
        )
    
    async def get_health_status(
        self,
        service_name: str,
        namespace: str,
    ) -> dict[str, Any]:
        """
        Get overall health status for a service.
        
        Returns:
            Health status including mesh status, endpoints, etc.
        """
        result = await self.check_health(service_name, namespace)
        golden = await self.get_golden_signals(service_name, namespace)
        
        return {
            "service": service_name,
            "namespace": namespace,
            "healthy": result.healthy and golden.is_healthy(),
            "health_check": {
                "status": "healthy" if result.healthy else "unhealthy",
                "response_time_ms": result.response_time_ms,
            },
            "golden_signals": {
                "latency_p99_ms": golden.latency_p99_ms,
                "error_rate": golden.error_rate,
                "requests_per_second": golden.requests_per_second,
            },
        }
    
    # -------------------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------------------
    
    async def get_active_alerts(
        self,
        namespace: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
    ) -> list[MeshAlert]:
        """
        Get active alerts.
        
        Args:
            namespace: Optional namespace filter
            severity: Optional severity filter
        
        Returns:
            List of active alerts
        """
        # In production: query alertmanager or mesh
        return []
    
    async def get_alert_history(
        self,
        service_name: str,
        namespace: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[MeshAlert]:
        """Get alert history for a service."""
        return []
    
    # -------------------------------------------------------------------------
    # Comparison / Diff
    # -------------------------------------------------------------------------
    
    async def compare_metrics(
        self,
        service_name: str,
        namespace: str,
        baseline_start: datetime,
        baseline_end: datetime,
        comparison_start: datetime,
        comparison_end: datetime,
    ) -> dict[str, Any]:
        """
        Compare metrics between two time windows.
        
        Useful for canary analysis, before/after deployments, etc.
        
        Returns:
            Comparison with deltas and significance
        """
        # In production: query and compare
        return {
            "service": service_name,
            "namespace": namespace,
            "baseline": {
                "start": baseline_start.isoformat(),
                "end": baseline_end.isoformat(),
            },
            "comparison": {
                "start": comparison_start.isoformat(),
                "end": comparison_end.isoformat(),
            },
            "deltas": {
                "latency_p99_ms": 0.0,
                "error_rate": 0.0,
                "requests_per_second": 0.0,
            },
            "significant_changes": [],
        }
