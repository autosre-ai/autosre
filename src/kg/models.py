"""
Pydantic models for the Knowledge Graph service.

Defines the core entities: Service, Team, Dependency, and related models
for service topology representation.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DependencyType(str, Enum):
    """Type of service dependency."""

    SYNC = "sync"
    ASYNC = "async"


class Protocol(str, Enum):
    """Communication protocol between services."""

    GRPC = "gRPC"
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    KAFKA = "kafka"
    REDIS = "redis"
    POSTGRES = "postgres"
    MYSQL = "mysql"


class ServiceTier(str, Enum):
    """Service criticality tier."""

    TIER_1 = "tier-1"  # Critical path, customer-facing
    TIER_2 = "tier-2"  # Important but not critical
    TIER_3 = "tier-3"  # Internal/support services
    TIER_4 = "tier-4"  # Development/non-production


class Criticality(str, Enum):
    """Dependency criticality level."""

    HARD = "hard"  # Service cannot function without this dependency
    SOFT = "soft"  # Service degrades gracefully without this dependency


class Team(BaseModel):
    """Team that owns services."""

    name: str = Field(..., description="Team name/identifier")
    slack_channel: str | None = Field(None, description="Slack channel for alerts")
    oncall_schedule: str | None = Field(
        None, description="PagerDuty/OpsGenie schedule ID"
    )
    email: str | None = Field(None, description="Team email for notifications")


class Dependency(BaseModel):
    """A dependency relationship between services."""

    target: str = Field(..., description="Name of the dependent service")
    type: DependencyType = Field(
        DependencyType.SYNC, description="Sync or async dependency"
    )
    protocol: Protocol = Field(Protocol.HTTP, description="Communication protocol")
    criticality: Criticality = Field(
        Criticality.HARD, description="How critical is this dependency"
    )
    port: int | None = Field(None, description="Target port if applicable")
    via: str | None = Field(None, description="Environment variable or config key")


class ServiceHealth(BaseModel):
    """Health status of a service."""

    status: str = Field("unknown", description="Current health status")
    last_incident: datetime | None = Field(None, description="Last incident timestamp")
    incident_count: int = Field(0, description="Total incident count")
    uptime_percentage: float | None = Field(
        None, description="Uptime percentage (0-100)"
    )


class Service(BaseModel):
    """A service in the topology."""

    name: str = Field(..., description="Unique service name")
    team: str | None = Field(None, description="Owning team name")
    tier: ServiceTier = Field(ServiceTier.TIER_2, description="Service tier")
    criticality: Criticality = Field(
        Criticality.HARD, description="Service criticality"
    )

    # Deployment info
    namespace: str | None = Field(None, description="Kubernetes namespace")
    cluster: str | None = Field(None, description="Kubernetes cluster")
    replicas: int | None = Field(None, description="Number of replicas")
    image: str | None = Field(None, description="Container image")
    language: str | None = Field(None, description="Primary programming language")
    port: int | None = Field(None, description="Primary service port")

    # Repository info
    repo: str | None = Field(None, description="Git repository URL")

    # Dependencies
    upstream_dependencies: list[Dependency] = Field(
        default_factory=list, description="Services this service depends on"
    )
    downstream_dependents: list[Dependency] = Field(
        default_factory=list, description="Services that depend on this service"
    )

    # Health
    health: ServiceHealth | None = Field(None, description="Current health status")

    # Metadata
    labels: dict[str, str] = Field(default_factory=dict, description="Service labels")
    annotations: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @property
    def blast_radius_count(self) -> int:
        """Number of services affected if this service fails."""
        return len(self.downstream_dependents)


class BlastRadius(BaseModel):
    """Blast radius analysis for a service."""

    service: str = Field(..., description="Source service name")
    direct_dependents: list[str] = Field(
        default_factory=list, description="Services directly depending on this service"
    )
    indirect_dependents: list[str] = Field(
        default_factory=list,
        description="Services indirectly affected (transitive dependencies)",
    )
    total_affected: int = Field(0, description="Total number of affected services")
    critical_path: bool = Field(
        False, description="Whether this service is on a critical path"
    )


class TopologyUpdate(BaseModel):
    """Batch update for service topology."""

    services: list[Service] = Field(
        default_factory=list, description="Services to create/update"
    )
    teams: list[Team] = Field(
        default_factory=list, description="Teams to create/update"
    )
    delete_missing: bool = Field(
        False, description="Delete services not in this update"
    )


class ServiceSearchResult(BaseModel):
    """Search result for service queries."""

    name: str
    team: str | None
    tier: ServiceTier
    namespace: str | None
    relevance_score: float = Field(
        1.0, description="Search relevance score (0-1 for exact match)"
    )


class AlertContext(BaseModel):
    """Context information for an alert from the knowledge graph."""

    service_name: str | None = Field(None, description="Resolved service name")
    service_info: Service | None = Field(None, description="Full service information")
    blast_radius: BlastRadius | None = Field(
        None, description="Blast radius analysis"
    )
    connected_components: list[str] = Field(
        default_factory=list, description="Related services in the topology"
    )
    recent_incidents: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent incidents for this service"
    )
