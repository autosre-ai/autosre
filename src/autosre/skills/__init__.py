"""
Skills Module

Provides specialized skills for SRE operations including:
- Cascading failure detection and analysis
- Recovery planning and execution
- Golden Signals monitoring (latency, traffic, errors, saturation)
- Latency metrics with proper percentiles (no avg!)
"""

from .cascading_failure import (
    CascadingFailureAnalyzer,
    CascadePattern,
    CascadeDetection,
    FailureStage,
)
from .recovery import (
    RecoveryPlanner,
    RecoveryPlan,
    RecoveryAction,
    RecoveryStage,
    LoadProfile,
)
from .golden_signals import (
    GoldenSignalsSkill,
    GoldenSignalsResult,
    SignalResult,
    SignalStatus,
    create_golden_signals_skill,
    create_datadog_golden_signals_skill,
)
from .metrics import (
    LatencyMetricsSkill,
    LatencyResult,
    LatencyPercentiles,
    create_latency_skill,
    validate_latency_query,
    PERCENTILE_VALUES,
)

__all__ = [
    # Cascading Failure
    "CascadingFailureAnalyzer",
    "CascadePattern",
    "CascadeDetection",
    "FailureStage",
    # Recovery
    "RecoveryPlanner",
    "RecoveryPlan",
    "RecoveryAction",
    "RecoveryStage",
    "LoadProfile",
    # Golden Signals
    "GoldenSignalsSkill",
    "GoldenSignalsResult",
    "SignalResult",
    "SignalStatus",
    "create_golden_signals_skill",
    "create_datadog_golden_signals_skill",
    # Latency Metrics
    "LatencyMetricsSkill",
    "LatencyResult",
    "LatencyPercentiles",
    "create_latency_skill",
    "validate_latency_query",
    "PERCENTILE_VALUES",
]
