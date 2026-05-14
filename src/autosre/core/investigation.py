"""
Investigation state machine for AutoSRE V2.

Manages the lifecycle of an incident investigation, including hypothesis
tracking, evidence collection, and conclusion synthesis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field

from autosre.core.alert import Alert, AlertSeverity


class InvestigationStatus(str, Enum):
    """Investigation lifecycle status."""

    PENDING = "pending"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class HypothesisPriority(str, Enum):
    """Hypothesis priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HypothesisStatus(str, Enum):
    """Hypothesis evaluation status."""

    PENDING = "pending"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class EvidenceType(str, Enum):
    """Types of evidence collected during investigation."""

    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    CONFIG = "config"
    DEPLOYMENT = "deployment"
    RESOURCE_STATUS = "resource_status"
    NETWORK = "network"
    CUSTOM = "custom"


class Evidence(BaseModel):
    """
    A piece of evidence collected during investigation.

    Evidence supports the hypothesis testing process by providing
    concrete data points from various sources.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EvidenceType
    source: str = Field(..., description="Source system (prometheus, loki, kubernetes, etc.)")
    query: str | None = Field(default=None, description="Query used to obtain evidence")
    data: Any = Field(..., description="The actual evidence data")
    summary: str = Field(..., description="Human-readable summary")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    relevance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relevance to the investigation (0-1)",
    )
    hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="Hypotheses this evidence relates to",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def supports_hypothesis(self, hypothesis_id: str) -> bool:
        """Check if this evidence supports a specific hypothesis."""
        return hypothesis_id in self.hypothesis_ids


class Hypothesis(BaseModel):
    """
    A hypothesis about the root cause of an incident.

    Hypotheses are generated during triage and tested during investigation.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str = Field(..., description="What we think might be wrong")
    priority: HypothesisPriority = Field(default=HypothesisPriority.MEDIUM)
    status: HypothesisStatus = Field(default=HypothesisStatus.PENDING)

    # Testing details
    agents_to_test: list[str] = Field(
        default_factory=list,
        description="Which agents should test this hypothesis",
    )
    test_plan: str | None = Field(
        default=None,
        description="Specific steps to test this hypothesis",
    )

    # Results
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence this is the root cause (0-1)",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence supporting or refuting this hypothesis",
    )
    reasoning: str | None = Field(
        default=None,
        description="Explanation of why hypothesis was confirmed/rejected",
    )

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="triage_agent")

    def confirm(self, confidence: float, reasoning: str) -> None:
        """Mark hypothesis as confirmed."""
        self.status = HypothesisStatus.CONFIRMED
        self.confidence = confidence
        self.reasoning = reasoning
        self.updated_at = datetime.now(timezone.utc)

    def reject(self, reasoning: str) -> None:
        """Mark hypothesis as rejected."""
        self.status = HypothesisStatus.REJECTED
        self.confidence = 0.0
        self.reasoning = reasoning
        self.updated_at = datetime.now(timezone.utc)

    def mark_inconclusive(self, reasoning: str) -> None:
        """Mark hypothesis as inconclusive due to insufficient evidence."""
        self.status = HypothesisStatus.INCONCLUSIVE
        self.reasoning = reasoning
        self.updated_at = datetime.now(timezone.utc)


class Finding(BaseModel):
    """
    A significant finding from the investigation.

    Findings are distilled insights from evidence that contribute
    to understanding the incident.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    category: str = Field(default="general", description="Finding category")

    # Related entities
    evidence_ids: list[str] = Field(default_factory=list)
    hypothesis_ids: list[str] = Field(default_factory=list)
    agent_id: str = Field(default="unknown", description="Agent that discovered this")

    # Impact
    is_root_cause: bool = Field(default=False)
    is_contributing_factor: bool = Field(default=False)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """State of an individual investigation agent."""

    agent_id: str
    status: str = Field(default="pending")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    iterations: int = Field(default=0)
    findings: list[str] = Field(default_factory=list, description="Finding text summaries")
    evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    duration_seconds: float | None = None

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Check if agent has completed (successfully or with error)."""
        return self.status in ("completed", "error", "timeout")


class InvestigationResult(BaseModel):
    """Final result of an investigation."""

    root_cause: str | None = Field(
        default=None,
        description="Identified root cause (if found)",
    )
    root_cause_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    summary: str = Field(
        default="",
        description="Executive summary of the investigation",
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Factors that contributed to the incident",
    )
    timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Timeline of events leading to the incident",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommended remediation actions",
    )
    requires_human_review: bool = Field(
        default=False,
        description="Whether human review is needed",
    )


class Investigation(BaseModel):
    """
    Main investigation state machine.

    Tracks the entire lifecycle of an incident investigation, from
    initial alert to final conclusion.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    thread_id: str = Field(default_factory=lambda: str(uuid4()))

    # Input
    alert: Alert
    correlation_id: str | None = None

    # Status tracking
    status: InvestigationStatus = Field(default=InvestigationStatus.PENDING)
    iteration: int = Field(default=0)
    max_iterations: int = Field(default=3)

    # Investigation state
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    agent_states: dict[str, AgentState] = Field(default_factory=dict)

    # Context
    memory_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Context from past investigations",
    )
    knowledge_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Relevant knowledge base entries",
    )
    service_topology: dict[str, Any] = Field(
        default_factory=dict,
        description="Service dependency information",
    )

    # Results
    result: InvestigationResult | None = None

    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Messages for debugging/audit
    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Internal messages between agents",
    )

    @computed_field
    @property
    def duration_seconds(self) -> float | None:
        """Get total investigation duration."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Check if investigation is in a terminal state."""
        return self.status in (
            InvestigationStatus.COMPLETED,
            InvestigationStatus.FAILED,
            InvestigationStatus.TIMEOUT,
            InvestigationStatus.CANCELLED,
        )

    @computed_field
    @property
    def active_hypotheses(self) -> list[Hypothesis]:
        """Get hypotheses that are still being tested."""
        return [
            h for h in self.hypotheses
            if h.status in (HypothesisStatus.PENDING, HypothesisStatus.TESTING)
        ]

    @computed_field
    @property
    def confirmed_hypotheses(self) -> list[Hypothesis]:
        """Get confirmed hypotheses sorted by confidence."""
        confirmed = [h for h in self.hypotheses if h.status == HypothesisStatus.CONFIRMED]
        return sorted(confirmed, key=lambda h: h.confidence, reverse=True)

    @computed_field
    @property
    def root_cause_findings(self) -> list[Finding]:
        """Get findings marked as root cause."""
        return [f for f in self.findings if f.is_root_cause]

    def start(self) -> None:
        """Mark investigation as started."""
        self.status = InvestigationStatus.TRIAGING
        self.started_at = datetime.now(timezone.utc)

    def advance_to_investigation(self) -> None:
        """Move from triage to investigation phase."""
        self.status = InvestigationStatus.INVESTIGATING

    def advance_to_synthesis(self) -> None:
        """Move to synthesis phase."""
        self.status = InvestigationStatus.SYNTHESIZING

    def complete(self, result: InvestigationResult) -> None:
        """Mark investigation as completed."""
        self.status = InvestigationStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.result = result

    def fail(self, reason: str) -> None:
        """Mark investigation as failed."""
        self.status = InvestigationStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.add_message("system", f"Investigation failed: {reason}")

    def timeout(self) -> None:
        """Mark investigation as timed out."""
        self.status = InvestigationStatus.TIMEOUT
        self.completed_at = datetime.now(timezone.utc)
        self.add_message("system", "Investigation timed out")

    def cancel(self) -> None:
        """Cancel the investigation."""
        self.status = InvestigationStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self.add_message("system", "Investigation cancelled")

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Add a hypothesis to test."""
        self.hypotheses.append(hypothesis)
        self.add_message(
            hypothesis.created_by,
            f"Added hypothesis: {hypothesis.description}",
        )

    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to the investigation."""
        self.evidence.append(evidence)

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the investigation."""
        self.findings.append(finding)
        self.add_message(
            finding.agent_id,
            f"Finding: {finding.title}",
        )

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the investigation log."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def update_agent_state(self, agent_id: str, **updates: Any) -> None:
        """Update state for a specific agent."""
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = AgentState(agent_id=agent_id)

        state = self.agent_states[agent_id]
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)

    def get_evidence_for_hypothesis(self, hypothesis_id: str) -> list[Evidence]:
        """Get all evidence related to a hypothesis."""
        return [
            e for e in self.evidence
            if hypothesis_id in e.hypothesis_ids
        ]

    def should_continue(self) -> bool:
        """
        Determine if investigation should continue.

        Returns True if:
        - Not in terminal state
        - Below max iterations
        - Has active hypotheses to test
        """
        if self.is_complete:
            return False

        if self.iteration >= self.max_iterations:
            return False

        # Continue if we have hypotheses to test or are in early stages
        if self.status in (InvestigationStatus.PENDING, InvestigationStatus.TRIAGING):
            return True

        return len(self.active_hypotheses) > 0

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration += 1
        self.add_message("coordinator", f"Starting iteration {self.iteration}")

    def to_state_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for graph state.

        Returns a flat dictionary suitable for LangGraph state.
        """
        return {
            "investigation_id": self.id,
            "thread_id": self.thread_id,
            "alert": self.alert.model_dump(),
            "status": self.status.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "hypotheses": [h.model_dump() for h in self.hypotheses],
            "agent_states": {
                aid: state.model_dump()
                for aid, state in self.agent_states.items()
            },
            "memory_context": self.memory_context,
            "knowledge_context": self.knowledge_context,
            "service_topology": self.service_topology,
            "messages": self.messages,
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> Investigation:
        """Reconstruct investigation from state dictionary."""
        alert = Alert(**state["alert"])
        hypotheses = [Hypothesis(**h) for h in state.get("hypotheses", [])]
        agent_states = {
            aid: AgentState(**s)
            for aid, s in state.get("agent_states", {}).items()
        }

        return cls(
            id=state.get("investigation_id", str(uuid4())),
            thread_id=state.get("thread_id", str(uuid4())),
            alert=alert,
            status=InvestigationStatus(state.get("status", "pending")),
            iteration=state.get("iteration", 0),
            max_iterations=state.get("max_iterations", 3),
            hypotheses=hypotheses,
            agent_states=agent_states,
            memory_context=state.get("memory_context", {}),
            knowledge_context=state.get("knowledge_context", {}),
            service_topology=state.get("service_topology", {}),
            messages=state.get("messages", []),
        )
