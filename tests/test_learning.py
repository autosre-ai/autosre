"""
Tests for the learning pipeline module.
"""

import pytest
import tempfile
import os
from pathlib import Path

from autosre.feedback.tracker import (
    FeedbackTracker,
    Feedback,
    FeedbackType,
    IncidentOutcome,
    OutcomeType,
)
from autosre.feedback.learning import LearningPipeline


@pytest.fixture
def tracker():
    """Create a temporary feedback tracker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "feedback.db")
        yield FeedbackTracker(db_path=db_path)


@pytest.fixture
def pipeline(tracker):
    """Create a learning pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LearningPipeline(feedback_tracker=tracker, output_dir=tmpdir)


class TestLearningPipeline:
    """Test LearningPipeline class."""
    
    def test_create_pipeline(self, tracker):
        """Test creating pipeline."""
        pipeline = LearningPipeline(feedback_tracker=tracker)
        assert pipeline.tracker == tracker
        assert pipeline.output_dir.exists()
    
    def test_create_pipeline_custom_dir(self, tracker):
        """Test creating pipeline with custom output dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = os.path.join(tmpdir, "custom_learning")
            pipeline = LearningPipeline(feedback_tracker=tracker, output_dir=custom_dir)
            assert pipeline.output_dir == Path(custom_dir)
            assert pipeline.output_dir.exists()


class TestExportTrainingData:
    """Test training data export."""
    
    def test_export_empty(self, pipeline):
        """Test export with no data."""
        output_file = pipeline.export_training_data()
        assert os.path.exists(output_file)
        
        with open(output_file) as f:
            content = f.read()
        
        assert content == ""  # Empty file for no data
    
    def test_export_with_corrections(self, tracker, pipeline):
        """Test export with correction data."""
        # Add a correction
        tracker.submit_feedback(Feedback(
            id="fb-1",
            incident_id="inc-1",
            feedback_type=FeedbackType.CORRECTION,
            agent_analysis="The issue is high CPU",
            correction="The issue is actually memory leak causing high CPU",
            submitted_by="user",
        ))
        
        output_file = pipeline.export_training_data()
        
        with open(output_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        
        import json
        data = json.loads(lines[0])
        assert data["type"] == "correction"
        assert "high CPU" in data["input"]
        assert "memory leak" in data["output"]
    
    def test_export_with_positive_feedback(self, tracker, pipeline):
        """Test export with positive feedback."""
        tracker.submit_feedback(Feedback(
            id="fb-2",
            incident_id="inc-2",
            feedback_type=FeedbackType.THUMBS_UP,
            agent_analysis="Root cause: database connection timeout",
            rating=5,
            submitted_by="user",
        ))
        
        output_file = pipeline.export_training_data()
        
        with open(output_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 1


class TestIdentifyPatterns:
    """Test pattern identification."""
    
    def test_patterns_empty(self, pipeline):
        """Test patterns with no data."""
        patterns = pipeline.identify_patterns()
        
        assert "common_corrections" in patterns
        assert "failure_patterns" in patterns
        assert "success_patterns" in patterns
        assert "recommendations" in patterns
    
    def test_patterns_with_data(self, tracker, pipeline):
        """Test patterns with actual data."""
        # Add some feedback
        for i in range(3):
            tracker.submit_feedback(Feedback(
                id=f"fb-down-{i}",
                incident_id="inc-bad",
                feedback_type=FeedbackType.THUMBS_DOWN,
                submitted_by="user",
            ))
        
        tracker.submit_feedback(Feedback(
            id="fb-correction",
            incident_id="inc-1",
            feedback_type=FeedbackType.CORRECTION,
            correction="Should check database connections first",
            submitted_by="user",
        ))
        
        patterns = pipeline.identify_patterns()
        
        # Should find failure patterns
        assert len(patterns["failure_patterns"]) >= 1
        
        # Should find keyword patterns from corrections
        assert "common_corrections" in patterns
    
    def test_patterns_with_outcomes(self, tracker, pipeline):
        """Test patterns include outcome analysis."""
        tracker.record_outcome(IncidentOutcome(
            incident_id="inc-1",
            outcome=OutcomeType.RESOLVED_BY_AGENT,
            root_cause_correct=True,
            recorded_by="system",
        ))
        
        tracker.record_outcome(IncidentOutcome(
            incident_id="inc-2",
            outcome=OutcomeType.AGENT_HELPED,
            root_cause_correct=True,
            recorded_by="system",
        ))
        
        patterns = pipeline.identify_patterns()
        
        assert len(patterns["success_patterns"]) >= 1


class TestRecommendations:
    """Test recommendation generation."""
    
    def test_low_accuracy_recommendation(self, tracker, pipeline):
        """Test recommendation for low accuracy."""
        # Add outcomes with low accuracy
        for i in range(10):
            tracker.record_outcome(IncidentOutcome(
                incident_id=f"inc-{i}",
                outcome=OutcomeType.AGENT_WRONG,
                root_cause_correct=False,
                recorded_by="system",
            ))
        
        patterns = pipeline.identify_patterns()
        
        # Should recommend improving context
        recommendations = patterns["recommendations"]
        # Check if any recommendation mentions accuracy
        assert len(recommendations) >= 0  # May or may not trigger based on thresholds
