"""Configuration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from ..auth import User
from ..auth.jwt import require_scope
from ..models.config import (
    TeamConfig,
    TeamConfigUpdate,
    SkillConfig,
    SkillList,
)
from ..models.common import ErrorResponse
from ..services import ConfigService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])

# Service instance (in production: use dependency injection)
_service = ConfigService()


@router.get(
    "/teams",
    response_model=list[TeamConfig],
    summary="List Teams",
    description="List all team configurations",
)
async def list_teams(
    user: Annotated[User, Depends(require_scope("config:read"))],
) -> list[TeamConfig]:
    """
    List all configured teams and their settings.
    
    Teams define:
    - Which services they own
    - Notification preferences
    - Escalation policies
    - Auto-remediation settings
    
    **Required scope:** `config:read`
    """
    return await _service.list_teams()


@router.get(
    "/teams/{team_id}",
    response_model=TeamConfig,
    summary="Get Team",
    description="Get a specific team configuration",
    responses={
        200: {"description": "Team configuration"},
        404: {"description": "Team not found", "model": ErrorResponse},
    },
)
async def get_team(
    team_id: str,
    user: Annotated[User, Depends(require_scope("config:read"))],
) -> TeamConfig:
    """
    Get detailed configuration for a specific team.
    
    **Required scope:** `config:read`
    """
    team = await _service.get_team(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found",
        )
    return team


@router.put(
    "/teams/{team_id}",
    response_model=TeamConfig,
    summary="Update Team",
    description="Update team configuration",
    responses={
        200: {"description": "Updated team configuration"},
        404: {"description": "Team not found", "model": ErrorResponse},
    },
)
async def update_team(
    team_id: str,
    update: TeamConfigUpdate,
    user: Annotated[User, Depends(require_scope("config:write"))],
) -> TeamConfig:
    """
    Update configuration for a specific team.
    
    Only provided fields will be updated. To remove a field,
    explicitly set it to null.
    
    **Required scope:** `config:write`
    """
    logger.info(
        "team_update_requested",
        team_id=team_id,
        user=user.user_id,
        fields=list(update.model_dump(exclude_unset=True).keys()),
    )

    team = await _service.update_team(team_id, update)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found",
        )
    return team


@router.get(
    "/skills",
    response_model=SkillList,
    summary="List Skills",
    description="List available agent skills",
)
async def list_skills(
    user: Annotated[User, Depends(require_scope("config:read"))],
    category: str | None = Query(None, description="Filter by category"),
    enabled_only: bool = Query(True, description="Only show enabled skills"),
) -> SkillList:
    """
    List all available agent skills.
    
    Skills are the capabilities that agents can use during investigations:
    - **diagnostic**: Information gathering (metrics, logs, etc.)
    - **remediation**: Actions to fix issues (rollback, scale, etc.)
    - **escalation**: Notification and escalation actions
    - **monitoring**: Post-resolution monitoring
    
    **Required scope:** `config:read`
    """
    return await _service.list_skills(
        category=category,
        enabled_only=enabled_only,
    )


@router.get(
    "/skills/{skill_id}",
    response_model=SkillConfig,
    summary="Get Skill",
    description="Get a specific skill configuration",
    responses={
        200: {"description": "Skill configuration"},
        404: {"description": "Skill not found", "model": ErrorResponse},
    },
)
async def get_skill(
    skill_id: str,
    user: Annotated[User, Depends(require_scope("config:read"))],
) -> SkillConfig:
    """
    Get detailed configuration for a specific skill.
    
    **Required scope:** `config:read`
    """
    skill = await _service.get_skill(skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found",
        )
    return skill
