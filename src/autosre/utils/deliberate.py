"""
Deliberate Reasoning Utilities for AutoSRE.

Implements the PAUSE checklist to avoid rapid intuitive action under stress.
Key principle: Slow down, cite evidence, consider alternatives.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum


class DeliberationStep(Enum):
    """Steps in the PAUSE checklist."""
    EVIDENCE = "evidence"          # What evidence supports this?
    DISPROVE = "disprove"         # What would disprove this?
    ASSUMPTIONS = "assumptions"    # What assumptions am I making?
    SAFER = "safer"               # Is there a safer action?
    CONSULT = "consult"           # Should I consult someone?


@dataclass
class EvidenceCitation:
    """A citation of evidence for a conclusion."""
    
    source: str  # Where the evidence came from
    data: str    # The actual evidence
    confidence: float = 0.8  # Confidence in this evidence (0-1)
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "data": self.data,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class DeliberationRecord:
    """Record of deliberation before taking action."""
    
    action_proposed: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # PAUSE checklist responses
    evidence: list[EvidenceCitation] = field(default_factory=list)
    disprove_attempts: list[str] = field(default_factory=list)
    assumptions_identified: list[str] = field(default_factory=list)
    safer_alternatives: list[str] = field(default_factory=list)
    consultation_needed: bool = False
    consultation_reason: Optional[str] = None
    
    # Outcome
    proceed: bool = False
    proceed_reason: str = ""
    
    @property
    def deliberation_seconds(self) -> float:
        """Time spent deliberating."""
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()
    
    @property
    def checklist_completion(self) -> float:
        """Percentage of PAUSE checklist completed."""
        completed = 0
        total = 5
        
        if self.evidence:
            completed += 1
        if self.disprove_attempts:
            completed += 1
        if self.assumptions_identified:
            completed += 1
        if self.safer_alternatives or self.proceed_reason:
            completed += 1
        if self.consultation_needed is not None:
            completed += 1
        
        return completed / total
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_proposed": self.action_proposed,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deliberation_seconds": self.deliberation_seconds,
            "evidence": [e.to_dict() for e in self.evidence],
            "disprove_attempts": self.disprove_attempts,
            "assumptions_identified": self.assumptions_identified,
            "safer_alternatives": self.safer_alternatives,
            "consultation_needed": self.consultation_needed,
            "consultation_reason": self.consultation_reason,
            "proceed": self.proceed,
            "proceed_reason": self.proceed_reason,
            "checklist_completion": self.checklist_completion,
        }


class DeliberateReasoner:
    """
    Enforces deliberate reasoning before actions.
    
    Implements PAUSE checklist:
    - P: Proof - What evidence supports this?
    - A: Alternatives - Is there a safer action?
    - U: Underlying assumptions - What am I assuming?
    - S: Seek to disprove - What would prove this wrong?
    - E: Expert consultation - Should I ask someone?
    """
    
    def __init__(
        self,
        require_evidence: bool = True,
        min_evidence_count: int = 1,
        require_disprove_attempt: bool = True,
        track_time: bool = True,
    ):
        """
        Initialize reasoner.
        
        Args:
            require_evidence: Require at least one evidence citation
            min_evidence_count: Minimum evidence citations required
            require_disprove_attempt: Require attempt to disprove
            track_time: Track deliberation time
        """
        self.require_evidence = require_evidence
        self.min_evidence_count = min_evidence_count
        self.require_disprove_attempt = require_disprove_attempt
        self.track_time = track_time
        
        # Metrics
        self._total_deliberations = 0
        self._total_deliberation_seconds = 0
        self._total_action_seconds = 0
        self._evidence_citations = 0
    
    def start_deliberation(self, action: str) -> DeliberationRecord:
        """
        Start a deliberation record for a proposed action.
        
        Args:
            action: Description of proposed action
            
        Returns:
            DeliberationRecord to fill in
        """
        return DeliberationRecord(action_proposed=action)
    
    def add_evidence(
        self,
        record: DeliberationRecord,
        source: str,
        data: str,
        confidence: float = 0.8,
    ) -> None:
        """Add evidence citation to deliberation."""
        record.evidence.append(EvidenceCitation(
            source=source,
            data=data,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
        ))
        self._evidence_citations += 1
    
    def add_disprove_attempt(
        self,
        record: DeliberationRecord,
        attempt: str,
    ) -> None:
        """Add attempt to disprove the hypothesis."""
        record.disprove_attempts.append(attempt)
    
    def add_assumption(
        self,
        record: DeliberationRecord,
        assumption: str,
    ) -> None:
        """Identify an assumption being made."""
        record.assumptions_identified.append(assumption)
    
    def add_safer_alternative(
        self,
        record: DeliberationRecord,
        alternative: str,
    ) -> None:
        """Add a potentially safer alternative action."""
        record.safer_alternatives.append(alternative)
    
    def mark_consultation_needed(
        self,
        record: DeliberationRecord,
        reason: str,
    ) -> None:
        """Mark that consultation is needed."""
        record.consultation_needed = True
        record.consultation_reason = reason
    
    def complete_deliberation(
        self,
        record: DeliberationRecord,
        proceed: bool,
        reason: str = "",
    ) -> tuple[bool, list[str]]:
        """
        Complete deliberation and validate.
        
        Args:
            record: Deliberation record
            proceed: Whether to proceed with action
            reason: Reason for decision
            
        Returns:
            Tuple of (can_proceed, warnings)
        """
        record.completed_at = datetime.now(timezone.utc)
        record.proceed = proceed
        record.proceed_reason = reason
        
        # Track metrics
        self._total_deliberations += 1
        self._total_deliberation_seconds += record.deliberation_seconds
        
        # Validate
        warnings = []
        can_proceed = True
        
        if self.require_evidence:
            if len(record.evidence) < self.min_evidence_count:
                warnings.append(
                    f"Insufficient evidence: {len(record.evidence)}/{self.min_evidence_count} citations"
                )
                if proceed:
                    can_proceed = False
        
        if self.require_disprove_attempt:
            if not record.disprove_attempts:
                warnings.append("No attempt to disprove hypothesis")
        
        if record.consultation_needed and proceed:
            warnings.append(f"Proceeding despite consultation flag: {record.consultation_reason}")
        
        if record.checklist_completion < 0.6:
            warnings.append(
                f"PAUSE checklist only {record.checklist_completion:.0%} complete"
            )
        
        return can_proceed, warnings
    
    def record_action_time(self, seconds: float) -> None:
        """Record time spent on action (vs deliberation)."""
        self._total_action_seconds += seconds
    
    def get_metrics(self) -> dict[str, Any]:
        """Get deliberation metrics."""
        total_time = self._total_deliberation_seconds + self._total_action_seconds
        
        return {
            "total_deliberations": self._total_deliberations,
            "total_deliberation_seconds": self._total_deliberation_seconds,
            "total_action_seconds": self._total_action_seconds,
            "deliberation_ratio": (
                self._total_deliberation_seconds / total_time
                if total_time > 0 else 0
            ),
            "average_deliberation_seconds": (
                self._total_deliberation_seconds / self._total_deliberations
                if self._total_deliberations > 0 else 0
            ),
            "evidence_citations": self._evidence_citations,
        }


# PAUSE Checklist prompt for LLM
PAUSE_CHECKLIST_PROMPT = """
Before taking this action, complete the PAUSE checklist:

## P - Proof (Evidence)
What specific evidence supports this conclusion?
- Cite logs, metrics, or observations
- Rate confidence (low/medium/high)

## A - Alternatives
Is there a safer or more reversible action?
- List alternatives considered
- Why is proposed action preferred?

## U - Underlying Assumptions
What assumptions are being made?
- List explicit assumptions
- Which could be wrong?

## S - Seek to Disprove
What would prove this hypothesis wrong?
- What evidence would contradict?
- Did we look for that evidence?

## E - Expert Consultation
Should someone else be consulted?
- Is this within normal operating bounds?
- Would additional expertise help?

Only proceed after addressing each point.
"""


def create_deliberation_prompt(action: str, context: str) -> str:
    """
    Create a deliberation prompt for an action.
    
    Args:
        action: Proposed action
        context: Investigation context
        
    Returns:
        Formatted prompt
    """
    return f"""
# Deliberation Required

**Proposed Action:** {action}

**Context:**
{context}

{PAUSE_CHECKLIST_PROMPT}

Respond with your completed checklist, then state whether to PROCEED or STOP.
"""


def validate_deliberation_response(response: str) -> tuple[bool, dict[str, Any]]:
    """
    Validate that a response contains proper deliberation.
    
    Args:
        response: LLM response to deliberation prompt
        
    Returns:
        Tuple of (is_valid, extracted_data)
    """
    response_lower = response.lower()
    
    extracted = {
        "has_evidence": False,
        "has_alternatives": False,
        "has_assumptions": False,
        "has_disprove": False,
        "has_consultation": False,
        "decision": None,
    }
    
    # Check for each section
    if any(word in response_lower for word in ["evidence", "proof", "logs show", "metrics indicate"]):
        extracted["has_evidence"] = True
    
    if any(word in response_lower for word in ["alternative", "instead", "could also", "safer"]):
        extracted["has_alternatives"] = True
    
    if any(word in response_lower for word in ["assum", "if", "might be", "could be wrong"]):
        extracted["has_assumptions"] = True
    
    if any(word in response_lower for word in ["disprove", "contradict", "wrong if", "look for"]):
        extracted["has_disprove"] = True
    
    if any(word in response_lower for word in ["consult", "expert", "escalate", "ask"]):
        extracted["has_consultation"] = True
    
    # Extract decision
    if "proceed" in response_lower:
        extracted["decision"] = "proceed"
    elif "stop" in response_lower:
        extracted["decision"] = "stop"
    
    # Calculate validity
    checklist_complete = sum([
        extracted["has_evidence"],
        extracted["has_alternatives"],
        extracted["has_assumptions"],
        extracted["has_disprove"],
        extracted["has_consultation"],
    ])
    
    is_valid = checklist_complete >= 3 and extracted["decision"] is not None
    extracted["checklist_score"] = checklist_complete / 5
    
    return is_valid, extracted
