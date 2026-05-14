"""PagerDuty Integration for AutoSRE V2 Notifications.

Provides PagerDuty incident management:
- Event creation (trigger/resolve)
- Incident management
- Alert grouping
- Priority mapping
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.notifications.notification_router import (
    ChannelConfig,
    DeliveryResult,
    Notification,
    NotificationChannel,
    NotificationHandler,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class PagerDutyEventAction(str, Enum):
    """PagerDuty Events API v2 action types."""
    
    TRIGGER = "trigger"
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"


class PagerDutySeverity(str, Enum):
    """PagerDuty event severity levels."""
    
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class PagerDutyEvent(BaseModel):
    """A PagerDuty Events API v2 event."""
    
    routing_key: str
    event_action: PagerDutyEventAction = PagerDutyEventAction.TRIGGER
    dedup_key: Optional[str] = None
    
    # Payload
    summary: str
    source: str
    severity: PagerDutySeverity = PagerDutySeverity.ERROR
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Optional payload fields
    component: Optional[str] = None
    group: Optional[str] = None
    event_class: Optional[str] = None
    
    # Custom details
    custom_details: Dict[str, Any] = Field(default_factory=dict)
    
    # Links and images
    links: List[Dict[str, str]] = Field(default_factory=list)
    images: List[Dict[str, str]] = Field(default_factory=list)
    
    @classmethod
    def from_notification(
        cls,
        notification: Notification,
        routing_key: str,
    ) -> "PagerDutyEvent":
        """Create PagerDutyEvent from a Notification."""
        # Map priority to severity
        severity_map = {
            NotificationPriority.CRITICAL: PagerDutySeverity.CRITICAL,
            NotificationPriority.URGENT: PagerDutySeverity.CRITICAL,
            NotificationPriority.HIGH: PagerDutySeverity.ERROR,
            NotificationPriority.NORMAL: PagerDutySeverity.WARNING,
            NotificationPriority.LOW: PagerDutySeverity.INFO,
        }
        
        event = cls(
            routing_key=routing_key,
            event_action=PagerDutyEventAction.TRIGGER,
            dedup_key=notification.dedup_key or f"autosre:{notification.source_id or notification.id}",
            summary=f"{notification.title}: {notification.message[:200]}",
            source=notification.source,
            severity=severity_map.get(notification.priority, PagerDutySeverity.ERROR),
            timestamp=notification.created_at,
            component=notification.details.get("component"),
            group=notification.details.get("group"),
            event_class=notification.notification_type.value,
            custom_details={
                "title": notification.title,
                "message": notification.message,
                "notification_id": notification.id,
                "tenant_id": notification.tenant_id,
                "priority": notification.priority.value,
                "type": notification.notification_type.value,
                **notification.details,
            },
        )
        
        # Add source URL as link
        if notification.source_url:
            event.links.append({
                "href": notification.source_url,
                "text": "View in AutoSRE",
            })
        
        return event
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to PagerDuty Events API v2 payload."""
        payload: Dict[str, Any] = {
            "routing_key": self.routing_key,
            "event_action": self.event_action.value,
            "payload": {
                "summary": self.summary[:1024],
                "source": self.source,
                "severity": self.severity.value,
                "timestamp": self.timestamp.isoformat(),
                "custom_details": self.custom_details,
            },
        }
        
        if self.dedup_key:
            payload["dedup_key"] = self.dedup_key
        
        if self.component:
            payload["payload"]["component"] = self.component
        if self.group:
            payload["payload"]["group"] = self.group
        if self.event_class:
            payload["payload"]["class"] = self.event_class
        
        if self.links:
            payload["links"] = self.links
        if self.images:
            payload["images"] = self.images
        
        return payload


class PagerDutyIncident(BaseModel):
    """A PagerDuty incident."""
    
    id: str
    incident_number: int
    title: str
    status: str
    urgency: str
    service_id: str
    created_at: datetime
    last_status_change_at: Optional[datetime] = None
    html_url: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "PagerDutyIncident":
        """Create from PagerDuty API response."""
        return cls(
            id=data["id"],
            incident_number=data.get("incident_number", 0),
            title=data.get("title", ""),
            status=data.get("status", ""),
            urgency=data.get("urgency", ""),
            service_id=data.get("service", {}).get("id", ""),
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
            ),
            last_status_change_at=datetime.fromisoformat(
                data["last_status_change_at"].replace("Z", "+00:00")
            ) if data.get("last_status_change_at") else None,
            html_url=data.get("html_url"),
        )


class PagerDutyConfig(BaseModel):
    """PagerDuty-specific configuration."""
    
    # Integration key (routing key) for Events API v2
    integration_key: str
    
    # Optional: API token for REST API (for resolving, etc.)
    api_token: Optional[str] = None
    
    # Service ID for REST API operations
    service_id: Optional[str] = None
    
    # Auto-resolve settings
    auto_resolve_on_recovery: bool = True
    
    # Priority mapping
    priority_to_urgency: Dict[str, str] = Field(default_factory=lambda: {
        "critical": "high",
        "urgent": "high",
        "high": "high",
        "normal": "low",
        "low": "low",
    })
    
    # Include only certain notification types
    notification_types: List[str] = Field(default_factory=lambda: [
        "alert",
        "incident",
        "action_required",
    ])


class PagerDutyIntegration(NotificationHandler):
    """
    PagerDuty notification handler.
    
    Supports:
    - Events API v2 (trigger/acknowledge/resolve)
    - Incident management via REST API
    - Deduplication
    - Priority mapping
    
    Example:
        pagerduty = PagerDutyIntegration()
        
        config = ChannelConfig(
            tenant_id="tenant-123",
            channel=NotificationChannel.PAGERDUTY,
            name="PagerDuty",
            config={
                "integration_key": "xxxx",
                "api_token": "yyyy",  # Optional
            },
        )
        
        result = await pagerduty.send(notification, config)
    """
    
    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"
    REST_API_URL = "https://api.pagerduty.com"
    
    def __init__(self, timeout: float = 10.0):
        """Initialize PagerDutyIntegration.
        
        Args:
            timeout: HTTP request timeout
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.PAGERDUTY
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def send(
        self,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send notification to PagerDuty.
        
        Args:
            notification: Notification to send
            config: Channel configuration
            
        Returns:
            DeliveryResult
        """
        pd_config = PagerDutyConfig(**config.config)
        
        # Check if notification type should be sent to PagerDuty
        if notification.notification_type.value not in pd_config.notification_types:
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.PAGERDUTY,
                success=True,
                status=NotificationStatus.SKIPPED,
            )
        
        # Build event
        event = PagerDutyEvent.from_notification(notification, pd_config.integration_key)
        payload = event.to_api_payload()
        
        try:
            client = await self._get_client()
            
            response = await client.post(
                self.EVENTS_API_URL,
                json=payload,
            )
            
            if response.status_code in (200, 201, 202):
                data = response.json()
                
                return DeliveryResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.PAGERDUTY,
                    success=True,
                    status=NotificationStatus.DELIVERED,
                    provider_id=data.get("dedup_key"),
                    provider_response=data,
                    delivered_at=datetime.now(timezone.utc),
                )
            
            error_data = {}
            try:
                error_data = response.json()
            except json.JSONDecodeError:
                pass
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.PAGERDUTY,
                success=False,
                status=NotificationStatus.FAILED,
                error_code=f"http_{response.status_code}",
                error_message=error_data.get("message", response.text[:500]),
                provider_response=error_data,
            )
            
        except Exception as e:
            logger.error(
                "PagerDuty send failed",
                notification_id=notification.id,
                error=str(e),
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.PAGERDUTY,
                success=False,
                status=NotificationStatus.FAILED,
                error_code="exception",
                error_message=str(e),
            )
    
    async def resolve_incident(
        self,
        config: ChannelConfig,
        dedup_key: str,
    ) -> bool:
        """Resolve a PagerDuty incident by dedup key.
        
        Args:
            config: Channel configuration
            dedup_key: Deduplication key
            
        Returns:
            True if resolved
        """
        pd_config = PagerDutyConfig(**config.config)
        
        payload = {
            "routing_key": pd_config.integration_key,
            "event_action": "resolve",
            "dedup_key": dedup_key,
        }
        
        try:
            client = await self._get_client()
            
            response = await client.post(
                self.EVENTS_API_URL,
                json=payload,
            )
            
            return response.status_code in (200, 201, 202)
            
        except Exception as e:
            logger.error(
                "PagerDuty resolve failed",
                dedup_key=dedup_key,
                error=str(e),
            )
            return False
    
    async def acknowledge_incident(
        self,
        config: ChannelConfig,
        dedup_key: str,
    ) -> bool:
        """Acknowledge a PagerDuty incident by dedup key.
        
        Args:
            config: Channel configuration
            dedup_key: Deduplication key
            
        Returns:
            True if acknowledged
        """
        pd_config = PagerDutyConfig(**config.config)
        
        payload = {
            "routing_key": pd_config.integration_key,
            "event_action": "acknowledge",
            "dedup_key": dedup_key,
        }
        
        try:
            client = await self._get_client()
            
            response = await client.post(
                self.EVENTS_API_URL,
                json=payload,
            )
            
            return response.status_code in (200, 201, 202)
            
        except Exception as e:
            logger.error(
                "PagerDuty acknowledge failed",
                dedup_key=dedup_key,
                error=str(e),
            )
            return False
    
    async def get_incidents(
        self,
        config: ChannelConfig,
        statuses: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[PagerDutyIncident]:
        """Get incidents from PagerDuty REST API.
        
        Args:
            config: Channel configuration
            statuses: Filter by status (triggered, acknowledged, resolved)
            since: Start time
            until: End time
            
        Returns:
            List of incidents
        """
        pd_config = PagerDutyConfig(**config.config)
        
        if not pd_config.api_token:
            logger.warning("PagerDuty API token not configured")
            return []
        
        params: Dict[str, Any] = {}
        
        if statuses:
            params["statuses[]"] = statuses
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if pd_config.service_id:
            params["service_ids[]"] = [pd_config.service_id]
        
        try:
            client = await self._get_client()
            
            response = await client.get(
                f"{self.REST_API_URL}/incidents",
                headers={
                    "Authorization": f"Token token={pd_config.api_token}",
                    "Content-Type": "application/json",
                },
                params=params,
            )
            
            if response.status_code == 200:
                data = response.json()
                return [
                    PagerDutyIncident.from_api_response(inc)
                    for inc in data.get("incidents", [])
                ]
            
            logger.warning(
                "PagerDuty get incidents failed",
                status_code=response.status_code,
            )
            return []
            
        except Exception as e:
            logger.error(
                "PagerDuty get incidents failed",
                error=str(e),
            )
            return []
    
    async def health_check(self, config: ChannelConfig) -> bool:
        """Check PagerDuty connectivity."""
        pd_config = PagerDutyConfig(**config.config)
        
        # For Events API, we can only really validate the key format
        if not pd_config.integration_key:
            return False
        
        # If we have an API token, we can test the REST API
        if pd_config.api_token:
            try:
                client = await self._get_client()
                
                response = await client.get(
                    f"{self.REST_API_URL}/abilities",
                    headers={
                        "Authorization": f"Token token={pd_config.api_token}",
                        "Content-Type": "application/json",
                    },
                )
                
                return response.status_code == 200
                
            except Exception:
                return False
        
        # Assume valid if integration key is present
        return True
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
