"""
AI Hypothesis Output Format

Every AI finding is a HYPOTHESIS, not an instruction.
This module enforces that all AI recommendations include:
- Clear confidence levels
- Supporting evidence with citations
- Counter-checks to verify the hypothesis
- Blast radius assessment
- Human approval requirements

Based on Marcel Koert's AI reliability insights:
"AI recommendations are hypothesis, not instructions"
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json


class BlastRadius(str, Enum):
    """Impact scope of a recommended action."""
    NONE = "none"           # Read-only, no changes
    SINGLE_POD = "single_pod"       # Affects one pod
    SINGLE_SERVICE = "single_service"   # Affects one service
    MULTI_SERVICE = "multi_service"    # Affects multiple services
    NAMESPACE = "namespace"         # Affects entire namespace
    CLUSTER = "cluster"           # Cluster-wide impact
    UNKNOWN = "unknown"           # Cannot determine impact


class ApprovalRequirement(str, Enum):
    """Level of human approval required."""
    NONE = "none"               # Safe to auto-execute
    OPTIONAL = "optional"         # Human can review but not required
    REQUIRED = "required"         # Must have human approval
    MANDATORY_MULTIPLE = "mandatory_multiple"  # Requires 2+ humans


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class Evidence:
    """
    A piece of evidence supporting or refuting a hypothesis.
    
    Every claim must be backed by evidence with clear provenance.
    """
    source: str  # e.g., "prometheus", "kubernetes", "logs", "runbook"
    query: str   # The actual query/command used to gather this evidence
    raw_data: Any  # The raw data returned
    interpretation: str  # AI's interpretation of this data
    timestamp: datetime = field(default_factory=utcnow)
    confidence: float = 0.5  # How confident in this interpretation (0-1)
    
    # Provenance tracking
    document_id: Optional[str] = None  # If from a document/runbook
    metric_name: Optional[str] = None  # If from metrics
    log_source: Optional[str] = None   # If from logs
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "query": self.query,
            "raw_data": self.raw_data if isinstance(self.raw_data, (dict, list, str, int, float, bool, type(None))) else str(self.raw_data),
            "interpretation": self.interpretation,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "document_id": self.document_id,
            "metric_name": self.metric_name,
            "log_source": self.log_source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
    
    def to_citation(self) -> str:
        """Generate a citation string for this evidence."""
        parts = [f"[{self.source}]"]
        if self.metric_name:
            parts.append(f"metric:{self.metric_name}")
        if self.document_id:
            parts.append(f"doc:{self.document_id}")
        if self.log_source:
            parts.append(f"logs:{self.log_source}")
        parts.append(f"@{self.timestamp.strftime('%H:%M:%S')}")
        return " ".join(parts)


@dataclass
class CounterCheck:
    """
    A check that could disprove the hypothesis.
    
    Good hypotheses are falsifiable - we should know what would prove us wrong.
    """
    description: str  # What to check
    command: str     # How to check it (query, kubectl command, etc.)
    expected_if_hypothesis_wrong: str  # What we'd see if hypothesis is wrong
    status: str = "pending"  # pending, checked, confirmed, refuted
    result: Optional[str] = None  # Actual result when checked
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "command": self.command,
            "expected_if_hypothesis_wrong": self.expected_if_hypothesis_wrong,
            "status": self.status,
            "result": self.result,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CounterCheck":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AIHypothesis:
    """
    An AI-generated hypothesis about an incident.
    
    This is the CORE OUTPUT FORMAT for all AI findings.
    Every finding is explicitly labeled as a hypothesis, not a fact.
    
    Key principles:
    1. Confidence is always explicit (never implied certainty)
    2. Evidence is cited for every claim
    3. Counter-checks exist to verify/refute
    4. Blast radius is assessed before any action
    5. Human approval is required for risky actions
    """
    # Core hypothesis
    summary: str  # One-line summary of the hypothesis
    detailed_explanation: str = ""  # Longer explanation with reasoning
    
    # Confidence and evidence
    confidence: float = 0.0  # 0.0 to 1.0 - MUST be set explicitly
    evidence: list[Evidence] = field(default_factory=list)
    
    # Falsifiability
    counter_checks: list[CounterCheck] = field(default_factory=list)
    
    # Risk assessment
    blast_radius: BlastRadius = BlastRadius.UNKNOWN
    blast_radius_details: str = ""  # Specific services/pods affected
    
    # Approval requirements
    requires_human_approval: bool = True  # Default to safe
    approval_requirement: ApprovalRequirement = ApprovalRequirement.REQUIRED
    approval_reason: str = ""  # Why approval is/isn't needed
    
    # Recommended action (if any)
    recommended_action: Optional[str] = None
    action_command: Optional[str] = None
    action_reversible: bool = False
    rollback_steps: list[str] = field(default_factory=list)
    
    # Metadata
    hypothesis_id: str = ""
    created_at: datetime = field(default_factory=utcnow)
    category: str = "unknown"  # resource, network, application, config, external
    
    def __post_init__(self):
        """Validate hypothesis after creation."""
        if not self.hypothesis_id:
            import uuid
            self.hypothesis_id = f"hyp-{uuid.uuid4().hex[:8]}"
        
        # Auto-set approval requirement based on blast radius
        if self.blast_radius in (BlastRadius.CLUSTER, BlastRadius.NAMESPACE):
            self.approval_requirement = ApprovalRequirement.MANDATORY_MULTIPLE
            self.requires_human_approval = True
        elif self.blast_radius == BlastRadius.MULTI_SERVICE:
            self.approval_requirement = ApprovalRequirement.REQUIRED
            self.requires_human_approval = True
        elif self.blast_radius == BlastRadius.NONE:
            if not self.requires_human_approval:
                self.approval_requirement = ApprovalRequirement.NONE
    
    @property
    def confidence_label(self) -> str:
        """Human-readable confidence label."""
        if self.confidence >= 0.9:
            return "very high"
        elif self.confidence >= 0.7:
            return "high"
        elif self.confidence >= 0.5:
            return "moderate"
        elif self.confidence >= 0.3:
            return "low"
        else:
            return "very low"
    
    @property
    def needs_more_evidence(self) -> bool:
        """Whether more evidence gathering is recommended."""
        return self.confidence < 0.5 or len(self.evidence) < 2
    
    @property
    def is_actionable(self) -> bool:
        """Whether this hypothesis has a clear action."""
        return bool(self.recommended_action and self.confidence >= 0.5)
    
    @property
    def evidence_citations(self) -> str:
        """Generate citations for all evidence."""
        return "; ".join(e.to_citation() for e in self.evidence)
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add supporting evidence."""
        self.evidence.append(evidence)
        # Recalculate confidence based on evidence
        if self.evidence:
            avg_confidence = sum(e.confidence for e in self.evidence) / len(self.evidence)
            # Weight by number of sources (more sources = higher base confidence)
            source_bonus = min(0.2, len(self.evidence) * 0.05)
            self.confidence = min(1.0, avg_confidence + source_bonus)
    
    def add_counter_check(self, check: CounterCheck) -> None:
        """Add a counter-check."""
        self.counter_checks.append(check)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "summary": self.summary,
            "detailed_explanation": self.detailed_explanation,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "evidence": [e.to_dict() for e in self.evidence],
            "counter_checks": [c.to_dict() for c in self.counter_checks],
            "blast_radius": self.blast_radius.value,
            "blast_radius_details": self.blast_radius_details,
            "requires_human_approval": self.requires_human_approval,
            "approval_requirement": self.approval_requirement.value,
            "approval_reason": self.approval_reason,
            "recommended_action": self.recommended_action,
            "action_command": self.action_command,
            "action_reversible": self.action_reversible,
            "rollback_steps": self.rollback_steps,
            "created_at": self.created_at.isoformat(),
            "category": self.category,
            "needs_more_evidence": self.needs_more_evidence,
            "is_actionable": self.is_actionable,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AIHypothesis":
        """Create from dictionary."""
        data = data.copy()
        
        # Remove computed properties
        data.pop("confidence_label", None)
        data.pop("needs_more_evidence", None)
        data.pop("is_actionable", None)
        
        # Convert nested objects
        if "evidence" in data:
            data["evidence"] = [Evidence.from_dict(e) for e in data["evidence"]]
        if "counter_checks" in data:
            data["counter_checks"] = [CounterCheck.from_dict(c) for c in data["counter_checks"]]
        if isinstance(data.get("blast_radius"), str):
            data["blast_radius"] = BlastRadius(data["blast_radius"])
        if isinstance(data.get("approval_requirement"), str):
            data["approval_requirement"] = ApprovalRequirement(data["approval_requirement"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        
        return cls(**data)
    
    def to_markdown(self) -> str:
        """Generate human-readable markdown report."""
        lines = [
            f"## Hypothesis: {self.summary}",
            "",
            f"**Confidence:** {self.confidence:.0%} ({self.confidence_label})",
            f"**Category:** {self.category}",
            f"**Blast Radius:** {self.blast_radius.value}",
            "",
        ]
        
        if self.detailed_explanation:
            lines.extend([
                "### Explanation",
                self.detailed_explanation,
                "",
            ])
        
        if self.evidence:
            lines.append("### Evidence")
            for i, e in enumerate(self.evidence, 1):
                lines.append(f"{i}. **{e.source}** (confidence: {e.confidence:.0%})")
                lines.append(f"   - Query: `{e.query}`")
                lines.append(f"   - Interpretation: {e.interpretation}")
            lines.append("")
        
        if self.counter_checks:
            lines.append("### Counter-Checks (to verify/refute)")
            for c in self.counter_checks:
                status_icon = "⏳" if c.status == "pending" else ("✅" if c.status == "confirmed" else "❌")
                lines.append(f"- {status_icon} {c.description}")
                lines.append(f"  - Command: `{c.command}`")
                lines.append(f"  - If wrong: {c.expected_if_hypothesis_wrong}")
            lines.append("")
        
        if self.recommended_action:
            lines.extend([
                "### Recommended Action",
                f"**Action:** {self.recommended_action}",
                f"**Command:** `{self.action_command}`" if self.action_command else "",
                f"**Reversible:** {'Yes' if self.action_reversible else 'No'}",
                f"**Requires Approval:** {self.approval_requirement.value}",
                "",
            ])
            
            if self.rollback_steps:
                lines.append("**Rollback Steps:**")
                for step in self.rollback_steps:
                    lines.append(f"1. {step}")
                lines.append("")
        
        return "\n".join(lines)


@dataclass
class InvestigationOutput:
    """
    Complete output from an AI investigation.
    
    Contains multiple hypotheses, ranked by confidence,
    with clear guidance on what to verify.
    """
    investigation_id: str
    alert_name: str
    alert_description: str
    
    # Multiple hypotheses, ranked
    hypotheses: list[AIHypothesis] = field(default_factory=list)
    
    # Summary
    primary_hypothesis: Optional[AIHypothesis] = None
    overall_confidence: float = 0.0
    
    # Recommendations
    immediate_actions: list[str] = field(default_factory=list)  # Safe to do now
    verification_steps: list[str] = field(default_factory=list)  # Check these first
    escalation_triggers: list[str] = field(default_factory=list)  # When to escalate
    
    # Metadata
    context_documents_used: list[str] = field(default_factory=list)
    total_evidence_count: int = 0
    investigation_duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=utcnow)
    
    def __post_init__(self):
        """Set derived fields."""
        if self.hypotheses and not self.primary_hypothesis:
            self.primary_hypothesis = max(self.hypotheses, key=lambda h: h.confidence)
        if self.hypotheses:
            self.overall_confidence = self.primary_hypothesis.confidence if self.primary_hypothesis else 0.0
            self.total_evidence_count = sum(len(h.evidence) for h in self.hypotheses)
    
    def add_hypothesis(self, hypothesis: AIHypothesis) -> None:
        """Add a hypothesis and re-rank."""
        self.hypotheses.append(hypothesis)
        self.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        self.primary_hypothesis = self.hypotheses[0]
        self.overall_confidence = self.primary_hypothesis.confidence
        self.total_evidence_count = sum(len(h.evidence) for h in self.hypotheses)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "investigation_id": self.investigation_id,
            "alert_name": self.alert_name,
            "alert_description": self.alert_description,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "primary_hypothesis": self.primary_hypothesis.to_dict() if self.primary_hypothesis else None,
            "overall_confidence": self.overall_confidence,
            "immediate_actions": self.immediate_actions,
            "verification_steps": self.verification_steps,
            "escalation_triggers": self.escalation_triggers,
            "context_documents_used": self.context_documents_used,
            "total_evidence_count": self.total_evidence_count,
            "investigation_duration_seconds": self.investigation_duration_seconds,
            "created_at": self.created_at.isoformat(),
        }
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Generate full markdown report."""
        lines = [
            f"# Investigation Report: {self.alert_name}",
            "",
            f"**Investigation ID:** {self.investigation_id}",
            f"**Alert:** {self.alert_description}",
            f"**Overall Confidence:** {self.overall_confidence:.0%}",
            f"**Duration:** {self.investigation_duration_seconds:.1f}s",
            "",
            "---",
            "",
        ]
        
        if self.primary_hypothesis:
            lines.extend([
                "## Primary Hypothesis",
                "",
                self.primary_hypothesis.to_markdown(),
                "",
            ])
        
        if len(self.hypotheses) > 1:
            lines.append("## Alternative Hypotheses")
            lines.append("")
            for h in self.hypotheses[1:]:
                lines.append(f"### {h.summary} ({h.confidence:.0%})")
                lines.append(h.detailed_explanation or "_No details_")
                lines.append("")
        
        if self.immediate_actions:
            lines.append("## Immediate Actions (Safe)")
            for action in self.immediate_actions:
                lines.append(f"- {action}")
            lines.append("")
        
        if self.verification_steps:
            lines.append("## Verification Steps (Do First)")
            for step in self.verification_steps:
                lines.append(f"1. {step}")
            lines.append("")
        
        if self.escalation_triggers:
            lines.append("## Escalation Triggers")
            for trigger in self.escalation_triggers:
                lines.append(f"- ⚠️ {trigger}")
            lines.append("")
        
        if self.context_documents_used:
            lines.append("## Context Documents Used")
            for doc in self.context_documents_used:
                lines.append(f"- {doc}")
            lines.append("")
        
        return "\n".join(lines)
