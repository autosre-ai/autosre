"""
Security Tests - Audit Logging
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from opensre_core.security.audit import (
    AuditLogger,
    AuditEntry,
    EventType,
    audit_log,
    get_audit_logger,
)


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""
    
    def test_to_dict(self):
        """Test entry serialization to dict."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:30:00Z",
            event_type="test.event",
            user="test_user",
            action="test action",
            result="success",
            details={"key": "value"},
        )
        
        d = entry.to_dict()
        
        assert d["timestamp"] == "2024-01-15T10:30:00Z"
        assert d["event_type"] == "test.event"
        assert d["user"] == "test_user"
        assert d["action"] == "test action"
        assert d["result"] == "success"
        assert d["details"] == {"key": "value"}
    
    def test_to_json(self):
        """Test entry serialization to JSON."""
        entry = AuditEntry(
            timestamp="2024-01-15T10:30:00Z",
            event_type="test.event",
            user="test_user",
            action="test action",
            result="success",
            details={},
        )
        
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["event_type"] == "test.event"
        assert parsed["user"] == "test_user"


class TestEventType:
    """Tests for EventType enum."""
    
    def test_event_type_values(self):
        """Test event type value format."""
        assert EventType.AUTH_SUCCESS.value == "auth.success"
        assert EventType.ACTION_EXECUTED.value == "action.executed"
        assert EventType.COMMAND_SANITIZE_FAIL.value == "command.sanitize_fail"


class TestAuditLogger:
    """Tests for AuditLogger."""
    
    def test_log_creates_file(self):
        """Test that logging creates audit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            logger.log(
                EventType.AUTH_SUCCESS,
                user="test_user",
                action="login",
            )
            
            # Check file was created
            log_files = list(Path(tmpdir).glob("audit-*.jsonl"))
            assert len(log_files) == 1
    
    def test_log_writes_json(self):
        """Test that logs are valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            logger.log(
                "test.event",
                user="test_user",
                action="test action",
                details={"foo": "bar"},
            )
            
            # Read and parse log
            log_file = list(Path(tmpdir).glob("audit-*.jsonl"))[0]
            with open(log_file) as f:
                line = f.readline()
                entry = json.loads(line)
            
            assert entry["event_type"] == "test.event"
            assert entry["user"] == "test_user"
            assert entry["action"] == "test action"
            assert entry["details"] == {"foo": "bar"}
    
    def test_log_multiple_entries(self):
        """Test logging multiple entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            for i in range(5):
                logger.log("test.event", user=f"user_{i}", action=f"action_{i}")
            
            # Read all entries
            log_file = list(Path(tmpdir).glob("audit-*.jsonl"))[0]
            with open(log_file) as f:
                lines = f.readlines()
            
            assert len(lines) == 5
    
    def test_log_investigation(self):
        """Test logging investigation start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            entry = logger.log_investigation(
                user="sre_user",
                issue="high CPU on payment-service",
                namespace="production",
            )
            
            assert entry.event_type == EventType.INVESTIGATION_START.value
            assert entry.user == "sre_user"
            assert "high CPU" in entry.action
    
    def test_log_action_executed(self):
        """Test logging action execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            entry = logger.log_action_executed(
                user="operator",
                action_id="action_1",
                command="kubectl scale deployment my-app --replicas=3",
                exit_code=0,
                approved_by="sre_lead",
            )
            
            assert entry.event_type == EventType.ACTION_EXECUTED.value
            assert entry.result == "success"
            assert entry.details["approved_by"] == "sre_lead"
    
    def test_log_action_rejected(self):
        """Test logging action rejection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            entry = logger.log_action_rejected(
                user="operator",
                action_id="action_2",
                reason="Too risky for current traffic levels",
            )
            
            assert entry.event_type == EventType.ACTION_REJECTED.value
            assert entry.result == "rejected"
            assert "Too risky" in entry.details["reason"]
    
    def test_log_sanitize_failure(self):
        """Test logging sanitization failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            entry = logger.log_sanitize_failure(
                user="attacker",
                command="kubectl get pods; rm -rf /",
                reason="Dangerous pattern detected",
            )
            
            assert entry.event_type == EventType.COMMAND_SANITIZE_FAIL.value
            assert entry.result == "blocked"
    
    def test_query_logs(self):
        """Test querying audit logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            # Create some entries
            logger.log("auth.success", user="user_a", action="login")
            logger.log("action.executed", user="user_b", action="execute")
            logger.log("auth.failure", user="user_a", action="failed login")
            
            # Query all
            entries = logger.query()
            assert len(entries) == 3
            
            # Query by user
            entries = logger.query(user="user_a")
            assert len(entries) == 2
            
            # Query by event type
            entries = logger.query(event_type="auth.success")
            assert len(entries) == 1
            assert entries[0].user == "user_a"
    
    def test_query_limit(self):
        """Test query limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            
            for i in range(20):
                logger.log("test.event", user="user", action=f"action_{i}")
            
            entries = logger.query(limit=5)
            assert len(entries) == 5


class TestAuditLogFunction:
    """Tests for audit_log convenience function."""
    
    def test_audit_log_function(self):
        """Test the audit_log convenience function."""
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set environment variable for audit dir
            old_env = os.environ.get("OPENSRE_AUDIT_DIR")
            try:
                os.environ["OPENSRE_AUDIT_DIR"] = tmpdir
                
                # Reset global logger
                import opensre_core.security.audit as audit_module
                audit_module._audit_logger = None
                
                entry = audit_log(
                    EventType.ACTION_APPROVED,
                    user="test_user",
                    action="approved action",
                    details={"action_id": "123"},
                )
                
                assert entry.event_type == EventType.ACTION_APPROVED.value
                assert entry.user == "test_user"
            finally:
                if old_env:
                    os.environ["OPENSRE_AUDIT_DIR"] = old_env
                else:
                    os.environ.pop("OPENSRE_AUDIT_DIR", None)
