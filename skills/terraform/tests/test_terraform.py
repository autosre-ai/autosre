"""Tests for Terraform skill."""

import pytest
from skills.terraform.actions import TerraformSkill


@pytest.fixture
def terraform_skill():
    config = {
        "url": "https://app.terraform.io",
        "token": "test-token",
        "organization": "my-org",
    }
    return TerraformSkill(config)


class TestTerraformSkillInit:
    def test_init_with_config(self):
        config = {
            "url": "https://tfe.example.com",
            "token": "secret_token",
            "organization": "test-org",
            "timeout": 120,
        }
        skill = TerraformSkill(config)
        
        assert skill.url == "https://tfe.example.com"
        assert skill.organization == "test-org"
        assert skill.timeout == 120

    def test_init_defaults(self):
        skill = TerraformSkill({"token": "t", "organization": "o"})
        assert skill.url == "https://app.terraform.io"
