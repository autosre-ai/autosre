"""Tests for the investigation synthesizer module."""

import pytest
from datetime import datetime, timezone, timedelta

from autosre.agents.synthesizer import Synthesizer, Synthesis
from autosre.agents.state import (
    InvestigationState,
    Alert,
    Evidence,
    AgentResult,
    Hypothesis,
)


@pytest.fixture
def sample_alert():
    """Create a sample alert for testing."""
    return Alert(
        name="HighLatency",
        service="api-gateway",
        severity="warning",
        description="API latency above threshold",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_state(sample_alert):
    """Create a sample investigation state with evidence."""
    state = InvestigationState(
        investigation_id="test-inv-001",
        alert=sample_alert,
    )
    return state


class TestSynthesizerCorrelateFindings:
    """Test the correlate_findings method."""

    @pytest.mark.asyncio
    async def test_correlate_findings_empty_state(self, sample_state):
        """Empty state should return no correlations."""
        synthesizer = Synthesizer()
        correlations = await synthesizer.correlate_findings(sample_state)
        assert correlations == []

    @pytest.mark.asyncio
    async def test_temporal_correlation(self, sample_state):
        """Findings within 5 minutes should be temporally correlated."""
        now = datetime.now(timezone.utc)
        
        # Add two agent results with evidence close in time
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="CPU spike detected at 95%",
                    confidence=0.8,
                    timestamp=now,
                )
            ],
        )
        
        sample_state.agent_results["logs-agent"] = AgentResult(
            agent_id="logs-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="logs-agent",
                    skill="elasticsearch",
                    finding="Error rate increased 10x",
                    confidence=0.9,
                    timestamp=now + timedelta(minutes=2),  # 2 minutes later
                )
            ],
        )
        
        synthesizer = Synthesizer()
        correlations = await synthesizer.correlate_findings(sample_state)
        
        temporal = [c for c in correlations if c["type"] == "temporal"]
        assert len(temporal) >= 1
        assert "metrics-agent" in temporal[0]["sources"]
        assert "logs-agent" in temporal[0]["sources"]
        assert temporal[0]["time_delta_seconds"] == 120  # 2 minutes

    @pytest.mark.asyncio
    async def test_hypothesis_correlation(self, sample_state):
        """Evidence supporting same hypothesis should be correlated."""
        now = datetime.now(timezone.utc)
        
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="Memory usage at 98%",
                    confidence=0.85,
                    timestamp=now,
                    supports_hypothesis="memory_leak",
                )
            ],
        )
        
        sample_state.agent_results["k8s-agent"] = AgentResult(
            agent_id="k8s-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="k8s-agent",
                    skill="kubectl",
                    finding="Pod OOMKilled 3 times",
                    confidence=0.95,
                    timestamp=now + timedelta(hours=1),  # Not temporally close
                    supports_hypothesis="memory_leak",
                )
            ],
        )
        
        synthesizer = Synthesizer()
        correlations = await synthesizer.correlate_findings(sample_state)
        
        hypothesis_corr = [c for c in correlations if c["type"] == "hypothesis"]
        assert len(hypothesis_corr) >= 1
        assert hypothesis_corr[0]["hypothesis"] == "memory_leak"
        assert "metrics-agent" in hypothesis_corr[0]["sources"]
        assert "k8s-agent" in hypothesis_corr[0]["sources"]

    @pytest.mark.asyncio
    async def test_cross_validation_correlation(self, sample_state):
        """High-confidence evidence from multiple sources should be cross-validated."""
        now = datetime.now(timezone.utc)
        
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="Request latency p99 = 2s",
                    confidence=0.75,  # Above 0.7 threshold
                    timestamp=now,
                )
            ],
        )
        
        sample_state.agent_results["traces-agent"] = AgentResult(
            agent_id="traces-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="traces-agent",
                    skill="jaeger",
                    finding="Database queries taking 1.5s average",
                    confidence=0.80,  # Above 0.7 threshold
                    timestamp=now + timedelta(hours=2),  # Not temporally close
                )
            ],
        )
        
        synthesizer = Synthesizer()
        correlations = await synthesizer.correlate_findings(sample_state)
        
        cross_val = [c for c in correlations if c["type"] == "cross_validation"]
        assert len(cross_val) >= 1
        assert "metrics-agent" in cross_val[0]["sources"]
        assert "traces-agent" in cross_val[0]["sources"]

    @pytest.mark.asyncio
    async def test_no_same_source_temporal_correlation(self, sample_state):
        """Evidence from same source should not create temporal correlations."""
        now = datetime.now(timezone.utc)
        
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="CPU at 95%",
                    confidence=0.8,
                    timestamp=now,
                ),
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="Memory at 90%",
                    confidence=0.8,
                    timestamp=now + timedelta(minutes=1),
                ),
            ],
        )
        
        synthesizer = Synthesizer()
        correlations = await synthesizer.correlate_findings(sample_state)
        
        # Should have no temporal correlations (same source)
        temporal = [c for c in correlations if c["type"] == "temporal"]
        assert len(temporal) == 0


class TestSynthesizerSynthesize:
    """Test the synthesize method."""

    @pytest.mark.asyncio
    async def test_synthesize_basic(self, sample_state):
        """Basic synthesis should return a Synthesis object."""
        synthesizer = Synthesizer()
        result = await synthesizer.synthesize(sample_state)
        
        assert isinstance(result, Synthesis)
        assert result.affected_services == ["api-gateway"]

    @pytest.mark.asyncio
    async def test_synthesize_with_hypothesis(self, sample_state):
        """Synthesis should include existing hypotheses."""
        sample_state.hypotheses = [
            Hypothesis(
                hypothesis="Database connection pool exhausted",
                priority="high",
                confidence=0.85,
            )
        ]
        
        synthesizer = Synthesizer()
        result = await synthesizer.synthesize(sample_state)
        
        assert len(result.hypotheses) == 1
        assert result.primary_hypothesis is not None
        assert result.primary_hypothesis.hypothesis == "Database connection pool exhausted"


class TestSynthesizerValidateHypothesis:
    """Test the validate_hypothesis method."""

    @pytest.mark.asyncio
    async def test_validate_hypothesis_no_evidence(self, sample_state):
        """Hypothesis with no supporting evidence should have reduced confidence."""
        hypothesis = Hypothesis(
            hypothesis="Database connection pool exhausted",
            priority="high",
            confidence=0.8,
            agents_to_test=["db-agent"],
        )
        
        synthesizer = Synthesizer()
        validated = await synthesizer.validate_hypothesis(hypothesis, sample_state)
        
        # Confidence should be reduced (0.8 * 0.7 = 0.56)
        assert validated.confidence < hypothesis.confidence
        assert validated.confidence == pytest.approx(0.504, rel=0.01)  # 0.8 * 0.7 * 0.9 (pending agent)

    @pytest.mark.asyncio
    async def test_validate_hypothesis_with_supporting_evidence(self, sample_state):
        """Hypothesis with supporting evidence should have maintained or boosted confidence."""
        now = datetime.now(timezone.utc)
        
        hypothesis = Hypothesis(
            hypothesis="Database connection pool exhausted",
            priority="high",
            confidence=0.7,
            agents_to_test=["db-agent"],
        )
        
        # Add evidence that explicitly supports this hypothesis
        sample_state.agent_results["db-agent"] = AgentResult(
            agent_id="db-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="db-agent",
                    skill="postgres",
                    finding="Connection pool at 100% capacity",
                    confidence=0.9,
                    quality_score=0.8,
                    timestamp=now,
                    supports_hypothesis="Database connection pool exhausted",
                )
            ],
        )
        
        synthesizer = Synthesizer()
        validated = await synthesizer.validate_hypothesis(hypothesis, sample_state)
        
        # Confidence should be boosted since we have high-quality supporting evidence
        assert validated.confidence >= hypothesis.confidence
        assert validated.hypothesis == hypothesis.hypothesis

    @pytest.mark.asyncio
    async def test_validate_hypothesis_keyword_matching(self, sample_state):
        """Hypothesis validation should work with implicit keyword matching."""
        now = datetime.now(timezone.utc)
        
        hypothesis = Hypothesis(
            hypothesis="Memory leak causing high latency response",
            priority="high",
            confidence=0.6,
            agents_to_test=["metrics-agent"],
        )
        
        # Add evidence with overlapping keywords (memory, latency)
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="Memory usage increasing, latency degrading",
                    confidence=0.85,
                    quality_score=0.75,
                    timestamp=now,
                )
            ],
        )
        
        synthesizer = Synthesizer()
        validated = await synthesizer.validate_hypothesis(hypothesis, sample_state)
        
        # Should recognize keyword overlap and boost confidence
        assert validated.confidence >= hypothesis.confidence

    @pytest.mark.asyncio
    async def test_validate_hypothesis_pending_agents(self, sample_state):
        """Hypothesis with pending agents should have slightly reduced confidence."""
        now = datetime.now(timezone.utc)
        
        hypothesis = Hypothesis(
            hypothesis="CPU throttling causing slowdown",
            priority="medium",
            confidence=0.7,
            agents_to_test=["metrics-agent", "k8s-agent"],  # k8s-agent hasn't run
        )
        
        # Only metrics-agent has results
        sample_state.agent_results["metrics-agent"] = AgentResult(
            agent_id="metrics-agent",
            status="completed",
            evidence=[
                Evidence(
                    source="metrics-agent",
                    skill="prometheus",
                    finding="CPU throttling detected on pods",
                    confidence=0.9,
                    quality_score=0.8,
                    timestamp=now,
                    supports_hypothesis="CPU throttling causing slowdown",
                )
            ],
        )
        
        synthesizer = Synthesizer()
        validated = await synthesizer.validate_hypothesis(hypothesis, sample_state)
        
        # Confidence boosted by evidence but penalized for pending agent
        assert validated.confidence < 1.0  # Can't be 100% with pending agents
