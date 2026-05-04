"""Tests for AutoSRE episodic memory system."""

import tempfile
import os
from pathlib import Path

import pytest

from autosre.memory import Episode, Strategy, EpisodicMemory


@pytest.fixture
def memory():
    """Create a temporary episodic memory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.db")
        mem = EpisodicMemory(db_path=db_path)
        yield mem


class TestEpisode:
    """Tests for Episode model."""
    
    def test_episode_creation(self):
        """Test basic episode creation."""
        ep = Episode(
            id="test-1",
            alert_type="high_latency",
            service_name="checkout"
        )
        assert ep.id == "test-1"
        assert ep.alert_type == "high_latency"
        assert ep.service_name == "checkout"
        assert ep.severity == "info"
        assert ep.resolved is False
        assert ep.skills_used == []
        assert ep.key_findings == []
    
    def test_episode_full(self):
        """Test episode with all fields."""
        ep = Episode(
            id="test-2",
            alert_type="cpu_spike",
            service_name="api-gateway",
            severity="critical",
            root_cause="Memory leak in cache module",
            summary="Investigated CPU spike, found memory leak",
            resolved=True,
            effectiveness_score=0.95,
            skills_used=["log_analysis", "metric_query"],
            key_findings=[{"type": "log", "message": "OOM detected"}],
            duration_seconds=300
        )
        assert ep.severity == "critical"
        assert ep.resolved is True
        assert ep.effectiveness_score == 0.95
        assert len(ep.skills_used) == 2
        assert len(ep.key_findings) == 1


class TestStrategy:
    """Tests for Strategy model."""
    
    def test_strategy_creation(self):
        """Test basic strategy creation."""
        strategy = Strategy(
            id="strat-1",
            alert_type="high_latency",
            strategy_text="Check database connections first"
        )
        assert strategy.id == "strat-1"
        assert strategy.service_name == "*"
        assert strategy.source_episode_ids == []


class TestEpisodicMemory:
    """Tests for EpisodicMemory class."""
    
    def test_store_and_retrieve_episode(self, memory):
        """Test storing and retrieving an episode."""
        ep = Episode(
            id="test-1",
            alert_type="high_latency",
            service_name="checkout"
        )
        memory.store_episode(ep)
        
        results = memory.search_similar("high_latency", "checkout")
        assert len(results) == 1
        assert results[0].id == "test-1"
        assert results[0].alert_type == "high_latency"
        assert results[0].service_name == "checkout"
    
    def test_search_by_alert_type_only(self, memory):
        """Test searching by alert type without service filter."""
        memory.store_episode(Episode(id="ep-1", alert_type="cpu_spike", service_name="api"))
        memory.store_episode(Episode(id="ep-2", alert_type="cpu_spike", service_name="web"))
        memory.store_episode(Episode(id="ep-3", alert_type="memory_leak", service_name="api"))
        
        results = memory.search_similar("cpu_spike")
        assert len(results) == 2
        assert all(r.alert_type == "cpu_spike" for r in results)
    
    def test_search_with_limit(self, memory):
        """Test search respects limit parameter."""
        for i in range(5):
            memory.store_episode(Episode(
                id=f"ep-{i}",
                alert_type="test_alert",
                service_name="test"
            ))
        
        results = memory.search_similar("test_alert", limit=2)
        assert len(results) == 2
    
    def test_search_prioritizes_service_match(self, memory):
        """Test that exact service matches come first."""
        memory.store_episode(Episode(id="ep-1", alert_type="latency", service_name="checkout"))
        memory.store_episode(Episode(id="ep-2", alert_type="latency", service_name="payment"))
        memory.store_episode(Episode(id="ep-3", alert_type="latency", service_name="checkout"))
        
        results = memory.search_similar("latency", service="checkout", limit=3)
        # Should get checkout episodes first
        checkout_eps = [r for r in results if r.service_name == "checkout"]
        assert len(checkout_eps) >= 2
    
    def test_store_and_get_strategy(self, memory):
        """Test storing and retrieving a strategy."""
        strategy = Strategy(
            id="strat-1",
            alert_type="high_latency",
            service_name="checkout",
            strategy_text="1. Check DB connections\n2. Review recent deployments"
        )
        memory.store_strategy(strategy)
        
        result = memory.get_or_generate_strategy("high_latency", "checkout")
        assert result is not None
        assert "Check DB connections" in result
    
    def test_strategy_fallback_to_wildcard(self, memory):
        """Test that wildcard strategy is used when no specific match."""
        strategy = Strategy(
            id="strat-1",
            alert_type="cpu_spike",
            service_name="*",
            strategy_text="Generic CPU spike handling"
        )
        memory.store_strategy(strategy)
        
        # Should find wildcard strategy even for unknown service
        result = memory.get_or_generate_strategy("cpu_spike", "unknown_service")
        assert result == "Generic CPU spike handling"
    
    def test_get_stats_empty(self, memory):
        """Test stats on empty database."""
        stats = memory.get_stats()
        assert stats["total_episodes"] == 0
        assert stats["resolved_count"] == 0
        assert stats["resolution_rate"] == 0.0
        assert stats["total_strategies"] == 0
    
    def test_get_stats_with_data(self, memory):
        """Test stats with populated database."""
        memory.store_episode(Episode(
            id="ep-1", alert_type="latency", resolved=True, effectiveness_score=0.9
        ))
        memory.store_episode(Episode(
            id="ep-2", alert_type="latency", resolved=True, effectiveness_score=0.8
        ))
        memory.store_episode(Episode(
            id="ep-3", alert_type="cpu", resolved=False
        ))
        memory.store_strategy(Strategy(
            id="strat-1", alert_type="latency", strategy_text="Check DB"
        ))
        
        stats = memory.get_stats()
        assert stats["total_episodes"] == 3
        assert stats["resolved_count"] == 2
        assert stats["resolution_rate"] == 2/3
        assert stats["total_strategies"] == 1
        assert stats["avg_effectiveness_score"] == 0.85
    
    def test_episode_update(self, memory):
        """Test that storing same ID updates the episode."""
        ep1 = Episode(id="ep-1", alert_type="test", resolved=False)
        memory.store_episode(ep1)
        
        ep2 = Episode(id="ep-1", alert_type="test", resolved=True, root_cause="Fixed!")
        memory.store_episode(ep2)
        
        results = memory.search_similar("test")
        assert len(results) == 1
        assert results[0].resolved is True
        assert results[0].root_cause == "Fixed!"
    
    def test_clear(self, memory):
        """Test clearing the database."""
        memory.store_episode(Episode(id="ep-1", alert_type="test"))
        memory.store_strategy(Strategy(id="s-1", alert_type="test", strategy_text="x"))
        
        memory.clear()
        
        stats = memory.get_stats()
        assert stats["total_episodes"] == 0
        assert stats["total_strategies"] == 0


class TestVerification:
    """Verification tests matching the task requirements."""
    
    def test_task_verification(self, memory):
        """Run the exact verification from the task."""
        ep = Episode(id="test-1", alert_type="high_latency", service_name="checkout")
        memory.store_episode(ep)
        results = memory.search_similar("high_latency", "checkout")
        assert len(results) > 0
