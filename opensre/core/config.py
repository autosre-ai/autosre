"""Configuration management for OpenSRE."""

import os
from pathlib import Path
from typing import Any

from .exceptions import ConfigError, SecretNotFoundError
from .models import EnvironmentConfig, OpenSREConfig
from .utils import deep_merge, get_project_root, load_yaml, resolve_env_vars


class ConfigManager:
    """Manages configuration for OpenSRE projects."""

    def __init__(
        self,
        project_root: Path | str | None = None,
        environment: str | None = None
    ):
        self.project_root = Path(project_root) if project_root else get_project_root()
        self._config: OpenSREConfig | None = None
        self._environment = environment
        self._resolved_config: dict[str, Any] = {}
        self._secrets_cache: dict[str, str] = {}

    def load(self) -> OpenSREConfig:
        """Load the project configuration."""
        config_path = self.project_root / "opensre.yaml"
        if not config_path.exists():
            raise ConfigError("opensre.yaml", "Configuration file not found")

        raw_config = load_yaml(config_path)

        # Parse environments
        environments: dict[str, EnvironmentConfig] = {}
        for env_name, env_data in raw_config.get("environments", {}).items():
            environments[env_name] = EnvironmentConfig(name=env_name, **env_data)

        self._config = OpenSREConfig(
            project_name=raw_config.get("project_name", "unnamed"),
            version=raw_config.get("version", "1.0.0"),
            default_environment=raw_config.get("default_environment", "dev"),
            environments=environments,
            global_config=raw_config.get("config", {})
        )

        # Resolve environment-specific config
        self._resolve_config()

        return self._config

    @property
    def environment(self) -> str:
        """Get the current environment name."""
        if self._environment:
            return self._environment
        # Check env var
        env_from_var = os.environ.get("OPENSRE_ENV")
        if env_from_var:
            return env_from_var
        # Use default
        if self._config:
            return self._config.default_environment
        return "dev"

    @environment.setter
    def environment(self, value: str) -> None:
        """Set the current environment."""
        self._environment = value
        if self._config:
            self._resolve_config()

    def _resolve_config(self) -> None:
        """Resolve configuration for the current environment."""
        if not self._config:
            return

        # Start with global config
        self._resolved_config = self._config.global_config.copy()

        # Merge environment-specific config
        env_config = self._config.environments.get(self.environment)
        if env_config:
            self._resolved_config = deep_merge(
                self._resolved_config,
                env_config.variables
            )

        # Resolve environment variables in string values
        self._resolved_config = self._resolve_env_in_dict(self._resolved_config)

    def _resolve_env_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve environment variables in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = resolve_env_vars(value)
            elif isinstance(value, dict):
                result[key] = self._resolve_env_in_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    resolve_env_vars(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Supports dot notation for nested keys (e.g., "database.host").
        """
        parts = key.split(".")
        value: Any = self._resolved_config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
            if value is None:
                return default
        return value

    def get_secret(self, name: str, required: bool = True) -> str | None:
        """Get a secret value.

        Looks up secrets in this order:
        1. Environment variable: OPENSRE_SECRET_{NAME}
        2. Environment-specific secret file
        3. Global secrets file
        """
        # Check cache
        if name in self._secrets_cache:
            return self._secrets_cache[name]

        # Try environment variable
        env_key = f"OPENSRE_SECRET_{name.upper()}"
        env_value = os.environ.get(env_key)
        if env_value:
            self._secrets_cache[name] = env_value
            return env_value

        # Try environment-specific secrets file
        secrets_file = self.project_root / "secrets" / f"{self.environment}.yaml"
        if secrets_file.exists():
            secrets = load_yaml(secrets_file)
            if name in secrets:
                self._secrets_cache[name] = str(secrets[name])
                return self._secrets_cache[name]

        # Try global secrets file
        global_secrets_file = self.project_root / "secrets" / "global.yaml"
        if global_secrets_file.exists():
            secrets = load_yaml(global_secrets_file)
            if name in secrets:
                self._secrets_cache[name] = str(secrets[name])
                return self._secrets_cache[name]

        if required:
            raise SecretNotFoundError(name)
        return None

    def get_skills_dir(self) -> Path:
        """Get the skills directory for the current environment."""
        if self._config:
            env_config = self._config.environments.get(self.environment)
            if env_config:
                return self.project_root / env_config.skills_dir
        return self.project_root / "skills"

    def get_agents_dir(self) -> Path:
        """Get the agents directory for the current environment."""
        if self._config:
            env_config = self._config.environments.get(self.environment)
            if env_config:
                return self.project_root / env_config.agents_dir
        return self.project_root / "agents"

    def all(self) -> dict[str, Any]:
        """Get all resolved configuration."""
        return self._resolved_config.copy()


# Global config instance (convenience)
_global_config: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Get or create the global configuration manager."""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
        try:
            _global_config.load()
        except ConfigError:
            pass  # Allow usage without config file
    return _global_config


def init_config(project_root: Path | str | None = None, environment: str | None = None) -> ConfigManager:
    """Initialize the global configuration manager."""
    global _global_config
    _global_config = ConfigManager(project_root, environment)
    _global_config.load()
    return _global_config
