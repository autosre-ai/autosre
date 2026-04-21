"""Tests for incident learning module."""

import os
import tempfile
from datetime import datetime

import pytest

from opensre_core.learning.patterns import PatternRecognizer
from opensre_core.learning.store import IncidentStore, StoredIncident


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def store(temp_db):
    """Create a store with temp db."""
    return IncidentStore(temp_db)


@pytest.fixture
def sample_incidents():
    """Sample incidents for testing."""
    return [
        StoredIncident(
            id="inc1",
            issue="OOMKilled on payment-service",
            namespace="production",
            root_cause="memory leak in payment handler",
            confidence=0.9,
            observations=[{"source": "kubernetes", "summary": "Pod killed due to OOMKilled"}],
            actions=[{"command": "kubectl rollout restart deployment/payment"}],
            actions_executed=["kubectl rollout restart deployment/payment"],
            outcome="resolved",
            resolution_time_minutes=15,
            created_at=datetime.now(),
        ),
        StoredIncident(
            id="inc2",
            issue="memory exhausted on api-gateway",
            namespace="production",
            root_cause="memory leak in request handler",
            confidence=0.85,
            observations=[{"source": "prometheus", "summary": "Memory usage > 90%"}],
            actions=[{"command": "kubectl rollout restart deployment/api"}],
            actions_executed=["kubectl rollout restart deployment/api"],
            outcome="resolved",
            resolution_time_minutes=12,
            created_at=datetime.now(),
        ),
        StoredIncident(
            id="inc3",
            issue="high CPU on checkout service",
            namespace="staging",
            root_cause="runaway loop in checkout handler",
            confidence=0.75,
            observations=[{"source": "prometheus", "summary": "CPU throttling detected"}],
            actions=[{"command": "kubectl scale deployment/checkout"}],
            actions_executed=["kubectl scale deployment/checkout --replicas=3"],
            outcome="escalated",
            resolution_time_minutes=45,
            created_at=datetime.now(),
        ),
    ]


class TestIncidentStore:
    """Tests for IncidentStore."""

    def test_save_and_get(self, store):
        """Test saving and retrieving an incident."""
        incident = StoredIncident(
            id="test1",
            issue="test issue",
            namespace="default",
            root_cause="test cause",
            confidence=0.8,
            created_at=datetime.now(),
        )

        store.save(incident)
        retrieved = store.get("test1")

        assert retrieved is not None
        assert retrieved.id == "test1"
        assert retrieved.issue == "test issue"
        assert retrieved.root_cause == "test cause"

    def test_find_similar(self, store, sample_incidents):
        """Test finding similar incidents."""
        for inc in sample_incidents:
            store.save(inc)

        similar = store.find_similar("memory issue", "production")

        assert len(similar) >= 1
        assert any("memory" in inc.issue.lower() for inc in similar)

    def test_find_by_root_cause(self, store, sample_incidents):
        """Test finding by root cause."""
        for inc in sample_incidents:
            store.save(inc)

        results = store.find_by_root_cause("memory leak")

        assert len(results) == 2
        assert all("memory" in inc.root_cause.lower() for inc in results)

    def test_find_by_namespace(self, store, sample_incidents):
        """Test finding by namespace."""
        for inc in sample_incidents:
            store.save(inc)

        prod_incidents = store.find_by_namespace("production")
        staging_incidents = store.find_by_namespace("staging")

        assert len(prod_incidents) == 2
        assert len(staging_incidents) == 1

    def test_get_statistics(self, store, sample_incidents):
        """Test getting statistics."""
        for inc in sample_incidents:
            store.save(inc)

        stats = store.get_statistics()

        assert stats["total_incidents"] == 3
        assert stats["resolved"] == 2
        assert stats["escalated"] == 1
        assert stats["resolution_rate"] == 2/3

    def test_update_outcome(self, store):
        """Test updating incident outcome."""
        incident = StoredIncident(
            id="test2",
            issue="test",
            namespace="default",
            root_cause="test",
            confidence=0.5,
            created_at=datetime.now(),
        )
        store.save(incident)

        success = store.update_outcome("test2", "resolved", "Fixed it!")

        assert success
        updated = store.get("test2")
        assert updated.outcome == "resolved"
        assert updated.user_feedback == "Fixed it!"
        assert updated.resolved_at is not None

    def test_record_action_executed(self, store):
        """Test recording executed actions."""
        incident = StoredIncident(
            id="test3",
            issue="test",
            namespace="default",
            root_cause="test",
            confidence=0.5,
            actions_executed=[],
            created_at=datetime.now(),
        )
        store.save(incident)

        store.record_action_executed("test3", "kubectl rollout restart")
        store.record_action_executed("test3", "kubectl scale --replicas=3")

        updated = store.get("test3")
        assert len(updated.actions_executed) == 2
        assert "kubectl rollout restart" in updated.actions_executed


class TestPatternRecognizer:
    """Tests for PatternRecognizer."""

    def test_find_matching_pattern(self, store, sample_incidents):
        """Test finding matching patterns."""
        for inc in sample_incidents:
            store.save(inc)

        recognizer = PatternRecognizer(store)
        observations = [{"summary": "Pod terminated due to OOMKilled event"}]

        pattern = recognizer.find_matching_pattern(observations, "production")

        assert pattern is not None
        assert "memory" in pattern.likely_root_cause.lower()
        assert pattern.similar_incidents >= 1

    def test_suggest_runbook(self, store, sample_incidents):
        """Test runbook suggestions."""
        for inc in sample_incidents:
            store.save(inc)

        recognizer = PatternRecognizer(store)
        suggestion = recognizer.suggest_runbook("memory leak")

        assert suggestion is not None
        assert len(suggestion.recommended_actions) > 0
        assert suggestion.success_count >= 1

    def test_extract_signals(self, store):
        """Test signal extraction from observations."""
        recognizer = PatternRecognizer(store)

        observations = [
            {"summary": "Container was OOMKilled due to memory pressure"},
            {"summary": "High CPU throttling detected"},
            {"summary": "5xx errors increasing on /api/checkout"},
        ]

        signals = recognizer._extract_signals(observations)

        assert "memory" in signals
        assert "cpu" in signals
        assert "errors" in signals

    def test_analyze_trends(self, store, sample_incidents):
        """Test trend analysis."""
        for inc in sample_incidents:
            store.save(inc)

        recognizer = PatternRecognizer(store)
        trends = recognizer.analyze_trends(days=30)

        assert trends["total_incidents"] == 3
        assert trends["incidents_per_day"] > 0
        assert trends["resolution_rate"] == 2/3


class TestIntegration:
    """Integration tests."""

    def test_full_learning_flow(self, temp_db):
        """Test complete learning flow."""
        store = IncidentStore(temp_db)
        recognizer = PatternRecognizer(store)

        # 1. Create several similar incidents
        for i in range(5):
            inc = StoredIncident(
                id=f"mem_{i}",
                issue=f"OOM issue #{i} on service",
                namespace="prod",
                root_cause="memory leak",
                confidence=0.9,
                observations=[{"summary": "OOMKilled"}],
                actions_executed=["kubectl rollout restart"],
                outcome="resolved",
                resolution_time_minutes=10 + i,
                created_at=datetime.now(),
            )
            store.save(inc)

        # 2. Check pattern matching
        pattern = recognizer.find_matching_pattern(
            [{"summary": "New OOM event detected"}],
            "prod"
        )

        assert pattern is not None
        assert pattern.pattern_confidence >= 0.8
        assert pattern.likely_root_cause == "memory leak"

        # 3. Get runbook suggestion
        suggestion = recognizer.suggest_runbook("memory leak", "prod")

        assert suggestion is not None
        assert "kubectl rollout restart" in suggestion.recommended_actions

        # 4. Check statistics
        stats = store.get_statistics("prod")
        assert stats["total_incidents"] == 5
        assert stats["resolution_rate"] == 1.0
