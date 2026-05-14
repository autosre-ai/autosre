"""
Chaos Engineering data models.

Defines all data structures for chaos experiments.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FaultType(str, Enum):
    """Types of faults that can be injected."""
    
    # Resource faults
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    IO_STRESS = "io_stress"
    DISK_FILL = "disk_fill"
    
    # Network faults
    NETWORK_LATENCY = "network_latency"
    NETWORK_LOSS = "network_loss"
    NETWORK_CORRUPTION = "network_corruption"
    NETWORK_PARTITION = "network_partition"
    DNS_FAILURE = "dns_failure"
    
    # Container/Pod faults
    POD_KILL = "pod_kill"
    POD_FAILURE = "pod_failure"
    CONTAINER_KILL = "container_kill"
    
    # Node faults
    NODE_DRAIN = "node_drain"
    NODE_FAILURE = "node_failure"
    
    # Application faults
    HTTP_ABORT = "http_abort"
    HTTP_DELAY = "http_delay"
    GRPC_ABORT = "grpc_abort"
    
    # Time faults
    TIME_TRAVEL = "time_travel"
    
    # Custom
    CUSTOM = "custom"


class FaultSeverity(str, Enum):
    """Severity of a fault."""
    
    MINOR = "minor"         # Minimal impact
    MODERATE = "moderate"   # Noticeable impact
    MAJOR = "major"         # Significant impact
    CRITICAL = "critical"   # Severe impact


class TargetType(str, Enum):
    """Type of chaos target."""
    
    POD = "pod"
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    DAEMONSET = "daemonset"
    SERVICE = "service"
    NODE = "node"
    NAMESPACE = "namespace"
    CONTAINER = "container"


class ExperimentStatus(str, Enum):
    """Status of a chaos experiment."""
    
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class GameDayStatus(str, Enum):
    """Status of a game day."""
    
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Target(BaseModel):
    """Target for chaos injection."""
    
    type: TargetType
    name: str
    namespace: str | None = None
    
    # Selection criteria
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Percentage of targets to affect
    percentage: float = Field(100.0, ge=0, le=100)
    count: int | None = None  # Specific count instead of percentage
    
    # Node selection for node faults
    node_selector: dict[str, str] = Field(default_factory=dict)
    
    def to_label_selector(self) -> str:
        """Convert labels to Kubernetes label selector."""
        return ",".join(f"{k}={v}" for k, v in self.labels.items())


class Fault(BaseModel):
    """A fault to inject."""
    
    id: UUID = Field(default_factory=uuid4)
    type: FaultType
    severity: FaultSeverity = FaultSeverity.MODERATE
    
    # Target
    target: Target
    
    # Parameters
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Duration
    duration_seconds: int = Field(60, description="How long to inject fault")
    
    # Timing
    delay_seconds: int = Field(0, description="Delay before injection")
    ramp_time_seconds: int = Field(0, description="Time to ramp up to full effect")
    
    # Safety
    dry_run: bool = False
    abort_on_failure: bool = True
    
    def get_cpu_stress_params(self) -> dict[str, Any]:
        """Get parameters for CPU stress."""
        return {
            "workers": self.parameters.get("workers", 1),
            "load": self.parameters.get("load", 100),  # percentage
        }
    
    def get_memory_stress_params(self) -> dict[str, Any]:
        """Get parameters for memory stress."""
        return {
            "workers": self.parameters.get("workers", 1),
            "bytes": self.parameters.get("bytes", "256M"),
        }
    
    def get_network_latency_params(self) -> dict[str, Any]:
        """Get parameters for network latency."""
        return {
            "latency": self.parameters.get("latency", "100ms"),
            "jitter": self.parameters.get("jitter", "10ms"),
            "correlation": self.parameters.get("correlation", 25),
        }
    
    def get_network_loss_params(self) -> dict[str, Any]:
        """Get parameters for network loss."""
        return {
            "loss": self.parameters.get("loss", 25),  # percentage
            "correlation": self.parameters.get("correlation", 25),
        }


class SteadyStateHypothesis(BaseModel):
    """Steady state hypothesis for experiment validation."""
    
    name: str
    description: str = ""
    
    # Probe type
    probe_type: str = "http"  # http, tcp, prometheus, command
    
    # Probe configuration
    endpoint: str | None = None
    query: str | None = None
    command: str | None = None
    
    # Expected results
    expected_status: int | None = None  # HTTP status
    expected_value: Any = None
    threshold: float | None = None
    
    # Tolerance
    tolerance: float = Field(0.1, description="Acceptable deviation (0-1)")
    
    # Timing
    timeout_seconds: int = 30
    interval_seconds: int = 10
    
    def to_probe_config(self) -> dict[str, Any]:
        """Convert to probe configuration."""
        return {
            "type": self.probe_type,
            "endpoint": self.endpoint,
            "query": self.query,
            "command": self.command,
            "expected_status": self.expected_status,
            "expected_value": self.expected_value,
            "threshold": self.threshold,
            "tolerance": self.tolerance,
            "timeout_seconds": self.timeout_seconds,
        }


class ExperimentResult(BaseModel):
    """Result of a chaos experiment."""
    
    experiment_id: UUID
    
    # Overall result
    success: bool
    status: ExperimentStatus
    message: str = ""
    
    # Steady state validation
    steady_state_met_before: bool = True
    steady_state_met_during: bool = True
    steady_state_met_after: bool = True
    
    # Impact metrics
    impact_metrics: dict[str, Any] = Field(default_factory=dict)
    
    # Timeline
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    
    # Errors
    errors: list[str] = Field(default_factory=list)
    
    # Timing
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Rollback info
    was_rolled_back: bool = False
    rollback_success: bool | None = None
    
    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
    
    def add_event(
        self,
        event_type: str,
        description: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add event to timeline."""
        self.timeline.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "description": description,
            "data": data or {},
        })


class Experiment(BaseModel):
    """A chaos experiment definition."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    
    # Faults to inject
    faults: list[Fault] = Field(default_factory=list)
    
    # Steady state hypothesis
    steady_state: list[SteadyStateHypothesis] = Field(default_factory=list)
    
    # Execution
    status: ExperimentStatus = ExperimentStatus.PENDING
    
    # Timing
    duration_seconds: int = Field(300, description="Total experiment duration")
    warmup_seconds: int = Field(30, description="Warmup before fault injection")
    cooldown_seconds: int = Field(30, description="Cooldown after fault injection")
    
    # Scheduling
    scheduled_at: datetime | None = None
    recurrence: str | None = None  # Cron expression
    
    # Safety
    dry_run: bool = False
    abort_on_failure: bool = True
    require_approval: bool = True
    
    # Rollback
    auto_rollback: bool = True
    rollback_on_steady_state_failure: bool = True
    
    # Result
    result: ExperimentResult | None = None
    
    # Metadata
    owner: str | None = None
    team: str | None = None
    tags: list[str] = Field(default_factory=list)
    
    # Timing tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    @property
    def is_active(self) -> bool:
        return self.status in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]
    
    @property
    def total_duration_seconds(self) -> int:
        return self.warmup_seconds + self.duration_seconds + self.cooldown_seconds
    
    def get_fault_summary(self) -> str:
        """Get summary of faults."""
        if not self.faults:
            return "No faults"
        
        fault_types = [f.type.value for f in self.faults]
        return f"{len(self.faults)} faults: {', '.join(fault_types)}"


class ResilienceScore(BaseModel):
    """Resilience score for a system or service."""
    
    service: str
    namespace: str = "default"
    
    # Overall score (0-100)
    overall_score: float = Field(50.0, ge=0, le=100)
    
    # Component scores
    availability_score: float = Field(50.0, ge=0, le=100)
    recovery_score: float = Field(50.0, ge=0, le=100)
    degradation_score: float = Field(50.0, ge=0, le=100)
    blast_radius_score: float = Field(50.0, ge=0, le=100)
    
    # Experiment data
    experiments_run: int = 0
    experiments_passed: int = 0
    last_experiment_at: datetime | None = None
    
    # Recommendations
    recommendations: list[str] = Field(default_factory=list)
    
    # Trends
    score_trend: str = "stable"  # improving, declining, stable
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def pass_rate(self) -> float:
        if self.experiments_run == 0:
            return 0
        return self.experiments_passed / self.experiments_run
    
    def calculate_overall(self) -> float:
        """Calculate overall score from components."""
        weights = {
            "availability": 0.3,
            "recovery": 0.3,
            "degradation": 0.2,
            "blast_radius": 0.2,
        }
        
        self.overall_score = (
            self.availability_score * weights["availability"] +
            self.recovery_score * weights["recovery"] +
            self.degradation_score * weights["degradation"] +
            self.blast_radius_score * weights["blast_radius"]
        )
        
        return self.overall_score
    
    def get_grade(self) -> str:
        """Get letter grade from score."""
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"


class GameDay(BaseModel):
    """A game day event with multiple experiments."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    
    # Experiments
    experiments: list[Experiment] = Field(default_factory=list)
    experiment_order: list[UUID] = Field(default_factory=list)
    
    # Scheduling
    scheduled_date: datetime
    estimated_duration_hours: float = 4.0
    
    # Status
    status: GameDayStatus = GameDayStatus.PLANNED
    
    # Participants
    facilitator: str | None = None
    participants: list[str] = Field(default_factory=list)
    observers: list[str] = Field(default_factory=list)
    
    # Communication
    war_room_url: str | None = None
    slack_channel: str | None = None
    
    # Results
    overall_success: bool | None = None
    findings: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Metadata
    tags: list[str] = Field(default_factory=list)
    
    @property
    def completed_experiments(self) -> int:
        return sum(
            1 for e in self.experiments
            if e.status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED]
        )
    
    @property
    def successful_experiments(self) -> int:
        return sum(
            1 for e in self.experiments
            if e.result and e.result.success
        )
    
    def add_experiment(self, experiment: Experiment) -> None:
        """Add experiment to game day."""
        self.experiments.append(experiment)
        self.experiment_order.append(experiment.id)
    
    def get_next_experiment(self) -> Experiment | None:
        """Get next experiment to run."""
        for exp_id in self.experiment_order:
            exp = next((e for e in self.experiments if e.id == exp_id), None)
            if exp and exp.status == ExperimentStatus.PENDING:
                return exp
        return None
