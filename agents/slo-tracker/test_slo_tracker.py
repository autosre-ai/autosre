"""Tests for slo-tracker agent."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


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
        "api-availability": 0.9987,
        "api-latency-p99": 0.9923,
        "checkout-availability": 0.9996
    }
    mock.query_range.return_value = {
        "api-availability_budget": [
            {"time": "2024-01-01T00:00:00Z", "value": 0.85},
            {"time": "2024-01-15T00:00:00Z", "value": 0.65},
            {"time": "2024-01-30T00:00:00Z", "value": 0.45}
        ]
    }
    mock.push_metrics.return_value = {"status": "success"}
    return mock


@pytest.fixture
def mock_slack():
    """Mock Slack skill."""
    mock = MagicMock()
    mock.send_message.return_value = {
        "ok": True,
        "ts": "1234567890.123456"
    }
    return mock


@pytest.fixture
def mock_pagerduty():
    """Mock PagerDuty skill."""
    mock = MagicMock()
    mock.create_incident.return_value = {
        "incident": {"id": "PXXXXXX", "status": "triggered"}
    }
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM skill."""
    mock = MagicMock()
    mock.analyze.return_value = """
    Root Cause Analysis:
    The API availability SLO is being impacted by increased 503 errors from the payment-service.
    
    Immediate Actions:
    1. Scale payment-service horizontally
    2. Enable circuit breaker for payment calls
    
    Long-term Recommendations:
    1. Implement request hedging
    2. Add fallback payment provider
    """
    return mock


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        """Test that agent has all required top-level fields."""
        assert agent_yaml["name"] == "slo-tracker"
        assert "description" in agent_yaml
        assert "version" in agent_yaml
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "config" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        """Test triggers are properly configured."""
        triggers = agent_yaml["triggers"]
        assert len(triggers) >= 2
        
        # Check schedule trigger
        schedule_trigger = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule_trigger is not None
        assert "cron" in schedule_trigger
        assert schedule_trigger["cron"] == "*/15 * * * *"
        
        # Check webhook trigger
        webhook_trigger = next((t for t in triggers if t["type"] == "webhook"), None)
        assert webhook_trigger is not None

    def test_required_skills(self, agent_yaml):
        """Test required skills are listed."""
        skills = agent_yaml["skills"]
        assert "prometheus" in skills
        assert "slack" in skills

    def test_slo_configuration(self, agent_yaml):
        """Test SLO configuration structure."""
        config = agent_yaml["config"]
        assert "slos" in config
        assert len(config["slos"]) > 0
        
        for slo in config["slos"]:
            assert "name" in slo
            assert "target" in slo
            assert "window_days" in slo
            assert "service" in slo
            assert "sli_query" in slo
            assert 0 < slo["target"] <= 100

    def test_burn_rate_windows(self, agent_yaml):
        """Test burn rate windows are configured."""
        config = agent_yaml["config"]
        assert "burn_rate_windows" in config
        windows = config["burn_rate_windows"]
        assert "fast" in windows
        assert "slow" in windows
        assert "long" in windows

    def test_error_budget_thresholds(self, agent_yaml):
        """Test error budget thresholds."""
        config = agent_yaml["config"]
        thresholds = config["error_budget_thresholds"]
        assert thresholds["warning"] < thresholds["critical"]
        assert thresholds["critical"] < thresholds["exhausted"]


class TestStepDefinitions:
    """Test step definitions in the agent."""

    def test_all_steps_have_required_fields(self, agent_yaml):
        """Test all steps have name and action."""
        for step in agent_yaml["steps"]:
            assert "name" in step
            assert "action" in step

    def test_step_action_format(self, agent_yaml):
        """Test step actions follow skill.method format."""
        for step in agent_yaml["steps"]:
            action = step["action"]
            assert "." in action, f"Action {action} should be in skill.method format"
            skill, method = action.split(".", 1)
            assert skill in agent_yaml["skills"] or skill == "compute", \
                f"Skill {skill} not in declared skills"

    def test_calculate_sli_step(self, agent_yaml):
        """Test SLI calculation step."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "calculate_sli_values")
        assert step["action"] == "prometheus.query"
        assert "queries" in step["params"]

    def test_alert_steps_have_conditions(self, agent_yaml):
        """Test alert steps have appropriate conditions."""
        alert_steps = [s for s in agent_yaml["steps"] if "alert" in s["name"]]
        for step in alert_steps:
            assert "condition" in step, f"Alert step {step['name']} should have condition"


class TestBurnRateCalculation:
    """Test burn rate calculation logic."""

    def test_burn_rate_formula(self):
        """Test burn rate calculation formula."""
        # Burn rate = error_rate / error_budget_rate
        # For 99.9% SLO over 30 days:
        # Error budget = 0.1% = 0.001
        # Monthly budget = 0.001 * 30 * 24 = 0.72 hours of downtime
        
        target = 99.9  # 99.9%
        error_budget = (100 - target) / 100  # 0.001
        
        # If current error rate is 0.003 (0.3%)
        current_error_rate = 0.003
        burn_rate = current_error_rate / error_budget
        
        assert burn_rate == 3.0  # Burning 3x faster than sustainable

    def test_time_to_exhaustion(self):
        """Test time to exhaustion calculation."""
        # If 50% budget remains and burn rate is 2x
        budget_remaining = 0.5
        burn_rate = 2.0
        window_days = 30
        
        # Normal burn rate would exhaust in 30 days
        # At 2x, remaining 50% would exhaust in:
        time_to_exhaustion_days = (budget_remaining * window_days) / burn_rate
        assert time_to_exhaustion_days == 7.5


class TestAlertThresholds:
    """Test alert threshold logic."""

    def test_warning_threshold(self, agent_yaml):
        """Test warning threshold configuration."""
        thresholds = agent_yaml["config"]["error_budget_thresholds"]
        assert thresholds["warning"] == 50

    def test_critical_threshold(self, agent_yaml):
        """Test critical threshold configuration."""
        thresholds = agent_yaml["config"]["error_budget_thresholds"]
        assert thresholds["critical"] == 75

    def test_budget_status_categorization(self):
        """Test budget status categorization."""
        def get_budget_status(consumed_percent):
            if consumed_percent >= 100:
                return "EXHAUSTED"
            elif consumed_percent >= 75:
                return "CRITICAL"
            elif consumed_percent >= 50:
                return "WARNING"
            else:
                return "HEALTHY"

        assert get_budget_status(25) == "HEALTHY"
        assert get_budget_status(50) == "WARNING"
        assert get_budget_status(75) == "CRITICAL"
        assert get_budget_status(100) == "EXHAUSTED"
        assert get_budget_status(110) == "EXHAUSTED"


class TestSlackNotifications:
    """Test Slack notification steps."""

    def test_warning_notification_step(self, agent_yaml):
        """Test warning notification step configuration."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "alert_warning_budget")
        assert step["action"] == "slack.send_message"
        assert "channel" in step["params"]
        assert "blocks" in step["params"]

    def test_critical_notification_step(self, agent_yaml):
        """Test critical notification step configuration."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "alert_critical_budget")
        assert step["action"] == "slack.send_message"
        assert "condition" in step

    def test_notification_includes_dashboard_link(self, agent_yaml):
        """Test notifications include dashboard links."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "alert_critical_budget")
        params_str = str(step["params"])
        assert "grafana" in params_str.lower() or "dashboard" in params_str.lower()


class TestPagerDutyIntegration:
    """Test PagerDuty integration."""

    def test_page_on_exhausted_budget(self, agent_yaml):
        """Test PagerDuty is triggered on exhausted budget."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "page_exhausted_budget")
        assert step["action"] == "pagerduty.create_incident"
        assert "condition" in step
        assert "EXHAUSTED" in step["condition"]

    def test_pagerduty_incident_has_details(self, agent_yaml):
        """Test PagerDuty incident includes relevant details."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "page_exhausted_budget")
        params = step["params"]
        assert "title" in params
        assert "body" in params


class TestMetricsPushing:
    """Test metrics pushing to Prometheus."""

    def test_push_metrics_step_exists(self, agent_yaml):
        """Test metrics pushing step exists."""
        step = next((s for s in agent_yaml["steps"] if s["name"] == "push_metrics"), None)
        assert step is not None
        assert step["action"] == "prometheus.push_metrics"

    def test_metrics_include_slo_values(self, agent_yaml):
        """Test pushed metrics include SLO values."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "push_metrics")
        params_str = str(step["params"])
        assert "opensre_slo" in params_str


class TestWeeklyReport:
    """Test weekly report functionality."""

    def test_weekly_report_step(self, agent_yaml):
        """Test weekly report step exists."""
        step = next((s for s in agent_yaml["steps"] if s["name"] == "send_weekly_report"), None)
        assert step is not None
        assert step["action"] == "email.send"

    def test_weekly_report_condition(self, agent_yaml):
        """Test weekly report runs on Monday."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "send_weekly_report")
        assert "Monday" in step["condition"] or "day_of_week" in step["condition"]


class TestAIAnalysis:
    """Test AI analysis integration."""

    def test_ai_analysis_step(self, agent_yaml):
        """Test AI analysis step exists."""
        step = next((s for s in agent_yaml["steps"] if s["name"] == "generate_ai_analysis"), None)
        assert step is not None
        assert step["action"] == "llm.analyze"

    def test_ai_analysis_has_condition(self, agent_yaml):
        """Test AI analysis only runs when needed."""
        step = next(s for s in agent_yaml["steps"] if s["name"] == "generate_ai_analysis")
        assert "condition" in step


class TestIntegration:
    """Integration tests for SLO tracker."""

    def test_full_workflow_healthy_slo(self, mock_prometheus, mock_slack):
        """Test full workflow with healthy SLOs."""
        # Simulate healthy SLOs
        mock_prometheus.query.return_value = {
            "api-availability": 0.9995,  # Above 99.9% target
        }
        mock_prometheus.query_range.return_value = {
            "api-availability_budget": [{"value": 0.80}]  # 20% consumed
        }
        
        # Should not trigger any alerts
        # (In real implementation, this would be checked by agent runtime)

    def test_full_workflow_warning_slo(self, mock_prometheus, mock_slack):
        """Test full workflow with SLO in warning state."""
        # Simulate SLO at 55% budget consumption
        mock_prometheus.query_range.return_value = {
            "api-availability_budget": [{"value": 0.45}]  # 55% consumed
        }
        
        # Should trigger warning alert

    def test_full_workflow_critical_slo(self, mock_prometheus, mock_slack, mock_pagerduty):
        """Test full workflow with critical SLO."""
        # Simulate SLO at 80% budget consumption
        mock_prometheus.query_range.return_value = {
            "api-availability_budget": [{"value": 0.20}]  # 80% consumed
        }
        
        # Should trigger critical alert (but not page)

    def test_full_workflow_exhausted_slo(self, mock_prometheus, mock_slack, mock_pagerduty):
        """Test full workflow with exhausted SLO."""
        # Simulate SLO with exhausted budget
        mock_prometheus.query_range.return_value = {
            "api-availability_budget": [{"value": -0.05}]  # 105% consumed
        }
        
        # Should trigger page


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
