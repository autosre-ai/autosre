"""Pydantic models for Telegram skill."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TelegramError(Exception):
    """Telegram API error."""

    def __init__(self, error_code: int, description: str):
        self.error_code = error_code
        self.description = description
        super().__init__(f"[{error_code}] {description}")


class TelegramUser(BaseModel):
    """Telegram user info."""

    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


class TelegramChat(BaseModel):
    """Telegram chat info."""

    id: int
    type: str = Field(description="private, group, supergroup, or channel")
    title: Optional[str] = None
    username: Optional[str] = None

    @property
    def is_group(self) -> bool:
        return self.type in ("group", "supergroup")

    @property
    def is_channel(self) -> bool:
        return self.type == "channel"


class TelegramMessage(BaseModel):
    """Telegram message."""

    message_id: int
    chat: TelegramChat
    date: datetime
    text: Optional[str] = None
    caption: Optional[str] = None
    from_user: Optional[TelegramUser] = None

    @property
    def content(self) -> str:
        return self.text or self.caption or ""


class TelegramFile(BaseModel):
    """Telegram file info."""

    file_id: str
    file_unique_id: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None


class TelegramPhoto(BaseModel):
    """Telegram photo sizes."""

    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None


class TelegramDocument(BaseModel):
    """Telegram document."""

    file_id: str
    file_unique_id: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
