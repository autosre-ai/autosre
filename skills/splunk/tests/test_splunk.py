"""Tests for Splunk skill."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from skills.splunk.actions import SplunkSkill


@pytest.fixture
def splunk_skill():
    """Create a SplunkSkill instance for testing."""
    config = {
        "host": "splunk.example.com",
        "port": 8089,
        "username": "admin",
        "password": "password",
    }
    return SplunkSkill(config)


class TestSplunkSkillInit:
    """Test SplunkSkill initialization."""

    def test_init_with_config(self):
        config = {
            "host": "splunk.test.com",
            "port": 8089,
            "username": "api_user",
            "password": "secret",
            "timeout": 120,
        }
        skill = SplunkSkill(config)
        
        assert skill.host == "splunk.test.com"
        assert skill.port == 8089
        assert skill.username == "api_user"
        assert skill.timeout == 120
        assert "splunk.test.com:8089" in skill.base_url
