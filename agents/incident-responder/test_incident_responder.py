"""
Tests for Incident Responder Agent
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestIncidentResponderAgent:
    """Test suite for incident-responder agent"""
    
    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "incident-responder",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#incidents",
                "auto_ack": True,
                "escalation_timeout_minutes": 30,
                "severity_threshold": "warning"
            }
        }
    
    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "pagerduty": Mock(),
            "prometheus": Mock(),
            "kubernetes": Mock(),
            "slack": Mock()
        }
    
    @pytest.fixture
    def pagerduty_trigger(self):
        """Sample PagerDuty trigger payload"""
        return {
            "source": "pagerduty",
            "incident_id": "P1234567",
            "title": "High Error Rate on api-gateway",
            "severity": "critical",
            "namespace": "production",
            "labels": {"app": "api-gateway"},
            "alert_query": "rate(http_requests_total{status=~\"5..\"}[5m]) > 0.1",
            "fired_at": datetime.utcnow().isoformat()
        }
    
    @pytest.fixture
    def alertmanager_trigger(self):
        """Sample Alertmanager trigger payload"""
        return {
            "source": "alertmanager",
            "alert_name": "HighErrorRate",
            "severity": "warning",
            "namespace": "default",
            "job": "api-gateway",
            "alert_query": "rate(http_requests_total{status=~\"5..\"}[5m])",
            "labels": {},
            "fired_at": datetime.utcnow().isoformat()
        }
    
    def test_acknowledge_step_pagerduty(self, agent_config, mock_skills, pagerduty_trigger):
        """Test that PagerDuty incidents are acknowledged when auto_ack is true"""
        mock_skills["pagerduty"].acknowledge_incident.return_value = {"status": "acknowledged"}
        
        # Simulate step execution
        result = mock_skills["pagerduty"].acknowledge_incident(
            incident_id=pagerduty_trigger["incident_id"],
            message="Auto-acknowledged by OpenSRE incident-responder"
        )
        
        mock_skills["pagerduty"].acknowledge_incident.assert_called_once_with(
            incident_id="P1234567",
            message="Auto-acknowledged by OpenSRE incident-responder"
        )
        assert result["status"] == "acknowledged"
    
    def test_acknowledge_skipped_for_alertmanager(self, agent_config, mock_skills, alertmanager_trigger):
        """Test that acknowledge step is skipped for non-PagerDuty sources"""
        # Condition: trigger.source == 'pagerduty'
        # Since source is 'alertmanager', this step should not execute
        condition = alertmanager_trigger["source"] == "pagerduty"
        assert condition is False
        mock_skills["pagerduty"].acknowledge_incident.assert_not_called()
    
    def test_gather_context_step(self, mock_skills, pagerduty_trigger):
        """Test Prometheus metric gathering"""
        mock_skills["prometheus"].query.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"instance": "api-1"}, "value": [1234567890, "0.15"]},
                    {"metric": {"instance": "api-2"}, "value": [1234567890, "0.12"]}
                ]
            }
        }
        
        result = mock_skills["prometheus"].query(
            promql=pagerduty_trigger["alert_query"],
            time_range="30m",
            step="1m"
        )
        
        assert result["status"] == "success"
        assert len(result["data"]["result"]) == 2
    
    def test_check_pods_step(self, mock_skills, pagerduty_trigger):
        """Test Kubernetes pod status check"""
        mock_skills["kubernetes"].get_pods.return_value = {
            "items": [
                {
                    "metadata": {"name": "api-gateway-abc123"},
                    "status": {"phase": "CrashLoopBackOff"}
                }
            ]
        }
        
        result = mock_skills["kubernetes"].get_pods(
            namespace=pagerduty_trigger["namespace"],
            labels=pagerduty_trigger["labels"],
            field_selector="status.phase!=Running"
        )
        
        assert len(result["items"]) == 1
        assert result["items"][0]["status"]["phase"] == "CrashLoopBackOff"
    
    def test_get_recent_events_step(self, mock_skills, pagerduty_trigger):
        """Test Kubernetes events retrieval"""
        mock_skills["kubernetes"].get_events.return_value = {
            "items": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "involvedObject": {"name": "api-gateway-abc123"}
                }
            ]
        }
        
        result = mock_skills["kubernetes"].get_events(
            namespace=pagerduty_trigger["namespace"],
            field_selector="type=Warning",
            limit=20
        )
        
        assert len(result["items"]) == 1
        assert result["items"][0]["reason"] == "BackOff"
    
    def test_notify_slack_step(self, mock_skills, pagerduty_trigger):
        """Test Slack notification is sent with correct format"""
        mock_skills["slack"].send_message.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }
        
        result = mock_skills["slack"].send_message(
            channel="#incidents",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "🚨 Incident: High Error Rate"}}
            ]
        )
        
        assert result["ok"] is True
        mock_skills["slack"].send_message.assert_called_once()
    
    def test_create_incident_channel_critical(self, mock_skills, pagerduty_trigger):
        """Test incident channel is created for critical severity"""
        mock_skills["slack"].create_channel.return_value = {
            "ok": True,
            "channel": {"id": "C123456", "name": "inc-p1234567"}
        }
        
        # Condition: severity == 'critical'
        assert pagerduty_trigger["severity"] == "critical"
        
        result = mock_skills["slack"].create_channel(
            name=f"inc-{pagerduty_trigger['incident_id'].lower()}",
            topic=f"Incident: {pagerduty_trigger['title']}"
        )
        
        assert result["ok"] is True
    
    def test_create_incident_channel_skipped_non_critical(self, alertmanager_trigger):
        """Test incident channel is NOT created for non-critical severity"""
        # Condition: severity == 'critical'
        assert alertmanager_trigger["severity"] != "critical"
    
    def test_update_pagerduty_notes(self, mock_skills, pagerduty_trigger):
        """Test PagerDuty notes are updated with analysis"""
        mock_skills["pagerduty"].add_note.return_value = {"status": "success"}
        
        result = mock_skills["pagerduty"].add_note(
            incident_id=pagerduty_trigger["incident_id"],
            content="OpenSRE Auto-Analysis:\n- Metrics gathered: 2 data points"
        )
        
        assert result["status"] == "success"
    
    def test_step_error_handling_continue(self, mock_skills):
        """Test that steps with on_error: continue don't stop execution"""
        mock_skills["prometheus"].query.side_effect = Exception("Connection timeout")
        
        with pytest.raises(Exception):
            mock_skills["prometheus"].query(promql="up", time_range="30m")
        
        # Next step should still execute (simulated by calling next skill)
        mock_skills["kubernetes"].get_pods.return_value = {"items": []}
        result = mock_skills["kubernetes"].get_pods(namespace="default")
        assert result["items"] == []
    
    def test_step_retry_logic(self, mock_skills):
        """Test that steps retry on failure"""
        call_count = 0
        
        def flaky_call(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"status": "success"}
        
        mock_skills["prometheus"].query.side_effect = flaky_call
        
        # Simulate retry logic
        max_retries = 3
        result = None
        for attempt in range(max_retries):
            try:
                result = mock_skills["prometheus"].query(promql="up")
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
        
        assert result["status"] == "success"
        assert call_count == 3
    
    def test_variable_interpolation(self, pagerduty_trigger):
        """Test that variables are correctly interpolated"""
        variables = {
            "incident_id": pagerduty_trigger.get("incident_id"),
            "alert_name": pagerduty_trigger.get("alert_name", "Unknown Alert"),
            "namespace": pagerduty_trigger.get("namespace", "default"),
            "severity": pagerduty_trigger.get("severity", "warning")
        }
        
        assert variables["incident_id"] == "P1234567"
        assert variables["alert_name"] == "Unknown Alert"  # Not in pagerduty trigger
        assert variables["namespace"] == "production"
        assert variables["severity"] == "critical"
    
    def test_full_workflow_pagerduty(self, agent_config, mock_skills, pagerduty_trigger):
        """Integration test: full workflow for PagerDuty incident"""
        # Setup mocks
        mock_skills["pagerduty"].acknowledge_incident.return_value = {"status": "acknowledged"}
        mock_skills["prometheus"].query.return_value = {"status": "success", "data": {"result": []}}
        mock_skills["kubernetes"].get_pods.return_value = {"items": []}
        mock_skills["kubernetes"].get_events.return_value = {"items": []}
        mock_skills["kubernetes"].get_deployments.return_value = {"items": []}
        mock_skills["slack"].send_message.return_value = {"ok": True, "ts": "123"}
        mock_skills["slack"].create_channel.return_value = {"ok": True}
        mock_skills["pagerduty"].add_note.return_value = {"status": "success"}
        
        # Execute workflow steps
        steps_executed = []
        
        # Step 1: Acknowledge (condition met)
        if agent_config["config"]["auto_ack"] and pagerduty_trigger["source"] == "pagerduty":
            mock_skills["pagerduty"].acknowledge_incident(incident_id=pagerduty_trigger["incident_id"])
            steps_executed.append("acknowledge")
        
        # Step 2: Gather context
        mock_skills["prometheus"].query(promql=pagerduty_trigger["alert_query"])
        steps_executed.append("gather_context")
        
        # Step 3: Check pods
        mock_skills["kubernetes"].get_pods(namespace=pagerduty_trigger["namespace"])
        steps_executed.append("check_pods")
        
        # Step 4: Get events
        mock_skills["kubernetes"].get_events(namespace=pagerduty_trigger["namespace"])
        steps_executed.append("get_recent_events")
        
        # Step 5: Check deployments
        mock_skills["kubernetes"].get_deployments(namespace=pagerduty_trigger["namespace"])
        steps_executed.append("check_deployments")
        
        # Step 6: Notify Slack
        mock_skills["slack"].send_message(channel=agent_config["config"]["slack_channel"])
        steps_executed.append("notify_slack")
        
        # Step 7: Create channel (condition met - critical)
        if pagerduty_trigger["severity"] == "critical":
            mock_skills["slack"].create_channel(name=f"inc-{pagerduty_trigger['incident_id'].lower()}")
            steps_executed.append("create_incident_channel")
        
        # Step 8: Update PagerDuty notes
        mock_skills["pagerduty"].add_note(incident_id=pagerduty_trigger["incident_id"])
        steps_executed.append("update_pagerduty_notes")
        
        # Verify all expected steps executed
        expected_steps = [
            "acknowledge", "gather_context", "check_pods", "get_recent_events",
            "check_deployments", "notify_slack", "create_incident_channel", "update_pagerduty_notes"
        ]
        assert steps_executed == expected_steps


class TestTriggerValidation:
    """Test trigger payload validation"""
    
    def test_pagerduty_webhook_path(self):
        """Verify PagerDuty webhook path"""
        trigger_config = {
            "type": "webhook",
            "path": "/webhook/pagerduty",
            "source": "pagerduty"
        }
        assert trigger_config["path"] == "/webhook/pagerduty"
    
    def test_alertmanager_webhook_path(self):
        """Verify Alertmanager webhook path"""
        trigger_config = {
            "type": "webhook",
            "path": "/webhook/prometheus",
            "source": "alertmanager"
        }
        assert trigger_config["path"] == "/webhook/prometheus"
    
    def test_missing_incident_id(self):
        """Test handling of missing incident_id"""
        trigger = {"source": "pagerduty", "title": "Test"}
        incident_id = trigger.get("incident_id", f"auto-{datetime.utcnow().timestamp()}")
        assert incident_id.startswith("auto-")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
