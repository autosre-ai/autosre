"""Tests for On-Call Load Tracker and Alert Quality Validator."""

import pytest
from datetime import datetime, timedelta, timezone

from autosre.oncall.load import (
    OnCallLoadTracker,
    ShiftIncident,
    ShiftStatus,
    LoadStatus,
    MAX_INCIDENTS_PER_SHIFT,
    SHIFT_HOURS,
)
from autosre.alerts.quality import (
    AlertQualityValidator,
    AlertPayload,
    AlertQualityResult,
    AlertSeverity,
    REQUIRED_ALERT_FIELDS,
    validate_alert,
)


class TestAlertQualityValidator:
    """Tests for AlertQualityValidator."""
    
    def test_validate_complete_alert(self):
        """Test validation of a complete, high-quality alert."""
        alert = AlertPayload(
            name="HighErrorRate",
            failure_mode="Error rate increased to 15% on checkout service",
            user_impact="Users cannot complete purchases, ~500 orders/hour affected",
            action_required="Check deployment logs, consider rollback of recent deploy",
            severity="critical",
            runbook_url="https://runbooks.example.com/checkout-errors",
        )
        
        validator = AlertQualityValidator()
        result = validator.validate(alert)
        
        assert result.is_valid
        assert result.quality_score > 0.8
        assert result.should_page
        assert len(result.missing_fields) == 0
    
    def test_validate_missing_required_fields(self):
        """Test that missing fields are detected."""
        alert = AlertPayload(
            name="VagueAlert",
            failure_mode="Something is wrong",
            # Missing: user_impact, action_required, severity, runbook_url
        )
        
        validator = AlertQualityValidator()
        result = validator.validate(alert)
        
        assert not result.should_page  # Missing too many fields
        assert "user_impact" in result.missing_fields
        assert "action_required" in result.missing_fields
        assert "severity" in result.missing_fields
        assert "runbook_url" in result.missing_fields
    
    def test_strict_mode_rejects_any_missing(self):
        """Test strict mode rejects alerts missing any required field."""
        alert = AlertPayload(
            name="AlmostComplete",
            failure_mode="Database connection pool exhausted",
            user_impact="API responses degraded",
            action_required="Scale database connections",
            severity="high",
            # Missing: runbook_url
        )
        
        validator = AlertQualityValidator(strict_mode=True)
        result = validator.validate(alert)
        
        assert not result.is_valid
        assert "runbook_url" in result.missing_fields
    
    def test_4_of_5_fields_can_page(self):
        """Test that 4/5 high-quality fields is sufficient to page."""
        alert = AlertPayload(
            name="MostlyComplete",
            failure_mode="Memory leak detected in worker pods causing OOMKilled",
            user_impact="Users experiencing 2x latency degradation on checkout",
            action_required="Restart affected pods immediately",
            severity="high",
            # Missing: runbook_url
        )
        
        # Lower quality threshold to allow 4/5 fields with good content
        validator = AlertQualityValidator(strict_mode=False, min_quality_score=0.5)
        result = validator.validate(alert)
        
        assert result.should_page
        assert len(result.missing_fields) == 1
    
    def test_3_of_5_fields_cannot_page(self):
        """Test that 3/5 fields is insufficient to page."""
        alert = AlertPayload(
            name="IncompleteAlert",
            failure_mode="Service unhealthy",
            severity="high",
            runbook_url="https://runbooks.example.com/generic",
            # Missing: user_impact, action_required
        )
        
        validator = AlertQualityValidator()
        result = validator.validate(alert)
        
        assert not result.should_page
    
    def test_quality_score_calculation(self):
        """Test quality score is calculated correctly."""
        # Perfect alert
        perfect = AlertPayload(
            name="PerfectAlert",
            failure_mode="Timeout errors increased to 50%",
            user_impact="Users experiencing slow page loads",
            action_required="Check upstream service health",
            severity="high",
            runbook_url="https://runbooks.example.com/timeouts",
        )
        
        validator = AlertQualityValidator()
        result = validator.validate(perfect)
        
        assert result.quality_score >= 0.8
        
        # Empty alert
        empty = AlertPayload(name="EmptyAlert")
        empty_result = validator.validate(empty)
        
        assert empty_result.quality_score == 0.0
    
    def test_validate_from_dict(self):
        """Test validation from dictionary input."""
        alert_dict = {
            "name": "DictAlert",
            "failure_mode": "Disk usage exceeded 90%",
            "user_impact": "Writes will fail if disk fills",
            "action_required": "Expand disk or clean up",
            "severity": "medium",
            "runbook_url": "https://runbooks.example.com/disk",
        }
        
        result = validate_alert(alert_dict)
        
        assert result.is_valid
        assert result.should_page
    
    def test_critical_requires_runbook(self):
        """Test critical alerts require runbook URL."""
        alert = AlertPayload(
            name="CriticalNoRunbook",
            failure_mode="Complete service outage",
            user_impact="All users affected",
            action_required="Investigate immediately",
            severity="critical",
            # Missing: runbook_url
        )
        
        validator = AlertQualityValidator(require_runbook_for_critical=True)
        result = validator.validate(alert)
        
        assert not result.should_page
        assert any("runbook" in w.lower() for w in result.warnings)
    
    def test_suggestions_generated(self):
        """Test that suggestions are generated for missing fields."""
        alert = AlertPayload(name="MissingFields")
        
        validator = AlertQualityValidator()
        result = validator.validate(alert)
        
        assert len(result.suggestions) > 0
        # Should have suggestion for each missing field
        assert len(result.suggestions) == len(result.missing_fields)
    
    def test_reject_reason(self):
        """Test rejection reason is human-readable."""
        alert = AlertPayload(name="BadAlert")
        
        validator = AlertQualityValidator()
        result = validator.validate(alert)
        reason = validator.reject_reason(result)
        
        assert reason is not None
        assert "Missing required fields" in reason


class TestOnCallLoadTracker:
    """Tests for OnCallLoadTracker."""
    
    def test_start_shift(self):
        """Test starting a new on-call shift."""
        tracker = OnCallLoadTracker()
        shift = tracker.start_shift("alice@example.com")
        
        assert shift.on_call_user == "alice@example.com"
        assert shift.incident_count == 0
        assert shift.load_status == LoadStatus.NORMAL
        assert shift.remaining_capacity == MAX_INCIDENTS_PER_SHIFT
        assert shift.hours_remaining > 0
    
    def test_record_incident(self):
        """Test recording an incident."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("bob@example.com")
        
        shift, should_escalate = tracker.record_incident(
            user="bob@example.com",
            incident_id="INC001",
            title="Database connection failure",
            severity="high",
        )
        
        assert shift.incident_count == 1
        assert not should_escalate  # First incident, not overloaded
        assert shift.load_status == LoadStatus.ELEVATED  # At warning threshold
    
    def test_overload_after_max_incidents(self):
        """Test overload status after max incidents."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("charlie@example.com")
        
        # Record MAX_INCIDENTS_PER_SHIFT incidents
        for i in range(MAX_INCIDENTS_PER_SHIFT):
            shift, should_escalate = tracker.record_incident(
                user="charlie@example.com",
                incident_id=f"INC{i:03d}",
                title=f"Incident {i}",
                severity="high",
            )
        
        assert shift.is_overloaded
        assert should_escalate
        assert shift.load_status == LoadStatus.OVERLOADED
        assert shift.remaining_capacity == 0
        assert shift.escalation_suggested
    
    def test_escalation_suggestion(self):
        """Test escalation suggestions when overloaded."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("dave@example.com")
        
        # Overload the shift
        for i in range(MAX_INCIDENTS_PER_SHIFT):
            tracker.record_incident(
                user="dave@example.com",
                incident_id=f"INC{i:03d}",
                title=f"Incident {i}",
                severity="high",
            )
        
        suggestion = tracker.suggest_escalation("dave@example.com")
        
        assert suggestion is not None
        assert suggestion["should_escalate"]
        assert len(suggestion["suggested_actions"]) > 0
    
    def test_resolve_incident(self):
        """Test resolving an incident."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("eve@example.com")
        
        tracker.record_incident(
            user="eve@example.com",
            incident_id="INC001",
            title="Test incident",
            severity="medium",
        )
        
        shift = tracker.resolve_incident(
            user="eve@example.com",
            incident_id="INC001",
            notes="Root cause: config error. Fixed by updating config.",
        )
        
        assert shift is not None
        incident = shift.incidents[0]
        assert incident.resolved_at is not None
        assert incident.notes == "Root cause: config error. Fixed by updating config."
    
    def test_check_capacity(self):
        """Test capacity checking."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("frank@example.com")
        
        # Initial capacity
        capacity = tracker.check_capacity("frank@example.com")
        assert capacity["has_capacity"]
        assert capacity["remaining"] == MAX_INCIDENTS_PER_SHIFT
        
        # Fill capacity
        for i in range(MAX_INCIDENTS_PER_SHIFT):
            tracker.record_incident(
                user="frank@example.com",
                incident_id=f"INC{i:03d}",
                title=f"Incident {i}",
                severity="medium",
            )
        
        # Check again
        capacity = tracker.check_capacity("frank@example.com")
        assert not capacity["has_capacity"]
        assert capacity["remaining"] == 0
        assert capacity["escalation_suggested"]
    
    def test_shift_summary(self):
        """Test shift summary generation."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("grace@example.com")
        
        # Add and resolve an incident
        tracker.record_incident(
            user="grace@example.com",
            incident_id="INC001",
            title="Test incident",
            severity="high",
        )
        
        tracker.resolve_incident(
            user="grace@example.com",
            incident_id="INC001",
            notes="Fixed",
        )
        
        summary = tracker.get_shift_summary("grace@example.com")
        
        assert summary is not None
        assert summary["total_incidents"] == 1
        assert summary["resolved_incidents"] == 1
        assert summary["active_incidents"] == 0
    
    def test_shift_expiration(self):
        """Test that expired shifts are cleaned up."""
        tracker = OnCallLoadTracker()
        
        # Start shift in the past
        past_time = datetime.now(timezone.utc) - timedelta(hours=SHIFT_HOURS + 1)
        tracker.start_shift("henry@example.com", start_time=past_time)
        
        # Shift should be expired
        shift = tracker.get_shift("henry@example.com")
        assert shift is None
    
    def test_no_shift_user(self):
        """Test handling of users without active shifts."""
        tracker = OnCallLoadTracker()
        
        # No shift started
        capacity = tracker.check_capacity("nonexistent@example.com")
        assert capacity["has_capacity"]
        assert capacity["reason"] == "No active shift"
    
    def test_export_shift(self):
        """Test shift export to JSON."""
        tracker = OnCallLoadTracker()
        tracker.start_shift("iris@example.com")
        
        tracker.record_incident(
            user="iris@example.com",
            incident_id="INC001",
            title="Export test",
            severity="low",
        )
        
        json_export = tracker.export_shift("iris@example.com")
        
        assert json_export is not None
        assert "INC001" in json_export
        assert "iris@example.com" in json_export


class TestLoadTrackerIntegration:
    """Integration tests for load tracking."""
    
    def test_full_shift_lifecycle(self):
        """Test a complete shift lifecycle."""
        tracker = OnCallLoadTracker()
        
        # Start shift
        shift = tracker.start_shift("john@example.com")
        assert shift.load_status == LoadStatus.NORMAL
        
        # First incident - elevated
        shift, _ = tracker.record_incident(
            user="john@example.com",
            incident_id="INC001",
            title="Incident 1",
            severity="high",
        )
        assert shift.load_status == LoadStatus.ELEVATED
        
        # Resolve it
        tracker.resolve_incident("john@example.com", "INC001", "Fixed")
        
        # Second incident - overloaded
        shift, should_escalate = tracker.record_incident(
            user="john@example.com",
            incident_id="INC002",
            title="Incident 2",
            severity="critical",
        )
        assert shift.load_status == LoadStatus.OVERLOADED
        assert should_escalate
        
        # Check summary
        summary = tracker.get_shift_summary("john@example.com")
        assert summary["total_incidents"] == 2
        assert summary["resolved_incidents"] == 1
        assert summary["active_incidents"] == 1
