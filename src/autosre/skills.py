"""
OpenSRE Skill Base Class

Skills provide a standardized interface for interacting with external systems.
Each skill defines actions that can be invoked by the OpenSRE orchestrator.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ActionResult(Generic[T]):
    """Result from a skill action."""
    success: bool
    data: T | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: T, **metadata) -> "ActionResult[T]":
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "ActionResult[T]":
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


@dataclass
class ActionDefinition:
    """Definition of a skill action."""
    name: str
    description: str
    handler: Callable
    params: list[dict[str, Any]] = field(default_factory=list)
    returns: str = "Any"
    requires_approval: bool = False


class Skill(ABC):
    """Base class for OpenSRE skills.

    Skills encapsulate interactions with external systems (Prometheus, Kubernetes,
    Dynatrace, etc.) and expose them as a set of actions.

    Example:
        class PrometheusSkill(Skill):
            name = "prometheus"
            version = "1.0.0"

            def __init__(self, config):
                self.url = config.get("url")

            async def query(self, promql: str) -> ActionResult:
                # Implementation
                pass
    """

    # Subclasses must define these
    name: str = ""
    version: str = "1.0.0"
    description: str = ""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize skill with configuration.

        Args:
            config: Skill-specific configuration (URLs, auth, etc.)
        """
        self.config = config or {}
        self._actions: dict[str, ActionDefinition] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the skill (connect to services, validate config, etc.).

        Override this method to perform async initialization.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """Clean up resources when skill is no longer needed.

        Override this method to clean up connections, etc.
        """
        self._initialized = False

    @abstractmethod
    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check if the skill's backing service is healthy.

        Returns:
            ActionResult with health status details.
        """
        pass

    def get_actions(self) -> list[ActionDefinition]:
        """Get all actions defined by this skill."""
        return list(self._actions.values())

    def get_action(self, name: str) -> ActionDefinition | None:
        """Get a specific action by name."""
        return self._actions.get(name)

    def register_action(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        params: list[dict[str, Any]] | None = None,
        returns: str = "Any",
        requires_approval: bool = False,
    ) -> None:
        """Register an action for this skill.

        Args:
            name: Action name (e.g., "query", "get_alerts")
            handler: Async function to handle the action
            description: Human-readable description
            params: Parameter definitions
            returns: Return type description
            requires_approval: Whether action needs human approval
        """
        self._actions[name] = ActionDefinition(
            name=name,
            description=description,
            handler=handler,
            params=params or [],
            returns=returns,
            requires_approval=requires_approval,
        )

    async def invoke(self, action: str, **kwargs) -> ActionResult:
        """Invoke an action by name.

        Args:
            action: Action name to invoke
            **kwargs: Arguments to pass to the action

        Returns:
            ActionResult from the action
        """
        action_def = self._actions.get(action)
        if not action_def:
            return ActionResult.fail(f"Unknown action: {action}")

        try:
            result = await action_def.handler(**kwargs)
            if isinstance(result, ActionResult):
                return result
            return ActionResult.ok(result)
        except Exception as e:
            logger.exception(f"Error invoking {self.name}.{action}")
            return ActionResult.fail(str(e))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} version={self.version}>"


def action(
    name: str | None = None,
    description: str = "",
    requires_approval: bool = False,
):
    """Decorator to register a method as a skill action.

    Example:
        class MySkill(Skill):
            @action(description="Query metrics")
            async def query(self, promql: str) -> ActionResult:
                ...
    """
    def decorator(func: Callable) -> Callable:
        action_name = name or func.__name__

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        # Store action metadata on the function
        wrapper._action_metadata = {
            "name": action_name,
            "description": description or func.__doc__ or "",
            "requires_approval": requires_approval,
        }
        return wrapper

    return decorator


class SkillRegistry:
    """Registry for managing available skills."""

    def __init__(self):
        self._skills: dict[str, type[Skill]] = {}
        self._instances: dict[str, Skill] = {}

    def register(self, skill_class: type[Skill]) -> None:
        """Register a skill class."""
        self._skills[skill_class.name] = skill_class

    def get(self, name: str) -> type[Skill] | None:
        """Get a skill class by name."""
        return self._skills.get(name)

    async def get_instance(self, name: str, config: dict[str, Any] | None = None) -> Skill | None:
        """Get or create a skill instance."""
        if name not in self._instances:
            skill_class = self._skills.get(name)
            if not skill_class:
                return None
            instance = skill_class(config)
            await instance.initialize()
            self._instances[name] = instance
        return self._instances.get(name)

    def list_skills(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    async def shutdown_all(self) -> None:
        """Shutdown all skill instances."""
        for instance in self._instances.values():
            await instance.shutdown()
        self._instances.clear()


# Global registry
registry = SkillRegistry()
