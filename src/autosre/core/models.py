"""AutoSRE Core Data Models - Pydantic models for alerts, investigations, and actions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status."""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class Alert(BaseModel):
    """Incoming alert from monitoring systems."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Alert name/title")
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.FIRING
    
    # Source information
    source: str = Field(..., description="Monitoring system (prometheus, datadog, etc)")
    source_id: str | None = Field(None, description="ID in the source system")
    
    # Alert details
    description: str | None = None
    summary: str | None = None
    runbook_url: str | None = None
    
    # Labels and annotations (Prometheus-style)
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Affected resources
    service: str | None = None
    namespace: str | None = None
    cluster: str | None = None
    instance: str | None = None
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    
    # Raw payload from source
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float | None:
        """Get alert duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (datetime.utcnow() - self.started_at).total_seconds()
    
    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status == AlertStatus.FIRING
    
    def to_context_string(self) -> str:
        """Format alert for LLM context."""
        lines = [
            f"Alert: {self.name}",
            f"Severity: {self.severity.value}",
            f"Status: {self.status.value}",
            f"Source: {self.source}",
        ]
        
        if self.description:
            lines.append(f"Description: {self.description}")
        if self.service:
            lines.append(f"Service: {self.service}")
        if self.namespace:
            lines.append(f"Namespace: {self.namespace}")
        if self.cluster:
            lines.append(f"Cluster: {self.cluster}")
        
        if self.labels:
            lines.append(f"Labels: {self.labels}")
        
        lines.append(f"Started: {self.started_at.isoformat()}")
        if duration := self.duration_seconds:
            lines.append(f"Duration: {duration:.0f}s")
        
        return "\n".join(lines)


class InvestigationStatus(str, Enum):
    """Investigation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_DATA = "waiting_for_data"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Investigation(BaseModel):
    """An automated investigation triggered by an alert."""
    
    id: UUID = Field(default_factory=uuid4)
    alert_id: UUID = Field(..., description="Associated alert ID")
    status: InvestigationStatus = InvestigationStatus.PENDING
    
    # Investigation context
    title: str = Field(..., description="Investigation title")
    objective: str | None = Field(None, description="What we're trying to determine")
    
    # Results
    observations: list[Observation] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    # LLM interaction tracking
    llm_calls: int = 0
    total_tokens: int = 0
    
    # Final report
    report: Report | None = None
    
    def add_observation(self, observation: Observation) -> None:
        """Add an observation to the investigation."""
        self.observations.append(observation)
    
    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Add a hypothesis to the investigation."""
        self.hypotheses.append(hypothesis)
    
    def add_action(self, action: Action) -> None:
        """Add an action to the investigation."""
        self.actions.append(action)
    
    def get_active_hypotheses(self) -> list[Hypothesis]:
        """Get hypotheses still being investigated."""
        return [h for h in self.hypotheses if h.status == HypothesisStatus.INVESTIGATING]
    
    def get_confirmed_hypotheses(self) -> list[Hypothesis]:
        """Get confirmed hypotheses."""
        return [h for h in self.hypotheses if h.status == HypothesisStatus.CONFIRMED]


class ObservationType(str, Enum):
    """Types of observations during investigation."""
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    RESOURCE = "resource"
    CONFIG = "config"
    COMMAND = "command"
    API_RESPONSE = "api_response"


class Observation(BaseModel):
    """An observation gathered during investigation."""
    
    id: UUID = Field(default_factory=uuid4)
    type: ObservationType
    
    # What was observed
    source: str = Field(..., description="Where this came from (prometheus, k8s, etc)")
    query: str | None = Field(None, description="Query or command used")
    description: str = Field(..., description="Human-readable description")
    
    # The data
    data: Any = Field(..., description="Raw observation data")
    summary: str | None = Field(None, description="LLM-generated summary")
    
    # Relevance
    is_anomalous: bool = False
    relevance_score: float = Field(0.5, ge=0, le=1, description="How relevant to the investigation")
    
    # Timing
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    data_timestamp: datetime | None = Field(None, description="When the data was generated")
    
    def to_context_string(self) -> str:
        """Format observation for LLM context."""
        lines = [
            f"[{self.type.value.upper()}] {self.description}",
            f"Source: {self.source}",
        ]
        if self.query:
            lines.append(f"Query: {self.query}")
        if self.summary:
            lines.append(f"Summary: {self.summary}")
        if self.is_anomalous:
            lines.append("⚠️ ANOMALOUS")
        return "\n".join(lines)


class HypothesisStatus(str, Enum):
    """Hypothesis status during investigation."""
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class Hypothesis(BaseModel):
    """A hypothesis about the root cause."""
    
    id: UUID = Field(default_factory=uuid4)
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    
    # The hypothesis
    statement: str = Field(..., description="The hypothesis statement")
    reasoning: str | None = Field(None, description="Why this hypothesis was proposed")
    
    # Evidence
    supporting_observations: list[UUID] = Field(default_factory=list)
    contradicting_observations: list[UUID] = Field(default_factory=list)
    
    # Confidence
    confidence: float = Field(0.5, ge=0, le=1)
    
    # Verification
    verification_steps: list[str] = Field(default_factory=list)
    verification_result: str | None = None
    
    # Timing
    proposed_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    
    def add_supporting_evidence(self, observation_id: UUID) -> None:
        """Add supporting evidence."""
        if observation_id not in self.supporting_observations:
            self.supporting_observations.append(observation_id)
            self._update_confidence()
    
    def add_contradicting_evidence(self, observation_id: UUID) -> None:
        """Add contradicting evidence."""
        if observation_id not in self.contradicting_observations:
            self.contradicting_observations.append(observation_id)
            self._update_confidence()
    
    def _update_confidence(self) -> None:
        """Update confidence based on evidence."""
        supporting = len(self.supporting_observations)
        contradicting = len(self.contradicting_observations)
        total = supporting + contradicting
        if total > 0:
            self.confidence = supporting / total


class ActionType(str, Enum):
    """Types of actions that can be taken."""
    DIAGNOSTIC = "diagnostic"  # Read-only information gathering
    REMEDIATION = "remediation"  # Fixing the issue
    ESCALATION = "escalation"  # Escalating to humans
    NOTIFICATION = "notification"  # Sending notifications
    ROLLBACK = "rollback"  # Reverting changes
    SCALE = "scale"  # Scaling resources
    RESTART = "restart"  # Restarting services
    CONFIG_CHANGE = "config_change"  # Changing configuration


class ActionStatus(str, Enum):
    """Action execution status."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_APPROVAL = "requires_approval"


class Action(BaseModel):
    """An action to take during investigation or remediation."""
    
    id: UUID = Field(default_factory=uuid4)
    type: ActionType
    status: ActionStatus = ActionStatus.PENDING
    
    # What to do
    name: str = Field(..., description="Action name")
    description: str = Field(..., description="What this action does")
    
    # Execution details
    tool: str | None = Field(None, description="Tool/plugin to use")
    command: str | None = Field(None, description="Command to execute")
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Safety
    is_destructive: bool = False
    requires_approval: bool = False
    risk_level: str = Field("low", pattern="^(low|medium|high|critical)$")
    
    # Results
    result: Any | None = None
    error: str | None = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Approval
    approved_by: str | None = None
    approved_at: datetime | None = None
    
    @property
    def duration_seconds(self) -> float | None:
        """Get action duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_context_string(self) -> str:
        """Format action for LLM context."""
        lines = [
            f"Action: {self.name}",
            f"Type: {self.type.value}",
            f"Status: {self.status.value}",
            f"Description: {self.description}",
        ]
        if self.tool:
            lines.append(f"Tool: {self.tool}")
        if self.is_destructive:
            lines.append("⚠️ DESTRUCTIVE")
        if self.requires_approval:
            lines.append("🔒 REQUIRES APPROVAL")
        return "\n".join(lines)


class Report(BaseModel):
    """Final investigation report."""
    
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    
    # Summary
    title: str
    executive_summary: str = Field(..., description="Brief summary for stakeholders")
    
    # Root cause
    root_cause: str | None = Field(None, description="Identified root cause")
    root_cause_confidence: float = Field(0.0, ge=0, le=1)
    
    # Timeline
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    
    # Impact
    impact_summary: str | None = None
    affected_services: list[str] = Field(default_factory=list)
    affected_users: int | None = None
    downtime_seconds: float | None = None
    
    # Resolution
    resolution_summary: str | None = None
    actions_taken: list[str] = Field(default_factory=list)
    
    # Recommendations
    recommendations: list[str] = Field(default_factory=list)
    preventive_measures: list[str] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "autosre"
    
    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# {self.title}",
            "",
            "## Executive Summary",
            self.executive_summary,
            "",
        ]
        
        if self.root_cause:
            lines.extend([
                "## Root Cause",
                f"{self.root_cause}",
                f"*Confidence: {self.root_cause_confidence:.0%}*",
                "",
            ])
        
        if self.impact_summary:
            lines.extend([
                "## Impact",
                self.impact_summary,
            ])
            if self.affected_services:
                lines.append(f"- Affected services: {', '.join(self.affected_services)}")
            if self.downtime_seconds:
                lines.append(f"- Downtime: {self.downtime_seconds / 60:.1f} minutes")
            lines.append("")
        
        if self.timeline:
            lines.extend(["## Timeline", ""])
            for event in self.timeline:
                ts = event.get("timestamp", "")
                desc = event.get("description", "")
                lines.append(f"- **{ts}**: {desc}")
            lines.append("")
        
        if self.resolution_summary:
            lines.extend([
                "## Resolution",
                self.resolution_summary,
                "",
            ])
            if self.actions_taken:
                lines.append("### Actions Taken")
                for action in self.actions_taken:
                    lines.append(f"- {action}")
                lines.append("")
        
        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        
        if self.preventive_measures:
            lines.extend(["## Preventive Measures", ""])
            for measure in self.preventive_measures:
                lines.append(f"- {measure}")
            lines.append("")
        
        lines.extend([
            "---",
            f"*Generated by {self.generated_by} at {self.generated_at.isoformat()}*",
        ])
        
        return "\n".join(lines)


# Type aliases for convenience
AlertDict = dict[str, Any]
ObservationDict = dict[str, Any]
