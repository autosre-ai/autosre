"""
Unit Tests for ActorAgent

Tests the action planning and execution functionality including:
- Risk level determination
- Action parsing from LLM responses
- Command execution with approval flow
- Security sanitization integration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensre_core.agents.act import (
    Action,
    ActionPlan,
    ActionRisk,
    ActionStatus,
    ActorAgent,
)


class TestActorAgentRiskDetermination:
    """Tests for command risk level determination."""

    @pytest.fixture
    def agent(self):
        return ActorAgent()

    # LOW risk commands
    def test_determine_risk_level_get(self, agent):
        """Test GET commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl get pods -n default")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_describe(self, agent):
        """Test DESCRIBE commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl describe pod my-pod")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_logs(self, agent):
        """Test LOGS commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl logs my-pod --tail=100")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_top(self, agent):
        """Test TOP commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl top pods")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_events(self, agent):
        """Test EVENTS commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl events -n production")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_explain(self, agent):
        """Test EXPLAIN commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl explain deployment")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_version(self, agent):
        """Test VERSION commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl version")
        assert risk == ActionRisk.LOW

    def test_determine_risk_level_cluster_info(self, agent):
        """Test CLUSTER-INFO commands are LOW risk."""
        risk = agent._determine_risk_level("kubectl cluster-info")
        assert risk == ActionRisk.LOW

    # MEDIUM risk commands
    def test_determine_risk_level_scale(self, agent):
        """Test SCALE commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl scale deployment/api --replicas=3")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_rollout_restart(self, agent):
        """Test ROLLOUT RESTART commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl rollout restart deployment/api")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_rollout_status(self, agent):
        """Test ROLLOUT STATUS commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl rollout status deployment/api")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_cordon(self, agent):
        """Test CORDON commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl cordon node-1")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_uncordon(self, agent):
        """Test UNCORDON commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl uncordon node-1")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_label(self, agent):
        """Test LABEL commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl label pods my-pod env=prod")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_annotate(self, agent):
        """Test ANNOTATE commands are MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl annotate deployment api version=2")
        assert risk == ActionRisk.MEDIUM

    # HIGH risk commands
    def test_determine_risk_level_delete(self, agent):
        """Test DELETE commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl delete pod my-pod")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_apply(self, agent):
        """Test APPLY commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl apply -f config.yaml")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_patch(self, agent):
        """Test PATCH commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl patch deployment api -p '{}'")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_edit(self, agent):
        """Test EDIT commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl edit deployment api")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_create(self, agent):
        """Test CREATE commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl create secret generic my-secret")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_replace(self, agent):
        """Test REPLACE commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl replace -f config.yaml")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_rollout_undo(self, agent):
        """Test ROLLOUT UNDO commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl rollout undo deployment/api")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_exec(self, agent):
        """Test EXEC commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl exec -it my-pod -- bash")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_drain(self, agent):
        """Test DRAIN commands are HIGH risk."""
        risk = agent._determine_risk_level("kubectl drain node-1")
        assert risk == ActionRisk.HIGH

    def test_determine_risk_level_unknown_defaults_medium(self, agent):
        """Test unknown commands default to MEDIUM risk."""
        risk = agent._determine_risk_level("kubectl custom-verb something")
        assert risk == ActionRisk.MEDIUM

    def test_determine_risk_level_non_kubectl(self, agent):
        """Test non-kubectl commands default to MEDIUM."""
        risk = agent._determine_risk_level("helm install my-release")
        assert risk == ActionRisk.MEDIUM


class TestActorAgentAssessRisk:
    """Tests for risk assessment (risk + approval requirement)."""

    @pytest.fixture
    def agent(self):
        return ActorAgent()

    def test_assess_risk_low_no_approval(self, agent):
        """Test LOW risk commands don't require approval."""
        risk, requires_approval = agent._assess_risk("kubectl get pods")

        assert risk == ActionRisk.LOW
        assert requires_approval is False

    def test_assess_risk_medium_requires_approval(self, agent):
        """Test MEDIUM risk commands require approval."""
        risk, requires_approval = agent._assess_risk("kubectl scale deployment/api --replicas=3")

        assert risk == ActionRisk.MEDIUM
        assert requires_approval is True

    def test_assess_risk_high_requires_approval(self, agent):
        """Test HIGH risk commands require approval."""
        risk, requires_approval = agent._assess_risk("kubectl delete pod my-pod")

        assert risk == ActionRisk.HIGH
        assert requires_approval is True


class TestActionDataclass:
    """Tests for Action dataclass."""

    def test_action_creation(self):
        """Test action creation with all fields."""
        action = Action(
            id="action_1",
            description="Restart deployment",
            command="kubectl rollout restart deployment/api",
            risk=ActionRisk.MEDIUM,
            requires_approval=True,
            rationale="Apply new configuration",
        )

        assert action.id == "action_1"
        assert action.risk == ActionRisk.MEDIUM
        assert action.status == ActionStatus.PENDING

    def test_action_is_safe_true(self):
        """Test is_safe for low-risk, no-approval actions."""
        action = Action(
            id="action_1",
            description="Get pods",
            command="kubectl get pods",
            risk=ActionRisk.LOW,
            requires_approval=False,
        )

        assert action.is_safe is True

    def test_action_is_safe_false_high_risk(self):
        """Test is_safe is False for high-risk actions."""
        action = Action(
            id="action_1",
            description="Delete pod",
            command="kubectl delete pod my-pod",
            risk=ActionRisk.HIGH,
            requires_approval=True,
        )

        assert action.is_safe is False

    def test_action_is_safe_false_requires_approval(self):
        """Test is_safe is False when approval required."""
        action = Action(
            id="action_1",
            description="Scale",
            command="kubectl scale deployment/api --replicas=3",
            risk=ActionRisk.LOW,  # Even if marked low risk
            requires_approval=True,  # But requires approval
        )

        assert action.is_safe is False


class TestActionPlan:
    """Tests for ActionPlan dataclass."""

    def test_action_plan_get_pending(self, sample_action_plan):
        """Test getting pending actions."""
        pending = sample_action_plan.get_pending()

        assert len(pending) == 3
        assert all(a.status == ActionStatus.PENDING for a in pending)

    def test_action_plan_get_safe_actions(self, sample_action_plan):
        """Test getting safe actions."""
        safe = sample_action_plan.get_safe_actions()

        assert len(safe) == 1
        assert all(a.is_safe for a in safe)


class TestActorAgentPlanActions:
    """Tests for action planning."""

    @pytest.fixture
    def agent(self, mock_llm, mock_audit_logger):
        agent = ActorAgent()
        agent.llm = mock_llm
        agent.audit = mock_audit_logger
        return agent

    @pytest.mark.asyncio
    async def test_plan_actions_returns_plan(self, agent, sample_analysis_result, mock_llm):
        """Test plan_actions returns ActionPlan."""
        mock_llm.generate.return_value = MagicMock(
            content="""
1. Check current pod status
`kubectl get pods -n default -l app=api-server`

2. Restart the deployment
`kubectl rollout restart deployment/api-server -n default`
"""
        )

        plan = await agent.plan_actions(sample_analysis_result, namespace="default")

        assert isinstance(plan, ActionPlan)

    @pytest.mark.asyncio
    async def test_plan_actions_extracts_commands(self, agent, sample_analysis_result, mock_llm):
        """Test commands are extracted from LLM response."""
        mock_llm.generate.return_value = MagicMock(
            content="""
1. Check pods: `kubectl get pods -n default`
2. Delete stuck pod: `kubectl delete pod stuck-pod -n default`
"""
        )

        plan = await agent.plan_actions(sample_analysis_result)

        assert len(plan.actions) >= 2

    @pytest.mark.asyncio
    async def test_plan_actions_assigns_risk_levels(self, agent, sample_analysis_result, mock_llm):
        """Test risk levels are assigned to actions."""
        mock_llm.generate.return_value = MagicMock(
            content="""
1. Check pods: `kubectl get pods -n default`
2. Delete pod: `kubectl delete pod my-pod -n default`
"""
        )

        plan = await agent.plan_actions(sample_analysis_result)

        # Should have different risk levels
        risks = [a.risk for a in plan.actions]
        assert ActionRisk.LOW in risks or ActionRisk.HIGH in risks


class TestActorAgentExecuteAction:
    """Tests for action execution."""

    @pytest.fixture
    def agent(self, mock_audit_logger):
        agent = ActorAgent()
        agent.audit = mock_audit_logger
        return agent

    @pytest.fixture
    def low_risk_action(self):
        return Action(
            id="action_1",
            description="Get pods",
            command="kubectl get pods -n default",
            risk=ActionRisk.LOW,
            requires_approval=False,
        )

    @pytest.fixture
    def high_risk_action(self):
        return Action(
            id="action_2",
            description="Delete pod",
            command="kubectl delete pod my-pod -n default",
            risk=ActionRisk.HIGH,
            requires_approval=True,
        )

    @pytest.mark.asyncio
    async def test_execute_action_dry_run(self, agent, low_risk_action):
        """Test dry run mode."""
        result = await agent.execute_action(low_risk_action, dry_run=True)

        assert result["dry_run"] is True
        assert result["command"] == low_risk_action.command
        assert low_risk_action.status == ActionStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_action_checks_rbac(self, agent, high_risk_action):
        """Test RBAC permission check."""
        # Try with viewer role (insufficient permissions)
        result = await agent.execute_action(
            high_risk_action,
            dry_run=False,
            user_roles=["viewer"],
        )

        assert "error" in result or "Permission denied" in str(result.get("error", ""))

    @pytest.mark.asyncio
    async def test_execute_action_sanitizes_command(self, agent):
        """Test command sanitization."""
        malicious_action = Action(
            id="action_malicious",
            description="Bad action",
            command="kubectl get pods; rm -rf /",
            risk=ActionRisk.LOW,
            requires_approval=False,
        )

        await agent.execute_action(
            malicious_action,
            dry_run=False,
            user_roles=["sre"],
        )

        # Should be blocked by sanitization
        assert malicious_action.status == ActionStatus.REJECTED

    @pytest.mark.asyncio
    async def test_execute_action_requires_approval(self, agent, high_risk_action):
        """Test approval requirement for high-risk actions."""
        with patch.object(agent, '_execute_command', new_callable=AsyncMock):
            with patch("opensre_core.config.settings") as mock_settings:
                mock_settings.require_approval = True

                result = await agent.execute_action(
                    high_risk_action,
                    dry_run=False,
                    user_roles=["sre"],
                )

                assert result.get("requires_approval") is True


class TestActorAgentApproveAction:
    """Tests for action approval."""

    @pytest.fixture
    def agent(self, mock_audit_logger):
        agent = ActorAgent()
        agent.audit = mock_audit_logger
        return agent

    @pytest.fixture
    def pending_action(self):
        return Action(
            id="action_1",
            description="Delete pod",
            command="kubectl get pods -n default",  # Using safe command for test
            risk=ActionRisk.HIGH,
            requires_approval=True,
            status=ActionStatus.PENDING,
        )

    @pytest.mark.asyncio
    async def test_approve_action_changes_status(self, agent, pending_action):
        """Test approval changes action status."""
        with patch.object(agent, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "command": pending_action.command,
                "exit_code": 0,
                "stdout": "pod deleted",
                "stderr": "",
                "success": True,
            }

            # Mock settings to not require approval (since we're testing the approval flow)
            with patch("opensre_core.agents.act.settings") as mock_settings:
                mock_settings.require_approval = False

                await agent.approve_action(
                    pending_action,
                    approved_by="admin@example.com",
                    user_roles=["sre"],
                )

                assert pending_action.status == ActionStatus.APPROVED or pending_action.status == ActionStatus.COMPLETED


class TestActorAgentRejectAction:
    """Tests for action rejection."""

    @pytest.fixture
    def agent(self, mock_audit_logger):
        agent = ActorAgent()
        agent.audit = mock_audit_logger
        return agent

    def test_reject_action_changes_status(self, agent):
        """Test rejection changes action status."""
        action = Action(
            id="action_1",
            description="Delete pod",
            command="kubectl delete pod my-pod",
            risk=ActionRisk.HIGH,
            requires_approval=True,
        )

        agent.reject_action(action, reason="Too risky")

        assert action.status == ActionStatus.REJECTED
        assert action.result["rejected"] is True
        assert action.result["reason"] == "Too risky"
