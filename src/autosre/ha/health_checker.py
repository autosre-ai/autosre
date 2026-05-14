"""Health Checker for AutoSRE V2 High Availability.

Provides deep health checking with:
- Component-level health checks
- Dependency health aggregation
- Configurable check intervals
- Health history tracking
"""

from __future__ import annotations

import asyncio
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status values."""
    
    HEALTHY = "healthy"  # All checks passing
    DEGRADED = "degraded"  # Some non-critical checks failing
    UNHEALTHY = "unhealthy"  # Critical checks failing
    UNKNOWN = "unknown"  # Unable to determine health


class HealthCheckType(str, Enum):
    """Types of health checks."""
    
    LIVENESS = "liveness"  # Is the service alive?
    READINESS = "readiness"  # Is the service ready to accept traffic?
    STARTUP = "startup"  # Has the service started?
    DEPENDENCY = "dependency"  # Is a dependency available?
    CUSTOM = "custom"  # Custom check


@dataclass
class HealthConfig:
    """Configuration for health checking."""
    
    # Check intervals
    check_interval_seconds: float = 30.0
    timeout_seconds: float = 10.0
    
    # Failure thresholds
    failure_threshold: int = 3  # Failures before unhealthy
    success_threshold: int = 1  # Successes before healthy
    
    # History
    max_history_size: int = 100
    
    # Dependencies
    critical_dependencies: Set[str] = field(default_factory=set)
    
    # Caching
    cache_ttl_seconds: float = 5.0


class HealthCheckResult(BaseModel):
    """Result of a health check."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    check_type: HealthCheckType
    status: HealthStatus
    
    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    
    # Details
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    
    # For dependencies
    dependency_name: Optional[str] = None
    endpoint: Optional[str] = None
    
    def is_healthy(self) -> bool:
        """Check if result indicates healthy state."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


class DependencyHealth(BaseModel):
    """Health status of a dependency."""
    
    name: str
    type: str  # database, cache, service, etc.
    status: HealthStatus
    
    # Connection info
    endpoint: Optional[str] = None
    version: Optional[str] = None
    
    # Metrics
    latency_ms: Optional[float] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    
    # Details
    details: Dict[str, Any] = Field(default_factory=dict)
    
    def is_critical(self, critical_deps: Set[str]) -> bool:
        """Check if this is a critical dependency."""
        return self.name in critical_deps


class ComponentHealth(BaseModel):
    """Health status of a component."""
    
    name: str
    status: HealthStatus
    
    # Checks
    liveness: Optional[HealthCheckResult] = None
    readiness: Optional[HealthCheckResult] = None
    startup: Optional[HealthCheckResult] = None
    custom_checks: Dict[str, HealthCheckResult] = Field(default_factory=dict)
    
    # Dependencies
    dependencies: Dict[str, DependencyHealth] = Field(default_factory=dict)
    
    # Metrics
    uptime_seconds: float = 0.0
    last_status_change: Optional[datetime] = None
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    
    def calculate_status(self) -> HealthStatus:
        """Calculate overall status from checks."""
        # Check liveness first
        if self.liveness and self.liveness.status == HealthStatus.UNHEALTHY:
            return HealthStatus.UNHEALTHY
        
        # Check readiness
        if self.readiness and self.readiness.status == HealthStatus.UNHEALTHY:
            return HealthStatus.DEGRADED
        
        # Check dependencies
        unhealthy_deps = [
            d for d in self.dependencies.values()
            if d.status == HealthStatus.UNHEALTHY
        ]
        if unhealthy_deps:
            return HealthStatus.DEGRADED
        
        # Check custom checks
        unhealthy_checks = [
            c for c in self.custom_checks.values()
            if c.status == HealthStatus.UNHEALTHY
        ]
        if unhealthy_checks:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY


# Type for health check functions
HealthCheckFunc = Callable[[], Awaitable[HealthCheckResult]]


class HealthCheck(ABC):
    """Abstract base class for health checks."""
    
    def __init__(
        self,
        name: str,
        check_type: HealthCheckType = HealthCheckType.CUSTOM,
        timeout_seconds: float = 10.0,
        critical: bool = False,
    ):
        self.name = name
        self.check_type = check_type
        self.timeout_seconds = timeout_seconds
        self.critical = critical
        
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_result: Optional[HealthCheckResult] = None
    
    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check.
        
        Returns:
            HealthCheckResult
        """
        ...
    
    async def execute(self) -> HealthCheckResult:
        """Execute the check with timeout handling."""
        start = asyncio.get_event_loop().time()
        
        try:
            result = await asyncio.wait_for(
                self.check(),
                timeout=self.timeout_seconds,
            )
            
            # Track consecutive successes
            if result.status == HealthStatus.HEALTHY:
                self._consecutive_successes += 1
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                self._consecutive_successes = 0
            
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error="Health check timed out",
            )
            self._consecutive_failures += 1
            self._consecutive_successes = 0
        
        except Exception as e:
            result = HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )
            self._consecutive_failures += 1
            self._consecutive_successes = 0
        
        result.duration_ms = (asyncio.get_event_loop().time() - start) * 1000
        self._last_result = result
        
        return result
    
    @property
    def last_result(self) -> Optional[HealthCheckResult]:
        """Get last check result."""
        return self._last_result
    
    @property
    def consecutive_failures(self) -> int:
        """Get consecutive failure count."""
        return self._consecutive_failures


class HTTPHealthCheck(HealthCheck):
    """Health check via HTTP endpoint."""
    
    def __init__(
        self,
        name: str,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 10.0,
        critical: bool = False,
    ):
        super().__init__(name, HealthCheckType.DEPENDENCY, timeout_seconds, critical)
        self.url = url
        self.method = method
        self.expected_status = expected_status
        self.headers = headers or {}
    
    async def check(self) -> HealthCheckResult:
        """Perform HTTP health check."""
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    self.method,
                    self.url,
                    headers=self.headers,
                )
                
                if response.status_code == self.expected_status:
                    return HealthCheckResult(
                        name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.HEALTHY,
                        message=f"HTTP {response.status_code}",
                        endpoint=self.url,
                    )
                else:
                    return HealthCheckResult(
                        name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Unexpected status: {response.status_code}",
                        endpoint=self.url,
                    )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                endpoint=self.url,
            )


class TCPHealthCheck(HealthCheck):
    """Health check via TCP connection."""
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        timeout_seconds: float = 10.0,
        critical: bool = False,
    ):
        super().__init__(name, HealthCheckType.DEPENDENCY, timeout_seconds, critical)
        self.host = host
        self.port = port
    
    async def check(self) -> HealthCheckResult:
        """Perform TCP health check."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                endpoint=f"{self.host}:{self.port}",
            )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                endpoint=f"{self.host}:{self.port}",
            )


class RedisHealthCheck(HealthCheck):
    """Health check for Redis."""
    
    def __init__(
        self,
        name: str = "redis",
        url: str = "redis://localhost:6379",
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ):
        super().__init__(name, HealthCheckType.DEPENDENCY, timeout_seconds, critical)
        self.url = url
    
    async def check(self) -> HealthCheckResult:
        """Perform Redis health check."""
        try:
            import redis.asyncio as redis
            
            client = redis.from_url(self.url)
            
            try:
                start = asyncio.get_event_loop().time()
                pong = await asyncio.wait_for(
                    client.ping(),
                    timeout=self.timeout_seconds,
                )
                latency = (asyncio.get_event_loop().time() - start) * 1000
                
                info = await client.info("server")
                
                return HealthCheckResult(
                    name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.HEALTHY if pong else HealthStatus.UNHEALTHY,
                    details={
                        "redis_version": info.get("redis_version"),
                        "latency_ms": latency,
                    },
                )
            finally:
                await client.close()
        
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNKNOWN,
                error="redis package not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class PostgresHealthCheck(HealthCheck):
    """Health check for PostgreSQL."""
    
    def __init__(
        self,
        name: str = "postgres",
        dsn: str = "postgresql://localhost/autosre",
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ):
        super().__init__(name, HealthCheckType.DEPENDENCY, timeout_seconds, critical)
        self.dsn = dsn
    
    async def check(self) -> HealthCheckResult:
        """Perform PostgreSQL health check."""
        try:
            import asyncpg
            
            conn = await asyncio.wait_for(
                asyncpg.connect(self.dsn),
                timeout=self.timeout_seconds,
            )
            
            try:
                start = asyncio.get_event_loop().time()
                version = await conn.fetchval("SELECT version()")
                latency = (asyncio.get_event_loop().time() - start) * 1000
                
                return HealthCheckResult(
                    name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.HEALTHY,
                    details={
                        "version": version[:50] if version else None,
                        "latency_ms": latency,
                    },
                )
            finally:
                await conn.close()
        
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNKNOWN,
                error="asyncpg package not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class FunctionHealthCheck(HealthCheck):
    """Health check using a custom function."""
    
    def __init__(
        self,
        name: str,
        check_func: HealthCheckFunc,
        check_type: HealthCheckType = HealthCheckType.CUSTOM,
        timeout_seconds: float = 10.0,
        critical: bool = False,
    ):
        super().__init__(name, check_type, timeout_seconds, critical)
        self.check_func = check_func
    
    async def check(self) -> HealthCheckResult:
        """Perform custom health check."""
        return await self.check_func()


class AggregateHealth(BaseModel):
    """Aggregate health status."""
    
    status: HealthStatus
    
    # Components
    components: Dict[str, ComponentHealth] = Field(default_factory=dict)
    
    # Summary
    total_checks: int = 0
    healthy_checks: int = 0
    degraded_checks: int = 0
    unhealthy_checks: int = 0
    
    # Dependencies
    dependencies: Dict[str, DependencyHealth] = Field(default_factory=dict)
    
    # Timing
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    check_duration_ms: float = 0.0
    
    # History
    uptime_percentage: float = 100.0
    
    def to_response(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "status": self.status.value,
            "checked_at": self.checked_at.isoformat(),
            "uptime_percentage": self.uptime_percentage,
            "summary": {
                "total": self.total_checks,
                "healthy": self.healthy_checks,
                "degraded": self.degraded_checks,
                "unhealthy": self.unhealthy_checks,
            },
            "components": {
                name: {
                    "status": comp.status.value,
                    "uptime_seconds": comp.uptime_seconds,
                }
                for name, comp in self.components.items()
            },
            "dependencies": {
                name: {
                    "status": dep.status.value,
                    "type": dep.type,
                    "latency_ms": dep.latency_ms,
                }
                for name, dep in self.dependencies.items()
            },
        }


class HealthChecker:
    """
    Comprehensive health checking system.
    
    Provides deep health checking with:
    - Multiple check types (liveness, readiness, startup)
    - Dependency health monitoring
    - Configurable failure thresholds
    - Health history tracking
    - Aggregate status calculation
    
    Example:
        checker = HealthChecker()
        
        # Add checks
        checker.add_check(RedisHealthCheck())
        checker.add_check(PostgresHealthCheck())
        checker.add_check(HTTPHealthCheck(
            name="api",
            url="http://localhost:8080/health",
        ))
        
        # Start monitoring
        await checker.start()
        
        # Get health
        health = await checker.get_health()
        print(f"Status: {health.status}")
        
        await checker.stop()
    """
    
    def __init__(
        self,
        config: Optional[HealthConfig] = None,
    ):
        """Initialize HealthChecker.
        
        Args:
            config: Health check configuration
        """
        self.config = config or HealthConfig()
        
        self._checks: Dict[str, HealthCheck] = {}
        self._history: List[HealthCheckResult] = []
        self._component_health: Dict[str, ComponentHealth] = {}
        
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._cached_health: Optional[AggregateHealth] = None
        self._cache_time: Optional[datetime] = None
        
        self._start_time = datetime.now(timezone.utc)
        self._status_changes: List[tuple[datetime, HealthStatus]] = []
    
    def add_check(self, check: HealthCheck) -> None:
        """Add a health check.
        
        Args:
            check: Health check to add
        """
        self._checks[check.name] = check
        
        if check.critical:
            self.config.critical_dependencies.add(check.name)
        
        logger.info(
            "Added health check",
            name=check.name,
            type=check.check_type.value,
            critical=check.critical,
        )
    
    def add_http_check(
        self,
        name: str,
        url: str,
        **kwargs,
    ) -> None:
        """Add an HTTP health check.
        
        Args:
            name: Check name
            url: URL to check
            **kwargs: Additional arguments for HTTPHealthCheck
        """
        self.add_check(HTTPHealthCheck(name=name, url=url, **kwargs))
    
    def add_tcp_check(
        self,
        name: str,
        host: str,
        port: int,
        **kwargs,
    ) -> None:
        """Add a TCP health check.
        
        Args:
            name: Check name
            host: Host to connect to
            port: Port to connect to
            **kwargs: Additional arguments for TCPHealthCheck
        """
        self.add_check(TCPHealthCheck(name=name, host=host, port=port, **kwargs))
    
    def add_function_check(
        self,
        name: str,
        func: HealthCheckFunc,
        **kwargs,
    ) -> None:
        """Add a custom function health check.
        
        Args:
            name: Check name
            func: Async function to call
            **kwargs: Additional arguments for FunctionHealthCheck
        """
        self.add_check(FunctionHealthCheck(name=name, check_func=func, **kwargs))
    
    def remove_check(self, name: str) -> bool:
        """Remove a health check.
        
        Args:
            name: Check name
            
        Returns:
            True if removed
        """
        if name in self._checks:
            del self._checks[name]
            self.config.critical_dependencies.discard(name)
            return True
        return False
    
    async def start(self) -> None:
        """Start health checking."""
        if self._running:
            return
        
        self._running = True
        self._start_time = datetime.now(timezone.utc)
        
        logger.info(
            "Starting health checker",
            check_count=len(self._checks),
            interval_seconds=self.config.check_interval_seconds,
        )
        
        # Run initial check
        await self._run_checks()
        
        # Start background check task
        self._check_task = asyncio.create_task(self._check_loop())
    
    async def stop(self) -> None:
        """Stop health checking."""
        if not self._running:
            return
        
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
        
        logger.info("Stopped health checker")
    
    async def get_health(self, use_cache: bool = True) -> AggregateHealth:
        """Get aggregate health status.
        
        Args:
            use_cache: Whether to use cached result
            
        Returns:
            AggregateHealth
        """
        # Check cache
        if use_cache and self._cached_health and self._cache_time:
            age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
            if age < self.config.cache_ttl_seconds:
                return self._cached_health
        
        # Run checks if needed
        if not self._running:
            await self._run_checks()
        
        return self._calculate_aggregate_health()
    
    async def check_liveness(self) -> HealthCheckResult:
        """Perform liveness check.
        
        Returns:
            HealthCheckResult
        """
        # Simple liveness - service is responsive
        return HealthCheckResult(
            name="liveness",
            check_type=HealthCheckType.LIVENESS,
            status=HealthStatus.HEALTHY,
            message="Service is alive",
        )
    
    async def check_readiness(self) -> HealthCheckResult:
        """Perform readiness check.
        
        Returns:
            HealthCheckResult
        """
        # Check critical dependencies
        critical_unhealthy = []
        
        for name, check in self._checks.items():
            if check.critical and check.last_result:
                if check.last_result.status == HealthStatus.UNHEALTHY:
                    critical_unhealthy.append(name)
        
        if critical_unhealthy:
            return HealthCheckResult(
                name="readiness",
                check_type=HealthCheckType.READINESS,
                status=HealthStatus.UNHEALTHY,
                message=f"Critical dependencies unhealthy: {critical_unhealthy}",
            )
        
        return HealthCheckResult(
            name="readiness",
            check_type=HealthCheckType.READINESS,
            status=HealthStatus.HEALTHY,
            message="Service is ready",
        )
    
    async def check_specific(self, name: str) -> Optional[HealthCheckResult]:
        """Run a specific health check.
        
        Args:
            name: Check name
            
        Returns:
            HealthCheckResult or None
        """
        check = self._checks.get(name)
        if not check:
            return None
        
        return await check.execute()
    
    def get_history(
        self,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> List[HealthCheckResult]:
        """Get check history.
        
        Args:
            name: Filter by check name
            limit: Maximum results
            
        Returns:
            List of results
        """
        history = self._history
        
        if name:
            history = [h for h in history if h.name == name]
        
        return history[-limit:]
    
    def get_stats(
        self,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get health check statistics.
        
        Args:
            name: Filter by check name
            
        Returns:
            Statistics dict
        """
        history = self._history
        
        if name:
            history = [h for h in history if h.name == name]
        
        if not history:
            return {"total_checks": 0}
        
        durations = [h.duration_ms for h in history]
        healthy_count = sum(1 for h in history if h.status == HealthStatus.HEALTHY)
        
        return {
            "total_checks": len(history),
            "healthy_count": healthy_count,
            "unhealthy_count": len(history) - healthy_count,
            "success_rate": healthy_count / len(history),
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p50_duration_ms": statistics.median(durations),
            "p95_duration_ms": statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else durations[0],
        }
    
    def get_uptime(self) -> Dict[str, Any]:
        """Get uptime information.
        
        Returns:
            Uptime info
        """
        now = datetime.now(timezone.utc)
        uptime = (now - self._start_time).total_seconds()
        
        # Calculate uptime percentage from history
        healthy_time = 0
        total_time = 0
        
        for i, (time, status) in enumerate(self._status_changes):
            if i < len(self._status_changes) - 1:
                duration = (self._status_changes[i + 1][0] - time).total_seconds()
            else:
                duration = (now - time).total_seconds()
            
            total_time += duration
            if status == HealthStatus.HEALTHY:
                healthy_time += duration
        
        uptime_percentage = (healthy_time / total_time * 100) if total_time > 0 else 100.0
        
        return {
            "started_at": self._start_time.isoformat(),
            "uptime_seconds": uptime,
            "uptime_percentage": uptime_percentage,
            "status_changes": len(self._status_changes),
        }
    
    async def _check_loop(self) -> None:
        """Background check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                await self._run_checks()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Health check loop error",
                    error=str(e),
                )
    
    async def _run_checks(self) -> None:
        """Run all health checks."""
        start = asyncio.get_event_loop().time()
        
        # Run checks concurrently
        tasks = []
        for check in self._checks.values():
            tasks.append(check.execute())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for check, result in zip(self._checks.values(), results):
            if isinstance(result, Exception):
                result = HealthCheckResult(
                    name=check.name,
                    check_type=check.check_type,
                    status=HealthStatus.UNHEALTHY,
                    error=str(result),
                )
            
            # Add to history
            self._history.append(result)
            
            # Trim history
            if len(self._history) > self.config.max_history_size:
                self._history = self._history[-self.config.max_history_size:]
        
        # Update cached health
        self._cached_health = self._calculate_aggregate_health()
        self._cached_health.check_duration_ms = (
            asyncio.get_event_loop().time() - start
        ) * 1000
        self._cache_time = datetime.now(timezone.utc)
        
        # Track status changes
        if self._status_changes:
            last_status = self._status_changes[-1][1]
            if self._cached_health.status != last_status:
                self._status_changes.append(
                    (datetime.now(timezone.utc), self._cached_health.status)
                )
        else:
            self._status_changes.append(
                (datetime.now(timezone.utc), self._cached_health.status)
            )
    
    def _calculate_aggregate_health(self) -> AggregateHealth:
        """Calculate aggregate health from check results."""
        total = 0
        healthy = 0
        degraded = 0
        unhealthy = 0
        
        dependencies: Dict[str, DependencyHealth] = {}
        
        for check in self._checks.values():
            result = check.last_result
            if not result:
                continue
            
            total += 1
            
            if result.status == HealthStatus.HEALTHY:
                healthy += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded += 1
            else:
                unhealthy += 1
            
            # Track dependency health
            if check.check_type == HealthCheckType.DEPENDENCY:
                dependencies[check.name] = DependencyHealth(
                    name=check.name,
                    type="service",
                    status=result.status,
                    endpoint=result.endpoint,
                    latency_ms=result.duration_ms,
                    last_success=(
                        result.timestamp
                        if result.status == HealthStatus.HEALTHY
                        else None
                    ),
                    last_failure=(
                        result.timestamp
                        if result.status == HealthStatus.UNHEALTHY
                        else None
                    ),
                    consecutive_failures=check.consecutive_failures,
                )
        
        # Determine overall status
        if unhealthy > 0:
            # Check if any critical dependencies are unhealthy
            critical_unhealthy = any(
                dep.name in self.config.critical_dependencies
                and dep.status == HealthStatus.UNHEALTHY
                for dep in dependencies.values()
            )
            status = HealthStatus.UNHEALTHY if critical_unhealthy else HealthStatus.DEGRADED
        elif degraded > 0:
            status = HealthStatus.DEGRADED
        elif healthy > 0:
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNKNOWN
        
        return AggregateHealth(
            status=status,
            total_checks=total,
            healthy_checks=healthy,
            degraded_checks=degraded,
            unhealthy_checks=unhealthy,
            dependencies=dependencies,
            uptime_percentage=self.get_uptime()["uptime_percentage"],
        )
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
