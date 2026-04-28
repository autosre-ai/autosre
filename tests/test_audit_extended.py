"""
Tests for the security/audit module - extended coverage.
"""

import json
import os
import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from autosre.security.audit import (
    EventType,
    AuditEntry,
    AuditLogger,
    get_audit_logger,
    audit_log,
)


class TestEventType:
    """Test EventType enum."""
    
    def test_auth_events(self):
        """Test auth event types exist."""
        assert EventType.AUTH_SUCCESS.value == "auth.success"
        assert EventType.AUTH_FAILURE.value == "auth.failure"
        assert EventType.AUTH_REVOKE.value == "auth.revoke"
    
    def test_investigation_events(self):
        """Test investigation event types exist."""
        assert EventType.INVESTIGATION_START.value == "investigation.start"
        assert EventType.INVESTIGATION_COMPLETE.value == "investigation.complete"
    
    def test_action_events(self):
        """Test action event types exist."""
        assert EventType.ACTION_PROPOSED.value == "action.proposed"
        assert EventType.ACTION_APPROVED.value == "action.approved"
        assert EventType.ACTION_REJECTED.value == "action.rejected"
        assert EventType.ACTION_EXECUTED.value == "action.executed"
        assert EventType.ACTION_FAILED.value == "action.failed"
    
    def test_security_events(self):
        """Test security event types exist."""
        assert EventType.COMMAND_SANITIZE_FAIL.value == "command.sanitize_fail"
        assert EventType.PERMISSION_DENIED.value == "permission.denied"


class TestAuditEntry:
    """Test AuditEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating an audit entry."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="auth.success",
            user="testuser",
            action="Login",
            result="success",
            details={"method": "api_key"},
        )
        assert entry.timestamp == "2024-01-15T10:00:00Z"
        assert entry.event_type == "auth.success"
        assert entry.user == "testuser"
    
    def test_entry_with_optional_fields(self):
        """Test entry with optional fields."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="action.executed",
            user="admin",
            action="Scale deployment",
            result="success",
            details={},
            source_ip="192.168.1.100",
            session_id="sess-12345",
        )
        assert entry.source_ip == "192.168.1.100"
        assert entry.session_id == "sess-12345"
    
    def test_to_dict(self):
        """Test converting entry to dict."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="test.event",
            user="user",
            action="test",
            result="success",
            details={"key": "value"},
        )
        d = entry.to_dict()
        assert d["timestamp"] == "2024-01-15T10:00:00Z"
        assert d["event_type"] == "test.event"
        assert d["details"]["key"] == "value"
    
    def test_to_json(self):
        """Test converting entry to JSON."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="test.event",
            user="user",
            action="test",
            result="success",
            details={},
        )
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        assert parsed["user"] == "user"


class TestAuditLoggerConvenienceMethods:
    """Test AuditLogger convenience methods."""
    
    @pytest.fixture
    def logger(self, tmp_path):
        """Create an AuditLogger with temp directory."""
        return AuditLogger(log_dir=str(tmp_path / "audit"))
    
    def test_log_investigation(self, logger):
        """Test log_investigation convenience method."""
        entry = logger.log_investigation(
            user="sre",
            issue="HighCPU alert",
            namespace="production",
        )
        assert entry.event_type == "investigation.start"
        assert "HighCPU" in entry.action
    
    def test_log_investigation_complete(self, logger):
        """Test log_investigation_complete method."""
        entry = logger.log_investigation_complete(
            user="sre",
            investigation_id="inv-123",
            root_cause="Memory leak",
            actions_count=3,
        )
        assert entry.event_type == "investigation.complete"
        assert entry.details["root_cause"] == "Memory leak"
    
    def test_log_action_proposed(self, logger):
        """Test log_action_proposed method."""
        entry = logger.log_action_proposed(
            user="sre",
            action_id="act-001",
            command="kubectl scale --replicas=5",
            risk="medium",
        )
        assert entry.event_type == "action.proposed"
        assert entry.details["risk_level"] == "medium"
    
    def test_log_action_approved(self, logger):
        """Test log_action_approved method."""
        entry = logger.log_action_approved(
            user="sre",
            action_id="act-001",
            command="kubectl scale",
            approved_by="manager",
        )
        assert entry.event_type == "action.approved"
        assert entry.details["approved_by"] == "manager"
    
    def test_log_action_executed_success(self, logger):
        """Test log_action_executed with success."""
        entry = logger.log_action_executed(
            user="sre",
            action_id="act-001",
            command="kubectl scale",
            exit_code=0,
            approved_by="manager",
        )
        assert entry.event_type == "action.executed"
        assert entry.result == "success"
    
    def test_log_action_executed_failure(self, logger):
        """Test log_action_executed with failure."""
        entry = logger.log_action_executed(
            user="sre",
            action_id="act-001",
            command="kubectl scale",
            exit_code=1,
            approved_by="manager",
        )
        assert entry.result == "failure"
    
    def test_log_action_rejected(self, logger):
        """Test log_action_rejected method."""
        entry = logger.log_action_rejected(
            user="sre",
            action_id="act-001",
            reason="Too risky",
        )
        assert entry.event_type == "action.rejected"
        assert entry.result == "rejected"
    
    def test_log_sanitize_failure(self, logger):
        """Test log_sanitize_failure method."""
        entry = logger.log_sanitize_failure(
            user="user",
            command="rm -rf /",
            reason="Dangerous command",
        )
        assert entry.event_type == "command.sanitize_fail"
        assert entry.result == "blocked"
    
    def test_log_permission_denied(self, logger):
        """Test log_permission_denied method."""
        entry = logger.log_permission_denied(
            user="viewer",
            action="Delete namespace",
            required_permission="admin",
        )
        assert entry.event_type == "permission.denied"
        assert entry.result == "denied"
