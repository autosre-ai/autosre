"""
Metrics Skills — Latency, Error Rates, and Resource Metrics.

From Google SRE book learnings:
- NEVER use avg() for latency - it hides outliers and masks real user experience
- ALWAYS use percentiles: p50, p90, p95, p99, p999
- Use histogram_quantile() in Prometheus, not avg()
"""

from .latency import (
    LatencyMetricsSkill,
    LatencyResult,
    LatencyPercentiles,
    create_latency_skill,
    validate_latency_query,
    PERCENTILE_VALUES,
)

__all__ = [
    "LatencyMetricsSkill",
    "LatencyResult",
    "LatencyPercentiles",
    "create_latency_skill",
    "validate_latency_query",
    "PERCENTILE_VALUES",
]
