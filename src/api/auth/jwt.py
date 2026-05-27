"""JWT Authentication middleware."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import structlog

from .models import TokenData, User

logger = structlog.get_logger()

# Configuration (in production: use pydantic-settings)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer(auto_error=False)


class JWTAuth:
    """JWT authentication handler."""

    def __init__(
        self,
        secret: str = JWT_SECRET,
        algorithm: str = JWT_ALGORITHM,
        expiration_hours: int = JWT_EXPIRATION_HOURS,
    ) -> None:
        self.secret = secret
        self.algorithm = algorithm
        self.expiration_hours = expiration_hours

    def create_token(
        self,
        user_id: str,
        scopes: list[str] | None = None,
        team_id: str | None = None,
    ) -> str:
        """Create a new JWT token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=self.expiration_hours)

        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expires,
            "scopes": scopes or [],
            "team_id": team_id,
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> TokenData | None:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
            )
            return TokenData(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                scopes=payload.get("scopes", []),
                team_id=payload.get("team_id"),
            )
        except JWTError as e:
            logger.warning("jwt_decode_failed", error=str(e))
            return None

    def verify_scope(self, token_data: TokenData, required_scope: str) -> bool:
        """Check if token has required scope."""
        # Admin scope grants all access
        if "admin" in token_data.scopes:
            return True

        # Check specific scope
        if required_scope in token_data.scopes:
            return True

        # Check wildcard scopes (e.g., "investigations:*" matches "investigations:read")
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 2:
            wildcard_scope = f"{scope_parts[0]}:*"
            if wildcard_scope in token_data.scopes:
                return True

        return False


# Global auth instance
_auth = JWTAuth()


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(security),
    ] = None,
) -> User | None:
    """Get current authenticated user from JWT token.
    
    Returns None if no valid token is provided (for optional auth).
    """
    if not credentials:
        return None

    token_data = _auth.decode_token(credentials.credentials)
    if not token_data:
        return None

    # In production: look up user from database
    return User(
        user_id=token_data.sub,
        username=token_data.sub,  # Placeholder
        team_id=token_data.team_id,
        scopes=token_data.scopes,
    )


async def require_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(security),
    ] = None,
) -> User:
    """Require authentication - raises 401 if not authenticated."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = _auth.decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In production: look up user from database
    return User(
        user_id=token_data.sub,
        username=token_data.sub,
        team_id=token_data.team_id,
        scopes=token_data.scopes,
    )


def require_scope(scope: str):
    """Dependency factory for requiring a specific scope."""

    async def _check_scope(
        user: Annotated[User, Depends(require_auth)],
    ) -> User:
        token_data = TokenData(
            sub=user.user_id,
            exp=datetime.now(timezone.utc) + timedelta(hours=1),  # Placeholder
            iat=datetime.now(timezone.utc),
            scopes=user.scopes,
            team_id=user.team_id,
        )

        if not _auth.verify_scope(token_data, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {scope}",
            )

        return user

    return _check_scope
