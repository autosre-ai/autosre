"""Authentication models."""

from datetime import datetime
from pydantic import BaseModel, Field


class TokenData(BaseModel):
    """JWT token payload data."""
    sub: str = Field(..., description="Subject (user ID)")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    scopes: list[str] = Field(default_factory=list, description="Authorized scopes")
    team_id: str | None = Field(default=None, description="User's team ID")


class User(BaseModel):
    """Authenticated user information."""
    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str | None = Field(default=None, description="User email")
    team_id: str | None = Field(default=None, description="User's team")
    scopes: list[str] = Field(default_factory=list, description="User permissions")
    is_active: bool = Field(default=True, description="Whether user is active")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user-123",
                "username": "john.doe",
                "email": "john@example.com",
                "team_id": "team-platform",
                "scopes": ["investigations:read", "investigations:write"],
                "is_active": True
            }
        }
    }


class TokenResponse(BaseModel):
    """Token response for authentication."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token validity in seconds")
    scopes: list[str] = Field(default_factory=list, description="Granted scopes")
