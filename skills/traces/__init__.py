"""
Trace analysis skill for distributed tracing investigation.

This skill provides distributed tracing analysis for debugging request flows,
identifying latency bottlenecks, and correlating errors across services.
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class Span:
    """A single span in a trace."""
    span_id: str
    trace_id: str
    operation_name: str
    service_name: str
    duration_ms: float
    start_time: str
    end_time: str
    status: str  # ok, error
    parent_span_id: str | None = None
    tags: dict | None = None
    logs: list | None = None


@dataclass
class Trace:
    """A complete distributed trace."""
    trace_id: str
    spans: list[Span]
    duration_ms: float
    span_count: int
    services: list[str]
    status: str


@dataclass
class TraceAnalysis:
    """Analysis results for a trace."""
    trace_id: str
    critical_path: list[str]
    bottleneck_span: Span | None
    latency_by_service: dict[str, float]
    error_spans: list[Span]
    recommendations: list[str]


async def find_traces(
    service: str,
    operation: str | None = None,
    time_range: str = "1h",
    status: str | None = None,
    min_duration: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Find traces by service, operation, time range, or error status.
    
    Args:
        service: Service name
        operation: Operation/endpoint name
        time_range: Time range (e.g., 1h, 15m)
        status: Filter by status (error, ok)
        min_duration: Minimum duration (e.g., 1s, 500ms)
        limit: Maximum traces to return
    
    Returns:
        List of trace summaries
    """
    raise NotImplementedError("Implement for your tracing backend")


async def get_trace(trace_id: str) -> dict[str, Any]:
    """
    Get full trace details by trace ID.
    
    Args:
        trace_id: Trace ID
    
    Returns:
        Complete trace with all spans
    """
    raise NotImplementedError("Implement for your tracing backend")


async def analyze_trace(trace_id: str) -> dict[str, Any]:
    """
    Analyze a trace for bottlenecks and issues.
    
    Performs:
    - Critical path analysis
    - Latency breakdown by service
    - Error identification
    - Bottleneck detection
    
    Args:
        trace_id: Trace ID
    
    Returns:
        Analysis with critical path, bottlenecks, recommendations
    """
    # 1. Get the trace
    trace = await get_trace(trace_id)
    
    # 2. Build span tree
    # 3. Find critical path (longest chain)
    # 4. Calculate latency by service
    # 5. Identify bottleneck (highest duration span)
    # 6. Find error spans
    # 7. Generate recommendations
    
    raise NotImplementedError("Implement for your tracing backend")


async def compare_traces(trace_ids: list[str]) -> dict[str, Any]:
    """
    Compare traces to find differences (e.g., slow vs fast).
    
    Useful for debugging intermittent issues by comparing
    successful/fast traces with failed/slow ones.
    
    Args:
        trace_ids: List of trace IDs to compare
    
    Returns:
        Comparison showing differences in duration, spans
    """
    raise NotImplementedError("Implement for your tracing backend")


async def get_service_latency(
    service: str,
    time_range: str = "1h",
) -> dict[str, Any]:
    """
    Get latency contribution by service.
    
    Args:
        service: Service name
        time_range: Time range
    
    Returns:
        Latency percentiles (p50, p95, p99) and breakdown
    """
    raise NotImplementedError("Implement for your tracing backend")


async def get_service_dependencies(
    service: str,
    time_range: str = "1h",
) -> dict[str, Any]:
    """
    Get service dependency graph from traces.
    
    Args:
        service: Service name
        time_range: Time range
    
    Returns:
        Upstream and downstream dependencies with call counts
    """
    raise NotImplementedError("Implement for your tracing backend")


# Backend-specific implementations

class JaegerBackend:
    """Jaeger tracing backend."""
    
    def __init__(self, url: str):
        self.url = url
    
    # Implementation methods...


class TempoBackend:
    """Grafana Tempo tracing backend."""
    
    def __init__(self, url: str):
        self.url = url
    
    # Implementation methods...


class ZipkinBackend:
    """Zipkin tracing backend."""
    
    def __init__(self, url: str):
        self.url = url
    
    # Implementation methods...


class XRayBackend:
    """AWS X-Ray tracing backend."""
    
    def __init__(self, region: str):
        self.region = region
    
    # Implementation methods...
