"""Tests for Telegram skill."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from skills.telegram import TelegramSkill, TelegramMessage, TelegramUser, TelegramError


@pytest.fixture
def skill():
    """Create a TelegramSkill with mocked config."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123456:ABC-DEF"}):
        return TelegramSkill()


def make_message(message_id: int = 1, text: str = "Hello") -> dict:
    """Create a mock message response."""
    return {
        "message_id": message_id,
        "chat": {
            "id": -100123456789,
            "type": "supergroup",
            "title": "Test Group",
        },
        "from": {
            "id": 12345,
            "is_bot": False,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
        },
        "date": 1704067200,  # 2024-01-01
        "text": text,
    }


@pytest.mark.asyncio
async def test_send_message(skill):
    """Test sending a message."""
    mock_response = {"ok": True, "result": make_message(text="Test message")}
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response["result"])):
        result = await skill.send_message(
            chat_id="-100123456789",
            text="Test message",
            parse_mode="Markdown"
        )
    
    assert isinstance(result, TelegramMessage)
    assert result.text == "Test message"
    assert result.chat.is_group


@pytest.mark.asyncio
async def test_send_message_with_reply(skill):
    """Test sending a reply."""
    mock_response = {"ok": True, "result": make_message()}
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response["result"])) as mock_req:
        await skill.send_message(
            chat_id="-100123456789",
            text="Reply",
            reply_to_message_id=42
        )
        
        call_args = mock_req.call_args
        assert call_args[0][1]["reply_to_message_id"] == 42


@pytest.mark.asyncio
async def test_send_photo(skill):
    """Test sending a photo."""
    mock_response = make_message()
    mock_response["photo"] = [{"file_id": "abc123", "file_unique_id": "xyz", "width": 100, "height": 100}]
    mock_response["caption"] = "Test caption"
    mock_response.pop("text")
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await skill.send_photo(
            chat_id="-100123456789",
            photo_url="https://example.com/image.png",
            caption="Test caption"
        )
        
        call_args = mock_req.call_args
        assert call_args[0][0] == "sendPhoto"
    
    assert result.caption == "Test caption"


@pytest.mark.asyncio
async def test_send_document(skill):
    """Test sending a document."""
    mock_response = make_message()
    mock_response["document"] = {"file_id": "abc123", "file_unique_id": "xyz", "file_name": "test.pdf"}
    mock_response.pop("text")
    
    with patch("builtins.open", AsyncMock()):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
                # Create a mock file context
                import builtins
                original_open = builtins.open
                
                def mock_open(*args, **kwargs):
                    from io import BytesIO
                    return BytesIO(b"test content")
                
                with patch("builtins.open", mock_open):
                    result = await skill.send_document(
                        chat_id="-100123456789",
                        file_path="/tmp/test.pdf"
                    )
    
    assert isinstance(result, TelegramMessage)


@pytest.mark.asyncio
async def test_send_document_file_not_found(skill):
    """Test error when file not found."""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(TelegramError) as exc_info:
            await skill.send_document(
                chat_id="-100123456789",
                file_path="/nonexistent/file.pdf"
            )
        assert exc_info.value.error_code == 400


@pytest.mark.asyncio
async def test_get_me(skill):
    """Test getting bot info."""
    mock_response = {
        "id": 123456789,
        "is_bot": True,
        "first_name": "TestBot",
        "username": "test_bot",
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_me()
    
    assert isinstance(result, TelegramUser)
    assert result.is_bot
    assert result.username == "test_bot"


def test_missing_token():
    """Test error when token is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(TelegramError) as exc_info:
            TelegramSkill()
        assert exc_info.value.error_code == 401


def test_parse_message_content(skill):
    """Test message content property."""
    msg_data = make_message(text="Hello world")
    result = skill._parse_message(msg_data)
    assert result.content == "Hello world"
    
    # Test with caption instead
    msg_data.pop("text")
    msg_data["caption"] = "Photo caption"
    result = skill._parse_message(msg_data)
    assert result.content == "Photo caption"
