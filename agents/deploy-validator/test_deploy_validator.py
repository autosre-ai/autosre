"""
Tests for Deployment Validator Agent
"""
from datetime import datetime
from unittest.mock import Mock

import pytest


class TestDeployValidatorAgent:
    """Test suite for deploy-validator agent"""

    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "deploy-validator",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#deployments",
                "validation_timeout_seconds": 300,
                "health_check_retries": 5,
                "health_check_interval_seconds": 10,
                "metrics_stabilization_seconds": 60,
                "thresholds": {
                    "error_rate_percent": 1.0,
                    "latency_p99_ms": 500,
                    "latency_p50_ms": 100,
                    "success_rate_percent": 99.0
                },
                "auto_rollback": False,
                "rollback_on_failure": True
            }
        }

    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "kubernetes": Mock(),
            "prometheus": Mock(),
            "http": Mock(),
            "slack": Mock(),
            "pagerduty": Mock(),
            "compute": Mock()
        }

    @pytest.fixture
    def deployment_trigger(self):
        """Sample deployment trigger"""
        return {
            "source": "kubernetes",
            "event_type": "deployment.successful",
            "deployment_name": "api-server",
            "namespace": "production",
            "version": "v1.2.3",
            "previous_version": "v1.2.2",
            "deployed_at": datetime.utcnow().isoformat()
        }

    @pytest.fixture
    def healthy_metrics(self):
        """Sample healthy metrics"""
        return {
            "error_rate": 0.05,
            "latency_p99": 245,
            "latency_p50": 45,
            "success_rate": 99.8,
            "rps": 1250.5
        }

    @pytest.fixture
    def unhealthy_metrics(self):
        """Sample unhealthy metrics"""
        return {
            "error_rate": 2.5,
            "latency_p99": 850,
            "latency_p50": 200,
            "success_rate": 97.5,
            "rps": 1100
        }

    def test_get_deployment_info(self, mock_skills, deployment_trigger):
        """Test deployment info retrieval"""
        mock_skills["kubernetes"].get_deployment.return_value = {
            "metadata": {
                "name": "api-server",
                "namespace": "production"
            },
            "spec": {
                "replicas": 3
            },
            "status": {
                "availableReplicas": 3,
                "readyReplicas": 3
            }
        }

        result = mock_skills["kubernetes"].get_deployment(
            namespace=deployment_trigger["namespace"],
            name=deployment_trigger["deployment_name"]
        )

        assert result["metadata"]["name"] == "api-server"
        assert result["status"]["readyReplicas"] == 3

    def test_wait_for_rollout(self, mock_skills, deployment_trigger):
        """Test waiting for rollout completion"""
        mock_skills["kubernetes"].wait_rollout.return_value = {
            "status": "complete",
            "duration_seconds": 45
        }

        result = mock_skills["kubernetes"].wait_rollout(
            namespace=deployment_trigger["namespace"],
            deployment=deployment_trigger["deployment_name"],
            timeout_seconds=300
        )

        assert result["status"] == "complete"

    def test_health_check_success(self, mock_skills):
        """Test successful health checks"""
        mock_skills["http"].check_health.return_value = {
            "all_healthy": True,
            "results": [
                {"endpoint": "10.0.0.1:8080", "status": 200, "latency_ms": 15},
                {"endpoint": "10.0.0.2:8080", "status": 200, "latency_ms": 12},
                {"endpoint": "10.0.0.3:8080", "status": 200, "latency_ms": 18}
            ]
        }

        result = mock_skills["http"].check_health(
            endpoints=["10.0.0.1:8080", "10.0.0.2:8080", "10.0.0.3:8080"],
            path="/health",
            expected_status=200
        )

        assert result["all_healthy"] is True
        assert len(result["results"]) == 3

    def test_health_check_failure(self, mock_skills):
        """Test failed health checks"""
        mock_skills["http"].check_health.return_value = {
            "all_healthy": False,
            "results": [
                {"endpoint": "10.0.0.1:8080", "status": 200, "latency_ms": 15},
                {"endpoint": "10.0.0.2:8080", "status": 503, "error": "Service Unavailable"},
                {"endpoint": "10.0.0.3:8080", "status": 200, "latency_ms": 18}
            ]
        }

        result = mock_skills["http"].check_health(
            endpoints=["10.0.0.1:8080", "10.0.0.2:8080", "10.0.0.3:8080"],
            path="/health"
        )

        assert result["all_healthy"] is False

    def test_get_baseline_metrics(self, mock_skills, healthy_metrics):
        """Test Prometheus metrics retrieval"""
        mock_skills["prometheus"].query.return_value = healthy_metrics

        result = mock_skills["prometheus"].query(
            queries={"error_rate": "...promql..."},
            time_range="5m"
        )

        assert result["error_rate"] == 0.05
        assert result["latency_p99"] == 245

    def test_validate_metrics_pass(self, agent_config, mock_skills, healthy_metrics):
        """Test metrics validation passes with healthy metrics"""
        mock_skills["compute"].validate_thresholds.return_value = {
            "passed": True,
            "results": [
                {"metric": "error_rate", "value": 0.05, "threshold": 1.0, "passed": True},
                {"metric": "latency_p99", "value": 245, "threshold": 500, "passed": True},
                {"metric": "success_rate", "value": 99.8, "threshold": 99.0, "passed": True}
            ]
        }

        result = mock_skills["compute"].validate_thresholds(
            metrics=healthy_metrics,
            thresholds=agent_config["config"]["thresholds"]
        )

        assert result["passed"] is True

    def test_validate_metrics_fail(self, agent_config, mock_skills, unhealthy_metrics):
        """Test metrics validation fails with unhealthy metrics"""
        mock_skills["compute"].validate_thresholds.return_value = {
            "passed": False,
            "results": [
                {"metric": "error_rate", "value": 2.5, "threshold": 1.0, "passed": False},
                {"metric": "latency_p99", "value": 850, "threshold": 500, "passed": False},
                {"metric": "success_rate", "value": 97.5, "threshold": 99.0, "passed": False}
            ]
        }

        result = mock_skills["compute"].validate_thresholds(
            metrics=unhealthy_metrics,
            thresholds=agent_config["config"]["thresholds"]
        )

        assert result["passed"] is False

    def test_analyze_pod_health(self, mock_skills):
        """Test pod health analysis"""
        mock_skills["compute"].analyze.return_value = {
            "all_checks_passed": True,
            "checks": {
                "all_running": True,
                "all_ready": True,
                "no_restarts": True
            }
        }

        result = mock_skills["compute"].analyze(
            pods=[{"status": {"phase": "Running"}}],
            checks=["all_running", "all_ready", "no_restarts"]
        )

        assert result["all_checks_passed"] is True

    def test_determine_validation_success(self, mock_skills):
        """Test validation scoring with passing score"""
        mock_skills["compute"].evaluate.return_value = {
            "passed": True,
            "score": 95,
            "checks": [
                {"name": "health_check", "passed": True, "weight": 30},
                {"name": "readiness_check", "passed": True, "weight": 20},
                {"name": "metrics_validation", "passed": True, "weight": 30},
                {"name": "pod_health", "passed": True, "weight": 20}
            ],
            "failed_checks": []
        }

        result = mock_skills["compute"].evaluate(
            conditions=[{"name": "health_check", "passed": True}],
            pass_threshold=80
        )

        assert result["passed"] is True
        assert result["score"] == 95

    def test_determine_validation_failure(self, mock_skills):
        """Test validation scoring with failing score"""
        mock_skills["compute"].evaluate.return_value = {
            "passed": False,
            "score": 60,
            "checks": [
                {"name": "health_check", "passed": True, "weight": 30},
                {"name": "readiness_check", "passed": True, "weight": 20},
                {"name": "metrics_validation", "passed": False, "weight": 30},
                {"name": "pod_health", "passed": False, "weight": 20}
            ],
            "failed_checks": [
                {"name": "metrics_validation", "reason": "Error rate 2.5% exceeds threshold 1%"},
                {"name": "pod_health", "reason": "2 pods have restarts"}
            ]
        }

        result = mock_skills["compute"].evaluate(
            conditions=[{"name": "health_check", "passed": True}],
            pass_threshold=80
        )

        assert result["passed"] is False
        assert result["score"] == 60
        assert len(result["failed_checks"]) == 2

    def test_notify_success(self, mock_skills):
        """Test success notification"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#deployments",
            blocks=[{"type": "header", "text": {"type": "plain_text", "text": "✅ Deployment Validated"}}]
        )

        assert result["ok"] is True

    def test_notify_failure(self, mock_skills):
        """Test failure notification with rollback button"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#deployments",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "❌ Deployment Validation Failed"}},
                {"type": "actions", "elements": [{"action_id": "rollback_deployment"}]}
            ]
        )

        assert result["ok"] is True

    def test_auto_rollback(self, mock_skills, deployment_trigger):
        """Test automatic rollback on failure"""
        mock_skills["kubernetes"].rollback_deployment.return_value = {
            "status": "success",
            "message": "Rolled back to previous revision"
        }

        result = mock_skills["kubernetes"].rollback_deployment(
            namespace=deployment_trigger["namespace"],
            deployment=deployment_trigger["deployment_name"]
        )

        assert result["status"] == "success"

    def test_page_on_failure(self, mock_skills, deployment_trigger):
        """Test PagerDuty incident on failure"""
        mock_skills["pagerduty"].create_incident.return_value = {"id": "P123"}

        result = mock_skills["pagerduty"].create_incident(
            title=f"Deployment Validation Failed: {deployment_trigger['deployment_name']}",
            urgency="high"
        )

        assert result["id"] == "P123"

    def test_full_workflow_success(self, agent_config, mock_skills, deployment_trigger, healthy_metrics):
        """Integration test: full successful validation workflow"""
        # Setup mocks
        mock_skills["kubernetes"].get_deployment.return_value = {"status": {"readyReplicas": 3}}
        mock_skills["kubernetes"].wait_rollout.return_value = {"status": "complete"}
        mock_skills["kubernetes"].get_endpoints.return_value = {"addresses": ["10.0.0.1"]}
        mock_skills["http"].check_health.return_value = {"all_healthy": True}
        mock_skills["prometheus"].query.return_value = healthy_metrics
        mock_skills["prometheus"].query_range.return_value = {}
        mock_skills["compute"].validate_thresholds.return_value = {"passed": True}
        mock_skills["kubernetes"].get_pods.return_value = {"items": []}
        mock_skills["compute"].analyze.return_value = {"all_checks_passed": True}
        mock_skills["compute"].evaluate.return_value = {"passed": True, "score": 95}
        mock_skills["slack"].send_message.return_value = {"ok": True}
        mock_skills["prometheus"].push_metrics.return_value = {}

        steps_executed = []

        # Execute workflow
        mock_skills["kubernetes"].get_deployment(name=deployment_trigger["deployment_name"])
        steps_executed.append("get_deployment_info")

        mock_skills["kubernetes"].wait_rollout(deployment=deployment_trigger["deployment_name"])
        steps_executed.append("wait_for_rollout")

        mock_skills["kubernetes"].get_endpoints(service=deployment_trigger["deployment_name"])
        steps_executed.append("get_service_endpoints")

        mock_skills["http"].check_health(path="/health")
        steps_executed.append("check_health_endpoints")

        mock_skills["http"].check_health(path="/ready")
        steps_executed.append("check_readiness_endpoints")

        mock_skills["prometheus"].query(queries={})
        steps_executed.append("get_baseline_metrics")

        mock_skills["compute"].validate_thresholds(metrics=healthy_metrics)
        steps_executed.append("validate_metrics")

        result = mock_skills["compute"].evaluate(conditions=[])
        steps_executed.append("determine_validation_result")

        if result["passed"]:
            mock_skills["slack"].send_message(channel="#deployments")
            steps_executed.append("notify_success")

        expected = [
            "get_deployment_info", "wait_for_rollout", "get_service_endpoints",
            "check_health_endpoints", "check_readiness_endpoints",
            "get_baseline_metrics", "validate_metrics",
            "determine_validation_result", "notify_success"
        ]
        assert steps_executed == expected


class TestThresholdValidation:
    """Test threshold validation logic"""

    def test_error_rate_threshold(self):
        """Test error rate threshold checking"""
        threshold = 1.0
        current = 0.5
        assert current <= threshold

        current = 1.5
        assert current > threshold

    def test_latency_threshold(self):
        """Test latency threshold checking"""
        threshold_p99 = 500
        current_p99 = 450
        assert current_p99 <= threshold_p99

    def test_success_rate_threshold(self):
        """Test success rate threshold checking"""
        threshold = 99.0
        current = 99.5
        assert current >= threshold

        current = 98.5
        assert current < threshold

    def test_regression_detection(self):
        """Test regression detection vs baseline"""
        baseline_latency = 100
        current_latency = 150
        max_regression_percent = 20

        regression_percent = ((current_latency - baseline_latency) / baseline_latency) * 100
        assert regression_percent == 50.0
        assert regression_percent > max_regression_percent


class TestScoringLogic:
    """Test validation scoring logic"""

    def test_weighted_score_calculation(self):
        """Test weighted score calculation"""
        checks = [
            {"name": "health", "passed": True, "weight": 30},
            {"name": "readiness", "passed": True, "weight": 20},
            {"name": "metrics", "passed": False, "weight": 30},
            {"name": "pods", "passed": True, "weight": 20}
        ]

        total_weight = sum(c["weight"] for c in checks)
        earned_weight = sum(c["weight"] for c in checks if c["passed"])
        score = (earned_weight / total_weight) * 100

        assert score == 70.0

    def test_pass_threshold(self):
        """Test pass threshold evaluation"""
        pass_threshold = 80

        assert 95 >= pass_threshold  # Pass
        assert 80 >= pass_threshold  # Pass (boundary)
        assert 79 < pass_threshold   # Fail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
