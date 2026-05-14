"""Tests for configuration."""

import os
import pytest
from pathlib import Path

from autosre.core.config import (
    Settings,
    LLMProviderType,
    get_settings,
    reload_settings,
)


class TestSettings:
    """Test Settings configuration."""
    
    def test_default_settings(self):
        """Test default configuration."""
        settings = Settings()
        
        assert settings.default_provider == LLMProviderType.OPENAI
        assert settings.cache.enabled is True
        assert settings.retry.max_retries == 3
    
    def test_provider_settings(self):
        """Test provider-specific settings."""
        settings = Settings()
        
        openai = settings.get_provider_settings(LLMProviderType.OPENAI)
        assert openai.default_model == "gpt-4-turbo"
        
        anthropic = settings.get_provider_settings(LLMProviderType.ANTHROPIC)
        assert "claude" in anthropic.default_model
    
    def test_token_limits(self):
        """Test token limit configuration."""
        settings = Settings()
        
        limits = settings.tokens.model_limits.get("gpt-4")
        assert limits is not None
        assert limits["context_window"] > 0


class TestSettingsCache:
    """Test settings caching."""
    
    def test_cached_settings(self):
        """Test that get_settings returns cached instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
    
    def test_reload_settings(self):
        """Test settings reload."""
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2
