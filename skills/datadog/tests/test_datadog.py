"""Tests for Datadog skill."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import time

from skills.datadog.actions import DatadogSkill, MetricSeries, Monitor, Event, Incident


@pytest.fixture
def datadog_skill():
    """Create a DatadogSkill instance for testing."""
    config = {
        "api_key": "test-api-key",
        "app_key": "test-app-key",
        "site": "datadoghq.com",
    }
    return DatadogSkill(config)


@pytest.fixture
async def initialized_skill(datadog_skill):
    """Create an initialized DatadogSkill."""
    await datadog_skill.initialize()
    yield datadog_skill
    await datadog_skill.shutdown()


class TestDatadogSkillInit:
    """Test DatadogSkill initialization."""

    def test_init_with_config(self):
        config = {
            "api_key": "test-api",
            "app_key": "test-app",
            "site": "datadoghq.eu",
            "timeout": 60,
        }
        skill = DatadogSkill(config)
        
        assert skill.api_key == "test-api"
        assert skill.app_key == "test-app"
        assert skill.site == "datadoghq.eu"
        assert skill.timeout == 60
        assert skill.base_url == "https://api.datadoghq.eu"

    def test_init_defaults(self):
        skill = DatadogSkill({})
        
        assert skill.site == "datadoghq.com"
        assert skill.timeout == 30


class TestQueryMetrics:
    """Test query_metrics action."""

    @pytest.mark.asyncio
    async def test_query_metrics_success(self, initialized_skill):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "series": [
                {
                    "metric": "system.cpu.user",
                    "scope": "host:web-01",
                    "pointlist": [[1234567890000, 45.5], [1234567950000, 46.2]],
                    "unit": [{"name": "percent"}],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(initialized_skill._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await initialized_skill.query_metrics("avg:system.cpu.user{*}")
            
            assert result.success
            assert len(result.data) == 1
            assert result.data[0].metric == "system.cpu.user"
            assert len(result.data[0].points) == 2

    @pytest.mark.asyncio
    async def test_query_metrics_not_initialized(self, datadog_skill):
        result = await datadog_skill.query_metrics("avg:system.cpu.user{*}")
        
        assert not result.success
        assert "not initialized" in result.error.lower()


class TestGetMonitors:
    """Test get_monitors action."""

    @pytest.mark.asyncio
    async def test_get_monitors_success(self, initialized_skill):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 123,
                "name": "High CPU",
                "type": "metric alert",
                "query": "avg:system.cpu.user{*} > 90",
                "message": "CPU is too high",
                "overall_state": "Alert",
                "tags": ["env:prod"],
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(initialized_skill._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await initialized_skill.get_monitors()
            
            assert result.success
            assert len(result.data) == 1
            assert result.data[0].name == "High CPU"
            assert result.data[0].overall_state == "Alert"
