"""OpenSRE custom exceptions."""


class OpenSREError(Exception):
    """Base exception for OpenSRE."""
    pass


class SkillNotFoundError(OpenSREError):
    """Raised when a skill cannot be found."""
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        super().__init__(f"Skill not found: {skill_name}")


class SkillLoadError(OpenSREError):
    """Raised when a skill fails to load."""
    def __init__(self, skill_name: str, reason: str):
        self.skill_name = skill_name
        self.reason = reason
        super().__init__(f"Failed to load skill '{skill_name}': {reason}")


class SkillExecutionError(OpenSREError):
    """Raised when a skill method fails during execution."""
    def __init__(self, skill_name: str, method: str, reason: str):
        self.skill_name = skill_name
        self.method = method
        self.reason = reason
        super().__init__(f"Skill '{skill_name}.{method}' failed: {reason}")


class AgentDefinitionError(OpenSREError):
    """Raised when an agent definition is invalid."""
    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"Invalid agent definition '{agent_name}': {reason}")


class StepExecutionError(OpenSREError):
    """Raised when a step fails to execute."""
    def __init__(self, step_id: str, reason: str, retryable: bool = False):
        self.step_id = step_id
        self.reason = reason
        self.retryable = retryable
        super().__init__(f"Step '{step_id}' failed: {reason}")


class ConfigError(OpenSREError):
    """Raised when configuration is invalid."""
    def __init__(self, key: str, reason: str):
        self.key = key
        self.reason = reason
        super().__init__(f"Config error for '{key}': {reason}")


class SecretNotFoundError(OpenSREError):
    """Raised when a required secret is not found."""
    def __init__(self, secret_name: str):
        self.secret_name = secret_name
        super().__init__(f"Secret not found: {secret_name}")


class RetryExhaustedError(OpenSREError):
    """Raised when all retries are exhausted."""
    def __init__(self, step_id: str, attempts: int):
        self.step_id = step_id
        self.attempts = attempts
        super().__init__(f"Step '{step_id}' failed after {attempts} attempts")
