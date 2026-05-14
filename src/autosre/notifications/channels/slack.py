"""Slack Integration for AutoSRE V2 Notifications.

Provides rich Slack messaging with:
- Block Kit formatting
- Interactive messages
- Thread support
- Channel/DM routing
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
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class SlackBlockType(str, Enum):
    """Slack Block Kit block types."""
    
    SECTION = "section"
    HEADER = "header"
    DIVIDER = "divider"
    ACTIONS = "actions"
    CONTEXT = "context"
    IMAGE = "image"


class SlackTextType(str, Enum):
    """Slack text object types."""
    
    PLAIN = "plain_text"
    MARKDOWN = "mrkdwn"


class SlackBlock(BaseModel):
    """A Slack Block Kit block."""
    
    type: SlackBlockType
    text: Optional[Dict[str, Any]] = None
    accessory: Optional[Dict[str, Any]] = None
    elements: Optional[List[Dict[str, Any]]] = None
    fields: Optional[List[Dict[str, Any]]] = None
    block_id: Optional[str] = None
    
    @classmethod
    def header(cls, text: str) -> "SlackBlock":
        """Create a header block."""
        return cls(
            type=SlackBlockType.HEADER,
            text={"type": SlackTextType.PLAIN.value, "text": text[:150]},
        )
    
    @classmethod
    def section(
        cls,
        text: str,
        markdown: bool = True,
        fields: Optional[List[str]] = None,
    ) -> "SlackBlock":
        """Create a section block."""
        block = cls(
            type=SlackBlockType.SECTION,
            text={
                "type": SlackTextType.MARKDOWN.value if markdown else SlackTextType.PLAIN.value,
                "text": text[:3000],
            },
        )
        
        if fields:
            block.fields = [
                {"type": SlackTextType.MARKDOWN.value, "text": f[:2000]}
                for f in fields
            ]
        
        return block
    
    @classmethod
    def divider(cls) -> "SlackBlock":
        """Create a divider block."""
        return cls(type=SlackBlockType.DIVIDER)
    
    @classmethod
    def context(cls, elements: List[str]) -> "SlackBlock":
        """Create a context block."""
        return cls(
            type=SlackBlockType.CONTEXT,
            elements=[
                {"type": SlackTextType.MARKDOWN.value, "text": e[:2000]}
                for e in elements[:10]
            ],
        )
    
    @classmethod
    def actions(cls, buttons: List[Dict[str, str]]) -> "SlackBlock":
        """Create an actions block with buttons."""
        elements = []
        for button in buttons[:5]:
            element = {
                "type": "button",
                "text": {"type": SlackTextType.PLAIN.value, "text": button["text"][:75]},
                "action_id": button.get("action_id", str(uuid4())),
            }
            if "url" in button:
                element["url"] = button["url"]
            if "value" in button:
                element["value"] = button["value"]
            if "style" in button:
                element["style"] = button["style"]  # primary, danger
            elements.append(element)
        
        return cls(type=SlackBlockType.ACTIONS, elements=elements)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Slack API format."""
        result: Dict[str, Any] = {"type": self.type.value}
        
        if self.text:
            result["text"] = self.text
        if self.accessory:
            result["accessory"] = self.accessory
        if self.elements:
            result["elements"] = self.elements
        if self.fields:
            result["fields"] = self.fields
        if self.block_id:
            result["block_id"] = self.block_id
        
        return result


class SlackMessage(BaseModel):
    """A Slack message with rich formatting."""
    
    # Basic message
    text: str  # Fallback text
    
    # Rich content
    blocks: List[SlackBlock] = Field(default_factory=list)
    
    # Targeting
    channel: Optional[str] = None
    thread_ts: Optional[str] = None  # Reply to thread
    
    # Options
    unfurl_links: bool = False
    unfurl_media: bool = True
    mrkdwn: bool = True
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_notification(cls, notification: Notification) -> "SlackMessage":
        """Create SlackMessage from a Notification."""
        blocks = []
        
        # Header with title
        blocks.append(SlackBlock.header(notification.title))
        
        # Main message
        blocks.append(SlackBlock.section(notification.message))
        
        # Details as fields
        if notification.details:
            fields = []
            for key, value in list(notification.details.items())[:10]:
                fields.append(f"*{key}:* {value}")
            
            if fields:
                blocks.append(SlackBlock.divider())
                blocks.append(SlackBlock.section(
                    "Details",
                    fields=fields,
                ))
        
        # Actions
        if notification.actions or notification.source_url:
            buttons = []
            
            if notification.source_url:
                buttons.append({
                    "text": "View Details",
                    "url": notification.source_url,
                })
            
            for action in notification.actions[:4]:
                buttons.append({
                    "text": action.get("label", "Action"),
                    "url": action.get("url"),
                    "value": action.get("action"),
                })
            
            if buttons:
                blocks.append(SlackBlock.actions(buttons))
        
        # Footer context
        context_items = [
            f"Source: {notification.source}",
            f"Priority: {notification.priority.value}",
            f"Time: <!date^{int(notification.created_at.timestamp())}^{{date_short_pretty}} at {{time}}|{notification.created_at.isoformat()}>",
        ]
        blocks.append(SlackBlock.context(context_items))
        
        return cls(
            text=f"{notification.title}: {notification.message[:200]}",
            blocks=blocks,
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Slack API payload."""
        payload: Dict[str, Any] = {
            "text": self.text,
            "mrkdwn": self.mrkdwn,
            "unfurl_links": self.unfurl_links,
            "unfurl_media": self.unfurl_media,
        }
        
        if self.blocks:
            payload["blocks"] = [b.to_dict() for b in self.blocks]
        
        if self.channel:
            payload["channel"] = self.channel
        
        if self.thread_ts:
            payload["thread_ts"] = self.thread_ts
        
        if self.metadata:
            payload["metadata"] = self.metadata
        
        return payload


class SlackConfig(BaseModel):
    """Slack-specific configuration."""
    
    # Webhook or API
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None  # For API usage
    
    # Default channel
    default_channel: Optional[str] = None
    
    # Priority to channel mapping
    channel_routing: Dict[str, str] = Field(default_factory=dict)
    # e.g., {"critical": "#incidents", "high": "#alerts"}
    
    # Mention settings
    mention_users_on_critical: List[str] = Field(default_factory=list)
    mention_groups_on_critical: List[str] = Field(default_factory=list)


class SlackIntegration(NotificationHandler):
    """
    Slack notification handler.
    
    Supports:
    - Incoming webhooks
    - Bot API (with token)
    - Rich Block Kit messages
    - Thread replies
    - Priority-based routing
    
    Example:
        slack = SlackIntegration()
        
        config = ChannelConfig(
            tenant_id="tenant-123",
            channel=NotificationChannel.SLACK,
            name="Slack",
            config={
                "webhook_url": "https://hooks.slack.com/...",
                "default_channel": "#alerts",
            },
        )
        
        result = await slack.send(notification, config)
    """
    
    def __init__(self, timeout: float = 10.0):
        """Initialize SlackIntegration.
        
        Args:
            timeout: HTTP request timeout
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.SLACK
    
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
        """Send notification to Slack.
        
        Args:
            notification: Notification to send
            config: Channel configuration
            
        Returns:
            DeliveryResult
        """
        slack_config = SlackConfig(**config.config)
        
        # Build message
        message = SlackMessage.from_notification(notification)
        
        # Determine target channel
        target_channel = self._get_target_channel(notification, slack_config)
        if target_channel:
            message.channel = target_channel
        
        # Add mentions for critical
        if notification.priority == NotificationPriority.CRITICAL:
            mention_text = self._build_mentions(slack_config)
            if mention_text:
                message.text = f"{mention_text} {message.text}"
        
        # Get payload
        payload = message.to_api_payload()
        
        try:
            client = await self._get_client()
            
            if slack_config.webhook_url:
                # Use webhook
                response = await client.post(
                    slack_config.webhook_url,
                    json=payload,
                )
            elif slack_config.bot_token:
                # Use API
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {slack_config.bot_token}"},
                    json=payload,
                )
            else:
                return DeliveryResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.SLACK,
                    success=False,
                    status=NotificationStatus.FAILED,
                    error_code="no_credentials",
                    error_message="No webhook URL or bot token configured",
                )
            
            # Check response
            if response.status_code == 200:
                # Webhook returns "ok", API returns JSON
                try:
                    data = response.json()
                    if data.get("ok") is False:
                        return DeliveryResult(
                            notification_id=notification.id,
                            channel=NotificationChannel.SLACK,
                            success=False,
                            status=NotificationStatus.FAILED,
                            error_code=data.get("error", "unknown"),
                            error_message=data.get("error"),
                            provider_response=data,
                        )
                    
                    return DeliveryResult(
                        notification_id=notification.id,
                        channel=NotificationChannel.SLACK,
                        success=True,
                        status=NotificationStatus.DELIVERED,
                        provider_id=data.get("ts"),
                        provider_response=data,
                        delivered_at=datetime.now(timezone.utc),
                    )
                except json.JSONDecodeError:
                    # Webhook just returns "ok" text
                    if response.text == "ok":
                        return DeliveryResult(
                            notification_id=notification.id,
                            channel=NotificationChannel.SLACK,
                            success=True,
                            status=NotificationStatus.DELIVERED,
                            delivered_at=datetime.now(timezone.utc),
                        )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.SLACK,
                success=False,
                status=NotificationStatus.FAILED,
                error_code=f"http_{response.status_code}",
                error_message=response.text[:500],
            )
            
        except Exception as e:
            logger.error(
                "Slack send failed",
                notification_id=notification.id,
                error=str(e),
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.SLACK,
                success=False,
                status=NotificationStatus.FAILED,
                error_code="exception",
                error_message=str(e),
            )
    
    async def health_check(self, config: ChannelConfig) -> bool:
        """Check Slack connectivity."""
        slack_config = SlackConfig(**config.config)
        
        if slack_config.bot_token:
            try:
                client = await self._get_client()
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {slack_config.bot_token}"},
                )
                data = response.json()
                return data.get("ok", False)
            except Exception:
                return False
        
        # For webhooks, we can't easily test without sending
        return slack_config.webhook_url is not None
    
    def _get_target_channel(
        self,
        notification: Notification,
        config: SlackConfig,
    ) -> Optional[str]:
        """Determine target channel based on routing rules."""
        # Check priority routing
        priority_str = notification.priority.value
        if priority_str in config.channel_routing:
            return config.channel_routing[priority_str]
        
        # Check notification type routing
        type_str = notification.notification_type.value
        if type_str in config.channel_routing:
            return config.channel_routing[type_str]
        
        # Default channel
        return config.default_channel
    
    def _build_mentions(self, config: SlackConfig) -> str:
        """Build mention string for critical alerts."""
        mentions = []
        
        for user_id in config.mention_users_on_critical:
            mentions.append(f"<@{user_id}>")
        
        for group_id in config.mention_groups_on_critical:
            mentions.append(f"<!subteam^{group_id}>")
        
        return " ".join(mentions)
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
