"""Tests for Vault skill."""

import pytest

from skills.vault.actions import VaultSkill


@pytest.fixture
def vault_skill():
    config = {
        "url": "https://vault.example.com",
        "token": "test-token",
    }
    return VaultSkill(config)


class TestVaultSkillInit:
    def test_init_with_config(self):
        config = {
            "url": "https://vault.test.com",
            "token": "secret_token",
            "namespace": "admin",
            "timeout": 60,
        }
        skill = VaultSkill(config)

        assert skill.url == "https://vault.test.com"
        assert skill.token == "secret_token"
        assert skill.namespace == "admin"
        assert skill.timeout == 60

    def test_init_approle(self):
        config = {
            "url": "https://vault.test.com",
            "auth_method": "approle",
            "role_id": "role123",
            "secret_id": "secret456",
        }
        skill = VaultSkill(config)

        assert skill.auth_method == "approle"
