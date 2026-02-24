"""
OpenSRE Configuration
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
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
    llm_provider: Literal["ollama", "openai", "anthropic"] = "ollama"
    
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    
    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4-turbo-preview"
    
    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-sonnet-20240229"
    
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
