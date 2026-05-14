"""
AutoSRE V2 Tracing Module.

Distributed tracing analysis with:
- TraceIngester: OpenTelemetry/Jaeger integration
- SpanAnalyzer: Identify slow spans, bottlenecks
- ServiceGraphBuilder: Auto-generate service dependency maps
- LatencyProfiler: P50/P95/P99 tracking per service

Example:
    from autosre.tracing import TraceIngester, SpanAnalyzer

    ingester = TraceIngester(jaeger_url="http://jaeger:16686")
    traces = await ingester.fetch_traces(service="api-gateway")

    analyzer = SpanAnalyzer()
    bottlenecks = analyzer.find_bottlenecks(traces)
"""

from .models import (
    Span,
    Trace,
    SpanKind,
    SpanStatus,
    SpanEvent,
    SpanLink,
    TraceContext,
    Resource,
    InstrumentationScope,
)

from .ingester import (
    TraceIngester,
    IngesterConfig,
    JaegerIngester,
    OTLPIngester,
    ZipkinIngester,
    TraceFetcher,
    TraceFilter,
)

from .analyzer import (
    SpanAnalyzer,
    AnalysisResult,
    Bottleneck,
    BottleneckType,
    SpanStatistics,
    OperationProfile,
    CriticalPath,
    AnalyzerConfig,
)

from .service_graph import (
    ServiceGraphBuilder,
    ServiceGraph,
    ServiceNode,
    ServiceEdge,
    GraphConfig,
    DependencyType,
    ServiceMetrics,
)

from .latency import (
    LatencyProfiler,
    LatencyProfile,
    LatencyBucket,
    LatencyDistribution,
    PercentileTracker,
    SLOConfig,
    LatencyAlert,
    ProfilerConfig,
)

__all__ = [
    # Models
    "Span",
    "Trace",
    "SpanKind",
    "SpanStatus",
    "SpanEvent",
    "SpanLink",
    "TraceContext",
    "Resource",
    "InstrumentationScope",
    # Ingester
    "TraceIngester",
    "IngesterConfig",
    "JaegerIngester",
    "OTLPIngester",
    "ZipkinIngester",
    "TraceFetcher",
    "TraceFilter",
    # Analyzer
    "SpanAnalyzer",
    "AnalysisResult",
    "Bottleneck",
    "BottleneckType",
    "SpanStatistics",
    "OperationProfile",
    "CriticalPath",
    "AnalyzerConfig",
    # Service Graph
    "ServiceGraphBuilder",
    "ServiceGraph",
    "ServiceNode",
    "ServiceEdge",
    "GraphConfig",
    "DependencyType",
    "ServiceMetrics",
    # Latency
    "LatencyProfiler",
    "LatencyProfile",
    "LatencyBucket",
    "LatencyDistribution",
    "PercentileTracker",
    "SLOConfig",
    "LatencyAlert",
    "ProfilerConfig",
]
