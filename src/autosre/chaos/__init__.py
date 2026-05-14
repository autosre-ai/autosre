"""
AutoSRE V2 Chaos Engineering.

This module provides chaos engineering capabilities:
- ExperimentRunner: Run chaos experiments
- FaultInjector: CPU/memory/network faults
- GameDayPlanner: Schedule game days
- ResilienceScorer: Score system resilience
- ReportGenerator: Generate experiment reports

Example:
    from autosre.chaos import ExperimentRunner, FaultInjector
    
    runner = ExperimentRunner(k8s_client)
    
    experiment = await runner.run_experiment(
        name="api-latency-test",
        target="deployment/api-server",
        fault_type="network-latency",
        duration_seconds=300,
    )
"""

from autosre.chaos.models import (
    Experiment,
    ExperimentStatus,
    ExperimentResult,
    Fault,
    FaultType,
    FaultSeverity,
    Target,
    TargetType,
    GameDay,
    GameDayStatus,
    ResilienceScore,
    SteadyStateHypothesis,
)

from autosre.chaos.experiment import ExperimentRunner
from autosre.chaos.faults import FaultInjector
from autosre.chaos.gameday import GameDayPlanner
from autosre.chaos.resilience import ResilienceScorer
from autosre.chaos.reports import ReportGenerator

__all__ = [
    # Models
    "Experiment",
    "ExperimentStatus",
    "ExperimentResult",
    "Fault",
    "FaultType",
    "FaultSeverity",
    "Target",
    "TargetType",
    "GameDay",
    "GameDayStatus",
    "ResilienceScore",
    "SteadyStateHypothesis",
    # Runner
    "ExperimentRunner",
    # Faults
    "FaultInjector",
    # Game Day
    "GameDayPlanner",
    # Resilience
    "ResilienceScorer",
    # Reports
    "ReportGenerator",
]
