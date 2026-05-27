"""
AutoSRE Slack Bot

Main Slack bot implementation using slack-bolt with Socket Mode for real-time
bidirectional communication. Handles app mentions, slash commands, and reactions.
"""

import asyncio
import os
from typing import Any, Callable, Optional

import httpx
import structlog
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from .messages import (
    format_investigation_start,
    format_progress_update,
    format_evidence_found,
    format_investigation_complete,
    format_error,
)

logger = structlog.get_logger(__name__)


class AutoSRESlackBot:
    """
    AutoSRE Slack Bot with Socket Mode support.
    
    Provides Slack integration for incident investigation, allowing users to
    trigger investigations via mentions or slash commands and receive real-time
    updates in Slack threads.
    
    Attributes:
        app: The slack-bolt AsyncApp instance
        handler: Socket Mode handler for real-time communication
        api_client: HTTP client for AutoSRE API calls
        api_base_url: Base URL for AutoSRE API
        
    Environment Variables:
        SLACK_BOT_TOKEN: OAuth bot token (xoxb-...)
        SLACK_APP_TOKEN: App-level token for Socket Mode (xapp-...)
        SLACK_SIGNING_SECRET: Signing secret for request verification
        AUTOSRE_API_URL: Base URL for AutoSRE API (default: http://localhost:8000)
    """
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        app_token: Optional[str] = None,
        signing_secret: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ):
        """
        Initialize the Slack bot.
        
        Args:
            bot_token: Slack bot OAuth token. Falls back to SLACK_BOT_TOKEN env var.
            app_token: Slack app-level token. Falls back to SLACK_APP_TOKEN env var.
            signing_secret: Slack signing secret. Falls back to SLACK_SIGNING_SECRET env var.
            api_base_url: AutoSRE API base URL. Falls back to AUTOSRE_API_URL env var.
        """
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN")
        self.app_token = app_token or os.environ.get("SLACK_APP_TOKEN")
        self.signing_secret = signing_secret or os.environ.get("SLACK_SIGNING_SECRET")
        self.api_base_url = api_base_url or os.environ.get("AUTOSRE_API_URL", "http://localhost:8000")
        
        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        if not self.app_token:
            raise ValueError("SLACK_APP_TOKEN is required (for Socket Mode)")
        if not self.signing_secret:
            raise ValueError("SLACK_SIGNING_SECRET is required")
        
        # Initialize the Slack app
        self.app = AsyncApp(
            token=self.bot_token,
            signing_secret=self.signing_secret,
        )
        
        # Socket Mode handler
        self.handler = AsyncSocketModeHandler(self.app, self.app_token)
        
        # HTTP client for API calls
        self.api_client: Optional[httpx.AsyncClient] = None
        
        # Active investigation tracking
        # Maps investigation_id -> {"channel": str, "thread_ts": str, "user": str}
        self._active_investigations: dict[str, dict[str, str]] = {}
        
        # Register all event handlers
        self._register_handlers()
        
        logger.info(
            "slack_bot_initialized",
            api_base_url=self.api_base_url,
        )
    
    def _register_handlers(self) -> None:
        """Register all Slack event handlers."""
        
        @self.app.event("app_mention")
        async def handle_mention(event: dict, say: Callable, client: Any) -> None:
            """Handle @mentions of the bot."""
            await self._handle_app_mention(event, say, client)
        
        @self.app.command("/investigate")
        async def handle_investigate(ack: Callable, respond: Callable, command: dict) -> None:
            """Handle /investigate slash command."""
            await self._handle_investigate_command(ack, respond, command)
        
        @self.app.command("/autosre")
        async def handle_autosre(ack: Callable, respond: Callable, command: dict) -> None:
            """Handle /autosre slash command (alias for /investigate)."""
            await self._handle_investigate_command(ack, respond, command)
        
        @self.app.event("reaction_added")
        async def handle_reaction(event: dict, client: Any) -> None:
            """Handle reaction additions for feedback."""
            await self._handle_reaction_added(event, client)
        
        @self.app.event("message")
        async def handle_message(event: dict, say: Callable, client: Any) -> None:
            """Handle messages in threads (for follow-up questions)."""
            # Only handle thread replies
            if "thread_ts" in event and event.get("thread_ts") != event.get("ts"):
                await self._handle_thread_reply(event, say, client)
        
        @self.app.error
        async def handle_error(error: Exception, body: dict, logger: Any) -> None:
            """Global error handler."""
            logger.error(
                "slack_error",
                error=str(error),
                body=body,
                exc_info=True,
            )
    
    async def _handle_app_mention(
        self,
        event: dict,
        say: Callable,
        client: Any,
    ) -> None:
        """
        Handle @mentions of the bot to start investigations.
        
        Expected format: @AutoSRE investigate <alert details>
        or: @AutoSRE <any text> (will try to extract alert info)
        """
        channel = event.get("channel")
        user = event.get("user")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        logger.info(
            "app_mention_received",
            channel=channel,
            user=user,
            text=text[:100],
        )
        
        # Parse the mention text to extract alert details
        alert_data = self._parse_mention_text(text)
        
        if not alert_data:
            # Provide help if no clear investigation request
            await say(
                text="Hi! I can help investigate incidents. Try:\n"
                     "• `@AutoSRE investigate payment-service high error rate`\n"
                     "• `/investigate service=auth-api severity=critical`",
                thread_ts=thread_ts,
            )
            return
        
        # Start the investigation
        try:
            investigation = await self._start_investigation(alert_data)
            investigation_id = investigation.get("id", "unknown")
            
            # Track this investigation
            self._active_investigations[investigation_id] = {
                "channel": channel,
                "thread_ts": thread_ts,
                "user": user,
            }
            
            # Send initial message
            blocks = format_investigation_start(
                investigation_id=investigation_id,
                alert=alert_data,
                requested_by=f"<@{user}>",
            )
            
            await say(blocks=blocks, thread_ts=thread_ts)
            
            # Start streaming updates in the background
            asyncio.create_task(
                self._stream_investigation_updates(
                    investigation_id=investigation_id,
                    channel=channel,
                    thread_ts=thread_ts,
                    client=client,
                )
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
    
    async def _handle_investigate_command(
        self,
        ack: Callable,
        respond: Callable,
        command: dict,
    ) -> None:
        """
        Handle /investigate slash command.
        
        Usage: /investigate service=payment-service severity=critical description="High error rate"
        """
        # Acknowledge immediately (Slack requires response within 3 seconds)
        await ack()
        
        user = command.get("user_id")
        channel = command.get("channel_id")
        text = command.get("text", "")
        
        logger.info(
            "investigate_command_received",
            user=user,
            channel=channel,
            text=text[:100],
        )
        
        # Parse command arguments
        alert_data = self._parse_command_args(text)
        
        if not alert_data:
            await respond(
                text="Please provide alert details.\n"
                     "Usage: `/investigate service=<name> severity=<level> description=\"<text>\"`\n"
                     "Example: `/investigate service=payment-api severity=critical description=\"Error rate above 5%\"`",
                response_type="ephemeral",
            )
            return
        
        try:
            investigation = await self._start_investigation(alert_data)
            investigation_id = investigation.get("id", "unknown")
            
            # Track this investigation
            self._active_investigations[investigation_id] = {
                "channel": channel,
                "thread_ts": None,  # Will be set when we post
                "user": user,
            }
            
            # Send visible response
            blocks = format_investigation_start(
                investigation_id=investigation_id,
                alert=alert_data,
                requested_by=f"<@{user}>",
            )
            
            result = await respond(
                blocks=blocks,
                response_type="in_channel",
            )
            
            # Stream updates to channel
            asyncio.create_task(
                self._stream_investigation_updates(
                    investigation_id=investigation_id,
                    channel=channel,
                    thread_ts=None,
                    client=self.app.client,
                )
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
    
    async def _handle_reaction_added(
        self,
        event: dict,
        client: Any,
    ) -> None:
        """
        Handle reaction additions for feedback.
        
        - 👍 (thumbsup): Positive feedback
        - 👎 (thumbsdown): Negative feedback
        - ❓ (-1, question): Unclear/needs more info
        """
        reaction = event.get("reaction")
        item = event.get("item", {})
        user = event.get("user")
        
        # Map reactions to feedback types
        feedback_map = {
            "+1": "positive",
            "thumbsup": "positive",
            "-1": "negative",
            "thumbsdown": "negative",
            "question": "unclear",
        }
        
        feedback_type = feedback_map.get(reaction)
        if not feedback_type:
            return  # Not a feedback reaction
        
        # Find the investigation ID from the message
        channel = item.get("channel")
        ts = item.get("ts")
        
        # Try to find which investigation this belongs to
        investigation_id = None
        for inv_id, inv_data in self._active_investigations.items():
            if inv_data.get("channel") == channel:
                investigation_id = inv_id
                break
        
        if not investigation_id:
            logger.debug(
                "reaction_no_investigation",
                channel=channel,
                ts=ts,
            )
            return
        
        logger.info(
            "feedback_received",
            investigation_id=investigation_id,
            feedback_type=feedback_type,
            user=user,
        )
        
        # Submit feedback to API
        try:
            await self._submit_feedback(
                investigation_id=investigation_id,
                feedback_type=feedback_type,
                user=user,
            )
        except Exception as e:
            logger.error(
                "feedback_submit_failed",
                investigation_id=investigation_id,
                error=str(e),
            )
    
    async def _handle_thread_reply(
        self,
        event: dict,
        say: Callable,
        client: Any,
    ) -> None:
        """
        Handle thread replies for follow-up questions.
        
        Users can ask follow-up questions in the investigation thread.
        """
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        user = event.get("user")
        text = event.get("text", "")
        
        # Check if this is a bot message (avoid infinite loops)
        if event.get("bot_id"):
            return
        
        # Find if this thread belongs to an active investigation
        investigation_id = None
        for inv_id, inv_data in self._active_investigations.items():
            if inv_data.get("thread_ts") == thread_ts and inv_data.get("channel") == channel:
                investigation_id = inv_id
                break
        
        if not investigation_id:
            return  # Not an investigation thread
        
        logger.info(
            "thread_reply_received",
            investigation_id=investigation_id,
            user=user,
            text=text[:100],
        )
        
        # For now, acknowledge the question and note it
        # In the future, this could trigger additional investigation
        await say(
            text=f"Got your follow-up question. I'll look into it as part of investigation `{investigation_id}`.",
            thread_ts=thread_ts,
        )
    
    def _parse_mention_text(self, text: str) -> Optional[dict]:
        """
        Parse @mention text to extract alert details.
        
        Handles formats like:
        - "@AutoSRE investigate payment-service error rate"
        - "@AutoSRE service=foo severity=critical"
        """
        import re
        
        # Remove the bot mention
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        
        # Try to parse key=value pairs
        alert = self._parse_command_args(text)
        if alert:
            return alert
        
        # Try to extract from natural language
        words = text.lower().split()
        
        # Remove common trigger words
        trigger_words = {"investigate", "check", "look", "at", "into", "the", "please"}
        filtered_words = [w for w in words if w not in trigger_words]
        
        if not filtered_words:
            return None
        
        # Guess service name and description
        return {
            "name": "SlackInvestigation",
            "service": filtered_words[0] if filtered_words else "unknown",
            "severity": "medium",
            "description": " ".join(filtered_words),
            "source": "slack",
        }
    
    def _parse_command_args(self, text: str) -> Optional[dict]:
        """
        Parse slash command arguments.
        
        Supports: service=foo severity=critical description="some text"
        """
        import shlex
        
        if not text.strip():
            return None
        
        alert = {
            "name": "SlackInvestigation",
            "source": "slack",
        }
        
        # Try to parse key=value pairs
        # Handle quoted values
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        
        for token in tokens:
            if "=" in token:
                key, value = token.split("=", 1)
                key = key.strip().lower()
                value = value.strip().strip('"').strip("'")
                
                if key in ("service", "severity", "description", "name"):
                    alert[key] = value
        
        # Require at least a service
        if "service" not in alert:
            # Maybe the first word is the service
            first_word = text.split()[0] if text.split() else None
            if first_word and "=" not in first_word:
                alert["service"] = first_word
                alert["description"] = text
            else:
                return None
        
        # Default severity
        if "severity" not in alert:
            alert["severity"] = "medium"
        
        return alert
    
    async def _start_investigation(self, alert_data: dict) -> dict:
        """Start an investigation via the AutoSRE API."""
        if not self.api_client:
            self.api_client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=30.0,
            )
        
        response = await self.api_client.post(
            "/api/v1/investigate",
            json={"alert": alert_data},
        )
        response.raise_for_status()
        return response.json()
    
    async def _submit_feedback(
        self,
        investigation_id: str,
        feedback_type: str,
        user: str,
    ) -> None:
        """Submit feedback for an investigation."""
        if not self.api_client:
            self.api_client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=30.0,
            )
        
        # Map feedback type to API format
        feedback = {
            "rating": 1.0 if feedback_type == "positive" else 0.0,
            "comment": f"Feedback from Slack user {user}: {feedback_type}",
            "correct": feedback_type == "positive",
        }
        
        response = await self.api_client.post(
            f"/api/v1/investigate/{investigation_id}/feedback",
            json=feedback,
        )
        response.raise_for_status()
    
    async def _stream_investigation_updates(
        self,
        investigation_id: str,
        channel: str,
        thread_ts: Optional[str],
        client: Any,
    ) -> None:
        """
        Stream investigation updates to a Slack channel.
        
        Connects to the SSE endpoint and posts updates as they arrive.
        """
        import httpx_sse
        
        if not self.api_client:
            self.api_client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=None,  # No timeout for streaming
            )
        
        try:
            async with httpx_sse.aconnect_sse(
                self.api_client,
                "GET",
                f"/api/v1/investigate/{investigation_id}/stream",
            ) as event_source:
                async for event in event_source.aiter_sse():
                    await self._handle_stream_event(
                        investigation_id=investigation_id,
                        event_type=event.event,
                        event_data=event.data,
                        channel=channel,
                        thread_ts=thread_ts,
                        client=client,
                    )
        except Exception as e:
            logger.error(
                "stream_error",
                investigation_id=investigation_id,
                error=str(e),
                exc_info=True,
            )
    
    async def _handle_stream_event(
        self,
        investigation_id: str,
        event_type: str,
        event_data: str,
        channel: str,
        thread_ts: Optional[str],
        client: Any,
    ) -> None:
        """Handle a single SSE event and post to Slack."""
        import json
        
        try:
            data = json.loads(event_data) if event_data else {}
        except json.JSONDecodeError:
            return
        
        blocks = None
        
        if event_type == "step_start":
            # A new investigation step started
            blocks = format_progress_update(
                investigation_id=investigation_id,
                step=data.get("step_name", "Unknown"),
                status="in_progress",
                details=data.get("details"),
            )
        
        elif event_type == "step_complete":
            # A step completed
            blocks = format_progress_update(
                investigation_id=investigation_id,
                step=data.get("step_name", "Unknown"),
                status="complete",
                details=data.get("details"),
            )
        
        elif event_type == "finding":
            # Evidence or finding discovered
            blocks = format_evidence_found(
                investigation_id=investigation_id,
                finding_type=data.get("type", "finding"),
                summary=data.get("summary", ""),
                details=data.get("details"),
                confidence=data.get("confidence"),
            )
        
        elif event_type == "complete":
            # Investigation completed
            blocks = format_investigation_complete(
                investigation_id=investigation_id,
                status="completed",
                root_cause=data.get("root_cause", "Unknown"),
                summary=data.get("summary", "Investigation complete."),
                recommendations=data.get("recommendations", []),
                duration_seconds=data.get("duration_seconds"),
            )
            
            # Clean up tracking
            self._active_investigations.pop(investigation_id, None)
        
        elif event_type == "error":
            # Error occurred
            blocks = format_error(
                title=f"Investigation Error ({investigation_id})",
                message=data.get("message", "An error occurred"),
            )
            
            # Clean up tracking
            self._active_investigations.pop(investigation_id, None)
        
        if blocks:
            await client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                thread_ts=thread_ts,
            )
    
    async def start(self) -> None:
        """Start the bot using Socket Mode."""
        logger.info("slack_bot_starting")
        await self.handler.start_async()
    
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        logger.info("slack_bot_stopping")
        
        if self.api_client:
            await self.api_client.aclose()
        
        await self.handler.close_async()
        logger.info("slack_bot_stopped")


async def main() -> None:
    """Main entry point for running the bot."""
    import signal
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    
    bot = AutoSRESlackBot()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(bot.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
