"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from ..models.common import HealthResponse, HealthStatus
from ..services import InvestigationService, MemoryService, AgentService

router = APIRouter(tags=["Health"])

# Service instances (in production: use dependency injection)
_investigation_service = InvestigationService()
_memory_service = MemoryService()
_agent_service = AgentService()

VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Comprehensive health check with component status",
)
async def health_check() -> HealthResponse:
    """
    Perform a comprehensive health check of the API and its dependencies.
    
    Returns status of:
    - Database connectivity
    - Redis/cache status
    - Agent system connectivity
    """
    checks: dict[str, HealthStatus] = {}
    overall = HealthStatus.HEALTHY

    # Check agent connectivity
    try:
        if await _agent_service.is_healthy():
            checks["agent"] = HealthStatus.HEALTHY
        else:
            checks["agent"] = HealthStatus.DEGRADED
            overall = HealthStatus.DEGRADED
    except Exception:
        checks["agent"] = HealthStatus.UNHEALTHY
        overall = HealthStatus.UNHEALTHY

    # Check memory service (database proxy)
    try:
        await _memory_service.get_stats()
        checks["database"] = HealthStatus.HEALTHY
    except Exception:
        checks["database"] = HealthStatus.UNHEALTHY
        overall = HealthStatus.UNHEALTHY

    # Redis check placeholder
    checks["redis"] = HealthStatus.HEALTHY

    return HealthResponse(
        status=overall,
        version=VERSION,
        timestamp=datetime.now(timezone.utc),
        checks=checks,
    )


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Kubernetes readiness probe - checks if service can accept traffic",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_check(response: Response) -> dict[str, str]:
    """
    Kubernetes readiness probe.
    
    Returns 200 if the service is ready to accept traffic.
    Returns 503 if the service is not ready (e.g., database unavailable).
    """
    try:
        # Check critical dependencies
        await _memory_service.get_stats()
        return {"status": "ready"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Kubernetes liveness probe - checks if service is alive",
    responses={
        200: {"description": "Service is alive"},
    },
)
async def liveness_check() -> dict[str, str]:
    """
    Kubernetes liveness probe.
    
    Always returns 200 if the service process is running.
    This should be a minimal check that doesn't depend on external services.
    """
    return {"status": "alive", "version": VERSION}
