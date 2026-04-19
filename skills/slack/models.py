"""Pydantic models for Slack skill."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class SlackError(Exception):
    """Slack API error."""
    
    def __init__(self, error: str, message: str = ""):
        self.error = error
        self.message = message
        super().__init__(f"{error}: {message}" if message else error)


class SlackMessage(BaseModel):
    """Slack message response."""
    
    ok: bool
    channel: str
    ts: str = Field(description="Message timestamp (unique ID)")
    message: Optional[dict[str, Any]] = None
    
    @property
    def timestamp(self) -> str:
        return self.ts
    
    @property
    def permalink(self) -> Optional[str]:
        return self.message.get("permalink") if self.message else None


class SlackChannel(BaseModel):
    """Slack channel info."""
    
    id: str
    name: str
    is_private: bool = False
    is_archived: bool = False
    created: Optional[datetime] = None
    creator: Optional[str] = None
    topic: Optional[str] = None
    purpose: Optional[str] = None
    num_members: Optional[int] = None


class SlackReaction(BaseModel):
    """Slack reaction response."""
    
    ok: bool
    channel: str
    timestamp: str
    emoji: str


class SlackFile(BaseModel):
    """Slack file upload response."""
    
    ok: bool
    file_id: str
    title: str
    permalink: Optional[str] = None
    url_private: Optional[str] = None
    size: Optional[int] = None
    mimetype: Optional[str] = None


class SlackHistoryMessage(BaseModel):
    """Single message from channel history."""
    
    ts: str
    text: str
    user: Optional[str] = None
    bot_id: Optional[str] = None
    thread_ts: Optional[str] = None
    reply_count: Optional[int] = None
    reactions: Optional[list[dict[str, Any]]] = None


class SlackHistory(BaseModel):
    """Channel history response."""
    
    ok: bool
    messages: list[SlackHistoryMessage]
    has_more: bool = False
    response_metadata: Optional[dict[str, Any]] = None
