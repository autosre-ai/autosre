"""
Change Management data models.

Defines all data structures for change tracking and management.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Type of change."""
    
    DEPLOYMENT = "deployment"
    CONFIG_MAP = "config_map"
    SECRET = "secret"
    SCALING = "scaling"
    RESOURCE_LIMIT = "resource_limit"
    NETWORK_POLICY = "network_policy"
    INGRESS = "ingress"
    SERVICE = "service"
    HPA = "hpa"
    PDB = "pdb"
    RBAC = "rbac"
    CRD = "crd"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    FEATURE_FLAG = "feature_flag"
    OTHER = "other"


class ChangeStatus(str, Enum):
    """Status of a change."""
    
    PLANNED = "planned"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ChangeRisk(str, Enum):
    """Risk level of a change."""
    
    MINIMAL = "minimal"     # No expected impact
    LOW = "low"             # Minor impact, easily reversible
    MEDIUM = "medium"       # Moderate impact
    HIGH = "high"           # Significant impact
    CRITICAL = "critical"   # Major impact, requires approval


class ChangeWindowType(str, Enum):
    """Type of change window."""
    
    MAINTENANCE = "maintenance"   # Scheduled maintenance
    FREEZE = "freeze"             # Change freeze
    PREFERRED = "preferred"       # Preferred change window
    EMERGENCY = "emergency"       # Emergency changes only
    BLOCKED = "blocked"           # No changes allowed


class ChangeImpact(BaseModel):
    """Assessed impact of a change."""
    
    # Affected resources
    affected_services: list[str] = Field(default_factory=list)
    affected_namespaces: list[str] = Field(default_factory=list)
    affected_pods_estimate: int = 0
    
    # User impact
    user_facing: bool = False
    estimated_user_impact_percentage: float = 0.0
    
    # Risk assessment
    downtime_risk: float = Field(0.0, ge=0, le=1)
    data_loss_risk: float = Field(0.0, ge=0, le=1)
    performance_impact_risk: float = Field(0.0, ge=0, le=1)
    
    # Dependencies
    upstream_dependencies: list[str] = Field(default_factory=list)
    downstream_dependencies: list[str] = Field(default_factory=list)
    
    # Rollback
    rollback_time_minutes: int = 5
    is_reversible: bool = True
    
    @property
    def overall_risk_score(self) -> float:
        """Calculate overall risk score (0-1)."""
        return max(
            self.downtime_risk,
            self.data_loss_risk,
            self.performance_impact_risk,
        )


class Change(BaseModel):
    """A tracked change."""
    
    id: UUID = Field(default_factory=uuid4)
    
    # Classification
    change_type: ChangeType
    status: ChangeStatus = ChangeStatus.PENDING
    risk: ChangeRisk = ChangeRisk.MEDIUM
    
    # Target
    resource_type: str = Field(..., description="Kubernetes resource type")
    resource_name: str = Field(..., description="Resource name")
    namespace: str | None = None
    cluster: str = "default"
    
    # Details
    title: str = ""
    description: str = ""
    reason: str = ""
    
    # Before/After state
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    diff: str | None = None
    
    # Impact assessment
    impact: ChangeImpact | None = None
    
    # Source
    source: str = "unknown"  # ci/cd, manual, autosre, etc.
    source_id: str | None = None  # PR number, CI job ID, etc.
    source_url: str | None = None
    
    # Actor
    changed_by: str = "unknown"
    approved_by: str | None = None
    
    # Timing
    planned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Rollback info
    rollback_id: UUID | None = None
    rolled_back_at: datetime | None = None
    
    # Correlation
    incident_ids: list[str] = Field(default_factory=list)
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_active(self) -> bool:
        return self.status in [ChangeStatus.PENDING, ChangeStatus.IN_PROGRESS]
    
    @property
    def was_successful(self) -> bool:
        return self.status == ChangeStatus.COMPLETED
    
    def to_summary(self) -> str:
        """Generate change summary."""
        status_emoji = {
            ChangeStatus.COMPLETED: "✅",
            ChangeStatus.FAILED: "❌",
            ChangeStatus.ROLLED_BACK: "🔄",
            ChangeStatus.IN_PROGRESS: "🔄",
            ChangeStatus.PENDING: "⏳",
        }.get(self.status, "❓")
        
        return (
            f"{status_emoji} [{self.change_type.value}] "
            f"{self.resource_type}/{self.namespace}/{self.resource_name} "
            f"by {self.changed_by}"
        )


class ChangeWindow(BaseModel):
    """A change window definition."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    
    # Type and status
    window_type: ChangeWindowType
    active: bool = True
    
    # Schedule
    start_time: datetime
    end_time: datetime
    
    # Recurrence (cron expression or simple pattern)
    recurrence: str | None = None
    timezone: str = "UTC"
    
    # Scope
    namespaces: list[str] = Field(default_factory=list)  # Empty = all
    clusters: list[str] = Field(default_factory=list)    # Empty = all
    change_types: list[ChangeType] = Field(default_factory=list)  # Empty = all
    
    # Exceptions
    allowed_teams: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)
    
    # Metadata
    created_by: str = "unknown"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_current(self) -> bool:
        """Check if window is currently active."""
        now = datetime.utcnow()
        return self.active and self.start_time <= now <= self.end_time
    
    @property
    def duration_hours(self) -> float:
        """Get window duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600
    
    def allows_change(
        self,
        change: Change,
        user: str | None = None,
    ) -> tuple[bool, str]:
        """
        Check if change is allowed in this window.
        
        Returns:
            Tuple of (allowed, reason)
        """
        # Check if window applies to this change
        if self.namespaces and change.namespace not in self.namespaces:
            return True, "Namespace not in window scope"
        
        if self.clusters and change.cluster not in self.clusters:
            return True, "Cluster not in window scope"
        
        if self.change_types and change.change_type not in self.change_types:
            return True, "Change type not in window scope"
        
        # Check window type
        if self.window_type == ChangeWindowType.BLOCKED:
            # Check exceptions
            if user and user in self.allowed_users:
                return True, "User is in exception list"
            return False, f"Change window '{self.name}' blocks all changes"
        
        elif self.window_type == ChangeWindowType.FREEZE:
            if user and user in self.allowed_users:
                return True, "User is in exception list"
            if change.risk == ChangeRisk.CRITICAL:
                return False, f"Change freeze '{self.name}' is active"
            return False, f"Change freeze '{self.name}' is active"
        
        elif self.window_type == ChangeWindowType.EMERGENCY:
            if change.risk in [ChangeRisk.CRITICAL, ChangeRisk.HIGH]:
                return True, "Emergency changes allowed"
            return False, f"Only emergency changes allowed during '{self.name}'"
        
        elif self.window_type == ChangeWindowType.MAINTENANCE:
            return True, f"Maintenance window '{self.name}' is active"
        
        elif self.window_type == ChangeWindowType.PREFERRED:
            return True, f"Preferred window '{self.name}' is active"
        
        return True, "No restrictions"


class IncidentCorrelation(BaseModel):
    """Correlation between an incident and changes."""
    
    incident_id: str
    incident_title: str | None = None
    incident_started_at: datetime
    
    # Correlated changes
    correlated_changes: list[UUID] = Field(default_factory=list)
    
    # Correlation details
    correlation_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Change ID -> correlation score"
    )
    
    # Analysis
    primary_suspect: UUID | None = None
    primary_suspect_confidence: float = 0.0
    analysis_summary: str = ""
    
    # Timing
    correlation_window_minutes: int = 60
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_top_suspects(self, limit: int = 5) -> list[tuple[UUID, float]]:
        """Get top suspected changes by correlation score."""
        sorted_scores = sorted(
            self.correlation_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(UUID(k), v) for k, v in sorted_scores[:limit]]
