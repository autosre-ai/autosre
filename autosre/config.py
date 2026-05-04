"""
AutoSRE v2 Configuration — Pydantic Settings with YAML support.

Supports loading from:
1. Environment variables (AUTOSRE_*)
2. config.yaml file
3. Defaults

Example:
    >>> from autosre.config import Settings
    >>> settings = Settings()
    >>> print(settings.llm.provider)
    'anthropic'
"""

from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Type aliases
LLMProvider = Literal["anthropic", "openai"]


class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AUTOSRE_LLM_")
    
    provider: LLMProvider = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    
    # API keys loaded from env
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")


class MemorySettings(BaseSettings):
    """Episodic memory configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AUTOSRE_MEMORY_")
    
    db_path: Path = Field(default=Path(".autosre/memory.db"))
    max_episodes: int = 1000
    similarity_threshold: float = 0.7
    
    @field_validator("db_path", mode="before")
    @classmethod
    def resolve_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v)
        return v


class InvestigationSettings(BaseSettings):
    """Investigation behavior settings."""
    
    model_config = SettingsConfigDict(env_prefix="AUTOSRE_INVESTIGATION_")
    
    max_iterations: int = 3
    max_subagent_loops: int = 25
    parallel_subagents: bool = True
    timeout_seconds: int = 300


class Settings(BaseSettings):
    """Root AutoSRE settings.
    
    Load order:
    1. Environment variables (AUTOSRE_*)
    2. .env file
    3. config.yaml (if exists)
    4. Defaults
    """
    
    model_config = SettingsConfigDict(
        env_prefix="AUTOSRE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )
    
    # Nested settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    investigation: InvestigationSettings = Field(default_factory=InvestigationSettings)
    
    # Paths
    topology_path: Path = Field(default=Path("topology.yaml"))
    skills_dir: Path = Field(default=Path("skills"))
    
    @field_validator("topology_path", "skills_dir", mode="before")
    @classmethod
    def resolve_paths(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v)
        return v
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """Load settings from YAML file."""
        import yaml
        
        if not path.exists():
            return cls()
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        return cls(**data)


# Global settings instance (lazy loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def configure(**kwargs: Any) -> Settings:
    """Override global settings."""
    global _settings
    _settings = Settings(**kwargs)
    return _settings
