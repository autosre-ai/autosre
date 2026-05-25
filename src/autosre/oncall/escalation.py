"""
Escalation Policy Management for AutoSRE.

Provides escalation policy capabilities including:
- Multi-level escalation chains
- Time-based escalation
- Acknowledgment tracking
- Notification channel routing
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable
import json
from collections import defaultdict

from pydantic import BaseModel, Field


class EscalationTrigger(str, Enum):
    """Events that trigger escalation."""
    
    NO_ACK = "no_ack"                 # No acknowledgment within timeout
    NO_RESOLUTION = "no_resolution"   # Not resolved within timeout
    SEVERITY_UPGRADE = "severity_upgrade"  # Severity increased
    MANUAL = "manual"                 # Manually triggered
    AUTO_DETECT = "auto_detect"       # System detected issue
    OVERLOAD = "overload"             # On-call is overloaded
    REPEATED = "repeated"             # Same issue recurring


class NotificationMethod(str, Enum):
    """Methods for sending notifications."""
    
    EMAIL = "email"
    SMS = "sms"
    PHONE_CALL = "phone_call"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    PUSH = "push"


class EscalationStatus(str, Enum):
    """Status of an escalation."""
    
    PENDING = "pending"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    TIMED_OUT = "timed_out"
    ESCALATED = "escalated"


class TargetType(str, Enum):
    """Types of escalation targets."""
    
    USER = "user"
    SCHEDULE = "schedule"
    ROTATION = "rotation"
    GROUP = "group"


class NotificationTarget(BaseModel):
    """Target for notifications."""
    
    target_type: TargetType
    target_id: str
    target_name: str = ""
    methods: list[NotificationMethod] = Field(
        default_factory=lambda: [NotificationMethod.EMAIL]
    )
    
    # Contact info (for direct user targets)
    email: Optional[str] = None
    phone: Optional[str] = None
    slack_id: Optional[str] = None
    
    def get_contact(self, method: NotificationMethod) -> Optional[str]:
        """Get contact info for a specific method."""
        if method == NotificationMethod.EMAIL:
            return self.email
        elif method in (NotificationMethod.SMS, NotificationMethod.PHONE_CALL):
            return self.phone
        elif method == NotificationMethod.SLACK:
            return self.slack_id
        return None


class EscalationLevel(BaseModel):
    """A level in an escalation policy."""
    
    level: int = Field(ge=1)
    name: str = ""
    
    # Targets at this level
    targets: list[NotificationTarget] = Field(default_factory=list)
    
    # Timing
    timeout_minutes: int = Field(default=15, ge=1)
    repeat_interval_minutes: int = Field(default=5, ge=1)
    max_repeats: int = Field(default=3, ge=1)
    
    # Notification settings
    methods: list[NotificationMethod] = Field(
        default_factory=lambda: [NotificationMethod.EMAIL, NotificationMethod.SLACK]
    )
    notify_all_at_once: bool = False  # Notify all targets at once vs sequentially
    
    # Requirements
    require_ack: bool = True
    ack_timeout_minutes: int = Field(default=5, ge=1)


class EscalationPolicy(BaseModel):
    """Complete escalation policy configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    team_id: str = ""
    
    # Policy levels
    levels: list[EscalationLevel] = Field(default_factory=list)
    
    # Configuration
    is_active: bool = True
    repeat_policy: bool = True  # Repeat from beginning if all levels exhausted
    max_total_escalations: int = Field(default=10, ge=1)
    
    # Severity-based timeouts
    severity_timeouts: dict[str, int] = Field(
        default_factory=lambda: {
            "critical": 5,
            "high": 15,
            "medium": 30,
            "low": 60,
        }
    )
    
    # Auto-escalation conditions
    auto_escalate_on_overload: bool = True
    auto_escalate_on_repeated_incident: bool = True
    repeated_incident_threshold: int = Field(default=3)
    
    # Hooks
    on_escalation_webhook: Optional[str] = None
    on_resolution_webhook: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add_level(
        self,
        targets: list[NotificationTarget],
        timeout_minutes: int = 15,
        methods: Optional[list[NotificationMethod]] = None,
        name: str = "",
    ) -> EscalationLevel:
        """Add a level to the policy."""
        level_num = len(self.levels) + 1
        
        level = EscalationLevel(
            level=level_num,
            name=name or f"Level {level_num}",
            targets=targets,
            timeout_minutes=timeout_minutes,
            methods=methods or [NotificationMethod.EMAIL, NotificationMethod.SLACK],
        )
        
        self.levels.append(level)
        self.updated_at = datetime.utcnow()
        return level
    
    def get_level(self, level_num: int) -> Optional[EscalationLevel]:
        """Get a specific level."""
        for level in self.levels:
            if level.level == level_num:
                return level
        return None
    
    def get_timeout_for_severity(self, severity: str) -> int:
        """Get timeout minutes for a severity level."""
        return self.severity_timeouts.get(
            severity.lower(),
            self.severity_timeouts.get("medium", 30)
        )


@dataclass
class EscalationEvent:
    """Record of an escalation event."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    policy_id: str = ""
    
    # Level info
    level: int = 1
    target: str = ""
    target_type: TargetType = TargetType.USER
    
    # Status
    status: EscalationStatus = EscalationStatus.PENDING
    trigger: EscalationTrigger = EscalationTrigger.NO_ACK
    
    # Timing
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notified_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    # Notification tracking
    notification_method: NotificationMethod = NotificationMethod.EMAIL
    notification_attempts: int = 0
    last_notification_at: Optional[datetime] = None
    
    # Notes
    notes: str = ""
    
    def acknowledge(self, by: str) -> None:
        """Acknowledge this escalation."""
        self.status = EscalationStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc)
        self.acknowledged_by = by
    
    def resolve(self) -> None:
        """Mark as resolved."""
        self.status = EscalationStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "policy_id": self.policy_id,
            "level": self.level,
            "target": self.target,
            "target_type": self.target_type.value,
            "status": self.status.value,
            "trigger": self.trigger.value,
            "triggered_at": self.triggered_at.isoformat(),
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notification_method": self.notification_method.value,
            "notification_attempts": self.notification_attempts,
            "notes": self.notes,
        }


class ActiveEscalation(BaseModel):
    """An active escalation in progress."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    policy_id: str
    
    # Current state
    current_level: int = Field(default=1)
    current_target_index: int = Field(default=0)
    status: EscalationStatus = EscalationStatus.PENDING
    
    # Tracking
    total_escalations: int = Field(default=0)
    events: list[dict] = Field(default_factory=list)  # EscalationEvent as dict
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_escalation_at: Optional[datetime] = None
    last_notification_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None
    
    # Incident info
    severity: str = "medium"
    title: str = ""
    
    def is_timed_out(self) -> bool:
        """Check if current level has timed out."""
        if not self.timeout_at:
            return False
        return datetime.now(timezone.utc) > self.timeout_at
    
    def add_event(self, event: EscalationEvent) -> None:
        """Add an escalation event."""
        self.events.append(event.to_dict())
        self.total_escalations += 1
        self.last_escalation_at = event.triggered_at


class EscalationEngine:
    """Engine for managing escalations."""
    
    def __init__(self):
        """Initialize the escalation engine."""
        self._policies: dict[str, EscalationPolicy] = {}
        self._active: dict[str, ActiveEscalation] = {}  # incident_id -> escalation
        self._history: dict[str, list[EscalationEvent]] = defaultdict(list)
        
        # Notification callback (to be set by integrations)
        self._notify_callback: Optional[Callable] = None
    
    def set_notification_callback(
        self,
        callback: Callable[[NotificationTarget, NotificationMethod, dict], bool],
    ) -> None:
        """Set the notification callback function."""
        self._notify_callback = callback
    
    def create_policy(
        self,
        name: str,
        team_id: str = "",
        **kwargs: Any,
    ) -> EscalationPolicy:
        """Create a new escalation policy."""
        policy = EscalationPolicy(
            name=name,
            team_id=team_id,
            **kwargs,
        )
        self._policies[policy.id] = policy
        return policy
    
    def get_policy(self, policy_id: str) -> Optional[EscalationPolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)
    
    def get_policies_for_team(self, team_id: str) -> list[EscalationPolicy]:
        """Get all policies for a team."""
        return [p for p in self._policies.values() if p.team_id == team_id]
    
    def trigger_escalation(
        self,
        incident_id: str,
        policy_id: str,
        severity: str = "medium",
        title: str = "",
        trigger: EscalationTrigger = EscalationTrigger.NO_ACK,
    ) -> Optional[ActiveEscalation]:
        """
        Trigger an escalation for an incident.
        
        Args:
            incident_id: Unique incident identifier
            policy_id: Escalation policy to use
            severity: Incident severity
            title: Incident title
            trigger: What triggered this escalation
            
        Returns:
            Active escalation object
        """
        policy = self.get_policy(policy_id)
        if not policy or not policy.is_active:
            return None
        
        # Check if there's already an active escalation
        if incident_id in self._active:
            return self._active[incident_id]
        
        # Calculate initial timeout
        timeout_minutes = policy.get_timeout_for_severity(severity)
        timeout_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
        
        # Create active escalation
        escalation = ActiveEscalation(
            incident_id=incident_id,
            policy_id=policy_id,
            severity=severity,
            title=title,
            timeout_at=timeout_at,
        )
        
        self._active[incident_id] = escalation
        
        # Process first level
        self._process_level(escalation, policy, trigger)
        
        return escalation
    
    def acknowledge(
        self,
        incident_id: str,
        by: str,
    ) -> bool:
        """
        Acknowledge an escalation.
        
        Args:
            incident_id: Incident being acknowledged
            by: User acknowledging
            
        Returns:
            True if acknowledged successfully
        """
        escalation = self._active.get(incident_id)
        if not escalation:
            return False
        
        escalation.status = EscalationStatus.ACKNOWLEDGED
        
        # Create acknowledgment event
        event = EscalationEvent(
            incident_id=incident_id,
            policy_id=escalation.policy_id,
            level=escalation.current_level,
            target=by,
            status=EscalationStatus.ACKNOWLEDGED,
        )
        event.acknowledge(by)
        
        escalation.add_event(event)
        self._history[incident_id].append(event)
        
        return True
    
    def resolve(self, incident_id: str) -> bool:
        """
        Resolve an escalation.
        
        Args:
            incident_id: Incident being resolved
            
        Returns:
            True if resolved successfully
        """
        escalation = self._active.get(incident_id)
        if not escalation:
            return False
        
        escalation.status = EscalationStatus.RESOLVED
        
        # Create resolution event
        event = EscalationEvent(
            incident_id=incident_id,
            policy_id=escalation.policy_id,
            level=escalation.current_level,
            status=EscalationStatus.RESOLVED,
        )
        event.resolve()
        
        escalation.add_event(event)
        self._history[incident_id].append(event)
        
        # Remove from active
        del self._active[incident_id]
        
        return True
    
    def escalate_to_next_level(
        self,
        incident_id: str,
        trigger: EscalationTrigger = EscalationTrigger.NO_ACK,
    ) -> Optional[EscalationLevel]:
        """
        Escalate to the next level.
        
        Args:
            incident_id: Incident to escalate
            trigger: What triggered the escalation
            
        Returns:
            Next escalation level or None
        """
        escalation = self._active.get(incident_id)
        if not escalation:
            return None
        
        policy = self.get_policy(escalation.policy_id)
        if not policy:
            return None
        
        # Mark current level as timed out
        escalation.status = EscalationStatus.TIMED_OUT
        
        # Create timeout event
        timeout_event = EscalationEvent(
            incident_id=incident_id,
            policy_id=policy.id,
            level=escalation.current_level,
            status=EscalationStatus.TIMED_OUT,
            trigger=trigger,
        )
        escalation.add_event(timeout_event)
        self._history[incident_id].append(timeout_event)
        
        # Check if we can escalate further
        if escalation.current_level >= len(policy.levels):
            if policy.repeat_policy:
                # Repeat from beginning
                escalation.current_level = 0
            else:
                # No more levels
                return None
        
        # Check total escalation limit
        if escalation.total_escalations >= policy.max_total_escalations:
            return None
        
        # Move to next level
        escalation.current_level += 1
        escalation.current_target_index = 0
        escalation.status = EscalationStatus.PENDING
        
        # Update timeout
        next_level = policy.get_level(escalation.current_level)
        if next_level:
            escalation.timeout_at = datetime.now(timezone.utc) + timedelta(
                minutes=next_level.timeout_minutes
            )
            
            # Process the new level
            self._process_level(escalation, policy, trigger)
        
        return next_level
    
    def _process_level(
        self,
        escalation: ActiveEscalation,
        policy: EscalationPolicy,
        trigger: EscalationTrigger,
    ) -> None:
        """Process notifications for current level."""
        level = policy.get_level(escalation.current_level)
        if not level:
            return
        
        # Get targets to notify
        targets = level.targets
        
        if level.notify_all_at_once:
            # Notify all targets
            for target in targets:
                self._notify_target(escalation, level, target, trigger)
        else:
            # Notify next target in sequence
            if escalation.current_target_index < len(targets):
                target = targets[escalation.current_target_index]
                self._notify_target(escalation, level, target, trigger)
    
    def _notify_target(
        self,
        escalation: ActiveEscalation,
        level: EscalationLevel,
        target: NotificationTarget,
        trigger: EscalationTrigger,
    ) -> None:
        """Send notification to a target."""
        for method in level.methods:
            if method not in target.methods:
                continue
            
            # Create event
            event = EscalationEvent(
                incident_id=escalation.incident_id,
                policy_id=escalation.policy_id,
                level=level.level,
                target=target.target_id,
                target_type=target.target_type,
                status=EscalationStatus.NOTIFIED,
                trigger=trigger,
                notification_method=method,
            )
            event.notified_at = datetime.now(timezone.utc)
            event.notification_attempts = 1
            
            # Call notification callback if set
            if self._notify_callback:
                notification_data = {
                    "incident_id": escalation.incident_id,
                    "title": escalation.title,
                    "severity": escalation.severity,
                    "level": level.level,
                    "trigger": trigger.value,
                }
                
                try:
                    self._notify_callback(target, method, notification_data)
                except Exception:
                    event.status = EscalationStatus.PENDING
            
            escalation.add_event(event)
            self._history[escalation.incident_id].append(event)
    
    def check_timeouts(self) -> list[str]:
        """
        Check for timed out escalations and escalate them.
        
        Returns:
            List of incident IDs that were escalated
        """
        escalated = []
        
        for incident_id, escalation in list(self._active.items()):
            if escalation.status == EscalationStatus.ACKNOWLEDGED:
                continue
            
            if escalation.is_timed_out():
                result = self.escalate_to_next_level(
                    incident_id,
                    EscalationTrigger.NO_ACK,
                )
                if result:
                    escalated.append(incident_id)
        
        return escalated
    
    def get_active_escalations(
        self,
        policy_id: Optional[str] = None,
    ) -> list[ActiveEscalation]:
        """Get all active escalations, optionally filtered by policy."""
        escalations = list(self._active.values())
        
        if policy_id:
            escalations = [e for e in escalations if e.policy_id == policy_id]
        
        return escalations
    
    def get_escalation_history(
        self,
        incident_id: str,
    ) -> list[EscalationEvent]:
        """Get escalation history for an incident."""
        return self._history.get(incident_id, [])
    
    def get_escalation_metrics(
        self,
        policy_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get escalation metrics.
        
        Args:
            policy_id: Filter by policy
            since: Only include events since this time
            
        Returns:
            Metrics summary
        """
        since = since or datetime.now(timezone.utc) - timedelta(days=30)
        
        events = []
        for incident_events in self._history.values():
            for event in incident_events:
                if event.triggered_at >= since:
                    if not policy_id or event.policy_id == policy_id:
                        events.append(event)
        
        if not events:
            return {
                "total_escalations": 0,
                "by_level": {},
                "by_trigger": {},
                "ack_times": [],
                "average_ack_time_minutes": None,
            }
        
        by_level = defaultdict(int)
        by_trigger = defaultdict(int)
        ack_times = []
        
        for event in events:
            by_level[event.level] += 1
            by_trigger[event.trigger.value] += 1
            
            if event.acknowledged_at and event.triggered_at:
                ack_time = (event.acknowledged_at - event.triggered_at).total_seconds() / 60
                ack_times.append(ack_time)
        
        avg_ack_time = sum(ack_times) / len(ack_times) if ack_times else None
        
        return {
            "total_escalations": len(events),
            "by_level": dict(by_level),
            "by_trigger": dict(by_trigger),
            "average_ack_time_minutes": round(avg_ack_time, 2) if avg_ack_time else None,
            "incidents_escalated": len(set(e.incident_id for e in events)),
            "since": since.isoformat(),
        }


# Convenience functions
def create_simple_policy(
    name: str,
    users: list[dict[str, str]],
    timeout_minutes: int = 15,
) -> EscalationPolicy:
    """
    Create a simple single-level escalation policy.
    
    Args:
        name: Policy name
        users: List of user dicts with user_id, name, email
        timeout_minutes: Minutes before escalating
        
    Returns:
        Configured policy
    """
    policy = EscalationPolicy(name=name)
    
    targets = [
        NotificationTarget(
            target_type=TargetType.USER,
            target_id=user["user_id"],
            target_name=user.get("name", ""),
            email=user.get("email"),
        )
        for user in users
    ]
    
    policy.add_level(
        targets=targets,
        timeout_minutes=timeout_minutes,
    )
    
    return policy


def create_tiered_policy(
    name: str,
    levels: list[dict[str, Any]],
) -> EscalationPolicy:
    """
    Create a multi-level escalation policy.
    
    Args:
        name: Policy name
        levels: List of level configs with users, timeout_minutes, methods
        
    Returns:
        Configured policy
    """
    policy = EscalationPolicy(name=name)
    
    for level_config in levels:
        users = level_config.get("users", [])
        targets = [
            NotificationTarget(
                target_type=TargetType.USER,
                target_id=user["user_id"],
                target_name=user.get("name", ""),
                email=user.get("email"),
                phone=user.get("phone"),
            )
            for user in users
        ]
        
        methods = [
            NotificationMethod(m) for m in level_config.get("methods", ["email"])
        ]
        
        policy.add_level(
            targets=targets,
            timeout_minutes=level_config.get("timeout_minutes", 15),
            methods=methods,
            name=level_config.get("name", ""),
        )
    
    return policy
