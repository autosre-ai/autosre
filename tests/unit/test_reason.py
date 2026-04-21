"""
Unit Tests for ReasonerAgent

Tests the analysis and root cause determination functionality including:
- LLM response parsing
- Hypothesis extraction
- Confidence scoring
- Analysis result formatting
"""

from unittest.mock import MagicMock

import pytest

from opensre_core.agents.reason import AnalysisResult, Hypothesis, ReasonerAgent


class TestReasonerAgentParseAnalysis:
    """Tests for parsing LLM responses into AnalysisResult."""

    @pytest.fixture
    def agent(self):
        return ReasonerAgent()

    def test_parse_analysis_extracts_root_cause(self, agent):
        """Test extraction of root cause."""
        response = "Root Cause: Memory leak in pod\nConfidence: 75%"
        result = agent._parse_analysis(response)

        assert "Memory leak" in result.root_cause

    def test_parse_analysis_extracts_confidence_percentage(self, agent):
        """Test extraction of confidence as percentage."""
        response = "Root Cause: Memory leak\nConfidence: 75%"
        result = agent._parse_analysis(response)

        assert result.confidence == 0.75

    def test_parse_analysis_extracts_confidence_decimal(self, agent):
        """Test extraction of confidence as decimal."""
        response = "Root Cause: Memory leak\nConfidence: 0.85"
        result = agent._parse_analysis(response)

        assert result.confidence == 0.85

    def test_parse_analysis_handles_markdown_bold(self, agent):
        """Test parsing with markdown bold formatting."""
        response = "**Root Cause:** Memory leak\n**Confidence:** 80%"
        result = agent._parse_analysis(response)

        assert "Memory leak" in result.root_cause
        assert result.confidence == 0.80

    def test_parse_analysis_handles_markdown_asterisk(self, agent):
        """Test parsing with asterisk formatting."""
        response = "*Root Cause:* Memory leak in the application\n*Confidence:* 90%"
        result = agent._parse_analysis(response)

        assert "Memory leak" in result.root_cause

    def test_parse_analysis_extracts_hypotheses_numbered(self, agent):
        """Test extraction of numbered hypotheses."""
        response = """
Root Cause: Unknown
Confidence: 50%

Hypotheses:
1. Memory leak (60%)
2. Resource exhaustion (30%)
3. Configuration error (10%)
"""
        result = agent._parse_analysis(response)

        assert len(result.hypotheses) >= 1
        # Check first hypothesis
        assert any("Memory" in h.description for h in result.hypotheses)

    def test_parse_analysis_extracts_hypotheses_bulleted(self, agent):
        """Test extraction of bulleted hypotheses."""
        response = """
Root Cause: Unknown
Confidence: 50%

Hypotheses:
- Memory leak (60%)
- Resource exhaustion (30%)
"""
        result = agent._parse_analysis(response)

        assert len(result.hypotheses) >= 1

    def test_parse_analysis_extracts_hypothesis_confidence(self, agent):
        """Test extraction of individual hypothesis confidence."""
        response = """
Root Cause: Memory leak
Confidence: 60%

Hypotheses:
1. Memory leak (60%)
2. CPU throttling (40%)
"""
        result = agent._parse_analysis(response)

        # Hypotheses should have confidence extracted
        for h in result.hypotheses:
            assert h.confidence > 0

    def test_parse_analysis_extracts_similar_incidents(self, agent):
        """Test extraction of similar incidents."""
        response = """
Root Cause: Memory leak
Confidence: 75%

Similar Incidents:
- INC-2024-001: Previous memory issue
- INC-2024-002: OOM in production
"""
        result = agent._parse_analysis(response)

        assert len(result.similar_incidents) >= 1

    def test_parse_analysis_sorts_hypotheses_by_confidence(self, agent):
        """Test hypotheses are sorted by confidence (descending)."""
        response = """
Root Cause: Unknown
Confidence: 50%

Hypotheses:
1. Low confidence issue (20%)
2. High confidence issue (80%)
3. Medium confidence issue (50%)
"""
        result = agent._parse_analysis(response)

        # Should be sorted descending
        if len(result.hypotheses) >= 2:
            confidences = [h.confidence for h in result.hypotheses]
            assert confidences == sorted(confidences, reverse=True)

    def test_parse_analysis_uses_top_hypothesis_as_fallback(self, agent):
        """Test using top hypothesis when root cause is unclear."""
        response = """
Root Cause: Unable to determine root cause
Confidence: 0%

Hypotheses:
1. Memory leak (80%)
2. CPU issue (20%)
"""
        result = agent._parse_analysis(response)

        # Should use top hypothesis
        if result.hypotheses:
            assert result.root_cause == result.hypotheses[0].description
            assert result.confidence == result.hypotheses[0].confidence

    def test_parse_analysis_preserves_reasoning(self, agent):
        """Test that original response is preserved as reasoning."""
        response = "Root Cause: Memory leak\nConfidence: 75%\n\nThis is detailed reasoning."
        result = agent._parse_analysis(response)

        assert result.reasoning == response

    def test_parse_analysis_handles_empty_response(self, agent):
        """Test handling of empty response."""
        result = agent._parse_analysis("")

        assert result.root_cause == "Unable to determine root cause"
        assert result.confidence == 0.0

    def test_parse_analysis_handles_invalid_confidence(self, agent):
        """Test handling of invalid confidence values."""
        response = "Root Cause: Memory leak\nConfidence: invalid"
        result = agent._parse_analysis(response)

        # Should default to 0 or handle gracefully
        assert isinstance(result.confidence, float)


class TestAnalysisResultProperties:
    """Tests for AnalysisResult properties."""

    def test_is_low_confidence_true(self):
        """Test low confidence detection."""
        result = AnalysisResult(
            root_cause="Unknown",
            confidence=0.4,
        )
        assert result.is_low_confidence is True

    def test_is_low_confidence_false(self):
        """Test high confidence detection."""
        result = AnalysisResult(
            root_cause="Memory leak",
            confidence=0.8,
        )
        assert result.is_low_confidence is False

    def test_is_low_confidence_boundary(self):
        """Test boundary at 50%."""
        # Exactly 50% is low confidence
        result = AnalysisResult(root_cause="Test", confidence=0.5)
        assert result.is_low_confidence is False

        result = AnalysisResult(root_cause="Test", confidence=0.49)
        assert result.is_low_confidence is True

    def test_needs_more_data_true(self):
        """Test needs more data detection."""
        result = AnalysisResult(
            root_cause="Unknown",
            confidence=0.2,
        )
        assert result.needs_more_data is True

    def test_needs_more_data_false(self):
        """Test sufficient data detection."""
        result = AnalysisResult(
            root_cause="Memory leak",
            confidence=0.7,
        )
        assert result.needs_more_data is False


class TestAnalysisResultToContext:
    """Tests for AnalysisResult.to_context()."""

    def test_to_context_basic(self, sample_analysis_result):
        """Test basic context generation."""
        context = sample_analysis_result.to_context()

        assert "Root Cause:" in context
        assert "Confidence:" in context
        assert sample_analysis_result.root_cause in context

    def test_to_context_includes_hypotheses(self, sample_analysis_result):
        """Test context includes hypotheses."""
        context = sample_analysis_result.to_context()

        assert "Hypotheses:" in context
        for h in sample_analysis_result.hypotheses:
            assert h.description in context

    def test_to_context_includes_evidence(self, sample_analysis_result):
        """Test context includes hypothesis evidence."""
        context = sample_analysis_result.to_context()

        for h in sample_analysis_result.hypotheses:
            for e in h.evidence:
                assert e in context


class TestReasonerAgentAnalyze:
    """Tests for the main analyze method."""

    @pytest.fixture
    def agent(self, mock_llm):
        agent = ReasonerAgent()
        agent.llm = mock_llm
        return agent

    @pytest.mark.asyncio
    async def test_analyze_returns_result(self, agent, sample_observations):
        """Test analyze returns valid AnalysisResult."""
        result = await agent.analyze(sample_observations)

        assert isinstance(result, AnalysisResult)
        assert result.root_cause is not None

    @pytest.mark.asyncio
    async def test_analyze_calls_llm(self, agent, sample_observations, mock_llm):
        """Test analyze calls LLM with correct parameters."""
        await agent.analyze(sample_observations)

        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args

        # Should include issue and observations in prompt
        assert sample_observations.issue in call_args.kwargs.get("prompt", "")

    @pytest.mark.asyncio
    async def test_analyze_with_runbook_context(self, agent, sample_observations, mock_llm):
        """Test analyze includes runbook context."""
        runbook = "## Memory Issues\n\nCommon cause: memory leaks in Java services."

        await agent.analyze(sample_observations, runbook_context=runbook)

        call_args = mock_llm.generate.call_args
        # Runbook context should be in prompt
        prompt = call_args.kwargs.get("prompt", "")
        assert "memory" in prompt.lower() or "runbook" in prompt.lower()

    @pytest.mark.asyncio
    async def test_analyze_uses_low_temperature(self, agent, sample_observations, mock_llm):
        """Test analyze uses low temperature for focused analysis."""
        await agent.analyze(sample_observations)

        call_args = mock_llm.generate.call_args
        temperature = call_args.kwargs.get("temperature")

        # Should use low temperature (0.3 or similar)
        assert temperature is not None
        assert temperature <= 0.5


class TestReasonerAgentExplain:
    """Tests for the explain method."""

    @pytest.fixture
    def agent(self, mock_llm):
        agent = ReasonerAgent()
        agent.llm = mock_llm
        return agent

    @pytest.mark.asyncio
    async def test_explain_returns_string(self, agent, sample_analysis_result, mock_llm):
        """Test explain returns a string explanation."""
        mock_llm.generate.return_value = MagicMock(
            content="The root cause is a memory leak that has been accumulating over time."
        )

        explanation = await agent.explain(sample_analysis_result)

        assert isinstance(explanation, str)
        assert len(explanation) > 0

    @pytest.mark.asyncio
    async def test_explain_calls_llm(self, agent, sample_analysis_result, mock_llm):
        """Test explain calls LLM."""
        await agent.explain(sample_analysis_result)

        mock_llm.generate.assert_called_once()


class TestHypothesis:
    """Tests for Hypothesis dataclass."""

    def test_hypothesis_creation(self):
        """Test hypothesis creation."""
        h = Hypothesis(
            description="Memory leak",
            confidence=0.8,
            evidence=["High memory usage", "Increasing trend"],
            category="resource",
        )

        assert h.description == "Memory leak"
        assert h.confidence == 0.8
        assert len(h.evidence) == 2
        assert h.category == "resource"

    def test_hypothesis_default_values(self):
        """Test hypothesis default values."""
        h = Hypothesis(
            description="Test",
            confidence=0.5,
        )

        assert h.evidence == []
        assert h.category == "unknown"
