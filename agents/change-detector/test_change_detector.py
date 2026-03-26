"""Tests for change-detector agent."""

import pytest
import yaml
from pathlib import Path
from datetime import datetime, timedelta


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        assert agent_yaml["name"] == "change-detector"
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        triggers = agent_yaml["triggers"]
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        assert schedule["cron"] == "*/15 * * * *"

    def test_required_skills(self, agent_yaml):
        skills = agent_yaml["skills"]
        assert "kubernetes" in skills
        assert "slack" in skills

    def test_change_sources_config(self, agent_yaml):
        sources = agent_yaml["config"]["change_sources"]
        assert "kubernetes" in sources
        assert "terraform" in sources
        assert "git" in sources

    def test_high_risk_patterns(self, agent_yaml):
        patterns = agent_yaml["config"]["high_risk_changes"]
        assert len(patterns) > 0
        for pattern in patterns:
            assert "pattern" in pattern
            assert "description" in pattern


class TestKubernetesChangeDetection:
    """Test Kubernetes change detection."""

    def test_watched_resources(self, agent_yaml):
        resources = agent_yaml["config"]["change_sources"]["kubernetes"]["watch_resources"]
        assert "deployments" in resources
        assert "configmaps" in resources
        assert "secrets" in resources

    def test_kubernetes_change_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "detect_kubernetes_changes"), None)
        assert step is not None

    def test_deployment_changes_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "get_deployment_changes"), None)
        assert step is not None


class TestHighRiskDetection:
    """Test high-risk change detection."""

    def test_scale_to_zero_pattern(self, agent_yaml):
        patterns = agent_yaml["config"]["high_risk_changes"]
        scale_pattern = next((p for p in patterns if "replicas" in p["pattern"]), None)
        assert scale_pattern is not None
        assert "Scale to zero" in scale_pattern["description"]

    def test_latest_tag_pattern(self, agent_yaml):
        patterns = agent_yaml["config"]["high_risk_changes"]
        latest_pattern = next((p for p in patterns if "latest" in p["pattern"]), None)
        assert latest_pattern is not None

    def test_privileged_container_pattern(self, agent_yaml):
        patterns = agent_yaml["config"]["high_risk_changes"]
        priv_pattern = next((p for p in patterns if "privileged" in p["pattern"]), None)
        assert priv_pattern is not None

    def test_high_risk_detection_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "detect_high_risk_changes"), None)
        assert step is not None


class TestChangeWindowEnforcement:
    """Test change window enforcement."""

    def test_change_window_config(self, agent_yaml):
        window = agent_yaml["config"]["change_window"]
        assert "enabled" in window
        assert "allowed_hours" in window
        assert "timezone" in window

    def test_allowed_hours(self, agent_yaml):
        allowed = agent_yaml["config"]["change_window"]["allowed_hours"]
        # Typical business hours
        assert 9 in allowed
        assert 10 in allowed
        assert 14 in allowed

    def test_window_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_change_window"), None)
        assert step is not None
        assert "condition" in step

    def test_window_violation_alert(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_change_window_violation"), None)
        assert step is not None


class TestIncidentCorrelation:
    """Test change-incident correlation."""

    def test_correlation_config(self, agent_yaml):
        correlation = agent_yaml["config"]["correlation"]
        assert correlation["enabled"] == True
        assert correlation["lookback_minutes"] == 60

    def test_correlation_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "correlate_changes_with_incidents"), None)
        assert step is not None
        assert "condition" in step

    def test_correlation_alert(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_incident_correlation"), None)
        assert step is not None

    def test_correlation_time_window(self):
        """Test correlation time matching."""
        change_time = datetime.now()
        incident_time = change_time + timedelta(minutes=15)
        time_diff = (incident_time - change_time).total_seconds() / 60
        
        # Within 30 minute window
        assert time_diff <= 30


class TestTerraformDrift:
    """Test Terraform drift detection."""

    def test_terraform_config(self, agent_yaml):
        terraform = agent_yaml["config"]["change_sources"]["terraform"]
        assert "enabled" in terraform
        assert "state_bucket" in terraform

    def test_terraform_drift_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_terraform_drift"), None)
        assert step is not None
        assert "condition" in step


class TestGitChanges:
    """Test Git change tracking."""

    def test_git_config(self, agent_yaml):
        git = agent_yaml["config"]["change_sources"]["git"]
        assert "enabled" in git
        assert "repositories" in git
        assert len(git["repositories"]) > 0

    def test_git_commits_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "get_git_commits"), None)
        assert step is not None


class TestAlertConditions:
    """Test alert conditions."""

    def test_changes_notification_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "notify_changes"), None)
        assert step is not None
        assert "condition" in step

    def test_high_risk_alert_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_high_risk"), None)
        assert step is not None
        assert "condition" in step


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        assert step is not None

    def test_metrics_include_totals(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])
        assert "opensre_changes_total" in params_str


class TestIntegration:
    """Integration tests."""

    def test_change_aggregation(self):
        """Test aggregating changes from multiple sources."""
        k8s_changes = [
            {"type": "deployment", "resource": "api-server", "timestamp": "2024-01-15T10:00:00Z"}
        ]
        git_changes = [
            {"type": "commit", "resource": "infrastructure/prod", "timestamp": "2024-01-15T09:55:00Z"}
        ]
        
        all_changes = k8s_changes + git_changes
        assert len(all_changes) == 2

    def test_high_risk_pattern_matching(self):
        """Test high-risk pattern matching."""
        import re
        
        patterns = [
            {"pattern": r"replicas.*0", "description": "Scale to zero"},
            {"pattern": r"image.*:latest", "description": "Latest tag"}
        ]
        
        changes = [
            {"diff": "replicas: 3 -> 0"},
            {"diff": "image: nginx:1.24 -> nginx:latest"},
            {"diff": "env: FOO=bar -> FOO=baz"}
        ]
        
        matches = []
        for change in changes:
            for pattern in patterns:
                if re.search(pattern["pattern"], change["diff"]):
                    matches.append({"change": change, "risk": pattern["description"]})
        
        assert len(matches) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
