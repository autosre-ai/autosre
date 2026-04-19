"""Tests for Elasticsearch skill."""


import pytest

from skills.elasticsearch.actions import ElasticsearchSkill


@pytest.fixture
def es_skill():
    """Create an ElasticsearchSkill instance for testing."""
    config = {
        "hosts": ["http://localhost:9200"],
        "username": "elastic",
        "password": "password",
    }
    return ElasticsearchSkill(config)


class TestElasticsearchSkillInit:
    """Test ElasticsearchSkill initialization."""

    def test_init_with_config(self):
        config = {
            "hosts": ["http://es1:9200", "http://es2:9200"],
            "api_key": "test-api-key",
            "timeout": 60,
        }
        skill = ElasticsearchSkill(config)

        assert len(skill.hosts) == 2
        assert skill.api_key == "test-api-key"
        assert skill.timeout == 60
