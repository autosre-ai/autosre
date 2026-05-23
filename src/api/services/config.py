"""Config service - manages team and skill configuration."""

from datetime import datetime, timezone
from typing import Any

import structlog

from ..models.config import (
    TeamConfig,
    TeamConfigUpdate,
    SkillConfig,
    SkillList,
    SkillParameter,
    NotificationChannel,
    EscalationPolicy,
)

logger = structlog.get_logger()


class ConfigService:
    """Service for managing team and skill configuration."""

    def __init__(self) -> None:
        self._teams: dict[str, TeamConfig] = {}
        self._skills: dict[str, SkillConfig] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize with default configuration."""
        # Default teams
        default_teams = [
            TeamConfig(
                team_id="team-platform",
                name="Platform Team",
                description="Core infrastructure and platform services",
                services=["api-gateway", "auth-service", "rate-limiter", "service-mesh"],
                notification_channels=[
                    NotificationChannel(
                        type="slack",
                        target="#platform-alerts",
                        priority_threshold=3,
                        enabled=True,
                    ),
                    NotificationChannel(
                        type="pagerduty",
                        target="platform-oncall",
                        priority_threshold=1,
                        enabled=True,
                    ),
                ],
                escalation_policies=[
                    EscalationPolicy(
                        name="Default",
                        timeout_minutes=30,
                        target_team="sre-oncall",
                        notification_channels=["pagerduty"],
                    ),
                ],
                auto_remediate=True,
                investigation_timeout_minutes=45,
                preferences={"prefer_rollback": True, "auto_scale_enabled": True},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            TeamConfig(
                team_id="team-sre",
                name="SRE Team",
                description="Site Reliability Engineering - On-call escalation",
                services=[],  # Handles all services as escalation target
                notification_channels=[
                    NotificationChannel(
                        type="pagerduty",
                        target="sre-oncall",
                        priority_threshold=1,
                        enabled=True,
                    ),
                ],
                escalation_policies=[],
                auto_remediate=False,
                investigation_timeout_minutes=60,
                preferences={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        for team in default_teams:
            self._teams[team.team_id] = team

        # Default skills
        default_skills = [
            SkillConfig(
                skill_id="skill-prometheus-query",
                name="Prometheus Query",
                description="Execute PromQL queries against Prometheus for metrics analysis",
                category="diagnostic",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="query",
                        type="string",
                        description="PromQL query to execute",
                        required=True,
                    ),
                    SkillParameter(
                        name="range",
                        type="string",
                        description="Time range (e.g., 1h, 6h, 1d)",
                        required=False,
                        default="1h",
                    ),
                    SkillParameter(
                        name="step",
                        type="string",
                        description="Query resolution step",
                        required=False,
                        default="1m",
                    ),
                ],
                required_permissions=["prometheus:read"],
                applicable_services=[],
                timeout_seconds=30,
                cooldown_seconds=0,
                version="1.0.0",
            ),
            SkillConfig(
                skill_id="skill-log-search",
                name="Log Search",
                description="Search application logs via Loki/Elasticsearch",
                category="diagnostic",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="query",
                        type="string",
                        description="Log search query",
                        required=True,
                    ),
                    SkillParameter(
                        name="service",
                        type="string",
                        description="Service to search logs for",
                        required=True,
                    ),
                    SkillParameter(
                        name="time_range",
                        type="string",
                        description="Time range to search",
                        required=False,
                        default="1h",
                    ),
                    SkillParameter(
                        name="limit",
                        type="integer",
                        description="Maximum log lines to return",
                        required=False,
                        default=100,
                    ),
                ],
                required_permissions=["logs:read"],
                applicable_services=[],
                timeout_seconds=60,
                cooldown_seconds=0,
                version="1.0.0",
            ),
            SkillConfig(
                skill_id="skill-k8s-describe",
                name="Kubernetes Describe",
                description="Get detailed information about Kubernetes resources",
                category="diagnostic",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="resource_type",
                        type="string",
                        description="Resource type (pod, deployment, service, etc.)",
                        required=True,
                    ),
                    SkillParameter(
                        name="name",
                        type="string",
                        description="Resource name or label selector",
                        required=True,
                    ),
                    SkillParameter(
                        name="namespace",
                        type="string",
                        description="Kubernetes namespace",
                        required=False,
                        default="default",
                    ),
                ],
                required_permissions=["kubernetes:read"],
                applicable_services=[],
                timeout_seconds=30,
                cooldown_seconds=0,
                version="1.0.0",
            ),
            SkillConfig(
                skill_id="skill-k8s-rollback",
                name="Kubernetes Rollback",
                description="Rollback a Kubernetes deployment to previous revision",
                category="remediation",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="deployment",
                        type="string",
                        description="Deployment name",
                        required=True,
                    ),
                    SkillParameter(
                        name="namespace",
                        type="string",
                        description="Kubernetes namespace",
                        required=True,
                    ),
                    SkillParameter(
                        name="revision",
                        type="integer",
                        description="Target revision (default: previous)",
                        required=False,
                    ),
                ],
                required_permissions=["kubernetes:write", "deployments:rollback"],
                applicable_services=[],
                timeout_seconds=120,
                cooldown_seconds=300,
                version="1.0.0",
            ),
            SkillConfig(
                skill_id="skill-k8s-scale",
                name="Kubernetes Scale",
                description="Scale a Kubernetes deployment up or down",
                category="remediation",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="deployment",
                        type="string",
                        description="Deployment name",
                        required=True,
                    ),
                    SkillParameter(
                        name="namespace",
                        type="string",
                        description="Kubernetes namespace",
                        required=True,
                    ),
                    SkillParameter(
                        name="replicas",
                        type="integer",
                        description="Target replica count",
                        required=True,
                    ),
                ],
                required_permissions=["kubernetes:write", "deployments:scale"],
                applicable_services=[],
                timeout_seconds=60,
                cooldown_seconds=60,
                version="1.0.0",
            ),
            SkillConfig(
                skill_id="skill-runbook-lookup",
                name="Runbook Lookup",
                description="Search and retrieve relevant runbooks for an issue",
                category="diagnostic",
                enabled=True,
                parameters=[
                    SkillParameter(
                        name="query",
                        type="string",
                        description="Search query for runbooks",
                        required=True,
                    ),
                    SkillParameter(
                        name="service",
                        type="string",
                        description="Filter by service",
                        required=False,
                    ),
                ],
                required_permissions=["runbooks:read"],
                applicable_services=[],
                timeout_seconds=15,
                cooldown_seconds=0,
                version="1.0.0",
            ),
        ]

        for skill in default_skills:
            self._skills[skill.skill_id] = skill

    async def list_teams(self) -> list[TeamConfig]:
        """List all team configurations."""
        return list(self._teams.values())

    async def get_team(self, team_id: str) -> TeamConfig | None:
        """Get a specific team configuration."""
        return self._teams.get(team_id)

    async def update_team(
        self,
        team_id: str,
        update: TeamConfigUpdate,
    ) -> TeamConfig | None:
        """Update a team configuration."""
        team = self._teams.get(team_id)
        if not team:
            return None

        # Apply updates
        update_data = update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(team, field, value)

        team.updated_at = datetime.now(timezone.utc)

        logger.info(
            "team_updated",
            team_id=team_id,
            updated_fields=list(update_data.keys()),
        )

        return team

    async def get_team_for_service(self, service: str) -> TeamConfig | None:
        """Find the team responsible for a service."""
        for team in self._teams.values():
            if service in team.services:
                return team
        return None

    async def list_skills(
        self,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> SkillList:
        """List available skills."""
        skills = list(self._skills.values())

        if category:
            skills = [s for s in skills if s.category == category]
        if enabled_only:
            skills = [s for s in skills if s.enabled]

        # Get unique categories
        categories = list(set(s.category for s in self._skills.values()))

        return SkillList(
            skills=skills,
            total=len(skills),
            categories=sorted(categories),
        )

    async def get_skill(self, skill_id: str) -> SkillConfig | None:
        """Get a specific skill configuration."""
        return self._skills.get(skill_id)

    async def get_skills_for_service(self, service: str) -> list[SkillConfig]:
        """Get skills applicable to a specific service."""
        return [
            s for s in self._skills.values()
            if s.enabled and (not s.applicable_services or service in s.applicable_services)
        ]
