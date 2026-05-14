"""JWT Authentication middleware for AutoSRE API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence


class User(BaseModel):
    """Authenticated user model."""

    id: str
    roles: list[str] = []
    email: str | None = None
    metadata: dict[str, Any] = {}


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # user_id
    roles: list[str]
    exp: datetime
    iat: datetime
    jti: str | None = None  # JWT ID for token revocation


class JWTAuth:
    """JWT authentication for API routes.

    Handles token creation, verification, and refresh with proper
    async patterns and security best practices.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
    ) -> None:
        """Initialize JWT authentication.

        Args:
            secret_key: Secret key for signing tokens. Defaults to env var.
            algorithm: JWT signing algorithm.
            access_token_expire_minutes: Access token lifetime in minutes.
            refresh_token_expire_days: Refresh token lifetime in days.
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "")
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY must be set")

        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

        # Token blacklist (in production, use Redis)
        self._revoked_tokens: set[str] = set()

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: The JWT token to verify.

        Returns:
            Decoded token payload.

        Raises:
            HTTPException: If token is invalid, expired, or revoked.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )

            # Check if token is revoked
            jti = payload.get("jti")
            if jti and jti in self._revoked_tokens:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def create_token(
        self,
        user_id: str,
        roles: list[str],
        token_type: str = "access",
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a new JWT token.

        Args:
            user_id: The user's unique identifier.
            roles: List of user roles.
            token_type: Either "access" or "refresh".
            additional_claims: Extra claims to include in the token.

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(timezone.utc)

        if token_type == "refresh":
            expire = now + timedelta(days=self.refresh_token_expire_days)
        else:
            expire = now + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "roles": roles,
            "exp": expire,
            "iat": now,
            "type": token_type,
            "jti": f"{user_id}-{now.timestamp()}",
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def refresh_token(self, token: str) -> str:
        """Refresh an existing token.

        Args:
            token: The refresh token to use.

        Returns:
            New access token.

        Raises:
            HTTPException: If refresh token is invalid or not a refresh token.
        """
        payload = await self.verify_token(token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for refresh",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Revoke the old refresh token
        if jti := payload.get("jti"):
            self._revoked_tokens.add(jti)

        # Create new access token
        return await self.create_token(
            user_id=payload["sub"],
            roles=payload.get("roles", []),
            token_type="access",
        )

    async def revoke_token(self, token: str) -> None:
        """Revoke a token (logout).

        Args:
            token: The token to revoke.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},  # Allow revoking expired tokens
            )
            if jti := payload.get("jti"):
                self._revoked_tokens.add(jti)
        except jwt.InvalidTokenError:
            pass  # Invalid tokens are already unusable


# Global JWT auth instance (configured on startup)
_jwt_auth: JWTAuth | None = None


def configure_jwt_auth(
    secret_key: str | None = None,
    **kwargs: Any,
) -> JWTAuth:
    """Configure the global JWT auth instance.

    Args:
        secret_key: Secret key for signing tokens.
        **kwargs: Additional arguments for JWTAuth.

    Returns:
        Configured JWTAuth instance.
    """
    global _jwt_auth
    _jwt_auth = JWTAuth(secret_key=secret_key, **kwargs)
    return _jwt_auth


def get_jwt_auth() -> JWTAuth:
    """Get the configured JWT auth instance.

    Raises:
        RuntimeError: If JWT auth is not configured.
    """
    if _jwt_auth is None:
        raise RuntimeError("JWT auth not configured. Call configure_jwt_auth() first.")
    return _jwt_auth


# Security scheme for OpenAPI docs
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """Extract and validate the current user from the request.

    This is a FastAPI dependency that can be used in route handlers.

    Args:
        request: The incoming request.
        credentials: Bearer token credentials.

    Returns:
        The authenticated User.

    Raises:
        HTTPException: If authentication fails.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_auth = get_jwt_auth()
    payload = await jwt_auth.verify_token(credentials.credentials)

    # Store user in request state for logging/auditing
    user = User(
        id=payload["sub"],
        roles=payload.get("roles", []),
        email=payload.get("email"),
        metadata=payload.get("metadata", {}),
    )
    request.state.user = user

    return user


def require_role(*required_roles: str) -> Callable[..., Any]:
    """Create a dependency that requires specific roles.

    Args:
        *required_roles: Roles that are allowed access.

    Returns:
        FastAPI dependency that enforces role requirements.

    Example:
        @app.get("/admin")
        async def admin_route(user: User = Depends(require_role("admin"))):
            return {"message": "Welcome, admin!"}
    """

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if not any(role in user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(required_roles)}",
            )
        return user

    return role_checker


def require_all_roles(*required_roles: str) -> Callable[..., Any]:
    """Create a dependency that requires ALL specified roles.

    Args:
        *required_roles: All roles that must be present.

    Returns:
        FastAPI dependency that enforces all role requirements.
    """

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        missing_roles = set(required_roles) - set(user.roles)
        if missing_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required roles: {', '.join(missing_roles)}",
            )
        return user

    return role_checker
