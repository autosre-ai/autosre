"""Tests for approval workflow."""

import pytest
import asyncio
from datetime import datetime, timedelta
from autosre.guardrails import (
    ApprovalWorkflow,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus,
    ApprovalLevel,
    ApprovalStrategy,
    ApprovalPolicy,
    Approver,
    ApproverGroup,
)
from autosre.guardrails.approval import create_simple_workflow


class TestApprovalWorkflow:
    """Tests for ApprovalWorkflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a basic approval workflow."""
        policy = ApprovalPolicy(
            id="test-policy",
            name="Test Policy",
            timeout_minutes=60,
            strategy=ApprovalStrategy.ANY,
        )
        workflow = ApprovalWorkflow(policy=policy)
        
        # Register some approvers
        workflow.register_approver(Approver(
            id="approver1",
            name="Alice",
            email="alice@example.com",
            approval_level=ApprovalLevel.TEAM_LEAD,
        ))
        workflow.register_approver(Approver(
            id="approver2",
            name="Bob",
            email="bob@example.com",
            approval_level=ApprovalLevel.MANAGER,
        ))
        
        return workflow
    
    @pytest.mark.asyncio
    async def test_request_approval(self, workflow):
        """Test creating an approval request."""
        request = await workflow.request_approval(
            action="deploy",
            target="production-service",
            justification="Critical bug fix",
            requester_id="user123",
            requester_name="John Doe",
            risk_level="high",
            risk_score=0.7,
        )
        
        assert request.id.startswith("AR-")
        assert request.status == ApprovalStatus.PENDING
        assert request.action == "deploy"
        assert request.requester_id == "user123"
    
    @pytest.mark.asyncio
    async def test_approve_request(self, workflow):
        """Test approving a request."""
        request = await workflow.request_approval(
            action="deploy",
            target="production-service",
            justification="Bug fix",
            requester_id="user123",
            requester_name="John Doe",
        )
        
        success, message = await workflow.submit_decision(
            request_id=request.id,
            approver_id="approver1",
            decision=ApprovalStatus.APPROVED,
            comment="Looks good!",
        )
        
        assert success is True
        
        updated_request = workflow.get_request(request.id)
        assert updated_request.status == ApprovalStatus.APPROVED
    
    @pytest.mark.asyncio
    async def test_deny_request(self, workflow):
        """Test denying a request."""
        request = await workflow.request_approval(
            action="delete",
            target="critical-data",
            justification="Cleanup",
            requester_id="user123",
            requester_name="John Doe",
        )
        
        success, message = await workflow.submit_decision(
            request_id=request.id,
            approver_id="approver2",
            decision=ApprovalStatus.DENIED,
            comment="Too risky",
        )
        
        assert success is True
        
        updated_request = workflow.get_request(request.id)
        assert updated_request.status == ApprovalStatus.DENIED
    
    @pytest.mark.asyncio
    async def test_cancel_request(self, workflow):
        """Test cancelling a request."""
        request = await workflow.request_approval(
            action="deploy",
            target="service",
            justification="Test",
            requester_id="user123",
            requester_name="John Doe",
        )
        
        success, message = await workflow.cancel(
            request_id=request.id,
            canceller_id="user123",
        )
        
        assert success is True
        
        updated_request = workflow.get_request(request.id)
        assert updated_request.status == ApprovalStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_only_requester_can_cancel(self, workflow):
        """Test that only the requester can cancel."""
        request = await workflow.request_approval(
            action="deploy",
            target="service",
            justification="Test",
            requester_id="user123",
            requester_name="John Doe",
        )
        
        success, message = await workflow.cancel(
            request_id=request.id,
            canceller_id="other_user",
        )
        
        assert success is False
        assert "Only requester" in message
    
    @pytest.mark.asyncio
    async def test_escalate_request(self, workflow):
        """Test escalating a request."""
        request = await workflow.request_approval(
            action="deploy",
            target="service",
            justification="Test",
            requester_id="user123",
            requester_name="John Doe",
        )
        
        success, message = await workflow.escalate(
            request_id=request.id,
            reason="No response",
        )
        
        assert success is True
        
        updated_request = workflow.get_request(request.id)
        assert updated_request.escalation_count == 1
    
    @pytest.mark.asyncio
    async def test_get_pending_requests(self, workflow):
        """Test getting pending requests."""
        # Create multiple requests
        await workflow.request_approval(
            action="deploy",
            target="service1",
            justification="Test 1",
            requester_id="user1",
            requester_name="User 1",
        )
        await workflow.request_approval(
            action="deploy",
            target="service2",
            justification="Test 2",
            requester_id="user2",
            requester_name="User 2",
        )
        
        pending = workflow.get_pending_requests()
        assert len(pending) == 2
    
    def test_create_simple_workflow(self):
        """Test creating a simple workflow."""
        approvers = [
            {"id": "approver1", "name": "Alice", "email": "alice@example.com", "level": "team_lead"},
            {"id": "approver2", "name": "Bob", "email": "bob@example.com", "level": "manager"},
        ]
        
        workflow = create_simple_workflow(
            approvers=approvers,
            timeout_minutes=30,
        )
        
        assert workflow is not None
        assert len(workflow._approvers) == 2


class TestApprovalRequest:
    """Tests for ApprovalRequest data class."""
    
    def test_request_creation(self):
        """Test creating an approval request."""
        request = ApprovalRequest(
            id="AR-123",
            action="deploy",
            target="service",
            justification="Bug fix",
            risk_level="medium",
            risk_score=0.5,
            requester_id="user123",
            requester_name="John Doe",
        )
        
        assert request.id == "AR-123"
        assert request.status == ApprovalStatus.PENDING
    
    def test_add_approval_decision(self):
        """Test adding an approval decision."""
        request = ApprovalRequest(
            id="AR-123",
            action="deploy",
            target="service",
            justification="Bug fix",
            risk_level="medium",
            risk_score=0.5,
            requester_id="user123",
            requester_name="John Doe",
        )
        
        decision = ApprovalDecision(
            approver_id="approver1",
            approver_name="Alice",
            decision=ApprovalStatus.APPROVED,
        )
        
        request.add_decision(decision)
        
        assert request.status == ApprovalStatus.APPROVED
        assert len(request.decisions) == 1
    
    def test_denial_overrides_approvals(self):
        """Test that a denial overrides previous approvals."""
        request = ApprovalRequest(
            id="AR-123",
            action="deploy",
            target="service",
            justification="Bug fix",
            risk_level="medium",
            risk_score=0.5,
            requester_id="user123",
            requester_name="John Doe",
            strategy=ApprovalStrategy.ALL,
            quorum_size=2,
        )
        
        # Add approval
        request.add_decision(ApprovalDecision(
            approver_id="approver1",
            approver_name="Alice",
            decision=ApprovalStatus.APPROVED,
        ))
        
        # Add denial - should override
        request.add_decision(ApprovalDecision(
            approver_id="approver2",
            approver_name="Bob",
            decision=ApprovalStatus.DENIED,
        ))
        
        assert request.status == ApprovalStatus.DENIED
    
    def test_to_dict(self):
        """Test converting request to dictionary."""
        request = ApprovalRequest(
            id="AR-123",
            action="deploy",
            target="service",
            justification="Bug fix",
            risk_level="medium",
            risk_score=0.5,
            requester_id="user123",
            requester_name="John Doe",
        )
        
        data = request.to_dict()
        
        assert data["id"] == "AR-123"
        assert data["action"] == "deploy"
        assert data["status"] == "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
