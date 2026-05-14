"""
API routes for chaos engineering operations.

Provides REST endpoints for:
- Chaos experiments
- Fault injection
- Game day management
- Resilience scoring
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from autosre.chaos.models import (
    Experiment,
    ExperimentStatus,
    Fault,
    FaultType,
    Target,
    TargetType,
    SteadyStateHypothesis,
)
from autosre.chaos.experiment import ExperimentRunner
from autosre.chaos.faults import FaultInjector
from autosre.chaos.gameday import GameDayPlanner, GameDayStatus
from autosre.chaos.resilience import ResilienceScorer

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chaos", tags=["chaos"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TargetRequest(BaseModel):
    """Target for fault injection."""
    
    type: TargetType
    name: str
    namespace: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class FaultRequest(BaseModel):
    """Request to create a fault."""
    
    type: FaultType
    target: TargetRequest
    parameters: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: int = 60


class SteadyStateRequest(BaseModel):
    """Steady state hypothesis."""
    
    name: str
    probe_type: str = "http"
    endpoint: str | None = None
    query: str | None = None
    expected_status: int | None = None
    threshold: float | None = None
    timeout_seconds: int = 5


class CreateExperimentRequest(BaseModel):
    """Request to create a chaos experiment."""
    
    name: str = Field(..., description="Experiment name")
    description: str = Field("", description="Description")
    faults: list[FaultRequest] = Field(..., description="Faults to inject")
    steady_state: list[SteadyStateRequest] = Field(default_factory=list)
    duration_seconds: int = Field(300, description="Experiment duration")
    warmup_seconds: int = Field(30, description="Warmup period")
    cooldown_seconds: int = Field(30, description="Cooldown period")
    auto_rollback: bool = Field(True, description="Auto-rollback on failure")
    tags: list[str] = Field(default_factory=list)


class RunExperimentRequest(BaseModel):
    """Request to run an experiment."""
    
    dry_run: bool = Field(False, description="Dry run mode")


class ExperimentResponse(BaseModel):
    """Response with experiment details."""
    
    id: UUID
    name: str
    description: str
    status: ExperimentStatus
    fault_count: int
    duration_seconds: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ExperimentResultResponse(BaseModel):
    """Response with experiment result."""
    
    experiment_id: UUID
    success: bool
    status: ExperimentStatus
    message: str
    steady_state_met_before: bool
    steady_state_met_during: bool
    steady_state_met_after: bool
    duration_seconds: float
    was_rolled_back: bool
    errors: list[str]


class GameDayRequest(BaseModel):
    """Request to create a game day."""
    
    name: str
    description: str = ""
    scheduled_at: datetime
    scenarios: list[CreateExperimentRequest] = Field(default_factory=list)


class GameDayResponse(BaseModel):
    """Response with game day details."""
    
    id: UUID
    name: str
    description: str
    status: GameDayStatus
    scenario_count: int
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ResilienceScoreResponse(BaseModel):
    """Response with resilience score."""
    
    service_name: str
    overall_score: float
    availability_score: float | None = None
    recovery_score: float | None = None
    fault_tolerance_score: float | None = None
    recommendations: list[str] = Field(default_factory=list)


# ============================================================================
# Dependencies
# ============================================================================

def get_experiment_runner() -> ExperimentRunner:
    """Get experiment runner instance."""
    # In production, use dependency injection with proper K8s client
    return ExperimentRunner(k8s_client=None)


def get_fault_injector() -> FaultInjector:
    """Get fault injector instance."""
    return FaultInjector(k8s_client=None)


def get_game_day_planner() -> GameDayPlanner:
    """Get game day planner instance."""
    return GameDayPlanner(k8s_client=None)


def get_resilience_scorer() -> ResilienceScorer:
    """Get resilience scorer instance."""
    return ResilienceScorer()


# ============================================================================
# Experiment Endpoints
# ============================================================================

@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    request: CreateExperimentRequest,
):
    """Create a new chaos experiment."""
    faults = []
    for fault_req in request.faults:
        target = Target(
            type=fault_req.target.type,
            name=fault_req.target.name,
            namespace=fault_req.target.namespace,
            labels=fault_req.target.labels,
        )
        fault = Fault(
            type=fault_req.type,
            target=target,
            parameters=fault_req.parameters,
        )
        faults.append(fault)
    
    steady_state = []
    for ss_req in request.steady_state:
        ss = SteadyStateHypothesis(
            name=ss_req.name,
            probe_type=ss_req.probe_type,
            endpoint=ss_req.endpoint,
            query=ss_req.query,
            expected_status=ss_req.expected_status,
            threshold=ss_req.threshold,
            timeout_seconds=ss_req.timeout_seconds,
        )
        steady_state.append(ss)
    
    experiment = Experiment(
        name=request.name,
        description=request.description,
        faults=faults,
        steady_state=steady_state,
        duration_seconds=request.duration_seconds,
        warmup_seconds=request.warmup_seconds,
        cooldown_seconds=request.cooldown_seconds,
        auto_rollback=request.auto_rollback,
        tags=request.tags,
    )
    
    return ExperimentResponse(
        id=experiment.id,
        name=experiment.name,
        description=experiment.description,
        status=experiment.status,
        fault_count=len(experiment.faults),
        duration_seconds=experiment.duration_seconds,
        created_at=experiment.created_at,
        started_at=experiment.started_at,
        completed_at=experiment.completed_at,
    )


@router.post("/experiments/{experiment_id}/run", response_model=ExperimentResultResponse)
async def run_experiment(
    experiment_id: UUID,
    request: RunExperimentRequest = RunExperimentRequest(),
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """Run a chaos experiment."""
    # Would need experiment storage in production
    raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(
    experiment_id: UUID,
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """Pause a running experiment."""
    paused = await runner.pause(experiment_id)
    
    if not paused:
        raise HTTPException(status_code=404, detail="Experiment not found or not running")
    
    return {"message": f"Experiment {experiment_id} paused"}


@router.post("/experiments/{experiment_id}/resume")
async def resume_experiment(
    experiment_id: UUID,
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """Resume a paused experiment."""
    resumed = await runner.resume(experiment_id)
    
    if not resumed:
        raise HTTPException(status_code=400, detail="Could not resume experiment")
    
    return {"message": f"Experiment {experiment_id} resumed"}


@router.post("/experiments/{experiment_id}/cancel")
async def cancel_experiment(
    experiment_id: UUID,
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """Cancel a running experiment."""
    cancelled = await runner.cancel(experiment_id)
    
    if not cancelled:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return {"message": f"Experiment {experiment_id} cancelled"}


@router.get("/experiments/active")
async def list_active_experiments(
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """List all active experiments."""
    active = runner.get_active_experiments()
    
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "status": e.status.value,
            "started_at": e.started_at.isoformat() if e.started_at else None,
        }
        for e in active
    ]


@router.get("/experiments/history")
async def get_experiment_history(
    limit: int = Query(100, ge=1, le=1000),
    runner: ExperimentRunner = Depends(get_experiment_runner),
):
    """Get experiment history."""
    history = runner.get_experiment_history(limit=limit)
    
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "status": e.status.value,
            "success": e.result.success if e.result else None,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        }
        for e in history
    ]


# ============================================================================
# Fault Injection Endpoints
# ============================================================================

@router.post("/faults/inject")
async def inject_fault(
    request: FaultRequest,
    dry_run: bool = Query(False),
    injector: FaultInjector = Depends(get_fault_injector),
):
    """Inject a fault."""
    target = Target(
        type=request.target.type,
        name=request.target.name,
        namespace=request.target.namespace,
        labels=request.target.labels,
    )
    
    fault = Fault(
        type=request.type,
        target=target,
        parameters=request.parameters,
    )
    
    result = await injector.inject(
        fault,
        duration=request.duration_seconds,
        dry_run=dry_run,
    )
    
    return {
        "fault_id": str(fault.id),
        "type": fault.type.value,
        "success": result.success,
        "message": result.message if hasattr(result, 'message') else "",
        "dry_run": dry_run,
    }


@router.post("/faults/{fault_id}/stop")
async def stop_fault(
    fault_id: UUID,
    injector: FaultInjector = Depends(get_fault_injector),
):
    """Stop an active fault."""
    stopped = await injector.stop(fault_id)
    
    if not stopped:
        raise HTTPException(status_code=404, detail="Fault not found")
    
    return {"message": f"Fault {fault_id} stopped"}


@router.post("/faults/{fault_id}/rollback")
async def rollback_fault(
    fault_id: UUID,
    injector: FaultInjector = Depends(get_fault_injector),
):
    """Rollback a fault's effects."""
    rolled_back = await injector.rollback(fault_id)
    
    if not rolled_back:
        raise HTTPException(status_code=400, detail="Could not rollback fault")
    
    return {"message": f"Fault {fault_id} rolled back"}


@router.get("/faults/active")
async def list_active_faults(
    injector: FaultInjector = Depends(get_fault_injector),
):
    """List all active faults."""
    active = injector.get_active_faults()
    
    return [
        {
            "id": str(f.id),
            "type": f.type.value,
            "target": f.target.name,
            "status": f.status.value,
        }
        for f in active
    ]


# ============================================================================
# Game Day Endpoints
# ============================================================================

@router.post("/gamedays", response_model=GameDayResponse)
async def create_game_day(
    request: GameDayRequest,
    planner: GameDayPlanner = Depends(get_game_day_planner),
):
    """Create a new game day."""
    game_day = planner.create_game_day(
        name=request.name,
        description=request.description,
        scheduled_at=request.scheduled_at,
    )
    
    # Add scenarios
    for scenario_req in request.scenarios:
        faults = []
        for fault_req in scenario_req.faults:
            target = Target(
                type=fault_req.target.type,
                name=fault_req.target.name,
                namespace=fault_req.target.namespace,
            )
            faults.append(Fault(type=fault_req.type, target=target))
        
        from autosre.chaos.gameday import Scenario
        scenario = Scenario(
            name=scenario_req.name,
            experiment=Experiment(
                name=scenario_req.name,
                faults=faults,
                duration_seconds=scenario_req.duration_seconds,
            ),
        )
        planner.add_scenario(game_day.id, scenario)
    
    return GameDayResponse(
        id=game_day.id,
        name=game_day.name,
        description=game_day.description,
        status=game_day.status,
        scenario_count=len(game_day.scenarios),
        scheduled_at=game_day.scheduled_at,
        started_at=game_day.started_at,
        completed_at=game_day.completed_at,
    )


@router.post("/gamedays/{game_day_id}/run")
async def run_game_day(
    game_day_id: UUID,
    dry_run: bool = Query(False),
    planner: GameDayPlanner = Depends(get_game_day_planner),
):
    """Run a game day."""
    result = await planner.run(game_day_id, dry_run=dry_run)
    
    if not result:
        raise HTTPException(status_code=404, detail="Game day not found")
    
    return {
        "game_day_id": str(game_day_id),
        "success": result.success if hasattr(result, 'success') else True,
        "dry_run": dry_run,
    }


@router.post("/gamedays/{game_day_id}/cancel")
async def cancel_game_day(
    game_day_id: UUID,
    reason: str = Query("Cancelled via API"),
    planner: GameDayPlanner = Depends(get_game_day_planner),
):
    """Cancel a game day."""
    cancelled = planner.cancel(game_day_id, reason=reason)
    
    if not cancelled:
        raise HTTPException(status_code=404, detail="Game day not found")
    
    return {"message": f"Game day {game_day_id} cancelled"}


@router.get("/gamedays/upcoming")
async def list_upcoming_game_days(
    days: int = Query(30, ge=1, le=365),
    planner: GameDayPlanner = Depends(get_game_day_planner),
):
    """List upcoming game days."""
    upcoming = planner.get_upcoming(days=days)
    
    return [
        {
            "id": str(gd.id),
            "name": gd.name,
            "status": gd.status.value,
            "scheduled_at": gd.scheduled_at.isoformat(),
            "scenario_count": len(gd.scenarios),
        }
        for gd in upcoming
    ]


# ============================================================================
# Resilience Endpoints
# ============================================================================

@router.get("/resilience/{service_name}", response_model=ResilienceScoreResponse)
async def get_resilience_score(
    service_name: str,
    scorer: ResilienceScorer = Depends(get_resilience_scorer),
):
    """Get resilience score for a service."""
    # In production, would calculate from historical experiment data
    from autosre.chaos.resilience import ResilienceScore
    
    # Mock score for demonstration
    score = ResilienceScore(
        service_name=service_name,
        overall_score=75.0,
        availability_score=80.0,
        recovery_score=70.0,
        fault_tolerance_score=75.0,
    )
    
    recommendations = scorer.get_recommendations(score)
    
    return ResilienceScoreResponse(
        service_name=service_name,
        overall_score=score.overall_score,
        availability_score=score.availability_score,
        recovery_score=score.recovery_score,
        fault_tolerance_score=score.fault_tolerance_score,
        recommendations=recommendations,
    )


@router.get("/resilience")
async def list_resilience_scores(
    namespace: str | None = None,
    scorer: ResilienceScorer = Depends(get_resilience_scorer),
):
    """List resilience scores for all services."""
    # In production, would aggregate from historical data
    return {
        "scores": [],
        "average_score": 0,
        "services_assessed": 0,
    }


@router.get("/resilience/trends")
async def get_resilience_trends(
    service_name: str | None = None,
    days: int = Query(30, ge=1, le=365),
):
    """Get resilience score trends."""
    return {
        "service_name": service_name,
        "days": days,
        "trend": "improving",
        "data_points": [],
    }
