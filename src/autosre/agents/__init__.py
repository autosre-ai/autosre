"""Investigation agents for AutoSRE."""

from .state import (
    Alert,
    Hypothesis,
    Evidence,
    AgentResult,
    InvestigationState,
    InvestigationPlan,
    # Enhanced SRE state models
    EnhancedInvestigationState,
    InvestigationPhase,
    PhaseRequirements,
    TriageResult,
    GoldenSignals,
    SLOContext,
    SLOTarget,
    Change,
    AIHypothesis as StateAIHypothesis,  # State-based hypothesis
    AIDecision,
    AITelemetry,
    PhaseTiming,
    PhaseTransition,
)
from .planner import Planner, AVAILABLE_AGENTS
from .synthesizer import Synthesizer, Synthesis
from .writeup import WriteupGenerator, IncidentReport

# AI Safety output format (dataclass-based, more detailed)
from .output import (
    AIHypothesis as SafetyAIHypothesis,  # Safety-focused hypothesis with full provenance
    Evidence as SafetyEvidence,
    CounterCheck,
    InvestigationOutput,
    BlastRadius,
    ApprovalRequirement,
)

# Safety prompts
from .safety_prompts import (
    AI_SAFETY_PREAMBLE,
    DELIBERATE_REASONING_CHECKLIST,
    PAUSE_AND_VERIFY_PROMPT,
    SAFE_REASONER_SYSTEM_PROMPT,
    SAFE_REASONER_ANALYSIS_PROMPT,
    SAFE_ACTOR_SYSTEM_PROMPT,
    SAFE_ACTOR_ACTION_PROMPT,
    inject_safety_preamble,
    add_deliberate_checklist,
    add_pause_and_verify,
    format_hypothesis_output,
)

# Legacy state machine (backwards compatibility)
from .state_machine import (
    InvestigationState as InvestigationStateMachine,
    InvestigationContext,
    StateTransition,
)

# Legacy planner (backwards compatibility)
from .planner_v1 import (
    Planner as PlannerV1,
    InvestigationStep,
)

__all__ = [
    # New v2 models
    "Alert",
    "Hypothesis",
    "Evidence",
    "AgentResult",
    "InvestigationState",
    "InvestigationPlan",
    "Planner",
    "AVAILABLE_AGENTS",
    "Synthesizer",
    "Synthesis",
    "WriteupGenerator",
    "IncidentReport",
    # Enhanced SRE state models
    "EnhancedInvestigationState",
    "InvestigationPhase",
    "PhaseRequirements",
    "TriageResult",
    "GoldenSignals",
    "SLOContext",
    "SLOTarget",
    "Change",
    "StateAIHypothesis",  # Pydantic-based state hypothesis
    "AIDecision",
    "AITelemetry",
    "PhaseTiming",
    "PhaseTransition",
    # AI Safety output format
    "SafetyAIHypothesis",  # Dataclass-based safety hypothesis with full provenance
    "SafetyEvidence",
    "CounterCheck",
    "InvestigationOutput",
    "BlastRadius",
    "ApprovalRequirement",
    # Safety prompts
    "AI_SAFETY_PREAMBLE",
    "DELIBERATE_REASONING_CHECKLIST",
    "PAUSE_AND_VERIFY_PROMPT",
    "SAFE_REASONER_SYSTEM_PROMPT",
    "SAFE_REASONER_ANALYSIS_PROMPT",
    "SAFE_ACTOR_SYSTEM_PROMPT",
    "SAFE_ACTOR_ACTION_PROMPT",
    "inject_safety_preamble",
    "add_deliberate_checklist",
    "add_pause_and_verify",
    "format_hypothesis_output",
    # Legacy
    "InvestigationStateMachine",
    "InvestigationContext",
    "StateTransition",
    "PlannerV1",
    "InvestigationStep",
]
