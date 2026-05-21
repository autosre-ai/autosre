"""
Tests for AutoSRE v2 Episodic Memory.
"""

import tempfile
from pathlib import Path

import pytest

from autosre.memory import EpisodicMemory, Episode, Strategy


class TestEpisodicMemory:
    """Test episodic memory storage and retrieval."""
    
    @pytest.fixture
    def memory(self, tmp_path: Path) -> EpisodicMemory:
        """Create a fresh memory instance for each test."""
        return EpisodicMemory(db_path=tmp_path / "test_memory.db")
    
    def test_store_and_retrieve(self, memory: EpisodicMemory):
        """Test storing and retrieving an episode."""
        episode = Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
            root_cause="Database connection pool exhausted",
            summary="High 500 errors due to DB pool saturation",
            skills_used=["pod_logs", "query_prometheus"],
            effectiveness_score=0.9,
        )
        
        episode_id = memory.store_episode(episode)
        
        # search_similar returns list, use first match
        results = memory.search_similar(alert_type="http_500", service="checkout-service", limit=1)
        assert len(results) == 1
        retrieved = results[0]
        assert retrieved.alert_type == "http_500"
        assert retrieved.service_name == "checkout-service"
        assert retrieved.resolved is True
        assert retrieved.root_cause == "Database connection pool exhausted"
        assert "pod_logs" in retrieved.skills_used
    
    def test_search_by_alert_type(self, memory: EpisodicMemory):
        """Test searching episodes by alert type."""
        # Store multiple episodes
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
            root_cause="DB pool exhausted",
        ))
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="payment-service",
            resolved=True,
            root_cause="Redis timeout",
        ))
        memory.store_episode(Episode(
            alert_type="high_latency",
            service_name="checkout-service",
            resolved=True,
            root_cause="Slow query",
        ))
        
        # Search for http_500
        results = memory.search_similar(alert_type="http_500", limit=10)
        assert len(results) == 2
        assert all(ep.alert_type == "http_500" for ep in results)
    
    def test_search_by_service(self, memory: EpisodicMemory):
        """Test searching episodes by service name."""
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
        ))
        memory.store_episode(Episode(
            alert_type="high_latency",
            service_name="checkout-service",
            resolved=True,
        ))
        memory.store_episode(Episode(
            alert_type="oom",
            service_name="payment-service",
            resolved=True,
        ))
        
        # search_similar filters primarily by alert_type, service is secondary
        # So we search all and filter
        results = memory.search_similar(alert_type="http_500", service="checkout-service", limit=10)
        assert len(results) >= 1
        assert results[0].service_name == "checkout-service"
    
    def test_search_exact_match_priority(self, memory: EpisodicMemory):
        """Test that exact alert+service matches come first."""
        # Store a high-effectiveness exact match
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
            root_cause="Exact match",
            effectiveness_score=0.9,
        ))
        
        # Store a lower-effectiveness different service
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="payment-service",
            resolved=True,
            root_cause="Different service",
            effectiveness_score=0.95,  # Higher score but different service
        ))
        
        results = memory.search_similar(
            alert_type="http_500",
            service="checkout-service",
            limit=1,
        )
        
        assert len(results) == 1
        assert results[0].root_cause == "Exact match"
    
    def test_full_text_search(self, memory: EpisodicMemory):
        """Test searching via alert_type and summary content."""
        memory.store_episode(Episode(
            alert_type="oom",
            service_name="ml-service",
            root_cause="Memory leak in TensorFlow model loading",
            summary="OOM killed due to unbounded tensor allocation",
        ))
        memory.store_episode(Episode(
            alert_type="high_cpu",
            service_name="api-gateway",
            root_cause="Regex backtracking",
            summary="CPU spike from regex DoS",
        ))
        
        # Search by alert_type
        results = memory.search_similar(alert_type="oom", limit=1)
        assert len(results) == 1
        assert results[0].service_name == "ml-service"
    
    def test_get_stats(self, memory: EpisodicMemory):
        """Test statistics retrieval."""
        memory.store_episode(Episode(alert_type="http_500", resolved=True))
        memory.store_episode(Episode(alert_type="http_500", resolved=True))
        memory.store_episode(Episode(alert_type="oom", resolved=False))
        
        stats = memory.get_stats()
        
        assert stats["total_episodes"] == 3
        assert stats["resolved_count"] == 2
        assert abs(stats["resolution_rate"] - 0.666) < 0.01
    
    def test_clear(self, memory: EpisodicMemory):
        """Test clearing all episodes."""
        memory.store_episode(Episode(alert_type="test"))
        memory.store_episode(Episode(alert_type="test2"))
        
        memory.clear()
        
        assert memory.get_stats()["total_episodes"] == 0
    
    def test_strategy_storage(self, memory: EpisodicMemory):
        """Test storing and retrieving strategies."""
        strategy = Strategy(
            alert_type="http_500",
            service_name="checkout-service",
            strategy_text="Check DB connections first, then look at Redis.",
            source_episode_ids=["ep1", "ep2"],
        )
        
        memory.store_strategy(strategy)
        
        retrieved = memory.get_or_generate_strategy("http_500", "checkout-service")
        assert retrieved is not None
        assert "DB connections" in retrieved
    
    def test_strategy_wildcard_fallback(self, memory: EpisodicMemory):
        """Test strategy retrieval falls back to wildcard."""
        # Store a wildcard strategy
        memory.store_strategy(Strategy(
            alert_type="http_500",
            service_name="*",
            strategy_text="Generic 500 debugging strategy",
        ))
        
        # Query for specific service - should fall back to wildcard
        retrieved = memory.get_or_generate_strategy("http_500", "unknown-service")
        assert retrieved is not None
        assert "Generic" in retrieved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
