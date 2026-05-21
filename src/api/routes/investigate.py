"""Investigation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import structlog

from ..auth import User, require_auth
from ..auth.jwt import require_scope
from ..models.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationStatus,
    InvestigationFeedback,
    InvestigationState,
)
from ..models.common import ErrorResponse, PaginatedResponse
from ..services import InvestigationService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/investigate", tags=["Investigations"])

# Service instance (in production: use dependency injection)
_service = InvestigationService()


@router.post(
    "",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Investigation",
    description="Create a new investigation from an alert",
    responses={
        201: {"description": "Investigation created successfully"},
        400: {"description": "Invalid alert data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def start_investigation(
    request: InvestigationCreate,
    user: Annotated[User, Depends(require_scope("investigations:write"))],
) -> InvestigationResponse:
    """
    Start a new investigation based on an incoming alert.
    
    The investigation will be queued and processed by the AutoSRE agent system.
    Use the SSE stream endpoint to receive real-time updates.
    
    **Required scope:** `investigations:write`
    """
    logger.info(
        "investigation_requested",
        user=user.user_id,
        service=request.alert.service,
        severity=request.alert.severity,
    )

    investigation = await _service.create_investigation(request)
    return investigation


@router.get(
    "",
    response_model=PaginatedResponse[InvestigationResponse],
    summary="List Investigations",
    description="List investigations with optional filters",
)
async def list_investigations(
    user: Annotated[User, Depends(require_scope("investigations:read"))],
    state: InvestigationState | None = Query(None, description="Filter by state"),
    service: str | None = Query(None, description="Filter by service"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[InvestigationResponse]:
    """
    List investigations with optional filters.
    
    **Required scope:** `investigations:read`
    """
    offset = (page - 1) * page_size
    items, total = await _service.list_investigations(
        state=state,
        service=service,
        limit=page_size,
        offset=offset,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Get Investigation",
    description="Get full details of an investigation",
    responses={
        200: {"description": "Investigation details"},
        404: {"description": "Investigation not found", "model": ErrorResponse},
    },
)
async def get_investigation(
    investigation_id: str,
    user: Annotated[User, Depends(require_scope("investigations:read"))],
) -> InvestigationResponse:
    """
    Get detailed information about a specific investigation.
    
    **Required scope:** `investigations:read`
    """
    investigation = await _service.get_investigation(investigation_id)
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} not found",
        )
    return investigation


@router.get(
    "/{investigation_id}/status",
    response_model=InvestigationStatus,
    summary="Get Investigation Status",
    description="Get lightweight status of an investigation",
    responses={
        200: {"description": "Investigation status"},
        404: {"description": "Investigation not found"},
    },
)
async def get_investigation_status(
    investigation_id: str,
    user: Annotated[User, Depends(require_scope("investigations:read"))],
) -> InvestigationStatus:
    """
    Get lightweight status information for polling.
    
    Use this for quick status checks. For detailed information,
    use the full GET endpoint or the SSE stream.
    
    **Required scope:** `investigations:read`
    """
    status_info = await _service.get_status(investigation_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} not found",
        )
    return status_info


@router.get(
    "/{investigation_id}/stream",
    summary="Stream Investigation Events",
    description="Server-Sent Events stream for real-time investigation updates",
    responses={
        200: {
            "description": "SSE event stream",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Investigation not found"},
    },
)
async def stream_investigation(
    investigation_id: str,
    user: Annotated[User, Depends(require_scope("investigations:read"))],
) -> EventSourceResponse:
    """
    Stream real-time investigation updates via Server-Sent Events (SSE).
    
    Event types:
    - `state_change`: Investigation state changed
    - `step_start`: New investigation step started
    - `step_complete`: Investigation step completed
    - `finding`: New finding discovered
    - `hypothesis`: New hypothesis formed
    - `error`: Error occurred
    - `complete`: Investigation completed
    
    **Required scope:** `investigations:read`
    
    Example client (JavaScript):
    ```javascript
    const es = new EventSource('/api/v1/investigate/{id}/stream');
    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Event:', data);
    };
    ```
    """
    investigation = await _service.get_investigation(investigation_id)
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} not found",
        )

    async def event_generator():
        async for event in _service.stream_events(investigation_id):
            yield {
                "event": event.event_type.value,
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())


@router.post(
    "/{investigation_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit Feedback",
    description="Submit human feedback on investigation results",
    responses={
        204: {"description": "Feedback accepted"},
        400: {"description": "Investigation not in valid state for feedback"},
        404: {"description": "Investigation not found"},
    },
)
async def submit_feedback(
    investigation_id: str,
    feedback: InvestigationFeedback,
    user: Annotated[User, Depends(require_scope("investigations:write"))],
) -> None:
    """
    Submit human feedback on a completed investigation.
    
    Feedback is used to improve future investigations through
    reinforcement learning and strategy refinement.
    
    **Required scope:** `investigations:write`
    """
    success = await _service.submit_feedback(investigation_id, feedback)
    if not success:
        # Could be not found or invalid state
        investigation = await _service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Investigation is not in a completed state",
        )


@router.delete(
    "/{investigation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Investigation",
    description="Cancel a running investigation",
    responses={
        204: {"description": "Investigation cancelled"},
        400: {"description": "Investigation cannot be cancelled"},
        404: {"description": "Investigation not found"},
    },
)
async def cancel_investigation(
    investigation_id: str,
    user: Annotated[User, Depends(require_scope("investigations:write"))],
) -> None:
    """
    Cancel an in-progress investigation.
    
    Only investigations in PENDING, RUNNING, or PAUSED states can be cancelled.
    
    **Required scope:** `investigations:write`
    """
    success = await _service.cancel_investigation(investigation_id)
    if not success:
        investigation = await _service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Investigation in state {investigation.state.value} cannot be cancelled",
        )
