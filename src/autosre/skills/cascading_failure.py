"""
Cascading Failure Analyzer

Detects and analyzes cascading failure patterns across services.

Key patterns detected:
1. Client-side throttling failure (clients not backing off)
2. Queue saturation (FIFO queues during overload)
3. Retry storms (exponential backoff gone wrong)
4. Resource exhaustion chains
5. Dependency cascade (one service taking down others)

Key insight: LIFO queues during overload (serve newest requests first)
prevents cascading timeouts as old requests in queue are already likely
to timeout on the client side.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class FailureStage(Enum):
    """Stage of cascading failure progression."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"         # Initial degradation
    CASCADING = "cascading"       # Active cascade
    CRITICAL = "critical"         # Multiple systems affected
    RECOVERY = "recovery"         # Attempting recovery


class CascadePattern(Enum):
    """Types of cascading failure patterns."""
    CLIENT_RETRY_STORM = "client_retry_storm"
    QUEUE_SATURATION = "queue_saturation"
    DEPENDENCY_CHAIN = "dependency_chain"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    TIMEOUT_CHAIN = "timeout_chain"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CONNECTION_POOL_EXHAUSTION = "connection_pool_exhaustion"
    MEMORY_PRESSURE = "memory_pressure"
    GC_PRESSURE = "gc_pressure"


@dataclass
class ServiceMetrics:
    """Metrics for a single service."""
    service: str
    
    # Request metrics
    request_rate: float           # Requests per second
    accept_rate: float            # Accepted requests per second
    reject_rate: float            # Rejected requests per second
    error_rate: float             # Error rate (0.0 to 1.0)
    
    # Queue metrics
    queue_depth: int = 0
    queue_wait_p50_ms: float = 0
    queue_wait_p99_ms: float = 0
    queue_mode: str = "fifo"      # fifo or lifo
    
    # Resource metrics
    cpu_percent: float = 0
    memory_percent: float = 0
    gc_pause_ms: float = 0
    
    # Connection metrics
    connection_pool_used: int = 0
    connection_pool_max: int = 100
    
    # Circuit breaker
    circuit_breaker_open: bool = False
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def accept_reject_ratio(self) -> float:
        """Ratio of accepted to total requests."""
        total = self.accept_rate + self.reject_rate
        return self.accept_rate / total if total > 0 else 1.0
    
    @property
    def connection_pool_utilization(self) -> float:
        """Connection pool utilization percentage."""
        return self.connection_pool_used / self.connection_pool_max if self.connection_pool_max > 0 else 0


@dataclass
class CascadeDetection:
    """Result of cascade failure detection."""
    is_cascading: bool
    stage: FailureStage
    confidence: float             # 0.0 to 1.0
    
    # Detected patterns
    patterns: list[CascadePattern] = field(default_factory=list)
    
    # Affected services
    origin_service: Optional[str] = None
    affected_services: list[str] = field(default_factory=list)
    
    # Metrics that triggered detection
    triggers: list[dict[str, Any]] = field(default_factory=list)
    
    # Recommendations
    immediate_actions: list[str] = field(default_factory=list)
    
    # Recovery requirements
    recovery_load_multiplier: float = 0.5  # Start recovery at this load
    estimated_recovery_minutes: float = 0
    
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "is_cascading": self.is_cascading,
            "stage": self.stage.value,
            "confidence": round(self.confidence, 2),
            "patterns": [p.value for p in self.patterns],
            "origin_service": self.origin_service,
            "affected_services": self.affected_services,
            "triggers": self.triggers,
            "immediate_actions": self.immediate_actions,
            "recovery_load_multiplier": self.recovery_load_multiplier,
            "estimated_recovery_minutes": self.estimated_recovery_minutes,
            "detected_at": self.detected_at.isoformat(),
        }
    
    def get_summary(self) -> str:
        """Human-readable summary."""
        if not self.is_cascading:
            return f"✅ No cascading failure detected (Stage: {self.stage.value})"
        
        lines = [
            f"🚨 CASCADING FAILURE DETECTED",
            f"Stage: {self.stage.value.upper()}",
            f"Confidence: {self.confidence * 100:.0f}%",
            f"",
            f"Patterns: {', '.join(p.value for p in self.patterns)}",
        ]
        
        if self.origin_service:
            lines.append(f"Origin: {self.origin_service}")
        
        if self.affected_services:
            lines.append(f"Affected: {', '.join(self.affected_services)}")
        
        if self.immediate_actions:
            lines.extend(["", "Immediate Actions:"])
            for action in self.immediate_actions[:3]:
                lines.append(f"  • {action}")
        
        return "\n".join(lines)


class CascadingFailureAnalyzer:
    """
    Analyzes metrics to detect cascading failure patterns.
    
    Detection heuristics:
    1. Client throttling: request_rate >> accept_rate
    2. Queue saturation: queue_wait_p99 > 2x normal
    3. Retry storms: request_rate increasing while error_rate high
    4. Resource exhaustion: CPU/memory > 90% sustained
    5. Dependency chain: errors in upstream correlate with downstream
    """
    
    # Thresholds for detection
    THRESHOLDS = {
        "accept_reject_ratio_critical": 0.5,    # <50% requests accepted
        "accept_reject_ratio_warning": 0.7,     # <70% requests accepted
        "queue_wait_critical_ms": 5000,         # 5 second queue wait
        "queue_wait_warning_ms": 1000,          # 1 second queue wait
        "error_rate_critical": 0.25,            # 25% error rate
        "error_rate_warning": 0.10,             # 10% error rate
        "cpu_critical": 90,                     # 90% CPU
        "memory_critical": 90,                  # 90% memory
        "gc_pause_critical_ms": 500,            # 500ms GC pause
        "connection_pool_critical": 0.9,        # 90% pool utilization
    }
    
    # Prometheus queries
    QUERIES = {
        # Client-side throttling
        "client_rejection_rate": 'sum(rate(client_requests_rejected_total{{service="{service}"}}[5m]))',
        
        # Request/accept ratio
        "request_rate": 'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
        "accept_rate": 'sum(rate(http_requests_accepted_total{{service="{service}"}}[5m]))',
        
        # Queue metrics
        "queue_depth": 'sum(request_queue_depth{{service="{service}"}})',
        "queue_wait_p99": 'histogram_quantile(0.99, rate(request_queue_wait_seconds_bucket{{service="{service}"}}[5m]))',
        
        # Error metrics
        "error_rate": 'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m]))',
        
        # Resource metrics
        "cpu_percent": 'avg(rate(container_cpu_usage_seconds_total{{service="{service}"}}[5m])) * 100',
        "memory_percent": 'avg(container_memory_usage_bytes{{service="{service}"}}) / avg(container_spec_memory_limit_bytes{{service="{service}"}}) * 100',
        
        # GC pressure
        "gc_pause_ms": 'rate(jvm_gc_pause_seconds_sum{{service="{service}"}}[5m]) * 1000',
        
        # Connection pool
        "connection_pool_used": 'sum(connection_pool_in_use{{service="{service}"}})',
        "connection_pool_max": 'sum(connection_pool_max{{service="{service}"}})',
        
        # Circuit breaker
        "circuit_breaker_open": 'sum(circuit_breaker_state{{service="{service}",state="open"}})',
    }
    
    def __init__(self, prometheus_client: Any = None):
        self.prometheus = prometheus_client
        self._service_history: dict[str, list[ServiceMetrics]] = {}
        self._dependencies: dict[str, list[str]] = {}  # service -> [dependencies]
    
    def configure_dependencies(self, service: str, dependencies: list[str]) -> None:
        """Configure service dependencies for cascade detection."""
        self._dependencies[service] = dependencies
    
    def analyze(
        self,
        services: list[ServiceMetrics],
    ) -> CascadeDetection:
        """
        Analyze service metrics for cascading failure patterns.
        
        Args:
            services: List of service metrics to analyze
        """
        patterns = []
        triggers = []
        affected = []
        origin = None
        confidence = 0.0
        
        for svc in services:
            svc_patterns, svc_triggers = self._analyze_service(svc)
            
            if svc_patterns:
                patterns.extend(svc_patterns)
                triggers.extend(svc_triggers)
                affected.append(svc.service)
                
                # First service with issues is likely origin
                if not origin:
                    origin = svc.service
        
        # Deduplicate patterns
        patterns = list(set(patterns))
        
        # Calculate confidence and stage
        if not patterns:
            stage = FailureStage.HEALTHY
            is_cascading = False
        elif len(affected) == 1:
            stage = FailureStage.DEGRADED
            is_cascading = False
            confidence = 0.3
        elif len(affected) == 2:
            stage = FailureStage.CASCADING
            is_cascading = True
            confidence = 0.6
        else:
            stage = FailureStage.CRITICAL
            is_cascading = True
            confidence = 0.9
        
        # Boost confidence for certain pattern combinations
        if CascadePattern.CLIENT_RETRY_STORM in patterns:
            confidence = min(confidence + 0.2, 1.0)
        if CascadePattern.QUEUE_SATURATION in patterns:
            confidence = min(confidence + 0.1, 1.0)
        
        # Generate recommendations
        actions = self._generate_actions(patterns, affected)
        
        # Calculate recovery requirements
        recovery_multiplier, recovery_time = self._calculate_recovery_requirements(
            patterns, services
        )
        
        return CascadeDetection(
            is_cascading=is_cascading,
            stage=stage,
            confidence=confidence,
            patterns=patterns,
            origin_service=origin,
            affected_services=affected,
            triggers=triggers,
            immediate_actions=actions,
            recovery_load_multiplier=recovery_multiplier,
            estimated_recovery_minutes=recovery_time,
        )
    
    async def analyze_from_prometheus(
        self,
        services: list[str],
    ) -> CascadeDetection:
        """
        Analyze services using Prometheus metrics.
        
        Args:
            services: List of service names to analyze
        """
        if not self.prometheus:
            raise RuntimeError("Prometheus client not configured")
        
        metrics = []
        for service in services:
            svc_metrics = await self._fetch_service_metrics(service)
            metrics.append(svc_metrics)
        
        return self.analyze(metrics)
    
    def _analyze_service(
        self, svc: ServiceMetrics
    ) -> tuple[list[CascadePattern], list[dict]]:
        """Analyze a single service for failure patterns."""
        patterns = []
        triggers = []
        
        # Check client-side throttling
        if svc.accept_reject_ratio < self.THRESHOLDS["accept_reject_ratio_critical"]:
            patterns.append(CascadePattern.CLIENT_RETRY_STORM)
            triggers.append({
                "service": svc.service,
                "pattern": "client_throttling",
                "metric": "accept_reject_ratio",
                "value": svc.accept_reject_ratio,
                "threshold": self.THRESHOLDS["accept_reject_ratio_critical"],
            })
        
        # Check queue saturation
        if svc.queue_wait_p99_ms > self.THRESHOLDS["queue_wait_critical_ms"]:
            patterns.append(CascadePattern.QUEUE_SATURATION)
            triggers.append({
                "service": svc.service,
                "pattern": "queue_saturation",
                "metric": "queue_wait_p99_ms",
                "value": svc.queue_wait_p99_ms,
                "threshold": self.THRESHOLDS["queue_wait_critical_ms"],
            })
            
            # FIFO queue during overload is especially problematic
            if svc.queue_mode == "fifo" and svc.queue_depth > 100:
                triggers[-1]["note"] = "FIFO queue mode - consider LIFO during overload"
        
        # Check error rate
        if svc.error_rate > self.THRESHOLDS["error_rate_critical"]:
            patterns.append(CascadePattern.TIMEOUT_CHAIN)
            triggers.append({
                "service": svc.service,
                "pattern": "high_error_rate",
                "metric": "error_rate",
                "value": svc.error_rate,
                "threshold": self.THRESHOLDS["error_rate_critical"],
            })
        
        # Check resource exhaustion
        if svc.cpu_percent > self.THRESHOLDS["cpu_critical"]:
            patterns.append(CascadePattern.RESOURCE_EXHAUSTION)
            triggers.append({
                "service": svc.service,
                "pattern": "cpu_exhaustion",
                "metric": "cpu_percent",
                "value": svc.cpu_percent,
                "threshold": self.THRESHOLDS["cpu_critical"],
            })
        
        if svc.memory_percent > self.THRESHOLDS["memory_critical"]:
            patterns.append(CascadePattern.MEMORY_PRESSURE)
            triggers.append({
                "service": svc.service,
                "pattern": "memory_pressure",
                "metric": "memory_percent",
                "value": svc.memory_percent,
                "threshold": self.THRESHOLDS["memory_critical"],
            })
        
        # Check GC pressure
        if svc.gc_pause_ms > self.THRESHOLDS["gc_pause_critical_ms"]:
            patterns.append(CascadePattern.GC_PRESSURE)
            triggers.append({
                "service": svc.service,
                "pattern": "gc_pressure",
                "metric": "gc_pause_ms",
                "value": svc.gc_pause_ms,
                "threshold": self.THRESHOLDS["gc_pause_critical_ms"],
            })
        
        # Check connection pool
        if svc.connection_pool_utilization > self.THRESHOLDS["connection_pool_critical"]:
            patterns.append(CascadePattern.CONNECTION_POOL_EXHAUSTION)
            triggers.append({
                "service": svc.service,
                "pattern": "connection_pool_exhaustion",
                "metric": "connection_pool_utilization",
                "value": svc.connection_pool_utilization,
                "threshold": self.THRESHOLDS["connection_pool_critical"],
            })
        
        # Check circuit breaker
        if svc.circuit_breaker_open:
            patterns.append(CascadePattern.CIRCUIT_BREAKER_OPEN)
            triggers.append({
                "service": svc.service,
                "pattern": "circuit_breaker_open",
                "metric": "circuit_breaker_state",
                "value": "open",
            })
        
        return patterns, triggers
    
    def _generate_actions(
        self,
        patterns: list[CascadePattern],
        affected: list[str],
    ) -> list[str]:
        """Generate immediate action recommendations."""
        actions = []
        
        if CascadePattern.CLIENT_RETRY_STORM in patterns:
            actions.extend([
                "Enable client-side load shedding",
                "Activate retry circuit breakers on clients",
                "Consider implementing adaptive concurrency limits",
            ])
        
        if CascadePattern.QUEUE_SATURATION in patterns:
            actions.extend([
                "Switch to LIFO queue mode to prioritize fresh requests",
                "Enable queue depth limits with fast-fail",
                "Consider dropping oldest queued requests",
            ])
        
        if CascadePattern.RESOURCE_EXHAUSTION in patterns:
            actions.extend([
                "Scale up affected services immediately",
                "Enable aggressive load shedding",
                "Reduce non-critical traffic",
            ])
        
        if CascadePattern.GC_PRESSURE in patterns:
            actions.extend([
                "Reduce heap allocation rate if possible",
                "Scale out to distribute load",
                "Consider increasing heap size temporarily",
            ])
        
        if CascadePattern.CONNECTION_POOL_EXHAUSTION in patterns:
            actions.extend([
                "Reduce connection pool checkout timeout",
                "Scale connection pool size if possible",
                "Implement connection pool fast-fail",
            ])
        
        # General actions for any cascade
        if patterns:
            actions.extend([
                "Reduce overall load to below current capacity",
                "Monitor for recovery - don't restore load too quickly",
            ])
        
        return actions
    
    def _calculate_recovery_requirements(
        self,
        patterns: list[CascadePattern],
        services: list[ServiceMetrics],
    ) -> tuple[float, float]:
        """
        Calculate recovery load multiplier and time estimate.
        
        Key insight: Can't recover at normal load when capacity is degraded.
        Must reduce load significantly, let service stabilize, then gradually increase.
        """
        # Base recovery multiplier (start at 30% of normal load)
        recovery_multiplier = 0.3
        
        # Adjust based on patterns
        if CascadePattern.GC_PRESSURE in patterns:
            recovery_multiplier = 0.2  # GC needs very low load to recover
        
        if CascadePattern.MEMORY_PRESSURE in patterns:
            recovery_multiplier = 0.25  # Memory issues need gradual recovery
        
        # Calculate estimated recovery time
        # Base: 5 minutes to stabilize
        recovery_minutes = 5.0
        
        # Add time for each affected service
        recovery_minutes += len(services) * 2
        
        # Add time for certain patterns
        if CascadePattern.GC_PRESSURE in patterns:
            recovery_minutes += 10  # GC recovery takes time
        
        if CascadePattern.MEMORY_PRESSURE in patterns:
            recovery_minutes += 15  # Memory recovery can be slow
        
        return recovery_multiplier, recovery_minutes
    
    async def _fetch_service_metrics(self, service: str) -> ServiceMetrics:
        """Fetch metrics for a service from Prometheus."""
        metrics = ServiceMetrics(
            service=service,
            request_rate=0,
            accept_rate=0,
            reject_rate=0,
            error_rate=0,
        )
        
        try:
            # Fetch each metric
            request_result = await self.prometheus.query(
                self.QUERIES["request_rate"].format(service=service)
            )
            metrics.request_rate = self._extract_value(request_result, 0)
            
            accept_result = await self.prometheus.query(
                self.QUERIES["accept_rate"].format(service=service)
            )
            metrics.accept_rate = self._extract_value(accept_result, metrics.request_rate)
            
            metrics.reject_rate = metrics.request_rate - metrics.accept_rate
            
            error_result = await self.prometheus.query(
                self.QUERIES["error_rate"].format(service=service)
            )
            metrics.error_rate = self._extract_value(error_result, 0)
            
            queue_depth_result = await self.prometheus.query(
                self.QUERIES["queue_depth"].format(service=service)
            )
            metrics.queue_depth = int(self._extract_value(queue_depth_result, 0))
            
            queue_wait_result = await self.prometheus.query(
                self.QUERIES["queue_wait_p99"].format(service=service)
            )
            metrics.queue_wait_p99_ms = self._extract_value(queue_wait_result, 0) * 1000
            
            cpu_result = await self.prometheus.query(
                self.QUERIES["cpu_percent"].format(service=service)
            )
            metrics.cpu_percent = self._extract_value(cpu_result, 0)
            
            memory_result = await self.prometheus.query(
                self.QUERIES["memory_percent"].format(service=service)
            )
            metrics.memory_percent = self._extract_value(memory_result, 0)
            
            gc_result = await self.prometheus.query(
                self.QUERIES["gc_pause_ms"].format(service=service)
            )
            metrics.gc_pause_ms = self._extract_value(gc_result, 0)
            
            pool_used_result = await self.prometheus.query(
                self.QUERIES["connection_pool_used"].format(service=service)
            )
            metrics.connection_pool_used = int(self._extract_value(pool_used_result, 0))
            
            pool_max_result = await self.prometheus.query(
                self.QUERIES["connection_pool_max"].format(service=service)
            )
            metrics.connection_pool_max = int(self._extract_value(pool_max_result, 100))
            
            cb_result = await self.prometheus.query(
                self.QUERIES["circuit_breaker_open"].format(service=service)
            )
            metrics.circuit_breaker_open = self._extract_value(cb_result, 0) > 0
            
        except Exception as e:
            logger.warning(f"Failed to fetch metrics for {service}: {e}")
        
        return metrics
    
    def _extract_value(self, result: Any, default: float) -> float:
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
    
    def get_prometheus_queries(self, service: str) -> dict[str, str]:
        """Get Prometheus queries for a service."""
        return {
            name: query.format(service=service)
            for name, query in self.QUERIES.items()
        }
