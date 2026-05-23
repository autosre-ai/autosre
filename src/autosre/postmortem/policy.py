"""
Postmortem Policy for AutoSRE.

Defines when postmortems are required and tracks completion.
Key triggers: user impact, data loss, on-call intervention, long resolution, monitoring failure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Callable
from enum import Enum
from pathlib import Path
import yaml


class TriggerType(Enum):
    """Types of postmortem triggers."""
    USER_VISIBLE_DEGRADATION = "user_visible_degradation"
    DATA_LOSS = "data_loss"
    ON_CALL_INTERVENTION = "on_call_intervention"
    LONG_RESOLUTION = "long_resolution"
    MONITORING_FAILURE = "monitoring_failure"
    SECURITY_INCIDENT = "security_incident"
    REVENUE_IMPACT = "revenue_impact"
    MANUAL = "manual"


@dataclass
class PostmortemTrigger:
    """A trigger condition for requiring a postmortem."""
    
    trigger_type: TriggerType
    description: str
    threshold: Optional[Any] = None  # e.g., resolution_time > 30 minutes
    enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.trigger_type.value,
            "description": self.description,
            "threshold": self.threshold,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostmortemTrigger":
        """Create from dictionary."""
        return cls(
            trigger_type=TriggerType(data["type"]),
            description=data.get("description", ""),
            threshold=data.get("threshold"),
            enabled=data.get("enabled", True),
        )


@dataclass
class PostmortemTicket:
    """A postmortem ticket/task."""
    
    incident_id: str
    title: str
    triggered_by: list[TriggerType]
    created_at: datetime
    due_date: datetime
    status: str = "open"  # open, in_progress, completed, overdue
    assignee: Optional[str] = None
    ticket_url: Optional[str] = None
    postmortem_url: Optional[str] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "triggered_by": [t.value for t in self.triggered_by],
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat(),
            "status": self.status,
            "assignee": self.assignee,
            "ticket_url": self.ticket_url,
            "postmortem_url": self.postmortem_url,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class PolicyConfig:
    """Configuration for postmortem policy."""
    
    # Triggers
    triggers: list[PostmortemTrigger] = field(default_factory=list)
    
    # Thresholds
    resolution_time_threshold_minutes: int = 30
    default_due_days: int = 5
    
    # Tracking
    require_action_items: bool = True
    require_ai_review: bool = True
    auto_create_ticket: bool = True
    
    # Notification
    notify_on_trigger: bool = True
    notification_channel: Optional[str] = None
    
    @classmethod
    def default(cls) -> "PolicyConfig":
        """Create default policy configuration."""
        return cls(
            triggers=[
                PostmortemTrigger(
                    trigger_type=TriggerType.USER_VISIBLE_DEGRADATION,
                    description="Any incident with user-visible impact",
                    enabled=True,
                ),
                PostmortemTrigger(
                    trigger_type=TriggerType.DATA_LOSS,
                    description="Any incident involving data loss or corruption",
                    enabled=True,
                ),
                PostmortemTrigger(
                    trigger_type=TriggerType.ON_CALL_INTERVENTION,
                    description="Any incident requiring on-call intervention",
                    enabled=True,
                ),
                PostmortemTrigger(
                    trigger_type=TriggerType.LONG_RESOLUTION,
                    description="Resolution time exceeded threshold",
                    threshold=30,  # minutes
                    enabled=True,
                ),
                PostmortemTrigger(
                    trigger_type=TriggerType.MONITORING_FAILURE,
                    description="Monitoring or alerting failed to detect issue",
                    enabled=True,
                ),
            ],
            resolution_time_threshold_minutes=30,
            default_due_days=5,
        )


class PostmortemPolicy:
    """
    Manages postmortem policy and ticket creation.
    
    Automatically determines when postmortems are required and
    tracks their completion.
    """
    
    def __init__(
        self,
        config: Optional[PolicyConfig] = None,
        ticket_callback: Optional[Callable[[PostmortemTicket], None]] = None,
    ):
        """
        Initialize policy manager.
        
        Args:
            config: Policy configuration
            ticket_callback: Callback for ticket creation (e.g., Jira, Linear)
        """
        self.config = config or PolicyConfig.default()
        self.ticket_callback = ticket_callback
        
        # Track tickets
        self._tickets: dict[str, PostmortemTicket] = {}
    
    def evaluate_incident(
        self,
        incident_id: str,
        incident_data: dict[str, Any],
    ) -> tuple[bool, list[TriggerType]]:
        """
        Evaluate if an incident requires a postmortem.
        
        Args:
            incident_id: Unique incident identifier
            incident_data: Incident details
            
        Returns:
            Tuple of (requires_postmortem, triggered_by)
        """
        triggered_by: list[TriggerType] = []
        
        for trigger in self.config.triggers:
            if not trigger.enabled:
                continue
            
            if self._check_trigger(trigger, incident_data):
                triggered_by.append(trigger.trigger_type)
        
        return len(triggered_by) > 0, triggered_by
    
    def _check_trigger(
        self,
        trigger: PostmortemTrigger,
        incident_data: dict[str, Any],
    ) -> bool:
        """Check if a specific trigger condition is met."""
        
        if trigger.trigger_type == TriggerType.USER_VISIBLE_DEGRADATION:
            # Check for user impact
            return bool(incident_data.get("user_impact")) or \
                   incident_data.get("user_facing", False)
        
        elif trigger.trigger_type == TriggerType.DATA_LOSS:
            # Check for data loss indicators
            return incident_data.get("data_loss", False) or \
                   "data loss" in str(incident_data.get("description", "")).lower()
        
        elif trigger.trigger_type == TriggerType.ON_CALL_INTERVENTION:
            # Check if on-call was paged
            return incident_data.get("on_call_paged", False) or \
                   incident_data.get("manual_intervention", False)
        
        elif trigger.trigger_type == TriggerType.LONG_RESOLUTION:
            # Check resolution time
            ttr = incident_data.get("time_to_resolve_minutes")
            threshold = trigger.threshold or self.config.resolution_time_threshold_minutes
            return ttr is not None and ttr > threshold
        
        elif trigger.trigger_type == TriggerType.MONITORING_FAILURE:
            # Check if monitoring failed
            return incident_data.get("monitoring_failure", False) or \
                   incident_data.get("detection_delay_minutes", 0) > 15
        
        elif trigger.trigger_type == TriggerType.SECURITY_INCIDENT:
            return incident_data.get("security_incident", False)
        
        elif trigger.trigger_type == TriggerType.REVENUE_IMPACT:
            return incident_data.get("revenue_impact", 0) > 0
        
        elif trigger.trigger_type == TriggerType.MANUAL:
            return incident_data.get("manual_postmortem", False)
        
        return False
    
    def create_postmortem_ticket(
        self,
        incident_id: str,
        title: str,
        triggered_by: list[TriggerType],
        assignee: Optional[str] = None,
    ) -> PostmortemTicket:
        """
        Create a postmortem ticket for tracking.
        
        Args:
            incident_id: Incident identifier
            title: Incident title
            triggered_by: Trigger types that fired
            assignee: Optional assignee
            
        Returns:
            Created ticket
        """
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=self.config.default_due_days)
        
        ticket = PostmortemTicket(
            incident_id=incident_id,
            title=f"Postmortem: {title}",
            triggered_by=triggered_by,
            created_at=now,
            due_date=due_date,
            assignee=assignee,
        )
        
        self._tickets[incident_id] = ticket
        
        # Call external ticket system if configured
        if self.config.auto_create_ticket and self.ticket_callback:
            self.ticket_callback(ticket)
        
        return ticket
    
    def complete_postmortem(
        self,
        incident_id: str,
        postmortem_url: Optional[str] = None,
    ) -> Optional[PostmortemTicket]:
        """
        Mark a postmortem as complete.
        
        Args:
            incident_id: Incident identifier
            postmortem_url: URL to completed postmortem
            
        Returns:
            Updated ticket or None
        """
        ticket = self._tickets.get(incident_id)
        if not ticket:
            return None
        
        ticket.status = "completed"
        ticket.completed_at = datetime.now(timezone.utc)
        ticket.postmortem_url = postmortem_url
        
        return ticket
    
    def get_overdue_postmortems(self) -> list[PostmortemTicket]:
        """Get list of overdue postmortem tickets."""
        now = datetime.now(timezone.utc)
        overdue = []
        
        for ticket in self._tickets.values():
            if ticket.status not in ("completed",) and ticket.due_date < now:
                ticket.status = "overdue"
                overdue.append(ticket)
        
        return overdue
    
    def get_completion_rate(
        self,
        since: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Calculate postmortem completion rate.
        
        Args:
            since: Optional start date filter
            
        Returns:
            Completion statistics
        """
        tickets = list(self._tickets.values())
        
        if since:
            tickets = [t for t in tickets if t.created_at >= since]
        
        if not tickets:
            return {
                "total": 0,
                "completed": 0,
                "open": 0,
                "overdue": 0,
                "completion_rate": 0.0,
            }
        
        now = datetime.now(timezone.utc)
        completed = [t for t in tickets if t.status == "completed"]
        overdue = [t for t in tickets if t.status != "completed" and t.due_date < now]
        open_tickets = [t for t in tickets if t.status not in ("completed",) and t.due_date >= now]
        
        return {
            "total": len(tickets),
            "completed": len(completed),
            "open": len(open_tickets),
            "overdue": len(overdue),
            "completion_rate": len(completed) / len(tickets) if tickets else 0.0,
            "average_completion_days": self._avg_completion_days(completed),
        }
    
    def _avg_completion_days(self, completed: list[PostmortemTicket]) -> Optional[float]:
        """Calculate average completion time in days."""
        if not completed:
            return None
        
        days = []
        for ticket in completed:
            if ticket.completed_at:
                delta = ticket.completed_at - ticket.created_at
                days.append(delta.total_seconds() / 86400)
        
        return sum(days) / len(days) if days else None
    
    def get_ticket(self, incident_id: str) -> Optional[PostmortemTicket]:
        """Get a postmortem ticket by incident ID."""
        return self._tickets.get(incident_id)
    
    def list_tickets(
        self,
        status: Optional[str] = None,
    ) -> list[PostmortemTicket]:
        """
        List all postmortem tickets.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of tickets
        """
        tickets = list(self._tickets.values())
        
        if status:
            tickets = [t for t in tickets if t.status == status]
        
        return sorted(tickets, key=lambda t: t.created_at, reverse=True)


def load_policy_from_yaml(path: str | Path) -> PolicyConfig:
    """
    Load policy configuration from YAML file.
    
    Args:
        path: Path to YAML file
        
    Returns:
        PolicyConfig
    """
    path = Path(path)
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    triggers = []
    for trigger_data in data.get("triggers", []):
        triggers.append(PostmortemTrigger.from_dict(trigger_data))
    
    return PolicyConfig(
        triggers=triggers,
        resolution_time_threshold_minutes=data.get("resolution_time_threshold_minutes", 30),
        default_due_days=data.get("default_due_days", 5),
        require_action_items=data.get("require_action_items", True),
        require_ai_review=data.get("require_ai_review", True),
        auto_create_ticket=data.get("auto_create_ticket", True),
        notify_on_trigger=data.get("notify_on_trigger", True),
        notification_channel=data.get("notification_channel"),
    )


def save_policy_to_yaml(config: PolicyConfig, path: str | Path) -> None:
    """
    Save policy configuration to YAML file.
    
    Args:
        config: Policy configuration
        path: Path to save to
    """
    path = Path(path)
    
    data = {
        "triggers": [t.to_dict() for t in config.triggers],
        "resolution_time_threshold_minutes": config.resolution_time_threshold_minutes,
        "default_due_days": config.default_due_days,
        "require_action_items": config.require_action_items,
        "require_ai_review": config.require_ai_review,
        "auto_create_ticket": config.auto_create_ticket,
        "notify_on_trigger": config.notify_on_trigger,
        "notification_channel": config.notification_channel,
    }
    
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
