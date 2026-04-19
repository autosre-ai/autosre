"""
Unit Tests for Configuration

Tests the configuration management functionality including:
- Settings loading
- Default values
- Environment variable parsing
- Computed properties
"""

import pytest
import os
from unittest.mock import patch
from pathlib import Path


class TestSettingsDefaults:
    """Tests for default configuration values."""
    
    def test_default_llm_provider(self):
        """Test default LLM provider is ollama."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.llm_provider == "ollama"
    
    def test_default_ollama_host(self):
        """Test default Ollama host."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.ollama_host == "http://localhost:11434"
    
    def test_default_prometheus_url(self):
        """Test default Prometheus URL."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.prometheus_url == "http://localhost:9090"
    
    def test_default_ui_port(self):
        """Test default UI port."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.ui_port == 8080
    
    def test_default_confidence_threshold(self):
        """Test default confidence threshold."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.confidence_threshold == 0.7
    
    def test_default_max_iterations(self):
        """Test default max iterations."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.max_iterations == 10
    
    def test_default_timeout_seconds(self):
        """Test default timeout."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.timeout_seconds == 300
    
    def test_default_require_approval(self):
        """Test default require approval setting."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.require_approval is True


class TestSettingsEnvironmentVariables:
    """Tests for environment variable loading."""
    
    def test_load_llm_provider_from_env(self):
        """Test loading LLM provider from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_LLM_PROVIDER": "openai"}, clear=True):
            settings = Settings()
            assert settings.llm_provider == "openai"
    
    def test_load_prometheus_url_from_env(self):
        """Test loading Prometheus URL from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_PROMETHEUS_URL": "http://prom:9090"}, clear=True):
            settings = Settings()
            assert settings.prometheus_url == "http://prom:9090"
    
    def test_load_openai_api_key_from_env(self):
        """Test loading OpenAI API key from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_OPENAI_API_KEY": "sk-test123"}, clear=True):
            settings = Settings()
            assert settings.openai_api_key == "sk-test123"
    
    def test_load_namespaces_from_env(self):
        """Test loading namespaces from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_K8S_NAMESPACES": "prod,staging,dev"}, clear=True):
            settings = Settings()
            assert settings.k8s_namespaces == "prod,staging,dev"
    
    def test_load_confidence_threshold_from_env(self):
        """Test loading confidence threshold from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_CONFIDENCE_THRESHOLD": "0.85"}, clear=True):
            settings = Settings()
            assert settings.confidence_threshold == 0.85
    
    def test_load_require_approval_false(self):
        """Test loading require_approval=false from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_REQUIRE_APPROVAL": "false"}, clear=True):
            settings = Settings()
            assert settings.require_approval is False


class TestSettingsComputedProperties:
    """Tests for computed properties."""
    
    def test_namespaces_property_single(self):
        """Test namespaces property with single namespace."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_K8S_NAMESPACES": "default"}, clear=True):
            settings = Settings()
            assert settings.namespaces == ["default"]
    
    def test_namespaces_property_multiple(self):
        """Test namespaces property with multiple namespaces."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_K8S_NAMESPACES": "prod, staging, dev"}, clear=True):
            settings = Settings()
            assert settings.namespaces == ["prod", "staging", "dev"]
    
    def test_namespaces_property_strips_whitespace(self):
        """Test namespaces property strips whitespace."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_K8S_NAMESPACES": "  prod  ,  staging  "}, clear=True):
            settings = Settings()
            assert settings.namespaces == ["prod", "staging"]
    
    def test_kubeconfig_path_property_none(self):
        """Test kubeconfig_path when not set."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.kubeconfig_path is None
    
    def test_kubeconfig_path_property_set(self):
        """Test kubeconfig_path when set."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_KUBECONFIG": "~/.kube/config"}, clear=True):
            settings = Settings()
            path = settings.kubeconfig_path
            assert path is not None
            assert isinstance(path, Path)
    
    def test_kubeconfig_path_expands_home(self):
        """Test kubeconfig_path expands ~ to home directory."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_KUBECONFIG": "~/.kube/config"}, clear=True):
            settings = Settings()
            path = settings.kubeconfig_path
            assert "~" not in str(path)
    
    def test_slack_enabled_true(self):
        """Test slack_enabled when token is set."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            settings = Settings()
            assert settings.slack_enabled is True
    
    def test_slack_enabled_false(self):
        """Test slack_enabled when token is not set."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.slack_enabled is False


class TestSettingsValidation:
    """Tests for settings validation."""
    
    def test_llm_provider_valid_values(self):
        """Test LLM provider accepts valid values."""
        from opensre_core.config import Settings
        
        for provider in ["ollama", "openai", "anthropic"]:
            with patch.dict(os.environ, {"OPENSRE_LLM_PROVIDER": provider}, clear=True):
                settings = Settings()
                assert settings.llm_provider == provider
    
    def test_log_format_valid_values(self):
        """Test log format accepts valid values."""
        from opensre_core.config import Settings
        
        for fmt in ["json", "text"]:
            with patch.dict(os.environ, {"OPENSRE_LOG_FORMAT": fmt}, clear=True):
                settings = Settings()
                assert settings.log_format == fmt


class TestSettingsVersion:
    """Tests for version configuration."""
    
    def test_version_default(self):
        """Test default version."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.version == "0.1.0"


class TestSettingsSlack:
    """Tests for Slack configuration."""
    
    def test_default_slack_channel(self):
        """Test default Slack channel."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.slack_channel == "#incidents"
    
    def test_slack_channel_from_env(self):
        """Test Slack channel from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_SLACK_CHANNEL": "#alerts"}, clear=True):
            settings = Settings()
            assert settings.slack_channel == "#alerts"


class TestSettingsRunbooks:
    """Tests for runbooks configuration."""
    
    def test_default_runbooks_path(self):
        """Test default runbooks path."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.runbooks_path == "./runbooks"
    
    def test_runbooks_path_from_env(self):
        """Test runbooks path from environment."""
        from opensre_core.config import Settings
        
        with patch.dict(os.environ, {"OPENSRE_RUNBOOKS_PATH": "/etc/opensre/runbooks"}, clear=True):
            settings = Settings()
            assert settings.runbooks_path == "/etc/opensre/runbooks"


class TestGlobalSettings:
    """Tests for global settings instance."""
    
    def test_global_settings_exists(self):
        """Test global settings instance exists."""
        from opensre_core.config import settings
        
        assert settings is not None
    
    def test_global_settings_is_singleton(self):
        """Test global settings is the same instance."""
        from opensre_core import config
        
        settings1 = config.settings
        settings2 = config.settings
        
        assert settings1 is settings2
