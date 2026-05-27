"""
Slack Event Handlers

Standalone handler functions for Slack events. These can be used independently
or registered with the AutoSRESlackBot. Each handler is designed to be testable
in isolation.
"""

import asyncio
import re
from typing import Any, Callable, Optional

import structlog

from .messages import (
    format_investigation_start,
    format_error,
)

logger = structlog.get_logger(__name__)


# Type aliases for Slack handler functions
SayFn = Callable[..., Any]
AckFn = Callable[..., Any]
RespondFn = Callable[..., Any]
SlackClient = Any


class InvestigationHandler:
    """
    Handler context for managing investigations from Slack.
    
    Holds references to API client and tracking state needed
    for investigation management.
    """
    
    def __init__(
        self,
        api_client: Any,
        api_base_url: str,
    ):
        """
        Initialize the handler.
        
        Args:
            api_client: HTTP client for API calls
            api_base_url: Base URL for AutoSRE API
        """
        self.api_client = api_client
        self.api_base_url = api_base_url
        self._active_investigations: dict[str, dict[str, Any]] = {}
    
    def track_investigation(
        self,
        investigation_id: str,
        channel: str,
        thread_ts: Optional[str],
        user: str,
    ) -> None:
        """Track an active investigation for a Slack thread."""
        self._active_investigations[investigation_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "user": user,
            "started_at": asyncio.get_event_loop().time(),
        }
    
    def get_investigation(self, investigation_id: str) -> Optional[dict]:
        """Get tracking info for an investigation."""
        return self._active_investigations.get(investigation_id)
    
    def remove_investigation(self, investigation_id: str) -> None:
        """Remove an investigation from tracking."""
        self._active_investigations.pop(investigation_id, None)
    
    def find_investigation_by_thread(
        self,
        channel: str,
        thread_ts: str,
    ) -> Optional[str]:
        """Find an investigation ID by channel and thread."""
        for inv_id, inv_data in self._active_investigations.items():
            if inv_data.get("channel") == channel and inv_data.get("thread_ts") == thread_ts:
                return inv_id
        return None


async def handle_app_mention(
    event: dict,
    say: SayFn,
    client: SlackClient,
    handler: InvestigationHandler,
) -> None:
    """
    Handle @mentions of the AutoSRE bot.
    
    Parses the mention text to extract investigation parameters and
    starts a new investigation if valid.
    
    Args:
        event: Slack event payload
        say: Function to send messages
        client: Slack client
        handler: Investigation handler context
    """
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    
    logger.info(
        "app_mention_handler",
        channel=channel,
        user=user,
        text_preview=text[:100],
    )
    
    # Parse alert from mention text
    alert_data = parse_mention_text(text)
    
    if not alert_data:
        await say(
            text=(
                "👋 Hi! I'm AutoSRE. I can help investigate incidents.\n\n"
                "*Try mentioning me with:*\n"
                "• `@AutoSRE investigate payment-service high error rate`\n"
                "• `@AutoSRE service=auth-api severity=critical`\n\n"
                "*Or use the slash command:*\n"
                "• `/investigate service=payment-api severity=high description=\"Error rate spike\"`"
            ),
            thread_ts=thread_ts,
        )
        return
    
    # Start investigation
    try:
        response = await handler.api_client.post(
            "/api/v1/investigate",
            json={"alert": alert_data},
        )
        response.raise_for_status()
        investigation = response.json()
        investigation_id = investigation.get("id", "unknown")
        
        # Track this investigation
        handler.track_investigation(
            investigation_id=investigation_id,
            channel=channel,
            thread_ts=thread_ts,
            user=user,
        )
        
        # Send start message
        blocks = format_investigation_start(
            investigation_id=investigation_id,
            alert=alert_data,
            requested_by=f"<@{user}>",
        )
        
        await say(blocks=blocks, thread_ts=thread_ts)
        
        logger.info(
            "investigation_started",
            investigation_id=investigation_id,
            channel=channel,
            user=user,
        )
        
    except Exception as e:
        logger.error(
            "investigation_start_failed",
            error=str(e),
            exc_info=True,
        )
        blocks = format_error(
            title="Failed to Start Investigation",
            message=str(e),
        )
        await say(blocks=blocks, thread_ts=thread_ts)


async def handle_investigate_command(
    ack: AckFn,
    respond: RespondFn,
    command: dict,
    handler: InvestigationHandler,
) -> None:
    """
    Handle /investigate slash command.
    
    Parses command arguments and starts a new investigation.
    
    Args:
        ack: Acknowledge function (must be called within 3 seconds)
        respond: Respond function for delayed responses
        command: Command payload
        handler: Investigation handler context
    """
    # Acknowledge immediately
    await ack()
    
    user = command.get("user_id")
    channel = command.get("channel_id")
    text = command.get("text", "")
    
    logger.info(
        "investigate_command_handler",
        user=user,
        channel=channel,
        text_preview=text[:100],
    )
    
    # Parse command arguments
    alert_data = parse_command_args(text)
    
    if not alert_data:
        await respond(
            text=(
                "Please provide alert details.\n\n"
                "*Usage:*\n"
                "`/investigate service=<name> severity=<level> description=\"<text>\"`\n\n"
                "*Examples:*\n"
                "• `/investigate service=payment-api severity=critical description=\"Error rate above 5%\"`\n"
                "• `/investigate payment-service high latency`\n"
                "• `/investigate service=auth`"
            ),
            response_type="ephemeral",
        )
        return
    
    # Start investigation
    try:
        response = await handler.api_client.post(
            "/api/v1/investigate",
            json={"alert": alert_data},
        )
        response.raise_for_status()
        investigation = response.json()
        investigation_id = investigation.get("id", "unknown")
        
        # Track this investigation
        handler.track_investigation(
            investigation_id=investigation_id,
            channel=channel,
            thread_ts=None,
            user=user,
        )
        
        # Send visible response
        blocks = format_investigation_start(
            investigation_id=investigation_id,
            alert=alert_data,
            requested_by=f"<@{user}>",
        )
        
        await respond(
            blocks=blocks,
            response_type="in_channel",
        )
        
        logger.info(
            "investigation_started_command",
            investigation_id=investigation_id,
            channel=channel,
            user=user,
        )
        
    except Exception as e:
        logger.error(
            "investigate_command_failed",
            error=str(e),
            exc_info=True,
        )
        blocks = format_error(
            title="Failed to Start Investigation",
            message=str(e),
        )
        await respond(blocks=blocks, response_type="ephemeral")


async def handle_reaction_added(
    event: dict,
    client: SlackClient,
    handler: InvestigationHandler,
) -> None:
    """
    Handle reaction additions for feedback.
    
    Converts certain reactions (👍, 👎) into feedback submissions
    for the investigation system.
    
    Args:
        event: Slack event payload
        client: Slack client
        handler: Investigation handler context
    """
    reaction = event.get("reaction")
    item = event.get("item", {})
    user = event.get("user")
    
    # Map reactions to feedback types
    feedback_map = {
        "+1": ("positive", 1.0),
        "thumbsup": ("positive", 1.0),
        "thumbs_up": ("positive", 1.0),
        "white_check_mark": ("positive", 1.0),
        "-1": ("negative", 0.0),
        "thumbsdown": ("negative", 0.0),
        "thumbs_down": ("negative", 0.0),
        "x": ("negative", 0.0),
        "question": ("unclear", 0.5),
        "thinking_face": ("unclear", 0.5),
    }
    
    feedback_info = feedback_map.get(reaction)
    if not feedback_info:
        return  # Not a feedback reaction
    
    feedback_type, rating = feedback_info
    
    # Find the investigation
    channel = item.get("channel")
    ts = item.get("ts")
    
    # Try to match by channel (simplified - in production, would parse the message)
    investigation_id = None
    for inv_id, inv_data in handler._active_investigations.items():
        if inv_data.get("channel") == channel:
            investigation_id = inv_id
            break
    
    if not investigation_id:
        logger.debug(
            "reaction_no_investigation",
            channel=channel,
            ts=ts,
            reaction=reaction,
        )
        return
    
    logger.info(
        "feedback_received",
        investigation_id=investigation_id,
        feedback_type=feedback_type,
        user=user,
    )
    
    # Submit feedback
    try:
        response = await handler.api_client.post(
            f"/api/v1/investigate/{investigation_id}/feedback",
            json={
                "rating": rating,
                "comment": f"Slack reaction feedback: {feedback_type}",
                "correct": feedback_type == "positive",
            },
        )
        response.raise_for_status()
        
        logger.info(
            "feedback_submitted",
            investigation_id=investigation_id,
            feedback_type=feedback_type,
        )
        
    except Exception as e:
        logger.error(
            "feedback_submit_failed",
            investigation_id=investigation_id,
            error=str(e),
        )


async def handle_thread_reply(
    event: dict,
    say: SayFn,
    client: SlackClient,
    handler: InvestigationHandler,
) -> None:
    """
    Handle thread replies for follow-up questions.
    
    Users can ask follow-up questions in investigation threads.
    Currently acknowledges the question; could trigger additional
    investigation in the future.
    
    Args:
        event: Slack event payload
        say: Function to send messages
        client: Slack client
        handler: Investigation handler context
    """
    thread_ts = event.get("thread_ts")
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")
    
    # Ignore bot messages
    if event.get("bot_id"):
        return
    
    # Find if this thread belongs to an investigation
    investigation_id = handler.find_investigation_by_thread(channel, thread_ts)
    
    if not investigation_id:
        return  # Not an investigation thread
    
    logger.info(
        "thread_reply_handler",
        investigation_id=investigation_id,
        user=user,
        text_preview=text[:100],
    )
    
    # Check if this is a command
    text_lower = text.lower().strip()
    
    if text_lower.startswith("status"):
        # Request status update
        try:
            response = await handler.api_client.get(
                f"/api/v1/investigate/{investigation_id}/status",
            )
            response.raise_for_status()
            status = response.json()
            
            await say(
                text=f"📊 *Investigation Status*\n"
                     f"• State: `{status.get('state', 'unknown')}`\n"
                     f"• Progress: {status.get('progress', 0):.0%}\n"
                     f"• Steps completed: {status.get('steps_completed', 0)}",
                thread_ts=thread_ts,
            )
        except Exception as e:
            await say(
                text=f"Failed to get status: {e}",
                thread_ts=thread_ts,
            )
    
    elif text_lower.startswith("cancel"):
        # Request cancellation
        await say(
            text=f"⚠️ To cancel this investigation, please use:\n"
                 f"`/autosre cancel {investigation_id}`",
            thread_ts=thread_ts,
        )
    
    else:
        # Generic follow-up acknowledgment
        await say(
            text=f"Got your follow-up. I'll factor this into the investigation `{investigation_id[:8]}...`\n"
                 f"_Type `status` to check progress or `cancel` to stop._",
            thread_ts=thread_ts,
        )


def parse_mention_text(text: str) -> Optional[dict]:
    """
    Parse @mention text to extract alert details.
    
    Handles various formats:
    - "@AutoSRE investigate payment-service error rate"
    - "@AutoSRE service=foo severity=critical"
    - "@AutoSRE check the auth service"
    
    Args:
        text: Raw mention text including the bot mention
        
    Returns:
        Alert dict if valid, None otherwise
    """
    # Remove bot mention(s)
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    
    # Try key=value parsing first
    alert = parse_command_args(text)
    if alert and "service" in alert:
        return alert
    
    # Natural language parsing
    words = text.lower().split()
    
    # Remove trigger words
    trigger_words = {
        "investigate", "check", "look", "at", "into", "the",
        "please", "can", "you", "what's", "whats", "wrong", "with",
        "why", "is", "are", "help", "me", "analyze", "debug",
    }
    filtered_words = [w for w in words if w not in trigger_words]
    
    if not filtered_words:
        return None
    
    # Try to identify service name (usually first remaining word)
    service = filtered_words[0]
    
    # Try to identify severity from keywords
    severity = "medium"
    severity_keywords = {
        "critical": ["critical", "crit", "emergency", "down", "outage"],
        "high": ["high", "urgent", "severe", "major"],
        "low": ["low", "minor", "small"],
    }
    
    for level, keywords in severity_keywords.items():
        if any(kw in filtered_words for kw in keywords):
            severity = level
            break
    
    return {
        "name": "SlackInvestigation",
        "service": service,
        "severity": severity,
        "description": " ".join(filtered_words),
        "source": "slack",
    }


def parse_command_args(text: str) -> Optional[dict]:
    """
    Parse slash command arguments.
    
    Supports formats:
    - service=foo severity=critical description="some text"
    - payment-service high latency (natural language fallback)
    
    Args:
        text: Command text (without the /command part)
        
    Returns:
        Alert dict if valid, None otherwise
    """
    import shlex
    
    if not text or not text.strip():
        return None
    
    text = text.strip()
    alert = {
        "name": "SlackInvestigation",
        "source": "slack",
    }
    
    # Try to parse key=value pairs
    try:
        tokens = shlex.split(text)
    except ValueError:
        # Fallback to simple split if shlex fails
        tokens = text.split()
    
    has_key_value = False
    remaining_tokens = []
    
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            
            if key in ("service", "svc", "s"):
                alert["service"] = value
                has_key_value = True
            elif key in ("severity", "sev", "p"):
                alert["severity"] = normalize_severity(value)
                has_key_value = True
            elif key in ("description", "desc", "d", "msg"):
                alert["description"] = value
                has_key_value = True
            elif key in ("name", "n"):
                alert["name"] = value
                has_key_value = True
        else:
            remaining_tokens.append(token)
    
    # If we found key=value pairs but no service, check remaining tokens
    if has_key_value and "service" not in alert and remaining_tokens:
        alert["service"] = remaining_tokens[0]
        if len(remaining_tokens) > 1:
            alert["description"] = " ".join(remaining_tokens)
    
    # If no key=value pairs, use natural language parsing
    if not has_key_value:
        if not tokens:
            return None
        
        # First token is service
        alert["service"] = tokens[0]
        
        # Rest is description
        if len(tokens) > 1:
            alert["description"] = " ".join(tokens[1:])
        
        # Try to extract severity from text
        text_lower = text.lower()
        if any(w in text_lower for w in ["critical", "crit", "p0", "outage"]):
            alert["severity"] = "critical"
        elif any(w in text_lower for w in ["high", "urgent", "p1"]):
            alert["severity"] = "high"
        elif any(w in text_lower for w in ["low", "minor", "p3"]):
            alert["severity"] = "low"
    
    # Validate we have at least a service
    if "service" not in alert:
        return None
    
    # Set defaults
    if "severity" not in alert:
        alert["severity"] = "medium"
    if "description" not in alert:
        alert["description"] = f"Investigation requested for {alert['service']}"
    
    return alert


def normalize_severity(value: str) -> str:
    """
    Normalize severity value to standard levels.
    
    Args:
        value: Raw severity value
        
    Returns:
        Normalized severity (critical, high, medium, low)
    """
    value = value.lower().strip()
    
    severity_map = {
        "critical": "critical",
        "crit": "critical",
        "p0": "critical",
        "0": "critical",
        "high": "high",
        "p1": "high",
        "1": "high",
        "medium": "medium",
        "med": "medium",
        "p2": "medium",
        "2": "medium",
        "low": "low",
        "p3": "low",
        "3": "low",
    }
    
    return severity_map.get(value, "medium")
