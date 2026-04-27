"""
Foundation Models - Core data structures for AutoSRE

These Pydantic models represent the entities that the agent reasons about.
All connectors normalize their data into these standard models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """Current status of a service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Alert/incident severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ChangeType(str, Enum):
    """Types of changes that can occur."""
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    ROLLBACK = "rollback"
    FEATURE_FLAG = "feature_flag"
    INFRASTRUCTURE = "infrastructure"


class Service(BaseModel):
    """
    A service in the topology.
    
    Services are the primary unit of ownership and monitoring.
    They can be Kubernetes deployments, Lambda functions, or any
    other compute unit.
    """
    name: str = Field(..., description="Unique service identifier")
    namespace: str = Field(default="default", description="Kubernetes namespace or equivalent grouping")
    cluster: str = Field(default="default", description="Cluster or environment name")
    
    # Topology
    dependencies: list[str] = Field(default_factory=list, description="Services this service depends on")
    dependents: list[str] = Field(default_factory=list, description="Services that depend on this service")
    
    # Current state
    status: ServiceStatus = Field(default=ServiceStatus.UNKNOWN)
    replicas: int = Field(default=1, description="Current replica count")
    ready_replicas: int = Field(default=0, description="Ready replicas")
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Timestamps
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is fully healthy."""
        return self.status == ServiceStatus.HEALTHY and self.ready_replicas >= self.replicas


class Ownership(BaseModel):
    """
    Ownership mapping for a service or component.
    
    Links services to teams/individuals for escalation.
    """
    service_name: str = Field(..., description="Service this ownership applies to")
    team: str = Field(..., description="Team name")
    slack_channel: Optional[str] = Field(None, description="Slack channel for alerts")
    pagerduty_service_id: Optional[str] = Field(None, description="PagerDuty service ID")
    oncall_email: Optional[str] = Field(None, description="On-call rotation email")
    escalation_contacts: list[str] = Field(default_factory=list, description="Escalation contact emails")
    
    # Metadata
    tier: int = Field(default=3, description="Service tier (1=critical, 2=important, 3=standard)")
    slo_target: Optional[float] = Field(None, description="SLO target percentage (e.g., 99.9)")


class ChangeEvent(BaseModel):
    """
    A change event in the system.
    
    Changes are the #1 cause of incidents. Tracking them is critical
    for root cause analysis.
    """
    id: str = Field(..., description="Unique change identifier")
    change_type: ChangeType
    service_name: str = Field(..., description="Service affected by this change")
    
    # Change details
    description: str = Field(..., description="Human-readable description")
    author: str = Field(..., description="Who made the change")
    
    # Git/deployment info
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    
    # Version info
    previous_version: Optional[str] = None
    new_version: Optional[str] = None
    
    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Status
    successful: bool = Field(default=True)
    rolled_back: bool = Field(default=False)


class Runbook(BaseModel):
    """
    A runbook for handling specific types of incidents.
    
    Runbooks contain documented procedures for remediation.
    """
    id: str = Field(..., description="Unique runbook identifier")
    title: str = Field(..., description="Runbook title")
    
    # Matching
    alert_names: list[str] = Field(default_factory=list, description="Alert names this runbook applies to")
    services: list[str] = Field(default_factory=list, description="Services this runbook applies to")
    keywords: list[str] = Field(default_factory=list, description="Keywords for matching")
    
    # Content
    description: str = Field(..., description="Brief description")
    steps: list[str] = Field(default_factory=list, description="Step-by-step remediation")
    
    # Automation
    automated: bool = Field(default=False, description="Can this runbook be automated?")
    automation_script: Optional[str] = Field(None, description="Path to automation script")
    requires_approval: bool = Field(default=True, description="Requires human approval?")
    
    # Metadata
    author: Optional[str] = None
    last_updated: Optional[datetime] = None
    success_rate: Optional[float] = Field(None, description="Historical success rate")


class Alert(BaseModel):
    """
    An alert from a monitoring system.
    
    Alerts are the primary input to the agent's reasoning loop.
    """
    id: str = Field(..., description="Unique alert identifier")
    name: str = Field(..., description="Alert name")
    severity: Severity = Field(default=Severity.MEDIUM)
    
    # Source
    source: str = Field(default="prometheus", description="Alert source system")
    service_name: Optional[str] = Field(None, description="Affected service")
    namespace: Optional[str] = None
    cluster: Optional[str] = None
    
    # Alert content
    summary: str = Field(..., description="Alert summary")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Labels and annotations (from Prometheus/Alertmanager)
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    # Timing
    fired_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    # Related data
    metric_query: Optional[str] = Field(None, description="PromQL query that triggered this")
    metric_value: Optional[float] = Field(None, description="Metric value when alert fired")
    
    @property
    def is_firing(self) -> bool:
        """Check if alert is still firing."""
        return self.resolved_at is None


class Incident(BaseModel):
    """
    An incident being investigated.
    
    Incidents may be triggered by one or more alerts and represent
    a user-impacting event being investigated.
    """
    id: str = Field(..., description="Unique incident identifier")
    title: str = Field(..., description="Incident title")
    severity: Severity = Field(default=Severity.MEDIUM)
    
    # Related entities
    alerts: list[str] = Field(default_factory=list, description="Related alert IDs")
    services: list[str] = Field(default_factory=list, description="Affected services")
    changes: list[str] = Field(default_factory=list, description="Related change event IDs")
    
    # Investigation
    root_cause: Optional[str] = Field(None, description="Identified root cause")
    remediation: Optional[str] = Field(None, description="Applied remediation")
    runbook_used: Optional[str] = Field(None, description="Runbook ID used")
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    detected_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Ownership
    assigned_to: Optional[str] = None
    team: Optional[str] = None
    
    # Agent analysis
    agent_analysis: Optional[str] = Field(None, description="Agent's analysis")
    agent_confidence: Optional[float] = Field(None, description="Agent confidence 0-1")
    human_override: bool = Field(default=False, description="Was agent overridden?")
    
    @property
    def is_resolved(self) -> bool:
        """Check if incident is resolved."""
        return self.resolved_at is not None
    
    @property
    def time_to_detect(self) -> Optional[float]:
        """Time from start to detection in seconds."""
        if self.detected_at and self.started_at:
            return (self.detected_at - self.started_at).total_seconds()
        return None
    
    @property
    def time_to_resolve(self) -> Optional[float]:
        """Time from start to resolution in seconds."""
        if self.resolved_at and self.started_at:
            return (self.resolved_at - self.started_at).total_seconds()
        return None
