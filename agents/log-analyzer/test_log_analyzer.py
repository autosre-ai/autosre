"""Tests for log-analyzer agent."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock
import re


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        assert agent_yaml["name"] == "log-analyzer"
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        triggers = agent_yaml["triggers"]
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        assert schedule["cron"] == "*/10 * * * *"

    def test_required_skills(self, agent_yaml):
        skills = agent_yaml["skills"]
        assert "elasticsearch" in skills
        assert "slack" in skills

    def test_pattern_configuration(self, agent_yaml):
        patterns = agent_yaml["config"]["patterns"]
        assert "critical" in patterns
        assert "warning" in patterns
        assert len(patterns["critical"]) > 0

    def test_anomaly_detection_config(self, agent_yaml):
        anomaly = agent_yaml["config"]["anomaly_detection"]
        assert anomaly["enabled"] == True
        assert anomaly["baseline_hours"] == 24
        assert anomaly["deviation_threshold"] == 3.0


class TestPatternMatching:
    """Test pattern matching logic."""

    def test_critical_pattern_matching(self):
        patterns = [
            {"pattern": "FATAL|CRITICAL|PANIC", "min_count": 1},
            {"pattern": "OutOfMemoryError|OOMKilled", "min_count": 1}
        ]
        
        logs = [
            {"message": "FATAL: Unable to connect to database"},
            {"message": "OutOfMemoryError: Java heap space"},
            {"message": "INFO: Request processed successfully"}
        ]
        
        matches = []
        for pattern in patterns:
            regex = re.compile(pattern["pattern"])
            count = sum(1 for log in logs if regex.search(log["message"]))
            if count >= pattern["min_count"]:
                matches.append({"pattern": pattern["pattern"], "count": count})
        
        assert len(matches) == 2

    def test_warning_pattern_threshold(self):
        pattern = {"pattern": "ERROR", "min_count": 100}
        
        # 50 errors - below threshold
        logs_50 = [{"message": "ERROR: Something failed"}] * 50
        count = sum(1 for log in logs_50 if "ERROR" in log["message"])
        assert count < pattern["min_count"]
        
        # 150 errors - above threshold
        logs_150 = [{"message": "ERROR: Something failed"}] * 150
        count = sum(1 for log in logs_150 if "ERROR" in log["message"])
        assert count >= pattern["min_count"]

    def test_noise_filter(self, agent_yaml):
        noise_filter = agent_yaml["config"]["patterns"]["noise_filter"]
        assert "health check" in noise_filter
        assert "DEBUG" in noise_filter


class TestAnomalyDetection:
    """Test anomaly detection logic."""

    def test_zscore_calculation(self):
        """Test z-score calculation."""
        baseline = [10, 12, 8, 11, 9, 10, 13, 7, 11, 10]  # Mean ~10
        current = 50  # Much higher than baseline
        
        import statistics
        mean = statistics.mean(baseline)
        stddev = statistics.stdev(baseline)
        zscore = (current - mean) / stddev
        
        assert zscore > 3.0  # Should be anomaly

    def test_normal_value_not_anomaly(self):
        """Test normal value is not flagged."""
        baseline = [10, 12, 8, 11, 9, 10, 13, 7, 11, 10]
        current = 11  # Within normal range
        
        import statistics
        mean = statistics.mean(baseline)
        stddev = statistics.stdev(baseline)
        zscore = (current - mean) / stddev
        
        assert abs(zscore) < 3.0

    def test_anomaly_detection_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "detect_anomalies"), None)
        assert step is not None
        assert "condition" in step


class TestErrorRateCalculation:
    """Test error rate calculation."""

    def test_error_rate_calculation(self):
        total_logs = 1000
        error_logs = 50
        
        error_rate = (error_logs / total_logs) * 100
        assert error_rate == 5.0

    def test_error_rate_threshold(self, agent_yaml):
        threshold = agent_yaml["config"]["error_rate_threshold_percent"]
        assert threshold == 5


class TestAlertConditions:
    """Test alert conditions."""

    def test_critical_alert_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_critical_patterns"), None)
        assert step is not None
        assert "condition" in step

    def test_anomaly_alert_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_anomaly"), None)
        assert step is not None

    def test_high_error_rate_alert(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "alert_high_error_rate"), None)
        assert step is not None


class TestAIAnalysis:
    """Test AI analysis integration."""

    def test_ai_analysis_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "analyze_with_ai"), None)
        assert step is not None
        assert step["action"] == "llm.analyze"

    def test_ai_analysis_condition(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "analyze_with_ai"), None)
        assert "condition" in step


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        assert step is not None

    def test_metrics_include_error_count(self, agent_yaml):
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])
        assert "opensre_log_error_count" in params_str


class TestIntegration:
    """Integration tests."""

    def test_full_analysis_workflow(self):
        """Test complete log analysis workflow."""
        # Simulate log data
        logs = [
            {"level": "ERROR", "message": "Connection failed", "service": "api"},
            {"level": "ERROR", "message": "Connection failed", "service": "api"},
            {"level": "FATAL", "message": "OOM killed", "service": "worker"},
            {"level": "INFO", "message": "Request processed", "service": "api"},
        ]
        
        # Calculate stats
        error_logs = [l for l in logs if l["level"] in ["ERROR", "FATAL", "CRITICAL"]]
        error_rate = len(error_logs) / len(logs) * 100
        
        assert len(error_logs) == 3
        assert error_rate == 75.0

    def test_pattern_grouping_by_service(self):
        """Test grouping patterns by service."""
        logs = [
            {"message": "ERROR: failed", "service": "api"},
            {"message": "ERROR: timeout", "service": "api"},
            {"message": "ERROR: failed", "service": "worker"},
        ]
        
        by_service = {}
        for log in logs:
            svc = log["service"]
            by_service.setdefault(svc, []).append(log)
        
        assert len(by_service["api"]) == 2
        assert len(by_service["worker"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
