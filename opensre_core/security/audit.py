"""
Audit Logging Module - Track all security-relevant events
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading


class EventType(Enum):
    """Types of audit events."""
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_REVOKE = "auth.revoke"
    
    INVESTIGATION_START = "investigation.start"
    INVESTIGATION_COMPLETE = "investigation.complete"
    
    ACTION_PROPOSED = "action.proposed"
    ACTION_APPROVED = "action.approved"
    ACTION_REJECTED = "action.rejected"
    ACTION_EXECUTED = "action.executed"
    ACTION_FAILED = "action.failed"
    
    COMMAND_SANITIZE_FAIL = "command.sanitize_fail"
    PERMISSION_DENIED = "permission.denied"
    
    CONFIG_CHANGE = "config.change"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: str
    event_type: str
    user: str
    action: str
    result: str
    details: dict
    source_ip: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Enterprise-grade audit logger.
    
    Features:
    - JSON Lines format for easy parsing
    - Thread-safe writes
    - Automatic log rotation (by date)
    - Structured events
    """
    
    def __init__(self, log_dir: str = "logs/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def _get_log_path(self) -> Path:
        """Get log file path for today."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{date_str}.jsonl"
    
    def log(
        self,
        event_type: str | EventType,
        user: str,
        action: str,
        details: dict = None,
        result: str = "success",
        source_ip: str = None,
        session_id: str = None,
    ) -> AuditEntry:
        """
        Write an audit log entry.
        
        Args:
            event_type: Type of event (string or EventType enum)
            user: User who performed the action
            action: Description of the action
            details: Additional details dict
            result: "success", "failure", "rejected", etc.
            source_ip: Client IP address
            session_id: Session identifier
        
        Returns:
            The created audit entry
        """
        if isinstance(event_type, EventType):
            event_type = event_type.value
        
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            event_type=event_type,
            user=user,
            action=action,
            result=result,
            details=details or {},
            source_ip=source_ip,
            session_id=session_id,
        )
        
        with self._lock:
            log_path = self._get_log_path()
            with open(log_path, "a") as f:
                f.write(entry.to_json() + "\n")
        
        return entry
    
    # Convenience methods for common events
    
    def log_investigation(self, user: str, issue: str, namespace: str) -> AuditEntry:
        """Log investigation start."""
        return self.log(
            EventType.INVESTIGATION_START,
            user,
            f"Started investigation: {issue}",
            {"issue": issue, "namespace": namespace},
        )
    
    def log_investigation_complete(
        self,
        user: str,
        investigation_id: str,
        root_cause: str,
        actions_count: int,
    ) -> AuditEntry:
        """Log investigation completion."""
        return self.log(
            EventType.INVESTIGATION_COMPLETE,
            user,
            f"Completed investigation {investigation_id}",
            {
                "investigation_id": investigation_id,
                "root_cause": root_cause,
                "actions_proposed": actions_count,
            },
        )
    
    def log_action_proposed(
        self,
        user: str,
        action_id: str,
        command: str,
        risk: str,
    ) -> AuditEntry:
        """Log proposed action."""
        return self.log(
            EventType.ACTION_PROPOSED,
            user,
            f"Proposed action: {action_id}",
            {
                "action_id": action_id,
                "command": command,
                "risk_level": risk,
            },
        )
    
    def log_action_approved(
        self,
        user: str,
        action_id: str,
        command: str,
        approved_by: str,
    ) -> AuditEntry:
        """Log approved action."""
        return self.log(
            EventType.ACTION_APPROVED,
            user,
            f"Approved action: {action_id}",
            {
                "action_id": action_id,
                "command": command,
                "approved_by": approved_by,
            },
        )
    
    def log_action_executed(
        self,
        user: str,
        action_id: str,
        command: str,
        exit_code: int,
        approved_by: str,
    ) -> AuditEntry:
        """Log executed action."""
        result = "success" if exit_code == 0 else "failure"
        return self.log(
            EventType.ACTION_EXECUTED,
            user,
            f"Executed action: {action_id}",
            {
                "action_id": action_id,
                "command": command,
                "exit_code": exit_code,
                "approved_by": approved_by,
            },
            result=result,
        )
    
    def log_action_rejected(
        self,
        user: str,
        action_id: str,
        reason: str,
    ) -> AuditEntry:
        """Log rejected action."""
        return self.log(
            EventType.ACTION_REJECTED,
            user,
            f"Rejected action: {action_id}",
            {
                "action_id": action_id,
                "reason": reason,
            },
            result="rejected",
        )
    
    def log_sanitize_failure(
        self,
        user: str,
        command: str,
        reason: str,
    ) -> AuditEntry:
        """Log command sanitization failure."""
        return self.log(
            EventType.COMMAND_SANITIZE_FAIL,
            user,
            "Command blocked by sanitizer",
            {
                "command": command,
                "reason": reason,
            },
            result="blocked",
        )
    
    def log_permission_denied(
        self,
        user: str,
        action: str,
        required_permission: str,
    ) -> AuditEntry:
        """Log permission denied."""
        return self.log(
            EventType.PERMISSION_DENIED,
            user,
            f"Permission denied: {action}",
            {
                "required_permission": required_permission,
            },
            result="denied",
        )
    
    def query(
        self,
        start_date: str = None,
        end_date: str = None,
        event_type: str = None,
        user: str = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """
        Query audit logs.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            event_type: Filter by event type
            user: Filter by user
            limit: Maximum entries to return
        
        Returns:
            List of matching audit entries
        """
        entries = []
        
        # Find relevant log files
        for log_file in sorted(self.log_dir.glob("audit-*.jsonl"), reverse=True):
            if len(entries) >= limit:
                break
            
            # Check date range
            file_date = log_file.stem.replace("audit-", "")
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue
            
            # Read and filter entries
            with open(log_file) as f:
                for line in f:
                    if len(entries) >= limit:
                        break
                    
                    try:
                        data = json.loads(line)
                        
                        # Apply filters
                        if event_type and data.get("event_type") != event_type:
                            continue
                        if user and data.get("user") != user:
                            continue
                        
                        entries.append(AuditEntry(**data))
                    except json.JSONDecodeError:
                        continue
        
        return entries


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        log_dir = os.environ.get("OPENSRE_AUDIT_DIR", "logs/audit")
        _audit_logger = AuditLogger(log_dir)
    return _audit_logger


def audit_log(
    event_type: str | EventType,
    user: str,
    action: str,
    details: dict = None,
    result: str = "success",
    **kwargs,
) -> AuditEntry:
    """Convenience function to log an audit event."""
    logger = get_audit_logger()
    return logger.log(event_type, user, action, details, result, **kwargs)
