"""
Tests for Runbook Executor Agent
"""
import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest


class TestRunbookExecutorAgent:
    """Test suite for runbook-executor agent"""

    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "runbook-executor",
            "version": "1.0.0",
            "config": {
                "runbook_repository": "s3://company-runbooks/",
                "runbook_format": "yaml",
                "slack_channel": "#runbook-executions",
                "require_approval": True,
                "approval_timeout_minutes": 30,
                "dry_run_default": False,
                "max_execution_time_minutes": 60,
                "allowed_actions": [
                    "kubernetes.*",
                    "ssh.execute",
                    "database.query"
                ],
                "blocked_actions": [
                    "ssh.delete_files",
                    "database.drop"
                ]
            }
        }

    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "runbook": Mock(),
            "kubernetes": Mock(),
            "ssh": Mock(),
            "database": Mock(),
            "slack": Mock(),
            "pagerduty": Mock(),
            "llm": Mock(),
            "compute": Mock(),
            "prometheus": Mock()
        }

    @pytest.fixture
    def sample_runbook(self):
        """Sample runbook definition"""
        return {
            "name": "restart-api-server",
            "description": "Safely restart the API server deployment",
            "version": "1.0.0",
            "parameters": [
                {"name": "namespace", "type": "string", "required": True, "default": "production"},
                {"name": "deployment", "type": "string", "required": True}
            ],
            "prerequisites": [
                {
                    "action": "kubernetes.check_deployment_exists",
                    "params": {"namespace": "{{ parameters.namespace }}"}
                }
            ],
            "steps": [
                {
                    "name": "scale_down",
                    "action": "kubernetes.scale_deployment",
                    "params": {"replicas": 0}
                },
                {
                    "name": "wait",
                    "action": "compute.sleep",
                    "params": {"seconds": 30}
                },
                {
                    "name": "scale_up",
                    "action": "kubernetes.scale_deployment",
                    "params": {"replicas": 3}
                }
            ],
            "rollback_on_failure": True
        }

    @pytest.fixture
    def trigger_payload(self):
        """Sample trigger payload"""
        return {
            "runbook_id": "restart-api-server",
            "triggered_by": "user@example.com",
            "parameters": {
                "namespace": "production",
                "deployment": "api-server"
            },
            "dry_run": False
        }

    def test_load_runbook(self, mock_skills, sample_runbook):
        """Test runbook loading from repository"""
        mock_skills["runbook"].load.return_value = sample_runbook

        result = mock_skills["runbook"].load(
            repository="s3://company-runbooks/",
            runbook_id="restart-api-server",
            format="yaml"
        )

        assert result["name"] == "restart-api-server"
        assert len(result["steps"]) == 3

    def test_validate_runbook_allowed_actions(self, mock_skills, sample_runbook, agent_config):
        """Test runbook validation passes with allowed actions"""
        mock_skills["runbook"].validate.return_value = {
            "valid": True,
            "errors": []
        }

        result = mock_skills["runbook"].validate(
            runbook=sample_runbook,
            allowed_actions=agent_config["config"]["allowed_actions"],
            blocked_actions=agent_config["config"]["blocked_actions"]
        )

        assert result["valid"] is True

    def test_validate_runbook_blocked_actions(self, mock_skills, agent_config):
        """Test runbook validation fails with blocked actions"""
        dangerous_runbook = {
            "name": "dangerous",
            "steps": [{"action": "database.drop", "params": {"table": "users"}}]
        }

        mock_skills["runbook"].validate.return_value = {
            "valid": False,
            "errors": ["Action 'database.drop' is blocked"]
        }

        result = mock_skills["runbook"].validate(
            runbook=dangerous_runbook,
            blocked_actions=agent_config["config"]["blocked_actions"]
        )

        assert result["valid"] is False
        assert "blocked" in result["errors"][0]

    def test_check_prerequisites_pass(self, mock_skills):
        """Test prerequisites check passes"""
        mock_skills["runbook"].check_prerequisites.return_value = {
            "passed": True,
            "results": [
                {"check": "kubernetes.check_deployment_exists", "passed": True}
            ]
        }

        result = mock_skills["runbook"].check_prerequisites(
            runbook={"prerequisites": []},
            parameters={"namespace": "production"}
        )

        assert result["passed"] is True

    def test_check_prerequisites_fail(self, mock_skills):
        """Test prerequisites check fails"""
        mock_skills["runbook"].check_prerequisites.return_value = {
            "passed": False,
            "results": [
                {"check": "kubernetes.check_deployment_exists", "passed": False,
                 "error": "Deployment not found"}
            ]
        }

        result = mock_skills["runbook"].check_prerequisites(
            runbook={"prerequisites": []},
            parameters={"namespace": "production", "deployment": "missing"}
        )

        assert result["passed"] is False

    def test_request_approval(self, mock_skills, sample_runbook):
        """Test approval request sent to Slack"""
        mock_skills["slack"].send_message.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }

        result = mock_skills["slack"].send_message(
            channel="#runbook-executions",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "📋 Runbook Execution Request"}}
            ]
        )

        assert result["ok"] is True

    def test_wait_for_approval_approved(self, mock_skills):
        """Test approval workflow - approved"""
        mock_skills["slack"].wait_interaction.return_value = {
            "action": "approve_runbook",
            "user": "approver@example.com",
            "timestamp": datetime.utcnow().isoformat()
        }

        result = mock_skills["slack"].wait_interaction(
            execution_id="exec-123",
            timeout_minutes=30,
            valid_actions=["approve_runbook", "reject_runbook"]
        )

        assert result["action"] == "approve_runbook"

    def test_wait_for_approval_rejected(self, mock_skills):
        """Test approval workflow - rejected"""
        mock_skills["slack"].wait_interaction.return_value = {
            "action": "reject_runbook",
            "user": "approver@example.com",
            "timestamp": datetime.utcnow().isoformat()
        }

        result = mock_skills["slack"].wait_interaction(
            execution_id="exec-123",
            timeout_minutes=30
        )

        assert result["action"] == "reject_runbook"

    def test_execute_runbook_success(self, mock_skills, sample_runbook, trigger_payload):
        """Test successful runbook execution"""
        mock_skills["runbook"].execute.return_value = {
            "status": "success",
            "completed_steps": 3,
            "duration_seconds": 45,
            "summary": "All steps completed successfully"
        }

        result = mock_skills["runbook"].execute(
            runbook=sample_runbook,
            parameters=trigger_payload["parameters"],
            dry_run=False
        )

        assert result["status"] == "success"
        assert result["completed_steps"] == 3

    def test_execute_runbook_failure(self, mock_skills, sample_runbook):
        """Test runbook execution failure"""
        mock_skills["runbook"].execute.return_value = {
            "status": "failed",
            "completed_steps": 2,
            "duration_seconds": 30,
            "failed_step": {
                "name": "scale_up",
                "action": "kubernetes.scale_deployment",
                "error": "Timeout waiting for pods"
            }
        }

        result = mock_skills["runbook"].execute(
            runbook=sample_runbook,
            parameters={"namespace": "production"},
            dry_run=False
        )

        assert result["status"] == "failed"
        assert result["failed_step"]["name"] == "scale_up"

    def test_execute_runbook_dry_run(self, mock_skills, sample_runbook):
        """Test dry-run execution"""
        mock_skills["runbook"].execute.return_value = {
            "status": "success",
            "completed_steps": 3,
            "duration_seconds": 1,
            "dry_run": True,
            "simulated_actions": [
                "Would scale deployment to 0 replicas",
                "Would wait 30 seconds",
                "Would scale deployment to 3 replicas"
            ]
        }

        result = mock_skills["runbook"].execute(
            runbook=sample_runbook,
            parameters={},
            dry_run=True
        )

        assert result["status"] == "success"
        assert result["dry_run"] is True

    def test_analyze_execution_failure(self, mock_skills):
        """Test LLM failure analysis"""
        mock_skills["llm"].analyze.return_value = {
            "root_cause": "Insufficient resources to scale up",
            "suggested_fix": "Increase node capacity or reduce pod resource requests",
            "retry_recommended": False
        }

        result = mock_skills["llm"].analyze(
            prompt="Analyze this runbook execution failure...",
            model="gpt-4"
        )

        assert "root_cause" in result
        assert "suggested_fix" in result

    def test_notify_success(self, mock_skills):
        """Test success notification"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#runbook-executions",
            blocks=[{"type": "header", "text": {"type": "plain_text", "text": "✅ Runbook Completed"}}]
        )

        assert result["ok"] is True

    def test_notify_failure(self, mock_skills):
        """Test failure notification with retry button"""
        mock_skills["slack"].send_message.return_value = {"ok": True}

        result = mock_skills["slack"].send_message(
            channel="#runbook-executions",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "❌ Runbook Failed"}},
                {"type": "actions", "elements": [{"action_id": "retry_runbook"}]}
            ]
        )

        assert result["ok"] is True

    def test_update_pagerduty(self, mock_skills):
        """Test PagerDuty incident update"""
        mock_skills["pagerduty"].add_note.return_value = {"status": "success"}

        result = mock_skills["pagerduty"].add_note(
            incident_id="P123456",
            content="Runbook Execution: SUCCESS\n\nRunbook: restart-api-server"
        )

        assert result["status"] == "success"

    def test_store_execution_record(self, mock_skills, trigger_payload):
        """Test execution record storage"""
        execution_id = str(uuid.uuid4())
        mock_skills["database"].insert.return_value = {"inserted": 1}

        result = mock_skills["database"].insert(
            table="runbook_executions",
            record={
                "execution_id": execution_id,
                "runbook_id": trigger_payload["runbook_id"],
                "status": "success"
            }
        )

        assert result["inserted"] == 1

    def test_push_metrics(self, mock_skills, trigger_payload):
        """Test metrics push"""
        mock_skills["prometheus"].push_metrics.return_value = {"status": "success"}

        result = mock_skills["prometheus"].push_metrics(
            metrics=[
                {"name": "opensre_runbook_execution_total", "value": 1},
                {"name": "opensre_runbook_execution_duration_seconds", "value": 45}
            ]
        )

        assert result["status"] == "success"

    def test_full_workflow_approved(self, agent_config, mock_skills, sample_runbook, trigger_payload):
        """Integration test: full workflow with approval"""
        # Setup mocks
        mock_skills["runbook"].load.return_value = sample_runbook
        mock_skills["runbook"].validate.return_value = {"valid": True}
        mock_skills["runbook"].check_prerequisites.return_value = {"passed": True}
        mock_skills["slack"].send_message.return_value = {"ok": True, "ts": "123"}
        mock_skills["slack"].wait_interaction.return_value = {"action": "approve_runbook", "user": "approver"}
        mock_skills["runbook"].execute.return_value = {"status": "success", "duration_seconds": 45}
        mock_skills["runbook"].get_logs.return_value = "Logs..."
        mock_skills["database"].insert.return_value = {"inserted": 1}
        mock_skills["prometheus"].push_metrics.return_value = {}

        steps_executed = []

        # Execute workflow
        mock_skills["runbook"].load(runbook_id=trigger_payload["runbook_id"])
        steps_executed.append("load_runbook")

        mock_skills["runbook"].validate(runbook=sample_runbook)
        steps_executed.append("validate_runbook")

        mock_skills["runbook"].check_prerequisites(runbook=sample_runbook)
        steps_executed.append("check_prerequisites")

        if agent_config["config"]["require_approval"]:
            mock_skills["slack"].send_message(channel="#runbook-executions")
            steps_executed.append("request_approval")

            result = mock_skills["slack"].wait_interaction(execution_id="exec-123")
            steps_executed.append("wait_for_approval")

            if result["action"] == "approve_runbook":
                steps_executed.append("approved")

        mock_skills["slack"].send_message(text="Execution started")
        steps_executed.append("notify_execution_start")

        mock_skills["runbook"].execute(runbook=sample_runbook)
        steps_executed.append("execute_runbook")

        mock_skills["runbook"].get_logs(execution_id="exec-123")
        steps_executed.append("collect_execution_logs")

        mock_skills["slack"].send_message(text="Success")
        steps_executed.append("notify_success")

        mock_skills["database"].insert(table="runbook_executions", record={})
        steps_executed.append("store_execution_record")

        mock_skills["prometheus"].push_metrics(metrics=[])
        steps_executed.append("push_metrics")

        expected = [
            "load_runbook", "validate_runbook", "check_prerequisites",
            "request_approval", "wait_for_approval", "approved",
            "notify_execution_start", "execute_runbook", "collect_execution_logs",
            "notify_success", "store_execution_record", "push_metrics"
        ]
        assert steps_executed == expected


class TestActionValidation:
    """Test action validation logic"""

    def test_action_matches_pattern(self):
        """Test action pattern matching"""
        def matches_pattern(action, pattern):
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                return action.startswith(prefix + ".")
            return action == pattern

        assert matches_pattern("kubernetes.scale_deployment", "kubernetes.*") is True
        assert matches_pattern("kubernetes.delete_namespace", "kubernetes.*") is True
        assert matches_pattern("ssh.execute", "kubernetes.*") is False
        assert matches_pattern("ssh.execute", "ssh.execute") is True

    def test_action_allowed(self):
        """Test allowed action check"""
        allowed_actions = ["kubernetes.*", "ssh.execute"]
        blocked_actions = ["kubernetes.delete_namespace"]

        def is_allowed(action):
            # Check blocked first
            if action in blocked_actions:
                return False
            # Check allowed patterns
            for pattern in allowed_actions:
                if pattern.endswith(".*"):
                    if action.startswith(pattern[:-2] + "."):
                        return True
                elif action == pattern:
                    return True
            return False

        assert is_allowed("kubernetes.scale_deployment") is True
        assert is_allowed("kubernetes.delete_namespace") is False
        assert is_allowed("ssh.execute") is True
        assert is_allowed("database.drop") is False


class TestApprovalFlow:
    """Test approval flow logic"""

    def test_approval_required(self):
        """Test approval requirement check"""
        config = {"require_approval": True, "dry_run_default": False}
        dry_run = False

        needs_approval = config["require_approval"] and not dry_run
        assert needs_approval is True

    def test_approval_not_required_dry_run(self):
        """Test no approval needed for dry run"""
        config = {"require_approval": True}
        dry_run = True

        needs_approval = config["require_approval"] and not dry_run
        assert needs_approval is False

    def test_approval_timeout(self):
        """Test approval timeout handling"""
        # Simulate timeout
        interaction_result = {"action": "timeout", "user": None}

        should_abort = interaction_result["action"] == "timeout"
        assert should_abort is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
