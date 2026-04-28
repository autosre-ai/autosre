"""
Tests for AutoSRE exception classes.
"""

import pytest
from autosre.exceptions import (
    AutoSREError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    KubernetesConnectionError,
    PrometheusConnectionError,
    LLMConnectionError,
    ContextError,
    ServiceNotFoundError,
    NoContextDataError,
    AgentError,
    InvestigationError,
    ActionBlockedError,
    ApprovalRequiredError,
    SandboxError,
    SandboxNotRunningError,
    SandboxCreationError,
    EvalError,
    ScenarioNotFoundError,
    ScenarioParseError,
    AuthenticationError,
    PermissionDeniedError,
)


class TestAutoSREErrorBase:
    """Tests for base AutoSREError class."""
    
    def test_basic_error(self):
        """Test creating basic error."""
        error = AutoSREError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.suggestion is None
        assert error.context == {}
    
    def test_error_with_suggestion(self):
        """Test error with suggestion."""
        error = AutoSREError(
            "Something went wrong",
            suggestion="Try restarting"
        )
        assert "Something went wrong" in str(error)
        assert "Try restarting" in str(error)
        assert "💡" in str(error)
    
    def test_error_with_context(self):
        """Test error with context dict."""
        error = AutoSREError(
            "Failed",
            context={"key": "value", "code": 123}
        )
        assert error.context == {"key": "value", "code": 123}
    
    def test_to_dict(self):
        """Test error serialization."""
        error = AutoSREError(
            "Test error",
            suggestion="Fix it",
            context={"foo": "bar"}
        )
        result = error.to_dict()
        
        assert result["error"] == "AutoSREError"
        assert result["message"] == "Test error"
        assert result["suggestion"] == "Fix it"
        assert result["context"] == {"foo": "bar"}


class TestConfigurationErrors:
    """Tests for configuration-related errors."""
    
    def test_missing_config_error(self):
        """Test MissingConfigError."""
        error = MissingConfigError("api_key", env_var="AUTOSRE_API_KEY")
        
        assert "api_key" in str(error)
        assert "AUTOSRE_API_KEY" in str(error)
        assert error.context["config_key"] == "api_key"
        assert error.context["env_var"] == "AUTOSRE_API_KEY"
    
    def test_missing_config_without_env_var(self):
        """Test MissingConfigError without env var suggestion."""
        error = MissingConfigError("prometheus_url")
        
        assert "prometheus_url" in str(error)
        assert error.context["env_var"] is None
    
    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        error = InvalidConfigError(
            "log_level",
            value="SUPER",
            expected="One of: DEBUG, INFO, WARNING, ERROR"
        )
        
        assert "log_level" in str(error)
        assert "SUPER" in str(error)
        assert "One of:" in str(error)


class TestConnectionErrors:
    """Tests for connection-related errors."""
    
    def test_kubernetes_connection_error(self):
        """Test KubernetesConnectionError."""
        error = KubernetesConnectionError()
        
        assert "Kubernetes" in str(error)
        assert "kubectl" in str(error)
        assert "kubeconfig" in str(error)
    
    def test_kubernetes_connection_with_details(self):
        """Test KubernetesConnectionError with details."""
        error = KubernetesConnectionError("Connection refused")
        
        assert "Connection refused" in str(error)
    
    def test_prometheus_connection_error(self):
        """Test PrometheusConnectionError."""
        error = PrometheusConnectionError("http://prometheus:9090")
        
        assert "Prometheus" in str(error)
        assert "http://prometheus:9090" in str(error)
        assert error.context["url"] == "http://prometheus:9090"
    
    def test_prometheus_connection_with_details(self):
        """Test PrometheusConnectionError with details."""
        error = PrometheusConnectionError(
            "http://localhost:9090",
            details="Connection timeout"
        )
        
        assert "Connection timeout" in str(error)
    
    def test_llm_connection_ollama(self):
        """Test LLMConnectionError for Ollama."""
        error = LLMConnectionError("ollama")
        
        assert "ollama" in str(error).lower()
        assert "ollama list" in str(error) or "OLLAMA_HOST" in str(error)
    
    def test_llm_connection_openai(self):
        """Test LLMConnectionError for OpenAI."""
        error = LLMConnectionError("openai")
        
        assert "openai" in str(error).lower()
        assert "OPENAI_API_KEY" in str(error)
    
    def test_llm_connection_anthropic(self):
        """Test LLMConnectionError for Anthropic."""
        error = LLMConnectionError("anthropic")
        
        assert "ANTHROPIC_API_KEY" in str(error)
    
    def test_llm_connection_unknown_provider(self):
        """Test LLMConnectionError for unknown provider."""
        error = LLMConnectionError("some-provider", details="Error details")
        
        assert "some-provider" in str(error)
        assert "Error details" in str(error)


class TestContextErrors:
    """Tests for context-related errors."""
    
    def test_service_not_found(self):
        """Test ServiceNotFoundError."""
        error = ServiceNotFoundError("api-gateway")
        
        assert "api-gateway" in str(error)
        assert "sync" in str(error).lower()
    
    def test_service_not_found_with_namespace(self):
        """Test ServiceNotFoundError with namespace."""
        error = ServiceNotFoundError("frontend", namespace="production")
        
        assert "frontend" in str(error)
        assert "production" in str(error)
        assert error.context["namespace"] == "production"
    
    def test_no_context_data(self):
        """Test NoContextDataError."""
        error = NoContextDataError("runbooks")
        
        assert "runbooks" in str(error)
        assert "sync" in str(error).lower()
    
    def test_no_context_data_default(self):
        """Test NoContextDataError default."""
        error = NoContextDataError()
        
        assert "services" in str(error)


class TestAgentErrors:
    """Tests for agent-related errors."""
    
    def test_investigation_error(self):
        """Test InvestigationError."""
        error = InvestigationError("analysis", "Timeout waiting for metrics")
        
        assert "analysis" in str(error)
        assert "Timeout" in str(error)
        assert error.context["phase"] == "analysis"
    
    def test_action_blocked(self):
        """Test ActionBlockedError."""
        error = ActionBlockedError(
            action="kubectl delete pod",
            reason="Destructive actions blocked",
            risk_level="high"
        )
        
        assert "blocked" in str(error).lower()
        assert "Destructive" in str(error)
        assert error.context["risk_level"] == "high"
    
    def test_approval_required(self):
        """Test ApprovalRequiredError."""
        error = ApprovalRequiredError(
            action_id="action-123",
            description="Restart deployment",
            risk_level="medium"
        )
        
        assert "approval" in str(error).lower()
        assert "medium" in str(error)
        assert "action-123" in str(error)


class TestSandboxErrors:
    """Tests for sandbox-related errors."""
    
    def test_sandbox_not_running(self):
        """Test SandboxNotRunningError."""
        error = SandboxNotRunningError()
        
        assert "not running" in str(error).lower()
        assert "sandbox start" in str(error)
    
    def test_sandbox_creation_error(self):
        """Test SandboxCreationError."""
        error = SandboxCreationError("Docker daemon not running")
        
        assert "Docker" in str(error)
        assert "docker ps" in str(error).lower() or "Docker" in str(error)


class TestEvalErrors:
    """Tests for evaluation-related errors."""
    
    def test_scenario_not_found(self):
        """Test ScenarioNotFoundError."""
        error = ScenarioNotFoundError("nonexistent-scenario")
        
        assert "nonexistent-scenario" in str(error)
        assert "eval list" in str(error)
        assert error.context["scenario_name"] == "nonexistent-scenario"
    
    def test_scenario_parse_error(self):
        """Test ScenarioParseError."""
        error = ScenarioParseError("custom.yaml", "Invalid YAML syntax at line 5")
        
        assert "custom.yaml" in str(error)
        assert "line 5" in str(error)
        assert error.context["filename"] == "custom.yaml"


class TestAuthErrors:
    """Tests for authentication errors."""
    
    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError()
        
        assert "Authentication" in str(error)
        assert "OPENSRE_API_KEY" in str(error) or "auth" in str(error).lower()
    
    def test_authentication_with_details(self):
        """Test AuthenticationError with details."""
        error = AuthenticationError("Token expired")
        
        assert "Token expired" in str(error)
    
    def test_permission_denied(self):
        """Test PermissionDeniedError."""
        error = PermissionDeniedError("delete_pod")
        
        assert "delete_pod" in str(error)
        assert "Permission" in str(error)
    
    def test_permission_denied_with_role(self):
        """Test PermissionDeniedError with required role."""
        error = PermissionDeniedError("admin_action", required_role="admin")
        
        assert "admin" in str(error)
        assert error.context["required_role"] == "admin"


class TestExceptionInheritance:
    """Tests for exception inheritance."""
    
    def test_config_error_is_autosre_error(self):
        """Test ConfigurationError inherits from AutoSREError."""
        error = ConfigurationError("Config issue")
        assert isinstance(error, AutoSREError)
    
    def test_missing_config_is_configuration_error(self):
        """Test MissingConfigError inherits from ConfigurationError."""
        error = MissingConfigError("key")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, AutoSREError)
    
    def test_sandbox_error_is_autosre_error(self):
        """Test SandboxError inherits from AutoSREError."""
        error = SandboxError("Sandbox issue")
        assert isinstance(error, AutoSREError)
    
    def test_eval_error_is_autosre_error(self):
        """Test EvalError inherits from AutoSREError."""
        error = EvalError("Eval issue")
        assert isinstance(error, AutoSREError)
