"""API dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Permission, verify_token_hash
from .db import get_session
from .models import Team, Token

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_token(
    api_key: str | None = Security(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> Token | None:
    """Get the current token from the API key header."""
    if not api_key:
        return None
    
    if not api_key.startswith("asre_"):
        return None
    
    token_prefix = api_key[:12]
    
    result = await session.execute(
        select(Token).where(
            Token.token_prefix == token_prefix,
            Token.is_active == True,  # noqa: E712
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        return None
    
    if not verify_token_hash(api_key, token.token_hash):
        return None
    
    if token.is_expired:
        return None
    
    return token


async def require_auth(
    token: Token | None = Depends(get_current_token),
) -> Token:
    """Require authentication - raises 401 if not authenticated."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return token


async def require_read_permission(
    token: Token = Depends(require_auth),
) -> Token:
    """Require read permission."""
    permissions = [Permission(p) for p in token.permissions]
    if Permission.ADMIN in permissions or Permission.WRITE in permissions or Permission.READ in permissions:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions - read access required",
    )


async def require_write_permission(
    token: Token = Depends(require_auth),
) -> Token:
    """Require write permission."""
    permissions = [Permission(p) for p in token.permissions]
    if Permission.ADMIN in permissions or Permission.WRITE in permissions:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions - write access required",
    )


async def require_admin_permission(
    token: Token = Depends(require_auth),
) -> Token:
    """Require admin permission."""
    permissions = [Permission(p) for p in token.permissions]
    if Permission.ADMIN in permissions:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions - admin access required",
    )


async def get_current_team(
    token: Token = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Team:
    """Get the team associated with the current token."""
    result = await session.execute(select(Team).where(Team.id == token.team_id))
    team = result.scalar_one_or_none()
    
    if not team or not team.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is inactive or does not exist",
        )
    
    return team


# Type aliases for dependency injection
CurrentToken = Annotated[Token, Depends(require_auth)]
ReadToken = Annotated[Token, Depends(require_read_permission)]
WriteToken = Annotated[Token, Depends(require_write_permission)]
AdminToken = Annotated[Token, Depends(require_admin_permission)]
CurrentTeam = Annotated[Team, Depends(get_current_team)]
