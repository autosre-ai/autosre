"""Tests for prompt templates."""

import pytest

from autosre.core.prompts import PromptTemplates


class TestPromptTemplates:
    """Test PromptTemplates."""
    
    def test_triage_prompt(self):
        """Test triage prompt rendering."""
        prompt = PromptTemplates.triage(
            alert_context="High CPU on api-server",
            additional_context="Recent deployment 1h ago",
        )
        
        assert "High CPU on api-server" in prompt
        assert "Recent deployment" in prompt
        assert "Severity Assessment" in prompt
    
    def test_investigation_prompt(self):
        """Test investigation prompt rendering."""
        prompt = PromptTemplates.investigate(
            alert_context="Memory alert",
            hypotheses="1. Memory leak\n2. Cache overflow",
            observations="Memory at 95%",
        )
        
        assert "Memory alert" in prompt
        assert "Memory leak" in prompt
        assert "Evidence Analysis" in prompt
    
    def test_root_cause_prompt(self):
        """Test root cause prompt rendering."""
        prompt = PromptTemplates.root_cause(
            alert_context="Service unavailable",
            investigation_summary="Checked metrics and logs",
            confirmed_hypotheses="Database connection exhaustion",
            key_observations="Connection pool at 100%",
        )
        
        assert "Root Cause" in prompt
        assert "Database connection exhaustion" in prompt
    
    def test_remediate_prompt(self):
        """Test remediation prompt rendering."""
        prompt = PromptTemplates.remediate(
            root_cause="Connection pool exhaustion",
            current_state="Service degraded",
            available_tools="kubectl, prometheus",
        )
        
        assert "Connection pool exhaustion" in prompt
        assert "Immediate Actions" in prompt
        assert "Rollback Plan" in prompt
    
    def test_chat_prompt(self):
        """Test chat prompt rendering."""
        prompt = PromptTemplates.chat(
            investigation_context="Looking at API latency",
            recent_observations="p99 latency spiked to 5s",
            user_question="What could cause this?",
        )
        
        assert "What could cause this?" in prompt
        assert "p99 latency" in prompt
    
    def test_render_by_name(self):
        """Test rendering by template name."""
        prompt = PromptTemplates.render(
            "TRIAGE_PROMPT",
            alert_context="Test alert",
            additional_context="None",
        )
        
        assert "Test alert" in prompt
    
    def test_render_invalid_template(self):
        """Test error on invalid template name."""
        with pytest.raises(ValueError):
            PromptTemplates.render("INVALID_TEMPLATE")
