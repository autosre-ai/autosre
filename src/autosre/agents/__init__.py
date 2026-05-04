"""Investigation agents for AutoSRE."""

from .state import (
    Alert,
    Hypothesis,
    Evidence,
    AgentResult,
    InvestigationState,
    InvestigationPlan,
)
from .planner import Planner, AVAILABLE_AGENTS
from .synthesizer import Synthesizer, Synthesis
from .writeup import WriteupGenerator, IncidentReport

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
    # Legacy
    "InvestigationStateMachine",
    "InvestigationContext",
    "StateTransition",
    "PlannerV1",
    "InvestigationStep",
]
