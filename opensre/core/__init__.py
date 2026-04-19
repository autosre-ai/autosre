"""OpenSRE - Site Reliability Engineering automation framework."""

from .config import ConfigManager, get_config, init_config
from .exceptions import (
    AgentDefinitionError,
    ConfigError,
    OpenSREError,
    RetryExhaustedError,
    SecretNotFoundError,
    SkillExecutionError,
    SkillLoadError,
    SkillNotFoundError,
    StepExecutionError,
)
from .models import (
    AgentDefinition,
    AgentRunResult,
    EnvironmentConfig,
    OpenSREConfig,
    SkillInfo,
    SkillMetadata,
    StepDefinition,
    StepResult,
    StepStatus,
)
from .runtime import Agent, AgentRunner, ExecutionContext
from .skills import Skill, SkillRegistry, skill

__version__ = "0.1.0"
__all__ = [
    # Core classes
    "Skill",
    "SkillRegistry",
    "skill",
    "Agent",
    "AgentRunner",
    "ExecutionContext",
    "ConfigManager",
    # Functions
    "get_config",
    "init_config",
    # Models
    "AgentDefinition",
    "AgentRunResult",
    "EnvironmentConfig",
    "OpenSREConfig",
    "SkillInfo",
    "SkillMetadata",
    "StepDefinition",
    "StepResult",
    "StepStatus",
    # Exceptions
    "OpenSREError",
    "AgentDefinitionError",
    "ConfigError",
    "RetryExhaustedError",
    "SecretNotFoundError",
    "SkillExecutionError",
    "SkillLoadError",
    "SkillNotFoundError",
    "StepExecutionError",
]
