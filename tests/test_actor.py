"""
Tests for the agent/actor module.
"""

import pytest
from unittest.mock import patch, MagicMock

from autosre.agent.actor import (
    ActionType,
    ActionStatus,
    ActionResult,
    Actor,
)


class TestActionType:
    """Test ActionType enum."""
    
    def test_action_types(self):
        """Test all action types exist."""
        assert ActionType.NOTIFICATION == "notification"
        assert ActionType.RUNBOOK == "runbook"
        assert ActionType.SCRIPT == "script"
        assert ActionType.SCALE == "scale"
        assert ActionType.ROLLBACK == "rollback"
        assert ActionType.TICKET == "ticket"
        assert ActionType.RESTART == "restart"


class TestActionStatus:
    """Test ActionStatus enum."""
    
    def test_action_statuses(self):
        """Test all action statuses exist."""
        assert ActionStatus.PENDING == "pending"
        assert ActionStatus.APPROVED == "approved"
        assert ActionStatus.REJECTED == "rejected"
        assert ActionStatus.RUNNING == "running"
        assert ActionStatus.SUCCESS == "success"
        assert ActionStatus.FAILED == "failed"
        assert ActionStatus.DRY_RUN == "dry_run"


class TestActionResult:
    """Test ActionResult model."""
    
    def test_create_result(self):
        """Test creating an action result."""
        result = ActionResult(
            action_id="act-001",
            action_type=ActionType.NOTIFICATION,
            status=ActionStatus.SUCCESS,
            description="Send alert notification",
        )
        assert result.action_id == "act-001"
        assert result.action_type == ActionType.NOTIFICATION
        assert result.status == ActionStatus.SUCCESS
    
    def test_result_with_target(self):
        """Test result with target."""
        result = ActionResult(
            action_id="act-002",
            action_type=ActionType.SCALE,
            status=ActionStatus.DRY_RUN,
            description="Scale deployment",
            target="api-service",
            dry_run=True,
            would_execute="Would scale to 5 replicas",
        )
        assert result.target == "api-service"
        assert result.dry_run is True
        assert "5 replicas" in result.would_execute
    
    def test_result_with_error(self):
        """Test result with error."""
        result = ActionResult(
            action_id="act-003",
            action_type=ActionType.SCRIPT,
            status=ActionStatus.FAILED,
            description="Execute script",
            error="Permission denied",
        )
        assert result.status == ActionStatus.FAILED
        assert result.error == "Permission denied"


class TestActor:
    """Test Actor class."""
    
    @pytest.fixture
    def actor(self):
        """Create an actor in dry-run mode."""
        return Actor(dry_run=True, require_approval=False)
    
    @pytest.fixture
    def live_actor(self):
        """Create an actor for live execution."""
        return Actor(dry_run=False, require_approval=False)
    
    @pytest.fixture
    def approval_actor(self):
        """Create an actor requiring approval."""
        return Actor(dry_run=False, require_approval=True)
    
    def test_init_defaults(self):
        """Test actor initialization with defaults."""
        actor = Actor()
        assert actor.dry_run is True
        assert actor.require_approval is True
        assert actor.kubeconfig is None
    
    def test_init_custom(self):
        """Test actor initialization with custom settings."""
        actor = Actor(
            dry_run=False,
            require_approval=False,
            kubeconfig="/path/to/kubeconfig",
        )
        assert actor.dry_run is False
        assert actor.require_approval is False
        assert actor.kubeconfig == "/path/to/kubeconfig"
    
    @pytest.mark.asyncio
    async def test_execute_notification_dry_run(self, actor):
        """Test notification in dry-run mode."""
        result = await actor.execute(
            ActionType.NOTIFICATION,
            target="#alerts",
            params={"message": "CPU alert resolved"},
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert result.dry_run is True
        assert "#alerts" in result.would_execute
        assert "CPU alert resolved" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_notification_live(self, live_actor):
        """Test notification in live mode."""
        result = await live_actor.execute(
            ActionType.NOTIFICATION,
            target="#alerts",
            params={"message": "Test message"},
        )
        
        assert result.status == ActionStatus.SUCCESS
        assert "Notification sent" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_runbook_dry_run(self, actor):
        """Test runbook execution in dry-run mode."""
        result = await actor.execute(
            ActionType.RUNBOOK,
            target="memory-leak-investigation",
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "memory-leak-investigation" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_scale_dry_run(self, actor):
        """Test scale action in dry-run mode."""
        result = await actor.execute(
            ActionType.SCALE,
            target="api-deployment",
            params={"replicas": 5, "namespace": "production"},
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "api-deployment" in result.would_execute
        assert "5" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_scale_live(self, live_actor):
        """Test scale action in live mode with kubectl mock."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="deployment.apps/api scaled",
                stderr="",
            )
            
            result = await live_actor.execute(
                ActionType.SCALE,
                target="api-deployment",
                params={"replicas": 3},
            )
            
            assert result.status == ActionStatus.SUCCESS
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_scale_failed(self, live_actor):
        """Test scale action failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="deployment not found",
            )
            
            result = await live_actor.execute(
                ActionType.SCALE,
                target="nonexistent",
                params={"replicas": 3},
            )
            
            assert result.status == ActionStatus.FAILED
            assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_rollback_dry_run(self, actor):
        """Test rollback action in dry-run mode."""
        result = await actor.execute(
            ActionType.ROLLBACK,
            target="api-deployment",
            params={"namespace": "default"},
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "rollback" in result.would_execute.lower()
    
    @pytest.mark.asyncio
    async def test_execute_rollback_with_revision(self, actor):
        """Test rollback to specific revision."""
        result = await actor.execute(
            ActionType.ROLLBACK,
            target="api-deployment",
            params={"revision": 5},
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "revision 5" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_restart_dry_run(self, actor):
        """Test restart action in dry-run mode."""
        result = await actor.execute(
            ActionType.RESTART,
            target="api-deployment",
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "restart" in result.would_execute.lower()
    
    @pytest.mark.asyncio
    async def test_execute_ticket_dry_run(self, actor):
        """Test ticket creation in dry-run mode."""
        result = await actor.execute(
            ActionType.TICKET,
            target="JIRA",
            params={
                "title": "Memory leak investigation",
                "priority": "critical",
            },
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "critical" in result.would_execute
        assert "Memory leak" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_script_dry_run(self, actor):
        """Test script execution in dry-run mode."""
        result = await actor.execute(
            ActionType.SCRIPT,
            target="/opt/scripts/restart-service.sh",
            params={"args": ["api-service"]},
        )
        
        assert result.status == ActionStatus.DRY_RUN
        assert "restart-service.sh" in result.would_execute
    
    @pytest.mark.asyncio
    async def test_execute_script_requires_explicit_approval(self, live_actor):
        """Test script execution requires explicit approval."""
        result = await live_actor.execute(
            ActionType.SCRIPT,
            target="/opt/scripts/dangerous.sh",
            params={},
        )
        
        assert result.status == ActionStatus.FAILED
        assert "explicit approval" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_script_with_explicit_approval(self, live_actor):
        """Test script execution with explicit approval."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Script executed successfully",
                stderr="",
            )
            
            result = await live_actor.execute(
                ActionType.SCRIPT,
                target="/opt/scripts/safe.sh",
                params={"explicitly_approved": True},
            )
            
            assert result.status == ActionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_execute_requires_approval(self, approval_actor):
        """Test action requiring approval."""
        result = await approval_actor.execute(
            ActionType.SCALE,
            target="api-deployment",
            params={"replicas": 10},
            approved=False,
        )
        
        assert result.status == ActionStatus.PENDING
        assert "requires approval" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_with_approval(self, approval_actor):
        """Test action with approval."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="scaled",
                stderr="",
            )
            
            result = await approval_actor.execute(
                ActionType.SCALE,
                target="api-deployment",
                params={"replicas": 5},
                approved=True,
            )
            
            assert result.status == ActionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_action_history(self, actor):
        """Test action history tracking."""
        await actor.execute(ActionType.NOTIFICATION, "#alerts")
        await actor.execute(ActionType.RUNBOOK, "test-runbook")
        await actor.execute(ActionType.TICKET, "JIRA")
        
        history = actor.get_history()
        assert len(history) == 3
        assert history[0].action_type == ActionType.NOTIFICATION
        assert history[2].action_type == ActionType.TICKET
    
    @pytest.mark.asyncio
    async def test_action_history_limit(self, actor):
        """Test action history limit."""
        for i in range(10):
            await actor.execute(ActionType.NOTIFICATION, f"#channel-{i}")
        
        history = actor.get_history(limit=5)
        assert len(history) == 5
    
    def test_clear_history(self, actor):
        """Test clearing action history."""
        actor._action_history = [
            ActionResult(
                action_id="test",
                action_type=ActionType.NOTIFICATION,
                status=ActionStatus.SUCCESS,
                description="test",
            )
        ]
        
        actor.clear_history()
        assert len(actor._action_history) == 0
    
    @pytest.mark.asyncio
    async def test_action_timestamps(self, actor):
        """Test action timestamps are set."""
        result = await actor.execute(
            ActionType.NOTIFICATION,
            target="#test",
        )
        
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
    
    @pytest.mark.asyncio
    async def test_kubeconfig_passed_to_kubectl(self, live_actor):
        """Test kubeconfig is passed to kubectl commands."""
        live_actor.kubeconfig = "/custom/kubeconfig"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            
            await live_actor.execute(
                ActionType.SCALE,
                target="deployment",
                params={"replicas": 1},
            )
            
            call_args = mock_run.call_args[0][0]
            assert "--kubeconfig" in call_args
            assert "/custom/kubeconfig" in call_args


class TestActorEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_execute_with_exception(self):
        """Test handling of unexpected exceptions."""
        actor = Actor(dry_run=False, require_approval=False)
        
        # Patch to raise exception
        with patch.object(actor, '_send_notification', side_effect=Exception("Unexpected error")):
            result = await actor.execute(
                ActionType.NOTIFICATION,
                target="#test",
            )
            
            assert result.status == ActionStatus.FAILED
            assert "Unexpected error" in result.error
    
    @pytest.mark.asyncio
    async def test_action_id_generated(self):
        """Test action ID is auto-generated."""
        actor = Actor(dry_run=True)
        
        result = await actor.execute(
            ActionType.NOTIFICATION,
            target="#test",
        )
        
        assert result.action_id is not None
        assert len(result.action_id) == 8
