"""
Tests for AutoSRE v2 Agents.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from autosre.agents import (
    InvestigationState,
    InvestigationStatus,
    Hypothesis,
    Evidence,
    Priority,
)
from autosre.agents.planner import run_planner, apply_plan_to_state, PlannerOutput
from autosre.agents.synthesizer import run_synthesizer, SynthesizerOutput


class TestInvestigationState:
    """Test investigation state management."""
    
    def test_create_state(self):
        """Test creating investigation state."""
        state = InvestigationState(
            alert={"name": "TestAlert", "service": "test-service"},
            max_iterations=3,
        )
        
        assert state.status == InvestigationStatus.PENDING
        assert state.alert["name"] == "TestAlert"
        assert state.iteration == 0
        assert state.max_iterations == 3
        assert state.investigation_id  # auto-generated
    
    def test_add_message(self):
        """Test adding messages."""
        state = InvestigationState()
        
        state.add_message("planner", "Starting investigation")
        state.add_message("synthesizer", "Need more evidence")
        
        assert len(state.messages) == 2
        assert state.messages[0]["role"] == "planner"
        assert state.messages[1]["role"] == "synthesizer"
    
    def test_add_evidence(self):
        """Test adding evidence."""
        state = InvestigationState()
        
        evidence = Evidence(
            source="kubernetes",
            skill="get_pods",
            query="kubectl get pods",
            result="pod-123 Running",
            relevance=0.8,
        )
        
        state.add_evidence(evidence)
        
        assert len(state.all_evidence) == 1
        assert state.all_evidence[0].source == "kubernetes"
    
    def test_get_all_skills_used(self):
        """Test skills extraction from evidence."""
        state = InvestigationState()
        
        state.add_evidence(Evidence(source="k8s", skill="get_pods", query="", result=""))
        state.add_evidence(Evidence(source="k8s", skill="describe_pod", query="", result=""))
        state.add_evidence(Evidence(source="metrics", skill="query_prometheus", query="", result=""))
        state.add_evidence(Evidence(source="k8s", skill="get_pods", query="", result=""))  # duplicate
        
        skills = state.get_all_skills_used()
        
        assert len(skills) == 3
        assert "get_pods" in skills
        assert "describe_pod" in skills
        assert "query_prometheus" in skills


class TestHypothesis:
    """Test hypothesis model."""
    
    def test_create_hypothesis(self):
        """Test creating hypothesis."""
        h = Hypothesis(
            hypothesis="Database connection pool exhausted",
            priority=Priority.HIGH,
            agents_to_test=["kubernetes", "metrics"],
        )
        
        assert h.hypothesis == "Database connection pool exhausted"
        assert h.priority == Priority.HIGH
        assert "kubernetes" in h.agents_to_test
        assert h.confirmed is None  # untested
    
    def test_to_prompt(self):
        """Test hypothesis prompt formatting."""
        h = Hypothesis(
            hypothesis="Memory leak in service",
            priority=Priority.MEDIUM,
            confidence=0.8,
            confirmed=True,
        )
        
        prompt = h.to_prompt()
        
        assert "Memory leak" in prompt
        assert "medium" in prompt.lower()
        assert "✓ Confirmed" in prompt
        assert "80%" in prompt


class TestPlanner:
    """Test planner agent."""
    
    @pytest.mark.asyncio
    async def test_run_planner_fallback(self):
        """Test planner with failed LLM falls back gracefully."""
        state = InvestigationState(
            alert={"name": "TestAlert", "service": "test-service"},
        )
        
        # Mock LLM client that raises
        mock_client = MagicMock()
        mock_client.complete_structured = AsyncMock(side_effect=Exception("LLM failed"))
        
        plan = await run_planner(
            state=state,
            available_agents=["kubernetes", "metrics"],
            llm_client=mock_client,
        )
        
        # Should return fallback plan
        assert len(plan.hypotheses) >= 1
        assert len(plan.selected_agents) >= 1
        assert "error" in plan.reasoning.lower() or "fallback" in plan.reasoning.lower()
    
    def test_apply_plan_to_state(self):
        """Test applying plan to state."""
        from autosre.agents.state import InvestigationPlan
        
        state = InvestigationState()
        plan = InvestigationPlan(
            hypotheses=[
                Hypothesis(hypothesis="Test", priority=Priority.HIGH),
            ],
            selected_agents=["kubernetes"],
            reasoning="Testing",
        )
        
        apply_plan_to_state(state, plan)
        
        assert len(state.hypotheses) == 1
        assert state.selected_agents == ["kubernetes"]
        assert len(state.messages) == 1


class TestSynthesizer:
    """Test synthesizer agent."""
    
    @pytest.mark.asyncio
    async def test_run_synthesizer_force_conclude(self):
        """Test synthesizer with force_conclude."""
        from autosre.agents.state import SubagentResult
        
        state = InvestigationState(
            alert={"name": "TestAlert"},
            iteration=2,
            max_iterations=3,
        )
        state.agent_results["kubernetes"] = SubagentResult(
            agent_id="kubernetes",
            findings="Found pod restarts",
            duration_seconds=5.0,
        )
        
        # Mock LLM that returns insufficient evidence
        mock_client = MagicMock()
        mock_client.complete_structured = AsyncMock(return_value=SynthesizerOutput(
            sufficient_evidence=False,
            confidence=0.5,
            summary="Need more evidence",
            gaps=["Missing metrics"],
            feedback="Check metrics",
        ))
        
        decision = await run_synthesizer(
            state=state,
            llm_client=mock_client,
            force_conclude=True,
        )
        
        # Should force conclusion despite LLM saying insufficient
        assert decision.sufficient_evidence is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
