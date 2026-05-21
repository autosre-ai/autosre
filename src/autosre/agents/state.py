"""Investigation state models with enhanced SRE phases and telemetry."""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ----- Investigation Phases (SRE-style lifecycle) -----

class InvestigationPhase(str, Enum):
    """Investigation phases following SRE best practices.
    
    TRIAGE → MITIGATE → INVESTIGATE → REMEDIATE → VERIFY → DOCUMENT
    """
    TRIAGE = "triage"           # Initial assessment, golden signals, severity
    MITIGATE = "mitigate"       # Stop the bleeding, reduce blast radius
    INVESTIGATE = "investigate"  # Root cause analysis
    REMEDIATE = "remediate"      # Fix the underlying issue
    VERIFY = "verify"            # Confirm fix works
    DOCUMENT = "document"        # Postmortem, learnings


class PhaseRequirements:
    """Requirements that must be met before advancing phases."""
    
    REQUIREMENTS: Dict[InvestigationPhase, List[str]] = {
        InvestigationPhase.TRIAGE: [],  # Can start immediately
        InvestigationPhase.MITIGATE: ["triage_completed", "severity_assessed"],
        InvestigationPhase.INVESTIGATE: ["mitigation_attempted_or_skipped"],
        InvestigationPhase.REMEDIATE: ["root_cause_identified", "confidence_threshold_met"],
        InvestigationPhase.VERIFY: ["remediation_applied"],
        InvestigationPhase.DOCUMENT: ["verification_completed"],
    }


# ----- Core Models -----

class Alert(BaseModel):
    """Input alert to investigate."""
    name: str
    service: Optional[str] = None
    severity: Literal["critical", "warning", "info"] = "warning"
    description: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = {}


class Hypothesis(BaseModel):
    """A potential root cause hypothesis."""
    hypothesis: str
    priority: Literal["high", "medium", "low"] = "medium"
    agents_to_test: List[str] = []
    confidence: float = 0.5


class Evidence(BaseModel):
    """Evidence gathered by a subagent."""
    source: str  # Which agent found this
    skill: str   # Which skill was used
    finding: str
    confidence: float = 0.5
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Optional[Dict] = None
    supports_hypothesis: Optional[str] = None  # Which hypothesis this supports
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)  # Evidence quality rating


class AgentResult(BaseModel):
    """Result from a subagent investigation."""
    agent_id: str
    status: Literal["completed", "failed", "timeout"] = "completed"
    evidence: List[Evidence] = []
    summary: str = ""
    duration_seconds: float = 0.0


# ----- SLO and Error Budget Context -----

class SLOTarget(BaseModel):
    """SLO target definition."""
    name: str
    target_percent: float  # e.g., 99.9
    window_days: int = 30
    current_percent: float = 100.0
    budget_remaining_percent: float = 100.0


class SLOContext(BaseModel):
    """SLO context for the affected service."""
    service: str
    slo_targets: List[SLOTarget] = []
    error_budget_burn_rate: float = 0.0  # Current burn rate (1.0 = normal, 2.0 = 2x burn)
    time_to_budget_exhaustion_hours: Optional[float] = None
    is_budget_critical: bool = False  # True if < 10% remaining
    
    @property
    def most_critical_slo(self) -> Optional[SLOTarget]:
        """Get the SLO with lowest remaining budget."""
        if not self.slo_targets:
            return None
        return min(self.slo_targets, key=lambda s: s.budget_remaining_percent)


# ----- Triage Results -----

class GoldenSignals(BaseModel):
    """Google SRE golden signals."""
    latency_p50_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None
    latency_change_percent: Optional[float] = None
    error_rate_percent: Optional[float] = None
    error_rate_change_percent: Optional[float] = None
    traffic_rps: Optional[float] = None
    traffic_change_percent: Optional[float] = None
    saturation_cpu_percent: Optional[float] = None
    saturation_memory_percent: Optional[float] = None
    saturation_disk_percent: Optional[float] = None


class TriageResult(BaseModel):
    """Result of the triage phase."""
    severity_assessed: Literal["critical", "high", "medium", "low"] = "medium"
    blast_radius: str = ""  # e.g., "10% of users", "all traffic to /api/v2"
    services_affected: List[str] = []
    golden_signals: GoldenSignals = Field(default_factory=GoldenSignals)
    immediate_action_required: bool = False
    triage_summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ----- Changes Correlation -----

class Change(BaseModel):
    """A recent change that might be correlated to the incident."""
    change_type: Literal["deployment", "config", "infra", "dependency", "feature_flag", "other"] = "other"
    timestamp: datetime
    author: str = ""
    description: str = ""
    service: str = ""
    artifact: str = ""  # e.g., commit SHA, deployment ID
    rollback_available: bool = False
    correlation_score: float = 0.0  # How likely this caused the issue


# ----- AI Telemetry -----

class AIHypothesis(BaseModel):
    """AI-generated hypothesis with counter-checks."""
    hypothesis: str
    initial_confidence: float = 0.5
    current_confidence: float = 0.5
    supporting_evidence: List[str] = []
    contradicting_evidence: List[str] = []
    counter_checks_performed: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AIDecision(BaseModel):
    """Record of an AI decision for telemetry."""
    decision_type: str  # e.g., "hypothesis_selection", "tool_call", "phase_transition"
    decision: str
    reasoning: str
    confidence: float
    alternatives_considered: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AITelemetry(BaseModel):
    """Telemetry data for AI decisions throughout investigation."""
    decisions: List[AIDecision] = []
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens_used: int = 0
    average_confidence: float = 0.0
    confidence_trend: List[float] = []  # Confidence over time


# ----- Phase Timing -----

class PhaseTransition(BaseModel):
    """Record of a phase transition."""
    from_phase: Optional[InvestigationPhase] = None
    to_phase: InvestigationPhase
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0
    requirements_met: List[str] = []
    reason: str = ""


class PhaseTiming(BaseModel):
    """Timing breakdown by phase."""
    transitions: List[PhaseTransition] = []
    phase_durations: Dict[str, float] = {}  # phase -> duration in seconds
    
    def record_transition(
        self,
        from_phase: Optional[InvestigationPhase],
        to_phase: InvestigationPhase,
        requirements_met: List[str],
        reason: str = "",
    ) -> None:
        """Record a phase transition."""
        now = datetime.utcnow()
        duration = 0.0
        
        if self.transitions:
            last = self.transitions[-1]
            duration = (now - last.timestamp).total_seconds()
            if last.to_phase:
                phase_key = last.to_phase.value
                self.phase_durations[phase_key] = self.phase_durations.get(phase_key, 0) + duration
        
        self.transitions.append(PhaseTransition(
            from_phase=from_phase,
            to_phase=to_phase,
            timestamp=now,
            duration_seconds=duration,
            requirements_met=requirements_met,
            reason=reason,
        ))


# ----- Investigation State -----

class InvestigationState(BaseModel):
    """Complete state of an investigation."""
    # Input
    investigation_id: str
    alert: Alert
    
    # Context
    memory_context: Dict = {}
    topology_context: Dict = {}
    
    # Planning
    hypotheses: List[Hypothesis] = []
    selected_agents: List[str] = []
    
    # Results
    agent_results: Dict[str, AgentResult] = {}
    
    # Synthesis
    conclusion: str = ""
    root_cause: Optional[str] = None
    confidence: float = 0.0
    
    # Control
    iteration: int = 0
    max_iterations: int = 3
    status: Literal["running", "completed", "failed"] = "running"
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class EnhancedInvestigationState(BaseModel):
    """Enhanced investigation state with SRE phases and AI telemetry.
    
    Extends InvestigationState with:
    - Phase management (TRIAGE → MITIGATE → INVESTIGATE → REMEDIATE → VERIFY → DOCUMENT)
    - SLO context and error budget tracking
    - Change correlation
    - AI hypothesis management with counter-checks
    - Detailed telemetry for postmortems
    """
    # Input
    investigation_id: str
    alert: Alert
    
    # Context
    memory_context: Dict[str, Any] = {}
    topology_context: Dict[str, Any] = {}
    
    # Phase Management
    phase: InvestigationPhase = InvestigationPhase.TRIAGE
    phase_timing: PhaseTiming = Field(default_factory=PhaseTiming)
    phase_blockers: List[str] = []  # Requirements not yet met
    
    # Triage
    triage_result: Optional[TriageResult] = None
    
    # Mitigation
    mitigation_attempted: bool = False
    mitigation_actions: List[str] = []
    mitigation_effective: Optional[bool] = None
    
    # SLO Context
    slo_context: Optional[SLOContext] = None
    error_budget_impact: float = 0.0  # Estimated % of budget consumed by this incident
    
    # Changes Correlation (early in flow)
    changes_correlated: List[Change] = []
    likely_change_cause: Optional[Change] = None
    
    # AI Hypothesis Management
    ai_hypotheses: List[AIHypothesis] = []
    ai_confidence: float = 0.0  # Overall AI confidence in current conclusion
    
    # Evidence Management
    evidence_collected: List[Evidence] = []
    evidence_quality_score: float = 0.0  # Average quality of evidence
    
    # Planning (from original state)
    hypotheses: List[Hypothesis] = []
    selected_agents: List[str] = []
    
    # Results
    agent_results: Dict[str, AgentResult] = {}
    
    # Synthesis
    conclusion: str = ""
    root_cause: Optional[str] = None
    confidence: float = 0.0
    contributing_factors: List[str] = []
    
    # Control
    iteration: int = 0
    max_iterations: int = 5
    status: Literal["running", "completed", "failed", "blocked"] = "running"
    
    # AI Telemetry
    ai_telemetry: AITelemetry = Field(default_factory=AITelemetry)
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Postmortem
    postmortem_generated: bool = False
    postmortem_path: Optional[str] = None
    
    def can_advance_to_phase(self, target_phase: InvestigationPhase) -> tuple[bool, List[str]]:
        """Check if we can advance to the target phase.
        
        Returns:
            Tuple of (can_advance, missing_requirements)
        """
        requirements = PhaseRequirements.REQUIREMENTS.get(target_phase, [])
        missing = []
        
        for req in requirements:
            if not self._check_requirement(req):
                missing.append(req)
        
        return len(missing) == 0, missing
    
    def _check_requirement(self, requirement: str) -> bool:
        """Check if a specific requirement is met."""
        checks = {
            "triage_completed": lambda: self.triage_result is not None,
            "severity_assessed": lambda: self.triage_result is not None and self.triage_result.severity_assessed is not None,
            "mitigation_attempted_or_skipped": lambda: self.mitigation_attempted or (self.triage_result and not self.triage_result.immediate_action_required),
            "root_cause_identified": lambda: self.root_cause is not None,
            "confidence_threshold_met": lambda: self.confidence >= 0.7,
            "remediation_applied": lambda: len([r for r in self.agent_results.values() if "remediation" in r.agent_id]) > 0,
            "verification_completed": lambda: self.phase == InvestigationPhase.VERIFY,
        }
        
        check_fn = checks.get(requirement)
        if check_fn:
            return check_fn()
        return False
    
    def advance_phase(self, reason: str = "") -> bool:
        """Attempt to advance to the next phase.
        
        Returns:
            True if phase was advanced, False if blocked
        """
        phase_order = [
            InvestigationPhase.TRIAGE,
            InvestigationPhase.MITIGATE,
            InvestigationPhase.INVESTIGATE,
            InvestigationPhase.REMEDIATE,
            InvestigationPhase.VERIFY,
            InvestigationPhase.DOCUMENT,
        ]
        
        current_idx = phase_order.index(self.phase)
        if current_idx >= len(phase_order) - 1:
            return False  # Already at final phase
        
        next_phase = phase_order[current_idx + 1]
        can_advance, missing = self.can_advance_to_phase(next_phase)
        
        if can_advance:
            self.phase_timing.record_transition(
                from_phase=self.phase,
                to_phase=next_phase,
                requirements_met=PhaseRequirements.REQUIREMENTS.get(next_phase, []),
                reason=reason,
            )
            self.phase = next_phase
            self.phase_blockers = []
            return True
        else:
            self.phase_blockers = missing
            self.status = "blocked"
            return False
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence and update quality score."""
        self.evidence_collected.append(evidence)
        if self.evidence_collected:
            self.evidence_quality_score = sum(
                e.quality_score for e in self.evidence_collected
            ) / len(self.evidence_collected)
    
    def add_ai_decision(self, decision: AIDecision) -> None:
        """Record an AI decision for telemetry."""
        self.ai_telemetry.decisions.append(decision)
        self.ai_telemetry.confidence_trend.append(decision.confidence)
        if self.ai_telemetry.confidence_trend:
            self.ai_telemetry.average_confidence = sum(
                self.ai_telemetry.confidence_trend
            ) / len(self.ai_telemetry.confidence_trend)
    
    def update_hypothesis_confidence(
        self,
        hypothesis: str,
        new_evidence: Evidence,
        supports: bool,
    ) -> None:
        """Update hypothesis confidence based on new evidence."""
        for h in self.ai_hypotheses:
            if h.hypothesis == hypothesis:
                if supports:
                    h.supporting_evidence.append(new_evidence.finding)
                    # Increase confidence (diminishing returns)
                    h.current_confidence = min(0.95, h.current_confidence + (1 - h.current_confidence) * 0.2)
                else:
                    h.contradicting_evidence.append(new_evidence.finding)
                    # Decrease confidence
                    h.current_confidence = max(0.05, h.current_confidence * 0.7)
                break
    
    def get_duration_by_phase(self) -> Dict[str, float]:
        """Get time spent in each phase."""
        return self.phase_timing.phase_durations
    
    def to_investigation_state(self) -> InvestigationState:
        """Convert to basic InvestigationState for backwards compatibility."""
        return InvestigationState(
            investigation_id=self.investigation_id,
            alert=self.alert,
            memory_context=self.memory_context,
            topology_context=self.topology_context,
            hypotheses=self.hypotheses,
            selected_agents=self.selected_agents,
            agent_results=self.agent_results,
            conclusion=self.conclusion,
            root_cause=self.root_cause,
            confidence=self.confidence,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            status=self.status if self.status != "blocked" else "running",
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


class InvestigationPlan(BaseModel):
    """Output from the planner."""
    hypotheses: List[Hypothesis]
    selected_agents: List[str]
    reasoning: str
