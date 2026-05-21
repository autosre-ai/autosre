"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ============ Enums ============

class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============ Team Schemas ============

class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class TeamResponse(TeamBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============ Token Schemas ============

class TokenBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    permissions: list[Permission] = Field(default=[Permission.READ])
    expires_at: datetime | None = None


class TokenCreate(TokenBase):
    team_id: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    description: str | None
    token_prefix: str
    permissions: list[str]
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    team_id: str


class TokenCreateResponse(TokenResponse):
    """Response when creating a token - includes the actual token value."""
    token: str  # Only returned on creation


class TokenVerifyRequest(BaseModel):
    token: str


class TokenVerifyResponse(BaseModel):
    valid: bool
    team_id: str | None = None
    permissions: list[str] = []
    expires_at: datetime | None = None
    message: str | None = None


# ============ Agent Config Schemas ============

class AgentConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    model: str = "claude-sonnet-4-20250514"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=100000)
    system_prompt: str | None = None
    context_window: int = Field(default=100000, ge=1000, le=200000)
    integrations: dict = Field(default_factory=dict)
    alert_channels: dict = Field(default_factory=dict)
    max_requests_per_minute: int = Field(default=60, ge=1, le=1000)
    max_actions_per_incident: int = Field(default=50, ge=1, le=500)


class AgentConfigCreate(AgentConfigBase):
    team_id: str


class AgentConfigUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=100000)
    system_prompt: str | None = None
    context_window: int | None = Field(None, ge=1000, le=200000)
    integrations: dict | None = None
    alert_channels: dict | None = None
    max_requests_per_minute: int | None = Field(None, ge=1, le=1000)
    max_actions_per_incident: int | None = Field(None, ge=1, le=500)


class AgentConfigResponse(AgentConfigBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    team_id: str
    created_at: datetime
    updated_at: datetime


# ============ Skill Config Schemas ============

class SkillConfigBase(BaseModel):
    skill_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: str = "general"
    is_enabled: bool = True
    config: dict = Field(default_factory=dict)
    requires_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    max_calls_per_hour: int | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=3600)


class SkillConfigCreate(SkillConfigBase):
    agent_config_id: str


class SkillConfigUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None
    is_enabled: bool | None = None
    config: dict | None = None
    requires_approval: bool | None = None
    risk_level: RiskLevel | None = None
    max_calls_per_hour: int | None = None
    timeout_seconds: int | None = Field(None, ge=1, le=3600)


class SkillConfigResponse(SkillConfigBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    agent_config_id: str
    created_at: datetime
    updated_at: datetime


class SkillToggleRequest(BaseModel):
    skill_ids: list[str]
    enabled: bool


class SkillToggleResponse(BaseModel):
    updated: int
    skills: list[SkillConfigResponse]


# ============ Common Schemas ============

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
