"""
Query Performance Analysis

Provides comprehensive query performance monitoring and analysis:
- Query execution time tracking
- Slow query detection and analysis
- Query plan analysis
- Index usage optimization
- Query pattern detection
- Performance regression detection
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class QueryType(str, Enum):
    """SQL query types."""
    
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"
    OTHER = "other"


class PerformanceLevel(str, Enum):
    """Query performance level."""
    
    EXCELLENT = "excellent"      # < 10ms
    GOOD = "good"                # 10-100ms
    ACCEPTABLE = "acceptable"    # 100-500ms
    SLOW = "slow"               # 500ms-2s
    VERY_SLOW = "very_slow"     # > 2s


class ScanType(str, Enum):
    """Database scan types."""
    
    INDEX_SCAN = "index_scan"
    INDEX_ONLY_SCAN = "index_only_scan"
    BITMAP_INDEX_SCAN = "bitmap_index_scan"
    SEQ_SCAN = "seq_scan"
    PARALLEL_SEQ_SCAN = "parallel_seq_scan"


class JoinType(str, Enum):
    """Join operation types."""
    
    NESTED_LOOP = "nested_loop"
    HASH_JOIN = "hash_join"
    MERGE_JOIN = "merge_join"
    PARALLEL_HASH = "parallel_hash"


class OptimizationType(str, Enum):
    """Types of optimization recommendations."""
    
    ADD_INDEX = "add_index"
    REMOVE_INDEX = "remove_index"
    REWRITE_QUERY = "rewrite_query"
    ADD_COVERING_INDEX = "add_covering_index"
    PARTITION_TABLE = "partition_table"
    UPDATE_STATISTICS = "update_statistics"
    INCREASE_WORK_MEM = "increase_work_mem"
    ENABLE_PARALLEL = "enable_parallel"


# =============================================================================
# Configuration
# =============================================================================


class PerformanceConfig(BaseModel):
    """Performance analysis configuration."""
    
    slow_query_threshold_ms: float = Field(default=500.0, description="Slow query threshold in ms")
    very_slow_query_threshold_ms: float = Field(default=2000.0, description="Very slow query threshold in ms")
    query_sample_rate: float = Field(default=1.0, description="Query sampling rate (0.0-1.0)")
    max_query_length: int = Field(default=4096, description="Maximum query length to store")
    retention_hours: int = Field(default=168, description="Query data retention (7 days)")
    enable_explain_analyze: bool = Field(default=True, description="Enable EXPLAIN ANALYZE for slow queries")
    track_io_timing: bool = Field(default=True, description="Track I/O timing")
    track_buffer_usage: bool = Field(default=True, description="Track buffer usage")


# =============================================================================
# Query Models
# =============================================================================


class QueryFingerprint(BaseModel):
    """Normalized query fingerprint for grouping similar queries."""
    
    fingerprint_id: str = Field(description="Unique fingerprint hash")
    normalized_query: str = Field(description="Query with parameters replaced")
    query_type: QueryType
    tables: list[str] = Field(default_factory=list, description="Tables involved")
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryExecution(BaseModel):
    """Individual query execution record."""
    
    execution_id: str
    fingerprint_id: str
    original_query: str
    query_type: QueryType
    database: str
    username: str
    
    # Timing
    started_at: datetime
    duration_ms: float
    planning_time_ms: Optional[float] = None
    execution_time_ms: Optional[float] = None
    
    # Resources
    rows_returned: int = 0
    rows_affected: int = 0
    shared_blks_hit: int = 0
    shared_blks_read: int = 0
    shared_blks_written: int = 0
    temp_blks_read: int = 0
    temp_blks_written: int = 0
    blk_read_time_ms: float = 0.0
    blk_write_time_ms: float = 0.0
    
    # Performance
    performance_level: PerformanceLevel = PerformanceLevel.GOOD


class QueryPlan(BaseModel):
    """Query execution plan."""
    
    query_fingerprint_id: str
    plan_text: str = Field(description="Raw EXPLAIN output")
    plan_json: Optional[dict] = Field(default=None, description="JSON EXPLAIN output")
    
    # Plan characteristics
    total_cost: float = 0.0
    startup_cost: float = 0.0
    actual_time_ms: Optional[float] = None
    actual_rows: Optional[int] = None
    planned_rows: Optional[int] = None
    
    # Operations
    scan_types: list[ScanType] = Field(default_factory=list)
    join_types: list[JoinType] = Field(default_factory=list)
    sorts: int = 0
    hashes: int = 0
    
    # Warnings
    seq_scans_on_large_tables: list[str] = Field(default_factory=list)
    missing_indexes: list[str] = Field(default_factory=list)
    row_estimate_errors: list[dict] = Field(default_factory=list)
    
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryStatistics(BaseModel):
    """Aggregated query statistics for a fingerprint."""
    
    fingerprint_id: str
    normalized_query: str
    query_type: QueryType
    
    # Call statistics
    total_calls: int = 0
    calls_per_minute: float = 0.0
    
    # Timing statistics
    total_time_ms: float = 0.0
    mean_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0
    stddev_time_ms: float = 0.0
    p50_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    p99_time_ms: float = 0.0
    
    # Row statistics
    total_rows: int = 0
    mean_rows: float = 0.0
    
    # Buffer statistics
    shared_blks_hit: int = 0
    shared_blks_read: int = 0
    cache_hit_ratio: float = 0.0
    
    # Performance classification
    performance_level: PerformanceLevel = PerformanceLevel.GOOD
    
    # Time range
    period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SlowQueryReport(BaseModel):
    """Report on a slow query."""
    
    fingerprint_id: str
    query: str
    query_type: QueryType
    
    # Execution details
    avg_duration_ms: float
    max_duration_ms: float
    occurrences: int
    
    # Analysis
    query_plan: Optional[QueryPlan] = None
    root_causes: list[str] = Field(default_factory=list)
    optimization_suggestions: list[str] = Field(default_factory=list)
    estimated_improvement_pct: float = 0.0
    
    # Impact
    total_time_consumed_ms: float = 0.0
    pct_of_total_query_time: float = 0.0
    
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IndexRecommendation(BaseModel):
    """Index optimization recommendation."""
    
    recommendation_id: str
    recommendation_type: OptimizationType
    table_name: str
    columns: list[str]
    
    # Details
    reason: str
    affected_queries: list[str] = Field(default_factory=list)
    
    # Impact estimates
    estimated_speedup: float = 0.0
    estimated_queries_improved: int = 0
    index_size_mb: float = 0.0
    
    # DDL
    create_statement: Optional[str] = None
    drop_statement: Optional[str] = None
    
    priority: int = Field(default=5, description="1-10, higher is more important")


class PerformanceRegression(BaseModel):
    """Detected performance regression."""
    
    fingerprint_id: str
    query: str
    
    # Baseline vs current
    baseline_mean_ms: float
    current_mean_ms: float
    regression_pct: float
    
    # Detection info
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_period: str
    current_period: str
    
    # Potential causes
    potential_causes: list[str] = Field(default_factory=list)


# =============================================================================
# Query Performance Analyzer
# =============================================================================


@dataclass
class QueryPerformanceAnalyzer:
    """
    Analyzes query performance and provides optimization recommendations.
    
    Features:
    - Query fingerprinting and grouping
    - Slow query detection
    - Query plan analysis
    - Index recommendations
    - Performance regression detection
    
    Usage:
        analyzer = QueryPerformanceAnalyzer(config)
        
        # Record query executions
        await analyzer.record_execution(execution)
        
        # Get slow queries
        slow_queries = await analyzer.get_slow_queries(limit=10)
        
        # Get index recommendations
        recommendations = await analyzer.get_index_recommendations()
    """
    
    config: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Internal storage
    _fingerprints: dict[str, QueryFingerprint] = field(default_factory=dict, init=False)
    _executions: list[QueryExecution] = field(default_factory=list, init=False)
    _statistics: dict[str, QueryStatistics] = field(default_factory=dict, init=False)
    _plans: dict[str, QueryPlan] = field(default_factory=dict, init=False)
    
    def fingerprint_query(self, query: str) -> str:
        """Generate fingerprint for a query by normalizing it."""
        # Simple normalization - replace literals with placeholders
        normalized = self._normalize_query(query)
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return fingerprint
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query by replacing literals with placeholders."""
        # This is a simplified implementation
        # Real implementation would use a proper SQL parser
        import re
        
        # Remove extra whitespace
        normalized = ' '.join(query.split())
        
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        
        # Replace numeric literals
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        # Convert to lowercase
        normalized = normalized.lower()
        
        return normalized
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of SQL query."""
        query_upper = query.strip().upper()
        
        if query_upper.startswith('SELECT'):
            return QueryType.SELECT
        elif query_upper.startswith('INSERT'):
            return QueryType.INSERT
        elif query_upper.startswith('UPDATE'):
            return QueryType.UPDATE
        elif query_upper.startswith('DELETE'):
            return QueryType.DELETE
        elif any(query_upper.startswith(ddl) for ddl in ['CREATE', 'ALTER', 'DROP', 'TRUNCATE']):
            return QueryType.DDL
        else:
            return QueryType.OTHER
    
    def _classify_performance(self, duration_ms: float) -> PerformanceLevel:
        """Classify query performance based on duration."""
        if duration_ms < 10:
            return PerformanceLevel.EXCELLENT
        elif duration_ms < 100:
            return PerformanceLevel.GOOD
        elif duration_ms < 500:
            return PerformanceLevel.ACCEPTABLE
        elif duration_ms < 2000:
            return PerformanceLevel.SLOW
        else:
            return PerformanceLevel.VERY_SLOW
    
    async def record_execution(self, execution: QueryExecution):
        """Record a query execution for analysis."""
        # Store fingerprint
        if execution.fingerprint_id not in self._fingerprints:
            self._fingerprints[execution.fingerprint_id] = QueryFingerprint(
                fingerprint_id=execution.fingerprint_id,
                normalized_query=self._normalize_query(execution.original_query),
                query_type=execution.query_type,
            )
        
        self._fingerprints[execution.fingerprint_id].last_seen = datetime.now(timezone.utc)
        
        # Store execution
        self._executions.append(execution)
        
        # Update statistics
        await self._update_statistics(execution)
        
        # Analyze slow queries
        if execution.duration_ms >= self.config.slow_query_threshold_ms:
            await self._analyze_slow_query(execution)
    
    async def _update_statistics(self, execution: QueryExecution):
        """Update aggregated statistics for a query fingerprint."""
        fp_id = execution.fingerprint_id
        
        if fp_id not in self._statistics:
            self._statistics[fp_id] = QueryStatistics(
                fingerprint_id=fp_id,
                normalized_query=self._normalize_query(execution.original_query),
                query_type=execution.query_type,
            )
        
        stats = self._statistics[fp_id]
        
        # Update call count
        stats.total_calls += 1
        
        # Update timing
        stats.total_time_ms += execution.duration_ms
        stats.mean_time_ms = stats.total_time_ms / stats.total_calls
        
        if execution.duration_ms < stats.min_time_ms or stats.min_time_ms == 0:
            stats.min_time_ms = execution.duration_ms
        if execution.duration_ms > stats.max_time_ms:
            stats.max_time_ms = execution.duration_ms
        
        # Update rows
        stats.total_rows += execution.rows_returned
        stats.mean_rows = stats.total_rows / stats.total_calls
        
        # Update buffer stats
        stats.shared_blks_hit += execution.shared_blks_hit
        stats.shared_blks_read += execution.shared_blks_read
        
        total_blocks = stats.shared_blks_hit + stats.shared_blks_read
        if total_blocks > 0:
            stats.cache_hit_ratio = stats.shared_blks_hit / total_blocks
        
        # Update performance level
        stats.performance_level = self._classify_performance(stats.mean_time_ms)
        stats.period_end = datetime.now(timezone.utc)
    
    async def _analyze_slow_query(self, execution: QueryExecution):
        """Perform detailed analysis of a slow query."""
        # In a real implementation, this would run EXPLAIN ANALYZE
        pass
    
    async def get_slow_queries(
        self,
        threshold_ms: Optional[float] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> list[SlowQueryReport]:
        """Get slow query reports."""
        threshold = threshold_ms or self.config.slow_query_threshold_ms
        
        slow_fingerprints = [
            stats for stats in self._statistics.values()
            if stats.mean_time_ms >= threshold
        ]
        
        # Sort by total time consumed
        slow_fingerprints.sort(
            key=lambda s: s.total_time_ms,
            reverse=True
        )
        
        reports = []
        for stats in slow_fingerprints[:limit]:
            report = SlowQueryReport(
                fingerprint_id=stats.fingerprint_id,
                query=stats.normalized_query,
                query_type=stats.query_type,
                avg_duration_ms=stats.mean_time_ms,
                max_duration_ms=stats.max_time_ms,
                occurrences=stats.total_calls,
                total_time_consumed_ms=stats.total_time_ms,
                query_plan=self._plans.get(stats.fingerprint_id),
            )
            reports.append(report)
        
        return reports
    
    async def get_query_statistics(
        self,
        order_by: str = "total_time",
        limit: int = 50,
    ) -> list[QueryStatistics]:
        """Get query statistics ordered by specified metric."""
        stats_list = list(self._statistics.values())
        
        if order_by == "total_time":
            stats_list.sort(key=lambda s: s.total_time_ms, reverse=True)
        elif order_by == "mean_time":
            stats_list.sort(key=lambda s: s.mean_time_ms, reverse=True)
        elif order_by == "calls":
            stats_list.sort(key=lambda s: s.total_calls, reverse=True)
        elif order_by == "rows":
            stats_list.sort(key=lambda s: s.total_rows, reverse=True)
        
        return stats_list[:limit]
    
    async def get_index_recommendations(self) -> list[IndexRecommendation]:
        """Generate index recommendations based on query patterns."""
        recommendations = []
        
        # Analyze slow queries for missing indexes
        slow_queries = await self.get_slow_queries(limit=20)
        
        for query in slow_queries:
            if query.query_plan and query.query_plan.seq_scans_on_large_tables:
                for table in query.query_plan.seq_scans_on_large_tables:
                    rec = IndexRecommendation(
                        recommendation_id=f"idx_{table}_{datetime.now(timezone.utc).timestamp()}",
                        recommendation_type=OptimizationType.ADD_INDEX,
                        table_name=table,
                        columns=[],  # Would be extracted from query analysis
                        reason=f"Sequential scan on large table {table}",
                        affected_queries=[query.fingerprint_id],
                        priority=7,
                    )
                    recommendations.append(rec)
        
        return recommendations
    
    async def detect_regressions(
        self,
        baseline_hours: int = 24,
        threshold_pct: float = 25.0,
    ) -> list[PerformanceRegression]:
        """Detect performance regressions compared to baseline."""
        regressions = []
        
        # In a real implementation, this would compare current stats
        # against historical baseline
        
        return regressions
    
    async def analyze_query_plan(self, query: str) -> QueryPlan:
        """Analyze execution plan for a query."""
        fingerprint = self.fingerprint_query(query)
        
        # Simulated plan analysis
        plan = QueryPlan(
            query_fingerprint_id=fingerprint,
            plan_text="Seq Scan on users (cost=0.00..10.00 rows=100 width=32)",
            total_cost=10.0,
        )
        
        self._plans[fingerprint] = plan
        return plan
    
    def get_cache_hit_ratio(self) -> float:
        """Calculate overall cache hit ratio."""
        total_hits = sum(s.shared_blks_hit for s in self._statistics.values())
        total_reads = sum(s.shared_blks_read for s in self._statistics.values())
        total = total_hits + total_reads
        
        if total == 0:
            return 1.0
        
        return total_hits / total
    
    async def get_performance_summary(self) -> dict[str, Any]:
        """Get overall query performance summary."""
        stats_list = list(self._statistics.values())
        
        if not stats_list:
            return {
                "total_queries": 0,
                "unique_queries": 0,
                "total_time_ms": 0,
                "avg_time_ms": 0,
                "cache_hit_ratio": 1.0,
                "performance_breakdown": {},
            }
        
        total_calls = sum(s.total_calls for s in stats_list)
        total_time = sum(s.total_time_ms for s in stats_list)
        
        performance_breakdown = {}
        for level in PerformanceLevel:
            count = sum(1 for s in stats_list if s.performance_level == level)
            performance_breakdown[level.value] = count
        
        return {
            "total_queries": total_calls,
            "unique_queries": len(stats_list),
            "total_time_ms": total_time,
            "avg_time_ms": total_time / total_calls if total_calls > 0 else 0,
            "cache_hit_ratio": self.get_cache_hit_ratio(),
            "performance_breakdown": performance_breakdown,
            "slow_query_count": sum(
                1 for s in stats_list 
                if s.performance_level in [PerformanceLevel.SLOW, PerformanceLevel.VERY_SLOW]
            ),
        }


__all__ = [
    # Enums
    "QueryType",
    "PerformanceLevel",
    "ScanType",
    "JoinType",
    "OptimizationType",
    # Configuration
    "PerformanceConfig",
    # Models
    "QueryFingerprint",
    "QueryExecution",
    "QueryPlan",
    "QueryStatistics",
    "SlowQueryReport",
    "IndexRecommendation",
    "PerformanceRegression",
    # Analyzer
    "QueryPerformanceAnalyzer",
]
