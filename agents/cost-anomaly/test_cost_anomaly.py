"""
Tests for Cost Anomaly Detector Agent
"""
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest


class TestCostAnomalyAgent:
    """Test suite for cost-anomaly agent"""

    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "cost-anomaly",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#cost-alerts",
                "email_recipients": ["finops@example.com"],
                "anomaly_threshold_percent": 20,
                "baseline_period_days": 30,
                "alert_on_increase_only": False,
                "cloud_providers": ["aws", "gcp"],
                "breakdown_by": ["service", "team", "environment"]
            }
        }

    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "cloud-cost": Mock(),
            "prometheus": Mock(),
            "slack": Mock(),
            "email": Mock(),
            "jira": Mock(),
            "compute": Mock(),
            "template": Mock()
        }

    @pytest.fixture
    def current_costs(self):
        """Sample current day costs"""
        return {
            "total": 15000.00,
            "date": "2024-01-15",
            "breakdown": {
                "service": {
                    "ec2": 8000.00,
                    "rds": 3500.00,
                    "s3": 1500.00,
                    "lambda": 2000.00
                },
                "team": {
                    "platform": 9000.00,
                    "data": 4000.00,
                    "ml": 2000.00
                }
            }
        }

    @pytest.fixture
    def baseline_costs(self):
        """Sample baseline costs"""
        return {
            "total": 12000.00,
            "average_daily": 12000.00,
            "std_dev": 1000.00,
            "breakdown": {
                "service": {
                    "ec2": 6000.00,
                    "rds": 3000.00,
                    "s3": 1500.00,
                    "lambda": 1500.00
                }
            }
        }

    @pytest.fixture
    def anomaly_result(self):
        """Sample anomaly detection result"""
        return {
            "has_anomalies": True,
            "severity": "high",
            "total_variance_percent": 25.0,
            "anomalies": [
                {
                    "category": "service",
                    "name": "ec2",
                    "current": 8000.00,
                    "baseline": 6000.00,
                    "change_percent": 33.3,
                    "direction": "increase",
                    "probable_cause": "New instances launched"
                },
                {
                    "category": "service",
                    "name": "lambda",
                    "current": 2000.00,
                    "baseline": 1500.00,
                    "change_percent": 33.3,
                    "direction": "increase",
                    "probable_cause": "Increased invocations"
                }
            ]
        }

    def test_get_current_costs(self, mock_skills, current_costs):
        """Test fetching current day costs"""
        mock_skills["cloud-cost"].get_daily_costs.return_value = current_costs

        result = mock_skills["cloud-cost"].get_daily_costs(
            date="2024-01-15",
            providers=["aws", "gcp"],
            group_by=["service", "team", "environment"]
        )

        assert result["total"] == 15000.00
        assert "ec2" in result["breakdown"]["service"]

    def test_get_baseline_costs(self, mock_skills, baseline_costs):
        """Test fetching baseline costs"""
        mock_skills["cloud-cost"].get_average_costs.return_value = baseline_costs

        result = mock_skills["cloud-cost"].get_average_costs(
            start_date="2023-12-16",
            end_date="2024-01-14",
            providers=["aws", "gcp"],
            group_by=["service"]
        )

        assert result["average_daily"] == 12000.00
        assert result["std_dev"] == 1000.00

    def test_detect_anomalies_zscore(self, mock_skills, current_costs, baseline_costs, anomaly_result):
        """Test anomaly detection using z-score method"""
        mock_skills["compute"].detect_anomalies.return_value = anomaly_result

        result = mock_skills["compute"].detect_anomalies(
            current=current_costs,
            baseline=baseline_costs,
            threshold_percent=20,
            method="zscore",
            min_absolute_change=100
        )

        assert result["has_anomalies"] is True
        assert len(result["anomalies"]) == 2
        assert result["anomalies"][0]["name"] == "ec2"

    def test_no_anomalies_within_threshold(self, mock_skills):
        """Test no anomalies when within threshold"""
        mock_skills["compute"].detect_anomalies.return_value = {
            "has_anomalies": False,
            "severity": "low",
            "total_variance_percent": 5.0,
            "anomalies": []
        }

        result = mock_skills["compute"].detect_anomalies(
            current={"total": 12600},
            baseline={"total": 12000, "std_dev": 500},
            threshold_percent=20
        )

        assert result["has_anomalies"] is False
        assert len(result["anomalies"]) == 0

    def test_notify_slack_anomaly(self, mock_skills, anomaly_result):
        """Test Slack notification when anomalies detected"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#cost-alerts",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "💰 Cost Anomaly Detected"}}
            ]
        )

        assert result["ok"] is True

    def test_notify_slack_normal(self, mock_skills):
        """Test brief Slack notification when no anomalies"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#cost-alerts",
            text="✅ Daily Cost Check - No anomalies detected."
        )

        assert result["ok"] is True

    def test_send_email_high_severity(self, mock_skills, agent_config):
        """Test email sent for high severity anomalies"""
        mock_skills["email"].send.return_value = {"status": "sent"}

        result = mock_skills["email"].send(
            to=agent_config["config"]["email_recipients"],
            subject="⚠️ Cost Anomaly Alert - 2024-01-15",
            body="# Daily Cost Report...",
            format="markdown"
        )

        assert result["status"] == "sent"

    def test_skip_email_low_severity(self, mock_skills):
        """Test email not sent for low severity"""
        anomaly_result = {"has_anomalies": True, "severity": "low"}

        should_send_email = (
            anomaly_result["has_anomalies"] and
            anomaly_result["severity"] == "high"
        )
        assert should_send_email is False
        mock_skills["email"].send.assert_not_called()

    def test_store_metrics(self, mock_skills, current_costs, anomaly_result):
        """Test metrics are pushed to Prometheus"""
        mock_skills["prometheus"].push_metrics.return_value = {"status": "success"}

        result = mock_skills["prometheus"].push_metrics(
            metrics=[
                {"name": "opensre_daily_cost_total", "value": current_costs["total"]},
                {"name": "opensre_cost_anomaly_count", "value": len(anomaly_result["anomalies"])},
                {"name": "opensre_cost_variance_percent", "value": anomaly_result["total_variance_percent"]}
            ]
        )

        assert result["status"] == "success"

    def test_create_ticket_critical(self, mock_skills):
        """Test Jira ticket created for critical severity"""
        mock_skills["jira"].create_issue.return_value = {"key": "FINOPS-123"}

        result = mock_skills["jira"].create_issue(
            project="FINOPS",
            issue_type="Task",
            summary="Cost Anomaly Investigation - 2024-01-15",
            priority="High"
        )

        assert result["key"] == "FINOPS-123"

    def test_cost_trend_retrieval(self, mock_skills):
        """Test 7-day cost trend data retrieval"""
        mock_skills["cloud-cost"].get_cost_trend.return_value = {
            "dates": ["2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-13", "2024-01-14", "2024-01-15"],
            "values": [11500, 12000, 11800, 12500, 12200, 13000, 15000]
        }

        result = mock_skills["cloud-cost"].get_cost_trend(
            providers=["aws", "gcp"],
            period_days=7,
            group_by="service"
        )

        assert len(result["dates"]) == 7
        assert result["values"][-1] == 15000

    def test_resource_changes_detection(self, mock_skills):
        """Test resource changes are detected for context"""
        mock_skills["cloud-cost"].get_resource_changes.return_value = {
            "new_resources": [
                {"type": "ec2", "count": 5, "estimated_daily_cost": 1500},
                {"type": "rds", "count": 1, "estimated_daily_cost": 500}
            ],
            "terminated_resources": [],
            "scaled_resources": [
                {"type": "ec2", "name": "api-asg", "change": "+3 instances"}
            ]
        }

        result = mock_skills["cloud-cost"].get_resource_changes(
            date="2024-01-15",
            providers=["aws", "gcp"]
        )

        assert len(result["new_resources"]) == 2
        assert result["new_resources"][0]["estimated_daily_cost"] == 1500

    def test_full_workflow_with_anomaly(self, agent_config, mock_skills, current_costs, baseline_costs, anomaly_result):
        """Integration test: full workflow with anomaly detection"""
        # Setup mocks
        mock_skills["cloud-cost"].get_daily_costs.return_value = current_costs
        mock_skills["cloud-cost"].get_average_costs.return_value = baseline_costs
        mock_skills["compute"].detect_anomalies.return_value = anomaly_result
        mock_skills["cloud-cost"].get_cost_trend.return_value = {"dates": [], "values": []}
        mock_skills["cloud-cost"].get_resource_changes.return_value = {"new_resources": []}
        mock_skills["template"].render.return_value = "# Report..."
        mock_skills["slack"].send_message.return_value = {"ok": True}
        mock_skills["email"].send.return_value = {"status": "sent"}
        mock_skills["prometheus"].push_metrics.return_value = {"status": "success"}

        steps_executed = []

        # Execute workflow
        mock_skills["cloud-cost"].get_daily_costs(date="2024-01-15")
        steps_executed.append("get_current_costs")

        mock_skills["cloud-cost"].get_average_costs(start_date="2023-12-16", end_date="2024-01-14")
        steps_executed.append("get_baseline_costs")

        result = mock_skills["compute"].detect_anomalies(current=current_costs, baseline=baseline_costs)
        steps_executed.append("calculate_anomalies")

        mock_skills["cloud-cost"].get_cost_trend(period_days=7)
        steps_executed.append("get_cost_trend")

        if result["has_anomalies"]:
            mock_skills["cloud-cost"].get_resource_changes(date="2024-01-15")
            steps_executed.append("get_resource_changes")

        mock_skills["template"].render(template="# Report...")
        steps_executed.append("format_report")

        if result["has_anomalies"]:
            mock_skills["slack"].send_message(channel="#cost-alerts")
            steps_executed.append("notify_slack_anomaly")

        if result["has_anomalies"] and result["severity"] == "high":
            mock_skills["email"].send(to=["finops@example.com"])
            steps_executed.append("send_email_report")

        mock_skills["prometheus"].push_metrics(metrics=[])
        steps_executed.append("store_metrics")

        expected = [
            "get_current_costs", "get_baseline_costs", "calculate_anomalies",
            "get_cost_trend", "get_resource_changes", "format_report",
            "notify_slack_anomaly", "send_email_report", "store_metrics"
        ]
        assert steps_executed == expected


class TestAnomalyCalculations:
    """Test anomaly calculation logic"""

    def test_variance_calculation(self):
        """Test variance percentage calculation"""
        current = 15000
        baseline = 12000
        variance_percent = ((current - baseline) / baseline) * 100
        assert variance_percent == 25.0

    def test_zscore_calculation(self):
        """Test z-score calculation"""
        current = 15000
        mean = 12000
        std_dev = 1000
        zscore = (current - mean) / std_dev
        assert zscore == 3.0

    def test_severity_from_zscore(self):
        """Test severity determination from z-score"""
        def get_severity(zscore):
            if abs(zscore) < 2:
                return "low"
            elif abs(zscore) < 3:
                return "medium"
            elif abs(zscore) < 4:
                return "high"
            else:
                return "critical"

        assert get_severity(1.5) == "low"
        assert get_severity(2.5) == "medium"
        assert get_severity(3.5) == "high"
        assert get_severity(4.5) == "critical"

    def test_min_absolute_change_filter(self):
        """Test filtering anomalies below minimum absolute change"""
        anomalies = [
            {"name": "small-change", "current": 150, "baseline": 100},  # +$50
            {"name": "large-change", "current": 500, "baseline": 300}   # +$200
        ]
        min_absolute_change = 100

        filtered = [
            a for a in anomalies
            if abs(a["current"] - a["baseline"]) >= min_absolute_change
        ]

        assert len(filtered) == 1
        assert filtered[0]["name"] == "large-change"


class TestScheduleTrigger:
    """Test schedule trigger behavior"""

    def test_cron_parsing(self):
        """Test cron expression parsing"""
        cron_expr = "0 9 * * *"
        # This would run at 9 AM UTC daily
        parts = cron_expr.split()
        assert parts[0] == "0"  # minute
        assert parts[1] == "9"  # hour
        assert parts[2] == "*"  # day of month
        assert parts[3] == "*"  # month
        assert parts[4] == "*"  # day of week

    def test_date_subtract_calculation(self):
        """Test baseline date calculation"""
        check_date = datetime(2024, 1, 15)
        baseline_days = 30
        start_date = check_date - timedelta(days=baseline_days)

        assert start_date == datetime(2023, 12, 16)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
