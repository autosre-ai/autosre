"""Escalation Engine for AutoSRE V2 Notifications.

Provides escalation policy management:
- Multi-level escalation
- Time-based escalation
- Acknowledgment tracking
- Override and snooze
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.notifications.notification_router import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationRouter,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class EscalationStatus(str, Enum):
    """Status of an escalation."""
    
    PENDING = "pending"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    TIMED_OUT = "timed_out"
    SNOOZED = "snoozed"


class EscalationLevel(BaseModel):
    """A level in an escalation policy."""
    
    level: int = 1
    name: str
    
    # Targets at this level
    users: List[str] = Field(default_factory=list)  # User IDs
    groups: List[str] = Field(default_factory=list)  # Group IDs
    channels: List[NotificationChannel] = Field(default_factory=list)
    channel_targets: Dict[str, str] = Field(default_factory=dict)
    # e.g., {"slack": "#oncall-team", "email": "oncall@example.com"}
    
    # Timing
    delay_minutes: int = 0  # Delay before escalating to this level
    repeat_interval_minutes: Optional[int] = None  # Repeat notifications
    max_repeats: int = 3
    
    # Escalation behavior
    escalate_after_minutes: Optional[int] = None  # Escalate to next level after
    require_acknowledgment: bool = True
    
    def get_notification_recipients(self) -> List[str]:
        """Get all recipients for notifications at this level."""
        recipients = []
        recipients.extend(self.users)
        for group in self.groups:
            recipients.append(f"group:{group}")
        return recipients


class EscalationRule(BaseModel):
    """A rule that determines when escalation applies."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Conditions
    priorities: List[NotificationPriority] = Field(default_factory=list)
    notification_types: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    
    # Schedule constraints
    active_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    # 0 = Monday, 6 = Sunday
    active_hours_start: int = 0  # 0-23
    active_hours_end: int = 24  # 0-24
    timezone: str = "UTC"
    
    # Priority
    priority: int = 0
    
    enabled: bool = True
    
    def matches(self, notification: Notification) -> bool:
        """Check if this rule matches a notification."""
        if not self.enabled:
            return False
        
        # Check priority
        if self.priorities and notification.priority not in self.priorities:
            return False
        
        # Check type
        if self.notification_types:
            if notification.notification_type.value not in self.notification_types:
                return False
        
        # Check tags
        if self.tags:
            if not any(tag in notification.tags for tag in self.tags):
                return False
        
        # Check schedule
        if not self._is_active_time():
            return False
        
        return True
    
    def _is_active_time(self) -> bool:
        """Check if current time is within active schedule."""
        from datetime import timezone as tz
        
        # Get current time in configured timezone
        # Simplified - would use pytz in production
        now = datetime.now(tz.utc)
        
        # Check day of week
        if now.weekday() not in self.active_days:
            return False
        
        # Check hour
        hour = now.hour
        if self.active_hours_start <= self.active_hours_end:
            if not (self.active_hours_start <= hour < self.active_hours_end):
                return False
        else:
            # Wrap around (e.g., 22:00 - 06:00)
            if not (hour >= self.active_hours_start or hour < self.active_hours_end):
                return False
        
        return True


class EscalationPolicy(BaseModel):
    """An escalation policy defining how alerts are escalated."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    description: Optional[str] = None
    
    # Levels
    levels: List[EscalationLevel] = Field(default_factory=list)
    
    # Rules
    rules: List[EscalationRule] = Field(default_factory=list)
    
    # Default behavior
    default_timeout_minutes: int = 60
    auto_resolve_on_recovery: bool = True
    
    # Metadata
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    def get_matching_rule(
        self,
        notification: Notification,
    ) -> Optional[EscalationRule]:
        """Get the highest priority matching rule."""
        matching = [r for r in self.rules if r.matches(notification)]
        
        if not matching:
            return None
        
        # Sort by priority descending
        matching.sort(key=lambda r: r.priority, reverse=True)
        
        return matching[0]


class EscalationInstance(BaseModel):
    """An active escalation instance."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    policy_id: str
    notification_id: str
    
    # Current state
    status: EscalationStatus = EscalationStatus.PENDING
    current_level: int = 1
    repeat_count: int = 0
    
    # Tracking
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_escalated_at: Optional[datetime] = None
    last_notified_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    # Snooze
    snoozed_until: Optional[datetime] = None
    snoozed_by: Optional[str] = None
    
    # History
    history: List[Dict[str, Any]] = Field(default_factory=list)
    
    def add_history(self, action: str, **kwargs) -> None:
        """Add an entry to escalation history."""
        self.history.append({
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })


class EscalationEngine:
    """
    Manages escalation policies and active escalations.
    
    Provides:
    - Policy management
    - Escalation execution
    - Acknowledgment handling
    - Snooze/override
    - Metrics and reporting
    
    Example:
        engine = EscalationEngine(notification_router)
        
        # Create policy
        policy = await engine.create_policy(
            tenant_id="tenant-123",
            name="Critical Alerts",
            levels=[
                EscalationLevel(
                    level=1,
                    name="Primary On-Call",
                    users=["user-1"],
                    channels=[NotificationChannel.SLACK, NotificationChannel.PAGERDUTY],
                    escalate_after_minutes=15,
                ),
                EscalationLevel(
                    level=2,
                    name="Secondary On-Call",
                    users=["user-2", "user-3"],
                    channels=[NotificationChannel.PAGERDUTY],
                    escalate_after_minutes=30,
                ),
                EscalationLevel(
                    level=3,
                    name="Engineering Lead",
                    users=["user-4"],
                    channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
                ),
            ],
        )
        
        # Start escalation
        instance = await engine.start_escalation(notification, policy.id)
        
        # Acknowledge
        await engine.acknowledge(instance.id, "user-1")
    """
    
    def __init__(
        self,
        notification_router: NotificationRouter,
        check_interval_seconds: int = 30,
    ):
        """Initialize EscalationEngine.
        
        Args:
            notification_router: NotificationRouter for sending notifications
            check_interval_seconds: Interval for checking escalations
        """
        self.notification_router = notification_router
        self.check_interval_seconds = check_interval_seconds
        
        self._policies: Dict[str, EscalationPolicy] = {}
        self._instances: Dict[str, EscalationInstance] = {}
        self._notifications: Dict[str, Notification] = {}  # notification_id -> Notification
        self._lock = asyncio.Lock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the escalation engine background task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Escalation engine started")
    
    async def stop(self) -> None:
        """Stop the escalation engine."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Escalation engine stopped")
    
    async def create_policy(
        self,
        tenant_id: str,
        name: str,
        levels: List[EscalationLevel],
        rules: Optional[List[EscalationRule]] = None,
        **kwargs,
    ) -> EscalationPolicy:
        """Create an escalation policy.
        
        Args:
            tenant_id: Tenant ID
            name: Policy name
            levels: Escalation levels
            rules: Optional matching rules
            **kwargs: Additional policy options
            
        Returns:
            Created policy
        """
        async with self._lock:
            policy = EscalationPolicy(
                tenant_id=tenant_id,
                name=name,
                levels=levels,
                rules=rules or [],
                **kwargs,
            )
            
            self._policies[policy.id] = policy
            
            logger.info(
                "Created escalation policy",
                policy_id=policy.id,
                tenant_id=tenant_id,
                levels=len(levels),
            )
            
            return policy
    
    async def get_policy(self, policy_id: str) -> Optional[EscalationPolicy]:
        """Get an escalation policy."""
        return self._policies.get(policy_id)
    
    async def list_policies(
        self,
        tenant_id: str,
        enabled_only: bool = True,
    ) -> List[EscalationPolicy]:
        """List policies for a tenant."""
        policies = [
            p for p in self._policies.values()
            if p.tenant_id == tenant_id
        ]
        
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        
        return policies
    
    async def update_policy(
        self,
        policy_id: str,
        **updates,
    ) -> EscalationPolicy:
        """Update an escalation policy."""
        async with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                raise ValueError(f"Policy {policy_id} not found")
            
            for key, value in updates.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            
            policy.updated_at = datetime.now(timezone.utc)
            
            return policy
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete an escalation policy."""
        async with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False
    
    async def start_escalation(
        self,
        notification: Notification,
        policy_id: str,
    ) -> EscalationInstance:
        """Start an escalation for a notification.
        
        Args:
            notification: Notification to escalate
            policy_id: Escalation policy ID
            
        Returns:
            Escalation instance
        """
        policy = await self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        if not policy.levels:
            raise ValueError("Policy has no escalation levels")
        
        async with self._lock:
            instance = EscalationInstance(
                policy_id=policy_id,
                notification_id=notification.id,
                current_level=1,
            )
            
            self._instances[instance.id] = instance
            self._notifications[notification.id] = notification
            
            instance.add_history("started", policy_id=policy_id)
            
            logger.info(
                "Started escalation",
                instance_id=instance.id,
                notification_id=notification.id,
                policy_id=policy_id,
            )
        
        # Send initial notification
        await self._notify_level(instance, policy, 1)
        
        return instance
    
    async def get_instance(
        self,
        instance_id: str,
    ) -> Optional[EscalationInstance]:
        """Get an escalation instance."""
        return self._instances.get(instance_id)
    
    async def list_instances(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[EscalationStatus] = None,
        notification_id: Optional[str] = None,
    ) -> List[EscalationInstance]:
        """List escalation instances.
        
        Args:
            tenant_id: Filter by tenant
            status: Filter by status
            notification_id: Filter by notification
            
        Returns:
            List of instances
        """
        instances = list(self._instances.values())
        
        if notification_id:
            instances = [i for i in instances if i.notification_id == notification_id]
        
        if status:
            instances = [i for i in instances if i.status == status]
        
        if tenant_id:
            # Filter by policy tenant
            instances = [
                i for i in instances
                if self._policies.get(i.policy_id, EscalationPolicy(tenant_id="", name="")).tenant_id == tenant_id
            ]
        
        return instances
    
    async def acknowledge(
        self,
        instance_id: str,
        user_id: str,
    ) -> EscalationInstance:
        """Acknowledge an escalation.
        
        Args:
            instance_id: Escalation instance ID
            user_id: User acknowledging
            
        Returns:
            Updated instance
        """
        async with self._lock:
            instance = self._instances.get(instance_id)
            if not instance:
                raise ValueError(f"Instance {instance_id} not found")
            
            if instance.status not in (EscalationStatus.PENDING, EscalationStatus.ACTIVE):
                raise ValueError(f"Cannot acknowledge escalation in status {instance.status.value}")
            
            instance.status = EscalationStatus.ACKNOWLEDGED
            instance.acknowledged_at = datetime.now(timezone.utc)
            instance.acknowledged_by = user_id
            
            instance.add_history("acknowledged", user_id=user_id)
            
            logger.info(
                "Escalation acknowledged",
                instance_id=instance_id,
                user_id=user_id,
            )
            
            return instance
    
    async def resolve(
        self,
        instance_id: str,
        resolution: Optional[str] = None,
    ) -> EscalationInstance:
        """Resolve an escalation.
        
        Args:
            instance_id: Escalation instance ID
            resolution: Resolution message
            
        Returns:
            Updated instance
        """
        async with self._lock:
            instance = self._instances.get(instance_id)
            if not instance:
                raise ValueError(f"Instance {instance_id} not found")
            
            instance.status = EscalationStatus.RESOLVED
            instance.resolved_at = datetime.now(timezone.utc)
            
            instance.add_history("resolved", resolution=resolution)
            
            logger.info(
                "Escalation resolved",
                instance_id=instance_id,
            )
            
            return instance
    
    async def snooze(
        self,
        instance_id: str,
        duration_minutes: int,
        user_id: str,
    ) -> EscalationInstance:
        """Snooze an escalation.
        
        Args:
            instance_id: Escalation instance ID
            duration_minutes: Snooze duration
            user_id: User snoozing
            
        Returns:
            Updated instance
        """
        async with self._lock:
            instance = self._instances.get(instance_id)
            if not instance:
                raise ValueError(f"Instance {instance_id} not found")
            
            instance.status = EscalationStatus.SNOOZED
            instance.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            instance.snoozed_by = user_id
            
            instance.add_history(
                "snoozed",
                user_id=user_id,
                duration_minutes=duration_minutes,
            )
            
            logger.info(
                "Escalation snoozed",
                instance_id=instance_id,
                duration_minutes=duration_minutes,
            )
            
            return instance
    
    async def _run_loop(self) -> None:
        """Background loop for processing escalations."""
        while self._running:
            try:
                await self._process_escalations()
            except Exception as e:
                logger.error("Escalation processing error", error=str(e))
            
            await asyncio.sleep(self.check_interval_seconds)
    
    async def _process_escalations(self) -> None:
        """Process all active escalations."""
        now = datetime.now(timezone.utc)
        
        for instance in list(self._instances.values()):
            if instance.status not in (
                EscalationStatus.PENDING,
                EscalationStatus.ACTIVE,
                EscalationStatus.SNOOZED,
            ):
                continue
            
            # Check snooze expiry
            if instance.status == EscalationStatus.SNOOZED:
                if instance.snoozed_until and now >= instance.snoozed_until:
                    instance.status = EscalationStatus.ACTIVE
                    instance.snoozed_until = None
                    instance.add_history("snooze_expired")
                else:
                    continue
            
            policy = self._policies.get(instance.policy_id)
            if not policy:
                continue
            
            current_level = self._get_level(policy, instance.current_level)
            if not current_level:
                continue
            
            # Check for escalation
            if current_level.escalate_after_minutes:
                last_time = instance.last_escalated_at or instance.started_at
                elapsed = (now - last_time).total_seconds() / 60
                
                if elapsed >= current_level.escalate_after_minutes:
                    # Escalate to next level
                    next_level = instance.current_level + 1
                    
                    if next_level <= len(policy.levels):
                        instance.current_level = next_level
                        instance.last_escalated_at = now
                        instance.status = EscalationStatus.ACTIVE
                        instance.add_history("escalated", level=next_level)
                        
                        await self._notify_level(instance, policy, next_level)
                    else:
                        # Max level reached
                        instance.status = EscalationStatus.TIMED_OUT
                        instance.add_history("timed_out")
            
            # Check for repeat notification
            if current_level.repeat_interval_minutes and instance.repeat_count < current_level.max_repeats:
                if instance.last_notified_at:
                    elapsed = (now - instance.last_notified_at).total_seconds() / 60
                    
                    if elapsed >= current_level.repeat_interval_minutes:
                        instance.repeat_count += 1
                        await self._notify_level(instance, policy, instance.current_level)
    
    async def _notify_level(
        self,
        instance: EscalationInstance,
        policy: EscalationPolicy,
        level_number: int,
    ) -> None:
        """Send notifications for an escalation level."""
        level = self._get_level(policy, level_number)
        if not level:
            return
        
        notification = self._notifications.get(instance.notification_id)
        if not notification:
            return
        
        # Clone notification with level info
        level_notification = notification.model_copy()
        level_notification.id = str(uuid4())  # New ID for tracking
        level_notification.title = f"[ESCALATION L{level_number}] {notification.title}"
        level_notification.recipients = level.get_notification_recipients()
        level_notification.channels = level.channels
        level_notification.metadata["escalation_id"] = instance.id
        level_notification.metadata["escalation_level"] = level_number
        level_notification.metadata["escalation_level_name"] = level.name
        
        # Send via router
        await self.notification_router.send(level_notification)
        
        instance.last_notified_at = datetime.now(timezone.utc)
        instance.status = EscalationStatus.ACTIVE
        instance.add_history(
            "notified",
            level=level_number,
            channels=[c.value for c in level.channels],
        )
    
    def _get_level(
        self,
        policy: EscalationPolicy,
        level_number: int,
    ) -> Optional[EscalationLevel]:
        """Get escalation level by number."""
        for level in policy.levels:
            if level.level == level_number:
                return level
        return None
    
    async def get_stats(
        self,
        tenant_id: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get escalation statistics.
        
        Args:
            tenant_id: Tenant ID
            since: Start time for stats
            
        Returns:
            Statistics dictionary
        """
        instances = await self.list_instances(tenant_id=tenant_id)
        
        if since:
            instances = [i for i in instances if i.started_at >= since]
        
        if not instances:
            return {
                "total": 0,
                "by_status": {},
                "avg_time_to_acknowledge_minutes": None,
                "avg_time_to_resolve_minutes": None,
            }
        
        by_status: Dict[str, int] = {}
        ack_times: List[float] = []
        resolve_times: List[float] = []
        
        for instance in instances:
            status = instance.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            if instance.acknowledged_at:
                ack_time = (instance.acknowledged_at - instance.started_at).total_seconds() / 60
                ack_times.append(ack_time)
            
            if instance.resolved_at:
                resolve_time = (instance.resolved_at - instance.started_at).total_seconds() / 60
                resolve_times.append(resolve_time)
        
        return {
            "total": len(instances),
            "by_status": by_status,
            "avg_time_to_acknowledge_minutes": sum(ack_times) / len(ack_times) if ack_times else None,
            "avg_time_to_resolve_minutes": sum(resolve_times) / len(resolve_times) if resolve_times else None,
            "escalated_count": sum(1 for i in instances if i.current_level > 1),
            "timed_out_count": by_status.get("timed_out", 0),
        }
