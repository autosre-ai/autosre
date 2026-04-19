"""Tests for PagerDuty skill."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.pagerduty import (
    Incident,
    IncidentList,
    OnCall,
    PagerDutyError,
    PagerDutySkill,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    session.closed = False
    return session


@pytest.fixture
def skill():
    """Create a PagerDutySkill with mocked config."""
    with patch.dict("os.environ", {
        "PAGERDUTY_API_KEY": "test-api-key",
        "PAGERDUTY_FROM_EMAIL": "test@example.com",
    }):
        return PagerDutySkill()


@pytest.mark.asyncio
async def test_list_incidents(skill):
    """Test listing incidents."""
    mock_response = {
        "incidents": [
            {
                "id": "P123",
                "incident_number": 1,
                "title": "Test Incident",
                "status": "triggered",
                "urgency": "high",
                "service": {"id": "S123", "summary": "Web Service"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://example.pagerduty.com/incidents/P123",
            }
        ],
        "total": 1,
        "more": False,
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.list_incidents(status="triggered")

    assert isinstance(result, IncidentList)
    assert len(result.incidents) == 1
    assert result.incidents[0].id == "P123"
    assert result.incidents[0].is_triggered


@pytest.mark.asyncio
async def test_get_incident(skill):
    """Test getting incident details."""
    mock_response = {
        "incident": {
            "id": "P123",
            "incident_number": 1,
            "title": "Test Incident",
            "status": "acknowledged",
            "urgency": "high",
            "service": {"id": "S123", "summary": "Web Service"},
            "created_at": "2024-01-01T00:00:00Z",
            "html_url": "https://example.pagerduty.com/incidents/P123",
        }
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_incident("P123")

    assert isinstance(result, Incident)
    assert result.id == "P123"
    assert result.is_acknowledged


@pytest.mark.asyncio
async def test_acknowledge_incident(skill):
    """Test acknowledging an incident."""
    mock_response = {
        "incident": {
            "id": "P123",
            "incident_number": 1,
            "title": "Test Incident",
            "status": "acknowledged",
            "urgency": "high",
            "service": {"id": "S123", "summary": "Web Service"},
            "created_at": "2024-01-01T00:00:00Z",
            "html_url": "https://example.pagerduty.com/incidents/P123",
        }
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await skill.acknowledge_incident("P123")

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "PUT"
        assert "acknowledged" in str(call_args)

    assert result.status == "acknowledged"


@pytest.mark.asyncio
async def test_resolve_incident(skill):
    """Test resolving an incident."""
    mock_response = {
        "incident": {
            "id": "P123",
            "incident_number": 1,
            "title": "Test Incident",
            "status": "resolved",
            "urgency": "high",
            "service": {"id": "S123", "summary": "Web Service"},
            "created_at": "2024-01-01T00:00:00Z",
            "resolved_at": "2024-01-01T01:00:00Z",
            "html_url": "https://example.pagerduty.com/incidents/P123",
        }
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.resolve_incident("P123")

    assert result.is_resolved
    assert result.resolved_at is not None


@pytest.mark.asyncio
async def test_get_oncall(skill):
    """Test getting on-call schedule."""
    mock_response = {
        "oncalls": [
            {
                "user": {
                    "id": "U123",
                    "summary": "John Doe",
                    "email": "john@example.com",
                },
                "schedule": {
                    "id": "SCHED123",
                    "summary": "Primary On-Call",
                },
                "escalation_level": 1,
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-01-08T00:00:00Z",
            }
        ]
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_oncall("SCHED123")

    assert len(result) == 1
    assert isinstance(result[0], OnCall)
    assert result[0].user.name == "John Doe"
    assert result[0].escalation_level == 1


@pytest.mark.asyncio
async def test_create_incident(skill):
    """Test creating a new incident."""
    mock_response = {
        "incident": {
            "id": "P456",
            "incident_number": 2,
            "title": "New Incident",
            "status": "triggered",
            "urgency": "high",
            "service": {"id": "S123", "summary": "Web Service"},
            "created_at": "2024-01-01T00:00:00Z",
            "html_url": "https://example.pagerduty.com/incidents/P456",
        }
    }

    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await skill.create_incident(
            service_id="S123",
            title="New Incident",
            body="Detailed description",
        )

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"

    assert result.id == "P456"
    assert result.is_triggered


def test_missing_api_key():
    """Test error when API key is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(PagerDutyError) as exc_info:
            PagerDutySkill()
        assert exc_info.value.code == 401


def test_missing_from_email():
    """Test error when from email is missing."""
    with patch.dict("os.environ", {"PAGERDUTY_API_KEY": "test"}, clear=True):
        with pytest.raises(PagerDutyError) as exc_info:
            PagerDutySkill()
        assert exc_info.value.code == 400
