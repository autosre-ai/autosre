"""
Tests for AutoSRE v2 Orchestrator.

Tests the main investigation flow including:
- Alert classification
- Memory lookup
- Topology lookup  
- Subagent dispatch
- Report generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from autosre.orchestrator import Orchestrator, Investigation
from autosre.config import Settings
from autosre.memory import EpisodicMemory, Episode


class TestOrchestratorInit:
    """Test orchestrator initialization."""
    
    def test_create_orchestrator_default(self):
        """Test creating orchestrator with defaults."""
        orch = Orchestrator()
        assert orch.settings is not None
        assert isinstance(orch.settings, Settings)
    
    def test_create_orchestrator_with_settings(self):
        """Test creating orchestrator with custom settings."""
        settings = Settings(max_iterations=5)
        orch = Orchestrator(settings=settings)
        assert orch.settings.max_iterations == 5


class TestInvestigationFlow:
    """Test investigation lifecycle."""
    
    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator with temp memory."""
        settings = Settings()
        return Orchestrator(settings=settings)
    
    @pytest.mark.asyncio
    async def test_start_investigation(self, orchestrator):
        """Test starting an investigation creates proper state."""
        inv = await orchestrator.start_investigation(
            alert_id="alert-001",
            context={"service": "checkout-service"},
        )
        
        assert inv is not None
        assert inv.alert_id == "alert-001"
        assert inv.id is not None
        assert len(inv.id) > 0
    
    @pytest.mark.asyncio
    async def test_get_investigation(self, orchestrator):
        """Test retrieving an investigation by ID."""
        inv = await orchestrator.start_investigation(
            alert_id="alert-001",
            context={},
        )
        
        retrieved = orchestrator.get_investigation(inv.id)
        assert retrieved is not None
        assert retrieved.id == inv.id
    
    @pytest.mark.asyncio
    async def test_get_investigation_not_found(self, orchestrator):
        """Test retrieving non-existent investigation returns None."""
        result = orchestrator.get_investigation("non-existent-id")
        assert result is None


class TestMemoryLookup:
    """Test memory integration in orchestrator."""
    
    @pytest.fixture
    def memory_with_episodes(self, tmp_path):
        """Create memory with pre-populated episodes."""
        memory = EpisodicMemory(db_path=tmp_path / "test_memory.db")
        
        # Add a resolved episode
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
            root_cause="Database pool exhausted",
            summary="Connection pool saturation caused 500 errors",
            effectiveness_score=0.9,
        ))
        
        # Add another episode
        memory.store_episode(Episode(
            alert_type="http_500",
            service_name="payment-service",
            resolved=True,
            root_cause="Redis timeout",
            summary="Redis connection timeouts",
            effectiveness_score=0.85,
        ))
        
        return memory
    
    def test_search_similar_episodes(self, memory_with_episodes):
        """Test finding similar past incidents."""
        results = memory_with_episodes.search_similar(
            alert_type="http_500",
            service="checkout-service",
            limit=5,
        )
        
        assert len(results) >= 1
        # Exact match should be first
        assert results[0].service_name == "checkout-service"
    
    def test_memory_stats(self, memory_with_episodes):
        """Test memory statistics."""
        stats = memory_with_episodes.get_stats()
        
        assert stats["total_episodes"] == 2
        assert stats["resolved_count"] == 2


class TestTopologyLookup:
    """Test topology integration."""
    
    def test_service_graph_creation(self):
        """Test creating service graph."""
        from autosre.topology import ServiceGraph, ServiceNode
        
        graph = ServiceGraph()
        graph.add_service(ServiceNode(
            name="checkout-service",
            dependencies=["payment-service"],
        ))
        graph.add_service(ServiceNode(
            name="payment-service",
            dependencies=[],
        ))
        
        assert "checkout-service" in graph._nodes
        assert "payment-service" in graph._nodes
    
    def test_get_dependencies(self):
        """Test retrieving service dependencies."""
        from autosre.topology import ServiceGraph, ServiceNode
        
        graph = ServiceGraph()
        graph.add_service(ServiceNode(
            name="checkout-service",
            dependencies=["payment-service", "inventory-service"],
        ))
        graph.add_service(ServiceNode(name="payment-service"))
        graph.add_service(ServiceNode(name="inventory-service"))
        
        deps = graph.get_dependencies("checkout-service")
        
        assert len(deps) == 2
        dep_names = [d.name for d in deps]
        assert "payment-service" in dep_names
        assert "inventory-service" in dep_names
    
    def test_get_service(self):
        """Test retrieving a service node."""
        from autosre.topology import ServiceGraph, ServiceNode
        
        graph = ServiceGraph()
        graph.add_service(ServiceNode(
            name="checkout-service",
            tier="critical",
            team="checkout-team",
        ))
        
        node = graph.get_service("checkout-service")
        
        assert node is not None
        assert node.name == "checkout-service"
        assert node.tier == "critical"


class TestSubagentDispatch:
    """Test subagent coordination."""
    
    def test_available_agents_list(self):
        """Test that available agents are defined."""
        from autosre.agents import AVAILABLE_AGENTS
        
        # Should have at least some built-in agents
        assert AVAILABLE_AGENTS is not None


class TestInvestigationComplete:
    """Integration tests for complete investigation flow."""
    
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Full integration test requires mocking external services "
        "(Prometheus, Kubernetes, LLM). The triage phase needs golden signals "
        "and changes subagent to be mocked. See tests/test_investigation_quality.py "
        "TestIntegration::test_full_triage_to_investigation_flow for properly mocked version."
    )
    async def test_run_investigation_completes(self, tmp_path):
        """Test that investigation runs to completion."""
        orch = Orchestrator()
        
        inv = await orch.start_investigation(
            alert_id="test-alert",
            context={"service": "test-service"},
        )
        
        result = await orch.run_investigation(inv.id)
        
        assert result is not None
        assert result["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
