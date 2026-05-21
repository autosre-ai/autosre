"""Pydantic models for PagerDuty entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    """PagerDuty incident status."""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentUrgency(str, Enum):
    """PagerDuty incident urgency."""
    HIGH = "high"
    LOW = "low"


class AlertSeverity(str, Enum):
    """PagerDuty alert severity."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class WebhookEventType(str, Enum):
    """PagerDuty webhook event types."""
    INCIDENT_TRIGGERED = "incident.triggered"
    INCIDENT_ACKNOWLEDGED = "incident.acknowledged"
    INCIDENT_UNACKNOWLEDGED = "incident.unacknowledged"
    INCIDENT_RESOLVED = "incident.resolved"
    INCIDENT_REASSIGNED = "incident.reassigned"
    INCIDENT_ESCALATED = "incident.escalated"
    INCIDENT_DELEGATED = "incident.delegated"
    INCIDENT_PRIORITY_UPDATED = "incident.priority_updated"
    INCIDENT_RESPONDER_ADDED = "incident.responder.added"
    INCIDENT_RESPONDER_REPLIED = "incident.responder.replied"
    INCIDENT_STATUS_UPDATE_PUBLISHED = "incident.status_update_published"
    INCIDENT_REOPENED = "incident.reopened"
    INCIDENT_ANNOTATED = "incident.annotated"


class User(BaseModel):
    """PagerDuty user model."""
    id: str = Field(..., description="User ID")
    type: str = Field(default="user", description="Object type")
    name: str = Field(..., description="User's name")
    email: str = Field(..., description="User's email")
    html_url: str | None = Field(default=None, description="URL to user in PagerDuty")
    avatar_url: str | None = Field(default=None, description="User avatar URL")
    time_zone: str | None = Field(default=None, description="User's timezone")
    color: str | None = Field(default=None, description="User color in PagerDuty UI")
    role: str | None = Field(default=None, description="User role")
    job_title: str | None = Field(default=None, description="User's job title")
    
    model_config = {"extra": "allow"}


class Service(BaseModel):
    """PagerDuty service model."""
    id: str = Field(..., description="Service ID")
    type: str = Field(default="service", description="Object type")
    name: str = Field(..., description="Service name")
    description: str | None = Field(default=None, description="Service description")
    html_url: str | None = Field(default=None, description="URL to service in PagerDuty")
    status: str | None = Field(default=None, description="Service status")
    created_at: datetime | None = Field(default=None, description="Service creation time")
    updated_at: datetime | None = Field(default=None, description="Last update time")
    escalation_policy: dict[str, Any] | None = Field(default=None, description="Escalation policy ref")
    teams: list[dict[str, Any]] = Field(default_factory=list, description="Associated teams")
    integrations: list[dict[str, Any]] = Field(default_factory=list, description="Service integrations")
    alert_creation: str | None = Field(default=None, description="Alert creation behavior")
    alert_grouping_parameters: dict[str, Any] | None = Field(default=None, description="Alert grouping config")
    
    model_config = {"extra": "allow"}


class EscalationRule(BaseModel):
    """Single escalation rule in a policy."""
    id: str = Field(..., description="Rule ID")
    escalation_delay_in_minutes: int = Field(..., description="Delay before escalating")
    targets: list[dict[str, Any]] = Field(default_factory=list, description="Escalation targets")


class Escalation(BaseModel):
    """PagerDuty escalation policy model."""
    id: str = Field(..., description="Escalation policy ID")
    type: str = Field(default="escalation_policy", description="Object type")
    name: str = Field(..., description="Policy name")
    description: str | None = Field(default=None, description="Policy description")
    html_url: str | None = Field(default=None, description="URL to policy in PagerDuty")
    num_loops: int = Field(default=0, description="Number of escalation loops")
    on_call_handoff_notifications: str | None = Field(default=None, description="Handoff notification setting")
    escalation_rules: list[EscalationRule] = Field(default_factory=list, description="Escalation rules")
    services: list[dict[str, Any]] = Field(default_factory=list, description="Associated services")
    teams: list[dict[str, Any]] = Field(default_factory=list, description="Associated teams")
    
    model_config = {"extra": "allow"}


class AlertBody(BaseModel):
    """Alert body details."""
    type: str = Field(default="alert_body", description="Body type")
    contexts: list[dict[str, Any]] = Field(default_factory=list, description="Alert contexts")
    details: dict[str, Any] = Field(default_factory=dict, description="Alert details")


class Alert(BaseModel):
    """PagerDuty alert model."""
    id: str = Field(..., description="Alert ID")
    type: str = Field(default="alert", description="Object type")
    status: str = Field(..., description="Alert status (triggered, resolved)")
    alert_key: str | None = Field(default=None, description="Deduplication key")
    service: dict[str, Any] | None = Field(default=None, description="Associated service ref")
    created_at: datetime = Field(..., description="Alert creation time")
    resolved_at: datetime | None = Field(default=None, description="Resolution time")
    incident: dict[str, Any] | None = Field(default=None, description="Parent incident ref")
    html_url: str | None = Field(default=None, description="URL to alert in PagerDuty")
    severity: AlertSeverity | None = Field(default=None, description="Alert severity")
    summary: str | None = Field(default=None, description="Alert summary")
    body: AlertBody | None = Field(default=None, description="Alert body with details")
    suppressed: bool = Field(default=False, description="Whether alert is suppressed")
    
    model_config = {"extra": "allow"}


class Priority(BaseModel):
    """PagerDuty priority level."""
    id: str = Field(..., description="Priority ID")
    type: str = Field(default="priority", description="Object type")
    name: str = Field(..., description="Priority name (e.g., P1, P2)")
    description: str | None = Field(default=None, description="Priority description")
    order: int | None = Field(default=None, description="Priority order (lower = higher priority)")
    color: str | None = Field(default=None, description="Priority color")


class Assignment(BaseModel):
    """Incident assignment."""
    at: datetime = Field(..., description="Assignment time")
    assignee: User = Field(..., description="Assigned user")


class Acknowledgement(BaseModel):
    """Incident acknowledgement."""
    at: datetime = Field(..., description="Acknowledgement time")
    acknowledger: User = Field(..., description="User who acknowledged")


class PendingAction(BaseModel):
    """Pending action on incident."""
    type: str = Field(..., description="Action type")
    at: datetime = Field(..., description="When action will occur")


class Incident(BaseModel):
    """PagerDuty incident model."""
    id: str = Field(..., description="Incident ID")
    type: str = Field(default="incident", description="Object type")
    incident_number: int = Field(..., description="Human-readable incident number")
    title: str = Field(..., description="Incident title/summary")
    description: str | None = Field(default=None, description="Incident description")
    status: IncidentStatus = Field(..., description="Incident status")
    urgency: IncidentUrgency = Field(..., description="Incident urgency")
    html_url: str | None = Field(default=None, description="URL to incident in PagerDuty")
    created_at: datetime = Field(..., description="Incident creation time")
    updated_at: datetime | None = Field(default=None, description="Last update time")
    resolved_at: datetime | None = Field(default=None, description="Resolution time")
    last_status_change_at: datetime | None = Field(default=None, description="Last status change")
    last_status_change_by: User | dict[str, Any] | None = Field(default=None, description="Who changed status")
    service: Service | dict[str, Any] | None = Field(default=None, description="Associated service")
    escalation_policy: Escalation | dict[str, Any] | None = Field(default=None, description="Escalation policy")
    priority: Priority | None = Field(default=None, description="Incident priority")
    teams: list[dict[str, Any]] = Field(default_factory=list, description="Associated teams")
    assignments: list[Assignment | dict[str, Any]] = Field(default_factory=list, description="Current assignments")
    acknowledgements: list[Acknowledgement | dict[str, Any]] = Field(default_factory=list, description="Acknowledgements")
    pending_actions: list[PendingAction | dict[str, Any]] = Field(default_factory=list, description="Pending actions")
    alert_counts: dict[str, int] | None = Field(default=None, description="Alert counts by status")
    is_mergeable: bool = Field(default=True, description="Whether incident can be merged")
    incident_key: str | None = Field(default=None, description="Deduplication key")
    
    # Relationships
    first_trigger_log_entry: dict[str, Any] | None = Field(default=None, description="First trigger log")
    alerts: list[Alert] = Field(default_factory=list, description="Associated alerts (when included)")
    
    model_config = {"extra": "allow"}

    @property
    def is_open(self) -> bool:
        """Check if incident is still open."""
        return self.status != IncidentStatus.RESOLVED
    
    @property
    def assigned_users(self) -> list[str]:
        """Get list of assigned user IDs."""
        users = []
        for assignment in self.assignments:
            if isinstance(assignment, Assignment):
                users.append(assignment.assignee.id)
            elif isinstance(assignment, dict) and "assignee" in assignment:
                users.append(assignment["assignee"].get("id", ""))
        return users


class Note(BaseModel):
    """PagerDuty incident note."""
    id: str = Field(..., description="Note ID")
    user: User | dict[str, Any] = Field(..., description="User who created the note")
    content: str = Field(..., description="Note content")
    created_at: datetime = Field(..., description="Note creation time")
    
    model_config = {"extra": "allow"}


class LogEntry(BaseModel):
    """PagerDuty incident log entry."""
    id: str = Field(..., description="Log entry ID")
    type: str = Field(..., description="Log entry type")
    created_at: datetime = Field(..., description="Entry creation time")
    channel: dict[str, Any] | None = Field(default=None, description="Channel info")
    agent: dict[str, Any] | None = Field(default=None, description="Agent that created entry")
    note: str | None = Field(default=None, description="Associated note content")
    contexts: list[dict[str, Any]] = Field(default_factory=list, description="Entry contexts")
    event_details: dict[str, Any] | None = Field(default=None, description="Event details")
    
    model_config = {"extra": "allow"}


class OnCall(BaseModel):
    """On-call responder information."""
    user: User = Field(..., description="On-call user")
    schedule: dict[str, Any] | None = Field(default=None, description="Associated schedule")
    escalation_policy: dict[str, Any] | None = Field(default=None, description="Escalation policy")
    escalation_level: int = Field(default=1, description="Escalation level")
    start: datetime | None = Field(default=None, description="On-call period start")
    end: datetime | None = Field(default=None, description="On-call period end")
    
    model_config = {"extra": "allow"}


class PagerDutyEvent(BaseModel):
    """Generic PagerDuty event from webhook."""
    event: WebhookEventType = Field(..., description="Event type")
    created_on: datetime = Field(..., description="Event timestamp")
    data: dict[str, Any] = Field(..., description="Event data payload")
    id: str = Field(..., description="Event ID")
    
    model_config = {"extra": "allow"}


class WebhookEvent(BaseModel):
    """PagerDuty V3 webhook event structure."""
    routing_key: str | None = Field(default=None, description="Routing key for event")
    event: PagerDutyEvent = Field(..., description="Event details")
    
    @property
    def event_type(self) -> WebhookEventType:
        """Get the event type."""
        return self.event.event
    
    @property
    def incident_data(self) -> dict[str, Any] | None:
        """Extract incident data from event."""
        return self.event.data.get("incident")
    
    model_config = {"extra": "allow"}


class WebhookPayload(BaseModel):
    """Full PagerDuty V3 webhook payload (array of events)."""
    events: list[WebhookEvent] = Field(default_factory=list, description="Webhook events")
    
    model_config = {"extra": "allow"}
