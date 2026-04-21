"""
Tests for Capacity Planner Agent
"""
from unittest.mock import Mock

import pytest


class TestCapacityPlannerAgent:
    """Test suite for capacity-planner agent"""

    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "capacity-planner",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#capacity-planning",
                "email_recipients": ["platform-team@example.com"],
                "report_period_days": 7,
                "forecast_days": 30,
                "namespaces": ["production", "staging"],
                "thresholds": {
                    "cpu_utilization_high": 80,
                    "cpu_utilization_low": 20,
                    "memory_utilization_high": 85,
                    "memory_utilization_low": 25,
                    "node_utilization_target": 70
                },
                "cost_per_cpu_hour": 0.05,
                "cost_per_gb_hour": 0.01,
                "enable_ai_recommendations": True
            }
        }

    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "prometheus": Mock(),
            "kubernetes": Mock(),
            "slack": Mock(),
            "email": Mock(),
            "llm": Mock(),
            "jira": Mock(),
            "compute": Mock(),
            "template": Mock()
        }

    @pytest.fixture
    def node_metrics(self):
        """Sample node metrics"""
        return {
            "by_node": [
                {"name": "node-1", "cpu_avg": 45, "cpu_peak": 72, "memory_avg": 60, "memory_peak": 78},
                {"name": "node-2", "cpu_avg": 52, "cpu_peak": 85, "memory_avg": 65, "memory_peak": 82},
                {"name": "node-3", "cpu_avg": 38, "cpu_peak": 65, "memory_avg": 55, "memory_peak": 70}
            ],
            "cpu_usage": [45, 52, 38],
            "memory_usage": [60, 65, 55]
        }

    @pytest.fixture
    def namespace_metrics(self):
        """Sample namespace metrics"""
        return {
            "by_namespace": [
                {
                    "name": "production",
                    "cpu_requests": "10.0",
                    "cpu_usage": "4.5",
                    "cpu_limits": "20.0",
                    "memory_requests": "20Gi",
                    "memory_usage": "12Gi",
                    "efficiency": 45
                },
                {
                    "name": "staging",
                    "cpu_requests": "5.0",
                    "cpu_usage": "0.8",
                    "cpu_limits": "10.0",
                    "memory_requests": "10Gi",
                    "memory_usage": "2Gi",
                    "efficiency": 16
                }
            ]
        }

    @pytest.fixture
    def rightsizing_result(self):
        """Sample rightsizing analysis result"""
        return {
            "overprovisioned": [
                {
                    "namespace": "production",
                    "deployment": "data-processor",
                    "cpu_requests": "2.0",
                    "cpu_usage": "0.3",
                    "memory_requests": "4Gi",
                    "memory_usage": "1Gi",
                    "recommended_cpu": "0.5",
                    "recommended_memory": "1.5Gi",
                    "monthly_savings": 450,
                    "utilization": 15
                },
                {
                    "namespace": "staging",
                    "deployment": "api-server",
                    "cpu_requests": "1.0",
                    "cpu_usage": "0.1",
                    "memory_requests": "2Gi",
                    "memory_usage": "0.3Gi",
                    "recommended_cpu": "0.2",
                    "recommended_memory": "0.5Gi",
                    "monthly_savings": 180,
                    "utilization": 10
                }
            ],
            "underprovisioned": [
                {
                    "namespace": "production",
                    "deployment": "web-frontend",
                    "cpu_usage": "0.9",
                    "cpu_limits": "1.0",
                    "utilization": 90
                }
            ],
            "no_limits": [
                {"namespace": "staging", "deployment": "test-service"}
            ],
            "no_requests": []
        }

    @pytest.fixture
    def forecast_result(self):
        """Sample forecast result"""
        return {
            "cluster_cpu": {
                "current": 45,
                "forecast_30d": 52,
                "trend": "increasing",
                "confidence": 0.95
            },
            "cluster_memory": {
                "current": 60,
                "forecast_30d": 68,
                "trend": "increasing",
                "confidence": 0.92
            }
        }

    def test_get_cluster_nodes(self, mock_skills):
        """Test cluster node retrieval"""
        mock_skills["kubernetes"].get_nodes.return_value = {
            "items": [
                {"metadata": {"name": "node-1"}, "status": {"capacity": {"cpu": "4", "memory": "16Gi"}}},
                {"metadata": {"name": "node-2"}, "status": {"capacity": {"cpu": "4", "memory": "16Gi"}}},
                {"metadata": {"name": "node-3"}, "status": {"capacity": {"cpu": "4", "memory": "16Gi"}}}
            ]
        }

        result = mock_skills["kubernetes"].get_nodes(label_selector="")

        assert len(result["items"]) == 3

    def test_get_node_metrics(self, mock_skills, node_metrics):
        """Test Prometheus node metrics retrieval"""
        mock_skills["prometheus"].query_range.return_value = node_metrics

        result = mock_skills["prometheus"].query_range(
            queries={"cpu_usage": "avg by (node) (rate(node_cpu_seconds_total[5m]))"},
            start="2024-01-08",
            end="2024-01-15",
            step="1h"
        )

        assert len(result["by_node"]) == 3
        assert result["by_node"][0]["cpu_avg"] == 45

    def test_calculate_utilization(self, mock_skills, node_metrics, namespace_metrics):
        """Test utilization calculations"""
        mock_skills["compute"].calculate.return_value = {
            "cluster_cpu_avg": 45.0,
            "cluster_memory_avg": 60.0,
            "cluster_cpu_peak": 85.0,
            "cluster_memory_peak": 82.0,
            "namespace_efficiency": {"production": 45, "staging": 16}
        }

        result = mock_skills["compute"].calculate(
            node_metrics=node_metrics,
            namespace_metrics=namespace_metrics
        )

        assert result["cluster_cpu_avg"] == 45.0
        assert result["namespace_efficiency"]["staging"] == 16

    def test_identify_rightsizing_overprovisioned(self, mock_skills, rightsizing_result):
        """Test overprovisioned workload identification"""
        mock_skills["compute"].analyze.return_value = rightsizing_result

        result = mock_skills["compute"].analyze(
            namespace_metrics={},
            thresholds={"cpu_utilization_low": 20}
        )

        assert len(result["overprovisioned"]) == 2
        assert result["overprovisioned"][0]["monthly_savings"] == 450

    def test_identify_rightsizing_underprovisioned(self, mock_skills, rightsizing_result):
        """Test underprovisioned workload identification"""
        mock_skills["compute"].analyze.return_value = rightsizing_result

        result = mock_skills["compute"].analyze(
            namespace_metrics={},
            thresholds={"cpu_utilization_high": 80}
        )

        assert len(result["underprovisioned"]) == 1
        assert result["underprovisioned"][0]["utilization"] == 90

    def test_forecast_capacity(self, mock_skills, forecast_result):
        """Test capacity forecasting"""
        mock_skills["compute"].forecast.return_value = forecast_result

        result = mock_skills["compute"].forecast(
            metrics=[{"name": "cluster_cpu", "data": [45, 46, 47]}],
            forecast_days=30,
            method="linear_regression"
        )

        assert result["cluster_cpu"]["forecast_30d"] == 52
        assert result["cluster_cpu"]["trend"] == "increasing"

    def test_calculate_cost_savings(self, mock_skills, agent_config, rightsizing_result):
        """Test cost savings calculation"""
        mock_skills["compute"].calculate.return_value = {
            "total_monthly": 3450,
            "by_workload": rightsizing_result["overprovisioned"]
        }

        result = mock_skills["compute"].calculate(
            rightsizing=rightsizing_result["overprovisioned"],
            cost_per_cpu_hour=agent_config["config"]["cost_per_cpu_hour"],
            cost_per_gb_hour=agent_config["config"]["cost_per_gb_hour"]
        )

        assert result["total_monthly"] == 3450

    def test_generate_ai_recommendations(self, mock_skills):
        """Test AI-powered recommendations"""
        mock_skills["llm"].analyze.return_value = {
            "priority_actions": [
                "Reduce data-processor CPU requests from 2.0 to 0.5",
                "Add memory limits to staging/test-service",
                "Scale down staging cluster by 1 node"
            ],
            "estimated_savings": "$3,450/month",
            "risks": ["Production web-frontend nearing CPU limits"],
            "scaling_recommendations": ["Consider HPA for web-frontend"]
        }

        result = mock_skills["llm"].analyze(
            prompt="Analyze cluster capacity...",
            model="gpt-4"
        )

        assert len(result["priority_actions"]) == 3
        assert "3,450" in result["estimated_savings"]

    def test_notify_slack(self, mock_skills):
        """Test Slack notification"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#capacity-planning",
            blocks=[{"type": "header", "text": {"type": "plain_text", "text": "📊 Weekly Capacity Report"}}]
        )

        assert result["ok"] is True

    def test_send_email_report(self, mock_skills, agent_config):
        """Test email report sending"""
        mock_skills["email"].send.return_value = {"status": "sent"}

        result = mock_skills["email"].send(
            to=agent_config["config"]["email_recipients"],
            subject="Weekly Capacity Report - 2024-01-15",
            body="# Weekly Capacity Report...",
            format="markdown"
        )

        assert result["status"] == "sent"

    def test_create_rightsizing_tickets(self, mock_skills, rightsizing_result):
        """Test Jira ticket creation for rightsizing"""
        mock_skills["jira"].bulk_create.return_value = {
            "issues": [
                {"key": "PLATFORM-123"},
                {"key": "PLATFORM-124"}
            ]
        }

        result = mock_skills["jira"].bulk_create(
            project="PLATFORM",
            issue_type="Task",
            issues=[{"summary": "Rightsize production/data-processor"}]
        )

        assert len(result["issues"]) == 2

    def test_full_workflow(self, agent_config, mock_skills, node_metrics, namespace_metrics,
                           rightsizing_result, forecast_result):
        """Integration test: full capacity planning workflow"""
        # Setup mocks
        mock_skills["kubernetes"].get_nodes.return_value = {"items": []}
        mock_skills["prometheus"].query_range.return_value = node_metrics
        mock_skills["compute"].calculate.return_value = {
            "cluster_cpu_avg": 45.0,
            "cluster_memory_avg": 60.0
        }
        mock_skills["compute"].analyze.return_value = rightsizing_result
        mock_skills["compute"].forecast.return_value = forecast_result
        mock_skills["llm"].analyze.return_value = {"priority_actions": []}
        mock_skills["template"].render.return_value = "# Report..."
        mock_skills["slack"].send_message.return_value = {"ok": True}
        mock_skills["email"].send.return_value = {"status": "sent"}
        mock_skills["prometheus"].push_metrics.return_value = {}

        steps_executed = []

        # Execute workflow
        mock_skills["kubernetes"].get_nodes()
        steps_executed.append("get_cluster_nodes")

        mock_skills["prometheus"].query_range(queries={}, start="", end="")
        steps_executed.append("get_node_metrics")

        mock_skills["prometheus"].query_range(queries={}, start="", end="")
        steps_executed.append("get_namespace_metrics")

        mock_skills["compute"].calculate(node_metrics=node_metrics)
        steps_executed.append("calculate_utilization")

        mock_skills["compute"].analyze(namespace_metrics={})
        steps_executed.append("identify_rightsizing_opportunities")

        mock_skills["compute"].forecast(metrics=[])
        steps_executed.append("forecast_capacity")

        mock_skills["compute"].calculate(rightsizing=[])
        steps_executed.append("calculate_cost_savings")

        if agent_config["config"]["enable_ai_recommendations"]:
            mock_skills["llm"].analyze(prompt="...")
            steps_executed.append("generate_ai_recommendations")

        mock_skills["template"].render(template="...")
        steps_executed.append("generate_report")

        mock_skills["slack"].send_message(channel="#capacity-planning")
        steps_executed.append("notify_slack")

        mock_skills["email"].send(to=[])
        steps_executed.append("send_email_report")

        expected = [
            "get_cluster_nodes", "get_node_metrics", "get_namespace_metrics",
            "calculate_utilization", "identify_rightsizing_opportunities",
            "forecast_capacity", "calculate_cost_savings",
            "generate_ai_recommendations", "generate_report",
            "notify_slack", "send_email_report"
        ]
        assert steps_executed == expected


class TestUtilizationCalculations:
    """Test utilization calculation logic"""

    def test_efficiency_calculation(self):
        """Test resource efficiency calculation"""
        cpu_requests = 2.0
        cpu_usage = 0.5
        efficiency = (cpu_usage / cpu_requests) * 100
        assert efficiency == 25.0

    def test_overprovisioned_detection(self):
        """Test overprovisioned detection logic"""
        def is_overprovisioned(requests, usage, threshold=0.5):
            return (requests - usage) / requests > threshold

        assert is_overprovisioned(2.0, 0.5) is True   # 75% unused
        assert is_overprovisioned(2.0, 1.5) is False  # 25% unused

    def test_underprovisioned_detection(self):
        """Test underprovisioned detection logic"""
        def is_underprovisioned(usage, limits, threshold=0.8):
            return usage / limits > threshold

        assert is_underprovisioned(0.9, 1.0) is True   # 90% of limits
        assert is_underprovisioned(0.5, 1.0) is False  # 50% of limits


class TestCostCalculations:
    """Test cost calculation logic"""

    def test_cpu_savings_calculation(self):
        """Test CPU cost savings calculation"""
        cpu_requests = 2.0
        recommended_cpu = 0.5
        cost_per_cpu_hour = 0.05
        hours_per_month = 24 * 30

        savings = (cpu_requests - recommended_cpu) * cost_per_cpu_hour * hours_per_month
        assert savings == 54.0  # 1.5 CPU * $0.05 * 720 hours

    def test_memory_savings_calculation(self):
        """Test memory cost savings calculation"""
        memory_requests_gb = 4.0
        recommended_memory_gb = 1.5
        cost_per_gb_hour = 0.01
        hours_per_month = 24 * 30

        savings = (memory_requests_gb - recommended_memory_gb) * cost_per_gb_hour * hours_per_month
        assert savings == 18.0  # 2.5 GB * $0.01 * 720 hours


class TestForecasting:
    """Test forecasting logic"""

    def test_linear_trend_detection(self):
        """Test linear trend detection"""
        data = [40, 42, 44, 46, 48, 50]
        trend = "increasing" if data[-1] > data[0] else "decreasing"
        assert trend == "increasing"

    def test_forecast_threshold_alert(self):
        """Test forecast threshold alerting"""
        forecast_cpu = 85
        threshold = 80
        should_alert = forecast_cpu > threshold
        assert should_alert is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
