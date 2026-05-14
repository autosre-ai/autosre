"""Tests for human approval gate."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from autosre.core.approval_gate import (
    ApprovalConfig,
    ApprovalState,
    HumanApprovalGate,
    NotificationChannel,
    ProposedAction,
    get_approval_gate,
)
from autosre.core.confidence import ConfidenceLevel, ConfidenceScore


class TestProposedAction:
    """Tests for ProposedAction model."""
    
    def test_create_proposal(self):
        proposal = ProposedAction(
            action_type="restart",
            action_name="Restart payment-service",
            action_description="Restart all pods",
            target_type="deployment",
            target_name="payment-service",
            target_namespace="production",
        )
        
        assert proposal.id is not None
        assert proposal.state == ApprovalState.PENDING
        assert proposal.is_pending
        assert not proposal.is_decided
    
    def test_proposal_with_confidence(self):
        confidence = ConfidenceScore(
            score=85.0,
            reasoning="High CPU indicates service overload",
        )
        
        proposal = ProposedAction(
            action_type="restart",
            action_name="Restart API",
            action_description="Restart API pods",
            target_type="deployment",
            target_name="api",
            confidence=confidence,
        )
        
        assert proposal.confidence.score == 85.0
        assert proposal.confidence.level == ConfidenceLevel.HIGH
    
    def test_can_execute_states(self):
        proposal = ProposedAction(
            action_type="scale",
            action_name="Scale up",
            action_description="Scale up replicas",
            target_type="deployment",
            target_name="web",
        )
        
        # Pending - cannot execute
        assert not proposal.can_execute
        
        # Approved - can execute
        proposal.state = ApprovalState.APPROVED
        assert proposal.can_execute
        
        # Modified - can execute
        proposal.state = ApprovalState.MODIFIED
        assert proposal.can_execute
        
        # Rejected - cannot execute
        proposal.state = ApprovalState.REJECTED
        assert not proposal.can_execute
    
    def test_format_for_notification(self):
        confidence = ConfidenceScore(
            score=75.0,
            reasoning="Pattern matches historical incidents",
        )
        
        proposal = ProposedAction(
            action_type="restart",
            action_name="Restart service",
            action_description="Restart all pods in the deployment",
            target_type="deployment",
            target_name="payment-service",
            target_namespace="production",
            confidence=confidence,
            alert_name="HighCPU",
            risk_level="high",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        
        notification = proposal.format_for_notification()
        
        assert "ACTION REQUIRES APPROVAL" in notification
        assert "Restart service" in notification
        assert "75.0%" in notification
        assert "HighCPU" in notification
        assert "HIGH" in notification


class TestApprovalConfig:
    """Tests for ApprovalConfig."""
    
    def test_default_config(self):
        config = ApprovalConfig()
        
        assert config.initial_timeout_minutes == 30
        assert config.max_escalations == 3
        assert NotificationChannel.CLI in config.notification_channels
    
    def test_custom_config(self):
        config = ApprovalConfig(
            initial_timeout_minutes=60,
            notification_channels=[NotificationChannel.SLACK],
            slack_channel="#alerts",
        )
        
        assert config.initial_timeout_minutes == 60
        assert config.slack_channel == "#alerts"


class TestHumanApprovalGate:
    """Tests for HumanApprovalGate."""
    
    @pytest.fixture
    def gate(self, tmp_path) -> HumanApprovalGate:
        """Create approval gate with test config."""
        # We need to mock the audit trail to avoid database issues
        import autosre.core.audit as audit_module
        from autosre.core.audit import AuditTrail
        audit_module._audit_trail = AuditTrail(db_path=tmp_path / "audit.db")
        
        config = ApprovalConfig(
            initial_timeout_minutes=5,
            notification_channels=[NotificationChannel.CLI],
        )
        return HumanApprovalGate(config)
    
    @pytest.mark.asyncio
    async def test_propose_action(self, gate: HumanApprovalGate):
        proposal = await gate.propose_action(
            action_type="restart",
            action_name="Restart API",
            action_description="Restart API deployment",
            target_type="deployment",
            target_name="api",
            target_namespace="default",
        )
        
        assert proposal.id is not None
        assert proposal.state == ApprovalState.PENDING
        assert proposal.expires_at is not None
        
        pending = await gate.get_pending()
        assert len(pending) == 1
        assert pending[0].id == proposal.id
    
    @pytest.mark.asyncio
    async def test_approve_action(self, gate: HumanApprovalGate):
        proposal = await gate.propose_action(
            action_type="restart",
            action_name="Restart",
            action_description="Restart pods",
            target_type="pod",
            target_name="web-1",
        )
        
        success = await gate.approve(proposal.id, "test-user", "Looks good")
        
        assert success
        
        # Should no longer be pending
        pending = await gate.get_pending()
        assert len(pending) == 0
        
        # Should be in history
        history = await gate.get_history()
        assert len(history) == 1
        assert history[0].state == ApprovalState.APPROVED
        assert history[0].approved_by == "test-user"
    
    @pytest.mark.asyncio
    async def test_reject_action(self, gate: HumanApprovalGate):
        proposal = await gate.propose_action(
            action_type="scale",
            action_name="Scale down",
            action_description="Scale to 0 replicas",
            target_type="deployment",
            target_name="worker",
        )
        
        success = await gate.reject(
            proposal.id,
            "test-user",
            "Not safe during peak hours",
        )
        
        assert success
        
        history = await gate.get_history()
        assert len(history) == 1
        assert history[0].state == ApprovalState.REJECTED
        assert history[0].rejection_reason == "Not safe during peak hours"
    
    @pytest.mark.asyncio
    async def test_modify_and_approve(self, gate: HumanApprovalGate):
        proposal = await gate.propose_action(
            action_type="scale",
            action_name="Scale up",
            action_description="Scale to 10 replicas",
            target_type="deployment",
            target_name="web",
            parameters={"replicas": 10},
        )
        
        success = await gate.modify_and_approve(
            proposal.id,
            "test-user",
            modifications={"replicas": 5},
            notes="Reduced replica count",
        )
        
        assert success
        
        history = await gate.get_history()
        assert history[0].state == ApprovalState.MODIFIED
        assert history[0].parameters["replicas"] == 5
        assert history[0].original_parameters["replicas"] == 10
    
    @pytest.mark.asyncio
    async def test_approve_by_short_id(self, gate: HumanApprovalGate):
        proposal = await gate.propose_action(
            action_type="restart",
            action_name="Restart",
            action_description="Restart",
            target_type="pod",
            target_name="test",
        )
        
        short_id = str(proposal.id)[:8]
        success = await gate.approve(short_id, "user")
        
        assert success
    
    @pytest.mark.asyncio
    async def test_approve_nonexistent(self, gate: HumanApprovalGate):
        success = await gate.approve(uuid4(), "user")
        assert not success
    
    @pytest.mark.asyncio
    async def test_callbacks(self, gate: HumanApprovalGate):
        approved_proposals = []
        rejected_proposals = []
        
        async def on_approved(p):
            approved_proposals.append(p)
        
        async def on_rejected(p):
            rejected_proposals.append(p)
        
        gate.on_approved(on_approved)
        gate.on_rejected(on_rejected)
        
        p1 = await gate.propose_action(
            action_type="restart",
            action_name="Restart 1",
            action_description="...",
            target_type="pod",
            target_name="pod1",
        )
        await gate.approve(p1.id, "user")
        
        p2 = await gate.propose_action(
            action_type="restart",
            action_name="Restart 2",
            action_description="...",
            target_type="pod",
            target_name="pod2",
        )
        await gate.reject(p2.id, "user", "No")
        
        assert len(approved_proposals) == 1
        assert len(rejected_proposals) == 1
    
    @pytest.mark.asyncio
    async def test_notification_handler(self, gate: HumanApprovalGate):
        notifications = []
        
        async def mock_sender(id: str, msg: str, meta: dict) -> bool:
            notifications.append((id, msg, meta))
            return True
        
        gate.register_notifier(NotificationChannel.CLI, mock_sender)
        
        await gate.propose_action(
            action_type="restart",
            action_name="Test",
            action_description="Test action",
            target_type="pod",
            target_name="test-pod",
        )
        
        assert len(notifications) == 1
        assert "ACTION REQUIRES APPROVAL" in notifications[0][1]
    
    def test_get_stats(self, gate: HumanApprovalGate):
        stats = gate.get_stats()
        
        assert "pending" in stats
        assert "total_decisions" in stats
        assert "approval_rate" in stats


class TestNoAutoExecution:
    """Tests ensuring no auto-execution is ever possible."""
    
    @pytest.mark.asyncio
    async def test_high_confidence_still_needs_approval(self, tmp_path):
        """Even 100% confidence requires human approval."""
        import autosre.core.audit as audit_module
        from autosre.core.audit import AuditTrail
        audit_module._audit_trail = AuditTrail(db_path=tmp_path / "audit.db")
        
        gate = HumanApprovalGate()
        
        # Create proposal with very high confidence
        confidence = ConfidenceScore(
            score=100.0,
            reasoning="Perfect match",
        )
        
        proposal = await gate.propose_action(
            action_type="restart",
            action_name="Restart",
            action_description="Auto-matched restart",
            target_type="pod",
            target_name="test",
            confidence=confidence,
        )
        
        # Still pending - NOT auto-approved
        assert proposal.state == ApprovalState.PENDING
        assert not proposal.can_execute
        
        # Must be explicitly approved
        await gate.approve(proposal.id, "human")
        
        history = await gate.get_history()
        assert history[0].state == ApprovalState.APPROVED
        assert history[0].can_execute
