"""Slack skill actions."""

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from .models import (
    SlackChannel,
    SlackError,
    SlackFile,
    SlackHistory,
    SlackHistoryMessage,
    SlackMessage,
    SlackReaction,
)


class RateLimiter:
    """Simple rate limiter for Slack API."""

    def __init__(self, calls_per_minute: int = 50):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()


class SlackSkill:
    """Slack integration skill."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        if not self.token:
            raise SlackError("missing_token", "SLACK_BOT_TOKEN not configured")

        self.client = AsyncWebClient(token=self.token)
        self.rate_limiter = RateLimiter()

    async def _api_call(self, method: str, **kwargs) -> dict[str, Any]:
        """Make rate-limited API call."""
        await self.rate_limiter.acquire()
        try:
            api_method = getattr(self.client, method)
            response = await api_method(**kwargs)
            return response.data
        except SlackApiError as e:
            raise SlackError(e.response["error"], str(e)) from e

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
        unfurl_links: bool = True,
        unfurl_media: bool = True,
    ) -> SlackMessage:
        """Post a message to a channel.

        Args:
            channel: Channel ID or name (e.g., "#general" or "C123ABC")
            text: Message text (fallback for blocks)
            blocks: Block Kit blocks for rich formatting
            thread_ts: Thread timestamp to reply in
            unfurl_links: Enable link previews
            unfurl_media: Enable media previews

        Returns:
            SlackMessage with channel and timestamp
        """
        data = await self._api_call(
            "chat_postMessage",
            channel=channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts,
            unfurl_links=unfurl_links,
            unfurl_media=unfurl_media,
        )
        return SlackMessage(
            ok=data["ok"],
            channel=data["channel"],
            ts=data["ts"],
            message=data.get("message"),
        )

    async def send_thread_reply(
        self,
        channel: str,
        thread_ts: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> SlackMessage:
        """Reply in a thread.

        Args:
            channel: Channel ID
            thread_ts: Parent message timestamp
            text: Reply text
            blocks: Optional Block Kit blocks

        Returns:
            SlackMessage with reply timestamp
        """
        return await self.send_message(
            channel=channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts,
        )

    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> SlackReaction:
        """Add an emoji reaction to a message.

        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons, e.g., "thumbsup")

        Returns:
            SlackReaction confirmation
        """
        # Remove colons if present
        emoji = emoji.strip(":")

        data = await self._api_call(
            "reactions_add",
            channel=channel,
            timestamp=timestamp,
            name=emoji,
        )
        return SlackReaction(
            ok=data["ok"],
            channel=channel,
            timestamp=timestamp,
            emoji=emoji,
        )

    async def upload_file(
        self,
        channel: str,
        file_path: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
    ) -> SlackFile:
        """Upload a file to a channel.

        Args:
            channel: Channel ID
            file_path: Local path to file
            title: File title
            initial_comment: Message to post with file

        Returns:
            SlackFile with file info
        """
        path = Path(file_path)
        if not path.exists():
            raise SlackError("file_not_found", f"File not found: {file_path}")

        data = await self._api_call(
            "files_upload_v2",
            channel=channel,
            file=str(path),
            title=title or path.name,
            initial_comment=initial_comment,
        )

        file_info = data.get("file", {})
        return SlackFile(
            ok=data["ok"],
            file_id=file_info.get("id", ""),
            title=file_info.get("title", title or path.name),
            permalink=file_info.get("permalink"),
            url_private=file_info.get("url_private"),
            size=file_info.get("size"),
            mimetype=file_info.get("mimetype"),
        )

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> SlackHistory:
        """Fetch recent messages from a channel.

        Args:
            channel: Channel ID
            limit: Maximum messages to return (1-1000)
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)

        Returns:
            SlackHistory with messages
        """
        kwargs = {"channel": channel, "limit": min(limit, 1000)}
        if oldest:
            kwargs["oldest"] = oldest
        if latest:
            kwargs["latest"] = latest

        data = await self._api_call("conversations_history", **kwargs)

        messages = [
            SlackHistoryMessage(
                ts=m["ts"],
                text=m.get("text", ""),
                user=m.get("user"),
                bot_id=m.get("bot_id"),
                thread_ts=m.get("thread_ts"),
                reply_count=m.get("reply_count"),
                reactions=m.get("reactions"),
            )
            for m in data.get("messages", [])
        ]

        return SlackHistory(
            ok=data["ok"],
            messages=messages,
            has_more=data.get("has_more", False),
            response_metadata=data.get("response_metadata"),
        )

    async def create_incident_channel(
        self,
        name: str,
        users: Optional[list[str]] = None,
        topic: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> SlackChannel:
        """Create a new incident channel.

        Args:
            name: Channel name (will be prefixed with # automatically)
            users: List of user IDs to invite
            topic: Channel topic
            purpose: Channel purpose/description

        Returns:
            SlackChannel with channel info
        """
        # Create the channel
        data = await self._api_call(
            "conversations_create",
            name=name,
            is_private=False,
        )

        channel_data = data["channel"]
        channel_id = channel_data["id"]

        # Set topic if provided
        if topic:
            await self._api_call(
                "conversations_setTopic",
                channel=channel_id,
                topic=topic,
            )

        # Set purpose if provided
        if purpose:
            await self._api_call(
                "conversations_setPurpose",
                channel=channel_id,
                purpose=purpose,
            )

        # Invite users if provided
        if users:
            await self._api_call(
                "conversations_invite",
                channel=channel_id,
                users=",".join(users),
            )

        return SlackChannel(
            id=channel_id,
            name=channel_data["name"],
            is_private=channel_data.get("is_private", False),
            is_archived=False,
            creator=channel_data.get("creator"),
            topic=topic,
            purpose=purpose,
        )

    async def archive_channel(self, channel: str) -> bool:
        """Archive a channel.

        Args:
            channel: Channel ID to archive

        Returns:
            True if successful
        """
        data = await self._api_call("conversations_archive", channel=channel)
        return data.get("ok", False)

    async def get_channel_info(self, channel: str) -> SlackChannel:
        """Get channel information.

        Args:
            channel: Channel ID

        Returns:
            SlackChannel with details
        """
        data = await self._api_call("conversations_info", channel=channel)
        ch = data["channel"]

        return SlackChannel(
            id=ch["id"],
            name=ch["name"],
            is_private=ch.get("is_private", False),
            is_archived=ch.get("is_archived", False),
            creator=ch.get("creator"),
            topic=ch.get("topic", {}).get("value"),
            purpose=ch.get("purpose", {}).get("value"),
            num_members=ch.get("num_members"),
        )
