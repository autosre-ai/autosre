"""
Audit Trail System for AutoSRE.

Comprehensive logging of all decisions:
- Alert → Analysis → Proposal → Approval → Execution
- Queryable audit log with full context
- Compliance and accountability tracking
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    
    # Alert lifecycle
    ALERT_RECEIVED = "alert_received"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"
    ALERT_ESCALATED = "alert_escalated"
    
    # Analysis
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    RUNBOOK_MATCHED = "runbook_matched"
    HYPOTHESIS_GENERATED = "hypothesis_generated"
    EVIDENCE_COLLECTED = "evidence_collected"
    
    # Proposal
    ACTION_PROPOSED = "action_proposed"
    CONFIDENCE_CALCULATED = "confidence_calculated"
    
    # Approval
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_ESCALATED = "approval_escalated"
    
    # Execution
    ACTION_STARTED = "action_started"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    ACTION_ROLLED_BACK = "action_rolled_back"
    
    # System
    SYSTEM_ERROR = "system_error"
    CONFIG_CHANGED = "config_changed"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """A single audit event."""
    
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Event type
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Context
    alert_id: UUID | None = None
    investigation_id: UUID | None = None
    action_id: UUID | None = None
    approval_id: UUID | None = None
    
    # Actor
    actor: str = "autosre"  # Who triggered this event
    actor_type: str = "system"  # system, user, llm
    
    # Details
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    
    # Confidence (for AI decisions)
    confidence_score: float | None = None
    confidence_level: str | None = None
    reasoning: str | None = None
    
    # Evidence
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    
    # Metadata
    model_used: str | None = None
    session_id: str | None = None
    correlation_id: UUID | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return self.model_dump(mode="json")


class AuditQuery(BaseModel):
    """Query parameters for audit log search."""
    
    # Time range
    start_time: datetime | None = None
    end_time: datetime | None = None
    
    # Filters
    event_types: list[AuditEventType] | None = None
    severities: list[AuditSeverity] | None = None
    alert_id: UUID | None = None
    investigation_id: UUID | None = None
    action_id: UUID | None = None
    actor: str | None = None
    
    # Search
    search_text: str | None = None
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Sorting
    order_by: str = "timestamp"
    order_desc: bool = True


class AuditResult(BaseModel):
    """Result of an audit query."""
    
    events: list[AuditEvent]
    total_count: int
    query: AuditQuery


class AuditTrail:
    """
    Audit trail manager with SQLite backend.
    
    Features:
    - Persistent storage of all events
    - Full-text search
    - Time-based queries
    - Correlation tracking
    - Export to JSON
    
    Example:
        >>> audit = AuditTrail()
        >>> 
        >>> # Record an event
        >>> audit.record(
        ...     event_type=AuditEventType.ACTION_PROPOSED,
        ...     alert_id=alert.id,
        ...     summary="Proposed restart of payment-service",
        ...     confidence_score=85.5,
        ...     reasoning="High CPU matches restart runbook",
        ... )
        >>> 
        >>> # Query events
        >>> result = audit.query(AuditQuery(
        ...     alert_id=alert.id,
        ...     event_types=[AuditEventType.ACTION_PROPOSED],
        ... ))
    """
    
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path.home() / ".autosre" / "audit.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    alert_id TEXT,
                    investigation_id TEXT,
                    action_id TEXT,
                    approval_id TEXT,
                    actor TEXT NOT NULL,
                    actor_type TEXT NOT NULL,
                    summary TEXT,
                    details TEXT,
                    confidence_score REAL,
                    confidence_level TEXT,
                    reasoning TEXT,
                    evidence TEXT,
                    model_used TEXT,
                    session_id TEXT,
                    correlation_id TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_alert_id ON audit_events(alert_id);
                CREATE INDEX IF NOT EXISTS idx_investigation_id ON audit_events(investigation_id);
                CREATE INDEX IF NOT EXISTS idx_action_id ON audit_events(action_id);
                CREATE INDEX IF NOT EXISTS idx_actor ON audit_events(actor);
                
                -- Full-text search
                CREATE VIRTUAL TABLE IF NOT EXISTS audit_fts USING fts5(
                    summary, reasoning, details_text,
                    content='audit_events',
                    content_rowid='rowid'
                );
                
                -- Triggers for FTS
                CREATE TRIGGER IF NOT EXISTS audit_fts_insert AFTER INSERT ON audit_events BEGIN
                    INSERT INTO audit_fts(rowid, summary, reasoning, details_text)
                    VALUES (NEW.rowid, NEW.summary, NEW.reasoning, NEW.details);
                END;
            """)
    
    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def record(
        self,
        event_type: AuditEventType,
        summary: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        alert_id: UUID | None = None,
        investigation_id: UUID | None = None,
        action_id: UUID | None = None,
        approval_id: UUID | None = None,
        actor: str = "autosre",
        actor_type: str = "system",
        details: dict[str, Any] | None = None,
        confidence_score: float | None = None,
        confidence_level: str | None = None,
        reasoning: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        model_used: str | None = None,
        session_id: str | None = None,
        correlation_id: UUID | None = None,
    ) -> AuditEvent:
        """
        Record an audit event.
        
        Args:
            event_type: Type of event
            summary: Brief description
            severity: Event severity
            alert_id: Associated alert
            investigation_id: Associated investigation
            action_id: Associated action
            approval_id: Associated approval
            actor: Who triggered this
            actor_type: Type of actor (system, user, llm)
            details: Additional details
            confidence_score: AI confidence (0-100)
            confidence_level: Confidence level name
            reasoning: AI reasoning
            evidence: Supporting evidence
            model_used: LLM model used
            session_id: Session identifier
            correlation_id: For event correlation
            
        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            alert_id=alert_id,
            investigation_id=investigation_id,
            action_id=action_id,
            approval_id=approval_id,
            actor=actor,
            actor_type=actor_type,
            summary=summary,
            details=details or {},
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            reasoning=reasoning,
            evidence=evidence or [],
            model_used=model_used,
            session_id=session_id,
            correlation_id=correlation_id,
        )
        
        self._store_event(event)
        
        logger.info(
            f"Audit: [{event_type.value}] {summary}",
            extra={
                "event_id": str(event.id),
                "confidence": confidence_score,
            }
        )
        
        return event
    
    def _store_event(self, event: AuditEvent) -> None:
        """Store event in database."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO audit_events (
                    id, timestamp, event_type, severity,
                    alert_id, investigation_id, action_id, approval_id,
                    actor, actor_type, summary, details,
                    confidence_score, confidence_level, reasoning, evidence,
                    model_used, session_id, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(event.id),
                event.timestamp.isoformat(),
                event.event_type.value,
                event.severity.value,
                str(event.alert_id) if event.alert_id else None,
                str(event.investigation_id) if event.investigation_id else None,
                str(event.action_id) if event.action_id else None,
                str(event.approval_id) if event.approval_id else None,
                event.actor,
                event.actor_type,
                event.summary,
                json.dumps(event.details),
                event.confidence_score,
                event.confidence_level,
                event.reasoning,
                json.dumps(event.evidence),
                event.model_used,
                event.session_id,
                str(event.correlation_id) if event.correlation_id else None,
            ))
    
    def query(self, query: AuditQuery) -> AuditResult:
        """
        Query audit events.
        
        Args:
            query: Query parameters
            
        Returns:
            Query result with matching events
        """
        conditions = []
        params: list[Any] = []
        
        if query.start_time:
            conditions.append("timestamp >= ?")
            params.append(query.start_time.isoformat())
        
        if query.end_time:
            conditions.append("timestamp <= ?")
            params.append(query.end_time.isoformat())
        
        if query.event_types:
            placeholders = ",".join("?" * len(query.event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(t.value for t in query.event_types)
        
        if query.severities:
            placeholders = ",".join("?" * len(query.severities))
            conditions.append(f"severity IN ({placeholders})")
            params.extend(s.value for s in query.severities)
        
        if query.alert_id:
            conditions.append("alert_id = ?")
            params.append(str(query.alert_id))
        
        if query.investigation_id:
            conditions.append("investigation_id = ?")
            params.append(str(query.investigation_id))
        
        if query.action_id:
            conditions.append("action_id = ?")
            params.append(str(query.action_id))
        
        if query.actor:
            conditions.append("actor = ?")
            params.append(query.actor)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Handle full-text search separately
        if query.search_text:
            # Join with FTS table
            sql = f"""
                SELECT a.* FROM audit_events a
                JOIN audit_fts ON a.rowid = audit_fts.rowid
                WHERE audit_fts MATCH ? AND {where_clause}
                ORDER BY a.{query.order_by} {'DESC' if query.order_desc else 'ASC'}
                LIMIT ? OFFSET ?
            """
            params = [query.search_text] + params + [query.limit, query.offset]
            count_sql = f"""
                SELECT COUNT(*) FROM audit_events a
                JOIN audit_fts ON a.rowid = audit_fts.rowid
                WHERE audit_fts MATCH ? AND {where_clause}
            """
            count_params = [query.search_text] + params[1:-2]
        else:
            sql = f"""
                SELECT * FROM audit_events
                WHERE {where_clause}
                ORDER BY {query.order_by} {'DESC' if query.order_desc else 'ASC'}
                LIMIT ? OFFSET ?
            """
            params += [query.limit, query.offset]
            count_sql = f"SELECT COUNT(*) FROM audit_events WHERE {where_clause}"
            count_params = params[:-2]
        
        with self._get_conn() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            cursor = conn.execute(count_sql, count_params)
            total_count = cursor.fetchone()[0]
        
        events = [self._row_to_event(row) for row in rows]
        
        return AuditResult(
            events=events,
            total_count=total_count,
            query=query,
        )
    
    def _row_to_event(self, row: sqlite3.Row) -> AuditEvent:
        """Convert database row to AuditEvent."""
        return AuditEvent(
            id=UUID(row["id"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=AuditEventType(row["event_type"]),
            severity=AuditSeverity(row["severity"]),
            alert_id=UUID(row["alert_id"]) if row["alert_id"] else None,
            investigation_id=UUID(row["investigation_id"]) if row["investigation_id"] else None,
            action_id=UUID(row["action_id"]) if row["action_id"] else None,
            approval_id=UUID(row["approval_id"]) if row["approval_id"] else None,
            actor=row["actor"],
            actor_type=row["actor_type"],
            summary=row["summary"],
            details=json.loads(row["details"]) if row["details"] else {},
            confidence_score=row["confidence_score"],
            confidence_level=row["confidence_level"],
            reasoning=row["reasoning"],
            evidence=json.loads(row["evidence"]) if row["evidence"] else [],
            model_used=row["model_used"],
            session_id=row["session_id"],
            correlation_id=UUID(row["correlation_id"]) if row["correlation_id"] else None,
        )
    
    def get_alert_timeline(self, alert_id: UUID) -> list[AuditEvent]:
        """Get complete timeline for an alert."""
        result = self.query(AuditQuery(
            alert_id=alert_id,
            order_desc=False,  # Chronological order
            limit=1000,
        ))
        return result.events
    
    def get_action_history(self, action_id: UUID) -> list[AuditEvent]:
        """Get complete history for an action."""
        result = self.query(AuditQuery(
            action_id=action_id,
            order_desc=False,
            limit=1000,
        ))
        return result.events
    
    def get_recent_decisions(
        self,
        hours: int = 24,
        include_evidence: bool = True,
    ) -> list[AuditEvent]:
        """Get recent AI decisions with confidence scores."""
        from datetime import timedelta
        
        result = self.query(AuditQuery(
            start_time=datetime.now(timezone.utc) - timedelta(hours=hours),
            event_types=[
                AuditEventType.ACTION_PROPOSED,
                AuditEventType.CONFIDENCE_CALCULATED,
            ],
            order_desc=True,
            limit=100,
        ))
        return result.events
    
    def get_approval_history(
        self,
        hours: int = 24,
        status: str | None = None,
    ) -> list[AuditEvent]:
        """Get approval history."""
        from datetime import timedelta
        
        event_types = [
            AuditEventType.APPROVAL_REQUESTED,
            AuditEventType.APPROVAL_GRANTED,
            AuditEventType.APPROVAL_DENIED,
            AuditEventType.APPROVAL_EXPIRED,
        ]
        
        result = self.query(AuditQuery(
            start_time=datetime.now(timezone.utc) - timedelta(hours=hours),
            event_types=event_types,
            order_desc=True,
            limit=200,
        ))
        return result.events
    
    def export_json(
        self,
        output_path: Path,
        query: AuditQuery | None = None,
    ) -> int:
        """
        Export audit events to JSON.
        
        Args:
            output_path: Path to output file
            query: Optional query to filter events
            
        Returns:
            Number of events exported
        """
        query = query or AuditQuery(limit=10000)
        result = self.query(query)
        
        output = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_events": result.total_count,
            "query": query.model_dump(mode="json"),
            "events": [e.to_dict() for e in result.events],
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, default=str))
        
        logger.info(f"Exported {len(result.events)} audit events to {output_path}")
        return len(result.events)
    
    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_events")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_events
                GROUP BY event_type
                ORDER BY count DESC
            """)
            by_type = {row["event_type"]: row["count"] for row in cursor.fetchall()}
            
            cursor = conn.execute("""
                SELECT severity, COUNT(*) as count
                FROM audit_events
                GROUP BY severity
            """)
            by_severity = {row["severity"]: row["count"] for row in cursor.fetchall()}
            
            cursor = conn.execute("""
                SELECT AVG(confidence_score) as avg_confidence
                FROM audit_events
                WHERE confidence_score IS NOT NULL
            """)
            avg_confidence = cursor.fetchone()["avg_confidence"]
            
            cursor = conn.execute("""
                SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
                FROM audit_events
            """)
            time_range = cursor.fetchone()
        
        return {
            "total_events": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "average_confidence": round(avg_confidence, 1) if avg_confidence else None,
            "oldest_event": time_range["oldest"],
            "newest_event": time_range["newest"],
            "db_path": str(self.db_path),
        }
    
    def cleanup_old(self, days: int = 90) -> int:
        """
        Remove audit events older than specified days.
        
        Args:
            days: Number of days to retain
            
        Returns:
            Number of deleted events
        """
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM audit_events WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            deleted = cursor.rowcount
        
        logger.info(f"Cleaned up {deleted} audit events older than {days} days")
        return deleted


# Singleton instance
_audit_trail: AuditTrail | None = None


def get_audit_trail(db_path: Path | None = None) -> AuditTrail:
    """Get or create the audit trail instance."""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = AuditTrail(db_path)
    return _audit_trail


# Convenience functions
def audit(
    event_type: AuditEventType,
    summary: str = "",
    **kwargs: Any,
) -> AuditEvent:
    """Quick audit event recording."""
    return get_audit_trail().record(event_type, summary, **kwargs)
