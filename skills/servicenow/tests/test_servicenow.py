"""Tests for ServiceNow skill."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from skills.servicenow.actions import ServiceNowSkill, Incident


@pytest.fixture
def servicenow_skill():
    """Create a ServiceNowSkill instance for testing."""
    config = {
        "instance": "test.service-now.com",
        "username": "admin",
        "password": "password",
    }
    return ServiceNowSkill(config)


@pytest.fixture
async def initialized_skill(servicenow_skill):
    """Create an initialized ServiceNowSkill."""
    await servicenow_skill.initialize()
    yield servicenow_skill
    await servicenow_skill.shutdown()


class TestServiceNowSkillInit:
    """Test ServiceNowSkill initialization."""

    def test_init_with_config(self):
        config = {
            "instance": "mycompany.service-now.com",
            "username": "api_user",
            "password": "secret",
            "timeout": 60,
        }
        skill = ServiceNowSkill(config)
        
        assert skill.instance == "mycompany.service-now.com"
        assert skill.username == "api_user"
        assert skill.timeout == 60
        assert "mycompany.service-now.com" in skill.base_url


class TestGetIncidents:
    """Test get_incidents action."""

    @pytest.mark.asyncio
    async def test_get_incidents_success(self, initialized_skill):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "abc123",
                    "number": "INC0001234",
                    "short_description": "Server down",
                    "description": "Production server is not responding",
                    "state": "1",
                    "urgency": "1",
                    "impact": "1",
                    "priority": "1",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(initialized_skill._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await initialized_skill.get_incidents()
            
            assert result.success
            assert len(result.data) == 1
            assert result.data[0].number == "INC0001234"
            assert result.data[0].short_description == "Server down"
