"""Memory and episodic learning endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from ..auth import User, require_auth
from ..auth.jwt import require_scope
from ..models.memory import (
    Episode,
    EpisodeList,
    EpisodeSearch,
    EpisodeSearchResults,
    Strategy,
    StrategyList,
    StrategyType,
    MemoryStats,
    EpisodeOutcome,
)
from ..models.common import ErrorResponse
from ..services import MemoryService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])

# Service instance (in production: use dependency injection)
_service = MemoryService()


@router.get(
    "/episodes",
    response_model=EpisodeList,
    summary="List Episodes",
    description="List investigation episodes stored in memory",
)
async def list_episodes(
    user: Annotated[User, Depends(require_scope("memory:read"))],
    service: str | None = Query(None, description="Filter by service"),
    outcome: EpisodeOutcome | None = Query(None, description="Filter by outcome"),
    date_from: datetime | None = Query(None, description="Start date filter"),
    date_to: datetime | None = Query(None, description="End date filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> EpisodeList:
    """
    List investigation episodes from the episodic memory system.
    
    Episodes are past investigations that have been processed and stored
    for learning and similarity matching.
    
    **Required scope:** `memory:read`
    """
    return await _service.list_episodes(
        service=service,
        outcome=outcome,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/episodes/{episode_id}",
    response_model=Episode,
    summary="Get Episode",
    description="Get a specific episode by ID",
    responses={
        200: {"description": "Episode details"},
        404: {"description": "Episode not found", "model": ErrorResponse},
    },
)
async def get_episode(
    episode_id: str,
    user: Annotated[User, Depends(require_scope("memory:read"))],
) -> Episode:
    """
    Get detailed information about a specific episode.
    
    **Required scope:** `memory:read`
    """
    episode = await _service.get_episode(episode_id)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode {episode_id} not found",
        )
    return episode


@router.post(
    "/search",
    response_model=EpisodeSearchResults,
    summary="Search Episodes",
    description="Search for similar episodes using semantic or keyword search",
)
async def search_episodes(
    search: EpisodeSearch,
    user: Annotated[User, Depends(require_scope("memory:read"))],
) -> EpisodeSearchResults:
    """
    Search for similar episodes in the episodic memory.
    
    Supports both semantic (vector similarity) and keyword search.
    Semantic search finds conceptually similar incidents even with
    different wording.
    
    **Use cases:**
    - Find past incidents similar to current alert
    - Learn from previous resolutions
    - Identify patterns across services
    
    **Required scope:** `memory:read`
    """
    logger.info(
        "episode_search",
        user=user.user_id,
        query=search.query[:50],
        semantic=search.use_semantic,
    )

    return await _service.search_episodes(search)


@router.get(
    "/strategies",
    response_model=StrategyList,
    summary="List Strategies",
    description="List learned investigation strategies",
)
async def list_strategies(
    user: Annotated[User, Depends(require_scope("memory:read"))],
    strategy_type: StrategyType | None = Query(None, description="Filter by type"),
    service: str | None = Query(None, description="Filter by applicable service"),
) -> StrategyList:
    """
    List investigation strategies learned from past episodes.
    
    Strategies are generalized approaches extracted from successful
    investigations. They provide reusable patterns for common issues.
    
    **Strategy types:**
    - `diagnostic`: Steps to identify root cause
    - `remediation`: Steps to fix the issue
    - `escalation`: When and how to escalate
    - `monitoring`: What to watch after resolution
    
    **Required scope:** `memory:read`
    """
    return await _service.list_strategies(
        strategy_type=strategy_type,
        service=service,
    )


@router.get(
    "/strategies/{strategy_id}",
    response_model=Strategy,
    summary="Get Strategy",
    description="Get a specific strategy by ID",
    responses={
        200: {"description": "Strategy details"},
        404: {"description": "Strategy not found", "model": ErrorResponse},
    },
)
async def get_strategy(
    strategy_id: str,
    user: Annotated[User, Depends(require_scope("memory:read"))],
) -> Strategy:
    """
    Get detailed information about a specific strategy.
    
    **Required scope:** `memory:read`
    """
    strategy = await _service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )
    return strategy


@router.get(
    "/stats",
    response_model=MemoryStats,
    summary="Memory Statistics",
    description="Get memory system statistics and insights",
)
async def get_stats(
    user: Annotated[User, Depends(require_scope("memory:read"))],
) -> MemoryStats:
    """
    Get statistics about the episodic memory system.
    
    Includes:
    - Total episodes and strategies
    - Success rates
    - Top services and alert types
    - Feedback distribution
    
    **Required scope:** `memory:read`
    """
    return await _service.get_stats()
