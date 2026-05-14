"""
Span Analyzer for AutoSRE V2.

Analyzes spans to identify bottlenecks, performance issues, and critical paths.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from .models import Span, Trace, SpanKind, SpanStatus

logger = get_logger(__name__)


class BottleneckType(str, Enum):
    """Type of performance bottleneck."""
    
    HIGH_LATENCY = "high_latency"  # Span takes too long
    SERIAL_CALLS = "serial_calls"  # Sequential calls that could be parallel
    N_PLUS_ONE = "n_plus_one"  # Multiple similar calls in loop
    DEEP_NESTING = "deep_nesting"  # Too many levels of nesting
    ERROR_RATE = "error_rate"  # High error rate
    TIMEOUT = "timeout"  # Timeouts or near-timeouts
    RETRY_STORM = "retry_storm"  # Excessive retries
    HOT_PATH = "hot_path"  # Frequently called path
    RESOURCE_CONTENTION = "resource_contention"  # Waiting for resources


@dataclass
class AnalyzerConfig:
    """Configuration for span analysis."""
    
    # Latency thresholds
    latency_p50_threshold_ms: float = 100.0
    latency_p95_threshold_ms: float = 500.0
    latency_p99_threshold_ms: float = 1000.0
    
    # Error thresholds
    error_rate_threshold: float = 0.05  # 5%
    
    # N+1 detection
    n_plus_one_min_calls: int = 5
    n_plus_one_similarity_threshold: float = 0.8
    
    # Nesting
    max_depth_threshold: int = 10
    
    # Retry detection
    retry_threshold: int = 3
    
    # Analysis settings
    min_samples_for_statistics: int = 10
    outlier_std_multiplier: float = 3.0


@dataclass
class SpanStatistics:
    """Statistics for a span or operation."""
    
    name: str
    service: str
    
    # Counts
    total_count: int
    error_count: int
    
    # Latency distribution
    latency_min_ms: float
    latency_max_ms: float
    latency_mean_ms: float
    latency_median_ms: float
    latency_std_ms: float
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    
    # Time range
    first_seen: datetime
    last_seen: datetime
    
    # Derived metrics
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_count == 0:
            return 0.0
        return self.error_count / self.total_count
    
    @property
    def throughput_per_second(self) -> float:
        """Calculate approximate throughput."""
        duration = (self.last_seen - self.first_seen).total_seconds()
        if duration <= 0:
            return 0.0
        return self.total_count / duration
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "service": self.service,
            "total_count": self.total_count,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "latency": {
                "min_ms": self.latency_min_ms,
                "max_ms": self.latency_max_ms,
                "mean_ms": self.latency_mean_ms,
                "median_ms": self.latency_median_ms,
                "std_ms": self.latency_std_ms,
                "p50_ms": self.latency_p50_ms,
                "p90_ms": self.latency_p90_ms,
                "p95_ms": self.latency_p95_ms,
                "p99_ms": self.latency_p99_ms,
            },
            "throughput_per_second": self.throughput_per_second,
        }


@dataclass
class OperationProfile:
    """Performance profile for an operation."""
    
    name: str
    service: str
    statistics: SpanStatistics
    
    # Relationships
    callers: dict[str, int] = field(default_factory=dict)  # caller -> count
    callees: dict[str, int] = field(default_factory=dict)  # callee -> count
    
    # Common attributes
    common_attributes: dict[str, dict[str, int]] = field(default_factory=dict)
    
    # Performance characteristics
    is_entry_point: bool = False
    is_leaf: bool = False
    avg_child_count: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "service": self.service,
            "statistics": self.statistics.to_dict(),
            "callers": self.callers,
            "callees": self.callees,
            "is_entry_point": self.is_entry_point,
            "is_leaf": self.is_leaf,
            "avg_child_count": self.avg_child_count,
        }


@dataclass
class Bottleneck:
    """A detected performance bottleneck."""
    
    type: BottleneckType
    severity: float  # 0-1 score
    
    # Location
    service: str
    operation: str
    span_ids: list[str] = field(default_factory=list)
    
    # Details
    description: str = ""
    impact_ms: float = 0.0  # Estimated impact on latency
    recommendation: str = ""
    
    # Evidence
    evidence: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "service": self.service,
            "operation": self.operation,
            "description": self.description,
            "impact_ms": self.impact_ms,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }


@dataclass
class CriticalPath:
    """The critical path through a trace."""
    
    spans: list[Span]
    total_duration_ms: float
    
    # Breakdown
    service_breakdown: dict[str, float] = field(default_factory=dict)  # service -> ms
    operation_breakdown: dict[str, float] = field(default_factory=dict)  # operation -> ms
    
    # Issues
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    
    @property
    def span_count(self) -> int:
        return len(self.spans)
    
    @property
    def services(self) -> list[str]:
        return list(self.service_breakdown.keys())
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "span_count": self.span_count,
            "total_duration_ms": self.total_duration_ms,
            "services": self.services,
            "service_breakdown": self.service_breakdown,
            "operation_breakdown": self.operation_breakdown,
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "spans": [s.span_id for s in self.spans],
        }


@dataclass
class AnalysisResult:
    """Result of trace analysis."""
    
    # Summary statistics
    trace_count: int
    span_count: int
    service_count: int
    
    # Operation profiles
    operation_profiles: dict[str, OperationProfile]
    
    # Critical paths
    critical_paths: list[CriticalPath]
    
    # Detected issues
    bottlenecks: list[Bottleneck]
    
    # Time range
    analysis_start: datetime
    analysis_end: datetime
    processing_time_ms: float
    
    def get_top_bottlenecks(self, limit: int = 10) -> list[Bottleneck]:
        """Get top bottlenecks by severity."""
        return sorted(self.bottlenecks, key=lambda b: -b.severity)[:limit]
    
    def get_slowest_operations(self, limit: int = 10) -> list[OperationProfile]:
        """Get slowest operations by P95 latency."""
        profiles = list(self.operation_profiles.values())
        return sorted(profiles, key=lambda p: -p.statistics.latency_p95_ms)[:limit]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_count": self.trace_count,
            "span_count": self.span_count,
            "service_count": self.service_count,
            "operation_profiles": {k: v.to_dict() for k, v in self.operation_profiles.items()},
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "critical_paths": [cp.to_dict() for cp in self.critical_paths],
            "analysis_start": self.analysis_start.isoformat(),
            "analysis_end": self.analysis_end.isoformat(),
            "processing_time_ms": self.processing_time_ms,
        }


class SpanAnalyzer:
    """
    Analyzer for distributed traces and spans.
    
    Identifies performance issues, bottlenecks, and patterns.
    
    Example:
        analyzer = SpanAnalyzer()
        result = analyzer.analyze(traces)
        
        for bottleneck in result.get_top_bottlenecks():
            print(f"{bottleneck.type}: {bottleneck.description}")
    """
    
    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or AnalyzerConfig()
    
    def analyze(
        self,
        traces: Sequence[Trace],
    ) -> AnalysisResult:
        """
        Analyze a collection of traces.
        
        Returns comprehensive analysis including:
        - Operation statistics
        - Detected bottlenecks
        - Critical path analysis
        """
        import time
        start_time = time.time()
        
        # Collect all spans
        all_spans: list[Span] = []
        for trace in traces:
            all_spans.extend(trace.spans)
        
        # Build operation profiles
        profiles = self._build_operation_profiles(traces)
        
        # Analyze critical paths
        critical_paths = [self._analyze_critical_path(trace) for trace in traces]
        critical_paths = [cp for cp in critical_paths if cp]
        
        # Detect bottlenecks
        bottlenecks = []
        bottlenecks.extend(self._detect_high_latency(profiles))
        bottlenecks.extend(self._detect_n_plus_one(traces))
        bottlenecks.extend(self._detect_error_issues(profiles))
        bottlenecks.extend(self._detect_serial_calls(traces))
        bottlenecks.extend(self._detect_deep_nesting(traces))
        
        # Calculate time range
        if all_spans:
            analysis_start = min(s.start_time for s in all_spans)
            analysis_end = max(s.end_time for s in all_spans)
        else:
            analysis_start = analysis_end = datetime.now(timezone.utc)
        
        processing_time = (time.time() - start_time) * 1000
        
        return AnalysisResult(
            trace_count=len(traces),
            span_count=len(all_spans),
            service_count=len({s.service_name for s in all_spans}),
            operation_profiles=profiles,
            critical_paths=critical_paths[:100],  # Limit stored paths
            bottlenecks=bottlenecks,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            processing_time_ms=processing_time,
        )
    
    def _build_operation_profiles(
        self,
        traces: Sequence[Trace],
    ) -> dict[str, OperationProfile]:
        """Build performance profiles for each operation."""
        # Group spans by operation
        spans_by_op: dict[str, list[Span]] = defaultdict(list)
        
        for trace in traces:
            for span in trace.spans:
                key = f"{span.service_name}:{span.name}"
                spans_by_op[key].append(span)
        
        # Calculate profiles
        profiles = {}
        
        for key, spans in spans_by_op.items():
            if len(spans) < 2:
                continue
            
            service, operation = key.split(":", 1)
            
            # Calculate statistics
            durations = [s.duration_ms for s in spans]
            errors = [s for s in spans if s.is_error]
            
            sorted_durations = sorted(durations)
            n = len(sorted_durations)
            
            stats = SpanStatistics(
                name=operation,
                service=service,
                total_count=len(spans),
                error_count=len(errors),
                latency_min_ms=min(durations),
                latency_max_ms=max(durations),
                latency_mean_ms=statistics.mean(durations),
                latency_median_ms=statistics.median(durations),
                latency_std_ms=statistics.stdev(durations) if n > 1 else 0,
                latency_p50_ms=sorted_durations[n // 2],
                latency_p90_ms=sorted_durations[int(n * 0.9)],
                latency_p95_ms=sorted_durations[int(n * 0.95)],
                latency_p99_ms=sorted_durations[int(n * 0.99)],
                first_seen=min(s.start_time for s in spans),
                last_seen=max(s.end_time for s in spans),
            )
            
            # Track callers and callees
            callers: dict[str, int] = defaultdict(int)
            callees: dict[str, int] = defaultdict(int)
            child_counts = []
            
            for trace in traces:
                span_map = {s.span_id: s for s in trace.spans}
                
                for span in trace.spans:
                    if f"{span.service_name}:{span.name}" != key:
                        continue
                    
                    # Find parent (caller)
                    if span.parent_span_id and span.parent_span_id in span_map:
                        parent = span_map[span.parent_span_id]
                        caller_key = f"{parent.service_name}:{parent.name}"
                        callers[caller_key] += 1
                    
                    # Find children (callees)
                    children = [s for s in trace.spans if s.parent_span_id == span.span_id]
                    child_counts.append(len(children))
                    
                    for child in children:
                        callee_key = f"{child.service_name}:{child.name}"
                        callees[callee_key] += 1
            
            profiles[key] = OperationProfile(
                name=operation,
                service=service,
                statistics=stats,
                callers=dict(callers),
                callees=dict(callees),
                is_entry_point=len(callers) == 0,
                is_leaf=len(callees) == 0,
                avg_child_count=statistics.mean(child_counts) if child_counts else 0,
            )
        
        return profiles
    
    def _analyze_critical_path(self, trace: Trace) -> Optional[CriticalPath]:
        """Analyze the critical path of a single trace."""
        path_spans = trace.get_critical_path()
        
        if not path_spans:
            return None
        
        total_duration = sum(s.duration_ms for s in path_spans)
        
        # Breakdown by service
        service_breakdown: dict[str, float] = defaultdict(float)
        operation_breakdown: dict[str, float] = defaultdict(float)
        
        for span in path_spans:
            service_breakdown[span.service_name] += span.duration_ms
            operation_breakdown[span.name] += span.duration_ms
        
        return CriticalPath(
            spans=path_spans,
            total_duration_ms=total_duration,
            service_breakdown=dict(service_breakdown),
            operation_breakdown=dict(operation_breakdown),
        )
    
    def _detect_high_latency(
        self,
        profiles: dict[str, OperationProfile],
    ) -> list[Bottleneck]:
        """Detect high-latency operations."""
        bottlenecks = []
        
        for key, profile in profiles.items():
            stats = profile.statistics
            
            # Check against thresholds
            if stats.latency_p99_ms > self.config.latency_p99_threshold_ms:
                severity = min(1.0, stats.latency_p99_ms / (self.config.latency_p99_threshold_ms * 3))
                
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.HIGH_LATENCY,
                    severity=severity,
                    service=profile.service,
                    operation=profile.name,
                    description=f"P99 latency ({stats.latency_p99_ms:.1f}ms) exceeds threshold ({self.config.latency_p99_threshold_ms:.1f}ms)",
                    impact_ms=stats.latency_p99_ms - self.config.latency_p99_threshold_ms,
                    recommendation="Consider caching, query optimization, or horizontal scaling",
                    evidence={
                        "p50_ms": stats.latency_p50_ms,
                        "p95_ms": stats.latency_p95_ms,
                        "p99_ms": stats.latency_p99_ms,
                        "sample_count": stats.total_count,
                    },
                ))
            elif stats.latency_p95_ms > self.config.latency_p95_threshold_ms:
                severity = min(0.7, stats.latency_p95_ms / (self.config.latency_p95_threshold_ms * 2))
                
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.HIGH_LATENCY,
                    severity=severity,
                    service=profile.service,
                    operation=profile.name,
                    description=f"P95 latency ({stats.latency_p95_ms:.1f}ms) exceeds threshold",
                    impact_ms=stats.latency_p95_ms - self.config.latency_p95_threshold_ms,
                    recommendation="Review slow code paths and optimize hot spots",
                    evidence={
                        "p50_ms": stats.latency_p50_ms,
                        "p95_ms": stats.latency_p95_ms,
                        "sample_count": stats.total_count,
                    },
                ))
        
        return bottlenecks
    
    def _detect_n_plus_one(
        self,
        traces: Sequence[Trace],
    ) -> list[Bottleneck]:
        """Detect N+1 query patterns."""
        bottlenecks = []
        
        for trace in traces:
            # Group spans by parent
            spans_by_parent: dict[str, list[Span]] = defaultdict(list)
            
            for span in trace.spans:
                if span.parent_span_id:
                    spans_by_parent[span.parent_span_id].append(span)
            
            # Check each parent's children for N+1 pattern
            for parent_id, children in spans_by_parent.items():
                if len(children) < self.config.n_plus_one_min_calls:
                    continue
                
                # Group by operation name
                by_operation: dict[str, list[Span]] = defaultdict(list)
                for span in children:
                    by_operation[span.name].append(span)
                
                for operation, op_spans in by_operation.items():
                    if len(op_spans) < self.config.n_plus_one_min_calls:
                        continue
                    
                    # Check if these are similar calls (likely N+1)
                    if self._are_similar_spans(op_spans):
                        total_time = sum(s.duration_ms for s in op_spans)
                        
                        parent_span = trace.get_span(parent_id)
                        parent_name = parent_span.name if parent_span else "unknown"
                        service = op_spans[0].service_name
                        
                        severity = min(1.0, len(op_spans) / 20)  # More calls = higher severity
                        
                        bottlenecks.append(Bottleneck(
                            type=BottleneckType.N_PLUS_ONE,
                            severity=severity,
                            service=service,
                            operation=operation,
                            span_ids=[s.span_id for s in op_spans],
                            description=f"N+1 pattern detected: {len(op_spans)} similar calls to {operation} from {parent_name}",
                            impact_ms=total_time,
                            recommendation="Consider batching these calls or using eager loading",
                            evidence={
                                "call_count": len(op_spans),
                                "total_time_ms": total_time,
                                "avg_time_ms": total_time / len(op_spans),
                                "parent_operation": parent_name,
                            },
                        ))
        
        return bottlenecks
    
    def _are_similar_spans(self, spans: list[Span]) -> bool:
        """Check if spans are similar (indicating N+1 pattern)."""
        if len(spans) < 2:
            return False
        
        # Check if operations are identical
        operations = {s.name for s in spans}
        if len(operations) != 1:
            return False
        
        # Check service is same
        services = {s.service_name for s in spans}
        if len(services) != 1:
            return False
        
        # Check durations are similar (within 10x of each other)
        durations = [s.duration_ms for s in spans]
        min_d, max_d = min(durations), max(durations)
        
        if max_d > 0 and min_d / max_d < 0.1:
            return False  # Too much variation
        
        return True
    
    def _detect_error_issues(
        self,
        profiles: dict[str, OperationProfile],
    ) -> list[Bottleneck]:
        """Detect operations with high error rates."""
        bottlenecks = []
        
        for key, profile in profiles.items():
            stats = profile.statistics
            
            if stats.error_rate > self.config.error_rate_threshold:
                severity = min(1.0, stats.error_rate * 10)  # 10% error = severity 1.0
                
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.ERROR_RATE,
                    severity=severity,
                    service=profile.service,
                    operation=profile.name,
                    description=f"High error rate: {stats.error_rate * 100:.1f}% ({stats.error_count}/{stats.total_count} calls failed)",
                    recommendation="Review error logs and add proper error handling",
                    evidence={
                        "error_rate": stats.error_rate,
                        "error_count": stats.error_count,
                        "total_count": stats.total_count,
                    },
                ))
        
        return bottlenecks
    
    def _detect_serial_calls(
        self,
        traces: Sequence[Trace],
    ) -> list[Bottleneck]:
        """Detect serial calls that could be parallelized."""
        bottlenecks = []
        
        for trace in traces:
            # Find spans with multiple sequential children
            span_map = {s.span_id: s for s in trace.spans}
            
            for span in trace.spans:
                children = trace.get_children(span.span_id)
                
                if len(children) < 2:
                    continue
                
                # Check if children are sequential (non-overlapping)
                sorted_children = sorted(children, key=lambda s: s.start_time)
                sequential_groups = self._find_sequential_groups(sorted_children)
                
                for group in sequential_groups:
                    if len(group) >= 3:  # At least 3 sequential calls
                        total_time = sum(s.duration_ms for s in group)
                        max_single = max(s.duration_ms for s in group)
                        
                        # Potential savings if parallelized
                        potential_savings = total_time - max_single
                        
                        if potential_savings > 50:  # At least 50ms savings
                            severity = min(1.0, potential_savings / 500)
                            
                            bottlenecks.append(Bottleneck(
                                type=BottleneckType.SERIAL_CALLS,
                                severity=severity,
                                service=span.service_name,
                                operation=span.name,
                                span_ids=[s.span_id for s in group],
                                description=f"{len(group)} sequential calls that could be parallelized",
                                impact_ms=potential_savings,
                                recommendation="Consider using async/parallel execution for independent calls",
                                evidence={
                                    "call_count": len(group),
                                    "total_time_ms": total_time,
                                    "potential_savings_ms": potential_savings,
                                    "operations": [s.name for s in group],
                                },
                            ))
        
        return bottlenecks
    
    def _find_sequential_groups(
        self,
        spans: list[Span],
    ) -> list[list[Span]]:
        """Find groups of sequential (non-overlapping) spans."""
        if not spans:
            return []
        
        groups = []
        current_group = [spans[0]]
        
        for i in range(1, len(spans)):
            prev = spans[i - 1]
            curr = spans[i]
            
            # Check if sequential (no overlap)
            if curr.start_time >= prev.end_time:
                current_group.append(curr)
            else:
                # Overlapping - start new group
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [curr]
        
        if len(current_group) >= 2:
            groups.append(current_group)
        
        return groups
    
    def _detect_deep_nesting(
        self,
        traces: Sequence[Trace],
    ) -> list[Bottleneck]:
        """Detect traces with excessive nesting depth."""
        bottlenecks = []
        
        for trace in traces:
            depth = trace.depth
            
            if depth > self.config.max_depth_threshold:
                severity = min(1.0, (depth - self.config.max_depth_threshold) / 10)
                
                root = trace.root_span
                service = root.service_name if root else "unknown"
                operation = root.name if root else "unknown"
                
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.DEEP_NESTING,
                    severity=severity,
                    service=service,
                    operation=operation,
                    description=f"Trace depth ({depth}) exceeds threshold ({self.config.max_depth_threshold})",
                    recommendation="Review call hierarchy and consider flattening or consolidating services",
                    evidence={
                        "depth": depth,
                        "threshold": self.config.max_depth_threshold,
                        "trace_id": trace.trace_id,
                    },
                ))
        
        return bottlenecks
    
    def find_bottlenecks(
        self,
        traces: Sequence[Trace],
        min_severity: float = 0.0,
    ) -> list[Bottleneck]:
        """
        Find bottlenecks in traces.
        
        Convenience method that returns only bottlenecks.
        """
        result = self.analyze(traces)
        return [b for b in result.bottlenecks if b.severity >= min_severity]
    
    def get_operation_stats(
        self,
        traces: Sequence[Trace],
        service: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> list[SpanStatistics]:
        """
        Get statistics for operations.
        
        Convenience method for quick stats lookup.
        """
        result = self.analyze(traces)
        
        stats = []
        for key, profile in result.operation_profiles.items():
            if service and profile.service != service:
                continue
            if operation and profile.name != operation:
                continue
            stats.append(profile.statistics)
        
        return sorted(stats, key=lambda s: -s.total_count)
    
    def compare_traces(
        self,
        trace1: Trace,
        trace2: Trace,
    ) -> dict[str, Any]:
        """
        Compare two traces to find differences.
        
        Useful for debugging regressions.
        """
        cp1 = trace1.get_critical_path()
        cp2 = trace2.get_critical_path()
        
        return {
            "trace1": {
                "trace_id": trace1.trace_id,
                "duration_ms": trace1.duration_ms,
                "span_count": trace1.span_count,
                "services": list(trace1.services),
                "has_errors": trace1.has_errors,
            },
            "trace2": {
                "trace_id": trace2.trace_id,
                "duration_ms": trace2.duration_ms,
                "span_count": trace2.span_count,
                "services": list(trace2.services),
                "has_errors": trace2.has_errors,
            },
            "comparison": {
                "duration_diff_ms": trace2.duration_ms - trace1.duration_ms,
                "duration_diff_percent": (
                    (trace2.duration_ms - trace1.duration_ms) / trace1.duration_ms * 100
                    if trace1.duration_ms > 0 else 0
                ),
                "span_count_diff": trace2.span_count - trace1.span_count,
                "common_services": list(trace1.services & trace2.services),
                "trace1_only_services": list(trace1.services - trace2.services),
                "trace2_only_services": list(trace2.services - trace1.services),
            },
        }
