"""
Tests for HTTP Skill
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.http import HTTPSkill


@pytest.fixture
def skill():
    """Create HTTP skill instance."""
    return HTTPSkill({
        "base_url": "https://api.example.com",
        "timeout": 10,
        "headers": {"X-Custom": "header"},
    })


@pytest.fixture
def mock_response():
    """Factory for mock HTTP responses."""
    def _make(json_data=None, text="", status_code=200, headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {}
        response.url = "https://api.example.com/test"
        response.text = text
        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON")
        return response
    return _make


class TestHTTPSkillInit:
    """Test skill initialization."""

    def test_default_config(self):
        """Test skill with default config."""
        skill = HTTPSkill()
        assert skill.base_url == ""
        assert skill.timeout == 30
        assert skill.verify_ssl is True

    def test_custom_config(self):
        """Test skill with custom config."""
        skill = HTTPSkill({
            "base_url": "https://api.example.com/v1",
            "timeout": 60,
            "verify_ssl": False,
        })
        assert skill.base_url == "https://api.example.com/v1"
        assert skill.timeout == 60
        assert skill.verify_ssl is False


class TestURLBuilding:
    """Test URL building."""

    def test_full_url(self, skill):
        """Test with full URL."""
        result = skill._build_url("https://other.com/path")
        assert result == "https://other.com/path"

    def test_path_with_base(self, skill):
        """Test path with base URL."""
        result = skill._build_url("/users")
        assert result == "https://api.example.com/users"

    def test_path_without_slash(self, skill):
        """Test path without leading slash."""
        result = skill._build_url("users")
        assert result == "https://api.example.com/users"

    def test_path_without_base(self):
        """Test path without base URL."""
        skill = HTTPSkill()
        result = skill._build_url("/users")
        assert result == "/users"


class TestGet:
    """Test GET action."""

    @pytest.mark.asyncio
    async def test_get_json_success(self, skill, mock_response):
        """Test successful GET with JSON response."""
        response = mock_response(json_data={"id": 1, "name": "Test"})

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            result = await skill.get("/users/1")

            assert result.success
            assert result.data.status_code == 200
            assert result.data.body == {"id": 1, "name": "Test"}
            assert result.data.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_get_text_response(self, skill, mock_response):
        """Test GET with text response."""
        response = mock_response(text="Hello World")

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            result = await skill.get("/text")

            assert result.success
            assert result.data.body == "Hello World"

    @pytest.mark.asyncio
    async def test_get_with_params(self, skill, mock_response):
        """Test GET with query parameters."""
        response = mock_response(json_data=[])

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            await skill.get("/search", params={"q": "test"})

            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"] == {"q": "test"}

    @pytest.mark.asyncio
    async def test_get_timeout(self, skill):
        """Test GET timeout."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")

            result = await skill.get("/slow")

            assert not result.success
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_connection_error(self, skill):
        """Test GET connection error."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await skill.get("/unreachable")

            assert not result.success
            assert "Connection failed" in result.error


class TestPost:
    """Test POST action."""

    @pytest.mark.asyncio
    async def test_post_json_body(self, skill, mock_response):
        """Test POST with JSON body."""
        response = mock_response(json_data={"id": 1}, status_code=201)

        with patch.object(skill.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = response

            result = await skill.post("/users", body={"name": "Test"})

            assert result.success
            assert result.data.status_code == 201
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"] == {"name": "Test"}

    @pytest.mark.asyncio
    async def test_post_string_body(self, skill, mock_response):
        """Test POST with string body."""
        response = mock_response(text="OK")

        with patch.object(skill.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = response

            result = await skill.post("/webhook", body="raw data")

            assert result.success
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["content"] == "raw data"

    @pytest.mark.asyncio
    async def test_post_with_headers(self, skill, mock_response):
        """Test POST with custom headers."""
        response = mock_response(json_data={})

        with patch.object(skill.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = response

            await skill.post(
                "/api",
                body={"data": "test"},
                headers={"X-Request-ID": "123"},
            )

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["headers"] == {"X-Request-ID": "123"}


class TestHealthCheck:
    """Test health_check action."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, skill, mock_response):
        """Test healthy endpoint."""
        response = mock_response(status_code=200)

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            result = await skill.health_check_action("https://api.example.com/health")

            assert result.success
            assert result.data.healthy is True
            assert result.data.status_code == 200
            assert result.data.response_time_ms > 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self, skill, mock_response):
        """Test unhealthy endpoint (wrong status)."""
        response = mock_response(status_code=503)

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            result = await skill.health_check_action("https://api.example.com/health")

            assert result.success  # The action succeeded
            assert result.data.healthy is False
            assert result.data.status_code == 503
            assert "Expected 200" in result.data.error

    @pytest.mark.asyncio
    async def test_health_check_custom_status(self, skill, mock_response):
        """Test health check with custom expected status."""
        response = mock_response(status_code=204)

        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response

            result = await skill.health_check_action(
                "https://api.example.com/ready",
                expected_status=204,
            )

            assert result.data.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, skill):
        """Test health check timeout."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")

            result = await skill.health_check_action(
                "https://api.example.com/health",
                timeout=2,
            )

            assert result.success  # Action succeeded
            assert result.data.healthy is False
            assert result.data.error == "Request timed out"

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, skill):
        """Test health check connection error."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await skill.health_check_action("https://unreachable.local/health")

            assert result.success  # Action succeeded
            assert result.data.healthy is False
            assert result.data.error is not None


class TestActionRegistration:
    """Test action registration."""

    def test_actions_registered(self, skill):
        """Test that all actions are registered."""
        actions = skill.get_actions()
        action_names = [a.name for a in actions]

        assert "get" in action_names
        assert "post" in action_names
        assert "health_check" in action_names

    def test_no_approval_required(self, skill):
        """Test that HTTP actions don't require approval."""
        for action_def in skill.get_actions():
            assert not action_def.requires_approval
