"""Webhook Manager for AutoSRE V2 Notifications.

Provides custom webhook integration:
- Webhook registration and management
- Event delivery with retries
- Signature verification
- Event filtering
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, SecretStr

from autosre.notifications.notification_router import (
    ChannelConfig,
    DeliveryResult,
    Notification,
    NotificationChannel,
    NotificationHandler,
    NotificationStatus,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookEventType(str, Enum):
    """Types of events that can trigger webhooks."""
    
    ALERT_FIRED = "alert.fired"
    ALERT_RESOLVED = "alert.resolved"
    INVESTIGATION_STARTED = "investigation.started"
    INVESTIGATION_COMPLETED = "investigation.completed"
    INVESTIGATION_FAILED = "investigation.failed"
    ACTION_PROPOSED = "action.proposed"
    ACTION_APPROVED = "action.approved"
    ACTION_EXECUTED = "action.executed"
    ACTION_FAILED = "action.failed"
    RUNBOOK_EXECUTED = "runbook.executed"
    SYSTEM_EVENT = "system.event"


class WebhookStatus(str, Enum):
    """Webhook status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"  # Too many failures


class Webhook(BaseModel):
    """A webhook configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    description: Optional[str] = None
    
    # Target
    url: str
    method: str = "POST"
    
    # Authentication
    secret: Optional[SecretStr] = None  # For HMAC signing
    auth_header: Optional[str] = None  # Custom auth header value
    
    # Event filtering
    event_types: List[WebhookEventType] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    
    # Headers
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    
    # Payload transformation
    payload_template: Optional[str] = None  # JSON template
    include_raw_payload: bool = True
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 30
    
    # Status
    status: WebhookStatus = WebhookStatus.ACTIVE
    consecutive_failures: int = 0
    max_consecutive_failures: int = 10
    
    # Statistics
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    last_delivery_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_failure_reason: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None


class WebhookEvent(BaseModel):
    """An event to be sent to webhooks."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: WebhookEventType
    
    # Event data
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # Context
    tenant_id: str
    source: str = "autosre"
    source_id: Optional[str] = None
    
    # Tags for filtering
    tags: List[str] = Field(default_factory=list)
    
    # Timing
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_payload(self, webhook: Webhook) -> Dict[str, Any]:
        """Convert to webhook payload."""
        payload = {
            "event_id": self.id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "source": self.source,
            "source_id": self.source_id,
            "tenant_id": self.tenant_id,
        }
        
        if webhook.include_raw_payload:
            payload["data"] = self.data
        
        if webhook.payload_template:
            # Apply template (simple variable substitution)
            try:
                template_payload = json.loads(webhook.payload_template)
                payload = self._apply_template(template_payload, self.data)
            except json.JSONDecodeError:
                pass
        
        return payload
    
    def _apply_template(
        self,
        template: Any,
        data: Dict[str, Any],
    ) -> Any:
        """Apply template substitution."""
        if isinstance(template, str):
            # Check for variable reference
            if template.startswith("{{") and template.endswith("}}"):
                key = template[2:-2].strip()
                return data.get(key, template)
            return template
        elif isinstance(template, dict):
            return {
                k: self._apply_template(v, data)
                for k, v in template.items()
            }
        elif isinstance(template, list):
            return [self._apply_template(item, data) for item in template]
        return template
    
    @classmethod
    def from_notification(
        cls,
        notification: Notification,
        event_type: WebhookEventType,
    ) -> "WebhookEvent":
        """Create WebhookEvent from a Notification."""
        return cls(
            event_type=event_type,
            tenant_id=notification.tenant_id,
            source=notification.source,
            source_id=notification.source_id,
            tags=notification.tags,
            data={
                "notification_id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "type": notification.notification_type.value,
                "details": notification.details,
                "source_url": notification.source_url,
            },
        )


class WebhookDelivery(BaseModel):
    """Record of a webhook delivery attempt."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    webhook_id: str
    event_id: str
    
    # Attempt info
    attempt: int = 1
    
    # Request
    request_url: str
    request_method: str
    request_headers: Dict[str, str] = Field(default_factory=dict)
    request_body: str
    
    # Response
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    response_time_ms: Optional[float] = None
    
    # Status
    success: bool = False
    error: Optional[str] = None
    
    # Timing
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookManager(NotificationHandler):
    """
    Manages webhooks and event delivery.
    
    Provides:
    - Webhook registration
    - Event filtering
    - Signature verification
    - Retry logic
    - Delivery tracking
    
    Example:
        manager = WebhookManager()
        
        # Register webhook
        webhook = await manager.register_webhook(
            tenant_id="tenant-123",
            name="My Webhook",
            url="https://example.com/webhook",
            secret="my-secret",
            event_types=[WebhookEventType.ALERT_FIRED],
        )
        
        # Deliver event
        event = WebhookEvent(
            event_type=WebhookEventType.ALERT_FIRED,
            tenant_id="tenant-123",
            data={"alert_id": "..."},
        )
        
        results = await manager.deliver_event(event)
    """
    
    def __init__(self, timeout: float = 10.0):
        """Initialize WebhookManager.
        
        Args:
            timeout: HTTP request timeout
        """
        self.timeout = timeout
        self._webhooks: Dict[str, Webhook] = {}
        self._deliveries: List[WebhookDelivery] = []
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.WEBHOOK
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def register_webhook(
        self,
        tenant_id: str,
        name: str,
        url: str,
        secret: Optional[str] = None,
        event_types: Optional[List[WebhookEventType]] = None,
        **kwargs,
    ) -> Webhook:
        """Register a new webhook.
        
        Args:
            tenant_id: Tenant ID
            name: Webhook name
            url: Webhook URL
            secret: Signing secret
            event_types: Events to receive
            **kwargs: Additional webhook options
            
        Returns:
            Registered webhook
        """
        async with self._lock:
            webhook = Webhook(
                tenant_id=tenant_id,
                name=name,
                url=url,
                secret=SecretStr(secret) if secret else None,
                event_types=event_types or [],
                **kwargs,
            )
            
            self._webhooks[webhook.id] = webhook
            
            logger.info(
                "Registered webhook",
                webhook_id=webhook.id,
                tenant_id=tenant_id,
                url=url,
            )
            
            return webhook
    
    async def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get a webhook by ID."""
        return self._webhooks.get(webhook_id)
    
    async def list_webhooks(
        self,
        tenant_id: str,
        active_only: bool = True,
    ) -> List[Webhook]:
        """List webhooks for a tenant.
        
        Args:
            tenant_id: Tenant ID
            active_only: Only return active webhooks
            
        Returns:
            List of webhooks
        """
        webhooks = [
            w for w in self._webhooks.values()
            if w.tenant_id == tenant_id
        ]
        
        if active_only:
            webhooks = [w for w in webhooks if w.status == WebhookStatus.ACTIVE]
        
        return webhooks
    
    async def update_webhook(
        self,
        webhook_id: str,
        **updates,
    ) -> Webhook:
        """Update a webhook.
        
        Args:
            webhook_id: Webhook ID
            **updates: Fields to update
            
        Returns:
            Updated webhook
        """
        async with self._lock:
            webhook = self._webhooks.get(webhook_id)
            if not webhook:
                raise ValueError(f"Webhook {webhook_id} not found")
            
            for key, value in updates.items():
                if hasattr(webhook, key):
                    setattr(webhook, key, value)
            
            webhook.updated_at = datetime.now(timezone.utc)
            
            return webhook
    
    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        async with self._lock:
            if webhook_id in self._webhooks:
                del self._webhooks[webhook_id]
                return True
            return False
    
    async def deliver_event(
        self,
        event: WebhookEvent,
    ) -> List[DeliveryResult]:
        """Deliver an event to all matching webhooks.
        
        Args:
            event: Event to deliver
            
        Returns:
            List of delivery results
        """
        webhooks = await self.list_webhooks(event.tenant_id)
        
        # Filter by event type
        matching = [
            w for w in webhooks
            if not w.event_types or event.event_type in w.event_types
        ]
        
        # Filter by tags
        matching = [
            w for w in matching
            if not w.tags or any(tag in event.tags for tag in w.tags)
        ]
        
        # Deliver to each webhook
        results = []
        for webhook in matching:
            result = await self._deliver_to_webhook(event, webhook)
            results.append(result)
        
        return results
    
    async def send(
        self,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send notification as webhook event."""
        # Determine event type from notification
        event_type_map = {
            "alert": WebhookEventType.ALERT_FIRED,
            "incident": WebhookEventType.ALERT_FIRED,
            "investigation": WebhookEventType.INVESTIGATION_STARTED,
            "action_required": WebhookEventType.ACTION_PROPOSED,
        }
        
        event_type = event_type_map.get(
            notification.notification_type.value,
            WebhookEventType.SYSTEM_EVENT,
        )
        
        event = WebhookEvent.from_notification(notification, event_type)
        
        results = await self.deliver_event(event)
        
        if not results:
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.WEBHOOK,
                success=True,
                status=NotificationStatus.SKIPPED,
            )
        
        # Aggregate results
        all_success = all(r.success for r in results)
        any_success = any(r.success for r in results)
        
        return DeliveryResult(
            notification_id=notification.id,
            channel=NotificationChannel.WEBHOOK,
            success=any_success,
            status=NotificationStatus.DELIVERED if all_success else (
                NotificationStatus.PARTIAL if any_success else NotificationStatus.FAILED
            ),
            provider_response={
                "total": len(results),
                "successful": sum(1 for r in results if r.success),
            },
        )
    
    async def _deliver_to_webhook(
        self,
        event: WebhookEvent,
        webhook: Webhook,
    ) -> DeliveryResult:
        """Deliver event to a single webhook with retries.
        
        Args:
            event: Event to deliver
            webhook: Target webhook
            
        Returns:
            DeliveryResult
        """
        import time
        
        payload = event.to_payload(webhook)
        payload_json = json.dumps(payload)
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-AutoSRE-Event-ID": event.id,
            "X-AutoSRE-Event-Type": event.event_type.value,
            "X-AutoSRE-Timestamp": event.occurred_at.isoformat(),
            **webhook.custom_headers,
        }
        
        # Add signature
        if webhook.secret:
            signature = self._compute_signature(
                payload_json,
                webhook.secret.get_secret_value(),
            )
            headers["X-AutoSRE-Signature"] = f"sha256={signature}"
        
        # Add auth header
        if webhook.auth_header:
            headers["Authorization"] = webhook.auth_header
        
        last_delivery: Optional[WebhookDelivery] = None
        
        for attempt in range(1, webhook.max_retries + 1):
            start_time = time.time()
            
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_id=event.id,
                attempt=attempt,
                request_url=webhook.url,
                request_method=webhook.method,
                request_headers={k: v for k, v in headers.items() if k != "Authorization"},
                request_body=payload_json[:1000],
            )
            
            try:
                client = await self._get_client()
                
                response = await client.request(
                    method=webhook.method,
                    url=webhook.url,
                    headers=headers,
                    content=payload_json,
                )
                
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]
                delivery.response_time_ms = (time.time() - start_time) * 1000
                
                if 200 <= response.status_code < 300:
                    delivery.success = True
                    await self._record_success(webhook, delivery)
                    
                    return DeliveryResult(
                        notification_id=event.id,
                        channel=NotificationChannel.WEBHOOK,
                        success=True,
                        status=NotificationStatus.DELIVERED,
                        provider_id=webhook.id,
                        delivered_at=datetime.now(timezone.utc),
                    )
                
                delivery.error = f"HTTP {response.status_code}"
                last_delivery = delivery
                
            except Exception as e:
                delivery.error = str(e)
                last_delivery = delivery
            
            self._deliveries.append(delivery)
            
            # Retry delay
            if attempt < webhook.max_retries:
                await asyncio.sleep(webhook.retry_delay_seconds * attempt)
        
        # All retries failed
        await self._record_failure(webhook, last_delivery)
        
        return DeliveryResult(
            notification_id=event.id,
            channel=NotificationChannel.WEBHOOK,
            success=False,
            status=NotificationStatus.FAILED,
            error_code="delivery_failed",
            error_message=last_delivery.error if last_delivery else "Unknown error",
        )
    
    def _compute_signature(self, payload: str, secret: str) -> str:
        """Compute HMAC-SHA256 signature."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    async def _record_success(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery,
    ) -> None:
        """Record successful delivery."""
        async with self._lock:
            webhook.total_deliveries += 1
            webhook.successful_deliveries += 1
            webhook.consecutive_failures = 0
            webhook.last_delivery_at = datetime.now(timezone.utc)
            webhook.last_success_at = datetime.now(timezone.utc)
            
            if webhook.status == WebhookStatus.FAILED:
                webhook.status = WebhookStatus.ACTIVE
    
    async def _record_failure(
        self,
        webhook: Webhook,
        delivery: Optional[WebhookDelivery],
    ) -> None:
        """Record failed delivery."""
        async with self._lock:
            webhook.total_deliveries += 1
            webhook.failed_deliveries += 1
            webhook.consecutive_failures += 1
            webhook.last_delivery_at = datetime.now(timezone.utc)
            webhook.last_failure_at = datetime.now(timezone.utc)
            webhook.last_failure_reason = delivery.error if delivery else "Unknown"
            
            if webhook.consecutive_failures >= webhook.max_consecutive_failures:
                webhook.status = WebhookStatus.FAILED
                logger.warning(
                    "Webhook disabled due to consecutive failures",
                    webhook_id=webhook.id,
                    failures=webhook.consecutive_failures,
                )
    
    async def health_check(self, config: ChannelConfig) -> bool:
        """Check webhook endpoint reachability."""
        webhook_config = config.config
        url = webhook_config.get("url")
        
        if not url:
            return False
        
        try:
            client = await self._get_client()
            response = await client.head(url, timeout=5.0)
            return response.status_code < 500
        except Exception:
            return False
    
    async def get_deliveries(
        self,
        webhook_id: Optional[str] = None,
        event_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WebhookDelivery]:
        """Get delivery history.
        
        Args:
            webhook_id: Filter by webhook
            event_id: Filter by event
            limit: Maximum results
            
        Returns:
            List of deliveries
        """
        deliveries = self._deliveries
        
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        
        if event_id:
            deliveries = [d for d in deliveries if d.event_id == event_id]
        
        # Sort by time descending
        deliveries.sort(key=lambda d: d.sent_at, reverse=True)
        
        return deliveries[:limit]
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
