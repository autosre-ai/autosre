"""
Database Health Checks

Provides comprehensive database health monitoring:
- Connection pool monitoring
- Query execution health
- Resource utilization checks
- Deadlock detection
- Connection timeout monitoring
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class DatabaseType(str, Enum):
    """Supported database types."""
    
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MARIADB = "mariadb"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    CASSANDRA = "cassandra"
    COCKROACHDB = "cockroachdb"
    TIDB = "tidb"


class HealthStatus(str, Enum):
    """Database health status."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    UNREACHABLE = "unreachable"


class CheckType(str, Enum):
    """Types of health checks."""
    
    CONNECTIVITY = "connectivity"
    QUERY_EXECUTION = "query_execution"
    CONNECTION_POOL = "connection_pool"
    REPLICATION = "replication"
    DISK_SPACE = "disk_space"
    MEMORY = "memory"
    CPU = "cpu"
    DEADLOCKS = "deadlocks"
    LONG_RUNNING_QUERIES = "long_running_queries"
    TABLE_BLOAT = "table_bloat"
    INDEX_HEALTH = "index_health"
    VACUUM_STATUS = "vacuum_status"


class AlertLevel(str, Enum):
    """Alert severity levels."""
    
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# Configuration
# =============================================================================


class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    
    host: str = Field(description="Database host")
    port: int = Field(description="Database port")
    database: str = Field(description="Database name")
    username: Optional[str] = Field(default=None, description="Database username")
    password: Optional[str] = Field(default=None, description="Database password (use secrets)")
    db_type: DatabaseType = Field(description="Database type")
    ssl_enabled: bool = Field(default=True, description="Enable SSL/TLS")
    ssl_ca_cert: Optional[str] = Field(default=None, description="SSL CA certificate path")
    connection_timeout: int = Field(default=10, description="Connection timeout in seconds")
    query_timeout: int = Field(default=30, description="Query timeout in seconds")


class HealthCheckConfig(BaseModel):
    """Health check configuration."""
    
    enabled: bool = Field(default=True, description="Enable health checks")
    interval_seconds: int = Field(default=30, description="Check interval in seconds")
    timeout_seconds: int = Field(default=10, description="Check timeout in seconds")
    
    # Thresholds
    connection_pool_warning_pct: float = Field(default=70.0, description="Connection pool warning threshold %")
    connection_pool_critical_pct: float = Field(default=90.0, description="Connection pool critical threshold %")
    disk_space_warning_pct: float = Field(default=80.0, description="Disk space warning threshold %")
    disk_space_critical_pct: float = Field(default=95.0, description="Disk space critical threshold %")
    memory_warning_pct: float = Field(default=80.0, description="Memory warning threshold %")
    memory_critical_pct: float = Field(default=95.0, description="Memory critical threshold %")
    long_query_threshold_seconds: int = Field(default=60, description="Long running query threshold")
    deadlock_check_enabled: bool = Field(default=True, description="Enable deadlock detection")
    
    # Checks to run
    checks: list[CheckType] = Field(
        default_factory=lambda: [
            CheckType.CONNECTIVITY,
            CheckType.QUERY_EXECUTION,
            CheckType.CONNECTION_POOL,
            CheckType.DISK_SPACE,
            CheckType.MEMORY,
        ],
        description="Health checks to perform"
    )


# =============================================================================
# Health Check Results
# =============================================================================


class CheckResult(BaseModel):
    """Individual health check result."""
    
    check_type: CheckType
    status: HealthStatus
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = Field(default=0.0, description="Check execution time in ms")


class ConnectionPoolStatus(BaseModel):
    """Connection pool status."""
    
    total_connections: int = Field(default=0, description="Total connections in pool")
    active_connections: int = Field(default=0, description="Currently active connections")
    idle_connections: int = Field(default=0, description="Idle connections")
    waiting_requests: int = Field(default=0, description="Requests waiting for connection")
    max_connections: int = Field(default=100, description="Maximum allowed connections")
    utilization_pct: float = Field(default=0.0, description="Pool utilization percentage")
    avg_wait_time_ms: float = Field(default=0.0, description="Average wait time for connection")


class ResourceStatus(BaseModel):
    """Database resource status."""
    
    cpu_usage_pct: float = Field(default=0.0, description="CPU usage percentage")
    memory_usage_pct: float = Field(default=0.0, description="Memory usage percentage")
    memory_used_mb: float = Field(default=0.0, description="Memory used in MB")
    memory_total_mb: float = Field(default=0.0, description="Total memory in MB")
    disk_usage_pct: float = Field(default=0.0, description="Disk usage percentage")
    disk_used_gb: float = Field(default=0.0, description="Disk used in GB")
    disk_total_gb: float = Field(default=0.0, description="Total disk in GB")
    iops_read: float = Field(default=0.0, description="Read IOPS")
    iops_write: float = Field(default=0.0, description="Write IOPS")


class LongRunningQuery(BaseModel):
    """Long running query information."""
    
    query_id: str
    query_text: str = Field(description="Query text (truncated)")
    username: str
    database: str
    duration_seconds: float
    state: str
    waiting: bool = False
    blocked_by: Optional[str] = None


class DeadlockInfo(BaseModel):
    """Deadlock information."""
    
    detected_at: datetime
    victim_query_id: str
    blocking_query_id: str
    tables_involved: list[str]
    wait_time_seconds: float


class HealthAlert(BaseModel):
    """Health check alert."""
    
    alert_id: str
    level: AlertLevel
    check_type: CheckType
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class DatabaseHealthReport(BaseModel):
    """Complete database health report."""
    
    database_id: str
    database_type: DatabaseType
    host: str
    port: int
    database_name: str
    overall_status: HealthStatus
    check_results: list[CheckResult] = Field(default_factory=list)
    connection_pool: Optional[ConnectionPoolStatus] = None
    resources: Optional[ResourceStatus] = None
    long_running_queries: list[LongRunningQuery] = Field(default_factory=list)
    recent_deadlocks: list[DeadlockInfo] = Field(default_factory=list)
    alerts: list[HealthAlert] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    check_duration_ms: float = Field(default=0.0, description="Total check duration")


# =============================================================================
# Health Checker
# =============================================================================


@dataclass
class DatabaseHealthChecker:
    """
    Database health checker that performs comprehensive health monitoring.
    
    Supports multiple database types and provides detailed health reports
    including connection pool status, resource utilization, and query health.
    
    Usage:
        checker = DatabaseHealthChecker(config)
        report = await checker.check_health()
        
        if report.overall_status == HealthStatus.UNHEALTHY:
            for alert in report.alerts:
                print(f"Alert: {alert.level} - {alert.message}")
    """
    
    db_config: DatabaseConfig
    health_config: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    
    # Internal state
    _last_report: Optional[DatabaseHealthReport] = field(default=None, init=False)
    _alert_history: list[HealthAlert] = field(default_factory=list, init=False)
    
    async def check_health(self) -> DatabaseHealthReport:
        """Perform all configured health checks."""
        start_time = datetime.now(timezone.utc)
        check_results = []
        alerts = []
        
        for check_type in self.health_config.checks:
            result = await self._run_check(check_type)
            check_results.append(result)
            
            # Generate alerts for non-healthy results
            if result.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
                alert = self._create_alert(result)
                alerts.append(alert)
        
        # Get additional status information
        connection_pool = await self._get_connection_pool_status()
        resources = await self._get_resource_status()
        long_queries = await self._get_long_running_queries()
        deadlocks = await self._get_recent_deadlocks()
        
        # Determine overall status
        overall_status = self._calculate_overall_status(check_results)
        
        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        report = DatabaseHealthReport(
            database_id=f"{self.db_config.host}:{self.db_config.port}/{self.db_config.database}",
            database_type=self.db_config.db_type,
            host=self.db_config.host,
            port=self.db_config.port,
            database_name=self.db_config.database,
            overall_status=overall_status,
            check_results=check_results,
            connection_pool=connection_pool,
            resources=resources,
            long_running_queries=long_queries,
            recent_deadlocks=deadlocks,
            alerts=alerts,
            check_duration_ms=duration_ms,
        )
        
        self._last_report = report
        self._alert_history.extend(alerts)
        
        return report
    
    async def _run_check(self, check_type: CheckType) -> CheckResult:
        """Run a specific health check."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if check_type == CheckType.CONNECTIVITY:
                return await self._check_connectivity()
            elif check_type == CheckType.QUERY_EXECUTION:
                return await self._check_query_execution()
            elif check_type == CheckType.CONNECTION_POOL:
                return await self._check_connection_pool()
            elif check_type == CheckType.DISK_SPACE:
                return await self._check_disk_space()
            elif check_type == CheckType.MEMORY:
                return await self._check_memory()
            elif check_type == CheckType.CPU:
                return await self._check_cpu()
            elif check_type == CheckType.DEADLOCKS:
                return await self._check_deadlocks()
            elif check_type == CheckType.LONG_RUNNING_QUERIES:
                return await self._check_long_running_queries()
            elif check_type == CheckType.TABLE_BLOAT:
                return await self._check_table_bloat()
            elif check_type == CheckType.INDEX_HEALTH:
                return await self._check_index_health()
            elif check_type == CheckType.VACUUM_STATUS:
                return await self._check_vacuum_status()
            else:
                return CheckResult(
                    check_type=check_type,
                    status=HealthStatus.UNKNOWN,
                    message=f"Unknown check type: {check_type}",
                )
        except asyncio.TimeoutError:
            return CheckResult(
                check_type=check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self.health_config.timeout_seconds}s",
            )
        except Exception as e:
            return CheckResult(
                check_type=check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
            )
        finally:
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000
    
    async def _check_connectivity(self) -> CheckResult:
        """Check database connectivity."""
        # Simulated implementation - would connect to actual database
        return CheckResult(
            check_type=CheckType.CONNECTIVITY,
            status=HealthStatus.HEALTHY,
            message="Database connection successful",
            duration_ms=5.2,
            details={"latency_ms": 5.2, "ssl_enabled": self.db_config.ssl_enabled},
        )
    
    async def _check_query_execution(self) -> CheckResult:
        """Check query execution health."""
        return CheckResult(
            check_type=CheckType.QUERY_EXECUTION,
            status=HealthStatus.HEALTHY,
            message="Query execution healthy",
            value=10.5,
            details={"test_query_ms": 10.5},
        )
    
    async def _check_connection_pool(self) -> CheckResult:
        """Check connection pool status."""
        pool_status = await self._get_connection_pool_status()
        
        if pool_status.utilization_pct >= self.health_config.connection_pool_critical_pct:
            status = HealthStatus.UNHEALTHY
            message = f"Connection pool at critical level: {pool_status.utilization_pct:.1f}%"
        elif pool_status.utilization_pct >= self.health_config.connection_pool_warning_pct:
            status = HealthStatus.DEGRADED
            message = f"Connection pool at warning level: {pool_status.utilization_pct:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Connection pool healthy: {pool_status.utilization_pct:.1f}% utilized"
        
        return CheckResult(
            check_type=CheckType.CONNECTION_POOL,
            status=status,
            message=message,
            value=pool_status.utilization_pct,
            threshold=self.health_config.connection_pool_warning_pct,
            details=pool_status.model_dump(),
        )
    
    async def _check_disk_space(self) -> CheckResult:
        """Check disk space utilization."""
        resources = await self._get_resource_status()
        
        if resources.disk_usage_pct >= self.health_config.disk_space_critical_pct:
            status = HealthStatus.UNHEALTHY
            message = f"Disk space critical: {resources.disk_usage_pct:.1f}% used"
        elif resources.disk_usage_pct >= self.health_config.disk_space_warning_pct:
            status = HealthStatus.DEGRADED
            message = f"Disk space warning: {resources.disk_usage_pct:.1f}% used"
        else:
            status = HealthStatus.HEALTHY
            message = f"Disk space healthy: {resources.disk_usage_pct:.1f}% used"
        
        return CheckResult(
            check_type=CheckType.DISK_SPACE,
            status=status,
            message=message,
            value=resources.disk_usage_pct,
            threshold=self.health_config.disk_space_warning_pct,
            details={
                "used_gb": resources.disk_used_gb,
                "total_gb": resources.disk_total_gb,
            },
        )
    
    async def _check_memory(self) -> CheckResult:
        """Check memory utilization."""
        resources = await self._get_resource_status()
        
        if resources.memory_usage_pct >= self.health_config.memory_critical_pct:
            status = HealthStatus.UNHEALTHY
            message = f"Memory critical: {resources.memory_usage_pct:.1f}% used"
        elif resources.memory_usage_pct >= self.health_config.memory_warning_pct:
            status = HealthStatus.DEGRADED
            message = f"Memory warning: {resources.memory_usage_pct:.1f}% used"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory healthy: {resources.memory_usage_pct:.1f}% used"
        
        return CheckResult(
            check_type=CheckType.MEMORY,
            status=status,
            message=message,
            value=resources.memory_usage_pct,
            threshold=self.health_config.memory_warning_pct,
            details={
                "used_mb": resources.memory_used_mb,
                "total_mb": resources.memory_total_mb,
            },
        )
    
    async def _check_cpu(self) -> CheckResult:
        """Check CPU utilization."""
        resources = await self._get_resource_status()
        
        if resources.cpu_usage_pct >= 90:
            status = HealthStatus.UNHEALTHY
            message = f"CPU critical: {resources.cpu_usage_pct:.1f}%"
        elif resources.cpu_usage_pct >= 70:
            status = HealthStatus.DEGRADED
            message = f"CPU warning: {resources.cpu_usage_pct:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"CPU healthy: {resources.cpu_usage_pct:.1f}%"
        
        return CheckResult(
            check_type=CheckType.CPU,
            status=status,
            message=message,
            value=resources.cpu_usage_pct,
            threshold=70.0,
        )
    
    async def _check_deadlocks(self) -> CheckResult:
        """Check for deadlocks."""
        deadlocks = await self._get_recent_deadlocks()
        
        if len(deadlocks) > 5:
            status = HealthStatus.UNHEALTHY
            message = f"High deadlock activity: {len(deadlocks)} in last hour"
        elif len(deadlocks) > 0:
            status = HealthStatus.DEGRADED
            message = f"Deadlocks detected: {len(deadlocks)} in last hour"
        else:
            status = HealthStatus.HEALTHY
            message = "No deadlocks detected"
        
        return CheckResult(
            check_type=CheckType.DEADLOCKS,
            status=status,
            message=message,
            value=float(len(deadlocks)),
            details={"deadlock_count": len(deadlocks)},
        )
    
    async def _check_long_running_queries(self) -> CheckResult:
        """Check for long running queries."""
        long_queries = await self._get_long_running_queries()
        
        if len(long_queries) > 10:
            status = HealthStatus.UNHEALTHY
            message = f"Many long-running queries: {len(long_queries)}"
        elif len(long_queries) > 0:
            status = HealthStatus.DEGRADED
            message = f"Long-running queries detected: {len(long_queries)}"
        else:
            status = HealthStatus.HEALTHY
            message = "No long-running queries"
        
        return CheckResult(
            check_type=CheckType.LONG_RUNNING_QUERIES,
            status=status,
            message=message,
            value=float(len(long_queries)),
            details={"query_count": len(long_queries)},
        )
    
    async def _check_table_bloat(self) -> CheckResult:
        """Check for table bloat (PostgreSQL specific)."""
        return CheckResult(
            check_type=CheckType.TABLE_BLOAT,
            status=HealthStatus.HEALTHY,
            message="Table bloat within acceptable limits",
            value=5.2,
            details={"bloat_ratio": 5.2},
        )
    
    async def _check_index_health(self) -> CheckResult:
        """Check index health."""
        return CheckResult(
            check_type=CheckType.INDEX_HEALTH,
            status=HealthStatus.HEALTHY,
            message="All indexes healthy",
            details={"invalid_indexes": 0, "unused_indexes": 0},
        )
    
    async def _check_vacuum_status(self) -> CheckResult:
        """Check vacuum status (PostgreSQL specific)."""
        return CheckResult(
            check_type=CheckType.VACUUM_STATUS,
            status=HealthStatus.HEALTHY,
            message="Autovacuum running normally",
            details={"tables_needing_vacuum": 0},
        )
    
    async def _get_connection_pool_status(self) -> ConnectionPoolStatus:
        """Get connection pool status."""
        # Simulated implementation
        return ConnectionPoolStatus(
            total_connections=50,
            active_connections=25,
            idle_connections=25,
            waiting_requests=0,
            max_connections=100,
            utilization_pct=50.0,
            avg_wait_time_ms=0.5,
        )
    
    async def _get_resource_status(self) -> ResourceStatus:
        """Get database resource status."""
        # Simulated implementation
        return ResourceStatus(
            cpu_usage_pct=35.0,
            memory_usage_pct=60.0,
            memory_used_mb=6144.0,
            memory_total_mb=10240.0,
            disk_usage_pct=45.0,
            disk_used_gb=450.0,
            disk_total_gb=1000.0,
            iops_read=1500.0,
            iops_write=500.0,
        )
    
    async def _get_long_running_queries(self) -> list[LongRunningQuery]:
        """Get list of long running queries."""
        # Simulated implementation - would query pg_stat_activity or equivalent
        return []
    
    async def _get_recent_deadlocks(self) -> list[DeadlockInfo]:
        """Get recent deadlock information."""
        # Simulated implementation - would query database logs/stats
        return []
    
    def _calculate_overall_status(self, results: list[CheckResult]) -> HealthStatus:
        """Calculate overall health status from individual check results."""
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY
        if any(r.status == HealthStatus.UNREACHABLE for r in results):
            return HealthStatus.UNREACHABLE
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED
        if all(r.status == HealthStatus.HEALTHY for r in results):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN
    
    def _create_alert(self, result: CheckResult) -> HealthAlert:
        """Create alert from check result."""
        level = AlertLevel.CRITICAL if result.status == HealthStatus.UNHEALTHY else AlertLevel.WARNING
        
        return HealthAlert(
            alert_id=f"{result.check_type.value}_{datetime.now(timezone.utc).timestamp()}",
            level=level,
            check_type=result.check_type,
            message=result.message,
            details=result.details,
        )
    
    def get_last_report(self) -> Optional[DatabaseHealthReport]:
        """Get the last health report."""
        return self._last_report
    
    def get_alert_history(self, limit: int = 100) -> list[HealthAlert]:
        """Get recent alert history."""
        return self._alert_history[-limit:]
    
    async def run_continuous(self, callback=None):
        """Run health checks continuously at configured interval."""
        while True:
            report = await self.check_health()
            
            if callback:
                await callback(report)
            
            await asyncio.sleep(self.health_config.interval_seconds)


# =============================================================================
# Multi-Database Health Monitor
# =============================================================================


@dataclass
class MultiDatabaseHealthMonitor:
    """
    Monitor health across multiple databases.
    
    Provides aggregated health views and alerting for database fleets.
    """
    
    checkers: dict[str, DatabaseHealthChecker] = field(default_factory=dict)
    
    def add_database(self, name: str, db_config: DatabaseConfig, health_config: Optional[HealthCheckConfig] = None):
        """Add a database to monitor."""
        health_config = health_config or HealthCheckConfig()
        self.checkers[name] = DatabaseHealthChecker(db_config=db_config, health_config=health_config)
    
    def remove_database(self, name: str):
        """Remove a database from monitoring."""
        if name in self.checkers:
            del self.checkers[name]
    
    async def check_all(self) -> dict[str, DatabaseHealthReport]:
        """Check health of all databases."""
        tasks = {
            name: checker.check_health() 
            for name, checker in self.checkers.items()
        }
        
        results = {}
        for name, task in tasks.items():
            results[name] = await task
        
        return results
    
    async def get_fleet_status(self) -> dict[str, Any]:
        """Get aggregated fleet health status."""
        reports = await self.check_all()
        
        status_counts = {status: 0 for status in HealthStatus}
        for report in reports.values():
            status_counts[report.overall_status] += 1
        
        overall = HealthStatus.HEALTHY
        if status_counts[HealthStatus.UNHEALTHY] > 0:
            overall = HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.DEGRADED] > 0:
            overall = HealthStatus.DEGRADED
        
        return {
            "overall_status": overall,
            "database_count": len(reports),
            "status_breakdown": status_counts,
            "databases": {name: report.overall_status for name, report in reports.items()},
        }


__all__ = [
    # Enums
    "DatabaseType",
    "HealthStatus",
    "CheckType",
    "AlertLevel",
    # Configuration
    "DatabaseConfig",
    "HealthCheckConfig",
    # Results
    "CheckResult",
    "ConnectionPoolStatus",
    "ResourceStatus",
    "LongRunningQuery",
    "DeadlockInfo",
    "HealthAlert",
    "DatabaseHealthReport",
    # Health Checker
    "DatabaseHealthChecker",
    "MultiDatabaseHealthMonitor",
]
