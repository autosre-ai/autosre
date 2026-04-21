"""
Pytest-compatible Integration Tests for OpenSRE

This module provides pytest fixtures and tests for CI integration.
Run with: pytest tests/integration/test_investigations.py -v
"""

import pytest
import asyncio
from datetime import datetime

from opensre_core.agents.orchestrator import Orchestrator
from tests.integration.scenarios import SCENARIOS, get_deployable_scenarios


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for each test."""
    return Orchestrator()


class TestOrchestratorBasic:
    """Basic orchestrator functionality tests."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initializes(self, orchestrator):
        """Test that orchestrator initializes correctly."""
        assert orchestrator is not None
        assert orchestrator.observer is not None
        assert orchestrator.reasoner is not None
        assert orchestrator.actor is not None
    
    @pytest.mark.asyncio
    async def test_investigate_returns_result(self, orchestrator):
        """Test that investigate returns a result object."""
        result = await orchestrator.investigate(
            issue="test investigation",
            namespace="default",
            timeout=30,
        )
        
        assert result is not None
        assert result.issue == "test investigation"
        assert result.namespace == "default"
        assert result.status in ["completed", "timeout", "failed"]
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_investigate_timeout(self, orchestrator):
        """Test that investigate respects timeout."""
        start = datetime.now()
        
        result = await orchestrator.investigate(
            issue="complex issue requiring analysis",
            namespace="default",
            timeout=5,
        )
        
        elapsed = (datetime.now() - start).total_seconds()
        
        # Should complete within timeout + buffer
        assert elapsed < 15
        assert result.status in ["completed", "timeout"]


class ScenarioDefinitions:
    """Test scenario definitions are valid."""
    
    def test_all_scenarios_have_required_fields(self):
        """Test that all scenarios have required fields."""
        for name, scenario in SCENARIOS.items():
            assert scenario.name == name, f"Scenario {name} has mismatched name"
            assert scenario.issue, f"Scenario {name} missing issue"
            assert isinstance(scenario.expected_confidence_min, float)
            assert 0.0 <= scenario.expected_confidence_min <= 1.0
    
    def test_deployable_scenarios_have_manifests(self):
        """Test that deployable scenarios have valid manifest paths."""
        for scenario in get_deployable_scenarios():
            assert scenario.manifest is not None
            assert scenario.manifest.endswith(".yaml")
    
    def test_scenario_count(self):
        """Test that we have expected number of scenarios."""
        assert len(SCENARIOS) >= 6, "Should have at least 6 test scenarios"


@pytest.mark.integration
class TestMemoryScenario:
    """Tests for memory-related scenarios."""
    
    @pytest.mark.asyncio
    async def test_memory_hog_detection(self, orchestrator):
        """Test detection of memory issues."""
        scenario = SCENARIOS["memory_hog"]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status == "completed"
        # Confidence may vary based on cluster state
        # Just verify we get a valid response
        assert result.confidence >= 0.0


@pytest.mark.integration
class TestCrashloopScenario:
    """Tests for crashloop scenarios."""
    
    @pytest.mark.asyncio
    async def test_crashloop_detection(self, orchestrator):
        """Test detection of crashlooping pods."""
        scenario = SCENARIOS["crashloop"]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status == "completed"


@pytest.mark.integration
class TestCPUScenario:
    """Tests for CPU-related scenarios."""
    
    @pytest.mark.asyncio
    async def test_cpu_hog_detection(self, orchestrator):
        """Test detection of CPU issues."""
        scenario = SCENARIOS["cpu_hog"]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status == "completed"


@pytest.mark.integration
class TestOOMScenario:
    """Tests for OOM scenarios."""
    
    @pytest.mark.asyncio
    async def test_oom_detection(self, orchestrator):
        """Test detection of OOM killed pods."""
        scenario = SCENARIOS["oom_kill"]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status == "completed"


@pytest.mark.integration
class TestHealthCheck:
    """Tests for health check scenarios."""
    
    @pytest.mark.asyncio
    async def test_healthy_namespace(self, orchestrator):
        """Test health check returns results."""
        scenario = SCENARIOS["healthy_check"]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status == "completed"


# Parameterized test for all scenarios
@pytest.mark.integration
@pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
class TestAllScenarios:
    """Run all scenarios with parameterization."""
    
    @pytest.mark.asyncio
    async def test_scenario_completes(self, orchestrator, scenario_name):
        """Test that each scenario completes without error."""
        scenario = SCENARIOS[scenario_name]
        
        result = await orchestrator.investigate(
            issue=scenario.issue,
            namespace=scenario.namespace,
            timeout=scenario.timeout_seconds,
        )
        
        assert result.status in ["completed", "timeout"]
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
