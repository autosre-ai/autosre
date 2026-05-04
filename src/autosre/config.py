"""
OpenSRE Configuration
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="OPENSRE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Version
    version: str = "0.1.0"

    # LLM Configuration
    llm_provider: Literal["ollama", "openai", "anthropic", "azure"] = "ollama"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Azure OpenAI
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str = "gpt-4"
    azure_openai_api_version: str = "2024-02-01"

    # LLM Behavior
    llm_retry_max_attempts: int = 3
    llm_retry_backoff_factor: float = 2.0
    llm_cache_enabled: bool = True
    llm_cache_ttl_seconds: int = 3600

    # Prometheus
    prometheus_url: str = "http://localhost:9090"

    # Kubernetes
    kubeconfig: str | None = None
    k8s_namespaces: str = "default"

    # Loki
    loki_url: str | None = None

    # Slack Integration
    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    slack_channel: str = "#incidents"

    # PagerDuty Integration
    pagerduty_api_key: str | None = None

    # Alertmanager webhook
    alertmanager_webhook_path: str = "/webhook/alert"

    # UI
    ui_host: str = "0.0.0.0"
    ui_port: int = 8080
    ui_reload: bool = False

    # Agent Behavior
    require_approval: bool = True
    auto_approve_low_risk: bool = False
    confidence_threshold: float = 0.7
    max_iterations: int = 10
    timeout_seconds: int = 300

    # Runbooks
    runbooks_path: str = "./runbooks"

    # MCP Client
    mcp_enabled: bool = False
    mcp_config_path: str = "./mcp-clients.json"
    mcp_kubernetes: bool = True  # Use kubernetes-mcp if available
    mcp_prometheus: bool = True  # Use prometheus-mcp if available

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    @property
    def namespaces(self) -> list[str]:
        """Parse comma-separated namespaces into list."""
        return [ns.strip() for ns in self.k8s_namespaces.split(",")]

    @property
    def kubeconfig_path(self) -> Path | None:
        """Expand kubeconfig path."""
        if self.kubeconfig:
            return Path(self.kubeconfig).expanduser()
        return None

    @property
    def slack_enabled(self) -> bool:
        """Check if Slack integration is configured."""
        return self.slack_bot_token is not None


# Global settings instance
settings = Settings()

