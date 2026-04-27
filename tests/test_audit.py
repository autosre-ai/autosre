"""
Tests for the audit logging module.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone

from autosre.security.audit import (
    AuditLogger,
    AuditEntry,
    EventType,
)


@pytest.fixture
def audit_logger(temp_dir):
    """Create an audit logger with temp directory."""
    log_dir = os.path.join(temp_dir, "audit")
    return AuditLogger(log_dir=log_dir)


class TestEventType:
    """Test EventType enum."""
    
    def test_auth_events(self):
        """Test authentication event types."""
        assert EventType.AUTH_SUCCESS.value == "auth.success"
        assert EventType.AUTH_FAILURE.value == "auth.failure"
        assert EventType.AUTH_REVOKE.value == "auth.revoke"
    
    def test_investigation_events(self):
        """Test investigation event types."""
        assert EventType.INVESTIGATION_START.value == "investigation.start"
        assert EventType.INVESTIGATION_COMPLETE.value == "investigation.complete"
    
    def test_action_events(self):
        """Test action event types."""
        assert EventType.ACTION_PROPOSED.value == "action.proposed"
        assert EventType.ACTION_APPROVED.value == "action.approved"
        assert EventType.ACTION_REJECTED.value == "action.rejected"
        assert EventType.ACTION_EXECUTED.value == "action.executed"


class TestAuditEntry:
    """Test AuditEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating audit entry."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="action.approved",
            user="admin@example.com",
            action="Approved pod restart",
            result="success",
            details={"pod": "api-server-xyz"},
        )
        
        assert entry.event_type == "action.approved"
        assert entry.user == "admin@example.com"
        assert entry.result == "success"
    
    def test_entry_to_dict(self):
        """Test converting entry to dict."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="auth.success",
            user="user@example.com",
            action="Login",
            result="success",
            details={},
        )
        
        d = entry.to_dict()
        
        assert d["event_type"] == "auth.success"
        assert d["user"] == "user@example.com"
        assert d["details"] == {}
    
    def test_entry_to_json(self):
        """Test converting entry to JSON."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:00:00Z",
            event_type="config.change",
            user="system",
            action="Updated config",
            result="success",
            details={"key": "timeout", "value": 30},
        )
        
        j = entry.to_json()
        data = json.loads(j)
        
        assert data["event_type"] == "config.change"
        assert data["details"]["key"] == "timeout"


class TestAuditLogger:
    """Test AuditLogger class."""
    
    def test_create_logger(self, temp_dir):
        """Test creating logger creates directory."""
        log_dir = os.path.join(temp_dir, "new_audit")
        logger = AuditLogger(log_dir=log_dir)
        
        assert Path(log_dir).exists()
    
    def test_log_creates_file(self, audit_logger):
        """Test logging creates log file."""
        audit_logger.log(
            EventType.AUTH_SUCCESS,
            user="user@example.com",
            action="Login successful",
        )
        
        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        assert len(log_files) == 1
    
    def test_log_writes_json(self, audit_logger):
        """Test log entries are valid JSON."""
        audit_logger.log(
            EventType.ACTION_APPROVED,
            user="admin",
            action="Approved restart",
            details={"pod": "web-server"},
        )
        
        log_file = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))[0]
        with open(log_file) as f:
            content = f.read()
        
        entry = json.loads(content.strip())
        assert entry["event_type"] == "action.approved"
        assert entry["details"]["pod"] == "web-server"
    
    def test_log_with_string_event_type(self, audit_logger):
        """Test logging with string event type."""
        entry = audit_logger.log(
            "custom.event",
            user="system",
            action="Custom action",
        )
        
        assert entry.event_type == "custom.event"
    
    def test_log_with_source_ip(self, audit_logger):
        """Test logging with source IP."""
        entry = audit_logger.log(
            EventType.AUTH_SUCCESS,
            user="user",
            action="Login",
            source_ip="192.168.1.100",
        )
        
        assert entry.source_ip == "192.168.1.100"
    
    def test_log_with_session_id(self, audit_logger):
        """Test logging with session ID."""
        entry = audit_logger.log(
            EventType.AUTH_SUCCESS,
            user="user",
            action="Login",
            session_id="sess-abc123",
        )
        
        assert entry.session_id == "sess-abc123"


class TestAuditLoggerConvenienceMethods:
    """Test convenience methods."""
    
    def test_log_investigation(self, audit_logger):
        """Test investigation logging."""
        entry = audit_logger.log_investigation(
            user="oncall@example.com",
            issue="High CPU on api-gateway",
            namespace="production",
        )
        
        assert entry.event_type == EventType.INVESTIGATION_START.value
        assert "investigation" in entry.action.lower()
    
    def test_log_investigation_complete(self, audit_logger):
        """Test investigation completion logging."""
        entry = audit_logger.log_investigation_complete(
            user="oncall@example.com",
            investigation_id="inv-123",
            root_cause="Config change causing CPU spike",
            actions_count=3,
        )
        
        assert entry.event_type == EventType.INVESTIGATION_COMPLETE.value
        assert entry.details["actions_proposed"] == 3
    
    def test_log_action_proposed(self, audit_logger):
        """Test action proposed logging."""
        entry = audit_logger.log_action_proposed(
            user="system",
            action_id="act-456",
            command="kubectl rollout restart deployment/api",
            risk="medium",
        )
        
        assert entry.event_type == EventType.ACTION_PROPOSED.value
        assert entry.details["risk_level"] == "medium"
    
    def test_log_action_approved(self, audit_logger):
        """Test action approved logging."""
        entry = audit_logger.log_action_approved(
            user="system",
            action_id="act-456",
            command="kubectl rollout restart",
            approved_by="admin@example.com",
        )
        
        assert entry.event_type == EventType.ACTION_APPROVED.value
        assert entry.details["approved_by"] == "admin@example.com"


class TestAuditLogRotation:
    """Test log rotation behavior."""
    
    def test_log_path_includes_date(self, audit_logger):
        """Test log path includes today's date."""
        log_path = audit_logger._get_log_path()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        assert today in str(log_path)
        assert log_path.suffix == ".jsonl"
