"""Tests for dependency-checker agent."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        assert agent_yaml["name"] == "dependency-checker"
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        triggers = agent_yaml["triggers"]
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        assert schedule["cron"] == "*/5 * * * *"

    def test_required_skills(self, agent_yaml):
        skills = agent_yaml["skills"]
        assert "http" in skills
        assert "dns" in skills
        assert "slack" in skills

    def test_dependencies_configured(self, agent_yaml):
        deps = agent_yaml["config"]["dependencies"]
        assert "internal" in deps
        assert "external" in deps
        assert "dns" in deps

    def test_health_criteria(self, agent_yaml):
        criteria = agent_yaml["config"]["health_criteria"]
        assert criteria["response_time_warning_ms"] < criteria["response_time_critical_ms"]
        assert criteria["consecutive_failures_alert"] < criteria["consecutive_failures_page"]


class TestInternalDependencies:
    """Test internal dependency configuration."""

    def test_internal_deps_have_required_fields(self, agent_yaml):
        for dep in agent_yaml["config"]["dependencies"]["internal"]:
            assert "name" in dep
            assert "url" in dep
            assert "timeout_seconds" in dep

    def test_critical_flag(self, agent_yaml):
        internal = agent_yaml["config"]["dependencies"]["internal"]
        critical_deps = [d for d in internal if d.get("critical", False)]
        assert len(critical_deps) > 0

    def test_internal_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_internal_services"), None)
        assert step is not None
        assert step["action"] == "http.batch_check"


class TestExternalDependencies:
    """Test external dependency configuration."""

    def test_external_deps_have_required_fields(self, agent_yaml):
        for dep in agent_yaml["config"]["dependencies"]["external"]:
            assert "name" in dep
            assert "url" in dep
            assert "timeout_seconds" in dep

    def test_expected_status_override(self, agent_yaml):
        external = agent_yaml["config"]["dependencies"]["external"]
        stripe = next((d for d in external if d["name"] == "stripe-api"), None)
        assert stripe is not None
        assert stripe.get("expected_status") == 401

    def test_external_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_external_services"), None)
        assert step is not None


class TestDNSResolution:
    """Test DNS resolution checking."""

    def test_dns_deps_configured(self, agent_yaml):
        dns = agent_yaml["config"]["dependencies"]["dns"]
        assert len(dns) > 0
        for d in dns:
            assert "name" in d
            assert "host" in d

    def test_dns_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_dns_resolution"), None)
        assert step is not None
        assert step["action"] == "dns.resolve_batch"


class TestConsecutiveFailures:
    """Test consecutive failure tracking."""

    def test_failure_thresholds(self, agent_yaml):
        criteria = agent_yaml["config"]["health_criteria"]
        assert criteria["consecutive_failures_alert"] == 2
        assert criteria["consecutive_failures_page"] == 5

    def test_failure_count_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "check_consecutive_failures"), None)
        assert step is not None

    def test_update_failure_counts_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "update_failure_counts"), None)
        assert step is not None

    def test_failure_tracking_logic(self):
        """Test consecutive failure counting logic."""
        previous = {"service-a": 2, "service-b": 0}
        current_issues = [{"name": "service-a"}, {"name": "service-c"}]

        new_counts = {}
        for issue in current_issues:
            name = issue["name"]
            new_counts[name] = previous.get(name, 0) + 1

        # Reset healthy services
        for name in previous:
            if name not in [i["name"] for i in current_issues]:
                new_counts[name] = 0

        assert new_counts["service-a"] == 3  # Incremented
        assert new_counts["service-b"] == 0  # Reset (healthy)
        assert new_counts["service-c"] == 1  # New failure


class TestAlertConditions:
    """Test alert conditions."""

    def test_degraded_alert_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "notify_degraded"), None)
        assert step is not None
        assert "condition" in step

    def test_unhealthy_alert_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "notify_unhealthy"), None)
        assert step is not None

    def test_critical_page_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "page_critical_failures"), None)
        assert step is not None
        assert "condition" in step


class TestHealthStatus:
    """Test health status evaluation."""

    def test_status_aggregation_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "aggregate_health_status"), None)
        assert step is not None

    def test_health_status_categorization(self):
        """Test health status categorization."""
        results = [
            {"name": "svc-a", "status_code": 200, "response_time_ms": 50},
            {"name": "svc-b", "status_code": 200, "response_time_ms": 800},
            {"name": "svc-c", "status_code": 500, "response_time_ms": 100},
            {"name": "svc-d", "error": "Connection refused"}
        ]

        warning_threshold = 500

        healthy = []
        degraded = []
        unhealthy = []

        for r in results:
            if r.get("error") or r.get("status_code", 0) >= 500:
                unhealthy.append(r)
            elif r.get("response_time_ms", 0) > warning_threshold:
                degraded.append(r)
            else:
                healthy.append(r)

        assert len(healthy) == 1
        assert len(degraded) == 1
        assert len(unhealthy) == 2


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "push_metrics"), None)
        assert step is not None

    def test_metrics_include_counts(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"]
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])
        assert "opensre_dependency_healthy" in params_str
        assert "opensre_dependency_unhealthy" in params_str


class TestIntegration:
    """Integration tests."""

    def test_full_health_check_workflow(self):
        """Test complete health check workflow."""
        # Simulate check results
        internal_results = [
            {"name": "user-service", "status": "healthy", "response_time_ms": 45},
            {"name": "payment-service", "status": "unhealthy", "error": "Connection refused"}
        ]

        external_results = [
            {"name": "stripe-api", "status": "healthy", "response_time_ms": 120},
            {"name": "aws-s3", "status": "healthy", "response_time_ms": 85}
        ]


        # Aggregate
        total_healthy = (
            len([r for r in internal_results if r["status"] == "healthy"]) +
            len([r for r in external_results if r["status"] == "healthy"])
        )
        total_unhealthy = (
            len([r for r in internal_results if r["status"] == "unhealthy"]) +
            len([r for r in external_results if r["status"] == "unhealthy"])
        )

        assert total_healthy == 3
        assert total_unhealthy == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
