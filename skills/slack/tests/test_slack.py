"""Tests for Slack skill."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from skills.slack import SlackSkill, SlackMessage, SlackChannel, SlackError


@pytest.fixture
def mock_client():
    """Create a mock Slack client."""
    with patch("skills.slack.actions.AsyncWebClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def skill(mock_client):
    """Create a SlackSkill with mocked client."""
    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test-token"}):
        return SlackSkill()


@pytest.mark.asyncio
async def test_send_message(skill, mock_client):
    """Test sending a message."""
    mock_client.chat_postMessage = AsyncMock(return_value=MagicMock(
        data={
            "ok": True,
            "channel": "C123",
            "ts": "1234567890.123456",
            "message": {"text": "Hello"}
        }
    ))
    
    result = await skill.send_message(channel="#general", text="Hello")
    
    assert isinstance(result, SlackMessage)
    assert result.ok is True
    assert result.channel == "C123"
    assert result.ts == "1234567890.123456"


@pytest.mark.asyncio
async def test_send_message_with_blocks(skill, mock_client):
    """Test sending a message with blocks."""
    mock_client.chat_postMessage = AsyncMock(return_value=MagicMock(
        data={
            "ok": True,
            "channel": "C123",
            "ts": "1234567890.123456",
        }
    ))
    
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "*Bold*"}}]
    result = await skill.send_message(channel="C123", text="Fallback", blocks=blocks)
    
    mock_client.chat_postMessage.assert_called_once()
    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["blocks"] == blocks


@pytest.mark.asyncio
async def test_send_thread_reply(skill, mock_client):
    """Test replying in a thread."""
    mock_client.chat_postMessage = AsyncMock(return_value=MagicMock(
        data={
            "ok": True,
            "channel": "C123",
            "ts": "1234567890.999999",
        }
    ))
    
    result = await skill.send_thread_reply(
        channel="C123",
        thread_ts="1234567890.123456",
        text="Thread reply"
    )
    
    assert result.ok is True
    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["thread_ts"] == "1234567890.123456"


@pytest.mark.asyncio
async def test_add_reaction(skill, mock_client):
    """Test adding a reaction."""
    mock_client.reactions_add = AsyncMock(return_value=MagicMock(
        data={"ok": True}
    ))
    
    result = await skill.add_reaction(
        channel="C123",
        timestamp="1234567890.123456",
        emoji=":thumbsup:"  # Should strip colons
    )
    
    assert result.ok is True
    assert result.emoji == "thumbsup"


@pytest.mark.asyncio
async def test_create_incident_channel(skill, mock_client):
    """Test creating an incident channel."""
    mock_client.conversations_create = AsyncMock(return_value=MagicMock(
        data={
            "ok": True,
            "channel": {
                "id": "C456",
                "name": "inc-2024-001",
                "creator": "U123",
            }
        }
    ))
    mock_client.conversations_setTopic = AsyncMock(return_value=MagicMock(data={"ok": True}))
    mock_client.conversations_invite = AsyncMock(return_value=MagicMock(data={"ok": True}))
    
    result = await skill.create_incident_channel(
        name="inc-2024-001",
        users=["U123", "U456"],
        topic="Database outage"
    )
    
    assert isinstance(result, SlackChannel)
    assert result.id == "C456"
    assert result.name == "inc-2024-001"


@pytest.mark.asyncio
async def test_get_channel_history(skill, mock_client):
    """Test fetching channel history."""
    mock_client.conversations_history = AsyncMock(return_value=MagicMock(
        data={
            "ok": True,
            "messages": [
                {"ts": "1234567890.123456", "text": "Hello", "user": "U123"},
                {"ts": "1234567890.123457", "text": "World", "user": "U456"},
            ],
            "has_more": False,
        }
    ))
    
    result = await skill.get_channel_history(channel="C123", limit=10)
    
    assert result.ok is True
    assert len(result.messages) == 2
    assert result.messages[0].text == "Hello"


@pytest.mark.asyncio
async def test_archive_channel(skill, mock_client):
    """Test archiving a channel."""
    mock_client.conversations_archive = AsyncMock(return_value=MagicMock(
        data={"ok": True}
    ))
    
    result = await skill.archive_channel(channel="C123")
    
    assert result is True


def test_missing_token():
    """Test error when token is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SlackError) as exc_info:
            SlackSkill()
        assert "missing_token" in str(exc_info.value)
