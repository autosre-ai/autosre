"""
AutoSRE Chaos Engineering Module

Enterprise-grade chaos engineering capabilities providing:
- Chaos experiment definitions and orchestration
- Fault injection (pod kill, network delay, CPU stress)
- GameDay automation and scheduling
- Safety checks and blast radius control
- Experiment reports and analytics

Compatible with Chaos Mesh and LitmusChaos patterns.

Usage:
    from autosre.chaos import (
        ChaosExperiment, ExperimentState, ExperimentResult,
        FaultInjector, PodKillFault, NetworkDelayFault, CPUStressFault,
        GameDay, GameDayScheduler, GameDayResult,
        SafetyChecker, BlastRadius, SafetyViolation,
        ChaosReport, ExperimentMetrics,
    )
"""

from autosre.chaos.experiments import (
    ChaosExperiment,
    ExperimentState,
    ExperimentResult,
    ExperimentConfig,
    ExperimentType,
    TargetSelector,
    ExperimentSchedule,
    ExperimentRunner,
)
from autosre.chaos.faults import (
    Fault,
    FaultType,
    FaultInjector,
    PodKillFault,
    PodFailureFault,
    NetworkDelayFault,
    NetworkPartitionFault,
    NetworkLossFault,
    CPUStressFault,
    MemoryStressFault,
    IOStressFault,
    DNSFault,
    HTTPFault,
    FaultRegistry,
)
from autosre.chaos.gamedays import (
    GameDay,
    GameDayState,
    GameDayResult,
    GameDayScenario,
    GameDayScheduler,
    GameDayRunner,
    ParticipantRole,
    Participant,
)
from autosre.chaos.safety import (
    SafetyChecker,
    SafetyRule,
    SafetyViolation,
    BlastRadius,
    BlastRadiusConfig,
    SafetyPolicy,
    SafetyLevel,
    CircuitBreaker,
    RollbackTrigger,
)
from autosre.chaos.reports import (
    ChaosReport,
    ExperimentMetrics,
    ReportGenerator,
    ImpactAnalysis,
    ResilienceScore,
    TrendAnalysis,
    ReportFormat,
)

__all__ = [
    # Experiments
    "ChaosExperiment",
    "ExperimentState",
    "ExperimentResult",
    "ExperimentConfig",
    "ExperimentType",
    "TargetSelector",
    "ExperimentSchedule",
    "ExperimentRunner",
    # Faults
    "Fault",
    "FaultType",
    "FaultInjector",
    "PodKillFault",
    "PodFailureFault",
    "NetworkDelayFault",
    "NetworkPartitionFault",
    "NetworkLossFault",
    "CPUStressFault",
    "MemoryStressFault",
    "IOStressFault",
    "DNSFault",
    "HTTPFault",
    "FaultRegistry",
    # GameDays
    "GameDay",
    "GameDayState",
    "GameDayResult",
    "GameDayScenario",
    "GameDayScheduler",
    "GameDayRunner",
    "ParticipantRole",
    "Participant",
    # Safety
    "SafetyChecker",
    "SafetyRule",
    "SafetyViolation",
    "BlastRadius",
    "BlastRadiusConfig",
    "SafetyPolicy",
    "SafetyLevel",
    "CircuitBreaker",
    "RollbackTrigger",
    # Reports
    "ChaosReport",
    "ExperimentMetrics",
    "ReportGenerator",
    "ImpactAnalysis",
    "ResilienceScore",
    "TrendAnalysis",
    "ReportFormat",
]
