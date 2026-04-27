"""
Tests for learning patterns and incident store.
"""

import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autosre.learning.store import IncidentStore, StoredIncident
from autosre.learning.patterns import PatternRecognizer, PatternMatch, RunbookSuggestion


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def incident_store():
    """Create a temporary incident store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_incidents.db"
        yield IncidentStore(str(db_path))


@pytest.fixture
def pattern_recognizer(incident_store):
    """Create a pattern recognizer with the test store."""
    return PatternRecognizer(incident_store)


class TestIncidentStore:
    """Tests for IncidentStore."""
    
    def test_save_and_get(self, incident_store):
        """Test saving and retrieving an incident."""
        incident = StoredIncident(
            id="inc-001",
            issue="High CPU on api-service",
            namespace="production",
            root_cause="Memory leak in connection pool",
            confidence=0.85,
            created_at=utcnow(),
        )
        
        incident_store.save(incident)
        result = incident_store.get("inc-001")
        
        assert result is not None
        assert result.id == "inc-001"
        assert result.root_cause == "Memory leak in connection pool"
        assert result.confidence == 0.85
    
    def test_get_not_found(self, incident_store):
        """Test getting nonexistent incident."""
        result = incident_store.get("nonexistent")
        assert result is None
    
    def test_find_similar(self, incident_store):
        """Test finding similar incidents."""
        # Add incidents with various issues
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="High CPU usage on api-gateway",
            namespace="prod",
            root_cause="CPU spike",
            confidence=0.8,
            created_at=utcnow() - timedelta(hours=1),
        ))
        incident_store.save(StoredIncident(
            id="inc-2",
            issue="Memory leak in payment-service",
            namespace="prod",
            root_cause="Memory leak",
            confidence=0.9,
            created_at=utcnow(),
        ))
        
        # Search for CPU related
        results = incident_store.find_similar("cpu high", limit=10)
        
        assert len(results) >= 1
        assert any("cpu" in r.issue.lower() for r in results)
    
    def test_find_similar_with_namespace(self, incident_store):
        """Test finding similar incidents filtered by namespace."""
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="High CPU",
            namespace="production",
            root_cause="CPU spike",
            confidence=0.8,
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="inc-2",
            issue="High CPU",
            namespace="staging",
            root_cause="CPU spike",
            confidence=0.8,
            created_at=utcnow(),
        ))
        
        prod_results = incident_store.find_similar("CPU", namespace="production")
        
        assert all(r.namespace == "production" for r in prod_results)
    
    def test_find_by_root_cause(self, incident_store):
        """Test finding by root cause pattern."""
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="OOM crash",
            namespace="prod",
            root_cause="Memory exhaustion",
            confidence=0.9,
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="inc-2",
            issue="Pod crash",
            namespace="prod",
            root_cause="Memory exhaustion",
            confidence=0.85,
            created_at=utcnow(),
        ))
        
        results = incident_store.find_by_root_cause("memory")
        
        assert len(results) == 2
    
    def test_find_by_namespace(self, incident_store):
        """Test finding incidents by namespace."""
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="Issue 1",
            namespace="payments",
            root_cause="Cause 1",
            confidence=0.9,
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="inc-2",
            issue="Issue 2",
            namespace="payments",
            root_cause="Cause 2",
            confidence=0.8,
            created_at=utcnow(),
        ))
        
        results = incident_store.find_by_namespace("payments")
        
        assert len(results) == 2
        assert all(r.namespace == "payments" for r in results)
    
    def test_find_recent(self, incident_store):
        """Test finding recent incidents."""
        for i in range(5):
            incident_store.save(StoredIncident(
                id=f"inc-{i}",
                issue=f"Issue {i}",
                namespace="prod",
                root_cause=f"Cause {i}",
                confidence=0.8,
                created_at=utcnow() - timedelta(hours=i),
            ))
        
        results = incident_store.find_recent(limit=3)
        
        assert len(results) == 3
        # Should be ordered by created_at DESC
        assert results[0].id == "inc-0"  # Most recent
    
    def test_update_outcome(self, incident_store):
        """Test updating incident outcome."""
        created = utcnow() - timedelta(minutes=30)
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="Test issue",
            namespace="prod",
            root_cause="Test cause",
            confidence=0.8,
            created_at=created,
        ))
        
        success = incident_store.update_outcome(
            "inc-1",
            outcome="resolved",
            feedback="Fixed by scaling",
        )
        
        assert success
        
        updated = incident_store.get("inc-1")
        assert updated.outcome == "resolved"
        assert updated.user_feedback == "Fixed by scaling"
        assert updated.resolution_time_minutes is not None
    
    def test_update_outcome_not_found(self, incident_store):
        """Test updating nonexistent incident."""
        success = incident_store.update_outcome("nonexistent", "resolved")
        assert success is False
    
    def test_record_action_executed(self, incident_store):
        """Test recording executed actions."""
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="Test",
            namespace="prod",
            root_cause="Test",
            confidence=0.8,
            created_at=utcnow(),
        ))
        
        incident_store.record_action_executed("inc-1", "kubectl rollout restart")
        incident_store.record_action_executed("inc-1", "kubectl scale --replicas=3")
        
        incident = incident_store.get("inc-1")
        assert len(incident.actions_executed) == 2
        assert "kubectl rollout restart" in incident.actions_executed
    
    def test_get_statistics(self, incident_store):
        """Test getting incident statistics."""
        # Add some incidents
        for i in range(3):
            incident_store.save(StoredIncident(
                id=f"resolved-{i}",
                issue=f"Issue {i}",
                namespace="prod",
                root_cause="Common cause",
                confidence=0.8,
                outcome="resolved",
                resolution_time_minutes=30,
                created_at=utcnow(),
            ))
        
        incident_store.save(StoredIncident(
            id="escalated-1",
            issue="Escalated issue",
            namespace="prod",
            root_cause="Rare cause",
            confidence=0.5,
            outcome="escalated",
            created_at=utcnow(),
        ))
        
        stats = incident_store.get_statistics()
        
        assert stats["total_incidents"] == 4
        assert stats["resolved"] == 3
        assert stats["escalated"] == 1
        assert stats["resolution_rate"] == 0.75
        assert len(stats["top_root_causes"]) > 0
    
    def test_get_statistics_by_namespace(self, incident_store):
        """Test statistics filtered by namespace."""
        incident_store.save(StoredIncident(
            id="inc-prod",
            issue="Prod issue",
            namespace="production",
            root_cause="Test",
            confidence=0.8,
            outcome="resolved",
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="inc-staging",
            issue="Staging issue",
            namespace="staging",
            root_cause="Test",
            confidence=0.8,
            created_at=utcnow(),
        ))
        
        stats = incident_store.get_statistics(namespace="production")
        
        assert stats["total_incidents"] == 1
        assert stats["resolved"] == 1


class TestPatternRecognizer:
    """Tests for PatternRecognizer."""
    
    def test_extract_signals(self, pattern_recognizer):
        """Test signal extraction from observations."""
        observations = [
            {"summary": "Pod is in CrashLoopBackOff state"},
            {"summary": "Memory usage at 95%"},
        ]
        
        signals = pattern_recognizer._extract_signals(observations)
        
        assert "crashloop" in signals
        assert "memory" in signals
    
    def test_extract_signals_multiple_patterns(self, pattern_recognizer):
        """Test extracting multiple signal patterns."""
        observations = [
            {"summary": "High CPU throttling detected"},
            {"summary": "Network timeouts to database"},
            {"summary": "Disk space running low"},
        ]
        
        signals = pattern_recognizer._extract_signals(observations)
        
        assert "cpu" in signals
        assert "network" in signals
        assert "disk" in signals
    
    def test_extract_signals_empty(self, pattern_recognizer):
        """Test signal extraction with empty observations."""
        signals = pattern_recognizer._extract_signals([])
        assert signals == []
    
    def test_find_matching_pattern(self, incident_store, pattern_recognizer):
        """Test finding matching patterns."""
        # Add similar incidents
        for i in range(5):
            incident_store.save(StoredIncident(
                id=f"oom-{i}",
                issue="Pod OOMKilled",
                namespace="production",
                root_cause="Memory exhaustion due to leak",
                confidence=0.9,
                outcome="resolved" if i < 4 else "escalated",
                resolution_time_minutes=15,
                actions_executed=["kubectl rollout restart deployment/api"],
                created_at=utcnow() - timedelta(days=i),
            ))
        
        observations = [
            {"summary": "Container was OOMKilled"},
            {"summary": "Memory usage spiking"},
        ]
        
        result = pattern_recognizer.find_matching_pattern(observations)
        
        assert result is not None
        assert result.similar_incidents > 0
        assert "memory" in result.likely_root_cause.lower() or result.pattern_confidence > 0
    
    def test_find_matching_pattern_no_match(self, pattern_recognizer):
        """Test when no patterns match."""
        observations = [
            {"summary": "Something unique happened"},
        ]
        
        result = pattern_recognizer.find_matching_pattern(observations)
        
        # Could be None if no signals extracted or no similar incidents
        # (expected behavior for unique issues)
        assert result is None or result.similar_incidents == 0
    
    def test_suggest_runbook(self, incident_store, pattern_recognizer):
        """Test runbook suggestions."""
        # Add resolved incidents with actions
        for i in range(3):
            incident_store.save(StoredIncident(
                id=f"fixed-{i}",
                issue="High latency",
                namespace="production",
                root_cause="Database connection pool exhausted",
                confidence=0.9,
                outcome="resolved",
                resolution_time_minutes=20,
                actions_executed=["kubectl scale deployment/api --replicas=5"],
                created_at=utcnow() - timedelta(hours=i),
            ))
        
        suggestion = pattern_recognizer.suggest_runbook("database connection")
        
        assert suggestion is not None
        assert len(suggestion.recommended_actions) > 0
        assert suggestion.success_count > 0
    
    def test_suggest_runbook_no_matches(self, pattern_recognizer):
        """Test suggestion when no similar incidents exist."""
        suggestion = pattern_recognizer.suggest_runbook("completely unique issue xyz")
        assert suggestion is None
    
    def test_get_common_root_causes(self, incident_store, pattern_recognizer):
        """Test getting common root causes."""
        # Add incidents with various root causes
        for i in range(5):
            incident_store.save(StoredIncident(
                id=f"inc-{i}",
                issue=f"Issue {i}",
                namespace="prod",
                root_cause="Memory leak" if i < 3 else "CPU spike",
                confidence=0.8,
                created_at=utcnow(),
            ))
        
        causes = pattern_recognizer.get_common_root_causes(limit=5)
        
        assert len(causes) > 0
    
    def test_predict_resolution_time(self, incident_store, pattern_recognizer):
        """Test resolution time prediction."""
        # Add resolved incidents
        incident_store.save(StoredIncident(
            id="inc-1",
            issue="Issue 1",
            namespace="prod",
            root_cause="Connection timeout",
            confidence=0.9,
            outcome="resolved",
            resolution_time_minutes=10,
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="inc-2",
            issue="Issue 2",
            namespace="prod",
            root_cause="Connection timeout",
            confidence=0.8,
            outcome="resolved",
            resolution_time_minutes=20,
            created_at=utcnow(),
        ))
        
        prediction = pattern_recognizer.predict_resolution_time("connection timeout")
        
        assert prediction is not None
        assert prediction == 15.0  # Average of 10 and 20
    
    def test_predict_resolution_time_no_data(self, pattern_recognizer):
        """Test prediction with no historical data."""
        prediction = pattern_recognizer.predict_resolution_time("unknown issue type")
        assert prediction is None
    
    def test_analyze_trends(self, incident_store, pattern_recognizer):
        """Test trend analysis."""
        # Add recent incidents
        for i in range(10):
            incident_store.save(StoredIncident(
                id=f"trend-{i}",
                issue=f"Issue {i}",
                namespace="production",
                root_cause="Common issue",
                confidence=0.8,
                outcome="resolved" if i < 8 else "escalated",
                resolution_time_minutes=30,
                created_at=utcnow() - timedelta(days=i),
            ))
        
        trends = pattern_recognizer.analyze_trends(days=30)
        
        assert trends["total_incidents"] == 10
        assert trends["incidents_per_day"] > 0
        assert trends["resolution_rate"] == 0.8
    
    def test_analyze_trends_by_namespace(self, incident_store, pattern_recognizer):
        """Test trends filtered by namespace."""
        incident_store.save(StoredIncident(
            id="prod-1",
            issue="Prod issue",
            namespace="production",
            root_cause="Test",
            confidence=0.8,
            outcome="resolved",
            created_at=utcnow(),
        ))
        incident_store.save(StoredIncident(
            id="staging-1",
            issue="Staging issue",
            namespace="staging",
            root_cause="Test",
            confidence=0.8,
            created_at=utcnow(),
        ))
        
        trends = pattern_recognizer.analyze_trends(namespace="production", days=7)
        
        assert trends["total_incidents"] == 1
    
    def test_analyze_trends_empty(self, pattern_recognizer):
        """Test trends with no data."""
        trends = pattern_recognizer.analyze_trends(days=30)
        
        assert trends["total_incidents"] == 0
        assert trends["incidents_per_day"] == 0


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""
    
    def test_pattern_match_creation(self):
        """Test creating a PatternMatch."""
        match = PatternMatch(
            likely_root_cause="Memory leak",
            pattern_confidence=0.85,
            similar_incidents=5,
            common_actions=[("kubectl restart", 3), ("scale up", 2)],
            avg_resolution_time=15.0,
            success_rate=0.8,
        )
        
        assert match.likely_root_cause == "Memory leak"
        assert match.pattern_confidence == 0.85
        assert len(match.common_actions) == 2


class TestRunbookSuggestion:
    """Tests for RunbookSuggestion dataclass."""
    
    def test_runbook_suggestion_creation(self):
        """Test creating a RunbookSuggestion."""
        suggestion = RunbookSuggestion(
            recommended_actions=["restart pod", "check logs", "scale up"],
            success_count=10,
            total_similar=12,
            avg_resolution_time=20.0,
        )
        
        assert len(suggestion.recommended_actions) == 3
        assert suggestion.success_count == 10
        assert suggestion.avg_resolution_time == 20.0
