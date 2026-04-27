"""
Tests for the guardrails module (safety checks and approval flows).
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta

from autosre.agent.guardrails import (
    Guardrails,
    ApprovalRequest,
    ApprovalStatus,
    RiskLevel,
    AuditEntry,
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def guardrails():
    """Create guardrails with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit.db")
        yield Guardrails(db_path=db_path)


class TestRiskLevelEnum:
    """Test RiskLevel enum."""
    
    def test_risk_levels(self):
        """Test risk level values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestApprovalStatusEnum:
    """Test ApprovalStatus enum."""
    
    def test_approval_statuses(self):
        """Test approval status values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.AUTO_APPROVED.value == "auto_approved"


class TestApprovalRequest:
    """Test ApprovalRequest model."""
    
    def test_create_request(self):
        """Test creating approval request."""
        request = ApprovalRequest(
            id="req-001",
            action_type="restart",
            target="api-server",
            description="Restart api-server pod",
            risk_level=RiskLevel.MEDIUM,
            blast_radius=1,
        )
        
        assert request.id == "req-001"
        assert request.action_type == "restart"
        assert request.risk_level == RiskLevel.MEDIUM
        assert request.status == ApprovalStatus.PENDING
    
    def test_request_defaults(self):
        """Test default values."""
        request = ApprovalRequest(
            id="req-002",
            action_type="scale",
            target="worker",
            description="Scale workers",
            risk_level=RiskLevel.LOW,
        )
        
        assert request.requester == "autosre-agent"
        assert request.reason == "Automated remediation"
        assert request.blast_radius == 0


class TestAuditEntry:
    """Test AuditEntry model."""
    
    def test_create_entry(self):
        """Test creating audit entry."""
        entry = AuditEntry(
            action_type="restart",
            target="api-server",
            actor="human@example.com",
            status="success",
            details={"restart_count": 1},
        )
        
        assert entry.action_type == "restart"
        assert entry.status == "success"
        assert entry.details["restart_count"] == 1


class TestRiskAssessment:
    """Test risk assessment functionality."""
    
    def test_notification_is_low_risk(self, guardrails):
        """Test notification actions are low risk."""
        risk, blast = guardrails.assess_risk("notification", "slack-channel")
        assert risk == RiskLevel.LOW
    
    def test_ticket_is_low_risk(self, guardrails):
        """Test ticket actions are low risk."""
        risk, blast = guardrails.assess_risk("ticket", "jira")
        assert risk == RiskLevel.LOW
    
    def test_restart_is_medium_risk(self, guardrails):
        """Test restart actions are medium risk."""
        risk, blast = guardrails.assess_risk("restart", "api-server")
        assert risk == RiskLevel.MEDIUM
    
    def test_rollback_is_high_risk(self, guardrails):
        """Test rollback actions are high risk."""
        risk, blast = guardrails.assess_risk("rollback", "api-server")
        assert risk == RiskLevel.HIGH
    
    def test_script_is_critical_risk(self, guardrails):
        """Test script execution is critical risk."""
        risk, blast = guardrails.assess_risk("script", "cleanup.sh")
        assert risk == RiskLevel.CRITICAL
    
    def test_tier1_increases_risk(self, guardrails):
        """Test tier 1 services have increased risk."""
        risk, blast = guardrails.assess_risk(
            "restart",
            "payment-service",
            params={"tier": 1}
        )
        assert risk == RiskLevel.HIGH
    
    def test_production_increases_risk(self, guardrails):
        """Test production namespace increases risk."""
        risk, blast = guardrails.assess_risk(
            "notification",
            "api-server",
            params={"namespace": "production"}
        )
        assert risk == RiskLevel.MEDIUM


class TestApprovalWorkflow:
    """Test approval workflow."""
    
    def test_auto_approve_low_risk(self, guardrails):
        """Test low risk actions are auto-approved."""
        request = guardrails.request_approval(
            action_type="notification",
            target="slack-channel",
            description="Send notification",
            risk_level=RiskLevel.LOW,
            blast_radius=0,
        )
        
        assert request.status == ApprovalStatus.AUTO_APPROVED
        assert request.approver == "auto"
    
    def test_medium_risk_pending(self, guardrails):
        """Test medium risk actions need approval."""
        request = guardrails.request_approval(
            action_type="restart",
            target="api-server",
            description="Restart pod",
            risk_level=RiskLevel.MEDIUM,
            blast_radius=1,
        )
        
        assert request.status == ApprovalStatus.PENDING
    
    def test_reject_high_blast_radius(self, guardrails):
        """Test high blast radius is rejected."""
        request = guardrails.request_approval(
            action_type="script",
            target="servers",
            description="Run script on all servers",
            risk_level=RiskLevel.HIGH,
            blast_radius=100,  # Way above limit
        )
        
        assert request.status == ApprovalStatus.REJECTED
        assert "exceeds limit" in request.approval_notes
    
    def test_disable_auto_approve(self):
        """Test disabling auto-approval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            guardrails = Guardrails(db_path=db_path, auto_approve_low_risk=False)
            
            request = guardrails.request_approval(
                action_type="notification",
                target="slack",
                description="Notify",
                risk_level=RiskLevel.LOW,
                blast_radius=0,
            )
            
            assert request.status == ApprovalStatus.PENDING


class TestApprovalActions:
    """Test approve/reject actions."""
    
    def test_approve_request(self, guardrails):
        """Test approving a request."""
        request = guardrails.request_approval(
            action_type="restart",
            target="api-server",
            description="Restart",
            risk_level=RiskLevel.MEDIUM,
            blast_radius=1,
        )
        
        result = guardrails.approve(
            request.id,
            approver="admin@example.com",
            notes="Approved after review",
        )
        
        assert result.status == ApprovalStatus.APPROVED
        assert result.approver == "admin@example.com"
        assert result.approval_notes == "Approved after review"
    
    def test_reject_request(self, guardrails):
        """Test rejecting a request."""
        request = guardrails.request_approval(
            action_type="rollback",
            target="api-server",
            description="Rollback",
            risk_level=RiskLevel.HIGH,
            blast_radius=3,
        )
        
        result = guardrails.reject(
            request.id,
            approver="security@example.com",
            notes="Need more investigation first",
        )
        
        assert result.status == ApprovalStatus.REJECTED
        assert "investigation" in result.approval_notes


class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_audit_action(self, guardrails):
        """Test logging an action."""
        guardrails.audit(
            action_type="restart",
            target="api-server",
            status="success",
        )
        
        # Should not raise
        assert True
    
    def test_get_audit_log(self, guardrails):
        """Test retrieving audit log."""
        guardrails.audit(
            action_type="restart",
            target="api-server",
            status="success",
        )
        guardrails.audit(
            action_type="scale",
            target="worker",
            status="success",
        )
        
        log = guardrails.get_audit_log(limit=10)
        
        assert len(log) >= 2


class TestGuardrailsConfig:
    """Test guardrails configuration."""
    
    def test_custom_max_blast_radius(self):
        """Test custom max blast radius."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit.db")
            guardrails = Guardrails(db_path=db_path, max_blast_radius=2)
            
            # This should be rejected (blast > 2)
            request = guardrails.request_approval(
                action_type="restart",
                target="all-pods",
                description="Restart all",
                risk_level=RiskLevel.MEDIUM,
                blast_radius=5,
            )
            
            assert request.status == ApprovalStatus.REJECTED
