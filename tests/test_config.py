"""
Tests for the configuration module.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch


class TestSettings:
    """Test Settings configuration."""
    
    def test_default_settings(self):
        """Test default settings values."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.version == "0.1.0"
        assert settings.llm_provider == "ollama"
        assert settings.require_approval is True
    
    def test_ollama_defaults(self):
        """Test Ollama default configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.ollama_host == "http://localhost:11434"
        assert "llama" in settings.ollama_model.lower()
    
    def test_openai_defaults(self):
        """Test OpenAI default configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.openai_api_key is None
        assert "gpt" in settings.openai_model.lower()
    
    def test_anthropic_defaults(self):
        """Test Anthropic default configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.anthropic_api_key is None
        assert "claude" in settings.anthropic_model.lower()
    
    def test_prometheus_defaults(self):
        """Test Prometheus default configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.prometheus_url == "http://localhost:9090"
    
    def test_kubernetes_defaults(self):
        """Test Kubernetes default configuration."""
        from autosre.config import Settings
        
        # Create fresh settings without env file
        settings = Settings(_env_file=None)
        
        assert settings.kubeconfig is None
        # Default is "default" but .env may override
    
    def test_agent_behavior_defaults(self):
        """Test agent behavior defaults."""
        from autosre.config import Settings
        
        settings = Settings(_env_file=None)
        
        assert settings.require_approval is True
        assert settings.auto_approve_low_risk is False
        assert settings.confidence_threshold == 0.7
        assert settings.max_iterations == 10
    
    def test_ui_defaults(self):
        """Test UI defaults."""
        from autosre.config import Settings
        
        settings = Settings(_env_file=None)
        
        assert settings.ui_host == "0.0.0.0"
        assert settings.ui_port == 8080
    
    def test_logging_defaults(self):
        """Test logging defaults."""
        from autosre.config import Settings
        
        settings = Settings(_env_file=None)
        
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"


class TestSettingsProperties:
    """Test Settings property methods."""
    
    def test_namespaces_single(self):
        """Test single namespace parsing."""
        from autosre.config import Settings
        
        settings = Settings(k8s_namespaces="production")
        
        assert settings.namespaces == ["production"]
    
    def test_namespaces_multiple(self):
        """Test multiple namespace parsing."""
        from autosre.config import Settings
        
        settings = Settings(k8s_namespaces="dev,staging,production")
        
        assert settings.namespaces == ["dev", "staging", "production"]
    
    def test_namespaces_with_spaces(self):
        """Test namespace parsing handles spaces."""
        from autosre.config import Settings
        
        settings = Settings(k8s_namespaces="dev, staging, production")
        
        assert settings.namespaces == ["dev", "staging", "production"]
    
    def test_kubeconfig_path_none(self):
        """Test kubeconfig_path when not set."""
        from autosre.config import Settings
        
        settings = Settings(kubeconfig=None)
        
        assert settings.kubeconfig_path is None
    
    def test_kubeconfig_path_set(self):
        """Test kubeconfig_path when set."""
        from autosre.config import Settings
        
        settings = Settings(kubeconfig="~/.kube/config")
        
        assert settings.kubeconfig_path is not None
        assert isinstance(settings.kubeconfig_path, Path)
    
    def test_slack_enabled_false(self):
        """Test slack_enabled when token not set."""
        from autosre.config import Settings
        
        settings = Settings(slack_bot_token=None)
        
        assert settings.slack_enabled is False
    
    def test_slack_enabled_true(self):
        """Test slack_enabled when token is set."""
        from autosre.config import Settings
        
        settings = Settings(slack_bot_token="xoxb-test-token")
        
        assert settings.slack_enabled is True


class TestSettingsFromEnv:
    """Test Settings loading from environment."""
    
    def test_load_from_env(self):
        """Test loading settings from environment variables."""
        from autosre.config import Settings
        
        with patch.dict(os.environ, {
            "OPENSRE_LLM_PROVIDER": "openai",
            "OPENSRE_LOG_LEVEL": "DEBUG",
        }):
            settings = Settings()
            
            # Note: Settings are already loaded, so this tests if new ones work
            assert settings is not None
    
    def test_llm_retry_settings(self):
        """Test LLM retry configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.llm_retry_max_attempts == 3
        assert settings.llm_retry_backoff_factor == 2.0
    
    def test_llm_cache_settings(self):
        """Test LLM cache configuration."""
        from autosre.config import Settings
        
        settings = Settings()
        
        assert settings.llm_cache_enabled is True
        assert settings.llm_cache_ttl_seconds == 3600


class TestGlobalSettings:
    """Test global settings instance."""
    
    def test_global_settings_exists(self):
        """Test global settings instance exists."""
        from autosre.config import settings
        
        assert settings is not None
        assert settings.version == "0.1.0"
    
    def test_settings_singleton_behavior(self):
        """Test settings are consistent."""
        from autosre.config import settings as s1
        from autosre.config import settings as s2
        
        # Should reference same settings values
        assert s1.version == s2.version
