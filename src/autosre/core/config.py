"""AutoSRE Configuration - Pydantic Settings with environment and file support."""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderType(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    TOGETHER = "together"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CacheBackend(str, Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"


class LLMProviderSettings(BaseSettings):
    """Settings for a single LLM provider."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    enabled: bool = True
    api_key: SecretStr | None = None
    base_url: str | None = None
    default_model: str | None = None
    max_retries: int = 3
    timeout: float = 120.0
    
    # Azure-specific
    api_version: str | None = None
    deployment_name: str | None = None
    
    # Rate limiting
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None


class CacheSettings(BaseSettings):
    """Cache configuration."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    enabled: bool = True
    backend: CacheBackend = CacheBackend.MEMORY
    ttl_seconds: int = 3600
    max_size: int = 1000
    
    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    
    # Disk settings
    disk_path: Path = Path(".cache/autosre")


class RetrySettings(BaseSettings):
    """Retry configuration with exponential backoff."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    # Retryable status codes
    retryable_status_codes: list[int] = Field(
        default=[429, 500, 502, 503, 504]
    )


class TokenSettings(BaseSettings):
    """Token counting and limits."""
    
    model_config = SettingsConfigDict(extra="allow")
    
    # Default limits per model family
    default_max_tokens: int = 4096
    default_context_window: int = 128000
    
    # Model-specific overrides
    model_limits: dict[str, dict[str, int]] = Field(default_factory=lambda: {
        "gpt-4": {"max_tokens": 8192, "context_window": 128000},
        "gpt-4-turbo": {"max_tokens": 4096, "context_window": 128000},
        "gpt-4o": {"max_tokens": 16384, "context_window": 128000},
        "claude-3-opus": {"max_tokens": 4096, "context_window": 200000},
        "claude-3-sonnet": {"max_tokens": 4096, "context_window": 200000},
        "claude-3-haiku": {"max_tokens": 4096, "context_window": 200000},
        "claude-sonnet-4": {"max_tokens": 8192, "context_window": 200000},
    })
    
    # Reserve tokens for response
    response_reserve: int = 1024


class Settings(BaseSettings):
    """Main AutoSRE settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="AUTOSRE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )
    
    # General
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    config_file: Path | None = None
    
    # Default LLM provider
    default_provider: LLMProviderType = LLMProviderType.OPENAI
    default_model: str = "gpt-4-turbo"
    
    # Provider settings
    openai: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings(
        default_model="gpt-4-turbo"
    ))
    anthropic: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings(
        default_model="claude-3-sonnet-20240229"
    ))
    ollama: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings(
        base_url="http://localhost:11434",
        default_model="llama3"
    ))
    azure_openai: LLMProviderSettings = Field(default_factory=LLMProviderSettings)
    together: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings(
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3-70b-chat-hf"
    ))
    
    # Cache settings
    cache: CacheSettings = Field(default_factory=CacheSettings)
    
    # Retry settings
    retry: RetrySettings = Field(default_factory=RetrySettings)
    
    # Token settings
    tokens: TokenSettings = Field(default_factory=TokenSettings)
    
    # Structured output settings
    structured_output_retries: int = 2
    
    @field_validator("config_file", mode="before")
    @classmethod
    def resolve_config_path(cls, v: str | Path | None) -> Path | None:
        """Resolve config file path."""
        if v is None:
            return None
        return Path(v).expanduser().resolve()
    
    @model_validator(mode="after")
    def load_config_file(self) -> "Settings":
        """Load settings from config file if specified."""
        if self.config_file and self.config_file.exists():
            self._merge_config_file(self.config_file)
        return self
    
    def _merge_config_file(self, path: Path) -> None:
        """Merge settings from YAML config file."""
        with open(path) as f:
            config = yaml.safe_load(f)
        
        if not config:
            return
        
        # Merge provider settings
        for provider in ["openai", "anthropic", "ollama", "azure_openai", "together"]:
            if provider in config:
                provider_settings = getattr(self, provider)
                for key, value in config[provider].items():
                    if hasattr(provider_settings, key):
                        setattr(provider_settings, key, value)
        
        # Merge other settings
        for key in ["debug", "log_level", "default_provider", "default_model"]:
            if key in config:
                setattr(self, key, config[key])
        
        # Merge nested settings
        for section in ["cache", "retry", "tokens"]:
            if section in config:
                section_settings = getattr(self, section)
                for key, value in config[section].items():
                    if hasattr(section_settings, key):
                        setattr(section_settings, key, value)
    
    def get_provider_settings(self, provider: LLMProviderType) -> LLMProviderSettings:
        """Get settings for a specific provider."""
        provider_map = {
            LLMProviderType.OPENAI: self.openai,
            LLMProviderType.ANTHROPIC: self.anthropic,
            LLMProviderType.OLLAMA: self.ollama,
            LLMProviderType.AZURE_OPENAI: self.azure_openai,
            LLMProviderType.TOGETHER: self.together,
        }
        return provider_map[provider]
    
    def get_api_key(self, provider: LLMProviderType) -> str | None:
        """Get API key for a provider, checking environment fallbacks."""
        settings = self.get_provider_settings(provider)
        
        if settings.api_key:
            return settings.api_key.get_secret_value()
        
        # Environment variable fallbacks
        env_map = {
            LLMProviderType.OPENAI: "OPENAI_API_KEY",
            LLMProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProviderType.AZURE_OPENAI: "AZURE_OPENAI_API_KEY",
            LLMProviderType.TOGETHER: "TOGETHER_API_KEY",
        }
        
        if provider in env_map:
            return os.getenv(env_map[provider])
        
        return None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings (clears cache)."""
    get_settings.cache_clear()
    return get_settings()
