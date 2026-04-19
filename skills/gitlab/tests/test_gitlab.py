"""Tests for GitLab skill."""

import pytest

from skills.gitlab.actions import GitLabSkill


@pytest.fixture
def gitlab_skill():
    config = {
        "url": "https://gitlab.example.com",
        "token": "test-token",
    }
    return GitLabSkill(config)


class TestGitLabSkillInit:
    def test_init_with_config(self):
        config = {
            "url": "https://gitlab.test.com",
            "token": "secret_token",
            "timeout": 60,
        }
        skill = GitLabSkill(config)

        assert skill.url == "https://gitlab.test.com"
        assert skill.token == "secret_token"
        assert skill.timeout == 60

    def test_init_defaults(self):
        skill = GitLabSkill({"token": "test"})
        assert skill.url == "https://gitlab.com"
