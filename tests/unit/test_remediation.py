"""Tests for the RemediationManager."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from pathlib import Path

from opensre_core.remediation.manager import (
    RemediationManager,
    ActionStatus,
    QueuedAction,
)
from opensre_core.agents.act import Action, ActionRisk


@pytest.fixture(autouse=True)
def isolated_audit_dir(tmp_path, monkeypatch):
    """Ensure each test uses an isolated audit directory."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    monkeypatch.setenv("OPENSRE_AUDIT_DIR", str(audit_dir))
    # Reset the global audit logger
    import opensre_core.security.audit as audit_module
    audit_module._audit_logger = None
    yield audit_dir
    audit_module._audit_logger = None


@pytest.fixture
def manager(tmp_path):
    """Create a fresh RemediationManager for each test."""
    return RemediationManager(
        auto_approve_low_risk=False,  # Disable auto-approve for predictable tests
        approval_timeout_minutes=1,
        persist_path=tmp_path / "remediation_history.jsonl",
    )


@pytest.fixture
def low_risk_action():
    """Create a low-risk action."""
    return Action(
        id="action_1",
        description="Get pod status",
        command="kubectl get pods -n default",
        risk=ActionRisk.LOW,
        requires_approval=False,
    )


@pytest.fixture
def medium_risk_action():
    """Create a medium-risk action."""
    return Action(
        id="action_2",
        description="Scale deployment",
        command="kubectl scale deployment/web --replicas=3 -n default",
        risk=ActionRisk.MEDIUM,
        requires_approval=True,
    )


@pytest.fixture
def high_risk_action():
    """Create a high-risk action."""
    return Action(
        id="action_3",
        description="Delete pods",
        command="kubectl delete pod web-abc123 -n production",
        risk=ActionRisk.HIGH,
        requires_approval=True,
    )


@pytest.fixture
def rollback_action():
    """Create an action that can be rolled back."""
    return Action(
        id="action_4",
        description="Restart deployment",
        command="kubectl rollout restart deployment/api -n default",
        risk=ActionRisk.MEDIUM,
        requires_approval=True,
    )


class TestQueueAction:
    """Test action queueing."""
    
    @pytest.mark.asyncio
    async def test_queue_action_creates_queued_action(self, manager, medium_risk_action):
        """Test that queueing an action creates a QueuedAction."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        assert queued.id is not None
        assert queued.action == medium_risk_action
        assert queued.investigation_id == "inv_123"
        assert queued.status == ActionStatus.PENDING
        assert queued.created_at is not None
    
    @pytest.mark.asyncio
    async def test_queue_action_auto_approve_low_risk(self, low_risk_action):
        """Test that low-risk actions are auto-approved when configured."""
        manager = RemediationManager(auto_approve_low_risk=True)
        
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "pods listed"
            queued = await manager.queue_action(low_risk_action, "inv_123")
        
        # Action should be in history (completed), not queue
        assert queued.id not in manager.queue
        assert queued in manager.history
        assert queued.status == ActionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_queue_action_generates_rollback(self, manager, rollback_action):
        """Test that rollback commands are generated for applicable actions."""
        queued = await manager.queue_action(rollback_action, "inv_123")
        
        assert queued.rollback_command is not None
        assert "rollout undo" in queued.rollback_command


class TestApproveAction:
    """Test action approval."""
    
    @pytest.mark.asyncio
    async def test_approve_pending_action(self, manager, medium_risk_action):
        """Test approving a pending action."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        approved = await manager.approve(queued.id, "admin@example.com")
        
        assert approved.status == ActionStatus.APPROVED
        assert approved.approved_by == "admin@example.com"
        assert approved.approved_at is not None
    
    @pytest.mark.asyncio
    async def test_approve_nonexistent_action(self, manager):
        """Test approving a nonexistent action raises error."""
        with pytest.raises(ValueError, match="not found"):
            await manager.approve("nonexistent_id", "admin")
    
    @pytest.mark.asyncio
    async def test_approve_already_approved_action(self, manager, medium_risk_action):
        """Test approving an already approved action raises error."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        await manager.approve(queued.id, "admin")
        
        with pytest.raises(ValueError, match="not pending"):
            await manager.approve(queued.id, "admin2")


class TestRejectAction:
    """Test action rejection."""
    
    @pytest.mark.asyncio
    async def test_reject_action(self, manager, high_risk_action):
        """Test rejecting an action."""
        queued = await manager.queue_action(high_risk_action, "inv_123")
        
        rejected = await manager.reject(queued.id, "sre@example.com", "Too risky during peak hours")
        
        assert rejected.status == ActionStatus.REJECTED
        assert "sre@example.com" in rejected.error
        assert "Too risky" in rejected.error
        
        # Should be in history, not queue
        assert queued.id not in manager.queue
        assert rejected in manager.history
    
    @pytest.mark.asyncio
    async def test_reject_nonexistent_action(self, manager):
        """Test rejecting a nonexistent action raises error."""
        with pytest.raises(ValueError, match="not found"):
            await manager.reject("nonexistent_id", "admin", "reason")


class TestExecuteAction:
    """Test action execution."""
    
    @pytest.mark.asyncio
    async def test_execute_approved_action(self, manager, medium_risk_action):
        """Test executing an approved action."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        await manager.approve(queued.id, "admin")
        
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "deployment scaled"
            executed = await manager.execute(queued.id)
        
        assert executed.status == ActionStatus.COMPLETED
        assert executed.result == "deployment scaled"
        assert executed.executed_at is not None
        assert executed.completed_at is not None
        
        # Should be in history
        assert executed in manager.history
    
    @pytest.mark.asyncio
    async def test_execute_unapproved_action(self, manager, medium_risk_action):
        """Test executing an unapproved action raises error."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        with pytest.raises(ValueError, match="not approved"):
            await manager.execute(queued.id)
    
    @pytest.mark.asyncio
    async def test_execute_action_failure(self, manager, medium_risk_action):
        """Test handling of execution failure."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        await manager.approve(queued.id, "admin")
        
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("Connection refused")
            executed = await manager.execute(queued.id)
        
        assert executed.status == ActionStatus.FAILED
        assert "Connection refused" in executed.error


class TestRollback:
    """Test action rollback."""
    
    @pytest.mark.asyncio
    async def test_rollback_action(self, manager, rollback_action):
        """Test rolling back a completed action."""
        queued = await manager.queue_action(rollback_action, "inv_123")
        await manager.approve(queued.id, "admin")
        
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "deployment restarted"
            await manager.execute(queued.id)
        
        # Now rollback
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "rollback successful"
            result = await manager.rollback(queued.id, "sre")
        
        assert result == "rollback successful"
        
        # Check action status updated
        action = manager.get_action(queued.id)
        assert action.status == ActionStatus.ROLLED_BACK
    
    @pytest.mark.asyncio
    async def test_rollback_action_without_rollback_command(self, manager, high_risk_action):
        """Test rolling back an action without rollback command returns None."""
        queued = await manager.queue_action(high_risk_action, "inv_123")
        await manager.approve(queued.id, "admin")
        
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "pod deleted"
            await manager.execute(queued.id)
        
        result = await manager.rollback(queued.id, "sre")
        assert result is None


class TestStats:
    """Test statistics tracking."""
    
    @pytest.mark.asyncio
    async def test_get_stats(self, manager, low_risk_action, medium_risk_action, high_risk_action):
        """Test getting statistics."""
        # Queue some actions
        q1 = await manager.queue_action(low_risk_action, "inv_1")
        q2 = await manager.queue_action(medium_risk_action, "inv_2")
        q3 = await manager.queue_action(high_risk_action, "inv_3")
        
        # Approve and execute q1
        await manager.approve(q1.id, "admin")
        with patch.object(manager, '_execute_command', new_callable=AsyncMock) as mock:
            mock.return_value = "done"
            await manager.execute(q1.id)
        
        # Reject q3
        await manager.reject(q3.id, "admin", "too risky")
        
        stats = manager.get_stats()
        
        assert stats["pending"] == 1  # q2 still pending
        assert stats["total_executed"] == 1
        assert stats["total_rejected"] == 1
    
    def test_get_pending(self, manager):
        """Test getting pending actions."""
        # Create manager with auto-approve disabled
        assert manager.get_pending() == []


class TestWaitForApproval:
    """Test waiting for approval with timeout."""
    
    @pytest.mark.asyncio
    async def test_wait_for_approval_approved(self, manager, medium_risk_action):
        """Test waiting for approval when action is approved."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        # Start waiting in background
        async def wait_and_approve():
            await asyncio.sleep(0.1)
            await manager.approve(queued.id, "admin")
        
        wait_task = asyncio.create_task(wait_and_approve())
        result = await manager.wait_for_approval(queued.id, timeout=5)
        
        assert result is True
        await wait_task
    
    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, manager, medium_risk_action):
        """Test waiting for approval times out."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        # Use a short but valid timeout
        result = await manager.wait_for_approval(queued.id, timeout=0.2)
        
        assert result is False
        # Action should be rejected due to timeout
        action = manager.get_action(queued.id)
        assert action.status == ActionStatus.REJECTED
        assert "timeout" in action.error.lower()


class TestActionSerialization:
    """Test QueuedAction serialization."""
    
    @pytest.mark.asyncio
    async def test_to_dict(self, manager, medium_risk_action):
        """Test converting QueuedAction to dictionary."""
        queued = await manager.queue_action(medium_risk_action, "inv_123")
        
        data = queued.to_dict()
        
        assert data["id"] == queued.id
        assert data["investigation_id"] == "inv_123"
        assert data["status"] == "pending"
        assert data["action"]["command"] == "kubectl scale deployment/web --replicas=3 -n default"
        assert data["action"]["risk"] == "medium"
        assert data["can_rollback"] is False  # Scale doesn't have simple rollback
