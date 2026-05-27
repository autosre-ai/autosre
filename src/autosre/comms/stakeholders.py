"""
Stakeholder Notifications

Provides automated stakeholder notification and escalation management
for incident communications.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field


class StakeholderPriority(str, Enum):
    """Priority level for stakeholder notifications."""
    
    CRITICAL = "critical"  # Page immediately
    HIGH = "high"          # Notify within 5 minutes
    MEDIUM = "medium"      # Notify within 15 minutes
    LOW = "low"            # Notify within 30 minutes
    INFORMATIONAL = "informational"  # Best effort


class NotificationChannel(str, Enum):
    """Communication channels for notifications."""
    
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    VOICE = "voice"
    MOBILE_PUSH = "mobile_push"


class NotificationStatus(str, Enum):
    """Status of a notification."""
    
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.EMAIL, NotificationChannel.SLACK],
        description="Preferred notification channels"
    )
    escalation_channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
        description="Channels for escalations"
    )
    quiet_hours_start: Optional[int] = Field(
        None,
        description="Quiet hours start (0-23 UTC)"
    )
    quiet_hours_end: Optional[int] = Field(
        None,
        description="Quiet hours end (0-23 UTC)"
    )
    respect_quiet_hours: bool = Field(
        default=True,
        description="Whether to respect quiet hours"
    )
    minimum_severity: str = Field(
        default="warning",
        description="Minimum severity to notify"
    )
    digest_frequency: Optional[str] = Field(
        None,
        description="Frequency for digest notifications (hourly, daily)"
    )


class Stakeholder(BaseModel):
    """A stakeholder who receives incident notifications."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Stakeholder ID")
    name: str = Field(..., description="Display name")
    email: str = Field(..., description="Email address")
    role: str = Field(default="engineer", description="Role/title")
    team: Optional[str] = Field(None, description="Team name")
    department: Optional[str] = Field(None, description="Department")
    
    # Contact information
    phone_number: Optional[str] = Field(None, description="Phone number for SMS/voice")
    slack_user_id: Optional[str] = Field(None, description="Slack user ID")
    pagerduty_user_id: Optional[str] = Field(None, description="PagerDuty user ID")
    teams_user_id: Optional[str] = Field(None, description="Microsoft Teams user ID")
    
    # Notification settings
    preferences: NotificationPreferences = Field(
        default_factory=NotificationPreferences,
        description="Notification preferences"
    )
    
    # Scope
    service_ownership: list[str] = Field(
        default_factory=list,
        description="Services owned by this stakeholder"
    )
    notification_scopes: list[str] = Field(
        default_factory=list,
        description="Scopes to receive notifications for"
    )
    
    # Status
    is_active: bool = Field(default=True, description="Whether stakeholder is active")
    on_call: bool = Field(default=False, description="Currently on-call")
    
    def is_in_quiet_hours(self) -> bool:
        """Check if stakeholder is in quiet hours."""
        if not self.preferences.respect_quiet_hours:
            return False
        if self.preferences.quiet_hours_start is None or self.preferences.quiet_hours_end is None:
            return False
        
        current_hour = datetime.now(timezone.utc).hour
        start = self.preferences.quiet_hours_start
        end = self.preferences.quiet_hours_end
        
        if start <= end:
            return start <= current_hour < end
        else:
            # Wraps around midnight
            return current_hour >= start or current_hour < end


class StakeholderGroup(BaseModel):
    """A group of stakeholders."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Group ID")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    stakeholders: list[str] = Field(
        default_factory=list,
        description="Stakeholder IDs in this group"
    )
    
    # Group settings
    notify_all: bool = Field(
        default=True,
        description="Notify all members or just on-call"
    )
    escalation_group: bool = Field(
        default=False,
        description="Whether this is an escalation group"
    )
    notification_delay_minutes: int = Field(
        default=0,
        description="Delay before notifying this group"
    )
    
    # Scope
    services: list[str] = Field(
        default_factory=list,
        description="Services this group is responsible for"
    )
    severities: list[str] = Field(
        default_factory=lambda: ["critical", "high", "warning"],
        description="Severities to notify for"
    )


class EscalationLevel(BaseModel):
    """An escalation level configuration."""
    
    level: int = Field(..., description="Escalation level (1, 2, 3, etc.)")
    name: str = Field(..., description="Level name")
    stakeholder_groups: list[str] = Field(
        default_factory=list,
        description="Stakeholder group IDs at this level"
    )
    timeout_minutes: int = Field(
        default=15,
        description="Minutes before escalating to next level"
    )
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.PAGERDUTY],
        description="Notification channels for this level"
    )
    require_acknowledgment: bool = Field(
        default=True,
        description="Require acknowledgment before escalating"
    )


class EscalationRule(BaseModel):
    """A rule for when to escalate."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Rule ID")
    name: str = Field(..., description="Rule name")
    condition: str = Field(..., description="Condition expression")
    target_level: int = Field(..., description="Target escalation level")
    auto_escalate: bool = Field(
        default=True,
        description="Automatically escalate when condition is met"
    )


class EscalationPolicy(BaseModel):
    """An escalation policy."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Policy ID")
    name: str = Field(..., description="Policy name")
    description: Optional[str] = Field(None, description="Policy description")
    
    # Escalation configuration
    levels: list[EscalationLevel] = Field(
        default_factory=list,
        description="Escalation levels"
    )
    rules: list[EscalationRule] = Field(
        default_factory=list,
        description="Escalation rules"
    )
    
    # Scope
    services: list[str] = Field(
        default_factory=list,
        description="Services this policy applies to"
    )
    severities: list[str] = Field(
        default_factory=lambda: ["critical", "high"],
        description="Severities this policy applies to"
    )
    
    # Settings
    start_level: int = Field(default=1, description="Starting escalation level")
    max_escalations: int = Field(
        default=5,
        description="Maximum number of escalations"
    )
    loop_after_max: bool = Field(
        default=True,
        description="Loop back to level 1 after max"
    )
    
    def get_level(self, level_num: int) -> Optional[EscalationLevel]:
        """Get escalation level by number."""
        for level in self.levels:
            if level.level == level_num:
                return level
        return None
    
    def get_next_level(self, current_level: int) -> Optional[EscalationLevel]:
        """Get the next escalation level."""
        next_num = current_level + 1
        level = self.get_level(next_num)
        
        if level:
            return level
        
        if self.loop_after_max and current_level >= self.max_escalations:
            return self.get_level(1)
        
        return None


class NotificationResult(BaseModel):
    """Result of a notification attempt."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Result ID")
    notification_id: str = Field(..., description="Notification ID")
    stakeholder_id: str = Field(..., description="Stakeholder ID")
    channel: NotificationChannel = Field(..., description="Channel used")
    status: NotificationStatus = Field(
        default=NotificationStatus.PENDING,
        description="Notification status"
    )
    
    # Timing
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")
    delivered_at: Optional[datetime] = Field(None, description="Delivery timestamp")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgment timestamp")
    
    # Response
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retries: int = Field(default=0, description="Number of retry attempts")
    
    # External references
    external_id: Optional[str] = Field(
        None,
        description="External system message ID"
    )


class StakeholderNotifier:
    """Manages stakeholder notifications and escalations.
    
    Handles multi-channel notification delivery, escalation policies,
    and notification tracking.
    
    Example:
        notifier = StakeholderNotifier()
        
        # Add stakeholders
        notifier.add_stakeholder(Stakeholder(
            name="Jane Engineer",
            email="jane@example.com",
            slack_user_id="U12345",
            service_ownership=["payment-api"],
        ))
        
        # Create group
        notifier.add_group(StakeholderGroup(
            name="Payment Team",
            stakeholders=["stakeholder-id"],
            services=["payment-api"],
        ))
        
        # Add escalation policy
        notifier.add_escalation_policy(EscalationPolicy(
            name="Payment Service Critical",
            levels=[
                EscalationLevel(level=1, name="On-Call", timeout_minutes=5),
                EscalationLevel(level=2, name="Team Lead", timeout_minutes=10),
                EscalationLevel(level=3, name="Engineering Manager", timeout_minutes=15),
            ],
            services=["payment-api"],
            severities=["critical"],
        ))
        
        # Send notification
        results = await notifier.notify(
            incident_id="inc-123",
            title="Payment API Down",
            message="Payment API is experiencing 100% error rate",
            severity="critical",
            affected_services=["payment-api"],
        )
        
        # Escalate if needed
        await notifier.escalate(
            incident_id="inc-123",
            reason="No acknowledgment within 5 minutes",
        )
    """
    
    def __init__(
        self,
        slack_client: Optional[Any] = None,
        email_client: Optional[Any] = None,
        sms_client: Optional[Any] = None,
        pagerduty_client: Optional[Any] = None,
    ) -> None:
        """Initialize the stakeholder notifier.
        
        Args:
            slack_client: Slack API client
            email_client: Email sending client
            sms_client: SMS sending client
            pagerduty_client: PagerDuty API client
        """
        self.slack_client = slack_client
        self.email_client = email_client
        self.sms_client = sms_client
        self.pagerduty_client = pagerduty_client
        
        self._stakeholders: dict[str, Stakeholder] = {}
        self._groups: dict[str, StakeholderGroup] = {}
        self._policies: dict[str, EscalationPolicy] = {}
        self._notifications: dict[str, list[NotificationResult]] = {}
        self._escalation_state: dict[str, int] = {}  # incident_id -> current_level
    
    def add_stakeholder(self, stakeholder: Stakeholder) -> None:
        """Add a stakeholder.
        
        Args:
            stakeholder: Stakeholder to add
        """
        self._stakeholders[stakeholder.id] = stakeholder
    
    def remove_stakeholder(self, stakeholder_id: str) -> None:
        """Remove a stakeholder.
        
        Args:
            stakeholder_id: Stakeholder ID
        """
        self._stakeholders.pop(stakeholder_id, None)
    
    def get_stakeholder(self, stakeholder_id: str) -> Optional[Stakeholder]:
        """Get a stakeholder by ID.
        
        Args:
            stakeholder_id: Stakeholder ID
            
        Returns:
            Stakeholder if found
        """
        return self._stakeholders.get(stakeholder_id)
    
    def add_group(self, group: StakeholderGroup) -> None:
        """Add a stakeholder group.
        
        Args:
            group: Group to add
        """
        self._groups[group.id] = group
    
    def get_group(self, group_id: str) -> Optional[StakeholderGroup]:
        """Get a group by ID.
        
        Args:
            group_id: Group ID
            
        Returns:
            Group if found
        """
        return self._groups.get(group_id)
    
    def add_escalation_policy(self, policy: EscalationPolicy) -> None:
        """Add an escalation policy.
        
        Args:
            policy: Policy to add
        """
        self._policies[policy.id] = policy
    
    def get_escalation_policy(self, policy_id: str) -> Optional[EscalationPolicy]:
        """Get an escalation policy by ID.
        
        Args:
            policy_id: Policy ID
            
        Returns:
            Policy if found
        """
        return self._policies.get(policy_id)
    
    def find_policy_for_incident(
        self,
        affected_services: list[str],
        severity: str,
    ) -> Optional[EscalationPolicy]:
        """Find the appropriate escalation policy for an incident.
        
        Args:
            affected_services: Affected service names
            severity: Incident severity
            
        Returns:
            Matching policy if found
        """
        for policy in self._policies.values():
            # Check severity match
            if severity.lower() not in policy.severities:
                continue
            
            # Check service match
            if policy.services:
                if any(svc in policy.services for svc in affected_services):
                    return policy
            else:
                # Policy applies to all services
                return policy
        
        return None
    
    def find_stakeholders_for_incident(
        self,
        affected_services: list[str],
        severity: str,
    ) -> list[Stakeholder]:
        """Find stakeholders to notify for an incident.
        
        Args:
            affected_services: Affected service names
            severity: Incident severity
            
        Returns:
            List of stakeholders to notify
        """
        stakeholders = []
        
        # Find by service ownership
        for stakeholder in self._stakeholders.values():
            if not stakeholder.is_active:
                continue
            
            # Check service ownership
            for service in affected_services:
                if service in stakeholder.service_ownership:
                    stakeholders.append(stakeholder)
                    break
        
        # Find by groups
        for group in self._groups.values():
            # Check service match
            if group.services:
                if not any(svc in group.services for svc in affected_services):
                    continue
            
            # Check severity match
            if severity.lower() not in group.severities:
                continue
            
            # Add group members
            for stakeholder_id in group.stakeholders:
                stakeholder = self._stakeholders.get(stakeholder_id)
                if stakeholder and stakeholder.is_active and stakeholder not in stakeholders:
                    if group.notify_all or stakeholder.on_call:
                        stakeholders.append(stakeholder)
        
        return stakeholders
    
    async def notify(
        self,
        incident_id: str,
        title: str,
        message: str,
        severity: str,
        affected_services: list[str],
        priority: StakeholderPriority = StakeholderPriority.HIGH,
        stakeholder_ids: Optional[list[str]] = None,
        channels: Optional[list[NotificationChannel]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[NotificationResult]:
        """Send notifications to stakeholders.
        
        Args:
            incident_id: Incident identifier
            title: Notification title
            message: Notification message
            severity: Incident severity
            affected_services: Affected service names
            priority: Notification priority
            stakeholder_ids: Specific stakeholders to notify (or auto-find)
            channels: Override notification channels
            metadata: Additional notification data
            
        Returns:
            List of notification results
        """
        results = []
        notification_id = str(uuid.uuid4())
        
        # Determine stakeholders
        if stakeholder_ids:
            stakeholders = [
                self._stakeholders[sid]
                for sid in stakeholder_ids
                if sid in self._stakeholders
            ]
        else:
            stakeholders = self.find_stakeholders_for_incident(affected_services, severity)
        
        # Send notifications
        for stakeholder in stakeholders:
            # Determine channels
            notify_channels = channels or stakeholder.preferences.channels
            
            # Skip if in quiet hours (unless critical)
            if (stakeholder.is_in_quiet_hours() and 
                priority not in [StakeholderPriority.CRITICAL]):
                # Use escalation channels for quiet hours
                notify_channels = stakeholder.preferences.escalation_channels
            
            for channel in notify_channels:
                result = await self._send_notification(
                    notification_id=notification_id,
                    stakeholder=stakeholder,
                    channel=channel,
                    title=title,
                    message=message,
                    severity=severity,
                    incident_id=incident_id,
                    priority=priority,
                    metadata=metadata,
                )
                results.append(result)
        
        # Store notification results
        if incident_id not in self._notifications:
            self._notifications[incident_id] = []
        self._notifications[incident_id].extend(results)
        
        return results
    
    async def _send_notification(
        self,
        notification_id: str,
        stakeholder: Stakeholder,
        channel: NotificationChannel,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
        priority: StakeholderPriority,
        metadata: Optional[dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a single notification.
        
        Args:
            notification_id: Notification ID
            stakeholder: Stakeholder to notify
            channel: Channel to use
            title: Notification title
            message: Notification message
            severity: Incident severity
            incident_id: Incident ID
            priority: Notification priority
            metadata: Additional data
            
        Returns:
            Notification result
        """
        result = NotificationResult(
            notification_id=notification_id,
            stakeholder_id=stakeholder.id,
            channel=channel,
        )
        
        try:
            if channel == NotificationChannel.SLACK:
                await self._send_slack(stakeholder, title, message, severity, incident_id)
            elif channel == NotificationChannel.EMAIL:
                await self._send_email(stakeholder, title, message, severity, incident_id)
            elif channel == NotificationChannel.SMS:
                await self._send_sms(stakeholder, title, message, severity, incident_id)
            elif channel == NotificationChannel.PAGERDUTY:
                await self._send_pagerduty(stakeholder, title, message, severity, incident_id, priority)
            elif channel == NotificationChannel.WEBHOOK:
                await self._send_webhook(stakeholder, title, message, severity, incident_id, metadata)
            
            result.status = NotificationStatus.SENT
            result.sent_at = datetime.now(timezone.utc)
        except Exception as e:
            result.status = NotificationStatus.FAILED
            result.error_message = str(e)
        
        return result
    
    async def _send_slack(
        self,
        stakeholder: Stakeholder,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
    ) -> None:
        """Send Slack notification."""
        if not self.slack_client:
            return
        
        # Color based on severity
        colors = {
            "critical": "#FF0000",
            "high": "#FF9900",
            "warning": "#FFCC00",
            "low": "#00CC00",
        }
        color = colors.get(severity.lower(), "#808080")
        
        # Build message
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 {title}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Severity:* {severity} | *Incident:* {incident_id}"}
                ]
            }
        ]
        
        # Send DM (would use actual Slack API)
        # await self.slack_client.chat_postMessage(
        #     channel=stakeholder.slack_user_id,
        #     blocks=blocks,
        #     attachments=[{"color": color}]
        # )
    
    async def _send_email(
        self,
        stakeholder: Stakeholder,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
    ) -> None:
        """Send email notification."""
        if not self.email_client:
            return
        
        # Would use actual email client
        # await self.email_client.send(
        #     to=stakeholder.email,
        #     subject=f"[{severity.upper()}] {title} - {incident_id}",
        #     body=message,
        # )
    
    async def _send_sms(
        self,
        stakeholder: Stakeholder,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
    ) -> None:
        """Send SMS notification."""
        if not self.sms_client or not stakeholder.phone_number:
            return
        
        # Truncate for SMS
        sms_message = f"[{severity.upper()}] {title}: {message[:100]}..."
        
        # Would use actual SMS client
        # await self.sms_client.send(
        #     to=stakeholder.phone_number,
        #     message=sms_message,
        # )
    
    async def _send_pagerduty(
        self,
        stakeholder: Stakeholder,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
        priority: StakeholderPriority,
    ) -> None:
        """Send PagerDuty notification."""
        if not self.pagerduty_client or not stakeholder.pagerduty_user_id:
            return
        
        # Map priority to PagerDuty urgency
        urgency = "high" if priority in [StakeholderPriority.CRITICAL, StakeholderPriority.HIGH] else "low"
        
        # Would use actual PagerDuty API
        # await self.pagerduty_client.create_incident(
        #     title=title,
        #     description=message,
        #     urgency=urgency,
        #     user_id=stakeholder.pagerduty_user_id,
        # )
    
    async def _send_webhook(
        self,
        stakeholder: Stakeholder,
        title: str,
        message: str,
        severity: str,
        incident_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send webhook notification."""
        # Would send HTTP POST to configured webhook URL
        pass
    
    async def escalate(
        self,
        incident_id: str,
        title: str,
        message: str,
        severity: str,
        affected_services: list[str],
        reason: Optional[str] = None,
    ) -> list[NotificationResult]:
        """Escalate notifications to the next level.
        
        Args:
            incident_id: Incident ID
            title: Notification title
            message: Notification message
            severity: Incident severity
            affected_services: Affected services
            reason: Escalation reason
            
        Returns:
            Notification results from escalation
        """
        # Find policy
        policy = self.find_policy_for_incident(affected_services, severity)
        if not policy:
            return []
        
        # Get current level
        current_level = self._escalation_state.get(incident_id, 0)
        
        # Get next level
        next_level = policy.get_next_level(current_level)
        if not next_level:
            return []
        
        # Update escalation state
        self._escalation_state[incident_id] = next_level.level
        
        # Get stakeholders at this level
        stakeholder_ids = []
        for group_id in next_level.stakeholder_groups:
            group = self._groups.get(group_id)
            if group:
                stakeholder_ids.extend(group.stakeholders)
        
        # Build escalation message
        escalation_message = f"[ESCALATION L{next_level.level}] {message}"
        if reason:
            escalation_message += f"\n\nEscalation reason: {reason}"
        
        # Send notifications
        results = await self.notify(
            incident_id=incident_id,
            title=f"[Escalation L{next_level.level}] {title}",
            message=escalation_message,
            severity=severity,
            affected_services=affected_services,
            priority=StakeholderPriority.CRITICAL,
            stakeholder_ids=stakeholder_ids,
            channels=next_level.channels,
            metadata={"escalation_level": next_level.level, "reason": reason},
        )
        
        return results
    
    async def acknowledge(
        self,
        incident_id: str,
        stakeholder_id: str,
    ) -> None:
        """Record acknowledgment from a stakeholder.
        
        Args:
            incident_id: Incident ID
            stakeholder_id: Stakeholder who acknowledged
        """
        if incident_id in self._notifications:
            for result in self._notifications[incident_id]:
                if result.stakeholder_id == stakeholder_id:
                    result.status = NotificationStatus.ACKNOWLEDGED
                    result.acknowledged_at = datetime.now(timezone.utc)
    
    def get_notification_results(self, incident_id: str) -> list[NotificationResult]:
        """Get notification results for an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            List of notification results
        """
        return self._notifications.get(incident_id, [])
    
    def get_unacknowledged_notifications(self, incident_id: str) -> list[NotificationResult]:
        """Get unacknowledged notifications for an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            List of unacknowledged notification results
        """
        results = self._notifications.get(incident_id, [])
        return [
            r for r in results
            if r.status not in [NotificationStatus.ACKNOWLEDGED, NotificationStatus.FAILED]
        ]
    
    def get_escalation_level(self, incident_id: str) -> int:
        """Get current escalation level for an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            Current escalation level (0 if not escalated)
        """
        return self._escalation_state.get(incident_id, 0)


# Pre-built escalation policies
DEFAULT_CRITICAL_POLICY = EscalationPolicy(
    name="Critical Incident Default",
    description="Default escalation policy for critical incidents",
    levels=[
        EscalationLevel(
            level=1,
            name="Primary On-Call",
            timeout_minutes=5,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
        ),
        EscalationLevel(
            level=2,
            name="Secondary On-Call",
            timeout_minutes=10,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
        ),
        EscalationLevel(
            level=3,
            name="Team Lead",
            timeout_minutes=15,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.VOICE],
        ),
        EscalationLevel(
            level=4,
            name="Engineering Manager",
            timeout_minutes=20,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.VOICE],
        ),
        EscalationLevel(
            level=5,
            name="VP Engineering",
            timeout_minutes=30,
            channels=[NotificationChannel.VOICE],
        ),
    ],
    severities=["critical"],
    max_escalations=5,
    loop_after_max=True,
)

DEFAULT_HIGH_POLICY = EscalationPolicy(
    name="High Severity Default",
    description="Default escalation policy for high severity incidents",
    levels=[
        EscalationLevel(
            level=1,
            name="Primary On-Call",
            timeout_minutes=10,
            channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL],
        ),
        EscalationLevel(
            level=2,
            name="Secondary On-Call",
            timeout_minutes=15,
            channels=[NotificationChannel.PAGERDUTY],
        ),
        EscalationLevel(
            level=3,
            name="Team Lead",
            timeout_minutes=30,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
        ),
    ],
    severities=["high"],
    max_escalations=3,
)
