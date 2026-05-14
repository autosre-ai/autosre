"""Configuration management for AutoSRE V2."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "AutoSRE V2"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://localhost/autosre",
        description="PostgreSQL connection URL (async driver)"
    )
    
    # Redis (for caching/queuing)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # LLM Configuration
    llm_provider: str = Field(default="openai", description="LLM provider (openai, anthropic)")
    llm_model: str = Field(default="gpt-4o", description="Model name")
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key")
    llm_temperature: float = Field(default=0.1, description="Model temperature")
    llm_max_tokens: int = Field(default=4096, description="Max output tokens")
    
    # Alertmanager
    alertmanager_url: str = Field(
        default="http://localhost:9093",
        description="Alertmanager URL"
    )
    alertmanager_webhook_secret: Optional[str] = Field(
        default=None,
        description="Webhook secret for signature verification"
    )
    
    # Investigation settings
    max_investigation_depth: int = Field(
        default=10,
        description="Maximum depth of investigation loops"
    )
    investigation_timeout_seconds: int = Field(
        default=300,
        description="Timeout for investigations"
    )
    require_approval_for_actions: bool = Field(
        default=True,
        description="Require human approval for remediation actions"
    )
    
    # Kubernetes
    kubernetes_enabled: bool = Field(default=True)
    kubernetes_namespace: Optional[str] = Field(default=None)
    
    # Prometheus
    prometheus_url: str = Field(
        default="http://localhost:9090",
        description="Prometheus URL for metrics queries"
    )
    
    # Loki (logs)
    loki_url: Optional[str] = Field(
        default=None,
        description="Loki URL for log queries"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
