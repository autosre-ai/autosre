"""Authentication utilities: token hashing, JWT, permissions."""

import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from .settings import get_settings

settings = get_settings()

# Password/token hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Permission(str, Enum):
    """Permission levels for API access."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class TokenType(str, Enum):
    """Types of tokens."""
    ACCESS = "access"
    REFRESH = "refresh"
    API = "api"


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return pwd_context.hash(token)


def verify_token_hash(plain_token: str, hashed_token: str) -> bool:
    """Verify a plain token against its hash."""
    return pwd_context.verify(plain_token, hashed_token)


def generate_api_token() -> str:
    """Generate a secure random API token."""
    return f"asre_{secrets.token_urlsafe(32)}"


def create_jwt_token(
    data: dict[str, Any],
    token_type: TokenType = TokenType.ACCESS,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT token."""
    to_encode = data.copy()
    
    if expires_delta is None:
        if token_type == TokenType.ACCESS:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
        elif token_type == TokenType.REFRESH:
            expires_delta = timedelta(days=settings.refresh_token_expire_days)
        else:
            # API tokens don't expire by default
            expires_delta = timedelta(days=365 * 10)
    
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": token_type.value,
    })
    
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise InvalidTokenError(f"Invalid token: {e}") from e


def check_permission(required: Permission, granted: list[Permission]) -> bool:
    """Check if required permission is in granted permissions."""
    # Admin has all permissions
    if Permission.ADMIN in granted:
        return True
    
    # Write implies read
    if required == Permission.READ and Permission.WRITE in granted:
        return True
    
    return required in granted


class InvalidTokenError(Exception):
    """Raised when a token is invalid or expired."""
    pass


class InsufficientPermissionsError(Exception):
    """Raised when user lacks required permissions."""
    pass
