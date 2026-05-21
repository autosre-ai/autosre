"""
Investigation State Models — Pydantic models for investigation flow.

Based on OpenSRE's state.py but adapted for plain async Python (no LangGraph).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    """Status of an investigation."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(str, Enum):
    """Priority levels for hypotheses."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    """A piece of evidence gathered during investigation."""
    
    source: str  # e.g., "kubernetes", "metrics", "logs"
    skill: str  # e.g., "pod_logs", "query_prometheus"
    query: str = ""  # The query/command used
    result: str = ""  # The raw result
    summary: Optional[str] = None  # LLM-generated summary
    relevance: float = 0.5  # 0.0-1.0 relevance score
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_prompt(self) -> str:
        """Format evidence for LLM prompt."""
        lines = [
            f"**Source**: {self.source} / {self.skill}",
            f"**Query**: {self.query}" if self.query else "",
            f"**Result**:",
            self.result[:2000] if len(self.result) > 2000 else self.result,
        ]
        return "\n".join(line for line in lines if line)


class Hypothesis(BaseModel):
    """A hypothesis about the root cause."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    hypothesis: str  # Description of potential root cause
    priority: Priority = Priority.MEDIUM
    agents_to_test: list[str] = Field(default_factory=list)  # Which subagents should test
    evidence: list[Evidence] = Field(default_factory=list)  # Collected evidence
    confidence: float = 0.0  # 0.0-1.0 confidence after testing
    confirmed: Optional[bool] = None  # True if confirmed, False if refuted, None if untested
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to this hypothesis."""
        self.evidence.append(evidence)
    
    def to_prompt(self) -> str:
        """Format hypothesis for LLM prompt."""
        status = "✓ Confirmed" if self.confirmed else "✗ Refuted" if self.confirmed is False else "? Untested"
        lines = [
            f"### Hypothesis: {self.hypothesis}",
            f"- Priority: {self.priority.value}",
            f"- Status: {status}",
            f"- Confidence: {self.confidence:.0%}",
        ]
        if self.evidence:
            lines.append(f"- Evidence ({len(self.evidence)} items)")
        return "\n".join(lines)


class InvestigationPlan(BaseModel):
    """Output from the planner agent."""
    
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    reasoning: str = ""


class SynthesisDecision(BaseModel):
    """Output from the synthesizer agent."""
    
    sufficient_evidence: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    root_cause: Optional[str] = None
    gaps: list[str] = Field(default_factory=list)
    feedback: str = ""  # Guidance for next iteration if not sufficient


class SubagentResult(BaseModel):
    """Result from a subagent investigation."""
    
    agent_id: str
    status: InvestigationStatus = InvestigationStatus.COMPLETED
    findings: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    duration_seconds: float = 0.0
    react_loops: int = 0
    error: Optional[str] = None


class InvestigationReport(BaseModel):
    """Final investigation report."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Input
    alert: dict[str, Any] = Field(default_factory=dict)
    service_name: str = ""
    alert_type: str = ""
    
    # Results
    status: InvestigationStatus = InvestigationStatus.COMPLETED
    root_cause: Optional[str] = None
    summary: str = ""
    confidence: float = 0.0
    
    # Details
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    
    # Metadata
    iterations: int = 0
    duration_seconds: float = 0.0
    skills_used: list[str] = Field(default_factory=list)
    agents_used: list[str] = Field(default_factory=list)


class InvestigationState(BaseModel):
    """Complete state for an investigation flow.
    
    This replaces LangGraph's GraphState with a plain Pydantic model.
    The orchestrator manages state transitions.
    """
    
    # ----- Identification -----
    investigation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # ----- Input -----
    alert: dict[str, Any] = Field(default_factory=dict)
    images: list[dict[str, Any]] = Field(default_factory=list)
    
    # ----- Context (populated by init_context, memory_lookup, topology) -----
    service_name: str = ""
    alert_type: str = ""
    memory_context: dict[str, Any] = Field(default_factory=dict)
    topology_context: dict[str, Any] = Field(default_factory=dict)
    
    # ----- Investigation tracking -----
    status: InvestigationStatus = InvestigationStatus.PENDING
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    agent_results: dict[str, SubagentResult] = Field(default_factory=dict)
    all_evidence: list[Evidence] = Field(default_factory=list)
    
    # ----- Messages (for multi-turn conversation) -----
    messages: list[dict[str, str]] = Field(default_factory=list)
    
    # ----- Control flow -----
    iteration: int = 0
    max_iterations: int = 3
    max_subagent_loops: int = 25
    
    # ----- Results -----
    synthesis: Optional[SynthesisDecision] = None
    report: Optional[InvestigationReport] = None
    
    # ----- Error handling -----
    error: Optional[str] = None
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append({"role": role, "content": content})
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to the global evidence list."""
        self.all_evidence.append(evidence)
    
    def add_agent_result(self, result: SubagentResult) -> None:
        """Add a subagent result."""
        self.agent_results[result.agent_id] = result
        for ev in result.evidence:
            self.add_evidence(ev)
    
    def get_all_skills_used(self) -> list[str]:
        """Get list of all skills used across all evidence."""
        skills = set()
        for ev in self.all_evidence:
            skills.add(ev.skill)
        return sorted(skills)
    
    def finalize_report(self) -> InvestigationReport:
        """Generate final investigation report from current state."""
        self.report = InvestigationReport(
            id=self.investigation_id,
            created_at=self.created_at,
            alert=self.alert,
            service_name=self.service_name,
            alert_type=self.alert_type,
            status=self.status,
            root_cause=self.synthesis.root_cause if self.synthesis else None,
            summary=self.synthesis.summary if self.synthesis else "",
            confidence=self.synthesis.confidence if self.synthesis else 0.0,
            hypotheses=self.hypotheses,
            evidence=self.all_evidence,
            iterations=self.iteration,
            duration_seconds=sum(r.duration_seconds for r in self.agent_results.values()),
            skills_used=self.get_all_skills_used(),
            agents_used=list(self.agent_results.keys()),
        )
        return self.report
