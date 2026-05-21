"""Agent configuration routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import AgentConfig, SkillConfig, Team
from ..schemas import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigUpdate,
    PaginatedResponse,
    SkillConfigCreate,
    SkillConfigResponse,
    SkillConfigUpdate,
    SkillToggleRequest,
    SkillToggleResponse,
)

router = APIRouter(prefix="/agents", tags=["agents"])


# ============ Agent Config Routes ============


@router.get("/config", response_model=PaginatedResponse)
async def list_agent_configs(
    team_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List agent configurations."""
    query = select(AgentConfig)
    count_query = select(func.count(AgentConfig.id))
    
    if team_id:
        query = query.where(AgentConfig.team_id == team_id)
        count_query = count_query.where(AgentConfig.team_id == team_id)
    
    total = (await session.execute(count_query)).scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(
        AgentConfig.created_at.desc()
    )
    result = await session.execute(query)
    configs = result.scalars().all()
    
    return PaginatedResponse(
        items=[AgentConfigResponse.model_validate(c) for c in configs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/config", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_config(
    config_data: AgentConfigCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new agent configuration."""
    # Verify team exists
    team_result = await session.execute(select(Team).where(Team.id == config_data.team_id))
    team = team_result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with id '{config_data.team_id}' not found",
        )
    
    config = AgentConfig(**config_data.model_dump())
    session.add(config)
    await session.flush()
    await session.refresh(config)
    
    return AgentConfigResponse.model_validate(config)


@router.get("/config/{config_id}", response_model=AgentConfigResponse)
async def get_agent_config(
    config_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get an agent configuration by ID."""
    result = await session.execute(select(AgentConfig).where(AgentConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config with id '{config_id}' not found",
        )
    
    return AgentConfigResponse.model_validate(config)


@router.put("/config/{config_id}", response_model=AgentConfigResponse)
async def update_agent_config(
    config_id: str,
    config_data: AgentConfigUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an agent configuration."""
    result = await session.execute(select(AgentConfig).where(AgentConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config with id '{config_id}' not found",
        )
    
    update_data = config_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    
    await session.flush()
    await session.refresh(config)
    
    return AgentConfigResponse.model_validate(config)


@router.delete("/config/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_config(
    config_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete an agent configuration."""
    result = await session.execute(select(AgentConfig).where(AgentConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config with id '{config_id}' not found",
        )
    
    await session.delete(config)
    await session.flush()


# ============ Skill Config Routes ============


@router.get("/skills", response_model=PaginatedResponse)
async def list_skills(
    agent_config_id: str | None = Query(None),
    category: str | None = Query(None),
    enabled_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List skill configurations."""
    query = select(SkillConfig)
    count_query = select(func.count(SkillConfig.id))
    
    if agent_config_id:
        query = query.where(SkillConfig.agent_config_id == agent_config_id)
        count_query = count_query.where(SkillConfig.agent_config_id == agent_config_id)
    
    if category:
        query = query.where(SkillConfig.category == category)
        count_query = count_query.where(SkillConfig.category == category)
    
    if enabled_only:
        query = query.where(SkillConfig.is_enabled == True)  # noqa: E712
        count_query = count_query.where(SkillConfig.is_enabled == True)  # noqa: E712
    
    total = (await session.execute(count_query)).scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(SkillConfig.skill_id)
    result = await session.execute(query)
    skills = result.scalars().all()
    
    return PaginatedResponse(
        items=[SkillConfigResponse.model_validate(s) for s in skills],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/skills", response_model=SkillConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillConfigCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new skill configuration."""
    # Verify agent config exists
    config_result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == skill_data.agent_config_id)
    )
    if not config_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config with id '{skill_data.agent_config_id}' not found",
        )
    
    # Check for duplicate skill_id within same agent config
    existing = await session.execute(
        select(SkillConfig).where(
            SkillConfig.agent_config_id == skill_data.agent_config_id,
            SkillConfig.skill_id == skill_data.skill_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Skill '{skill_data.skill_id}' already exists for this agent config",
        )
    
    skill = SkillConfig(**skill_data.model_dump())
    session.add(skill)
    await session.flush()
    await session.refresh(skill)
    
    return SkillConfigResponse.model_validate(skill)


@router.get("/skills/{skill_id}", response_model=SkillConfigResponse)
async def get_skill(
    skill_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a skill configuration by ID."""
    result = await session.execute(select(SkillConfig).where(SkillConfig.id == skill_id))
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill config with id '{skill_id}' not found",
        )
    
    return SkillConfigResponse.model_validate(skill)


@router.put("/skills/{skill_id}", response_model=SkillConfigResponse)
async def update_skill(
    skill_id: str,
    skill_data: SkillConfigUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a skill configuration."""
    result = await session.execute(select(SkillConfig).where(SkillConfig.id == skill_id))
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill config with id '{skill_id}' not found",
        )
    
    update_data = skill_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(skill, key, value)
    
    await session.flush()
    await session.refresh(skill)
    
    return SkillConfigResponse.model_validate(skill)


@router.put("/skills", response_model=SkillToggleResponse)
async def toggle_skills(
    request: SkillToggleRequest,
    session: AsyncSession = Depends(get_session),
):
    """Bulk enable/disable skills."""
    # Update all matching skills
    stmt = (
        update(SkillConfig)
        .where(SkillConfig.id.in_(request.skill_ids))
        .values(is_enabled=request.enabled)
    )
    result = await session.execute(stmt)
    
    # Fetch updated skills
    skills_result = await session.execute(
        select(SkillConfig).where(SkillConfig.id.in_(request.skill_ids))
    )
    skills = skills_result.scalars().all()
    
    return SkillToggleResponse(
        updated=result.rowcount,
        skills=[SkillConfigResponse.model_validate(s) for s in skills],
    )


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a skill configuration."""
    result = await session.execute(select(SkillConfig).where(SkillConfig.id == skill_id))
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill config with id '{skill_id}' not found",
        )
    
    await session.delete(skill)
    await session.flush()
