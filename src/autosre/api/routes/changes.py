"""
API routes for change management.

Provides REST endpoints for:
- Change tracking
- Impact analysis
- Correlation
- Change windows
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from autosre.changes import ChangeTracker
from autosre.changes.models import (
    Change,
    ChangeType,
    ChangeStatus,
    ChangeRisk,
    ChangeImpact,
    ChangeWindow,
    ChangeWindowType,
)
from autosre.changes.correlation import CorrelationEngine
from autosre.changes.impact import ImpactAnalyzer, ImpactLevel

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/changes", tags=["changes"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RecordChangeRequest(BaseModel):
    """Request to record a change."""
    
    change_type: ChangeType
    resource_type: str
    resource_name: str
    namespace: str | None = None
    cluster: str = "default"
    title: str = ""
    description: str = ""
    reason: str = ""
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    source: str = "api"
    source_id: str | None = None
    source_url: str | None = None
    changed_by: str = "unknown"
    approved_by: str | None = None
    risk: ChangeRisk = ChangeRisk.MEDIUM
    labels: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class UpdateChangeRequest(BaseModel):
    """Request to update a change."""
    
    status: ChangeStatus | None = None
    after_state: dict[str, Any] | None = None
    error: str | None = None


class CorrelateIncidentRequest(BaseModel):
    """Request to correlate an incident to changes."""
    
    incident_id: str
    service: str | None = None
    namespace: str | None = None
    started_at: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class ChangeWindowRequest(BaseModel):
    """Request to create a change window."""
    
    name: str
    type: ChangeWindowType
    start_hour: int | None = None
    end_hour: int | None = None
    days_of_week: list[int] = Field(default_factory=list)
    freeze_start: datetime | None = None
    freeze_end: datetime | None = None


class ChangeResponse(BaseModel):
    """Response with change details."""
    
    id: UUID
    change_type: ChangeType
    resource_type: str
    resource_name: str
    namespace: str | None
    cluster: str
    title: str
    status: ChangeStatus
    risk: ChangeRisk
    source: str
    changed_by: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ChangeDetailResponse(BaseModel):
    """Detailed change response."""
    
    id: UUID
    change_type: ChangeType
    resource_type: str
    resource_name: str
    namespace: str | None
    cluster: str
    title: str
    description: str
    reason: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    status: ChangeStatus
    risk: ChangeRisk
    source: str
    source_id: str | None
    source_url: str | None
    changed_by: str
    approved_by: str | None
    labels: dict[str, str]
    tags: list[str]
    incident_ids: list[str]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    rolled_back_at: datetime | None


class CorrelationResponse(BaseModel):
    """Response with correlation details."""
    
    change_id: UUID
    incident_id: str
    correlation_type: str
    strength: str
    confidence: float
    evidence: list[str]


class ImpactAssessmentResponse(BaseModel):
    """Response with impact assessment."""
    
    change_id: UUID
    level: ImpactLevel
    affected_services: list[str]
    affected_users_estimate: int | None
    downtime_estimate_seconds: int | None
    risk_score: float
    recommendations: list[str]


class ChangeWindowResponse(BaseModel):
    """Response with change window details."""
    
    name: str
    type: ChangeWindowType
    is_change_allowed_now: bool
    next_allowed_at: datetime | None
    message: str


# ============================================================================
# Dependencies
# ============================================================================

_tracker = ChangeTracker()


def get_tracker() -> ChangeTracker:
    """Get change tracker instance."""
    return _tracker


def get_correlation_engine() -> CorrelationEngine:
    """Get correlation engine instance."""
    return CorrelationEngine(_tracker)


def get_impact_analyzer() -> ImpactAnalyzer:
    """Get impact analyzer instance."""
    return ImpactAnalyzer()


# ============================================================================
# Change Tracking Endpoints
# ============================================================================

@router.post("/", response_model=ChangeResponse)
async def record_change(
    request: RecordChangeRequest,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Record a new change."""
    change = await tracker.record_change(
        change_type=request.change_type,
        resource_type=request.resource_type,
        resource_name=request.resource_name,
        namespace=request.namespace,
        cluster=request.cluster,
        title=request.title,
        description=request.description,
        reason=request.reason,
        before_state=request.before_state,
        after_state=request.after_state,
        source=request.source,
        source_id=request.source_id,
        source_url=request.source_url,
        changed_by=request.changed_by,
        approved_by=request.approved_by,
        risk=request.risk,
        labels=request.labels,
        tags=request.tags,
    )
    
    return ChangeResponse(
        id=change.id,
        change_type=change.change_type,
        resource_type=change.resource_type,
        resource_name=change.resource_name,
        namespace=change.namespace,
        cluster=change.cluster,
        title=change.title,
        status=change.status,
        risk=change.risk,
        source=change.source,
        changed_by=change.changed_by,
        created_at=change.created_at,
        started_at=change.started_at,
        completed_at=change.completed_at,
    )


@router.get("/", response_model=list[ChangeResponse])
async def list_changes(
    namespace: str | None = None,
    cluster: str | None = None,
    change_type: ChangeType | None = None,
    status: ChangeStatus | None = None,
    minutes: int = Query(60, ge=1, le=10080),  # Max 1 week
    tracker: ChangeTracker = Depends(get_tracker),
):
    """List recent changes."""
    changes = await tracker.get_recent_changes(
        namespace=namespace,
        cluster=cluster,
        change_type=change_type,
        minutes=minutes,
        status=status,
    )
    
    return [
        ChangeResponse(
            id=c.id,
            change_type=c.change_type,
            resource_type=c.resource_type,
            resource_name=c.resource_name,
            namespace=c.namespace,
            cluster=c.cluster,
            title=c.title,
            status=c.status,
            risk=c.risk,
            source=c.source,
            changed_by=c.changed_by,
            created_at=c.created_at,
            started_at=c.started_at,
            completed_at=c.completed_at,
        )
        for c in changes
    ]


@router.get("/{change_id}", response_model=ChangeDetailResponse)
async def get_change(
    change_id: UUID,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Get change details."""
    change = await tracker.get_change(change_id)
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    return ChangeDetailResponse(
        id=change.id,
        change_type=change.change_type,
        resource_type=change.resource_type,
        resource_name=change.resource_name,
        namespace=change.namespace,
        cluster=change.cluster,
        title=change.title,
        description=change.description,
        reason=change.reason,
        before_state=change.before_state,
        after_state=change.after_state,
        status=change.status,
        risk=change.risk,
        source=change.source,
        source_id=change.source_id,
        source_url=change.source_url,
        changed_by=change.changed_by,
        approved_by=change.approved_by,
        labels=change.labels,
        tags=change.tags,
        incident_ids=change.incident_ids,
        created_at=change.created_at,
        started_at=change.started_at,
        completed_at=change.completed_at,
        rolled_back_at=change.rolled_back_at,
    )


@router.patch("/{change_id}")
async def update_change(
    change_id: UUID,
    request: UpdateChangeRequest,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Update a change status."""
    change = await tracker.get_change(change_id)
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    if request.status:
        if request.status == ChangeStatus.IN_PROGRESS:
            await tracker.start_change(change_id)
        elif request.status == ChangeStatus.COMPLETED:
            await tracker.complete_change(change_id, success=True, after_state=request.after_state)
        elif request.status == ChangeStatus.FAILED:
            await tracker.complete_change(change_id, success=False, after_state=request.after_state)
        elif request.status == ChangeStatus.ROLLED_BACK:
            await tracker.rollback_change(change_id)
    
    return {"message": f"Change {change_id} updated"}


@router.post("/{change_id}/start")
async def start_change(
    change_id: UUID,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Mark a change as started."""
    success = await tracker.start_change(change_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Change not found")
    
    return {"message": f"Change {change_id} started"}


@router.post("/{change_id}/complete")
async def complete_change(
    change_id: UUID,
    success: bool = True,
    after_state: dict[str, Any] | None = None,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Mark a change as completed."""
    result = await tracker.complete_change(change_id, success=success, after_state=after_state)
    
    if not result:
        raise HTTPException(status_code=404, detail="Change not found")
    
    return {"message": f"Change {change_id} completed (success={success})"}


@router.post("/{change_id}/rollback")
async def rollback_change(
    change_id: UUID,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Mark a change as rolled back."""
    result = await tracker.rollback_change(change_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Change not found")
    
    return {"message": f"Change {change_id} rolled back"}


@router.post("/{change_id}/link-incident")
async def link_incident(
    change_id: UUID,
    incident_id: str,
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Link a change to an incident."""
    result = await tracker.link_incident(change_id, incident_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Change not found")
    
    return {"message": f"Change {change_id} linked to incident {incident_id}"}


# ============================================================================
# Resource History Endpoints
# ============================================================================

@router.get("/resource/{resource_type}/{resource_name}")
async def get_resource_changes(
    resource_type: str,
    resource_name: str,
    namespace: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Get change history for a specific resource."""
    changes = await tracker.get_changes_for_resource(
        resource_type=resource_type,
        resource_name=resource_name,
        namespace=namespace,
        limit=limit,
    )
    
    return [
        {
            "id": str(c.id),
            "change_type": c.change_type.value,
            "title": c.title,
            "status": c.status.value,
            "risk": c.risk.value,
            "changed_by": c.changed_by,
            "created_at": c.created_at.isoformat(),
        }
        for c in changes
    ]


# ============================================================================
# Correlation Endpoints
# ============================================================================

@router.post("/correlate", response_model=list[CorrelationResponse])
async def correlate_incident(
    request: CorrelateIncidentRequest,
    engine: CorrelationEngine = Depends(get_correlation_engine),
):
    """Find changes correlated with an incident."""
    incident_data = {
        "id": request.incident_id,
        "service": request.service,
        "namespace": request.namespace,
        "started_at": request.started_at,
        "labels": request.labels,
    }
    
    correlations = await engine.correlate_incident(incident_data)
    
    return [
        CorrelationResponse(
            change_id=c.change_id,
            incident_id=c.incident_id,
            correlation_type=c.correlation_type.value if hasattr(c.correlation_type, 'value') else str(c.correlation_type),
            strength=c.strength.value if hasattr(c.strength, 'value') else str(c.strength),
            confidence=c.confidence,
            evidence=c.evidence,
        )
        for c in correlations
    ]


@router.get("/suspicious")
async def find_suspicious_changes(
    incident_time: datetime,
    namespace: str | None = None,
    service: str | None = None,
    lookback_minutes: int = Query(60, ge=1, le=1440),
    engine: CorrelationEngine = Depends(get_correlation_engine),
):
    """Find changes that might have caused an incident."""
    changes = await engine.find_suspicious_changes(
        incident_time=incident_time,
        namespace=namespace,
        lookback_minutes=lookback_minutes,
    )
    
    return [
        {
            "change_id": str(c.id),
            "title": c.title,
            "change_type": c.change_type.value,
            "risk": c.risk.value,
            "changed_by": c.changed_by,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "time_before_incident_minutes": (
                (incident_time - (c.started_at or c.created_at)).total_seconds() / 60
                if c.started_at or c.created_at else None
            ),
        }
        for c in changes
    ]


# ============================================================================
# Impact Analysis Endpoints
# ============================================================================

@router.get("/{change_id}/impact", response_model=ImpactAssessmentResponse)
async def analyze_change_impact(
    change_id: UUID,
    tracker: ChangeTracker = Depends(get_tracker),
    analyzer: ImpactAnalyzer = Depends(get_impact_analyzer),
):
    """Analyze the impact of a change."""
    change = await tracker.get_change(change_id)
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    assessment = await analyzer.analyze(change)
    recommendations = analyzer.get_recommendations(assessment)
    
    return ImpactAssessmentResponse(
        change_id=change_id,
        level=assessment.level,
        affected_services=assessment.affected_services,
        affected_users_estimate=assessment.affected_users_estimate,
        downtime_estimate_seconds=assessment.downtime_estimate_seconds,
        risk_score=assessment.risk_score if hasattr(assessment, 'risk_score') else 0,
        recommendations=recommendations,
    )


# ============================================================================
# Change Window Endpoints
# ============================================================================

_change_windows: list[ChangeWindow] = []


@router.post("/windows", response_model=ChangeWindowResponse)
async def create_change_window(request: ChangeWindowRequest):
    """Create a change window."""
    window = ChangeWindow(
        name=request.name,
        type=request.type,
        start_hour=request.start_hour,
        end_hour=request.end_hour,
        days_of_week=request.days_of_week,
        freeze_start=request.freeze_start,
        freeze_end=request.freeze_end,
    )
    
    _change_windows.append(window)
    
    now = datetime.utcnow()
    is_allowed = window.is_change_allowed(now)
    
    return ChangeWindowResponse(
        name=window.name,
        type=window.type,
        is_change_allowed_now=is_allowed,
        next_allowed_at=None,  # Would need to calculate
        message="Change window created",
    )


@router.get("/windows")
async def list_change_windows():
    """List all change windows."""
    now = datetime.utcnow()
    
    return [
        {
            "name": w.name,
            "type": w.type.value,
            "is_change_allowed_now": w.is_change_allowed(now),
        }
        for w in _change_windows
    ]


@router.get("/windows/check")
async def check_change_window(
    risk: ChangeRisk = ChangeRisk.MEDIUM,
    emergency: bool = False,
):
    """Check if changes are currently allowed."""
    now = datetime.utcnow()
    
    # Check all windows
    for window in _change_windows:
        if not window.is_change_allowed(now, risk=risk, emergency=emergency):
            return {
                "allowed": False,
                "reason": f"Blocked by window: {window.name}",
                "window_name": window.name,
            }
    
    return {
        "allowed": True,
        "reason": "No blocking windows",
    }


# ============================================================================
# Stats Endpoints
# ============================================================================

@router.get("/stats")
async def get_change_stats(
    tracker: ChangeTracker = Depends(get_tracker),
):
    """Get change tracking statistics."""
    stats = tracker.get_stats()
    
    # Add recent activity
    now = datetime.utcnow()
    
    last_hour = await tracker.get_recent_changes(minutes=60)
    last_day = await tracker.get_recent_changes(minutes=1440)
    
    active = await tracker.get_active_changes()
    failed = await tracker.get_failed_changes(hours=24)
    
    return {
        **stats,
        "changes_last_hour": len(last_hour),
        "changes_last_day": len(last_day),
        "active_changes": len(active),
        "failed_changes_24h": len(failed),
    }
