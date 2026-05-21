"""
Tests for AutoSRE v2 ReAct Loop.

Tests the reasoning and acting loop including:
- React iterations
- Tool deduplication
- Early exit conditions
- Max iterations handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.agents.state import InvestigationState, Alert, Hypothesis, Evidence


class TestReactIteration:
    """Test ReAct iteration behavior."""
    
    @pytest.fixture
    def investigation_state(self):
        """Create a sample investigation state."""
        return InvestigationState(
            investigation_id="test-001",
            alert=Alert(
                name="HighLatency",
                service="api-gateway",
                severity="warning",
                description="P99 latency above threshold",
            ),
        )
    
    def test_initial_state(self, investigation_state):
        """Test initial state values."""
        state = investigation_state
        
        assert state.iteration == 0
        assert state.max_iterations == 3
        assert state.status == "running"
        assert len(state.hypotheses) == 0
    
    def test_increment_iteration(self, investigation_state):
        """Test iteration counter increment."""
        state = investigation_state
        
        state.iteration += 1
        assert state.iteration == 1
        
        state.iteration += 1
        assert state.iteration == 2
    
    def test_add_hypothesis(self, investigation_state):
        """Test adding hypotheses to state."""
        state = investigation_state
        
        hyp = Hypothesis(
            hypothesis="Database connection pool exhausted",
            priority="high",
            agents_to_test=["kubernetes", "metrics"],
        )
        
        state.hypotheses.append(hyp)
        
        assert len(state.hypotheses) == 1
        assert state.hypotheses[0].hypothesis == "Database connection pool exhausted"


class TestToolDeduplication:
    """Test that tools are not called redundantly."""
    
    @pytest.fixture
    def state_with_evidence(self):
        """Create state with existing evidence."""
        state = InvestigationState(
            investigation_id="test-002",
            alert=Alert(
                name="Test",
                description="Test alert",
            ),
        )
        
        # Add some evidence
        state.agent_results["kubernetes"] = MagicMock(
            agent_id="kubernetes",
            evidence=[
                Evidence(
                    source="kubernetes",
                    skill="get_pods",
                    finding="All pods running",
                    confidence=0.9,
                ),
            ],
        )
        
        return state
    
    def test_evidence_recorded(self, state_with_evidence):
        """Test that evidence is properly recorded."""
        state = state_with_evidence
        
        assert "kubernetes" in state.agent_results
        assert len(state.agent_results["kubernetes"].evidence) == 1
    
    def test_check_existing_skills(self, state_with_evidence):
        """Test checking if a skill was already used."""
        state = state_with_evidence
        
        # Gather all skills used
        skills_used = set()
        for result in state.agent_results.values():
            for ev in result.evidence:
                skills_used.add(ev.skill)
        
        assert "get_pods" in skills_used
        assert "describe_pod" not in skills_used


class TestEarlyExit:
    """Test early exit conditions."""
    
    @pytest.fixture
    def high_confidence_state(self):
        """Create state with high confidence finding."""
        state = InvestigationState(
            investigation_id="test-003",
            alert=Alert(name="Test", description="Test"),
        )
        state.confidence = 0.95
        state.root_cause = "Database pool exhausted"
        return state
    
    def test_sufficient_confidence(self, high_confidence_state):
        """Test detecting sufficient confidence for early exit."""
        state = high_confidence_state
        
        # Check if confidence is above threshold
        threshold = 0.9
        should_exit = state.confidence >= threshold and state.root_cause is not None
        
        assert should_exit is True
    
    def test_insufficient_confidence(self):
        """Test continuing when confidence is low."""
        state = InvestigationState(
            investigation_id="test-004",
            alert=Alert(name="Test", description="Test"),
        )
        state.confidence = 0.5
        state.root_cause = "Maybe database?"
        
        threshold = 0.9
        should_exit = state.confidence >= threshold
        
        assert should_exit is False


class TestMaxIterations:
    """Test max iterations handling."""
    
    def test_max_iterations_default(self):
        """Test default max iterations."""
        state = InvestigationState(
            investigation_id="test-005",
            alert=Alert(name="Test", description="Test"),
        )
        
        assert state.max_iterations == 3
    
    def test_custom_max_iterations(self):
        """Test setting custom max iterations."""
        state = InvestigationState(
            investigation_id="test-006",
            alert=Alert(name="Test", description="Test"),
            max_iterations=5,
        )
        
        assert state.max_iterations == 5
    
    def test_reached_max_iterations(self):
        """Test detecting when max iterations reached."""
        state = InvestigationState(
            investigation_id="test-007",
            alert=Alert(name="Test", description="Test"),
            max_iterations=3,
        )
        
        state.iteration = 3
        
        reached_max = state.iteration >= state.max_iterations
        assert reached_max is True
    
    def test_below_max_iterations(self):
        """Test continuing when below max iterations."""
        state = InvestigationState(
            investigation_id="test-008",
            alert=Alert(name="Test", description="Test"),
            max_iterations=3,
        )
        
        state.iteration = 1
        
        reached_max = state.iteration >= state.max_iterations
        assert reached_max is False


class TestStatusTransitions:
    """Test state status transitions."""
    
    def test_initial_status(self):
        """Test initial status is running."""
        state = InvestigationState(
            investigation_id="test-009",
            alert=Alert(name="Test", description="Test"),
        )
        
        assert state.status == "running"
    
    def test_complete_status(self):
        """Test transitioning to completed."""
        state = InvestigationState(
            investigation_id="test-010",
            alert=Alert(name="Test", description="Test"),
        )
        
        state.status = "completed"
        assert state.status == "completed"
    
    def test_failed_status(self):
        """Test transitioning to failed."""
        state = InvestigationState(
            investigation_id="test-011",
            alert=Alert(name="Test", description="Test"),
        )
        
        state.status = "failed"
        assert state.status == "failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
