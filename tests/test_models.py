"""Tests for core data models."""

import pytest
from datetime import datetime
from uuid import uuid4

from autosre.core.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Investigation,
    InvestigationStatus,
    Observation,
    ObservationType,
    Hypothesis,
    HypothesisStatus,
    Action,
    ActionType,
    ActionStatus,
    Report,
)


class TestAlert:
    """Test Alert model."""
    
    def test_create_alert(self):
        """Test basic alert creation."""
        alert = Alert(
            name="High CPU Usage",
            source="prometheus",
            severity=AlertSeverity.HIGH,
            service="api-server",
        )
        
        assert alert.name == "High CPU Usage"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING
        assert alert.is_active is True
    
    def test_alert_context_string(self):
        """Test alert context formatting."""
        alert = Alert(
            name="Memory Alert",
            source="datadog",
            description="Memory usage above 90%",
            service="worker",
        )
        
        context = alert.to_context_string()
        assert "Memory Alert" in context
        assert "datadog" in context
        assert "worker" in context
    
    def test_alert_duration(self):
        """Test duration calculation."""
        alert = Alert(
            name="Test",
            source="test",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            ended_at=datetime(2024, 1, 1, 12, 5, 0),
        )
        
        assert alert.duration_seconds == 300.0


class TestInvestigation:
    """Test Investigation model."""
    
    def test_create_investigation(self):
        """Test basic investigation creation."""
        alert_id = uuid4()
        investigation = Investigation(
            alert_id=alert_id,
            title="Investigating high latency",
        )
        
        assert investigation.alert_id == alert_id
        assert investigation.status == InvestigationStatus.PENDING
        assert len(investigation.observations) == 0
    
    def test_add_observation(self):
        """Test adding observations."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Test",
        )
        
        obs = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="CPU at 95%",
            data={"value": 95},
        )
        
        investigation.add_observation(obs)
        assert len(investigation.observations) == 1
    
    def test_hypothesis_management(self):
        """Test hypothesis tracking."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Test",
        )
        
        h1 = Hypothesis(
            statement="Database connection pool exhausted",
            status=HypothesisStatus.INVESTIGATING,
        )
        h2 = Hypothesis(
            statement="Memory leak in service",
            status=HypothesisStatus.CONFIRMED,
        )
        
        investigation.add_hypothesis(h1)
        investigation.add_hypothesis(h2)
        
        assert len(investigation.get_active_hypotheses()) == 1
        assert len(investigation.get_confirmed_hypotheses()) == 1


class TestHypothesis:
    """Test Hypothesis model."""
    
    def test_evidence_tracking(self):
        """Test evidence tracking and confidence."""
        h = Hypothesis(statement="Test hypothesis")
        
        # Add supporting evidence
        obs1 = uuid4()
        obs2 = uuid4()
        h.add_supporting_evidence(obs1)
        h.add_supporting_evidence(obs2)
        
        assert len(h.supporting_observations) == 2
        assert h.confidence == 1.0  # All evidence supports
        
        # Add contradicting evidence
        obs3 = uuid4()
        h.add_contradicting_evidence(obs3)
        
        assert h.confidence == pytest.approx(0.666, rel=0.01)


class TestAction:
    """Test Action model."""
    
    def test_action_context_string(self):
        """Test action formatting."""
        action = Action(
            type=ActionType.RESTART,
            name="Restart API pods",
            description="Rolling restart of api-server pods",
            is_destructive=True,
            requires_approval=True,
        )
        
        context = action.to_context_string()
        assert "Restart API pods" in context
        assert "DESTRUCTIVE" in context
        assert "REQUIRES APPROVAL" in context


class TestReport:
    """Test Report model."""
    
    def test_markdown_generation(self):
        """Test markdown report generation."""
        report = Report(
            investigation_id=uuid4(),
            title="Incident Report: API Outage",
            executive_summary="Brief outage due to database connection issues",
            root_cause="Connection pool exhaustion",
            root_cause_confidence=0.85,
            recommendations=["Increase pool size", "Add monitoring"],
        )
        
        md = report.to_markdown()
        assert "# Incident Report: API Outage" in md
        assert "Connection pool exhaustion" in md
        assert "85%" in md
        assert "Increase pool size" in md
