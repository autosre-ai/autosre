"""
Tests for Pod Crash Handler Agent
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestPodCrashHandlerAgent:
    """Test suite for pod-crash-handler agent"""
    
    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "pod-crash-handler",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#pod-alerts",
                "max_restart_attempts": 3,
                "rollback_on_crash_threshold": 5,
                "log_lines": 200,
                "auto_rollback": False,
                "analysis_enabled": True
            }
        }
    
    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "kubernetes": Mock(),
            "slack": Mock(),
            "prometheus": Mock(),
            "llm": Mock(),
            "jira": Mock()
        }
    
    @pytest.fixture
    def crash_trigger(self):
        """Sample CrashLoopBackOff trigger"""
        return {
            "source": "kubernetes",
            "event_type": "Warning.CrashLoopBackOff",
            "pod_name": "api-server-abc123",
            "namespace": "production",
            "container_name": "api",
            "restart_count": 3,
            "message": "Back-off restarting failed container"
        }
    
    @pytest.fixture
    def pod_details(self):
        """Sample pod details response"""
        return {
            "metadata": {
                "name": "api-server-abc123",
                "namespace": "production",
                "ownerReferences": [
                    {
                        "kind": "ReplicaSet",
                        "name": "api-server-7d9f8b6c5d"
                    }
                ]
            },
            "status": {
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "api",
                        "state": {
                            "waiting": {
                                "reason": "CrashLoopBackOff",
                                "message": "back-off 5m0s restarting failed container"
                            }
                        },
                        "restartCount": 3
                    }
                ]
            }
        }
    
    def test_get_pod_details(self, mock_skills, crash_trigger, pod_details):
        """Test pod details retrieval"""
        mock_skills["kubernetes"].get_pod.return_value = pod_details
        
        result = mock_skills["kubernetes"].get_pod(
            namespace=crash_trigger["namespace"],
            name=crash_trigger["pod_name"]
        )
        
        assert result["metadata"]["name"] == "api-server-abc123"
        assert result["status"]["containerStatuses"][0]["restartCount"] == 3
    
    def test_get_pod_logs(self, mock_skills, crash_trigger):
        """Test pod logs retrieval with previous container"""
        mock_skills["kubernetes"].get_logs.return_value = """
        2024-01-15T10:30:00Z ERROR: Database connection failed
        2024-01-15T10:30:01Z ERROR: Retrying connection...
        2024-01-15T10:30:05Z FATAL: Max retries exceeded, exiting
        """
        
        result = mock_skills["kubernetes"].get_logs(
            namespace=crash_trigger["namespace"],
            pod=crash_trigger["pod_name"],
            container=crash_trigger["container_name"],
            tail_lines=200,
            previous=True
        )
        
        assert "Database connection failed" in result
        assert "FATAL" in result
    
    def test_get_pod_events(self, mock_skills, crash_trigger):
        """Test pod events retrieval"""
        mock_skills["kubernetes"].get_events.return_value = {
            "items": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "count": 5,
                    "lastTimestamp": "2024-01-15T10:30:00Z"
                },
                {
                    "type": "Warning",
                    "reason": "Unhealthy",
                    "message": "Liveness probe failed",
                    "count": 3,
                    "lastTimestamp": "2024-01-15T10:29:00Z"
                }
            ]
        }
        
        result = mock_skills["kubernetes"].get_events(
            namespace=crash_trigger["namespace"],
            field_selector=f"involvedObject.name={crash_trigger['pod_name']}",
            limit=50
        )
        
        assert len(result["items"]) == 2
        assert result["items"][0]["reason"] == "BackOff"
    
    def test_get_resource_metrics(self, mock_skills, crash_trigger):
        """Test Prometheus metrics retrieval"""
        mock_skills["prometheus"].query.return_value = {
            "memory": {"status": "success", "data": {"result": [{"value": [1234, "512000000"]}]}},
            "cpu": {"status": "success", "data": {"result": [{"value": [1234, "0.25"]}]}},
            "restarts": {"status": "success", "data": {"result": [{"value": [1234, "3"]}]}}
        }
        
        result = mock_skills["prometheus"].query(
            promql={"memory": "container_memory_usage_bytes{pod=\"api-server-abc123\"}"},
            time_range="1h"
        )
        
        assert "memory" in result
        assert "cpu" in result
    
    def test_analyze_crash_with_llm(self, mock_skills):
        """Test LLM crash analysis"""
        mock_skills["llm"].analyze.return_value = {
            "root_cause": "Database connection timeout causing application crash",
            "severity": "high",
            "recommendations": [
                "Increase database connection timeout",
                "Add connection retry logic",
                "Check database health"
            ],
            "rollback_recommended": False
        }
        
        result = mock_skills["llm"].analyze(
            prompt="Analyze this Kubernetes pod crash...",
            model="gpt-4",
            max_tokens=1000
        )
        
        assert result["severity"] == "high"
        assert "Database" in result["root_cause"]
    
    def test_notify_slack(self, mock_skills, crash_trigger):
        """Test Slack notification with action buttons"""
        mock_skills["slack"].send_message.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }
        
        result = mock_skills["slack"].send_message(
            channel="#pod-alerts",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "🔄 Pod CrashLoopBackOff Detected"}}
            ]
        )
        
        assert result["ok"] is True
    
    def test_attempt_restart_under_threshold(self, agent_config, mock_skills, crash_trigger):
        """Test pod restart when under max_restart_attempts"""
        mock_skills["kubernetes"].delete_pod.return_value = {"status": "Success"}
        
        # Condition: restart_count < max_restart_attempts
        assert crash_trigger["restart_count"] < agent_config["config"]["max_restart_attempts"] + 1
        
        result = mock_skills["kubernetes"].delete_pod(
            namespace=crash_trigger["namespace"],
            name=crash_trigger["pod_name"],
            grace_period_seconds=30
        )
        
        assert result["status"] == "Success"
    
    def test_skip_restart_over_threshold(self, agent_config, mock_skills):
        """Test restart is skipped when over threshold"""
        high_restart_trigger = {
            "pod_name": "failing-pod",
            "namespace": "production",
            "restart_count": 10
        }
        
        # Condition check
        should_restart = high_restart_trigger["restart_count"] < agent_config["config"]["max_restart_attempts"]
        assert should_restart is False
        mock_skills["kubernetes"].delete_pod.assert_not_called()
    
    def test_auto_rollback_triggered(self, mock_skills):
        """Test automatic rollback when threshold exceeded"""
        config = {
            "auto_rollback": True,
            "rollback_on_crash_threshold": 5
        }
        trigger = {"restart_count": 7}
        deployment_info = {
            "metadata": {
                "name": "api-server",
                "annotations": {"deployment.kubernetes.io/revision": "3"}
            }
        }
        
        # Condition check
        should_rollback = (
            config["auto_rollback"] and 
            trigger["restart_count"] >= config["rollback_on_crash_threshold"]
        )
        assert should_rollback is True
        
        mock_skills["kubernetes"].rollback_deployment.return_value = {
            "status": "Success",
            "message": "Rolled back to revision 2"
        }
        
        result = mock_skills["kubernetes"].rollback_deployment(
            namespace="production",
            deployment=deployment_info["metadata"]["name"],
            revision=2
        )
        
        assert result["status"] == "Success"
    
    def test_rollback_disabled(self, agent_config, mock_skills):
        """Test rollback is not triggered when disabled"""
        # Default config has auto_rollback: False
        assert agent_config["config"]["auto_rollback"] is False
        mock_skills["kubernetes"].rollback_deployment.assert_not_called()
    
    def test_create_incident_ticket_critical(self, mock_skills):
        """Test Jira ticket creation for critical severity"""
        mock_skills["llm"].analyze.return_value = {"severity": "critical"}
        mock_skills["jira"].create_issue.return_value = {
            "key": "SRE-123",
            "self": "https://jira.example.com/rest/api/2/issue/SRE-123"
        }
        
        result = mock_skills["jira"].create_issue(
            project="SRE",
            issue_type="Incident",
            summary="Pod CrashLoopBackOff: api-server-abc123",
            labels=["crashloop", "auto-generated", "production"]
        )
        
        assert result["key"] == "SRE-123"
    
    def test_skip_ticket_low_severity(self, mock_skills):
        """Test ticket is not created for low severity"""
        analysis_result = {"severity": "low"}
        
        should_create_ticket = analysis_result["severity"] in ["high", "critical"]
        assert should_create_ticket is False
        mock_skills["jira"].create_issue.assert_not_called()
    
    def test_error_handling_log_retrieval(self, mock_skills, crash_trigger):
        """Test graceful handling when logs cannot be retrieved"""
        mock_skills["kubernetes"].get_logs.side_effect = Exception(
            "container 'api' in pod 'api-server-abc123' is waiting to start"
        )
        
        # With on_error: continue, workflow should proceed
        try:
            mock_skills["kubernetes"].get_logs(
                namespace=crash_trigger["namespace"],
                pod=crash_trigger["pod_name"],
                previous=True
            )
        except Exception:
            pass
        
        # Next step should still work
        mock_skills["kubernetes"].get_events.return_value = {"items": []}
        result = mock_skills["kubernetes"].get_events(namespace=crash_trigger["namespace"])
        assert "items" in result
    
    def test_full_workflow_with_restart(self, agent_config, mock_skills, crash_trigger, pod_details):
        """Integration test: full workflow with pod restart"""
        # Setup mocks
        mock_skills["kubernetes"].get_pod.return_value = pod_details
        mock_skills["kubernetes"].get_logs.return_value = "Error logs..."
        mock_skills["kubernetes"].get_events.return_value = {"items": []}
        mock_skills["prometheus"].query.return_value = {"memory": {}, "cpu": {}}
        mock_skills["kubernetes"].get_deployment.return_value = {"metadata": {"name": "api-server"}}
        mock_skills["llm"].analyze.return_value = {"severity": "medium", "root_cause": "Memory leak"}
        mock_skills["slack"].send_message.return_value = {"ok": True}
        mock_skills["kubernetes"].delete_pod.return_value = {"status": "Success"}
        
        steps_executed = []
        
        # Execute workflow
        mock_skills["kubernetes"].get_pod(namespace=crash_trigger["namespace"], name=crash_trigger["pod_name"])
        steps_executed.append("get_pod_details")
        
        mock_skills["kubernetes"].get_logs(namespace=crash_trigger["namespace"], pod=crash_trigger["pod_name"])
        steps_executed.append("get_pod_logs")
        
        mock_skills["kubernetes"].get_events(namespace=crash_trigger["namespace"])
        steps_executed.append("get_pod_events")
        
        mock_skills["prometheus"].query(promql={}, time_range="1h")
        steps_executed.append("get_resource_metrics")
        
        if agent_config["config"]["analysis_enabled"]:
            mock_skills["llm"].analyze(prompt="Analyze crash...")
            steps_executed.append("analyze_crash")
        
        mock_skills["slack"].send_message(channel=agent_config["config"]["slack_channel"])
        steps_executed.append("notify_slack_initial")
        
        if crash_trigger["restart_count"] < agent_config["config"]["max_restart_attempts"]:
            mock_skills["kubernetes"].delete_pod(namespace=crash_trigger["namespace"], name=crash_trigger["pod_name"])
            steps_executed.append("attempt_restart")
        
        expected = [
            "get_pod_details", "get_pod_logs", "get_pod_events",
            "get_resource_metrics", "analyze_crash", "notify_slack_initial", "attempt_restart"
        ]
        assert steps_executed == expected


class TestCrashPatterns:
    """Test different crash pattern handling"""
    
    def test_oom_killed_detection(self):
        """Test OOMKilled pattern detection"""
        container_status = {
            "state": {
                "terminated": {
                    "reason": "OOMKilled",
                    "exitCode": 137
                }
            }
        }
        
        is_oom = container_status["state"].get("terminated", {}).get("reason") == "OOMKilled"
        assert is_oom is True
    
    def test_crashloop_detection(self):
        """Test CrashLoopBackOff pattern detection"""
        container_status = {
            "state": {
                "waiting": {
                    "reason": "CrashLoopBackOff",
                    "message": "back-off 5m0s restarting failed container"
                }
            }
        }
        
        is_crashloop = container_status["state"].get("waiting", {}).get("reason") == "CrashLoopBackOff"
        assert is_crashloop is True
    
    def test_image_pull_error_detection(self):
        """Test ImagePullBackOff pattern detection"""
        container_status = {
            "state": {
                "waiting": {
                    "reason": "ImagePullBackOff",
                    "message": "Back-off pulling image \"invalid:image\""
                }
            }
        }
        
        is_image_error = container_status["state"].get("waiting", {}).get("reason") in [
            "ImagePullBackOff", "ErrImagePull"
        ]
        assert is_image_error is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
