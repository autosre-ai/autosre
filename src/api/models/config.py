"""Configuration models for teams and skills."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationChannel(BaseModel):
    """Notification channel configuration."""
    type: str = Field(..., description="Channel type (slack, pagerduty, email, webhook)")
    target: str = Field(..., description="Channel target (ID, email, URL)")
    priority_threshold: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Minimum priority to notify"
    )
    enabled: bool = Field(default=True, description="Whether this channel is active")


class EscalationPolicy(BaseModel):
    """Escalation policy configuration."""
    name: str = Field(..., description="Policy name")
    timeout_minutes: int = Field(
        ...,
        ge=1,
        description="Minutes before escalating"
    )
    target_team: str | None = Field(
        default=None,
        description="Team to escalate to"
    )
    notification_channels: list[str] = Field(
        default_factory=list,
        description="Channels to notify on escalation"
    )


class TeamConfig(BaseModel):
    """Team configuration."""
    team_id: str = Field(..., description="Unique team identifier")
    name: str = Field(..., description="Team display name")
    description: str | None = Field(default=None, description="Team description")
    services: list[str] = Field(
        default_factory=list,
        description="Services owned by this team"
    )
    notification_channels: list[NotificationChannel] = Field(
        default_factory=list,
        description="Configured notification channels"
    )
    escalation_policies: list[EscalationPolicy] = Field(
        default_factory=list,
        description="Escalation policies"
    )
    auto_remediate: bool = Field(
        default=False,
        description="Allow automatic remediation for this team's services"
    )
    investigation_timeout_minutes: int = Field(
        default=30,
        ge=5,
        le=240,
        description="Max investigation time before escalation"
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Team-specific preferences"
    )
    created_at: datetime = Field(..., description="Team creation time")
    updated_at: datetime = Field(..., description="Last update time")

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": "team-platform",
                "name": "Platform Team",
                "description": "Core infrastructure and platform services",
                "services": ["api-gateway", "auth-service", "rate-limiter"],
                "notification_channels": [
                    {
                        "type": "slack",
                        "target": "#platform-alerts",
                        "priority_threshold": 3,
                        "enabled": True
                    }
                ],
                "escalation_policies": [
                    {
                        "name": "Default Escalation",
                        "timeout_minutes": 30,
                        "target_team": "sre-oncall",
                        "notification_channels": ["pagerduty"]
                    }
                ],
                "auto_remediate": True,
                "investigation_timeout_minutes": 45,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-14T12:00:00Z"
            }
        }
    }


class TeamConfigUpdate(BaseModel):
    """Partial update for team configuration."""
    name: str | None = Field(default=None, description="Team display name")
    description: str | None = Field(default=None, description="Team description")
    services: list[str] | None = Field(default=None, description="Services owned")
    notification_channels: list[NotificationChannel] | None = Field(
        default=None,
        description="Notification channels"
    )
    escalation_policies: list[EscalationPolicy] | None = Field(
        default=None,
        description="Escalation policies"
    )
    auto_remediate: bool | None = Field(default=None, description="Auto-remediate flag")
    investigation_timeout_minutes: int | None = Field(
        default=None,
        ge=5,
        le=240,
        description="Investigation timeout"
    )
    preferences: dict[str, Any] | None = Field(default=None, description="Preferences")

    model_config = {
        "json_schema_extra": {
            "example": {
                "auto_remediate": True,
                "notification_channels": [
                    {
                        "type": "slack",
                        "target": "#platform-alerts",
                        "priority_threshold": 2,
                        "enabled": True
                    }
                ]
            }
        }
    }


class SkillParameter(BaseModel):
    """Skill parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether required")
    default: Any | None = Field(default=None, description="Default value")


class SkillConfig(BaseModel):
    """Agent skill configuration."""
    skill_id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Skill display name")
    description: str = Field(..., description="What this skill does")
    category: str = Field(..., description="Skill category (diagnostic, remediation, etc)")
    enabled: bool = Field(default=True, description="Whether skill is enabled")
    parameters: list[SkillParameter] = Field(
        default_factory=list,
        description="Required parameters"
    )
    required_permissions: list[str] = Field(
        default_factory=list,
        description="Permissions needed"
    )
    applicable_services: list[str] = Field(
        default_factory=list,
        description="Services this skill can target (empty = all)"
    )
    timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=600,
        description="Execution timeout"
    )
    cooldown_seconds: int = Field(
        default=0,
        ge=0,
        description="Minimum time between executions"
    )
    version: str = Field(..., description="Skill version")

    model_config = {
        "json_schema_extra": {
            "example": {
                "skill_id": "skill-prometheus-query",
                "name": "Prometheus Query",
                "description": "Execute PromQL queries against Prometheus",
                "category": "diagnostic",
                "enabled": True,
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "PromQL query",
                        "required": True
                    },
                    {
                        "name": "range",
                        "type": "string",
                        "description": "Time range (e.g., 1h)",
                        "required": False,
                        "default": "1h"
                    }
                ],
                "required_permissions": ["prometheus:read"],
                "applicable_services": [],
                "timeout_seconds": 30,
                "cooldown_seconds": 0,
                "version": "1.0.0"
            }
        }
    }


class SkillList(BaseModel):
    """List of available skills."""
    skills: list[SkillConfig] = Field(..., description="Available skills")
    total: int = Field(..., ge=0, description="Total skill count")
    categories: list[str] = Field(..., description="Available categories")
