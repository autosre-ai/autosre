"""Token management routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import generate_api_token, hash_token, verify_token_hash
from ..db import get_session
from ..models import Team, Token
from ..schemas import (
    PaginatedResponse,
    TokenCreate,
    TokenCreateResponse,
    TokenResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=PaginatedResponse)
async def list_tokens(
    team_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """List all tokens with pagination."""
    query = select(Token)
    count_query = select(func.count(Token.id))
    
    if team_id:
        query = query.where(Token.team_id == team_id)
        count_query = count_query.where(Token.team_id == team_id)
    
    if not include_inactive:
        query = query.where(Token.is_active == True)  # noqa: E712
        count_query = count_query.where(Token.is_active == True)  # noqa: E712
    
    # Get total count
    total = (await session.execute(count_query)).scalar() or 0
    
    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Token.created_at.desc())
    result = await session.execute(query)
    tokens = result.scalars().all()
    
    return PaginatedResponse(
        items=[TokenResponse.model_validate(t) for t in tokens],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=TokenCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    token_data: TokenCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new API token."""
    # Verify team exists
    team_result = await session.execute(select(Team).where(Team.id == token_data.team_id))
    team = team_result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with id '{token_data.team_id}' not found",
        )
    
    if not team.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create tokens for inactive teams",
        )
    
    # Generate token
    raw_token = generate_api_token()
    token_prefix = raw_token[:12]  # "asre_" + first 7 chars
    token_hash = hash_token(raw_token)
    
    token = Token(
        name=token_data.name,
        description=token_data.description,
        token_hash=token_hash,
        token_prefix=token_prefix,
        permissions=[p.value for p in token_data.permissions],
        expires_at=token_data.expires_at,
        team_id=token_data.team_id,
    )
    
    session.add(token)
    await session.flush()
    await session.refresh(token)
    
    # Return response with the actual token (only time it's visible)
    response = TokenCreateResponse.model_validate(token)
    response.token = raw_token
    return response


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Revoke/delete a token."""
    result = await session.execute(select(Token).where(Token.id == token_id))
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token with id '{token_id}' not found",
        )
    
    # Soft delete by deactivating
    token.is_active = False
    await session.flush()


@router.post("/verify", response_model=TokenVerifyResponse)
async def verify_token(
    request: TokenVerifyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Verify an API token and return its metadata."""
    raw_token = request.token
    
    # Extract prefix for faster lookup
    if not raw_token.startswith("asre_"):
        return TokenVerifyResponse(
            valid=False,
            message="Invalid token format",
        )
    
    token_prefix = raw_token[:12]
    
    # Find token by prefix
    result = await session.execute(
        select(Token).where(
            Token.token_prefix == token_prefix,
            Token.is_active == True,  # noqa: E712
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        return TokenVerifyResponse(
            valid=False,
            message="Token not found or inactive",
        )
    
    # Verify hash
    if not verify_token_hash(raw_token, token.token_hash):
        return TokenVerifyResponse(
            valid=False,
            message="Invalid token",
        )
    
    # Check expiration
    if token.is_expired:
        return TokenVerifyResponse(
            valid=False,
            message="Token has expired",
        )
    
    # Update last used timestamp
    token.last_used_at = datetime.now(UTC)
    await session.flush()
    
    return TokenVerifyResponse(
        valid=True,
        team_id=token.team_id,
        permissions=token.permissions,
        expires_at=token.expires_at,
    )
