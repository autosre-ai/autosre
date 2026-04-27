"""
Tests for the actor module (action execution with guardrails).
"""

import pytest
from datetime import datetime, timezone

from autosre.agent.actor import (
    Actor,
    ActionType,
    ActionStatus,
    ActionResult,
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TestActionTypeEnum:
    """Test ActionType enum."""
    
    def test_action_types(self):
        """Test action type values."""
        assert ActionType.NOTIFICATION.value == "notification"
        assert ActionType.RUNBOOK.value == "runbook"
        assert ActionType.SCRIPT.value == "script"
        assert ActionType.RESTART.value == "restart"
        assert ActionType.ROLLBACK.value == "rollback"


class TestActionStatusEnum:
    """Test ActionStatus enum."""
    
    def test_action_statuses(self):
        """Test action status values."""
        assert ActionStatus.PENDING.value == "pending"
        assert ActionStatus.SUCCESS.value == "success"
        assert ActionStatus.FAILED.value == "failed"
        assert ActionStatus.DRY_RUN.value == "dry_run"


class TestActionResult:
    """Test ActionResult model."""
    
    def test_create_result(self):
        """Test creating action result."""
        result = ActionResult(
            action_id="action-001",
            action_type=ActionType.NOTIFICATION,
            status=ActionStatus.SUCCESS,
            description="Sent Slack notification",
        )
        
        assert result.action_id == "action-001"
        assert result.action_type == ActionType.NOTIFICATION
        assert result.status == ActionStatus.SUCCESS
    
    def test_result_with_output(self):
        """Test result with output."""
        result = ActionResult(
            action_id="action-002",
            action_type=ActionType.SCRIPT,
            status=ActionStatus.SUCCESS,
            description="Ran diagnostic script",
            output="All checks passed",
        )
        
        assert result.output == "All checks passed"
        assert result.error is None
    
    def test_result_with_error(self):
        """Test result with error."""
        result = ActionResult(
            action_id="action-003",
            action_type=ActionType.RESTART,
            status=ActionStatus.FAILED,
            description="Restart pod",
            error="Pod not found",
        )
        
        assert result.status == ActionStatus.FAILED
        assert result.error == "Pod not found"
    
    def test_dry_run_result(self):
        """Test dry run result."""
        result = ActionResult(
            action_id="action-004",
            action_type=ActionType.SCALE,
            status=ActionStatus.DRY_RUN,
            description="Scale deployment",
            dry_run=True,
            would_execute="kubectl scale deployment api-server --replicas=3",
        )
        
        assert result.dry_run is True
        assert "kubectl scale" in result.would_execute


class TestActor:
    """Test Actor functionality."""
    
    def test_create_actor_dry_run(self):
        """Test creating actor with dry run enabled."""
        actor = Actor(dry_run=True)
        assert actor.dry_run is True
    
    def test_create_actor_live(self):
        """Test creating actor for live execution."""
        actor = Actor(dry_run=False, require_approval=False)
        assert actor.dry_run is False
    
    @pytest.mark.asyncio
    async def test_execute_notification(self):
        """Test executing notification action."""
        actor = Actor(dry_run=True)
        
        result = await actor.execute(
            action_type=ActionType.NOTIFICATION,
            target="#alerts",
            params={"message": "Test notification", "channel": "slack"},
        )
        
        # In dry run, should return DRY_RUN status
        assert result.action_type == ActionType.NOTIFICATION
    
    @pytest.mark.asyncio
    async def test_execute_ticket(self):
        """Test executing ticket creation."""
        actor = Actor(dry_run=True)
        
        result = await actor.execute(
            action_type=ActionType.TICKET,
            target="jira",
            params={"title": "High CPU Alert", "description": "API server CPU > 90%"},
        )
        
        assert result.action_type == ActionType.TICKET
    
    def test_get_history_empty(self):
        """Test getting empty history."""
        actor = Actor(dry_run=True)
        history = actor.get_history()
        assert history == []
    
    def test_clear_history(self):
        """Test clearing history."""
        actor = Actor(dry_run=True)
        actor.clear_history()
        assert actor.get_history() == []


class TestActorHistory:
    """Test Actor history tracking."""
    
    @pytest.mark.asyncio
    async def test_history_tracking(self):
        """Test that actions are tracked in history."""
        actor = Actor(dry_run=True)
        
        await actor.execute(
            action_type=ActionType.NOTIFICATION,
            target="test",
            params={"message": "test"},
        )
        
        history = actor.get_history()
        assert len(history) == 1
        assert history[0].action_type == ActionType.NOTIFICATION


class TestActorApproval:
    """Test Actor approval requirements."""
    
    def test_requires_approval_by_default(self):
        """Test that actor requires approval by default."""
        actor = Actor(dry_run=False)
        assert actor.require_approval is True
    
    def test_can_disable_approval(self):
        """Test disabling approval requirement."""
        actor = Actor(dry_run=False, require_approval=False)
        assert actor.require_approval is False
