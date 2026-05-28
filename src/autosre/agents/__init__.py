"""
Investigation agents for AutoSRE.

This module provides the multi-agent investigation system that powers AutoSRE.
The system uses a planning-investigation-synthesis pattern inspired by the
Google SRE book principles:

- TRIAGE FIRST: Assess impact and consider mitigation before deep investigation
- CHANGES AGENT: Most incidents are caused by changes - always check first  
- FOUR GOLDEN SIGNALS: Latency, traffic, errors, saturation
- HUMAN-IN-THE-LOOP: Critical actions require human approval

Key Components:
    Planner: Generates hypotheses and selects which agents to dispatch.
    Synthesizer: Combines findings from multiple agents into root cause analysis.
    WriteupGenerator: Generates incident reports and postmortems.

State Models:
    Alert: The incoming alert or incident description.
    Hypothesis: A potential root cause to investigate.
    Evidence: Findings gathered by investigation agents.
    InvestigationState: Complete state of an ongoing investigation.

AI Safety:
    The module includes safety prompts and output formats designed to prevent
    overconfident or harmful AI decisions. All hypotheses include confidence
    scores, counter-checks, and approval requirements.

Example:
    >>> from autosre.agents import Planner, Alert, InvestigationState
    >>> planner = Planner()
    >>> state = InvestigationState(alert=alert)
    >>> plan = await planner.plan(state)
"""

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
