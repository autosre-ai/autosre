"""
Slack integration for AutoSRE V2.

Provides async Slack client with support for:
- Message posting with Block Kit
- Alert notifications with rich formatting
- Investigation updates and progress
- Interactive action approval buttons
- Webhook signature validation
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.core.alert import Alert, AlertSeverity, AlertStatus
from autosre.core.models import Action, ActionStatus, ActionType, Investigation, InvestigationStatus
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================


class MessageColor(str, Enum):
    """Attachment color constants."""

    GOOD = "good"
    WARNING = "warning"
    DANGER = "danger"
    DEFAULT = "#808080"

    @classmethod
    def from_severity(cls, severity: AlertSeverity) -> str:
        """Map alert severity to color."""
        return {
            AlertSeverity.CRITICAL: "#dc3545",  # Red
            AlertSeverity.HIGH: "#fd7e14",  # Orange
            AlertSeverity.MEDIUM: "#ffc107",  # Yellow
            AlertSeverity.LOW: "#17a2b8",  # Cyan
            AlertSeverity.INFO: "#6c757d",  # Gray
        }.get(severity, cls.DEFAULT.value)


class ButtonStyle(str, Enum):
    """Button styles for action blocks."""

    PRIMARY = "primary"
    DANGER = "danger"


class Block(BaseModel):
    """Base block model."""

    type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to Slack API format."""
        return self.model_dump(exclude_none=True, by_alias=True)


class TextObject(BaseModel):
    """Text object for blocks."""

    type: str = "mrkdwn"
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


class HeaderBlock(Block):
    """Header block."""

    type: str = "header"
    text: TextObject

    @classmethod
    def create(cls, text: str) -> HeaderBlock:
        return cls(text=TextObject(type="plain_text", text=text))

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text.to_dict()}


class DividerBlock(Block):
    """Divider block."""

    type: str = "divider"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type}


class SectionBlock(Block):
    """Section block with optional accessory."""

    type: str = "section"
    text: TextObject | None = None
    fields: list[TextObject] | None = None
    accessory: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        text: str | None = None,
        fields: list[str] | None = None,
        accessory: dict[str, Any] | None = None,
    ) -> SectionBlock:
        return cls(
            text=TextObject(text=text) if text else None,
            fields=[TextObject(text=f) for f in fields] if fields else None,
            accessory=accessory,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.text:
            result["text"] = self.text.to_dict()
        if self.fields:
            result["fields"] = [f.to_dict() for f in self.fields]
        if self.accessory:
            result["accessory"] = self.accessory
        return result


class ContextBlock(Block):
    """Context block for metadata."""

    type: str = "context"
    elements: list[TextObject]

    @classmethod
    def create(cls, texts: list[str]) -> ContextBlock:
        return cls(elements=[TextObject(text=t) for t in texts])

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "elements": [e.to_dict() for e in self.elements],
        }


class Button(BaseModel):
    """Button element for actions block."""

    type: str = "button"
    text: TextObject
    action_id: str
    value: str | None = None
    style: ButtonStyle | None = None
    confirm: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        text: str,
        action_id: str,
        value: str | None = None,
        style: ButtonStyle | None = None,
        confirm_title: str | None = None,
        confirm_text: str | None = None,
    ) -> Button:
        confirm = None
        if confirm_title and confirm_text:
            confirm = {
                "title": {"type": "plain_text", "text": confirm_title},
                "text": {"type": "mrkdwn", "text": confirm_text},
                "confirm": {"type": "plain_text", "text": "Confirm"},
                "deny": {"type": "plain_text", "text": "Cancel"},
            }
        return cls(
            text=TextObject(type="plain_text", text=text),
            action_id=action_id,
            value=value,
            style=style,
            confirm=confirm,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "type": self.type,
            "text": self.text.to_dict(),
            "action_id": self.action_id,
        }
        if self.value:
            result["value"] = self.value
        if self.style:
            result["style"] = self.style.value
        if self.confirm:
            result["confirm"] = self.confirm
        return result


class SelectOption(BaseModel):
    """Option for select menus."""

    text: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": {"type": "plain_text", "text": self.text},
            "value": self.value,
        }


class Select(BaseModel):
    """Static select menu element."""

    type: str = "static_select"
    action_id: str
    placeholder: str
    options: list[SelectOption]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "action_id": self.action_id,
            "placeholder": {"type": "plain_text", "text": self.placeholder},
            "options": [o.to_dict() for o in self.options],
        }


class ActionsBlock(Block):
    """Actions block containing interactive elements."""

    type: str = "actions"
    elements: list[Button | Select]
    block_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "elements": [e.to_dict() for e in self.elements],
        }
        if self.block_id:
            result["block_id"] = self.block_id
        return result


class Field(BaseModel):
    """Attachment field (legacy format)."""

    title: str
    value: str
    short: bool = True


class Attachment(BaseModel):
    """Message attachment (legacy but still useful)."""

    fallback: str
    color: str = MessageColor.DEFAULT.value
    title: str | None = None
    title_link: str | None = None
    text: str | None = None
    fields: list[Field] | None = None
    footer: str | None = None
    ts: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "fallback": self.fallback,
            "color": self.color,
        }
        if self.title:
            result["title"] = self.title
        if self.title_link:
            result["title_link"] = self.title_link
        if self.text:
            result["text"] = self.text
        if self.fields:
            result["fields"] = [
                {"title": f.title, "value": f.value, "short": f.short}
                for f in self.fields
            ]
        if self.footer:
            result["footer"] = self.footer
        if self.ts:
            result["ts"] = self.ts
        return result


class Message(BaseModel):
    """Complete Slack message."""

    channel: str
    text: str
    blocks: list[Block] | None = None
    attachments: list[Attachment] | None = None
    thread_ts: str | None = None
    reply_broadcast: bool = False
    unfurl_links: bool = False
    unfurl_media: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "channel": self.channel,
            "text": self.text,
            "unfurl_links": self.unfurl_links,
            "unfurl_media": self.unfurl_media,
        }
        if self.blocks:
            result["blocks"] = [b.to_dict() for b in self.blocks]
        if self.attachments:
            result["attachments"] = [a.to_dict() for a in self.attachments]
        if self.thread_ts:
            result["thread_ts"] = self.thread_ts
            result["reply_broadcast"] = self.reply_broadcast
        return result


class SlackInteraction(BaseModel):
    """Parsed Slack interaction payload."""

    type: str
    user_id: str
    user_name: str
    channel_id: str
    action_id: str
    action_value: str | None = None
    trigger_id: str
    response_url: str
    message_ts: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SlackEvent(BaseModel):
    """Parsed Slack event (from Events API)."""

    type: str
    event_type: str
    user_id: str | None = None
    channel_id: str | None = None
    text: str | None = None
    ts: str | None = None
    thread_ts: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Rate Limiter
# ============================================================================


class RateLimiter:
    """Token bucket rate limiter for Slack API."""

    def __init__(
        self,
        requests_per_minute: int = 50,
        burst_size: int = 10,
    ):
        self.rate = requests_per_minute / 60.0  # requests per second
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request can be made."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug("Rate limited", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


# ============================================================================
# Slack Client
# ============================================================================


class SlackError(Exception):
    """Base Slack API error."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class SlackRateLimitError(SlackError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(f"Rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class SlackNotifier:
    """
    Async Slack client for AutoSRE notifications.

    Provides methods for sending alerts, investigation updates,
    and interactive action approvals.
    """

    API_BASE = "https://slack.com/api"

    def __init__(
        self,
        token: str,
        signing_secret: str | None = None,
        default_channel: str | None = None,
        requests_per_minute: int = 50,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Slack client.

        Args:
            token: Slack Bot User OAuth Token (xoxb-...)
            signing_secret: Slack signing secret for webhook validation
            default_channel: Default channel for notifications
            requests_per_minute: Rate limit for API calls
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.token = token
        self.signing_secret = signing_secret
        self.default_channel = default_channel
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)
        self._interaction_handlers: dict[str, Callable] = {}

    async def __aenter__(self) -> SlackNotifier:
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an API request with retries and rate limiting.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            API response data

        Raises:
            SlackError: If the request fails after retries
        """
        client = await self._ensure_client()
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            await self._rate_limiter.acquire()

            try:
                response = await client.request(method, endpoint, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 30))
                    logger.warning(
                        "Slack rate limit hit",
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                # Slack returns ok: false for API errors
                if not data.get("ok"):
                    error = data.get("error", "unknown_error")
                    logger.error("Slack API error", error=error)
                    raise SlackError(f"Slack API error: {error}", error_code=error)

                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "Slack request failed",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
            except SlackError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Slack request error",
                    error=str(e),
                    attempt=attempt + 1,
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2**attempt)
                await asyncio.sleep(delay)

        raise SlackError(f"Request failed after {self.max_retries} attempts: {last_error}")

    # ========================================================================
    # Core Messaging
    # ========================================================================

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[Block] | None = None,
        attachments: list[Attachment] | None = None,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
    ) -> dict[str, Any]:
        """
        Send a message to a channel.

        Args:
            channel: Channel ID or name
            text: Plain text fallback
            blocks: Block Kit blocks
            attachments: Message attachments
            thread_ts: Thread timestamp for replies
            reply_broadcast: Also post reply to channel

        Returns:
            API response with ts (timestamp) and channel
        """
        message = Message(
            channel=channel,
            text=text,
            blocks=blocks,
            attachments=attachments,
            thread_ts=thread_ts,
            reply_broadcast=reply_broadcast,
        )

        response = await self._request("POST", "/chat.postMessage", json=message.to_dict())

        logger.info(
            "Message sent",
            channel=channel,
            ts=response.get("ts"),
        )

        return response

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[Block] | None = None,
        attachments: list[Attachment] | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing message.

        Args:
            channel: Channel ID
            ts: Message timestamp
            text: Updated text
            blocks: Updated blocks
            attachments: Updated attachments

        Returns:
            API response
        """
        payload: dict[str, Any] = {
            "channel": channel,
            "ts": ts,
            "text": text,
        }

        if blocks:
            payload["blocks"] = [b.to_dict() for b in blocks]
        if attachments:
            payload["attachments"] = [a.to_dict() for a in attachments]

        return await self._request("POST", "/chat.update", json=payload)

    async def delete_message(self, channel: str, ts: str) -> dict[str, Any]:
        """Delete a message."""
        return await self._request(
            "POST",
            "/chat.delete",
            json={"channel": channel, "ts": ts},
        )

    async def add_reaction(self, channel: str, ts: str, emoji: str) -> dict[str, Any]:
        """Add a reaction to a message."""
        return await self._request(
            "POST",
            "/reactions.add",
            json={"channel": channel, "timestamp": ts, "name": emoji},
        )

    # ========================================================================
    # Alert Notifications
    # ========================================================================

    async def send_alert_notification(
        self,
        alert: Alert,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """
        Send an alert notification with rich formatting.

        Args:
            alert: Alert to notify about
            channel: Target channel (uses default if not specified)

        Returns:
            API response
        """
        channel = channel or self.default_channel
        if not channel:
            raise ValueError("No channel specified and no default channel set")

        severity_emoji = {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.HIGH: "🟠",
            AlertSeverity.MEDIUM: "🟡",
            AlertSeverity.LOW: "🔵",
            AlertSeverity.INFO: "⚪",
        }

        status_emoji = {
            AlertStatus.FIRING: "🔥",
            AlertStatus.ACKNOWLEDGED: "👀",
            AlertStatus.INVESTIGATING: "🔍",
            AlertStatus.RESOLVED: "✅",
            AlertStatus.SILENCED: "🔇",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")
        status = status_emoji.get(alert.status, "")

        blocks: list[Block] = [
            HeaderBlock.create(f"{emoji} {alert.name}"),
            SectionBlock.create(
                text=alert.description or "_No description available_",
            ),
            SectionBlock.create(
                fields=[
                    f"*Severity:*\n{alert.severity.value.upper()}",
                    f"*Status:*\n{status} {alert.status.value}",
                    f"*Service:*\n{alert.service or 'N/A'}",
                    f"*Namespace:*\n{alert.namespace or 'N/A'}",
                ],
            ),
        ]

        # Add labels if present
        if alert.labels:
            label_text = "\n".join(
                f"• `{k}`: {v}"
                for k, v in list(alert.labels.items())[:10]  # Limit labels
            )
            blocks.append(SectionBlock.create(text=f"*Labels:*\n{label_text}"))

        # Add context with timing
        duration_str = "N/A"
        if alert.duration:
            minutes = int(alert.duration / 60)
            if minutes > 60:
                duration_str = f"{minutes // 60}h {minutes % 60}m"
            else:
                duration_str = f"{minutes}m"

        blocks.append(
            ContextBlock.create([
                f"🕐 Started: {alert.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"⏱️ Duration: {duration_str}",
                f"📡 Source: {alert.source.value}",
            ])
        )

        blocks.append(DividerBlock())

        # Add action buttons for active alerts
        if alert.is_active:
            blocks.append(
                ActionsBlock(
                    block_id=f"alert_actions_{alert.id}",
                    elements=[
                        Button.create(
                            text="Acknowledge",
                            action_id="ack_alert",
                            value=alert.id,
                            style=ButtonStyle.PRIMARY,
                        ),
                        Button.create(
                            text="Investigate",
                            action_id="investigate_alert",
                            value=alert.id,
                        ),
                        Button.create(
                            text="Silence (2h)",
                            action_id="silence_alert",
                            value=alert.id,
                        ),
                    ],
                )
            )

        return await self.send_message(
            channel=channel,
            text=f"{emoji} Alert: {alert.name} [{alert.severity.value.upper()}]",
            blocks=blocks,
        )

    # ========================================================================
    # Investigation Updates
    # ========================================================================

    async def send_investigation_update(
        self,
        investigation: Investigation,
        channel: str | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """
        Send an investigation status update.

        Args:
            investigation: Investigation to report on
            channel: Target channel
            thread_ts: Thread to reply to

        Returns:
            API response
        """
        channel = channel or self.default_channel
        if not channel:
            raise ValueError("No channel specified and no default channel set")

        status_emoji = {
            InvestigationStatus.PENDING: "⏳",
            InvestigationStatus.IN_PROGRESS: "🔄",
            InvestigationStatus.WAITING_FOR_DATA: "📊",
            InvestigationStatus.WAITING_FOR_APPROVAL: "⏸️",
            InvestigationStatus.COMPLETED: "✅",
            InvestigationStatus.FAILED: "❌",
            InvestigationStatus.CANCELLED: "🚫",
        }

        emoji = status_emoji.get(investigation.status, "🔍")

        blocks: list[Block] = [
            HeaderBlock.create(f"{emoji} Investigation: {investigation.title}"),
            SectionBlock.create(
                fields=[
                    f"*Status:*\n{investigation.status.value.replace('_', ' ').title()}",
                    f"*Observations:*\n{len(investigation.observations)}",
                    f"*Hypotheses:*\n{len(investigation.hypotheses)}",
                    f"*Actions:*\n{len(investigation.actions)}",
                ],
            ),
        ]

        # Add objective if present
        if investigation.objective:
            blocks.append(
                SectionBlock.create(text=f"*Objective:*\n{investigation.objective}")
            )

        # Add recent observations summary
        recent_obs = investigation.observations[-3:] if investigation.observations else []
        if recent_obs:
            obs_text = "\n".join(
                f"• [{o.type.value}] {o.description[:100]}..."
                if len(o.description) > 100
                else f"• [{o.type.value}] {o.description}"
                for o in recent_obs
            )
            blocks.append(SectionBlock.create(text=f"*Recent Observations:*\n{obs_text}"))

        # Add confirmed hypotheses
        confirmed = investigation.get_confirmed_hypotheses()
        if confirmed:
            hyp_text = "\n".join(f"• {h.statement}" for h in confirmed[:3])
            blocks.append(SectionBlock.create(text=f"*Confirmed Hypotheses:*\n{hyp_text}"))

        # Add context
        duration = "N/A"
        if investigation.started_at:
            elapsed = (datetime.now(timezone.utc) - investigation.started_at).total_seconds()
            minutes = int(elapsed / 60)
            duration = f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"

        blocks.append(
            ContextBlock.create([
                f"🆔 ID: {investigation.id}",
                f"⏱️ Duration: {duration}",
                f"🤖 LLM Calls: {investigation.llm_calls}",
            ])
        )

        return await self.send_message(
            channel=channel,
            text=f"{emoji} Investigation Update: {investigation.title}",
            blocks=blocks,
            thread_ts=thread_ts,
        )

    # ========================================================================
    # Action Approval
    # ========================================================================

    async def send_action_approval(
        self,
        action: Action,
        investigation_id: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """
        Send an action approval request.

        Args:
            action: Action requiring approval
            investigation_id: Related investigation ID
            channel: Target channel

        Returns:
            API response
        """
        channel = channel or self.default_channel
        if not channel:
            raise ValueError("No channel specified and no default channel set")

        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }

        type_emoji = {
            ActionType.DIAGNOSTIC: "🔍",
            ActionType.REMEDIATION: "🔧",
            ActionType.ESCALATION: "📢",
            ActionType.NOTIFICATION: "📬",
            ActionType.ROLLBACK: "⏪",
            ActionType.SCALE: "📈",
            ActionType.RESTART: "🔄",
            ActionType.CONFIG_CHANGE: "⚙️",
        }

        emoji = type_emoji.get(action.type, "⚡")
        risk = risk_emoji.get(action.risk_level, "⚪")

        blocks: list[Block] = [
            HeaderBlock.create(f"🔐 Action Approval Required"),
            SectionBlock.create(
                text=f"*{emoji} {action.name}*\n{action.description}",
            ),
            SectionBlock.create(
                fields=[
                    f"*Type:*\n{action.type.value.replace('_', ' ').title()}",
                    f"*Risk Level:*\n{risk} {action.risk_level.upper()}",
                    f"*Destructive:*\n{'⚠️ Yes' if action.is_destructive else 'No'}",
                    f"*Tool:*\n{action.tool or 'N/A'}",
                ],
            ),
        ]

        # Add command/parameters if present
        if action.command:
            blocks.append(
                SectionBlock.create(text=f"*Command:*\n```{action.command}```")
            )

        if action.parameters:
            params_text = "\n".join(
                f"• `{k}`: {v}" for k, v in action.parameters.items()
            )
            blocks.append(SectionBlock.create(text=f"*Parameters:*\n{params_text}"))

        blocks.append(DividerBlock())

        # Action buttons with confirmation for dangerous actions
        confirm_text = None
        if action.is_destructive or action.risk_level in ("high", "critical"):
            confirm_text = f"Are you sure you want to execute this {action.risk_level} risk action?"

        blocks.append(
            ActionsBlock(
                block_id=f"action_approval_{action.id}",
                elements=[
                    Button.create(
                        text="✅ Approve",
                        action_id="approve_action",
                        value=str(action.id),
                        style=ButtonStyle.PRIMARY,
                        confirm_title="Confirm Approval" if confirm_text else None,
                        confirm_text=confirm_text,
                    ),
                    Button.create(
                        text="❌ Reject",
                        action_id="reject_action",
                        value=str(action.id),
                        style=ButtonStyle.DANGER,
                    ),
                    Button.create(
                        text="ℹ️ Details",
                        action_id="action_details",
                        value=str(action.id),
                    ),
                ],
            )
        )

        # Add context
        context_items = [f"🆔 Action ID: {action.id}"]
        if investigation_id:
            context_items.append(f"🔍 Investigation: {investigation_id}")

        blocks.append(ContextBlock.create(context_items))

        return await self.send_message(
            channel=channel,
            text=f"🔐 Action Approval Required: {action.name}",
            blocks=blocks,
        )

    async def post_action_buttons(
        self,
        actions: list[Action],
        channel: str | None = None,
        title: str = "Available Actions",
    ) -> dict[str, Any]:
        """
        Post a list of available actions with buttons.

        Args:
            actions: List of actions to display
            channel: Target channel
            title: Message title

        Returns:
            API response
        """
        channel = channel or self.default_channel
        if not channel:
            raise ValueError("No channel specified and no default channel set")

        blocks: list[Block] = [HeaderBlock.create(title)]

        for action in actions[:10]:  # Limit to 10 actions
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
            risk = risk_emoji.get(action.risk_level, "⚪")

            blocks.append(
                SectionBlock(
                    text=TextObject(text=f"*{action.name}*\n{action.description}"),
                    accessory=Button.create(
                        text="Execute",
                        action_id=f"execute_action_{action.id}",
                        value=str(action.id),
                        style=ButtonStyle.DANGER if action.is_destructive else None,
                    ).to_dict(),
                )
            )
            blocks.append(
                ContextBlock.create([
                    f"Type: {action.type.value}",
                    f"Risk: {risk} {action.risk_level}",
                ])
            )

        return await self.send_message(
            channel=channel,
            text=title,
            blocks=blocks,
        )

    # ========================================================================
    # Interaction Handling
    # ========================================================================

    def register_interaction_handler(
        self,
        action_id: str,
        handler: Callable[[SlackInteraction], Any],
    ) -> None:
        """
        Register a handler for interactive component actions.

        Args:
            action_id: Action ID to handle (supports wildcards with *)
            handler: Async or sync function to handle the interaction
        """
        self._interaction_handlers[action_id] = handler

    async def handle_interaction(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle an incoming Slack interaction.

        Args:
            payload: Raw interaction payload

        Returns:
            Response to send back, or None
        """
        interaction_type = payload.get("type")

        if interaction_type == "block_actions":
            actions = payload.get("actions", [])
            if not actions:
                return None

            action = actions[0]
            action_id = action.get("action_id", "")

            interaction = SlackInteraction(
                type=interaction_type,
                user_id=payload.get("user", {}).get("id", ""),
                user_name=payload.get("user", {}).get("name", ""),
                channel_id=payload.get("channel", {}).get("id", ""),
                action_id=action_id,
                action_value=action.get("value"),
                trigger_id=payload.get("trigger_id", ""),
                response_url=payload.get("response_url", ""),
                message_ts=payload.get("message", {}).get("ts", ""),
                raw_payload=payload,
            )

            # Find handler (exact match or wildcard)
            handler = self._interaction_handlers.get(action_id)
            if not handler:
                # Check for wildcard patterns
                for pattern, h in self._interaction_handlers.items():
                    if pattern.endswith("*") and action_id.startswith(pattern[:-1]):
                        handler = h
                        break

            if handler:
                logger.info(
                    "Handling interaction",
                    action_id=action_id,
                    user=interaction.user_name,
                )
                try:
                    if asyncio.iscoroutinefunction(handler):
                        return await handler(interaction)
                    return handler(interaction)
                except Exception as e:
                    logger.error("Interaction handler error", error=str(e))
                    raise
            else:
                logger.warning("No handler for action", action_id=action_id)

        return None

    # ========================================================================
    # Webhook Validation
    # ========================================================================

    def verify_webhook_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str,
    ) -> bool:
        """
        Verify Slack webhook signature.

        Args:
            body: Raw request body
            timestamp: X-Slack-Request-Timestamp header
            signature: X-Slack-Signature header

        Returns:
            True if signature is valid
        """
        if not self.signing_secret:
            logger.warning("No signing secret configured, skipping verification")
            return True

        # Check timestamp to prevent replay attacks
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - request_time) > 60 * 5:  # 5 minute window
                logger.warning("Request timestamp too old", delta=current_time - request_time)
                return False
        except ValueError:
            return False

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(expected_sig, signature)

    def parse_event(self, payload: dict[str, Any]) -> SlackEvent | None:
        """
        Parse a Slack Events API payload.

        Args:
            payload: Raw event payload

        Returns:
            Parsed event or None
        """
        # Handle URL verification challenge
        if payload.get("type") == "url_verification":
            return None

        event = payload.get("event", {})
        event_type = event.get("type", "")

        return SlackEvent(
            type=payload.get("type", ""),
            event_type=event_type,
            user_id=event.get("user"),
            channel_id=event.get("channel"),
            text=event.get("text"),
            ts=event.get("ts"),
            thread_ts=event.get("thread_ts"),
            raw_payload=payload,
        )

    # ========================================================================
    # Utilities
    # ========================================================================

    async def get_channel_info(self, channel: str) -> dict[str, Any]:
        """Get information about a channel."""
        return await self._request(
            "GET",
            "/conversations.info",
            params={"channel": channel},
        )

    async def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List channels the bot has access to."""
        response = await self._request(
            "GET",
            "/conversations.list",
            params={"types": types, "limit": limit},
        )
        return response.get("channels", [])

    async def check_connection(self) -> bool:
        """Check if Slack connection is working."""
        try:
            response = await self._request("GET", "/auth.test")
            return response.get("ok", False)
        except Exception as e:
            logger.warning("Slack connection check failed", error=str(e))
            return False
