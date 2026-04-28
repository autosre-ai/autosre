"""
Tests for prompt templates.
"""

import pytest
from autosre.utils.prompts import (
    REASONER_SYSTEM_PROMPT,
    REASONER_ANALYSIS_PROMPT,
    ACTOR_SYSTEM_PROMPT,
    ACTOR_ACTION_PROMPT,
    OBSERVER_QUERY_PROMPT,
    COMMUNICATOR_INCIDENT_PROMPT,
    SUMMARIZE_LOGS_PROMPT,
    EXPLAIN_METRIC_PROMPT,
)


class TestReasonerPrompts:
    """Tests for reasoner prompts."""
    
    def test_system_prompt_exists(self):
        """Test system prompt is defined."""
        assert REASONER_SYSTEM_PROMPT is not None
        assert len(REASONER_SYSTEM_PROMPT) > 100
    
    def test_system_prompt_mentions_sre(self):
        """Test system prompt mentions SRE context."""
        prompt_lower = REASONER_SYSTEM_PROMPT.lower()
        assert "sre" in prompt_lower or "incident" in prompt_lower
    
    def test_system_prompt_has_anomaly_detection(self):
        """Test system prompt includes anomaly detection guidelines."""
        assert "anomaly" in REASONER_SYSTEM_PROMPT.lower()
    
    def test_analysis_prompt_has_placeholders(self):
        """Test analysis prompt has expected placeholders."""
        assert "{issue}" in REASONER_ANALYSIS_PROMPT
        assert "{observations}" in REASONER_ANALYSIS_PROMPT
    
    def test_analysis_prompt_format(self):
        """Test analysis prompt can be formatted."""
        result = REASONER_ANALYSIS_PROMPT.format(
            issue="High CPU on api-service",
            observations="CPU at 95%",
            runbook_context="Check CPU usage",
        )
        
        assert "High CPU" in result
        assert "95%" in result


class TestActorPrompts:
    """Tests for actor prompts."""
    
    def test_system_prompt_exists(self):
        """Test actor system prompt exists."""
        assert ACTOR_SYSTEM_PROMPT is not None
        assert len(ACTOR_SYSTEM_PROMPT) > 100
    
    def test_system_prompt_mentions_remediation(self):
        """Test prompt mentions remediation."""
        assert "remediation" in ACTOR_SYSTEM_PROMPT.lower()
    
    def test_system_prompt_has_risk_levels(self):
        """Test prompt defines risk levels."""
        assert "risk" in ACTOR_SYSTEM_PROMPT.lower()
        assert "low" in ACTOR_SYSTEM_PROMPT.lower()
        assert "medium" in ACTOR_SYSTEM_PROMPT.lower()
        assert "high" in ACTOR_SYSTEM_PROMPT.lower()
    
    def test_action_prompt_has_placeholders(self):
        """Test action prompt has placeholders."""
        assert "{root_cause}" in ACTOR_ACTION_PROMPT
        assert "{namespace}" in ACTOR_ACTION_PROMPT


class TestObserverPrompts:
    """Tests for observer prompts."""
    
    def test_query_prompt_exists(self):
        """Test observer query prompt exists."""
        assert OBSERVER_QUERY_PROMPT is not None
    
    def test_query_prompt_mentions_promql(self):
        """Test prompt mentions PromQL."""
        assert "promql" in OBSERVER_QUERY_PROMPT.lower()
    
    def test_query_prompt_has_placeholders(self):
        """Test prompt has required placeholders."""
        assert "{issue}" in OBSERVER_QUERY_PROMPT
        assert "{service}" in OBSERVER_QUERY_PROMPT


class TestCommunicatorPrompts:
    """Tests for communicator prompts."""
    
    def test_incident_prompt_exists(self):
        """Test incident prompt exists."""
        assert COMMUNICATOR_INCIDENT_PROMPT is not None
    
    def test_incident_prompt_has_placeholders(self):
        """Test incident prompt has placeholders."""
        assert "{status}" in COMMUNICATOR_INCIDENT_PROMPT
        assert "{impact}" in COMMUNICATOR_INCIDENT_PROMPT


class TestUtilityPrompts:
    """Tests for utility prompts."""
    
    def test_logs_prompt_exists(self):
        """Test logs summarization prompt exists."""
        assert SUMMARIZE_LOGS_PROMPT is not None
        assert "{logs}" in SUMMARIZE_LOGS_PROMPT
    
    def test_metric_prompt_exists(self):
        """Test metric explanation prompt exists."""
        assert EXPLAIN_METRIC_PROMPT is not None
        assert "{metric_name}" in EXPLAIN_METRIC_PROMPT


class TestPromptFormatting:
    """Tests for prompt formatting."""
    
    def test_reasoner_analysis_full_format(self):
        """Test full formatting of reasoner analysis prompt."""
        formatted = REASONER_ANALYSIS_PROMPT.format(
            issue="Service api-gateway returning 500 errors",
            observations="""
            - Error rate: 15%
            - Pod restarts: 3
            - Memory: 85%
            """,
            runbook_context="Check application logs for exceptions",
        )
        
        assert "api-gateway" in formatted
        assert "15%" in formatted
        assert "Check application" in formatted
    
    def test_actor_action_full_format(self):
        """Test full formatting of actor action prompt."""
        formatted = ACTOR_ACTION_PROMPT.format(
            root_cause="Memory leak causing OOM kills",
            confidence="85%",
            analysis="Memory usage steadily increasing",
            namespace="production",
            runbook_context="Scale horizontally or restart pods",
        )
        
        assert "Memory leak" in formatted
        assert "production" in formatted
    
    def test_observer_query_full_format(self):
        """Test full formatting of observer query prompt."""
        formatted = OBSERVER_QUERY_PROMPT.format(
            issue="High latency",
            service="payment-service",
            namespace="prod",
        )
        
        assert "High latency" in formatted
        assert "payment-service" in formatted
