"""
Tests for the feedback tracking system.
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone

from autosre.feedback.tracker import (
    FeedbackTracker,
    Feedback,
    FeedbackType,
    IncidentOutcome,
    OutcomeType,
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def tracker():
    """Create a temporary feedback tracker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "feedback.db")
        yield FeedbackTracker(db_path=db_path)


class TestFeedbackModels:
    """Test feedback data models."""
    
    def test_feedback_creation(self):
        """Test creating feedback."""
        feedback = Feedback(
            id="fb-1",
            incident_id="inc-123",
            feedback_type=FeedbackType.THUMBS_UP,
            rating=5,
            comment="Great analysis!",
            submitted_by="user@example.com",
        )
        assert feedback.id == "fb-1"
        assert feedback.incident_id == "inc-123"
        assert feedback.feedback_type == FeedbackType.THUMBS_UP
        assert feedback.rating == 5
    
    def test_feedback_with_correction(self):
        """Test feedback with correction."""
        feedback = Feedback(
            id="fb-2",
            incident_id="inc-456",
            feedback_type=FeedbackType.CORRECTION,
            correction="Should have checked database first",
            agent_analysis="API latency issue",
            submitted_by="oncall@example.com",
        )
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.correction == "Should have checked database first"
    
    def test_outcome_creation(self):
        """Test creating incident outcome."""
        outcome = IncidentOutcome(
            incident_id="inc-789",
            outcome=OutcomeType.RESOLVED_BY_AGENT,
            root_cause_correct=True,
            runbook_helpful=True,
            action_effective=True,
            time_to_resolution_seconds=300.0,
            agent_time_saved_seconds=600.0,
            recorded_by="system",
        )
        assert outcome.incident_id == "inc-789"
        assert outcome.outcome == OutcomeType.RESOLVED_BY_AGENT
        assert outcome.root_cause_correct is True
        assert outcome.time_to_resolution_seconds == 300.0


class TestFeedbackTracker:
    """Test FeedbackTracker functionality."""
    
    def test_submit_and_get_feedback(self, tracker):
        """Test submitting and retrieving feedback."""
        feedback = Feedback(
            id="fb-test-1",
            incident_id="inc-test",
            feedback_type=FeedbackType.THUMBS_UP,
            rating=4,
            comment="Good work",
            submitted_by="tester",
        )
        
        tracker.submit_feedback(feedback)
        
        results = tracker.get_feedback("inc-test")
        assert len(results) == 1
        assert results[0].id == "fb-test-1"
        assert results[0].rating == 4
    
    def test_multiple_feedback_same_incident(self, tracker):
        """Test multiple feedback entries for same incident."""
        feedback1 = Feedback(
            id="fb-1",
            incident_id="inc-multi",
            feedback_type=FeedbackType.THUMBS_UP,
            submitted_by="user1",
        )
        feedback2 = Feedback(
            id="fb-2",
            incident_id="inc-multi",
            feedback_type=FeedbackType.COMMENT,
            comment="Could be faster",
            submitted_by="user2",
        )
        
        tracker.submit_feedback(feedback1)
        tracker.submit_feedback(feedback2)
        
        results = tracker.get_feedback("inc-multi")
        assert len(results) == 2
    
    def test_record_and_get_outcome(self, tracker):
        """Test recording and retrieving outcome."""
        outcome = IncidentOutcome(
            incident_id="inc-outcome",
            outcome=OutcomeType.AGENT_HELPED,
            root_cause_correct=True,
            time_to_resolution_seconds=180.0,
            agent_time_saved_seconds=120.0,
            recorded_by="system",
        )
        
        tracker.record_outcome(outcome)
        
        result = tracker.get_outcome("inc-outcome")
        assert result is not None
        assert result.outcome == OutcomeType.AGENT_HELPED
        assert result.root_cause_correct is True
        assert result.time_to_resolution_seconds == 180.0
    
    def test_get_nonexistent_outcome(self, tracker):
        """Test getting outcome for nonexistent incident."""
        result = tracker.get_outcome("nonexistent")
        assert result is None
    
    def test_outcome_update(self, tracker):
        """Test updating outcome."""
        outcome1 = IncidentOutcome(
            incident_id="inc-update",
            outcome=OutcomeType.ONGOING,
            recorded_by="system",
        )
        tracker.record_outcome(outcome1)
        
        outcome2 = IncidentOutcome(
            incident_id="inc-update",
            outcome=OutcomeType.RESOLVED_BY_HUMAN,
            root_cause_correct=False,
            human_override=True,
            recorded_by="oncall",
        )
        tracker.record_outcome(outcome2)
        
        result = tracker.get_outcome("inc-update")
        assert result.outcome == OutcomeType.RESOLVED_BY_HUMAN
        assert result.human_override is True


class TestFeedbackSummary:
    """Test feedback summary statistics."""
    
    def test_empty_summary(self, tracker):
        """Test summary with no data."""
        summary = tracker.get_summary()
        assert summary["feedback"]["total"] == 0
        assert summary["outcomes"]["total"] == 0
    
    def test_summary_with_data(self, tracker):
        """Test summary with actual data."""
        # Add some feedback
        tracker.submit_feedback(Feedback(
            id="fb-1",
            incident_id="inc-1",
            feedback_type=FeedbackType.THUMBS_UP,
            submitted_by="user",
        ))
        tracker.submit_feedback(Feedback(
            id="fb-2",
            incident_id="inc-2",
            feedback_type=FeedbackType.THUMBS_UP,
            submitted_by="user",
        ))
        tracker.submit_feedback(Feedback(
            id="fb-3",
            incident_id="inc-3",
            feedback_type=FeedbackType.THUMBS_DOWN,
            submitted_by="user",
        ))
        
        # Add some outcomes
        tracker.record_outcome(IncidentOutcome(
            incident_id="inc-1",
            outcome=OutcomeType.RESOLVED_BY_AGENT,
            root_cause_correct=True,
            agent_time_saved_seconds=300.0,
            recorded_by="system",
        ))
        tracker.record_outcome(IncidentOutcome(
            incident_id="inc-2",
            outcome=OutcomeType.AGENT_HELPED,
            root_cause_correct=True,
            agent_time_saved_seconds=120.0,
            recorded_by="system",
        ))
        
        summary = tracker.get_summary()
        
        assert summary["feedback"]["total"] == 3
        assert summary["feedback"]["thumbs_up"] == 2
        assert summary["feedback"]["thumbs_down"] == 1
        assert summary["feedback"]["approval_rate"] == pytest.approx(0.666, rel=0.01)
        
        assert summary["outcomes"]["total"] == 2
        assert summary["outcomes"]["root_cause_accuracy"] == 1.0
        assert summary["outcomes"]["agent_helpful_rate"] == 1.0
        assert summary["outcomes"]["avg_time_saved_seconds"] == 210.0
