"""
GameDay Automation Module

Provides GameDay planning, scheduling, and execution for
organized chaos engineering events.
"""

import uuid
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from autosre.chaos.experiments import (
    ChaosExperiment,
    ExperimentResult,
    ExperimentRunner,
    ExperimentState,
)


class GameDayState(str, Enum):
    """States of a GameDay event."""
    
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ParticipantRole(str, Enum):
    """Roles in a GameDay."""
    
    FACILITATOR = "facilitator"
    OBSERVER = "observer"
    RESPONDER = "responder"
    ENGINEER = "engineer"
    STAKEHOLDER = "stakeholder"


class Participant(BaseModel):
    """A participant in a GameDay."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    role: ParticipantRole
    team: str = ""
    slack_id: Optional[str] = None
    is_available: bool = True
    notes: str = ""


class GameDayScenario(BaseModel):
    """A scenario to execute during a GameDay.
    
    Scenarios are sequences of chaos experiments with
    defined objectives and success criteria.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Objectives
    hypothesis: str = Field(
        default="", description="What behavior we expect to see"
    )
    success_criteria: list[str] = Field(
        default_factory=list, description="Criteria for scenario success"
    )
    
    # Experiments in this scenario
    experiments: list[ChaosExperiment] = Field(default_factory=list)
    experiment_order: str = Field(
        default="sequential", description="sequential or parallel"
    )
    
    # Timing
    estimated_duration_minutes: int = Field(default=30)
    max_duration_minutes: int = Field(default=60)
    
    # Dependencies
    depends_on: list[str] = Field(
        default_factory=list, description="Scenario IDs this depends on"
    )
    
    # Observability
    dashboards: list[str] = Field(
        default_factory=list, description="Dashboard URLs to monitor"
    )
    alerts_to_watch: list[str] = Field(
        default_factory=list, description="Alert names to monitor"
    )
    metrics_to_track: list[str] = Field(
        default_factory=list, description="PromQL queries to track"
    )
    
    # Results
    executed: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    success: Optional[bool] = None
    findings: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


@dataclass
class GameDayResult:
    """Results from a GameDay execution."""
    
    gameday_id: str
    state: GameDayState
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Scenario results
    scenarios_total: int = 0
    scenarios_completed: int = 0
    scenarios_failed: int = 0
    scenarios_skipped: int = 0
    scenario_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Overall assessment
    overall_success: bool = False
    resilience_score: float = 0.0  # 0-100
    
    # Findings
    findings: list[str] = field(default_factory=list)
    weaknesses_found: list[str] = field(default_factory=list)
    strengths_observed: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    
    # Participation
    participants_active: list[str] = field(default_factory=list)
    participant_feedback: dict[str, str] = field(default_factory=dict)
    
    # Timeline
    events: list[dict[str, Any]] = field(default_factory=list)
    
    def add_event(self, event_type: str, message: str, data: Optional[dict] = None) -> None:
        """Add an event to the timeline."""
        self.events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "message": message,
            "data": data or {},
        })
    
    def calculate_resilience_score(self) -> float:
        """Calculate overall resilience score."""
        if self.scenarios_total == 0:
            return 0.0
            
        # Base score from scenario completion
        completion_rate = self.scenarios_completed / self.scenarios_total
        success_rate = (
            (self.scenarios_completed - self.scenarios_failed) / 
            max(self.scenarios_completed, 1)
        )
        
        # Weighted score
        score = (completion_rate * 40) + (success_rate * 60)
        
        # Deductions for critical findings
        score -= len(self.weaknesses_found) * 5
        
        self.resilience_score = max(0.0, min(100.0, score))
        return self.resilience_score


class GameDay(BaseModel):
    """A GameDay event for organized chaos engineering.
    
    GameDays are structured chaos engineering events that:
    - Have clear objectives and success criteria
    - Include multiple scenarios and experiments
    - Involve cross-functional participants
    - Generate actionable findings and reports
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Planning
    objectives: list[str] = Field(default_factory=list)
    scope: str = Field(
        default="", description="Systems and services in scope"
    )
    out_of_scope: str = Field(
        default="", description="Systems explicitly excluded"
    )
    
    # Scenarios
    scenarios: list[GameDayScenario] = Field(default_factory=list)
    
    # Participants
    facilitator: Optional[Participant] = None
    participants: list[Participant] = Field(default_factory=list)
    required_roles: list[ParticipantRole] = Field(
        default_factory=lambda: [ParticipantRole.FACILITATOR, ParticipantRole.RESPONDER]
    )
    
    # Scheduling
    state: GameDayState = GameDayState.DRAFT
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    timezone: str = Field(default="UTC")
    
    # Safety
    emergency_contacts: list[str] = Field(default_factory=list)
    rollback_plan: str = Field(default="")
    abort_criteria: list[str] = Field(default_factory=list)
    max_blast_radius: str = Field(
        default="single-service", description="single-pod, single-service, namespace, cluster"
    )
    
    # Communication
    slack_channel: Optional[str] = None
    war_room_link: Optional[str] = None
    runbook_link: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Results
    result: Optional[dict[str, Any]] = None
    
    class Config:
        use_enum_values = True
    
    def add_scenario(self, scenario: GameDayScenario) -> None:
        """Add a scenario to the GameDay."""
        self.scenarios.append(scenario)
    
    def add_participant(self, participant: Participant) -> None:
        """Add a participant to the GameDay."""
        self.participants.append(participant)
        if participant.role == ParticipantRole.FACILITATOR:
            self.facilitator = participant
    
    def is_ready(self) -> tuple[bool, list[str]]:
        """Check if GameDay is ready to run."""
        issues = []
        
        # Check scenarios
        if not self.scenarios:
            issues.append("No scenarios defined")
        
        # Check participants
        if not self.facilitator:
            issues.append("No facilitator assigned")
        
        for role in self.required_roles:
            if not any(p.role == role for p in self.participants):
                issues.append(f"Missing required role: {role}")
        
        # Check safety
        if not self.emergency_contacts:
            issues.append("No emergency contacts defined")
        if not self.rollback_plan:
            issues.append("No rollback plan defined")
        
        # Check scheduling
        if not self.scheduled_start:
            issues.append("No start time scheduled")
        
        return len(issues) == 0, issues
    
    def get_duration_estimate(self) -> timedelta:
        """Estimate total GameDay duration."""
        total_minutes = sum(s.estimated_duration_minutes for s in self.scenarios)
        # Add buffer for transitions and discussions
        total_minutes = int(total_minutes * 1.3)
        return timedelta(minutes=total_minutes)


class GameDayRunner:
    """Executes GameDay events."""
    
    def __init__(
        self,
        experiment_runner: ExperimentRunner,
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.experiment_runner = experiment_runner
        self.notify_callback = notify_callback
        self._current_gameday: Optional[GameDay] = None
        self._result: Optional[GameDayResult] = None
        self._abort_requested: bool = False
    
    async def run(self, gameday: GameDay) -> GameDayResult:
        """Execute a GameDay."""
        is_ready, issues = gameday.is_ready()
        if not is_ready:
            raise ValueError(f"GameDay not ready: {', '.join(issues)}")
        
        self._current_gameday = gameday
        self._abort_requested = False
        
        result = GameDayResult(
            gameday_id=gameday.id,
            state=GameDayState.RUNNING,
            start_time=datetime.utcnow(),
            scenarios_total=len(gameday.scenarios),
        )
        self._result = result
        
        result.add_event("started", f"GameDay '{gameday.name}' started")
        await self._notify(f"🎮 GameDay Started: {gameday.name}")
        
        gameday.state = GameDayState.RUNNING
        
        try:
            # Execute scenarios
            for scenario in gameday.scenarios:
                if self._abort_requested:
                    result.add_event("aborted", "GameDay aborted by user")
                    break
                
                # Check dependencies
                if not self._check_dependencies(scenario, result):
                    result.scenarios_skipped += 1
                    result.scenario_results[scenario.id] = {
                        "status": "skipped",
                        "reason": "Dependencies not met",
                    }
                    continue
                
                # Run scenario
                scenario_result = await self._run_scenario(scenario)
                result.scenario_results[scenario.id] = scenario_result
                
                if scenario_result.get("success"):
                    result.scenarios_completed += 1
                else:
                    result.scenarios_failed += 1
                
                # Check abort criteria
                if self._should_abort(gameday, result):
                    result.add_event("abort_triggered", "Abort criteria met")
                    await self._notify("⚠️ GameDay abort criteria met, stopping")
                    break
            
            # Finalize
            if self._abort_requested:
                result.state = GameDayState.CANCELLED
                gameday.state = GameDayState.CANCELLED
            elif result.scenarios_failed > 0:
                result.state = GameDayState.FAILED
                gameday.state = GameDayState.FAILED
            else:
                result.state = GameDayState.COMPLETED
                gameday.state = GameDayState.COMPLETED
            
            result.end_time = datetime.utcnow()
            result.calculate_resilience_score()
            result.overall_success = result.resilience_score >= 70
            
            # Aggregate findings
            for scenario in gameday.scenarios:
                result.findings.extend(scenario.findings)
                result.action_items.extend(scenario.action_items)
            
            gameday.result = {
                "state": result.state.value if isinstance(result.state, Enum) else result.state,
                "resilience_score": result.resilience_score,
                "findings_count": len(result.findings),
                "action_items_count": len(result.action_items),
            }
            
            result.add_event("completed", f"GameDay completed with score {result.resilience_score:.1f}")
            await self._notify(
                f"✅ GameDay Completed: {gameday.name}\n"
                f"Score: {result.resilience_score:.1f}/100"
            )
            
        except Exception as e:
            result.state = GameDayState.FAILED
            gameday.state = GameDayState.FAILED
            result.add_event("error", f"GameDay failed: {e}")
            await self._notify(f"❌ GameDay Failed: {e}")
            raise
        
        return result
    
    async def pause(self) -> bool:
        """Pause the current GameDay."""
        if self._current_gameday and self._current_gameday.state == GameDayState.RUNNING:
            self._current_gameday.state = GameDayState.PAUSED
            if self._result:
                self._result.add_event("paused", "GameDay paused")
            await self._notify("⏸️ GameDay paused")
            return True
        return False
    
    async def resume(self) -> bool:
        """Resume a paused GameDay."""
        if self._current_gameday and self._current_gameday.state == GameDayState.PAUSED:
            self._current_gameday.state = GameDayState.RUNNING
            if self._result:
                self._result.add_event("resumed", "GameDay resumed")
            await self._notify("▶️ GameDay resumed")
            return True
        return False
    
    async def abort(self, reason: str = "User requested") -> bool:
        """Abort the current GameDay."""
        self._abort_requested = True
        if self._result:
            self._result.add_event("abort_requested", f"Abort requested: {reason}")
        await self._notify(f"🛑 GameDay abort requested: {reason}")
        return True
    
    async def _run_scenario(self, scenario: GameDayScenario) -> dict[str, Any]:
        """Execute a single scenario."""
        scenario.executed = True
        scenario.start_time = datetime.utcnow()
        
        result_data: dict[str, Any] = {
            "scenario_id": scenario.id,
            "name": scenario.name,
            "start_time": scenario.start_time.isoformat(),
            "experiments": [],
            "success": True,
        }
        
        if self._result:
            self._result.add_event(
                "scenario_started",
                f"Starting scenario: {scenario.name}",
                {"scenario_id": scenario.id},
            )
        
        await self._notify(f"🔬 Running scenario: {scenario.name}")
        
        try:
            if scenario.experiment_order == "parallel":
                # Run experiments in parallel
                tasks = [
                    self.experiment_runner.run(exp)
                    for exp in scenario.experiments
                ]
                exp_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for exp, exp_result in zip(scenario.experiments, exp_results):
                    if isinstance(exp_result, Exception):
                        result_data["experiments"].append({
                            "id": exp.id,
                            "success": False,
                            "error": str(exp_result),
                        })
                        result_data["success"] = False
                    else:
                        result_data["experiments"].append({
                            "id": exp.id,
                            "success": exp_result.is_successful(),
                            "findings": exp_result.findings,
                        })
                        if not exp_result.is_successful():
                            result_data["success"] = False
            else:
                # Run experiments sequentially
                for exp in scenario.experiments:
                    if self._abort_requested:
                        break
                    
                    exp_result = await self.experiment_runner.run(exp)
                    result_data["experiments"].append({
                        "id": exp.id,
                        "success": exp_result.is_successful(),
                        "findings": exp_result.findings,
                    })
                    
                    if not exp_result.is_successful():
                        result_data["success"] = False
                        # Continue with other experiments unless abort
                        
        except Exception as e:
            result_data["success"] = False
            result_data["error"] = str(e)
        
        scenario.end_time = datetime.utcnow()
        scenario.success = result_data["success"]
        
        result_data["end_time"] = scenario.end_time.isoformat()
        result_data["duration_seconds"] = (
            scenario.end_time - scenario.start_time
        ).total_seconds()
        
        return result_data
    
    def _check_dependencies(self, scenario: GameDayScenario, result: GameDayResult) -> bool:
        """Check if scenario dependencies are met."""
        for dep_id in scenario.depends_on:
            dep_result = result.scenario_results.get(dep_id)
            if not dep_result or not dep_result.get("success"):
                return False
        return True
    
    def _should_abort(self, gameday: GameDay, result: GameDayResult) -> bool:
        """Check if GameDay should abort based on criteria."""
        for criterion in gameday.abort_criteria:
            criterion_lower = criterion.lower()
            
            if "failure_rate" in criterion_lower:
                # Parse "failure_rate > 50%"
                try:
                    threshold = int(criterion_lower.split(">")[1].strip().replace("%", ""))
                    total = result.scenarios_completed + result.scenarios_failed
                    if total > 0:
                        failure_rate = (result.scenarios_failed / total) * 100
                        if failure_rate > threshold:
                            return True
                except (ValueError, IndexError):
                    pass
            
            if "consecutive_failures" in criterion_lower:
                # Parse "consecutive_failures > 2"
                try:
                    threshold = int(criterion_lower.split(">")[1].strip())
                    # Check last N results
                    recent = list(result.scenario_results.values())[-threshold:]
                    if len(recent) >= threshold:
                        if all(not r.get("success") for r in recent):
                            return True
                except (ValueError, IndexError):
                    pass
        
        return False
    
    async def _notify(self, message: str) -> None:
        """Send notification."""
        if self.notify_callback:
            self.notify_callback("gameday", message)


class GameDayScheduler:
    """Schedules and manages GameDay events."""
    
    def __init__(self):
        self._gamedays: dict[str, GameDay] = {}
        self._scheduled: list[str] = []
    
    def schedule(self, gameday: GameDay, start_time: datetime) -> bool:
        """Schedule a GameDay for future execution."""
        is_ready, issues = gameday.is_ready()
        
        # Check for conflicts
        for other_id in self._scheduled:
            other = self._gamedays.get(other_id)
            if other and other.scheduled_start:
                # Simple overlap check
                other_end = other.scheduled_end or (
                    other.scheduled_start + other.get_duration_estimate()
                )
                new_end = gameday.scheduled_end or (
                    start_time + gameday.get_duration_estimate()
                )
                
                if start_time < other_end and new_end > other.scheduled_start:
                    raise ValueError(
                        f"Schedule conflict with GameDay '{other.name}'"
                    )
        
        gameday.scheduled_start = start_time
        gameday.scheduled_end = start_time + gameday.get_duration_estimate()
        gameday.state = GameDayState.SCHEDULED
        
        self._gamedays[gameday.id] = gameday
        self._scheduled.append(gameday.id)
        
        return True
    
    def cancel(self, gameday_id: str) -> bool:
        """Cancel a scheduled GameDay."""
        if gameday_id in self._gamedays:
            self._gamedays[gameday_id].state = GameDayState.CANCELLED
            if gameday_id in self._scheduled:
                self._scheduled.remove(gameday_id)
            return True
        return False
    
    def reschedule(self, gameday_id: str, new_start_time: datetime) -> bool:
        """Reschedule a GameDay."""
        if gameday_id in self._gamedays:
            gameday = self._gamedays[gameday_id]
            if gameday_id in self._scheduled:
                self._scheduled.remove(gameday_id)
            return self.schedule(gameday, new_start_time)
        return False
    
    def get_upcoming(self, within_hours: int = 24) -> list[GameDay]:
        """Get GameDays scheduled within the next N hours."""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=within_hours)
        
        upcoming = []
        for gameday_id in self._scheduled:
            gameday = self._gamedays.get(gameday_id)
            if gameday and gameday.scheduled_start:
                if now <= gameday.scheduled_start <= cutoff:
                    upcoming.append(gameday)
        
        return sorted(upcoming, key=lambda g: g.scheduled_start or now)
    
    def get_by_id(self, gameday_id: str) -> Optional[GameDay]:
        """Get a GameDay by ID."""
        return self._gamedays.get(gameday_id)
    
    def list_all(
        self,
        state: Optional[GameDayState] = None,
        limit: int = 100,
    ) -> list[GameDay]:
        """List all GameDays, optionally filtered by state."""
        gamedays = list(self._gamedays.values())
        
        if state:
            gamedays = [g for g in gamedays if g.state == state]
        
        return sorted(
            gamedays,
            key=lambda g: g.scheduled_start or g.created_at,
            reverse=True,
        )[:limit]


# =============================================================================
# GameDay Templates
# =============================================================================

def create_service_resilience_gameday(
    service_name: str,
    namespace: str = "default",
    labels: Optional[dict[str, str]] = None,
) -> GameDay:
    """Create a standard service resilience GameDay template."""
    from autosre.chaos.experiments import (
        ChaosExperiment,
        ExperimentConfig,
        ExperimentType,
        TargetSelector,
        ExperimentSchedule,
    )
    
    target = TargetSelector(
        namespaces=[namespace],
        label_selectors=labels or {"app": service_name},
    )
    
    # Scenario 1: Pod failure recovery
    pod_failure_exp = ChaosExperiment(
        name=f"{service_name}-pod-failure",
        description="Test pod failure recovery",
        hypothesis=f"{service_name} should recover from single pod failure within 60s",
        config=ExperimentConfig(
            experiment_type=ExperimentType.POD_CHAOS,
            target=target,
            schedule=ExperimentSchedule(duration="30s"),
            fault_config={"action": "pod-kill", "gracePeriod": 0},
        ),
    )
    
    pod_scenario = GameDayScenario(
        name="Pod Failure Recovery",
        description=f"Test {service_name} recovery from pod failures",
        hypothesis=f"{service_name} maintains availability during pod failures",
        success_criteria=[
            "Service responds within 5 seconds during experiment",
            "All pods recover within 60 seconds",
            "No data loss observed",
        ],
        experiments=[pod_failure_exp],
        estimated_duration_minutes=15,
    )
    
    # Scenario 2: Network latency tolerance
    network_exp = ChaosExperiment(
        name=f"{service_name}-network-delay",
        description="Test network latency tolerance",
        hypothesis=f"{service_name} handles 200ms latency gracefully",
        config=ExperimentConfig(
            experiment_type=ExperimentType.NETWORK_CHAOS,
            target=target,
            schedule=ExperimentSchedule(duration="2m"),
            fault_config={
                "action": "delay",
                "delay": {"latency": "200ms", "jitter": "50ms"},
            },
        ),
    )
    
    network_scenario = GameDayScenario(
        name="Network Latency Tolerance",
        description=f"Test {service_name} behavior under network latency",
        hypothesis=f"{service_name} degrades gracefully under network latency",
        success_criteria=[
            "P99 latency stays under 1 second",
            "No timeout errors to end users",
            "Proper timeout handling in logs",
        ],
        experiments=[network_exp],
        estimated_duration_minutes=20,
        depends_on=[pod_scenario.id],
    )
    
    # Scenario 3: Resource pressure
    stress_exp = ChaosExperiment(
        name=f"{service_name}-cpu-stress",
        description="Test behavior under CPU pressure",
        hypothesis=f"{service_name} handles CPU contention",
        config=ExperimentConfig(
            experiment_type=ExperimentType.STRESS_CHAOS,
            target=target,
            schedule=ExperimentSchedule(duration="2m"),
            fault_config={
                "stressors": {"cpu": {"workers": 2, "load": 80}},
            },
        ),
    )
    
    stress_scenario = GameDayScenario(
        name="Resource Pressure",
        description=f"Test {service_name} under CPU pressure",
        hypothesis=f"{service_name} maintains functionality under resource constraints",
        success_criteria=[
            "Service remains responsive",
            "Autoscaling triggers if configured",
            "No OOM kills",
        ],
        experiments=[stress_exp],
        estimated_duration_minutes=15,
        depends_on=[network_scenario.id],
    )
    
    return GameDay(
        name=f"{service_name.title()} Resilience GameDay",
        description=f"Comprehensive resilience testing for {service_name}",
        objectives=[
            f"Validate {service_name} recovery capabilities",
            "Identify weaknesses in failure handling",
            "Document recovery procedures",
        ],
        scope=f"{service_name} service in {namespace} namespace",
        out_of_scope="Database and external dependencies",
        scenarios=[pod_scenario, network_scenario, stress_scenario],
        max_blast_radius="single-service",
        abort_criteria=[
            "failure_rate > 50%",
            "consecutive_failures > 2",
        ],
        rollback_plan=(
            f"1. Delete all chaos experiments: kubectl delete podchaos,networkchaos -l gameday={service_name}\n"
            f"2. Restart affected pods: kubectl rollout restart deployment/{service_name}\n"
            "3. Verify service health via /health endpoint"
        ),
    )
