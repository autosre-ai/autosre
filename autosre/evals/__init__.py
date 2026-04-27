"""
Evaluation Framework - Test and measure agent performance.

The eval framework provides:
- Synthetic incident scenarios
- Alert replay from real incidents
- Baseline metrics tracking
- Comparison over time
"""

from autosre.evals.framework import (
    Scenario,
    ScenarioResult,
    run_scenario,
    list_scenarios,
    get_results,
)
from autosre.evals.metrics import (
    EvalMetrics,
    calculate_metrics,
)

__all__ = [
    "Scenario",
    "ScenarioResult",
    "run_scenario",
    "list_scenarios",
    "get_results",
    "EvalMetrics",
    "calculate_metrics",
]
