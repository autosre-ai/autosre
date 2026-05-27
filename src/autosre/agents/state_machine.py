"""
Investigation State

State machine for tracking investigation progress.
"""
from enum import Enum, auto
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


class InvestigationState(Enum):
    """States an investigation can be in."""
    PENDING = auto()
    GATHERING = auto()
    ANALYZING = auto()
    HYPOTHESIZING = auto()
    VALIDATING = auto()
    SYNTHESIZING = auto()
    WRITING = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: InvestigationState
    to_state: InvestigationState
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: Optional[str] = None


@dataclass 
class InvestigationContext:
    """Context accumulated during investigation."""
    state: InvestigationState = InvestigationState.PENDING
    transitions: List[StateTransition] = field(default_factory=list)
    
    # Gathered data
    metrics: dict = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)
    
    # Analysis results
    hypotheses: List[str] = field(default_factory=list)
    validated: List[str] = field(default_factory=list)
    rejected: List[str] = field(default_factory=list)
    
    # Final outputs
    root_cause: Optional[str] = None
    summary: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    
    def transition_to(self, new_state: InvestigationState, reason: Optional[str] = None):
        """Transition to a new state."""
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            reason=reason,
        )
        self.transitions.append(transition)
        self.state = new_state
