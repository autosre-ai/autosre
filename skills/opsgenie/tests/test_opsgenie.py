"""Tests for OpsGenie skill."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.opsgenie.actions import OpsGenieSkill


@pytest.fixture
def opsgenie_skill():
    """Create an OpsGenieSkill instance for testing."""
    config = {
        "api_key": "test-api-key",
        "api_url": "https://api.opsgenie.com",
    }
    return OpsGenieSkill(config)


@pytest.fixture
async def initialized_skill(opsgenie_skill):
    """Create an initialized OpsGenieSkill."""
    await opsgenie_skill.initialize()
    yield opsgenie_skill
    await opsgenie_skill.shutdown()


class TestOpsGenieSkillInit:
    """Test OpsGenieSkill initialization."""

    def test_init_with_config(self):
        config = {
            "api_key": "test-key",
            "api_url": "https://api.eu.opsgenie.com",
            "timeout": 60,
        }
        skill = OpsGenieSkill(config)

        assert skill.api_key == "test-key"
        assert skill.api_url == "https://api.eu.opsgenie.com"
        assert skill.timeout == 60


class TestListAlerts:
    """Test list_alerts action."""

    @pytest.mark.asyncio
    async def test_list_alerts_success(self, initialized_skill):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "alert-123",
                    "tinyId": "1",
                    "message": "High CPU usage",
                    "status": "open",
                    "priority": "P2",
                    "tags": ["infrastructure"],
                    "acknowledged": False,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(initialized_skill._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await initialized_skill.list_alerts()

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].message == "High CPU usage"
            assert result.data[0].priority == "P2"
