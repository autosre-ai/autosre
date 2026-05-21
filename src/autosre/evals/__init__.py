"""
Evaluation Framework - Test and measure agent performance.

The eval framework provides:
- Synthetic incident scenarios
- Alert replay from real incidents
- Baseline metrics tracking
- Comparison over time
- AI Safety Game Day scenarios
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
from autosre.evals.game_day import (
    GameDayFramework,
    GameDayScenario,
    ScenarioType,
    ScenarioResult as GameDayResult,
    CheckResult,
    BehavioralCheck,
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
    # Game Day Framework
    "GameDayFramework",
    "GameDayScenario",
    "ScenarioType",
    "GameDayResult",
    "CheckResult",
    "BehavioralCheck",
]
