"""
Tests for Prometheus Skill
"""

# Import from skills directory (relative to project root)
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.prometheus import PrometheusSkill


@pytest.fixture
def skill():
    """Create Prometheus skill instance."""
    return PrometheusSkill({
        "url": "http://prometheus:9090",
        "alertmanager_url": "http://alertmanager:9093",
        "timeout": 10,
    })


@pytest.fixture
def mock_response():
    """Factory for mock HTTP responses."""
    def _make(json_data, status_code=200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=response
            )
        return response
    return _make


class TestPrometheusSkillInit:
    """Test skill initialization."""

    def test_default_config(self):
        """Test skill with default config."""
        skill = PrometheusSkill()
        assert skill.url == "http://localhost:9090"
        assert skill.alertmanager_url is None
        assert skill.timeout == 30

    def test_custom_config(self):
        """Test skill with custom config."""
        skill = PrometheusSkill({
            "url": "http://custom:9090",
            "alertmanager_url": "http://alertmanager:9093",
            "timeout": 60,
        })
        assert skill.url == "http://custom:9090"
        assert skill.alertmanager_url == "http://alertmanager:9093"
        assert skill.timeout == 60

    def test_basic_auth_config(self):
        """Test skill with basic auth."""
        skill = PrometheusSkill({
            "url": "http://prometheus:9090",
            "auth": {
                "type": "basic",
                "username": "admin",
                "password": "secret",
            },
        })
        assert skill._auth is not None

    def test_bearer_auth_config(self):
        """Test skill with bearer token."""
        skill = PrometheusSkill({
            "url": "http://prometheus:9090",
            "auth": {
                "type": "bearer",
                "token": "my-token",
            },
        })
        headers = skill._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my-token"


class TestHealthCheck:
    """Test health check action."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, skill, mock_response):
        """Test successful health check."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({})

            result = await skill.health_check()

            assert result.success
            assert result.data["status"] == "healthy"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, skill, mock_response):
        """Test failed health check."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await skill.health_check()

            assert not result.success
            assert "Connection failed" in result.error


class TestQuery:
    """Test query action."""

    @pytest.mark.asyncio
    async def test_query_success(self, skill, mock_response):
        """Test successful instant query."""
        response_data = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "node"},
                        "value": [1234567890, "1"],
                    }
                ],
            },
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.query("up{job='node'}")

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].metric_name == "up"
            assert result.data[0].labels["job"] == "node"
            assert result.data[0].value == 1.0

    @pytest.mark.asyncio
    async def test_query_empty_result(self, skill, mock_response):
        """Test query with no results."""
        response_data = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.query("nonexistent_metric")

            assert result.success
            assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_query_error(self, skill, mock_response):
        """Test query with Prometheus error."""
        response_data = {
            "status": "error",
            "error": "invalid expression",
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.query("invalid{")

            assert not result.success
            assert "invalid expression" in result.error


class TestQueryRange:
    """Test range query action."""

    @pytest.mark.asyncio
    async def test_query_range_success(self, skill, mock_response):
        """Test successful range query."""
        now = datetime.now().timestamp()
        response_data = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "cpu_usage", "pod": "app-1"},
                        "values": [
                            [now - 60, "0.5"],
                            [now - 30, "0.6"],
                            [now, "0.7"],
                        ],
                    }
                ],
            },
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.query_range("cpu_usage", step="30s")

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].metric_name == "cpu_usage"
            assert len(result.data[0].values) == 3
            assert result.data[0].value == 0.7  # Last value


class TestGetAlerts:
    """Test get_alerts action."""

    @pytest.mark.asyncio
    async def test_get_alerts_success(self, skill, mock_response):
        """Test getting active alerts."""
        response_data = {
            "status": "success",
            "data": {
                "alerts": [
                    {
                        "labels": {"alertname": "HighCPU", "severity": "warning"},
                        "annotations": {"summary": "CPU usage is high"},
                        "state": "firing",
                        "activeAt": "2024-01-15T10:00:00Z",
                        "value": "0.95",
                    },
                    {
                        "labels": {"alertname": "LowMemory", "severity": "critical"},
                        "annotations": {"summary": "Memory is low"},
                        "state": "pending",
                        "activeAt": "2024-01-15T10:05:00Z",
                    },
                ],
            },
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.get_alerts()

            assert result.success
            assert len(result.data) == 2
            assert result.data[0].alert_name == "HighCPU"
            assert result.data[0].state == "firing"
            assert result.data[0].value == 0.95

    @pytest.mark.asyncio
    async def test_get_alerts_filtered(self, skill, mock_response):
        """Test filtering alerts by state."""
        response_data = {
            "status": "success",
            "data": {
                "alerts": [
                    {"labels": {"alertname": "Alert1"}, "state": "firing", "annotations": {}},
                    {"labels": {"alertname": "Alert2"}, "state": "pending", "annotations": {}},
                ],
            },
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.get_alerts(state="firing")

            assert result.success
            assert len(result.data) == 1
            assert result.data[0].alert_name == "Alert1"


class TestGetTargets:
    """Test get_targets action."""

    @pytest.mark.asyncio
    async def test_get_targets_success(self, skill, mock_response):
        """Test getting scrape targets."""
        response_data = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "labels": {"job": "node", "instance": "localhost:9100"},
                        "health": "up",
                        "lastScrape": "2024-01-15T10:00:00Z",
                        "lastScrapeDuration": 0.05,
                        "lastError": "",
                    },
                    {
                        "labels": {"job": "prometheus", "instance": "localhost:9090"},
                        "health": "up",
                        "lastScrape": "2024-01-15T10:00:00Z",
                        "lastScrapeDuration": 0.02,
                    },
                ],
            },
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            result = await skill.get_targets()

            assert result.success
            assert len(result.data) == 2
            assert result.data[0].job == "node"
            assert result.data[0].health == "up"


class TestSilenceAlert:
    """Test silence_alert action."""

    @pytest.mark.asyncio
    async def test_silence_alert_success(self, skill, mock_response):
        """Test creating alert silence."""
        response_data = {"silenceID": "silence-123"}

        with patch.object(skill.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response(response_data)

            result = await skill.silence_alert("HighCPU", "2h", "Maintenance window")

            assert result.success
            assert result.data.silence_id == "silence-123"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_silence_alert_no_alertmanager(self):
        """Test silence without Alertmanager configured."""
        skill = PrometheusSkill({"url": "http://prometheus:9090"})

        result = await skill.silence_alert("HighCPU", "2h")

        assert not result.success
        assert "Alertmanager URL not configured" in result.error


class TestDeleteSilence:
    """Test delete_silence action."""

    @pytest.mark.asyncio
    async def test_delete_silence_success(self, skill, mock_response):
        """Test deleting silence."""
        with patch.object(skill.client, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_response({})

            result = await skill.delete_silence("silence-123")

            assert result.success
            assert result.data is True

    @pytest.mark.asyncio
    async def test_delete_silence_not_found(self, skill, mock_response):
        """Test deleting non-existent silence."""
        with patch.object(skill.client, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_response({}, status_code=404)

            result = await skill.delete_silence("nonexistent")

            assert not result.success
            assert "not found" in result.error.lower()


class TestDurationParsing:
    """Test duration string parsing."""

    def test_parse_seconds(self, skill):
        """Test parsing seconds."""
        assert skill._parse_duration("30s") == 30

    def test_parse_minutes(self, skill):
        """Test parsing minutes."""
        assert skill._parse_duration("5m") == 300

    def test_parse_hours(self, skill):
        """Test parsing hours."""
        assert skill._parse_duration("2h") == 7200

    def test_parse_days(self, skill):
        """Test parsing days."""
        assert skill._parse_duration("1d") == 86400

    def test_parse_invalid(self, skill):
        """Test parsing invalid duration."""
        with pytest.raises(ValueError):
            skill._parse_duration("invalid")


class TestActionRegistration:
    """Test action registration."""

    def test_actions_registered(self, skill):
        """Test that all actions are registered."""
        actions = skill.get_actions()
        action_names = [a.name for a in actions]

        assert "query" in action_names
        assert "query_range" in action_names
        assert "get_alerts" in action_names
        assert "get_alert_rules" in action_names
        assert "silence_alert" in action_names
        assert "delete_silence" in action_names
        assert "get_targets" in action_names

    def test_invoke_action(self, skill, mock_response):
        """Test invoking action by name."""
        response_data = {
            "status": "success",
            "data": {"result": []},
        }

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                skill.invoke("query", promql="up")
            )

            assert result.success

    def test_invoke_unknown_action(self, skill):
        """Test invoking unknown action."""
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            skill.invoke("nonexistent")
        )

        assert not result.success
        assert "Unknown action" in result.error
