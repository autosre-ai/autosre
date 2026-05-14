"""Notification Router for AutoSRE V2.

Central hub for routing notifications to appropriate channels:
- Priority-based routing
- Multi-channel delivery
- Delivery tracking and retries
- Rate limiting
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    PARTIAL = "partial"  # Some channels succeeded
    SKIPPED = "skipped"  # Deduplicated or filtered


class NotificationType(str, Enum):
    """Types of notifications."""
    
    ALERT = "alert"
    INCIDENT = "incident"
    INVESTIGATION = "investigation"
    ACTION_REQUIRED = "action_required"
    STATUS_UPDATE = "status_update"
    REPORT = "report"
    SYSTEM = "system"


class Notification(BaseModel):
    """A notification to be sent."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Classification
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    
    # Content
    title: str
    message: str
    summary: Optional[str] = None  # Short version for SMS/push
    
    # Rich content
    details: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, str]] = Field(default_factory=list)
    # e.g., [{"label": "View", "url": "https://..."}, {"label": "Acknowledge", "action": "ack"}]
    
    # Routing
    channels: List[NotificationChannel] = Field(default_factory=list)
    recipients: List[str] = Field(default_factory=list)  # User IDs or channel addresses
    
    # Context
    tenant_id: str
    source: str = "autosre"
    source_id: Optional[str] = None  # Alert ID, Investigation ID, etc.
    source_url: Optional[str] = None
    
    # Tags for filtering and routing
    tags: List[str] = Field(default_factory=list)
    
    # Deduplication
    dedup_key: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    send_at: Optional[datetime] = None  # Scheduled send time
    expires_at: Optional[datetime] = None  # Don't send after this time
    
    # Status tracking
    status: NotificationStatus = NotificationStatus.PENDING
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeliveryResult(BaseModel):
    """Result of notification delivery to a channel."""
    
    notification_id: str
    channel: NotificationChannel
    recipient: Optional[str] = None
    
    # Status
    success: bool
    status: NotificationStatus
    
    # Provider response
    provider_id: Optional[str] = None  # ID from the channel provider
    provider_response: Optional[Dict[str, Any]] = None
    
    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Timing
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    
    # Retry info
    attempt: int = 1
    retry_after: Optional[datetime] = None


class ChannelConfig(BaseModel):
    """Configuration for a notification channel."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    channel: NotificationChannel
    name: str
    
    # Channel-specific configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Routing rules
    priority_filter: List[NotificationPriority] = Field(default_factory=list)
    type_filter: List[NotificationType] = Field(default_factory=list)
    tag_filter: List[str] = Field(default_factory=list)
    
    # Rate limiting
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    
    # Status
    enabled: bool = True
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationHandler(ABC):
    """Abstract base class for notification channel handlers."""
    
    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """Return the channel type."""
        ...
    
    @abstractmethod
    async def send(
        self,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send a notification through this channel."""
        ...
    
    @abstractmethod
    async def health_check(self, config: ChannelConfig) -> bool:
        """Check if the channel is healthy."""
        ...


class NotificationRouter:
    """
    Routes notifications to appropriate channels.
    
    Provides:
    - Multi-channel delivery
    - Priority-based routing
    - Rate limiting
    - Retry logic
    - Delivery tracking
    
    Example:
        router = NotificationRouter()
        
        # Register channel handlers
        router.register_handler(SlackHandler())
        router.register_handler(PagerDutyHandler())
        
        # Configure channels for tenant
        await router.add_channel_config(ChannelConfig(
            tenant_id="tenant-123",
            channel=NotificationChannel.SLACK,
            name="Engineering Slack",
            config={"webhook_url": "https://..."},
        ))
        
        # Send notification
        results = await router.send(Notification(
            tenant_id="tenant-123",
            notification_type=NotificationType.ALERT,
            priority=NotificationPriority.HIGH,
            title="High CPU Alert",
            message="CPU usage exceeded 90%",
            channels=[NotificationChannel.SLACK],
        ))
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: int = 30,
        dedup_window_seconds: int = 300,
    ):
        """Initialize NotificationRouter.
        
        Args:
            max_retries: Maximum retry attempts
            retry_delay_seconds: Delay between retries
            dedup_window_seconds: Window for deduplication
        """
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.dedup_window_seconds = dedup_window_seconds
        
        self._handlers: Dict[NotificationChannel, NotificationHandler] = {}
        self._channel_configs: Dict[str, List[ChannelConfig]] = {}  # tenant_id -> configs
        self._delivery_results: List[DeliveryResult] = []
        self._dedup_cache: Dict[str, datetime] = {}
        self._rate_limits: Dict[str, List[datetime]] = {}  # config_id -> send times
        self._lock = asyncio.Lock()
    
    def register_handler(self, handler: NotificationHandler) -> None:
        """Register a channel handler.
        
        Args:
            handler: NotificationHandler instance
        """
        self._handlers[handler.channel] = handler
        logger.info(f"Registered notification handler for {handler.channel.value}")
    
    async def add_channel_config(self, config: ChannelConfig) -> ChannelConfig:
        """Add a channel configuration.
        
        Args:
            config: Channel configuration
            
        Returns:
            Added configuration
        """
        async with self._lock:
            if config.tenant_id not in self._channel_configs:
                self._channel_configs[config.tenant_id] = []
            
            self._channel_configs[config.tenant_id].append(config)
            
            logger.info(
                "Added channel configuration",
                config_id=config.id,
                tenant_id=config.tenant_id,
                channel=config.channel.value,
            )
            
            return config
    
    async def get_channel_configs(
        self,
        tenant_id: str,
        channel: Optional[NotificationChannel] = None,
    ) -> List[ChannelConfig]:
        """Get channel configurations for a tenant.
        
        Args:
            tenant_id: Tenant ID
            channel: Optional channel filter
            
        Returns:
            List of configurations
        """
        configs = self._channel_configs.get(tenant_id, [])
        
        if channel:
            configs = [c for c in configs if c.channel == channel]
        
        return [c for c in configs if c.enabled]
    
    async def send(
        self,
        notification: Notification,
        force: bool = False,
    ) -> List[DeliveryResult]:
        """Send a notification through configured channels.
        
        Args:
            notification: Notification to send
            force: Skip deduplication and rate limiting
            
        Returns:
            List of delivery results
        """
        results: List[DeliveryResult] = []
        
        # Check expiry
        if notification.expires_at and datetime.now(timezone.utc) > notification.expires_at:
            logger.debug(
                "Notification expired",
                notification_id=notification.id,
            )
            notification.status = NotificationStatus.SKIPPED
            return results
        
        # Check scheduled time
        if notification.send_at and datetime.now(timezone.utc) < notification.send_at:
            # Queue for later
            notification.status = NotificationStatus.QUEUED
            return results
        
        # Deduplication
        if not force and notification.dedup_key:
            if self._is_duplicate(notification.dedup_key):
                logger.debug(
                    "Notification deduplicated",
                    notification_id=notification.id,
                    dedup_key=notification.dedup_key,
                )
                notification.status = NotificationStatus.SKIPPED
                return results
        
        # Get channel configurations
        channels_to_use = notification.channels or [NotificationChannel.SLACK]
        
        for channel in channels_to_use:
            # Get handler
            handler = self._handlers.get(channel)
            if not handler:
                logger.warning(f"No handler registered for channel {channel.value}")
                continue
            
            # Get configurations for this channel
            configs = await self.get_channel_configs(notification.tenant_id, channel)
            
            if not configs:
                logger.debug(
                    "No configurations for channel",
                    tenant_id=notification.tenant_id,
                    channel=channel.value,
                )
                continue
            
            # Apply routing rules
            configs = self._filter_configs(configs, notification)
            
            for config in configs:
                # Rate limiting
                if not force and not self._check_rate_limit(config):
                    logger.debug(
                        "Rate limited",
                        config_id=config.id,
                        channel=channel.value,
                    )
                    continue
                
                # Send
                result = await self._send_with_retry(handler, notification, config)
                results.append(result)
                
                # Track rate limit
                self._record_send(config.id)
        
        # Update notification status
        if results:
            if all(r.success for r in results):
                notification.status = NotificationStatus.DELIVERED
            elif any(r.success for r in results):
                notification.status = NotificationStatus.PARTIAL
            else:
                notification.status = NotificationStatus.FAILED
        else:
            notification.status = NotificationStatus.SKIPPED
        
        # Record dedup
        if notification.dedup_key:
            self._record_dedup(notification.dedup_key)
        
        # Store results
        self._delivery_results.extend(results)
        
        logger.info(
            "Notification sent",
            notification_id=notification.id,
            status=notification.status.value,
            channels=len(results),
            successful=sum(1 for r in results if r.success),
        )
        
        return results
    
    async def send_batch(
        self,
        notifications: List[Notification],
        concurrency: int = 5,
    ) -> Dict[str, List[DeliveryResult]]:
        """Send multiple notifications concurrently.
        
        Args:
            notifications: Notifications to send
            concurrency: Max concurrent sends
            
        Returns:
            Dict of notification_id -> results
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def send_one(notification: Notification):
            async with semaphore:
                results = await self.send(notification)
                return notification.id, results
        
        tasks = [send_one(n) for n in notifications]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for item in completed:
            if isinstance(item, Exception):
                logger.error("Batch send error", error=str(item))
            else:
                notification_id, delivery_results = item
                results[notification_id] = delivery_results
        
        return results
    
    async def get_delivery_status(
        self,
        notification_id: str,
    ) -> List[DeliveryResult]:
        """Get delivery results for a notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            List of delivery results
        """
        return [r for r in self._delivery_results if r.notification_id == notification_id]
    
    async def health_check(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Check health of all configured channels.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Health status by channel
        """
        status = {}
        
        configs = self._channel_configs.get(tenant_id, [])
        
        for config in configs:
            handler = self._handlers.get(config.channel)
            if handler:
                try:
                    healthy = await handler.health_check(config)
                    status[config.id] = {
                        "channel": config.channel.value,
                        "name": config.name,
                        "healthy": healthy,
                    }
                except Exception as e:
                    status[config.id] = {
                        "channel": config.channel.value,
                        "name": config.name,
                        "healthy": False,
                        "error": str(e),
                    }
        
        return status
    
    async def _send_with_retry(
        self,
        handler: NotificationHandler,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send with retry logic.
        
        Args:
            handler: Channel handler
            notification: Notification
            config: Channel configuration
            
        Returns:
            Delivery result
        """
        last_result = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await handler.send(notification, config)
                result.attempt = attempt
                
                if result.success:
                    return result
                
                last_result = result
                
                # Check if retryable
                if result.retry_after:
                    delay = (result.retry_after - datetime.now(timezone.utc)).total_seconds()
                    if delay > 0:
                        await asyncio.sleep(min(delay, self.retry_delay_seconds * attempt))
                else:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)
                
            except Exception as e:
                logger.error(
                    "Send failed",
                    notification_id=notification.id,
                    channel=config.channel.value,
                    attempt=attempt,
                    error=str(e),
                )
                
                last_result = DeliveryResult(
                    notification_id=notification.id,
                    channel=config.channel,
                    success=False,
                    status=NotificationStatus.FAILED,
                    error_code="exception",
                    error_message=str(e),
                    attempt=attempt,
                )
                
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)
        
        return last_result or DeliveryResult(
            notification_id=notification.id,
            channel=config.channel,
            success=False,
            status=NotificationStatus.FAILED,
            error_code="max_retries",
            error_message="Maximum retries exceeded",
        )
    
    def _filter_configs(
        self,
        configs: List[ChannelConfig],
        notification: Notification,
    ) -> List[ChannelConfig]:
        """Filter configs based on routing rules."""
        filtered = []
        
        for config in configs:
            # Priority filter
            if config.priority_filter:
                if notification.priority not in config.priority_filter:
                    continue
            
            # Type filter
            if config.type_filter:
                if notification.notification_type not in config.type_filter:
                    continue
            
            # Tag filter
            if config.tag_filter:
                if not any(tag in notification.tags for tag in config.tag_filter):
                    continue
            
            filtered.append(config)
        
        return filtered
    
    def _is_duplicate(self, dedup_key: str) -> bool:
        """Check if notification is a duplicate."""
        if dedup_key in self._dedup_cache:
            last_sent = self._dedup_cache[dedup_key]
            if datetime.now(timezone.utc) - last_sent < timedelta(seconds=self.dedup_window_seconds):
                return True
        return False
    
    def _record_dedup(self, dedup_key: str) -> None:
        """Record dedup key."""
        self._dedup_cache[dedup_key] = datetime.now(timezone.utc)
        
        # Cleanup old entries
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.dedup_window_seconds * 2)
        self._dedup_cache = {
            k: v for k, v in self._dedup_cache.items()
            if v > cutoff
        }
    
    def _check_rate_limit(self, config: ChannelConfig) -> bool:
        """Check if config is within rate limits."""
        if not config.rate_limit_per_minute and not config.rate_limit_per_hour:
            return True
        
        now = datetime.now(timezone.utc)
        send_times = self._rate_limits.get(config.id, [])
        
        # Clean old entries
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        send_times = [t for t in send_times if t > hour_ago]
        self._rate_limits[config.id] = send_times
        
        # Check minute limit
        if config.rate_limit_per_minute:
            minute_count = sum(1 for t in send_times if t > minute_ago)
            if minute_count >= config.rate_limit_per_minute:
                return False
        
        # Check hour limit
        if config.rate_limit_per_hour:
            if len(send_times) >= config.rate_limit_per_hour:
                return False
        
        return True
    
    def _record_send(self, config_id: str) -> None:
        """Record a send for rate limiting."""
        if config_id not in self._rate_limits:
            self._rate_limits[config_id] = []
        self._rate_limits[config_id].append(datetime.now(timezone.utc))


# Convenience function for creating notifications
def create_alert_notification(
    tenant_id: str,
    alert_name: str,
    alert_severity: str,
    alert_description: str,
    alert_id: Optional[str] = None,
    source_url: Optional[str] = None,
    channels: Optional[List[NotificationChannel]] = None,
) -> Notification:
    """Create a notification for an alert.
    
    Args:
        tenant_id: Tenant ID
        alert_name: Alert name
        alert_severity: Alert severity
        alert_description: Alert description
        alert_id: Alert ID
        source_url: URL to view alert
        channels: Notification channels
        
    Returns:
        Notification
    """
    priority_map = {
        "critical": NotificationPriority.CRITICAL,
        "high": NotificationPriority.URGENT,
        "medium": NotificationPriority.HIGH,
        "low": NotificationPriority.NORMAL,
        "info": NotificationPriority.LOW,
    }
    
    return Notification(
        tenant_id=tenant_id,
        notification_type=NotificationType.ALERT,
        priority=priority_map.get(alert_severity.lower(), NotificationPriority.NORMAL),
        title=f"🚨 Alert: {alert_name}",
        message=alert_description,
        summary=f"[{alert_severity.upper()}] {alert_name}",
        source_id=alert_id,
        source_url=source_url,
        channels=channels or [NotificationChannel.SLACK],
        dedup_key=f"alert:{alert_id}" if alert_id else None,
        details={
            "alert_name": alert_name,
            "severity": alert_severity,
        },
        tags=[f"severity:{alert_severity}"],
    )


def create_investigation_notification(
    tenant_id: str,
    investigation_id: str,
    status: str,
    summary: str,
    source_url: Optional[str] = None,
    channels: Optional[List[NotificationChannel]] = None,
) -> Notification:
    """Create a notification for an investigation status update.
    
    Args:
        tenant_id: Tenant ID
        investigation_id: Investigation ID
        status: Investigation status
        summary: Investigation summary
        source_url: URL to view investigation
        channels: Notification channels
        
    Returns:
        Notification
    """
    status_emoji = {
        "started": "🔍",
        "in_progress": "⏳",
        "completed": "✅",
        "failed": "❌",
        "escalated": "⚠️",
    }
    
    return Notification(
        tenant_id=tenant_id,
        notification_type=NotificationType.INVESTIGATION,
        priority=NotificationPriority.NORMAL,
        title=f"{status_emoji.get(status, '📋')} Investigation {status.title()}",
        message=summary,
        summary=f"Investigation {status}: {summary[:50]}...",
        source_id=investigation_id,
        source_url=source_url,
        channels=channels or [NotificationChannel.SLACK],
        dedup_key=f"investigation:{investigation_id}:{status}",
        details={
            "investigation_id": investigation_id,
            "status": status,
        },
        tags=[f"status:{status}"],
    )
