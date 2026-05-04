"""
Tests for AutoSRE v2 Orchestrator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from autosre import Orchestrator, InvestigationStatus
from autosre.agents import InvestigationPlan, Hypothesis, Priority
from autosre.agents.synthesizer import SynthesizerOutput
from autosre.memory import EpisodicMemory


class MockLLMClient:
    """Mock LLM client for testing."""
    
    async def complete(self, prompt, **kwargs):
        return MagicMock(content="Mock response")
    
    async def complete_structured(self, prompt, output_type, **kwargs):
        if output_type.__name__ == "PlannerOutput":
            return MagicMock(
                hypotheses=[{"hypothesis": "Test hypothesis", "priority": "high", "agents_to_test": ["kubernetes"]}],
                selected_agents=["kubernetes"],
                reasoning="Test plan",
            )
        elif output_type.__name__ == "SynthesizerOutput":
            return SynthesizerOutput(
                sufficient_evidence=True,
                confidence=0.8,
                summary="Test complete",
                root_cause="Test root cause",
                gaps=[],
                feedback="",
            )
        return MagicMock()


class TestOrchestrator:
    """Test orchestrator flow."""
    
    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create orchestrator with mocked dependencies."""
        memory = EpisodicMemory(db_path=tmp_path / "test_memory.db")
        llm = MockLLMClient()
        return Orchestrator(
            memory=memory,
            llm_client=llm,
        )
    
    def test_classify_alert(self, mock_orchestrator):
        """Test alert classification."""
        orch = mock_orchestrator
        
        assert orch._classify_alert({"description": "503 errors"}) == "http_503"
        assert orch._classify_alert({"description": "high latency"}) == "high_latency"
        assert orch._classify_alert({"description": "OOM killed"}) == "out_of_memory"
        assert orch._classify_alert({"description": "something random"}) == "unknown"
    
    @pytest.mark.asyncio
    async def test_investigate_string_alert(self, mock_orchestrator, tmp_path):
        """Test investigating with string alert."""
        orch = mock_orchestrator
        
        # Mock subagent results
        with patch.object(orch, '_run_subagents', new_callable=AsyncMock) as mock_run:
            async def add_mock_result(state):
                from autosre.agents.state import SubagentResult
                state.agent_results["kubernetes"] = SubagentResult(
                    agent_id="kubernetes",
                    status=InvestigationStatus.COMPLETED,
                    findings="Mock findings",
                    duration_seconds=1.0,
                )
            mock_run.side_effect = add_mock_result
            
            # Mock writeup
            with patch('autosre.orchestrator.run_writeup', new_callable=AsyncMock) as mock_writeup:
                mock_writeup.return_value = (
                    "# Investigation Report\nMock narrative",
                    {"title": "Test", "executive_summary": "Test", "root_cause": {"summary": "Test root cause"}},
                )
                
                report = await orch.investigate("test-service 500 errors")
        
        assert report is not None
        assert report.status in [InvestigationStatus.COMPLETED, InvestigationStatus.FAILED]
    
    @pytest.mark.asyncio
    async def test_investigate_dict_alert(self, mock_orchestrator, tmp_path):
        """Test investigating with dict alert."""
        orch = mock_orchestrator
        
        alert = {
            "name": "HighErrorRate",
            "service": "checkout-service",
            "severity": "critical",
            "description": "Error rate above 5%",
        }
        
        # Mock subagent results
        with patch.object(orch, '_run_subagents', new_callable=AsyncMock) as mock_run:
            async def add_mock_result(state):
                from autosre.agents.state import SubagentResult
                state.agent_results["kubernetes"] = SubagentResult(
                    agent_id="kubernetes",
                    status=InvestigationStatus.COMPLETED,
                    findings="Mock findings",
                    duration_seconds=1.0,
                )
            mock_run.side_effect = add_mock_result
            
            with patch('autosre.orchestrator.run_writeup', new_callable=AsyncMock) as mock_writeup:
                mock_writeup.return_value = (
                    "Mock narrative",
                    {"title": "Test", "executive_summary": "Test", "root_cause": {"summary": "Test"}},
                )
                
                report = await orch.investigate(alert)
        
        assert report.service_name == "checkout-service"
    
    @pytest.mark.asyncio 
    async def test_memory_lookup(self, mock_orchestrator):
        """Test memory lookup phase."""
        orch = mock_orchestrator
        
        # Pre-populate memory
        from autosre.memory import Episode
        orch.memory.store(Episode(
            alert_type="http_500",
            service_name="checkout-service",
            resolved=True,
            root_cause="Database pool exhausted",
        ))
        
        from autosre.agents import InvestigationState
        state = InvestigationState(
            alert_type="http_500",
            service_name="checkout-service",
        )
        
        await orch._memory_lookup(state)
        
        assert state.memory_context.get("has_similar_episodes") is True
        assert state.memory_context.get("episode_count", 0) >= 1


class TestOrchestratorIntegration:
    """Integration tests (require actual dependencies)."""
    
    @pytest.mark.skip(reason="Requires LLM API key")
    @pytest.mark.asyncio
    async def test_full_investigation_flow(self, tmp_path):
        """Test complete investigation flow."""
        from autosre import Orchestrator, Settings
        
        settings = Settings()
        memory = EpisodicMemory(db_path=tmp_path / "memory.db")
        orch = Orchestrator(settings=settings, memory=memory)
        
        report = await orch.investigate({
            "name": "TestAlert",
            "service": "test-service",
            "severity": "warning",
            "description": "Test alert for integration testing",
        })
        
        assert report is not None
        assert report.iterations >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
