"""
Skills Module

Provides specialized skills for SRE operations including:
- Cascading failure detection and analysis
- Recovery planning and execution
- Golden Signals monitoring (latency, traffic, errors, saturation)
- Latency metrics with proper percentiles (no avg!)
"""

# Re-export base classes from autosre.skills module
# This allows `from autosre.skills import Skill, ActionResult, action` to work
import sys
import os
# Import the skills.py module directly
_skills_module_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'skills.py')
if os.path.exists(_skills_module_path):
    import importlib.util
    _spec = importlib.util.spec_from_file_location("autosre._skills_base", _skills_module_path)
    if _spec and _spec.loader:
        _skills_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_skills_module)
        Skill = _skills_module.Skill
        ActionResult = _skills_module.ActionResult
        action = _skills_module.action
        ActionDefinition = _skills_module.ActionDefinition
        SkillRegistry = _skills_module.SkillRegistry
        registry = _skills_module.registry

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
    # Base classes from skills.py module
    "Skill",
    "ActionResult",
    "action",
    "ActionDefinition",
    "SkillRegistry",
    "registry",
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
