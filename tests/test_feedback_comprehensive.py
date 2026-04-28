"""
Tests for AutoSRE feedback module.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from autosre.feedback import (
    FeedbackStore,
    Feedback,
    FeedbackTracker,
    IncidentOutcome,
    LearningPipeline,
)


class TestFeedbackModel:
    """Tests for Feedback model."""
    
    def test_create_feedback(self):
        """Test creating feedback."""
        feedback = Feedback(
            incident_id="INC-123",
            rating="correct"
        )
        
        assert feedback.incident_id == "INC-123"
        assert feedback.rating == "correct"
        assert feedback.actual_root_cause is None
    
    def test_feedback_with_all_fields(self):
        """Test feedback with all fields."""
        feedback = Feedback(
            incident_id="INC-456",
            rating="incorrect",
            actual_root_cause="DNS timeout",
            notes="Agent missed the network issue"
        )
        
        assert feedback.rating == "incorrect"
        assert feedback.actual_root_cause == "DNS timeout"
        assert "network" in feedback.notes
    
    def test_feedback_auto_timestamp(self):
        """Test feedback gets auto timestamp."""
        feedback = Feedback(
            incident_id="INC-789",
            rating="partial"
        )
        
        assert feedback.submitted_at is not None
        assert isinstance(feedback.submitted_at, datetime)
    
    def test_feedback_ratings(self):
        """Test valid feedback ratings."""
        for rating in ["correct", "incorrect", "partial"]:
            feedback = Feedback(
                incident_id="INC-001",
                rating=rating
            )
            assert feedback.rating == rating


class TestFeedbackStore:
    """Tests for FeedbackStore."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        # Cleanup
        Path(f.name).unlink(missing_ok=True)
    
    def test_create_store(self, temp_db):
        """Test creating feedback store."""
        store = FeedbackStore(db_path=temp_db)
        assert store.db_path == temp_db
    
    def test_store_default_path(self):
        """Test store with default path."""
        store = FeedbackStore()
        assert "feedback.db" in store.db_path
    
    def test_save_feedback(self, temp_db):
        """Test saving feedback."""
        store = FeedbackStore(db_path=temp_db)
        
        feedback = Feedback(
            incident_id="INC-123",
            rating="correct"
        )
        
        store.save(feedback)
        # Should not raise
    
    def test_save_and_list(self, temp_db):
        """Test saving and listing feedback."""
        store = FeedbackStore(db_path=temp_db)
        
        # Save some feedback
        for i in range(3):
            feedback = Feedback(
                incident_id=f"INC-{i}",
                rating="correct" if i % 2 == 0 else "incorrect"
            )
            store.save(feedback)
        
        # List them
        results = store.list_feedback(limit=10)
        assert len(results) == 3
    
    def test_list_with_limit(self, temp_db):
        """Test listing with limit."""
        store = FeedbackStore(db_path=temp_db)
        
        for i in range(5):
            feedback = Feedback(
                incident_id=f"INC-{i}",
                rating="correct"
            )
            store.save(feedback)
        
        results = store.list_feedback(limit=3)
        assert len(results) <= 3
    
    def test_list_with_rating_filter(self, temp_db):
        """Test listing with rating filter."""
        store = FeedbackStore(db_path=temp_db)
        
        # Save mixed feedback
        store.save(Feedback(incident_id="INC-1", rating="correct"))
        store.save(Feedback(incident_id="INC-2", rating="incorrect"))
        store.save(Feedback(incident_id="INC-3", rating="correct"))
        
        results = store.list_feedback(rating="correct")
        # Results are Feedback objects
        assert all(r.rating == "correct" for r in results)
    
    def test_get_stats(self, temp_db):
        """Test getting stats."""
        store = FeedbackStore(db_path=temp_db)
        
        # Save some feedback
        store.save(Feedback(incident_id="INC-1", rating="correct"))
        store.save(Feedback(incident_id="INC-2", rating="incorrect"))
        store.save(Feedback(incident_id="INC-3", rating="correct"))
        
        stats = store.get_stats()
        
        assert "total" in stats
        assert stats["total"] == 3


class TestFeedbackTracker:
    """Tests for FeedbackTracker."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)
    
    def test_create_tracker(self, temp_db):
        """Test creating tracker."""
        tracker = FeedbackTracker(db_path=temp_db)
        assert tracker is not None
    
    def test_tracker_default_path(self):
        """Test tracker with default path."""
        tracker = FeedbackTracker()
        assert tracker is not None


class TestIncidentOutcome:
    """Tests for IncidentOutcome model."""
    
    def test_create_outcome(self):
        """Test creating incident outcome."""
        from autosre.feedback.tracker import OutcomeType
        
        outcome = IncidentOutcome(
            incident_id="INC-123",
            outcome=OutcomeType.RESOLVED_BY_AGENT,
            root_cause_correct=True
        )
        
        assert outcome.incident_id == "INC-123"
        assert outcome.root_cause_correct is True
    
    def test_outcome_with_all_fields(self):
        """Test outcome with all fields."""
        from autosre.feedback.tracker import OutcomeType
        
        outcome = IncidentOutcome(
            incident_id="INC-456",
            outcome=OutcomeType.AGENT_HELPED,
            root_cause_correct=True,
            runbook_helpful=True,
            action_effective=False,
            time_to_resolution_seconds=1800.0,
            notes="Agent helped but action needed modification"
        )
        
        assert outcome.root_cause_correct is True
        assert outcome.time_to_resolution_seconds == 1800.0


class TestLearningPipeline:
    """Tests for LearningPipeline."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_create_pipeline(self, temp_dir):
        """Test creating pipeline."""
        db_path = f"{temp_dir}/learning.db"
        tracker = FeedbackTracker(db_path=db_path)
        pipeline = LearningPipeline(feedback_tracker=tracker)
        assert pipeline is not None
    
    def test_pipeline_with_output_dir(self, temp_dir):
        """Test pipeline with output directory."""
        db_path = f"{temp_dir}/learning.db"
        tracker = FeedbackTracker(db_path=db_path)
        pipeline = LearningPipeline(
            feedback_tracker=tracker,
            output_dir=temp_dir
        )
        assert pipeline is not None


class TestFeedbackIntegration:
    """Integration tests for feedback components."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)
    
    def test_full_feedback_flow(self, temp_db):
        """Test complete feedback flow."""
        store = FeedbackStore(db_path=temp_db)
        
        # Submit feedback
        feedback = Feedback(
            incident_id="INC-FLOW-1",
            rating="correct",
            notes="Agent correctly identified the issue"
        )
        store.save(feedback)
        
        # Retrieve and verify
        results = store.list_feedback()
        assert len(results) == 1
        assert results[0].incident_id == "INC-FLOW-1"
    
    def test_multiple_feedback_same_incident(self, temp_db):
        """Test multiple feedback for same incident."""
        store = FeedbackStore(db_path=temp_db)
        
        # First analysis - incorrect
        store.save(Feedback(
            incident_id="INC-MULTI",
            rating="incorrect",
            notes="First attempt missed root cause"
        ))
        
        # Second analysis - correct after learning
        store.save(Feedback(
            incident_id="INC-MULTI",
            rating="correct",
            notes="Agent learned and got it right"
        ))
        
        results = store.list_feedback()
        assert len(results) == 2
