"""
API routes for remediation operations.

Provides REST endpoints for:
- Remediation actions
- Plans
- Approvals
- Rollback
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from autosre.remediation import (
    RemediationEngine,
    EngineConfig,
    ActionRegistry,
    SafetyChecker,
    RollbackManager,
    ApprovalWorkflow,
    get_registry,
)
from autosre.remediation.models import (
    RemediationAction,
    RemediationPlan,
    RemediationResult,
    RemediationStatus,
    RiskLevel,
    ApprovalStatus,
)
from autosre.remediation.approval import NotificationChannel

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateActionRequest(BaseModel):
    """Request to create a remediation action."""
    
    definition_name: str = Field(..., description="Name of action definition")
    target_type: str = Field(..., description="Target resource type")
    target_name: str = Field(..., description="Target resource name")
    target_namespace: str | None = Field(None, description="Kubernetes namespace")
    target_cluster: str | None = Field(None, description="Cluster name")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    dry_run: bool = Field(False, description="Dry run mode")
    triggered_by: str = Field("api", description="Who triggered the action")
    investigation_id: UUID | None = None
    incident_id: str | None = None


class ExecuteActionRequest(BaseModel):
    """Request to execute a remediation action."""
    
    skip_safety_checks: bool = Field(False, description="Skip safety checks (dangerous)")
    skip_approval: bool = Field(False, description="Skip approval workflow")
    auto_rollback: bool = Field(True, description="Auto-rollback on failure")
    wait_for_approval: bool = Field(True, description="Wait for approval if required")
    approval_timeout_seconds: float | None = Field(None, description="Approval wait timeout")


class CreatePlanRequest(BaseModel):
    """Request to create a remediation plan."""
    
    name: str = Field(..., description="Plan name")
    description: str = Field(..., description="Plan description")
    actions: list[CreateActionRequest] = Field(..., description="Actions in the plan")
    parallel: bool = Field(False, description="Execute actions in parallel")
    stop_on_failure: bool = Field(True, description="Stop on first failure")
    incident_id: str | None = None


class ApprovalDecisionRequest(BaseModel):
    """Request for approval decision."""
    
    decision: str = Field(..., pattern="^(approve|reject)$")
    reason: str | None = None
    decided_by: str = Field(..., description="Who made the decision")


class ActionResponse(BaseModel):
    """Response with action details."""
    
    id: UUID
    definition_name: str
    target_type: str
    target_name: str
    target_namespace: str | None
    status: RemediationStatus
    dry_run: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    message: str = ""
    error: str | None = None
    
    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    """Response with plan details."""
    
    id: UUID
    name: str
    description: str
    status: RemediationStatus
    action_count: int
    completed_actions: int
    failed_actions: int
    progress_percent: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ApprovalResponse(BaseModel):
    """Response with approval request details."""
    
    id: UUID
    action_id: UUID
    action_name: str
    status: ApprovalStatus
    reason: str
    requested_by: str
    requested_at: datetime
    expires_at: datetime
    approved_by: str | None = None
    rejection_reason: str | None = None


class RegistryCatalogResponse(BaseModel):
    """Response with action catalog."""
    
    actions: list[dict[str, Any]]
    total: int


class StatsResponse(BaseModel):
    """Response with engine statistics."""
    
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    rolled_back: int
    active_executions: int


# ============================================================================
# Dependencies
# ============================================================================

def get_engine() -> RemediationEngine:
    """Get remediation engine instance."""
    # In production, this would use dependency injection
    return RemediationEngine()


def get_approval_workflow() -> ApprovalWorkflow:
    """Get approval workflow instance."""
    return ApprovalWorkflow()


# ============================================================================
# Action Endpoints
# ============================================================================

@router.post("/actions", response_model=ActionResponse)
async def create_action(
    request: CreateActionRequest,
    engine: RemediationEngine = Depends(get_engine),
):
    """Create a new remediation action."""
    try:
        action = engine.create_action(
            definition_name=request.definition_name,
            target_type=request.target_type,
            target_name=request.target_name,
            target_namespace=request.target_namespace,
            target_cluster=request.target_cluster,
            parameters=request.parameters,
            dry_run=request.dry_run,
            triggered_by=request.triggered_by,
            investigation_id=request.investigation_id,
            incident_id=request.incident_id,
        )
        
        return ActionResponse(
            id=action.id,
            definition_name=action.definition_name,
            target_type=action.target_type,
            target_name=action.target_name,
            target_namespace=action.target_namespace,
            status=action.status,
            dry_run=action.dry_run,
            created_at=action.created_at,
            started_at=action.started_at,
            completed_at=action.completed_at,
        )
        
    except Exception as e:
        logger.error(f"Failed to create action: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/actions/{action_id}/execute", response_model=dict)
async def execute_action(
    action_id: UUID,
    request: ExecuteActionRequest,
    background_tasks: BackgroundTasks,
    engine: RemediationEngine = Depends(get_engine),
):
    """Execute a remediation action."""
    # Get action from engine (would need action storage in production)
    # For now, return immediate response
    
    return {
        "message": f"Action {action_id} submitted for execution",
        "skip_safety_checks": request.skip_safety_checks,
        "skip_approval": request.skip_approval,
    }


@router.post("/execute", response_model=dict)
async def create_and_execute_action(
    action_request: CreateActionRequest,
    execute_request: ExecuteActionRequest = ExecuteActionRequest(),
    background_tasks: BackgroundTasks = None,
    engine: RemediationEngine = Depends(get_engine),
):
    """Create and execute a remediation action in one call."""
    try:
        action = engine.create_action(
            definition_name=action_request.definition_name,
            target_type=action_request.target_type,
            target_name=action_request.target_name,
            target_namespace=action_request.target_namespace,
            target_cluster=action_request.target_cluster,
            parameters=action_request.parameters,
            dry_run=action_request.dry_run,
            triggered_by=action_request.triggered_by,
            investigation_id=action_request.investigation_id,
            incident_id=action_request.incident_id,
        )
        
        result = await engine.execute(
            action,
            skip_safety_checks=execute_request.skip_safety_checks,
            skip_approval=execute_request.skip_approval,
            auto_rollback=execute_request.auto_rollback,
            wait_for_approval=execute_request.wait_for_approval,
            approval_timeout_seconds=execute_request.approval_timeout_seconds,
        )
        
        return {
            "action_id": str(action.id),
            "success": result.success,
            "status": result.status.value,
            "message": result.message,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "was_rolled_back": result.was_rolled_back,
        }
        
    except Exception as e:
        logger.error(f"Failed to execute action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: UUID,
    engine: RemediationEngine = Depends(get_engine),
):
    """Get action details."""
    # Would need action storage in production
    raise HTTPException(status_code=404, detail="Action not found")


@router.post("/actions/{action_id}/cancel")
async def cancel_action(
    action_id: UUID,
    engine: RemediationEngine = Depends(get_engine),
):
    """Cancel a pending or executing action."""
    cancelled = await engine.cancel(action_id)
    
    if not cancelled:
        raise HTTPException(status_code=404, detail="Action not found or not cancellable")
    
    return {"message": f"Action {action_id} cancelled"}


@router.post("/actions/{action_id}/rollback")
async def rollback_action(
    action_id: UUID,
    engine: RemediationEngine = Depends(get_engine),
):
    """Manually rollback an action."""
    result = await engine.rollback_action(action_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Action not found or not rollbackable")
    
    return {
        "success": result.success,
        "message": result.message,
        "steps_completed": result.steps_completed,
    }


# ============================================================================
# Plan Endpoints
# ============================================================================

@router.post("/plans", response_model=PlanResponse)
async def create_plan(
    request: CreatePlanRequest,
    engine: RemediationEngine = Depends(get_engine),
):
    """Create a remediation plan."""
    actions = []
    
    for action_req in request.actions:
        action = engine.create_action(
            definition_name=action_req.definition_name,
            target_type=action_req.target_type,
            target_name=action_req.target_name,
            target_namespace=action_req.target_namespace,
            target_cluster=action_req.target_cluster,
            parameters=action_req.parameters,
            dry_run=action_req.dry_run,
            triggered_by=action_req.triggered_by,
        )
        actions.append(action)
    
    plan = RemediationPlan(
        name=request.name,
        description=request.description,
        actions=actions,
        parallel=request.parallel,
        stop_on_failure=request.stop_on_failure,
        incident_id=request.incident_id,
    )
    
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        status=plan.status,
        action_count=len(plan.actions),
        completed_actions=plan.completed_actions,
        failed_actions=plan.failed_actions,
        progress_percent=plan.progress_percent,
        created_at=plan.created_at,
        started_at=plan.started_at,
        completed_at=plan.completed_at,
    )


@router.post("/plans/{plan_id}/execute")
async def execute_plan(
    plan_id: UUID,
    skip_safety_checks: bool = False,
    skip_approval: bool = False,
    engine: RemediationEngine = Depends(get_engine),
):
    """Execute a remediation plan."""
    # Would need plan storage in production
    raise HTTPException(status_code=404, detail="Plan not found")


# ============================================================================
# Approval Endpoints
# ============================================================================

@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    workflow: ApprovalWorkflow = Depends(get_approval_workflow),
):
    """List all pending approval requests."""
    pending = await workflow.get_pending_requests()
    
    return [
        ApprovalResponse(
            id=req.id,
            action_id=req.action_id,
            action_name=req.action_name,
            status=req.status,
            reason=req.reason,
            requested_by=req.requested_by,
            requested_at=req.requested_at,
            expires_at=req.expires_at,
            approved_by=req.approved_by,
            rejection_reason=req.rejection_reason,
        )
        for req in pending
    ]


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    workflow: ApprovalWorkflow = Depends(get_approval_workflow),
):
    """Get approval request details."""
    request = await workflow.get_request(approval_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    return ApprovalResponse(
        id=request.id,
        action_id=request.action_id,
        action_name=request.action_name,
        status=request.status,
        reason=request.reason,
        requested_by=request.requested_by,
        requested_at=request.requested_at,
        expires_at=request.expires_at,
        approved_by=request.approved_by,
        rejection_reason=request.rejection_reason,
    )


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: UUID,
    request: ApprovalDecisionRequest,
    workflow: ApprovalWorkflow = Depends(get_approval_workflow),
):
    """Make an approval decision."""
    if request.decision == "approve":
        success = await workflow.approve(
            approval_id,
            approved_by=request.decided_by,
            reason=request.reason,
        )
    else:
        if not request.reason:
            raise HTTPException(status_code=400, detail="Reason required for rejection")
        
        success = await workflow.reject(
            approval_id,
            rejected_by=request.decided_by,
            reason=request.reason,
        )
    
    if not success:
        raise HTTPException(status_code=400, detail="Could not process decision")
    
    return {
        "message": f"Approval {request.decision}d",
        "approval_id": str(approval_id),
    }


# ============================================================================
# Registry Endpoints
# ============================================================================

@router.get("/registry/actions", response_model=RegistryCatalogResponse)
async def list_registered_actions(
    action_type: str | None = None,
    tag: str | None = None,
    target_type: str | None = None,
):
    """List all registered action definitions."""
    registry = get_registry()
    
    if action_type:
        from autosre.remediation.models import ActionType
        try:
            at = ActionType(action_type)
            actions = registry.find_by_type(at)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action type: {action_type}")
    elif tag:
        actions = registry.find_by_tag(tag)
    elif target_type:
        actions = registry.find_by_target_type(target_type)
    else:
        actions = list(registry.actions.values())
    
    catalog = [
        {
            "name": a.definition.name,
            "display_name": a.definition.display_name,
            "description": a.definition.description,
            "type": a.definition.action_type.value,
            "risk_level": a.definition.risk_level.value,
            "is_destructive": a.definition.is_destructive,
            "requires_approval": a.definition.requires_approval,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "description": p.description,
                }
                for p in a.definition.parameters
            ],
            "target_types": a.definition.target_types,
            "tags": a.definition.tags,
        }
        for a in actions
    ]
    
    return RegistryCatalogResponse(actions=catalog, total=len(catalog))


@router.get("/registry/actions/{name}")
async def get_registered_action(name: str):
    """Get details of a registered action."""
    registry = get_registry()
    
    if not registry.has_action(name):
        raise HTTPException(status_code=404, detail=f"Action not found: {name}")
    
    action = registry.get(name)
    
    return {
        "name": action.definition.name,
        "display_name": action.definition.display_name,
        "description": action.definition.description,
        "type": action.definition.action_type.value,
        "risk_level": action.definition.risk_level.value,
        "is_destructive": action.definition.is_destructive,
        "is_reversible": action.definition.is_reversible,
        "requires_approval": action.definition.requires_approval,
        "parameters": [p.model_dump() for p in action.definition.parameters],
        "target_types": action.definition.target_types,
        "tags": action.definition.tags,
        "timeout_seconds": action.definition.timeout_seconds,
        "cooldown_seconds": action.definition.cooldown_seconds,
        "stats": {
            "execution_count": action.execution_count,
            "success_rate": action.success_rate,
            "average_duration": action.average_duration_seconds,
        },
    }


# ============================================================================
# Stats Endpoints
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    engine: RemediationEngine = Depends(get_engine),
):
    """Get remediation engine statistics."""
    stats = engine.get_stats()
    
    return StatsResponse(
        total_executions=stats["total_executions"],
        successful=stats["successful"],
        failed=stats["failed"],
        success_rate=stats["success_rate"],
        rolled_back=stats["rolled_back"],
        active_executions=stats["active_executions"],
    )


@router.get("/history")
async def get_execution_history(
    limit: int = Query(100, ge=1, le=1000),
    success_only: bool = False,
    failed_only: bool = False,
    engine: RemediationEngine = Depends(get_engine),
):
    """Get execution history."""
    history = engine.get_execution_history(
        limit=limit,
        success_only=success_only,
        failed_only=failed_only,
    )
    
    return [
        {
            "action_id": str(r.action_id),
            "success": r.success,
            "status": r.status.value,
            "message": r.message,
            "duration_seconds": r.duration_seconds,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "was_rolled_back": r.was_rolled_back,
        }
        for r in history
    ]
