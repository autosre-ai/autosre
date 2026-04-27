"""
AutoSRE Exceptions - User-friendly, actionable error messages.

All exceptions provide:
- Clear description of what went wrong
- Actionable suggestions for fixing the issue
- Context about what the system was trying to do
"""

from typing import Optional


class AutoSREError(Exception):
    """Base exception for all AutoSRE errors."""
    
    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        self.message = message
        self.suggestion = suggestion
        self.context = context or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format the full error message with suggestion."""
        parts = [self.message]
        if self.suggestion:
            parts.append(f"\n💡 Suggestion: {self.suggestion}")
        return "".join(parts)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "suggestion": self.suggestion,
            "context": self.context,
        }


# ==================== Configuration Errors ====================

class ConfigurationError(AutoSREError):
    """Error in configuration or setup."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""
    
    def __init__(self, config_key: str, env_var: Optional[str] = None):
        suggestion = f"Set the '{config_key}' in your config file"
        if env_var:
            suggestion += f" or set the {env_var} environment variable"
        
        super().__init__(
            message=f"Missing required configuration: {config_key}",
            suggestion=suggestion,
            context={"config_key": config_key, "env_var": env_var},
        )


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""
    
    def __init__(self, config_key: str, value: str, expected: str):
        super().__init__(
            message=f"Invalid configuration for '{config_key}': got '{value}'",
            suggestion=f"Expected: {expected}",
            context={"config_key": config_key, "value": value, "expected": expected},
        )


# ==================== Connection Errors ====================

class ConnectionError(AutoSREError):
    """Error connecting to external service."""
    pass


class KubernetesConnectionError(ConnectionError):
    """Cannot connect to Kubernetes cluster."""
    
    def __init__(self, details: Optional[str] = None):
        message = "Cannot connect to Kubernetes cluster"
        if details:
            message += f": {details}"
        
        super().__init__(
            message=message,
            suggestion=(
                "Check that:\n"
                "  1. Your kubeconfig is valid: kubectl config current-context\n"
                "  2. The cluster is reachable: kubectl cluster-info\n"
                "  3. Your credentials haven't expired (for cloud clusters)"
            ),
        )


class PrometheusConnectionError(ConnectionError):
    """Cannot connect to Prometheus."""
    
    def __init__(self, url: str, details: Optional[str] = None):
        message = f"Cannot connect to Prometheus at {url}"
        if details:
            message += f": {details}"
        
        super().__init__(
            message=message,
            suggestion=(
                "Check that:\n"
                "  1. Prometheus URL is correct in config\n"
                "  2. Prometheus is running and accessible\n"
                "  3. Any required authentication is configured"
            ),
            context={"url": url},
        )


class LLMConnectionError(ConnectionError):
    """Cannot connect to LLM provider."""
    
    def __init__(self, provider: str, details: Optional[str] = None):
        message = f"Cannot connect to {provider}"
        if details:
            message += f": {details}"
        
        suggestions = {
            "ollama": (
                "Check that:\n"
                "  1. Ollama is running: ollama list\n"
                "  2. The model is pulled: ollama pull llama3.2\n"
                "  3. OLLAMA_HOST is set correctly (default: http://localhost:11434)"
            ),
            "openai": (
                "Check that:\n"
                "  1. OPENAI_API_KEY is set\n"
                "  2. Your API key is valid\n"
                "  3. You have available credits/quota"
            ),
            "anthropic": (
                "Check that:\n"
                "  1. ANTHROPIC_API_KEY is set\n"
                "  2. Your API key is valid\n"
                "  3. You have available credits/quota"
            ),
        }
        
        super().__init__(
            message=message,
            suggestion=suggestions.get(provider.lower(), f"Check your {provider} configuration"),
            context={"provider": provider},
        )


# ==================== Context Errors ====================

class ContextError(AutoSREError):
    """Error related to context store or data."""
    pass


class ServiceNotFoundError(ContextError):
    """Service not found in context store."""
    
    def __init__(self, service_name: str, namespace: Optional[str] = None):
        location = f"'{service_name}'"
        if namespace:
            location += f" in namespace '{namespace}'"
        
        super().__init__(
            message=f"Service {location} not found",
            suggestion=(
                "Try:\n"
                "  1. Sync services from Kubernetes: autosre context sync\n"
                "  2. Check the service name is correct\n"
                "  3. Verify the service exists: kubectl get svc"
            ),
            context={"service_name": service_name, "namespace": namespace},
        )


class NoContextDataError(ContextError):
    """No context data available."""
    
    def __init__(self, data_type: str = "services"):
        super().__init__(
            message=f"No {data_type} found in context store",
            suggestion=(
                "Initialize context data:\n"
                "  1. Connect to your cluster: autosre init\n"
                "  2. Sync services: autosre context sync\n"
                "  3. Import ownership data: autosre context import-ownership"
            ),
        )


# ==================== Agent Errors ====================

class AgentError(AutoSREError):
    """Error in agent processing."""
    pass


class InvestigationError(AgentError):
    """Error during incident investigation."""
    
    def __init__(self, phase: str, details: str):
        super().__init__(
            message=f"Investigation failed during {phase}: {details}",
            suggestion="Check the logs for more details. Try running with --verbose for debug output.",
            context={"phase": phase},
        )


class ActionBlockedError(AgentError):
    """Action was blocked by guardrails."""
    
    def __init__(self, action: str, reason: str, risk_level: str = "unknown"):
        super().__init__(
            message=f"Action blocked: {reason}",
            suggestion=(
                "This action was blocked for safety. Options:\n"
                "  1. Review the action and approve manually if safe\n"
                "  2. Check your guardrails configuration\n"
                "  3. Run with lower risk tolerance if needed"
            ),
            context={"action": action, "reason": reason, "risk_level": risk_level},
        )


class ApprovalRequiredError(AgentError):
    """Action requires human approval."""
    
    def __init__(self, action_id: str, description: str, risk_level: str):
        super().__init__(
            message=f"Action requires approval (risk: {risk_level})",
            suggestion=(
                f"Approve with: autosre action approve {action_id}\n"
                f"Or reject with: autosre action reject {action_id}"
            ),
            context={"action_id": action_id, "description": description},
        )


# ==================== Sandbox Errors ====================

class SandboxError(AutoSREError):
    """Error in sandbox environment."""
    pass


class SandboxNotRunningError(SandboxError):
    """Sandbox cluster is not running."""
    
    def __init__(self):
        super().__init__(
            message="Sandbox cluster is not running",
            suggestion=(
                "Start the sandbox:\n"
                "  1. autosre sandbox start\n"
                "  2. Wait for cluster to be ready\n"
                "  3. Verify: autosre sandbox status"
            ),
        )


class SandboxCreationError(SandboxError):
    """Failed to create sandbox."""
    
    def __init__(self, details: str):
        super().__init__(
            message=f"Failed to create sandbox: {details}",
            suggestion=(
                "Check that:\n"
                "  1. Docker is running: docker ps\n"
                "  2. Kind is installed: kind version\n"
                "  3. Sufficient resources are available"
            ),
        )


# ==================== Eval Errors ====================

class EvalError(AutoSREError):
    """Error in evaluation framework."""
    pass


class ScenarioNotFoundError(EvalError):
    """Evaluation scenario not found."""
    
    def __init__(self, scenario_name: str):
        super().__init__(
            message=f"Scenario '{scenario_name}' not found",
            suggestion=(
                "List available scenarios: autosre eval list\n"
                "Or create a custom scenario in ~/.autosre/scenarios/"
            ),
            context={"scenario_name": scenario_name},
        )


class ScenarioParseError(EvalError):
    """Failed to parse scenario file."""
    
    def __init__(self, filename: str, error: str):
        super().__init__(
            message=f"Failed to parse scenario '{filename}': {error}",
            suggestion="Check the scenario YAML syntax and required fields",
            context={"filename": filename, "parse_error": error},
        )


# ==================== Authentication Errors ====================

class AuthenticationError(AutoSREError):
    """Authentication failed."""
    
    def __init__(self, details: Optional[str] = None):
        message = "Authentication required"
        if details:
            message += f": {details}"
        
        super().__init__(
            message=message,
            suggestion=(
                "Authenticate with:\n"
                "  1. API key: Set OPENSRE_API_KEY environment variable\n"
                "  2. Token: Use autosre auth login"
            ),
        )


class PermissionDeniedError(AutoSREError):
    """User doesn't have required permissions."""
    
    def __init__(self, action: str, required_role: Optional[str] = None):
        message = f"Permission denied for action: {action}"
        suggestion = "Contact your administrator for access"
        if required_role:
            suggestion = f"Required role: {required_role}. Contact your administrator for access."
        
        super().__init__(
            message=message,
            suggestion=suggestion,
            context={"action": action, "required_role": required_role},
        )
