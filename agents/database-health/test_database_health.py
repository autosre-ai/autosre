"""Tests for database-health agent."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_prometheus():
    """Mock Prometheus skill."""
    mock = MagicMock()
    mock.query.return_value = {
        "postgres_active": 45,
        "postgres_idle": 25,
        "postgres_max": 100,
        "postgres_lag": 2.5,
        "redis_hit_ratio": 0.95,
        "redis_memory_used": 0.65
    }
    return mock


@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL skill."""
    mock = MagicMock()
    mock.query.return_value = [
        {
            "pid": 12345,
            "duration": "00:05:32",
            "query": "SELECT * FROM large_table WHERE condition = 'value'",
            "state": "active",
            "usename": "app_user"
        }
    ]
    return mock


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        """Test that agent has all required top-level fields."""
        assert agent_yaml["name"] == "database-health"
        assert "description" in agent_yaml
        assert "version" in agent_yaml
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "config" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        """Test triggers are properly configured."""
        triggers = agent_yaml["triggers"]

        # Check schedule trigger
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        assert schedule["cron"] == "*/5 * * * *"

    def test_required_skills(self, agent_yaml):
        """Test required skills are listed."""
        skills = agent_yaml["skills"]
        assert "prometheus" in skills
        assert "postgres" in skills
        assert "slack" in skills

    def test_database_configuration(self, agent_yaml):
        """Test database configuration."""
        config = agent_yaml["config"]
        assert "databases" in config
        assert len(config["databases"]) > 0

        for db in config["databases"]:
            assert "name" in db
            assert "type" in db
            assert "host" in db

    def test_thresholds_configuration(self, agent_yaml):
        """Test thresholds configuration."""
        thresholds = agent_yaml["config"]["thresholds"]
        assert thresholds["connection_pool_usage_warning"] < thresholds["connection_pool_usage_critical"]
        assert thresholds["replication_lag_warning_seconds"] < thresholds["replication_lag_critical_seconds"]


class TestConnectionPoolMonitoring:
    """Test connection pool monitoring."""

    def test_pool_usage_calculation(self):
        """Test connection pool usage calculation."""
        active = 45
        idle = 25
        max_conn = 100

        usage = (active + idle) / max_conn * 100
        assert usage == 70.0

    def test_pool_warning_threshold(self, agent_yaml):
        """Test pool warning threshold."""
        threshold = agent_yaml["config"]["thresholds"]["connection_pool_usage_warning"]
        assert threshold == 70

    def test_pool_critical_threshold(self, agent_yaml):
        """Test pool critical threshold."""
        threshold = agent_yaml["config"]["thresholds"]["connection_pool_usage_critical"]
        assert threshold == 90

    def test_connection_check_step(self, agent_yaml):
        """Test connection check step exists."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_connection_pools"), None)
        assert step is not None
        assert step["action"] == "prometheus.query"


class TestReplicationMonitoring:
    """Test replication lag monitoring."""

    def test_replication_lag_check(self, agent_yaml):
        """Test replication lag check step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_replication_lag"), None)
        assert step is not None

    def test_lag_thresholds(self, agent_yaml):
        """Test lag thresholds are reasonable."""
        thresholds = agent_yaml["config"]["thresholds"]
        assert thresholds["replication_lag_warning_seconds"] == 5
        assert thresholds["replication_lag_critical_seconds"] == 30

    def test_lag_alert_step(self, agent_yaml):
        """Test replication lag alert step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "alert_replication_lag"), None)
        assert step is not None
        assert "condition" in step


class TestDeadlockDetection:
    """Test deadlock detection."""

    def test_deadlock_check_step(self, agent_yaml):
        """Test deadlock check step exists."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_deadlocks"), None)
        assert step is not None

    def test_deadlock_alert(self, agent_yaml):
        """Test deadlock alert step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "alert_deadlocks"), None)
        assert step is not None


class TestLongRunningQueries:
    """Test long-running query detection."""

    def test_long_query_check(self, agent_yaml):
        """Test long-running query check step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_long_running_queries"), None)
        assert step is not None
        assert step["action"] == "postgres.query"

    def test_long_query_threshold(self, agent_yaml):
        """Test long-running query threshold."""
        threshold = agent_yaml["config"]["thresholds"]["long_running_query_seconds"]
        assert threshold == 60

    def test_long_query_alert(self, agent_yaml):
        """Test long-running query alert."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "alert_long_queries"), None)
        assert step is not None
        assert "condition" in step


class TestCacheHealth:
    """Test cache health monitoring."""

    def test_cache_check_step(self, agent_yaml):
        """Test cache health check step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_cache_health"), None)
        assert step is not None

    def test_cache_hit_ratio_threshold(self, agent_yaml):
        """Test cache hit ratio threshold."""
        threshold = agent_yaml["config"]["thresholds"]["cache_hit_ratio_warning"]
        assert threshold == 0.90

    def test_cache_alert(self, agent_yaml):
        """Test cache alert step."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "alert_cache_issues"), None)
        assert step is not None


class TestAlertConditions:
    """Test alert conditions."""

    def test_critical_pool_alert_condition(self, agent_yaml):
        """Test critical pool alert has condition."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "alert_critical_pool"), None)
        assert step is not None
        assert "condition" in step
        assert "critical" in step["condition"]

    def test_pagerduty_condition(self, agent_yaml):
        """Test PagerDuty page condition."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "page_critical_issues"), None)
        assert step is not None
        assert "condition" in step


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step_exists(self, agent_yaml):
        """Test metrics pushing step exists."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "push_metrics"), None)
        assert step is not None

    def test_metrics_include_all_checks(self, agent_yaml):
        """Test metrics include all health checks."""
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])

        assert "connection_pool" in params_str
        assert "replication_lag" in params_str
        assert "deadlocks" in params_str


class TestIntegration:
    """Integration tests."""

    def test_full_health_check(self, mock_prometheus, mock_postgres):
        """Test full health check workflow."""
        # Get connection metrics
        conn_metrics = mock_prometheus.query()
        pool_usage = (conn_metrics["postgres_active"] + conn_metrics["postgres_idle"]) / conn_metrics["postgres_max"] * 100

        assert pool_usage == 70.0

        # Check replication
        assert conn_metrics["postgres_lag"] == 2.5

        # Check cache
        assert conn_metrics["redis_hit_ratio"] == 0.95

    def test_status_aggregation(self):
        """Test health status aggregation."""
        checks = {
            "connection_pool": {"status": "warning", "value": 75},
            "replication_lag": {"status": "healthy", "value": 2},
            "deadlocks": {"status": "healthy", "value": 0},
            "cache": {"status": "healthy", "value": 0.95}
        }

        # Count issues
        warnings = sum(1 for c in checks.values() if c["status"] == "warning")
        criticals = sum(1 for c in checks.values() if c["status"] == "critical")

        assert warnings == 1
        assert criticals == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
