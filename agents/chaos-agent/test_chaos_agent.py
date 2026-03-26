"""Tests for chaos-agent."""

import pytest
import yaml
from pathlib import Path


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        assert agent_yaml["name"] == "chaos-agent"
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        triggers = agent_yaml["triggers"]
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        # Should run on specific days
        assert "2,4" in schedule["cron"]  # Tue, Thu

    def test_required_skills(self, agent_yaml):
        skills = agent_yaml["skills"]
        assert "kubernetes" in skills
        assert "litmus" in skills
        assert "slack" in skills

    def test_master_kill_switch(self, agent_yaml):
        assert "enabled" in agent_yaml["config"]

    def test_approval_configuration(self, agent_yaml):
        config = agent_yaml["config"]
        assert "require_approval" in config
        assert "approval_timeout_minutes" in config


class TestEnvironmentSafety:
    """Test environment safety configuration."""

    def test_blocked_environments(self, agent_yaml):
        environments = agent_yaml["config"]["environments"]
        assert "production" in environments["blocked"]

    def test_allowed_environments(self, agent_yaml):
        environments = agent_yaml["config"]["environments"]
        assert "staging" in environments["allowed"]

    def test_environment_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_environment"), None)
        assert step is not None
        assert step["on_error"] == "fail"


class TestExperimentConfiguration:
    """Test experiment configuration."""

    def test_experiments_defined(self, agent_yaml):
        experiments = agent_yaml["config"]["experiments"]
        assert len(experiments) > 0

    def test_experiment_required_fields(self, agent_yaml):
        for exp in agent_yaml["config"]["experiments"]:
            assert "name" in exp
            assert "type" in exp
            assert "enabled" in exp
            assert "target" in exp
            assert "duration_seconds" in exp

    def test_pod_kill_experiment(self, agent_yaml):
        exp = next((e for e in agent_yaml["config"]["experiments"] 
                   if e["name"] == "pod-kill"), None)
        assert exp is not None
        assert exp["type"] == "pod-delete"
        assert exp["target"]["count"] == 1

    def test_network_chaos_experiment(self, agent_yaml):
        exp = next((e for e in agent_yaml["config"]["experiments"] 
                   if e["name"] == "network-latency"), None)
        assert exp is not None
        assert exp["type"] == "network-chaos"
        assert "latency" in exp["params"]


class TestSafetyConstraints:
    """Test safety constraints."""

    def test_safety_config_exists(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert "max_affected_pods_percent" in safety
        assert "min_healthy_pods" in safety
        assert "abort_on_alert" in safety

    def test_max_affected_percentage(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert safety["max_affected_pods_percent"] <= 50  # Should be conservative

    def test_min_healthy_pods(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert safety["min_healthy_pods"] >= 1

    def test_abort_on_alert(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert safety["abort_on_alert"] == True

    def test_alert_names_configured(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert len(safety["alert_names_to_watch"]) > 0

    def test_slo_breach_rollback(self, agent_yaml):
        safety = agent_yaml["config"]["safety"]
        assert safety["rollback_on_slo_breach"] == True

    def test_safety_check_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_safety_constraints"), None)
        assert step is not None


class TestApprovalWorkflow:
    """Test approval workflow."""

    def test_request_approval_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "request_approval"), None)
        assert step is not None
        assert "condition" in step

    def test_wait_for_approval_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "wait_for_approval"), None)
        assert step is not None

    def test_abort_if_rejected_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "abort_if_rejected"), None)
        assert step is not None


class TestBaselineCollection:
    """Test baseline metrics collection."""

    def test_baseline_collection_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "collect_baseline_metrics"), None)
        assert step is not None
        assert step["action"] == "prometheus.query_range"

    def test_baseline_calculation_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "calculate_baseline"), None)
        assert step is not None

    def test_baseline_duration(self, agent_yaml):
        assert agent_yaml["config"]["baseline_duration_minutes"] > 0


class TestExperimentExecution:
    """Test experiment execution."""

    def test_run_experiment_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "run_experiment"), None)
        assert step is not None
        assert step["action"] == "litmus.run_experiment"
        assert step["retries"] == 0  # No retries for chaos

    def test_monitor_during_experiment_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "monitor_during_experiment"), None)
        assert step is not None

    def test_rollback_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "rollback_if_needed"), None)
        assert step is not None
        assert "condition" in step


class TestImpactAnalysis:
    """Test impact analysis."""

    def test_collect_experiment_metrics(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "collect_experiment_metrics"), None)
        assert step is not None

    def test_analyze_impact_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "analyze_impact"), None)
        assert step is not None

    def test_ai_analysis_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "generate_ai_analysis"), None)
        assert step is not None
        assert step["action"] == "llm.analyze"


class TestNotifications:
    """Test notification steps."""

    def test_start_notification(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "notify_experiment_start"), None)
        assert step is not None

    def test_complete_notification(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "notify_experiment_complete"), None)
        assert step is not None

    def test_slo_breach_page(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "page_on_slo_breach"), None)
        assert step is not None
        assert "condition" in step


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        assert step is not None

    def test_metrics_include_experiment_data(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])
        assert "opensre_chaos" in params_str


class TestIntegration:
    """Integration tests."""

    def test_safety_constraint_evaluation(self):
        """Test safety constraint evaluation logic."""
        pods = [
            {"status": {"phase": "Running"}},
            {"status": {"phase": "Running"}},
            {"status": {"phase": "Running"}},
            {"status": {"phase": "Running"}},
            {"status": {"phase": "Pending"}}
        ]
        
        min_healthy = 2
        max_affected_percent = 30
        count_to_affect = 1
        
        # Check min healthy
        healthy = len([p for p in pods if p["status"]["phase"] == "Running"])
        assert healthy >= min_healthy
        
        # Check max affected
        total = len(pods)
        max_allowed = total * (max_affected_percent / 100)
        assert count_to_affect <= max_allowed

    def test_impact_calculation(self):
        """Test impact metric calculation."""
        baseline = {
            "error_rate": 0.5,
            "latency_p99": 100
        }
        
        during_experiment = {
            "error_rate": [0.5, 1.0, 2.5, 1.5, 0.6],
            "latency_p99": [100, 150, 300, 200, 110]
        }
        
        error_rate_delta = max(during_experiment["error_rate"]) - baseline["error_rate"]
        latency_delta = max(during_experiment["latency_p99"]) - baseline["latency_p99"]
        
        assert error_rate_delta == 2.0
        assert latency_delta == 200

    def test_recovery_time_detection(self):
        """Test recovery time calculation."""
        baseline_error_rate = 0.5
        threshold = baseline_error_rate * 1.1  # 10% tolerance
        
        # Error rates every 10 seconds
        error_rates = [0.5, 2.0, 3.0, 2.5, 1.5, 0.8, 0.6, 0.5, 0.5]
        
        # Find when it returned to threshold
        recovery_index = None
        for i, rate in enumerate(error_rates):
            if rate <= threshold and all(r <= threshold for r in error_rates[i:]):
                recovery_index = i
                break
        
        assert recovery_index is not None
        recovery_time_seconds = recovery_index * 10
        assert recovery_time_seconds == 70


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
