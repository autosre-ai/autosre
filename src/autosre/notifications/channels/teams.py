"""Microsoft Teams Integration for AutoSRE V2 Notifications.

Provides Teams messaging with:
- Adaptive Cards
- Incoming webhooks
- Rich formatting
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class TeamsCard(BaseModel):
    """Microsoft Teams Adaptive Card."""
    
    title: str
    summary: str
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    potential_actions: List[Dict[str, Any]] = Field(default_factory=list)
    theme_color: str = "0076D7"  # Blue
    
    @classmethod
    def from_notification(cls, notification: Notification) -> "TeamsCard":
        """Create TeamsCard from a Notification."""
        # Determine color based on priority
        color_map = {
            NotificationPriority.CRITICAL: "FF0000",  # Red
            NotificationPriority.URGENT: "FF4500",  # Orange Red
            NotificationPriority.HIGH: "FFA500",  # Orange
            NotificationPriority.NORMAL: "0076D7",  # Blue
            NotificationPriority.LOW: "808080",  # Gray
        }
        
        sections = []
        
        # Main section
        main_section: Dict[str, Any] = {
            "activityTitle": notification.title,
            "activitySubtitle": notification.source,
            "text": notification.message,
            "markdown": True,
        }
        sections.append(main_section)
        
        # Details section
        if notification.details:
            facts = [
                {"name": k, "value": str(v)}
                for k, v in list(notification.details.items())[:8]
            ]
            
            if facts:
                sections.append({
                    "title": "Details",
                    "facts": facts,
                })
        
        # Metadata section
        sections.append({
            "facts": [
                {"name": "Priority", "value": notification.priority.value.title()},
                {"name": "Type", "value": notification.notification_type.value.replace("_", " ").title()},
                {"name": "Time", "value": notification.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")},
            ],
        })
        
        # Actions
        actions = []
        
        if notification.source_url:
            actions.append({
                "@type": "OpenUri",
                "name": "View Details",
                "targets": [{"os": "default", "uri": notification.source_url}],
            })
        
        for action in notification.actions[:3]:
            if action.get("url"):
                actions.append({
                    "@type": "OpenUri",
                    "name": action.get("label", "Action"),
                    "targets": [{"os": "default", "uri": action["url"]}],
                })
        
        return cls(
            title=notification.title,
            summary=f"{notification.title}: {notification.message[:100]}",
            sections=sections,
            potential_actions=actions,
            theme_color=color_map.get(notification.priority, "0076D7"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Teams webhook payload (MessageCard format)."""
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": self.theme_color,
            "summary": self.summary,
            "sections": self.sections,
            "potentialAction": self.potential_actions,
        }
    
    def to_adaptive_card_payload(self) -> Dict[str, Any]:
        """Convert to Teams Adaptive Card format."""
        body: List[Dict[str, Any]] = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": self.title,
            },
        ]
        
        for section in self.sections:
            if "text" in section:
                body.append({
                    "type": "TextBlock",
                    "text": section["text"],
                    "wrap": True,
                })
            
            if "facts" in section:
                fact_set = {
                    "type": "FactSet",
                    "facts": [
                        {"title": f["name"], "value": f["value"]}
                        for f in section["facts"]
                    ],
                }
                body.append(fact_set)
        
        # Actions
        actions = []
        for action in self.potential_actions:
            if action.get("@type") == "OpenUri":
                targets = action.get("targets", [])
                url = targets[0].get("uri") if targets else ""
                actions.append({
                    "type": "Action.OpenUrl",
                    "title": action.get("name", "Action"),
                    "url": url,
                })
        
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": body,
        }
        
        if actions:
            card["actions"] = actions
        
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }


class TeamsMessage(BaseModel):
    """A simple Teams text message."""
    
    text: str
    title: Optional[str] = None
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Teams webhook payload."""
        if self.title:
            return {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "summary": self.title,
                "sections": [
                    {
                        "activityTitle": self.title,
                        "text": self.text,
                    }
                ],
            }
        return {"text": self.text}


class TeamsConfig(BaseModel):
    """Microsoft Teams-specific configuration."""
    
    webhook_url: str
    use_adaptive_cards: bool = True
    default_theme_color: str = "0076D7"


class TeamsIntegration(NotificationHandler):
    """
    Microsoft Teams notification handler.
    
    Supports:
    - Incoming webhooks
    - MessageCard format
    - Adaptive Cards
    - Rich formatting
    
    Example:
        teams = TeamsIntegration()
        
        config = ChannelConfig(
            tenant_id="tenant-123",
            channel=NotificationChannel.TEAMS,
            name="Teams",
            config={
                "webhook_url": "https://outlook.office.com/webhook/...",
            },
        )
        
        result = await teams.send(notification, config)
    """
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.TEAMS
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def send(
        self,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send notification to Teams."""
        teams_config = TeamsConfig(**config.config)
        
        # Build card
        card = TeamsCard.from_notification(notification)
        
        # Use appropriate format
        if teams_config.use_adaptive_cards:
            payload = card.to_adaptive_card_payload()
        else:
            payload = card.to_api_payload()
        
        try:
            client = await self._get_client()
            
            response = await client.post(
                teams_config.webhook_url,
                json=payload,
            )
            
            # Teams returns 1 (as text) on success, or JSON error
            if response.status_code == 200:
                return DeliveryResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.TEAMS,
                    success=True,
                    status=NotificationStatus.DELIVERED,
                    delivered_at=datetime.now(timezone.utc),
                )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.TEAMS,
                success=False,
                status=NotificationStatus.FAILED,
                error_code=f"http_{response.status_code}",
                error_message=response.text[:500],
            )
            
        except Exception as e:
            logger.error(
                "Teams send failed",
                notification_id=notification.id,
                error=str(e),
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.TEAMS,
                success=False,
                status=NotificationStatus.FAILED,
                error_code="exception",
                error_message=str(e),
            )
    
    async def health_check(self, config: ChannelConfig) -> bool:
        teams_config = TeamsConfig(**config.config)
        return bool(teams_config.webhook_url)
    
    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
