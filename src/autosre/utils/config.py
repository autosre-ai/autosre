"""Configuration management.

Handles loading and validating AutoSRE configuration files.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    """LLM configuration."""
    
    provider: str = Field(default="openai", description="LLM provider (openai, anthropic, ollama)")
    model: str = Field(default="gpt-4o", description="Model name")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="Base URL (for Ollama: http://localhost:11434)")
    timeout: float = Field(default=120.0, ge=1.0, description="Request timeout")
    
    # Ollama-specific settings
    ollama_fallback_enabled: bool = Field(
        default=True, 
        description="Enable fallback to another provider if Ollama unavailable"
    )
    ollama_fallback_provider: Optional[str] = Field(
        default="openai",
        description="Fallback provider when Ollama is unavailable"
    )
    ollama_fallback_model: Optional[str] = Field(
        default="gpt-4o-mini",
        description="Fallback model when Ollama is unavailable"
    )


class AlertsConfig(BaseModel):
    """Alert sources configuration."""
    
    sources: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationConfig(BaseModel):
    """Investigation settings."""
    
    auto_start: bool = Field(default=False)
    max_parallel: int = Field(default=3, ge=1, le=10)
    timeout_minutes: int = Field(default=30, ge=1, le=120)
    max_iterations: int = Field(default=3, ge=1, le=10)


class RunbookConfig(BaseModel):
    """Runbook configuration."""
    
    path: str = Field(default="./runbooks")
    auto_execute: bool = Field(default=False)


class ServerConfig(BaseModel):
    """Server configuration."""
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=32)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO")
    format: str = Field(default="json")


# ============================================================================
# Integration Configs (defined BEFORE Config class)
# ============================================================================


class AlertManagerConfig(BaseModel):
    """AlertManager integration configuration."""
    
    url: str = Field(default="http://localhost:9093", description="AlertManager URL")
    timeout: float = Field(default=30.0, ge=1.0, description="Request timeout")
    username: Optional[str] = Field(default=None, description="Basic auth username")
    password: Optional[str] = Field(default=None, description="Basic auth password")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    poll_interval: float = Field(default=30.0, ge=1.0, description="Polling interval")


class PrometheusConfig(BaseModel):
    """Prometheus integration configuration."""
    
    url: str = Field(default="http://localhost:9090", description="Prometheus URL")
    timeout: float = Field(default=30.0, ge=1.0, description="Request timeout")
    username: Optional[str] = Field(default=None, description="Basic auth username")
    password: Optional[str] = Field(default=None, description="Basic auth password")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")


class KubernetesConfig(BaseModel):
    """Kubernetes integration configuration."""
    
    context: Optional[str] = Field(default=None, description="Kubernetes context")
    namespace: str = Field(default="default", description="Default namespace")
    in_cluster: bool = Field(default=False, description="Running in cluster")


class LokiConfig(BaseModel):
    """Loki integration configuration."""
    
    url: str = Field(default="http://localhost:3100", description="Loki URL")
    timeout: float = Field(default=30.0, ge=1.0, description="Request timeout")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")


class AgentConfig(BaseModel):
    """Agent configuration."""
    
    name: str = Field(..., description="Agent name")
    enabled: bool = Field(default=True, description="Whether agent is enabled")
    max_iterations: int = Field(default=10, ge=1, le=50, description="Max iterations")
    timeout_seconds: int = Field(default=300, ge=1, description="Timeout in seconds")
    model: str = Field(default="gpt-4o", description="LLM model to use")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    
    def model_post_init(self, __context):
        """Validate configuration after initialization."""
        if self.max_iterations < 1 or self.max_iterations > 50:
            raise ValueError("max_iterations must be between 1 and 50")
        if self.temperature < 0.0 or self.temperature > 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")


# ============================================================================
# Main Config Class
# ============================================================================


class Config(BaseModel):
    """Main configuration model."""
    
    version: str = Field(default="2.0")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    investigation: InvestigationConfig = Field(default_factory=InvestigationConfig)
    runbooks: RunbookConfig = Field(default_factory=RunbookConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    # Integration configs
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    alertmanager: AlertManagerConfig = Field(default_factory=AlertManagerConfig)
    kubernetes: KubernetesConfig = Field(default_factory=KubernetesConfig)
    loki: LokiConfig = Field(default_factory=LokiConfig)
    agents: InvestigationConfig = Field(default_factory=InvestigationConfig)
    
    def get_llm_config_for_agent(self, agent_id: str) -> LLMConfig:
        """Get LLM config for a specific agent."""
        return self.llm
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file.
        
        Args:
            path: Path to YAML file
            
        Returns:
            Config instance
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        
        # Expand environment variables
        data = cls._expand_env_vars(data)
        
        return cls.model_validate(data)
    
    @classmethod
    def _expand_env_vars(cls, data: Any) -> Any:
        """Recursively expand environment variables in config.
        
        Args:
            data: Configuration data
            
        Returns:
            Data with environment variables expanded
        """
        if isinstance(data, dict):
            return {k: cls._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Expand ${VAR} patterns
            if data.startswith("${") and data.endswith("}"):
                var_name = data[2:-1]
                return os.environ.get(var_name, data)
            return data
        return data


def load_config(
    path: Optional[Path] = None,
    search_paths: Optional[list[Path]] = None,
) -> Config:
    """Load configuration from file.
    
    Searches for configuration in the following order:
    1. Explicit path if provided
    2. .autosre.yaml in current directory
    3. .autosre.yaml in home directory
    
    Args:
        path: Explicit path to config file
        search_paths: Additional paths to search
        
    Returns:
        Loaded configuration
        
    Raises:
        FileNotFoundError: If no config file found
    """
    if path and path.exists():
        return Config.from_yaml(path)
    
    # Default search paths
    paths_to_check = [
        Path.cwd() / ".autosre.yaml",
        Path.cwd() / ".autosre.yml",
        Path.home() / ".autosre.yaml",
        Path.home() / ".config" / "autosre" / "config.yaml",
    ]
    
    if search_paths:
        paths_to_check = list(search_paths) + paths_to_check
    
    for config_path in paths_to_check:
        if config_path.exists():
            return Config.from_yaml(config_path)
    
    # Return default config if no file found
    return Config()


class EnvSettings(BaseSettings):
    """Environment-based settings.
    
    These can be set via environment variables.
    """
    
    autosre_config_path: Optional[str] = Field(default=None)
    autosre_debug: bool = Field(default=False)
    autosre_log_level: str = Field(default="INFO")
    
    # LLM settings
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    
    # Integration settings
    prometheus_url: Optional[str] = Field(default=None)
    pagerduty_api_key: Optional[str] = Field(default=None)
    
    model_config = {"env_prefix": "", "case_sensitive": False}


# ============================================================================
# Global config accessor
# ============================================================================


_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration.
    
    Returns:
        Global Config instance
    """
    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


def set_config(config: Config) -> None:
    """Set global configuration.
    
    Args:
        config: Config instance to set
    """
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset global configuration."""
    global _global_config
    _global_config = None
