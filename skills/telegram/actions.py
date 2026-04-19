"""Telegram skill actions."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiohttp

from .models import (
    TelegramMessage,
    TelegramChat,
    TelegramUser,
    TelegramFile,
    TelegramError,
)


class RateLimiter:
    """Rate limiter for Telegram API."""
    
    def __init__(self, calls_per_second: int = 30):
        self.calls_per_second = calls_per_second
        self.interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()


class TelegramSkill:
    """Telegram integration skill."""
    
    BASE_URL = "https://api.telegram.org"
    
    def __init__(
        self,
        token: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.api_url = api_url or os.environ.get("TELEGRAM_API_URL", self.BASE_URL)
        
        if not self.token:
            raise TelegramError(401, "TELEGRAM_BOT_TOKEN not configured")
        
        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def _base_url(self) -> str:
        return f"{self.api_url}/bot{self.token}"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _request(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make rate-limited API request."""
        await self.rate_limiter.acquire()
        
        session = await self._get_session()
        url = f"{self._base_url}/{method}"
        
        if files:
            # Multipart form data for file uploads
            form = aiohttp.FormData()
            if data:
                for key, value in data.items():
                    form.add_field(key, str(value))
            for key, file_data in files.items():
                form.add_field(key, file_data["data"], filename=file_data["filename"])
            
            async with session.post(url, data=form) as resp:
                body = await resp.json()
        else:
            async with session.post(url, json=data or {}) as resp:
                body = await resp.json()
        
        if not body.get("ok"):
            raise TelegramError(
                error_code=body.get("error_code", 500),
                description=body.get("description", "Unknown error"),
            )
        
        return body.get("result", {})
    
    def _parse_message(self, data: dict[str, Any]) -> TelegramMessage:
        """Parse message from API response."""
        chat_data = data.get("chat", {})
        from_data = data.get("from")
        
        return TelegramMessage(
            message_id=data["message_id"],
            chat=TelegramChat(
                id=chat_data["id"],
                type=chat_data["type"],
                title=chat_data.get("title"),
                username=chat_data.get("username"),
            ),
            date=datetime.fromtimestamp(data["date"]),
            text=data.get("text"),
            caption=data.get("caption"),
            from_user=TelegramUser(
                id=from_data["id"],
                is_bot=from_data.get("is_bot", False),
                first_name=from_data["first_name"],
                last_name=from_data.get("last_name"),
                username=from_data.get("username"),
            ) if from_data else None,
        )
    
    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
    ) -> TelegramMessage:
        """Send a text message.
        
        Args:
            chat_id: Chat ID or @username
            text: Message text
            parse_mode: Text formatting (Markdown, MarkdownV2, HTML)
            disable_notification: Send silently
            reply_to_message_id: Reply to specific message
            
        Returns:
            Sent message
        """
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        if disable_notification:
            data["disable_notification"] = True
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        
        result = await self._request("sendMessage", data)
        return self._parse_message(result)
    
    async def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
    ) -> TelegramMessage:
        """Send a photo by URL.
        
        Args:
            chat_id: Chat ID or @username
            photo_url: Photo URL
            caption: Photo caption
            parse_mode: Caption formatting
            disable_notification: Send silently
            
        Returns:
            Sent message
        """
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo_url,
        }
        
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if disable_notification:
            data["disable_notification"] = True
        
        result = await self._request("sendPhoto", data)
        return self._parse_message(result)
    
    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
    ) -> TelegramMessage:
        """Send a document/file.
        
        Args:
            chat_id: Chat ID or @username
            file_path: Local path to file
            caption: Document caption
            parse_mode: Caption formatting
            disable_notification: Send silently
            
        Returns:
            Sent message
        """
        path = Path(file_path)
        if not path.exists():
            raise TelegramError(400, f"File not found: {file_path}")
        
        data: dict[str, Any] = {"chat_id": chat_id}
        
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if disable_notification:
            data["disable_notification"] = True
        
        with open(path, "rb") as f:
            files = {
                "document": {
                    "data": f.read(),
                    "filename": path.name,
                }
            }
            result = await self._request("sendDocument", data, files)
        
        return self._parse_message(result)
    
    async def send_photo_file(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
    ) -> TelegramMessage:
        """Send a photo from local file.
        
        Args:
            chat_id: Chat ID or @username
            file_path: Local path to image
            caption: Photo caption
            parse_mode: Caption formatting
            
        Returns:
            Sent message
        """
        path = Path(file_path)
        if not path.exists():
            raise TelegramError(400, f"File not found: {file_path}")
        
        data: dict[str, Any] = {"chat_id": chat_id}
        
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        with open(path, "rb") as f:
            files = {
                "photo": {
                    "data": f.read(),
                    "filename": path.name,
                }
            }
            result = await self._request("sendPhoto", data, files)
        
        return self._parse_message(result)
    
    async def get_me(self) -> TelegramUser:
        """Get bot info.
        
        Returns:
            Bot user info
        """
        result = await self._request("getMe")
        return TelegramUser(
            id=result["id"],
            is_bot=result.get("is_bot", True),
            first_name=result["first_name"],
            last_name=result.get("last_name"),
            username=result.get("username"),
        )
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
