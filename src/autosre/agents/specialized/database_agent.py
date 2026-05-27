"""
DatabaseAgent — Specialized database troubleshooting agent.

This agent provides database expertise with methods for:
- Connection checks (pool status, connection limits)
- Slow query analysis (identify problematic queries)
- Replication checks (lag, sync status)

Supports multiple database types through configurable backends.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


# ----- Database Backend Protocol -----

class DatabaseBackend(Protocol):
    """Protocol for database backend implementations."""
    
    async def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        ...
    
    async def get_connection_info(self) -> dict[str, Any]:
        """Get connection pool and limit information."""
        ...
    
    async def close(self) -> None:
        """Close database connections."""
        ...


# ----- Result Data Classes -----

@dataclass
class ConnectionCheckResult:
    """Result of database connection check."""
    
    database_type: str
    host: str
    healthy: bool = True
    current_connections: int = 0
    max_connections: int = 0
    connection_utilization_percent: float = 0.0
    pool_stats: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "database_type": self.database_type,
            "host": self.host,
            "healthy": self.healthy,
            "current_connections": self.current_connections,
            "max_connections": self.max_connections,
            "connection_utilization_percent": self.connection_utilization_percent,
            "pool_stats": self.pool_stats,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


@dataclass
class SlowQueryResult:
    """Result of slow query analysis."""
    
    database_type: str
    analysis_period: str
    total_slow_queries: int = 0
    queries: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "database_type": self.database_type,
            "analysis_period": self.analysis_period,
            "total_slow_queries": self.total_slow_queries,
            "queries": self.queries,
            "patterns": self.patterns,
            "recommendations": self.recommendations,
        }


@dataclass
class ReplicationCheckResult:
    """Result of replication status check."""
    
    database_type: str
    replication_enabled: bool = False
    is_primary: bool = True
    replicas: list[dict[str, Any]] = field(default_factory=list)
    replication_lag_seconds: Optional[float] = None
    sync_state: str = "unknown"
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "database_type": self.database_type,
            "replication_enabled": self.replication_enabled,
            "is_primary": self.is_primary,
            "replicas": self.replicas,
            "replication_lag_seconds": self.replication_lag_seconds,
            "sync_state": self.sync_state,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


# ----- Database Agent Configuration -----

@dataclass
class DatabaseAgentConfig:
    """Configuration for the database agent."""
    
    database_type: str = "postgresql"  # postgresql, mysql, mongodb
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    connection_timeout: int = 10
    query_timeout: int = 30
    dry_run: bool = False
    
    # Thresholds for alerts
    connection_warning_percent: float = 80.0
    connection_critical_percent: float = 95.0
    slow_query_threshold_ms: int = 1000
    replication_lag_warning_seconds: float = 30.0
    replication_lag_critical_seconds: float = 300.0


# ----- Mock Backend for Testing -----

class MockDatabaseBackend:
    """Mock database backend for testing."""
    
    def __init__(self, config: DatabaseAgentConfig):
        self.config = config
        self._mock_connections = 45
        self._mock_max_connections = 100
    
    async def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Return mock query results."""
        logger.debug(f"[MOCK] Executing query: {query[:100]}...")
        
        # Simulate slow query results
        if "pg_stat_statements" in query or "slow" in query.lower():
            return [
                {
                    "query": "SELECT * FROM orders WHERE status = 'pending'",
                    "calls": 1500,
                    "mean_time_ms": 2500.0,
                    "total_time_ms": 3750000.0,
                },
                {
                    "query": "SELECT * FROM users u JOIN orders o ON u.id = o.user_id",
                    "calls": 500,
                    "mean_time_ms": 1200.0,
                    "total_time_ms": 600000.0,
                },
            ]
        
        # Simulate connection info
        if "pg_stat_activity" in query or "connections" in query.lower():
            return [
                {"count": self._mock_connections},
            ]
        
        # Simulate replication info
        if "pg_stat_replication" in query or "replication" in query.lower():
            return [
                {
                    "client_addr": "10.0.1.2",
                    "state": "streaming",
                    "sent_lsn": "0/3000000",
                    "replay_lsn": "0/2F00000",
                    "replay_lag_seconds": 0.5,
                },
            ]
        
        return []
    
    async def get_connection_info(self) -> dict[str, Any]:
        """Return mock connection info."""
        return {
            "current_connections": self._mock_connections,
            "max_connections": self._mock_max_connections,
            "idle_connections": 20,
            "active_connections": 25,
        }
    
    async def close(self) -> None:
        """Mock close."""
        pass


# ----- PostgreSQL Backend -----

class PostgreSQLBackend:
    """PostgreSQL database backend using asyncpg."""
    
    def __init__(self, config: DatabaseAgentConfig):
        self.config = config
        self._pool = None
    
    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.username,
                    password=self.config.password,
                    min_size=1,
                    max_size=5,
                    timeout=self.config.connection_timeout,
                )
            except ImportError:
                raise ImportError("asyncpg is required for PostgreSQL. Install with: pip install asyncpg")
        return self._pool
    
    async def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if params:
                rows = await conn.fetch(query, *params.values())
            else:
                rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    async def get_connection_info(self) -> dict[str, Any]:
        """Get connection pool and limit information."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Get max connections
            max_conn = await conn.fetchval("SHOW max_connections")
            
            # Get current connections
            current = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE state != 'idle'"
            )
            
            # Get connection breakdown
            breakdown = await conn.fetch("""
                SELECT state, count(*) as count 
                FROM pg_stat_activity 
                GROUP BY state
            """)
            
            return {
                "max_connections": int(max_conn),
                "current_connections": int(current),
                "breakdown": {row["state"]: row["count"] for row in breakdown},
            }
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


# ----- Main Database Agent -----

class DatabaseAgent:
    """Specialized database troubleshooting agent.
    
    Provides high-level troubleshooting methods that work across
    different database types.
    
    Example:
        agent = DatabaseAgent(
            database_type="postgresql",
            host="db.example.com",
            database="myapp",
        )
        result = await agent.check_connections()
        if not result.healthy:
            print("Connection issues:", result.issues)
    """
    
    def __init__(
        self,
        database_type: str = "postgresql",
        host: str = "localhost",
        port: Optional[int] = None,
        database: str = "",
        username: str = "",
        password: str = "",
        connection_timeout: int = 10,
        query_timeout: int = 30,
        dry_run: bool = False,
        config: Optional[DatabaseAgentConfig] = None,
        backend: Optional[DatabaseBackend] = None,
    ):
        """Initialize the database agent.
        
        Args:
            database_type: Type of database (postgresql, mysql, mongodb)
            host: Database host
            port: Database port (defaults based on type)
            database: Database name
            username: Database username
            password: Database password
            connection_timeout: Connection timeout in seconds
            query_timeout: Query timeout in seconds
            dry_run: If True, use mock backend
            config: Full config object (overrides other params if provided)
            backend: Custom backend implementation
        """
        if config:
            self.config = config
        else:
            # Set default port based on database type
            if port is None:
                port = {
                    "postgresql": 5432,
                    "mysql": 3306,
                    "mongodb": 27017,
                }.get(database_type, 5432)
            
            self.config = DatabaseAgentConfig(
                database_type=database_type,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                connection_timeout=connection_timeout,
                query_timeout=query_timeout,
                dry_run=dry_run,
            )
        
        # Set up backend
        if backend:
            self._backend = backend
        elif self.config.dry_run:
            self._backend = MockDatabaseBackend(self.config)
        else:
            self._backend = self._create_backend()
    
    def _create_backend(self) -> DatabaseBackend:
        """Create the appropriate backend based on database type."""
        if self.config.database_type == "postgresql":
            return PostgreSQLBackend(self.config)
        elif self.config.database_type == "mysql":
            # MySQL backend would be implemented similarly
            logger.warning("MySQL backend not fully implemented, using mock")
            return MockDatabaseBackend(self.config)
        elif self.config.database_type == "mongodb":
            # MongoDB backend would be implemented similarly
            logger.warning("MongoDB backend not fully implemented, using mock")
            return MockDatabaseBackend(self.config)
        else:
            raise ValueError(f"Unsupported database type: {self.config.database_type}")
    
    async def close(self) -> None:
        """Close database connections."""
        await self._backend.close()
    
    # ----- Main troubleshooting methods -----
    
    async def check_connections(self) -> ConnectionCheckResult:
        """Check database connection health and utilization.
        
        Analyzes:
        - Current vs maximum connections
        - Connection pool status
        - Connection states (active, idle, waiting)
        
        Returns:
            ConnectionCheckResult with connection status and issues
        """
        issues: list[str] = []
        recommendations: list[str] = []
        
        try:
            conn_info = await self._backend.get_connection_info()
            
            current = conn_info.get("current_connections", 0)
            max_conn = conn_info.get("max_connections", 100)
            
            utilization = (current / max_conn * 100) if max_conn > 0 else 0
            
            # Check utilization thresholds
            if utilization >= self.config.connection_critical_percent:
                issues.append(
                    f"Critical: Connection utilization at {utilization:.1f}% "
                    f"({current}/{max_conn})"
                )
                recommendations.append("Immediately investigate connection leaks")
                recommendations.append("Consider increasing max_connections")
            elif utilization >= self.config.connection_warning_percent:
                issues.append(
                    f"Warning: Connection utilization at {utilization:.1f}% "
                    f"({current}/{max_conn})"
                )
                recommendations.append("Monitor for connection leaks")
                recommendations.append("Review connection pooling settings")
            
            # Check for idle connections
            breakdown = conn_info.get("breakdown", {})
            idle_count = breakdown.get("idle", 0)
            if idle_count > max_conn * 0.5:
                issues.append(f"High idle connection count: {idle_count}")
                recommendations.append("Consider reducing idle timeout")
            
            healthy = len(issues) == 0 or all("Warning" in i for i in issues)
            
            return ConnectionCheckResult(
                database_type=self.config.database_type,
                host=self.config.host,
                healthy=healthy,
                current_connections=current,
                max_connections=max_conn,
                connection_utilization_percent=utilization,
                pool_stats=conn_info,
                issues=issues,
                recommendations=recommendations,
            )
            
        except Exception as e:
            return ConnectionCheckResult(
                database_type=self.config.database_type,
                host=self.config.host,
                healthy=False,
                issues=[f"Failed to check connections: {e}"],
                recommendations=["Check database connectivity"],
            )
    
    async def analyze_slow_queries(
        self,
        min_duration_ms: Optional[int] = None,
        limit: int = 20,
        since_hours: int = 24,
    ) -> SlowQueryResult:
        """Analyze slow queries in the database.
        
        Identifies queries that exceed the duration threshold and
        provides recommendations for optimization.
        
        Args:
            min_duration_ms: Minimum query duration to consider slow
                           (defaults to config threshold)
            limit: Maximum number of queries to return
            since_hours: Analysis window in hours
            
        Returns:
            SlowQueryResult with slow queries and patterns
        """
        threshold = min_duration_ms or self.config.slow_query_threshold_ms
        queries: list[dict[str, Any]] = []
        patterns: list[str] = []
        recommendations: list[str] = []
        
        try:
            if self.config.database_type == "postgresql":
                # Query pg_stat_statements for slow queries
                result = await self._backend.execute_query(f"""
                    SELECT 
                        query,
                        calls,
                        mean_exec_time as mean_time_ms,
                        total_exec_time as total_time_ms,
                        rows,
                        shared_blks_hit,
                        shared_blks_read
                    FROM pg_stat_statements
                    WHERE mean_exec_time > {threshold}
                    ORDER BY total_exec_time DESC
                    LIMIT {limit}
                """)
                
                for row in result:
                    query_text = row.get("query", "")
                    mean_time = row.get("mean_time_ms", 0)
                    
                    queries.append({
                        "query": query_text[:500],  # Truncate long queries
                        "calls": row.get("calls", 0),
                        "mean_time_ms": mean_time,
                        "total_time_ms": row.get("total_time_ms", 0),
                        "rows": row.get("rows", 0),
                    })
                    
                    # Identify patterns
                    if "SELECT *" in query_text.upper():
                        if "SELECT * anti-pattern" not in patterns:
                            patterns.append("SELECT * anti-pattern - specify columns")
                    if "WHERE" not in query_text.upper() and "SELECT" in query_text.upper():
                        if "Missing WHERE clause" not in patterns:
                            patterns.append("Missing WHERE clause - full table scans")
                    if re.search(r'LIKE\s+[\'"]%', query_text, re.IGNORECASE):
                        if "Leading wildcard LIKE" not in patterns:
                            patterns.append("Leading wildcard LIKE - cannot use index")
            
            else:
                # Mock data for other database types
                result = await self._backend.execute_query("SELECT slow queries")
                queries = result
            
            # Generate recommendations based on patterns
            if patterns:
                recommendations.append("Review queries matching identified patterns")
            if any(q.get("calls", 0) > 1000 for q in queries):
                recommendations.append("Consider caching frequently executed slow queries")
            if queries:
                recommendations.append("Check query execution plans with EXPLAIN ANALYZE")
                recommendations.append("Verify appropriate indexes exist for slow queries")
            
            return SlowQueryResult(
                database_type=self.config.database_type,
                analysis_period=f"last {since_hours} hours",
                total_slow_queries=len(queries),
                queries=queries,
                patterns=patterns,
                recommendations=recommendations,
            )
            
        except Exception as e:
            return SlowQueryResult(
                database_type=self.config.database_type,
                analysis_period=f"last {since_hours} hours",
                recommendations=[f"Failed to analyze slow queries: {e}"],
            )
    
    async def check_replication(self) -> ReplicationCheckResult:
        """Check database replication status.
        
        Analyzes:
        - Replication lag
        - Replica sync state
        - Replication health
        
        Returns:
            ReplicationCheckResult with replication status and issues
        """
        issues: list[str] = []
        recommendations: list[str] = []
        replicas: list[dict[str, Any]] = []
        replication_lag: Optional[float] = None
        sync_state = "unknown"
        is_primary = True
        replication_enabled = False
        
        try:
            if self.config.database_type == "postgresql":
                # Check if this is a primary
                result = await self._backend.execute_query(
                    "SELECT pg_is_in_recovery() as is_replica"
                )
                if result and result[0].get("is_replica"):
                    is_primary = False
                
                # Get replication status
                repl_result = await self._backend.execute_query("""
                    SELECT 
                        client_addr,
                        state,
                        sent_lsn,
                        replay_lsn,
                        EXTRACT(EPOCH FROM (now() - replay_lag)) as replay_lag_seconds
                    FROM pg_stat_replication
                """)
                
                if repl_result:
                    replication_enabled = True
                    
                    for row in repl_result:
                        lag = row.get("replay_lag_seconds", 0)
                        state = row.get("state", "unknown")
                        
                        replicas.append({
                            "client_addr": row.get("client_addr"),
                            "state": state,
                            "lag_seconds": lag,
                        })
                        
                        # Track max lag
                        if replication_lag is None or (lag and lag > replication_lag):
                            replication_lag = lag
                        
                        # Check lag thresholds
                        if lag and lag > self.config.replication_lag_critical_seconds:
                            issues.append(
                                f"Critical: Replica {row.get('client_addr')} lag "
                                f"is {lag:.1f}s"
                            )
                        elif lag and lag > self.config.replication_lag_warning_seconds:
                            issues.append(
                                f"Warning: Replica {row.get('client_addr')} lag "
                                f"is {lag:.1f}s"
                            )
                        
                        if state != "streaming":
                            issues.append(
                                f"Replica {row.get('client_addr')} in state: {state}"
                            )
                    
                    # Determine overall sync state
                    states = [r.get("state") for r in replicas]
                    if all(s == "streaming" for s in states):
                        sync_state = "streaming"
                    elif "catchup" in states:
                        sync_state = "catching up"
                    else:
                        sync_state = "degraded"
            
            else:
                # Mock data for other database types
                result = await self._backend.execute_query("SELECT replication status")
                if result:
                    replication_enabled = True
                    replicas = result
            
            # Generate recommendations
            if issues:
                if any("Critical" in i for i in issues):
                    recommendations.append("Immediately investigate replication lag")
                    recommendations.append("Check network connectivity to replicas")
                    recommendations.append("Verify replica disk I/O and CPU")
                else:
                    recommendations.append("Monitor replication lag trend")
            
            if not replication_enabled:
                recommendations.append("No replicas detected - single point of failure")
            
            return ReplicationCheckResult(
                database_type=self.config.database_type,
                replication_enabled=replication_enabled,
                is_primary=is_primary,
                replicas=replicas,
                replication_lag_seconds=replication_lag,
                sync_state=sync_state,
                issues=issues,
                recommendations=recommendations,
            )
            
        except Exception as e:
            return ReplicationCheckResult(
                database_type=self.config.database_type,
                issues=[f"Failed to check replication: {e}"],
                recommendations=["Check database connectivity"],
            )
    
    # ----- Convenience methods -----
    
    async def health_check(self) -> dict[str, Any]:
        """Perform a comprehensive health check.
        
        Runs all checks and returns a summary.
        
        Returns:
            Dictionary with overall health status and individual check results
        """
        # Run all checks concurrently
        connection_result, slow_query_result, replication_result = await asyncio.gather(
            self.check_connections(),
            self.analyze_slow_queries(limit=5),
            self.check_replication(),
        )
        
        # Determine overall health
        all_issues = (
            connection_result.issues +
            replication_result.issues
        )
        
        critical_issues = [i for i in all_issues if "Critical" in i]
        warning_issues = [i for i in all_issues if "Warning" in i]
        
        if critical_issues:
            overall_status = "critical"
        elif warning_issues:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "database_type": self.config.database_type,
            "host": self.config.host,
            "checks": {
                "connections": connection_result.to_dict(),
                "slow_queries": slow_query_result.to_dict(),
                "replication": replication_result.to_dict(),
            },
            "total_issues": len(all_issues),
            "critical_count": len(critical_issues),
            "warning_count": len(warning_issues),
        }


def create_database_agent(
    database_type: str = "postgresql",
    host: str = "localhost",
    port: Optional[int] = None,
    database: str = "",
    username: str = "",
    password: str = "",
    dry_run: bool = False,
) -> DatabaseAgent:
    """Factory function to create a database agent.
    
    Args:
        database_type: Type of database (postgresql, mysql, mongodb)
        host: Database host
        port: Database port (defaults based on type)
        database: Database name
        username: Database username
        password: Database password
        dry_run: If True, use mock backend for testing
        
    Returns:
        Configured DatabaseAgent instance
    """
    return DatabaseAgent(
        database_type=database_type,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        dry_run=dry_run,
    )
