"""Team management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Team
from ..schemas import PaginatedResponse, TeamCreate, TeamResponse, TeamUpdate

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=PaginatedResponse)
async def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """List all teams with pagination."""
    # Base query
    query = select(Team)
    count_query = select(func.count(Team.id))
    
    if not include_inactive:
        query = query.where(Team.is_active == True)  # noqa: E712
        count_query = count_query.where(Team.is_active == True)  # noqa: E712
    
    # Get total count
    total = (await session.execute(count_query)).scalar() or 0
    
    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Team.created_at.desc())
    result = await session.execute(query)
    teams = result.scalars().all()
    
    return PaginatedResponse(
        items=[TeamResponse.model_validate(t) for t in teams],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new team."""
    # Check if name already exists
    existing = await session.execute(select(Team).where(Team.name == team_data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with name '{team_data.name}' already exists",
        )
    
    team = Team(**team_data.model_dump())
    session.add(team)
    await session.flush()
    await session.refresh(team)
    
    return TeamResponse.model_validate(team)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a team by ID."""
    result = await session.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with id '{team_id}' not found",
        )
    
    return TeamResponse.model_validate(team)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    team_data: TeamUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a team."""
    result = await session.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with id '{team_id}' not found",
        )
    
    # Check name uniqueness if changing
    update_data = team_data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != team.name:
        existing = await session.execute(
            select(Team).where(Team.name == update_data["name"], Team.id != team_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Team with name '{update_data['name']}' already exists",
            )
    
    for key, value in update_data.items():
        setattr(team, key, value)
    
    await session.flush()
    await session.refresh(team)
    
    return TeamResponse.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a team (soft delete by deactivating)."""
    result = await session.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with id '{team_id}' not found",
        )
    
    # Soft delete
    team.is_active = False
    await session.flush()
