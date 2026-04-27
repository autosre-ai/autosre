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
    EvalRunner,
    EvalStore,
    run_scenario,
    list_scenarios,
    get_results,
    get_all_scenarios,
    get_scenario,
    load_scenario,
)
from autosre.evals.metrics import (
    EvalMetrics,
    calculate_metrics,
)

__all__ = [
    "Scenario",
    "ScenarioResult",
    "EvalRunner",
    "EvalStore",
    "run_scenario",
    "list_scenarios",
    "get_results",
    "get_all_scenarios",
    "get_scenario",
    "load_scenario",
    "EvalMetrics",
    "calculate_metrics",
]
