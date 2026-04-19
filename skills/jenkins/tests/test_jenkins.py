"""Tests for Jenkins skill."""

import pytest
from skills.jenkins.actions import JenkinsSkill


@pytest.fixture
def jenkins_skill():
    config = {
        "url": "https://jenkins.example.com",
        "username": "admin",
        "api_token": "token123",
    }
    return JenkinsSkill(config)


class TestJenkinsSkillInit:
    def test_init_with_config(self):
        config = {
            "url": "https://jenkins.test.com",
            "username": "api_user",
            "api_token": "secret_token",
            "timeout": 60,
        }
        skill = JenkinsSkill(config)
        
        assert skill.url == "https://jenkins.test.com"
        assert skill.username == "api_user"
        assert skill.timeout == 60
