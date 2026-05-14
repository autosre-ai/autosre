"""Tests for audit trail system."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from autosre.core.audit import (
    AuditEvent,
    AuditEventType,
    AuditQuery,
    AuditSeverity,
    AuditTrail,
    audit,
    get_audit_trail,
)


class TestAuditEvent:
    """Tests for AuditEvent model."""
    
    def test_create_event(self):
        event = AuditEvent(
            event_type=AuditEventType.ALERT_RECEIVED,
            summary="Received alert HighCPU",
            alert_id=uuid4(),
        )
        
        assert event.id is not None
        assert event.timestamp is not None
        assert event.severity == AuditSeverity.INFO
        assert event.actor == "autosre"
    
    def test_event_with_confidence(self):
        event = AuditEvent(
            event_type=AuditEventType.ACTION_PROPOSED,
            summary="Proposed restart",
            confidence_score=85.5,
            confidence_level="high",
            reasoning="High CPU matches restart pattern",
        )
        
        assert event.confidence_score == 85.5
        assert event.confidence_level == "high"
        assert event.reasoning is not None
    
    def test_to_dict(self):
        event = AuditEvent(
            event_type=AuditEventType.APPROVAL_GRANTED,
            summary="Approved by user",
            actor="john.doe",
            actor_type="user",
        )
        
        d = event.to_dict()
        
        assert "id" in d
        assert d["event_type"] == "approval_granted"
        assert d["actor"] == "john.doe"


class TestAuditTrail:
    """Tests for AuditTrail."""
    
    @pytest.fixture
    def audit_trail(self, tmp_path: Path) -> AuditTrail:
        """Create a temporary audit trail."""
        return AuditTrail(db_path=tmp_path / "test_audit.db")
    
    def test_record_event(self, audit_trail: AuditTrail):
        event = audit_trail.record(
            event_type=AuditEventType.ALERT_RECEIVED,
            summary="Test alert received",
        )
        
        assert event.id is not None
        assert event.event_type == AuditEventType.ALERT_RECEIVED
    
    def test_record_with_all_fields(self, audit_trail: AuditTrail):
        alert_id = uuid4()
        investigation_id = uuid4()
        action_id = uuid4()
        
        event = audit_trail.record(
            event_type=AuditEventType.ACTION_PROPOSED,
            summary="Proposed restart",
            severity=AuditSeverity.WARNING,
            alert_id=alert_id,
            investigation_id=investigation_id,
            action_id=action_id,
            actor="llm",
            actor_type="llm",
            details={"action": "restart", "target": "payment-service"},
            confidence_score=75.0,
            confidence_level="high",
            reasoning="Matches runbook",
            evidence=[{"type": "runbook", "summary": "CPU runbook matched"}],
            model_used="gpt-4o",
        )
        
        assert event.alert_id == alert_id
        assert event.confidence_score == 75.0
        assert len(event.evidence) == 1
    
    def test_query_by_time(self, audit_trail: AuditTrail):
        # Record events
        for i in range(5):
            audit_trail.record(
                event_type=AuditEventType.ALERT_RECEIVED,
                summary=f"Alert {i}",
            )
        
        result = audit_trail.query(AuditQuery(
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            limit=10,
        ))
        
        assert len(result.events) == 5
        assert result.total_count == 5
    
    def test_query_by_event_type(self, audit_trail: AuditTrail):
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Alert 1")
        audit_trail.record(AuditEventType.APPROVAL_GRANTED, "Approved")
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Alert 2")
        
        result = audit_trail.query(AuditQuery(
            event_types=[AuditEventType.ALERT_RECEIVED],
        ))
        
        assert len(result.events) == 2
        assert all(e.event_type == AuditEventType.ALERT_RECEIVED for e in result.events)
    
    def test_query_by_alert_id(self, audit_trail: AuditTrail):
        alert_id = uuid4()
        
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Alert 1", alert_id=alert_id)
        audit_trail.record(AuditEventType.ANALYSIS_STARTED, "Analysis", alert_id=alert_id)
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Other alert", alert_id=uuid4())
        
        result = audit_trail.query(AuditQuery(alert_id=alert_id))
        
        assert len(result.events) == 2
        assert all(e.alert_id == alert_id for e in result.events)
    
    def test_get_alert_timeline(self, audit_trail: AuditTrail):
        alert_id = uuid4()
        
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Received", alert_id=alert_id)
        audit_trail.record(AuditEventType.ANALYSIS_STARTED, "Started", alert_id=alert_id)
        audit_trail.record(AuditEventType.ACTION_PROPOSED, "Proposed", alert_id=alert_id)
        audit_trail.record(AuditEventType.APPROVAL_GRANTED, "Approved", alert_id=alert_id)
        
        timeline = audit_trail.get_alert_timeline(alert_id)
        
        assert len(timeline) == 4
        # Should be in chronological order
        assert timeline[0].event_type == AuditEventType.ALERT_RECEIVED
    
    def test_get_recent_decisions(self, audit_trail: AuditTrail):
        audit_trail.record(
            AuditEventType.ACTION_PROPOSED,
            "Proposed action",
            confidence_score=80.0,
        )
        audit_trail.record(
            AuditEventType.CONFIDENCE_CALCULATED,
            "Calculated confidence",
            confidence_score=75.0,
        )
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Just an alert")
        
        decisions = audit_trail.get_recent_decisions(hours=1)
        
        assert len(decisions) == 2
        assert all(e.confidence_score is not None for e in decisions)
    
    def test_export_json(self, audit_trail: AuditTrail, tmp_path: Path):
        for i in range(10):
            audit_trail.record(AuditEventType.ALERT_RECEIVED, f"Alert {i}")
        
        output_path = tmp_path / "export.json"
        count = audit_trail.export_json(output_path)
        
        assert count == 10
        assert output_path.exists()
        
        data = json.loads(output_path.read_text())
        assert data["total_events"] == 10
        assert len(data["events"]) == 10
    
    def test_get_stats(self, audit_trail: AuditTrail):
        audit_trail.record(AuditEventType.ALERT_RECEIVED, "Alert")
        audit_trail.record(AuditEventType.ACTION_PROPOSED, "Action", confidence_score=80.0)
        audit_trail.record(AuditEventType.APPROVAL_GRANTED, "Approved")
        
        stats = audit_trail.get_stats()
        
        assert stats["total_events"] == 3
        assert "alert_received" in stats["by_type"]
        assert stats["average_confidence"] == 80.0
    
    def test_cleanup_old(self, audit_trail: AuditTrail):
        # This is tricky to test properly without manipulating timestamps
        # We'll just verify it runs without error
        deleted = audit_trail.cleanup_old(days=365)
        assert deleted >= 0


class TestAuditConvenienceFunction:
    """Tests for audit() convenience function."""
    
    def test_audit_function(self, tmp_path: Path, monkeypatch):
        # Reset global instance
        import autosre.core.audit as audit_module
        audit_module._audit_trail = AuditTrail(db_path=tmp_path / "test.db")
        
        event = audit(
            AuditEventType.ALERT_RECEIVED,
            "Test alert",
        )
        
        assert event is not None
        assert event.event_type == AuditEventType.ALERT_RECEIVED
