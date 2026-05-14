"""
Action Registry for remediation actions.

The ActionRegistry manages the catalog of available remediation actions,
including their definitions, implementations, and validation rules.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Awaitable, TypeVar
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    ActionDefinition,
    ActionParameter,
    ActionType,
    RiskLevel,
    RollbackStrategy,
    RemediationAction,
    RemediationResult,
    RemediationStatus,
)

logger = get_logger(__name__)

# Type for action handler functions
ActionHandler = Callable[..., Awaitable[dict[str, Any]]]
RollbackHandler = Callable[..., Awaitable[bool]]

T = TypeVar('T')


class ActionRegistryError(Exception):
    """Error in action registry operations."""
    pass


class ActionNotFoundError(ActionRegistryError):
    """Action not found in registry."""
    
    def __init__(self, action_name: str):
        super().__init__(f"Action '{action_name}' not found in registry")
        self.action_name = action_name


class ActionValidationError(ActionRegistryError):
    """Action validation failed."""
    
    def __init__(self, action_name: str, errors: list[str]):
        super().__init__(f"Validation failed for '{action_name}': {'; '.join(errors)}")
        self.action_name = action_name
        self.errors = errors


class ActionCooldownError(ActionRegistryError):
    """Action is in cooldown period."""
    
    def __init__(self, action_name: str, remaining_seconds: float):
        super().__init__(
            f"Action '{action_name}' is in cooldown. "
            f"Wait {remaining_seconds:.0f}s"
        )
        self.action_name = action_name
        self.remaining_seconds = remaining_seconds


class RegisteredAction:
    """A registered action with its handler and definition."""
    
    def __init__(
        self,
        definition: ActionDefinition,
        handler: ActionHandler,
        rollback_handler: RollbackHandler | None = None,
    ):
        self.definition = definition
        self.handler = handler
        self.rollback_handler = rollback_handler
        
        # Execution tracking
        self.last_execution: datetime | None = None
        self.execution_count: int = 0
        self.success_count: int = 0
        self.failure_count: int = 0
        self.total_duration_seconds: float = 0.0
    
    @property
    def name(self) -> str:
        return self.definition.name
    
    @property
    def is_in_cooldown(self) -> bool:
        """Check if action is in cooldown period."""
        if not self.last_execution:
            return False
        
        cooldown_end = self.last_execution + timedelta(
            seconds=self.definition.cooldown_seconds
        )
        return datetime.utcnow() < cooldown_end
    
    @property
    def cooldown_remaining_seconds(self) -> float:
        """Get remaining cooldown time in seconds."""
        if not self.last_execution:
            return 0
        
        cooldown_end = self.last_execution + timedelta(
            seconds=self.definition.cooldown_seconds
        )
        remaining = (cooldown_end - datetime.utcnow()).total_seconds()
        return max(0, remaining)
    
    @property
    def average_duration_seconds(self) -> float:
        """Get average execution duration."""
        if self.execution_count == 0:
            return self.definition.estimated_duration_seconds
        return self.total_duration_seconds / self.execution_count
    
    @property
    def success_rate(self) -> float:
        """Get success rate (0-1)."""
        if self.execution_count == 0:
            return 1.0
        return self.success_count / self.execution_count
    
    def record_execution(
        self,
        success: bool,
        duration_seconds: float,
    ) -> None:
        """Record an execution for metrics."""
        self.last_execution = datetime.utcnow()
        self.execution_count += 1
        self.total_duration_seconds += duration_seconds
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1


class ActionRegistry:
    """
    Registry of available remediation actions.
    
    The registry maintains a catalog of action definitions and their
    implementations. It supports:
    - Action registration via decorator or direct call
    - Parameter validation
    - Cooldown enforcement
    - Execution metrics
    
    Example:
        registry = ActionRegistry()
        
        # Register via decorator
        @registry.register(
            name="restart_pod",
            display_name="Restart Pod",
            description="Restarts a Kubernetes pod",
            action_type=ActionType.RESTART,
            risk_level=RiskLevel.LOW,
        )
        async def restart_pod(namespace: str, name: str) -> dict:
            # Implementation
            return {"restarted": True}
        
        # Or register directly
        registry.register_action(definition, handler)
        
        # Execute
        result = await registry.execute("restart_pod", {"namespace": "default", "name": "api"})
    """
    
    def __init__(self):
        self._actions: dict[str, RegisteredAction] = {}
        self._tags_index: dict[str, set[str]] = {}  # tag -> action names
        self._type_index: dict[ActionType, set[str]] = {}  # type -> action names
        self._lock = asyncio.Lock()
    
    @property
    def actions(self) -> dict[str, RegisteredAction]:
        """Get all registered actions."""
        return dict(self._actions)
    
    @property
    def action_names(self) -> list[str]:
        """Get list of registered action names."""
        return list(self._actions.keys())
    
    def register(
        self,
        name: str,
        display_name: str,
        description: str,
        action_type: ActionType,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        is_destructive: bool = False,
        is_reversible: bool = True,
        parameters: list[ActionParameter] | None = None,
        rollback_strategy: RollbackStrategy = RollbackStrategy.AUTOMATIC,
        rollback_action: str | None = None,
        estimated_duration_seconds: int = 60,
        timeout_seconds: int = 300,
        cooldown_seconds: int = 60,
        target_types: list[str] | None = None,
        requires_approval: bool = False,
        approval_roles: list[str] | None = None,
        pre_flight_checks: list[str] | None = None,
        post_checks: list[str] | None = None,
        tags: list[str] | None = None,
        documentation_url: str | None = None,
    ) -> Callable[[ActionHandler], ActionHandler]:
        """
        Decorator to register an action handler.
        
        Usage:
            @registry.register(
                name="restart_pod",
                display_name="Restart Pod",
                description="Restarts a Kubernetes pod",
                action_type=ActionType.RESTART,
            )
            async def restart_pod(namespace: str, name: str) -> dict:
                ...
        """
        def decorator(func: ActionHandler) -> ActionHandler:
            # Infer parameters from function signature if not provided
            inferred_params = parameters or self._infer_parameters(func)
            
            definition = ActionDefinition(
                name=name,
                display_name=display_name,
                description=description,
                action_type=action_type,
                risk_level=risk_level,
                is_destructive=is_destructive,
                is_reversible=is_reversible,
                parameters=inferred_params,
                rollback_strategy=rollback_strategy,
                rollback_action=rollback_action,
                estimated_duration_seconds=estimated_duration_seconds,
                timeout_seconds=timeout_seconds,
                cooldown_seconds=cooldown_seconds,
                target_types=target_types or [],
                requires_approval=requires_approval,
                approval_roles=approval_roles or [],
                pre_flight_checks=pre_flight_checks or [],
                post_checks=post_checks or [],
                tags=tags or [],
                documentation_url=documentation_url,
            )
            
            self.register_action(definition, func)
            
            return func
        
        return decorator
    
    def register_rollback(
        self,
        action_name: str,
    ) -> Callable[[RollbackHandler], RollbackHandler]:
        """
        Decorator to register a rollback handler for an action.
        
        Usage:
            @registry.register_rollback("restart_pod")
            async def rollback_restart_pod(rollback_data: dict) -> bool:
                ...
        """
        def decorator(func: RollbackHandler) -> RollbackHandler:
            if action_name not in self._actions:
                raise ActionNotFoundError(action_name)
            
            self._actions[action_name].rollback_handler = func
            logger.info(f"Registered rollback handler for action: {action_name}")
            
            return func
        
        return decorator
    
    def register_action(
        self,
        definition: ActionDefinition,
        handler: ActionHandler,
        rollback_handler: RollbackHandler | None = None,
    ) -> None:
        """
        Register an action with its definition and handler.
        
        Args:
            definition: Action definition
            handler: Async function to execute the action
            rollback_handler: Optional async function to rollback the action
        """
        if definition.name in self._actions:
            logger.warning(f"Overwriting existing action: {definition.name}")
        
        registered = RegisteredAction(
            definition=definition,
            handler=handler,
            rollback_handler=rollback_handler,
        )
        
        self._actions[definition.name] = registered
        
        # Update indexes
        for tag in definition.tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(definition.name)
        
        if definition.action_type not in self._type_index:
            self._type_index[definition.action_type] = set()
        self._type_index[definition.action_type].add(definition.name)
        
        logger.info(
            f"Registered action: {definition.name} "
            f"(type={definition.action_type.value}, risk={definition.risk_level.value})"
        )
    
    def unregister(self, name: str) -> None:
        """
        Unregister an action.
        
        Args:
            name: Action name
        """
        if name not in self._actions:
            raise ActionNotFoundError(name)
        
        action = self._actions.pop(name)
        
        # Update indexes
        for tag in action.definition.tags:
            if tag in self._tags_index:
                self._tags_index[tag].discard(name)
        
        if action.definition.action_type in self._type_index:
            self._type_index[action.definition.action_type].discard(name)
        
        logger.info(f"Unregistered action: {name}")
    
    def get(self, name: str) -> RegisteredAction:
        """
        Get a registered action by name.
        
        Args:
            name: Action name
            
        Returns:
            Registered action
            
        Raises:
            ActionNotFoundError: If action not found
        """
        if name not in self._actions:
            raise ActionNotFoundError(name)
        return self._actions[name]
    
    def get_definition(self, name: str) -> ActionDefinition:
        """
        Get action definition by name.
        
        Args:
            name: Action name
            
        Returns:
            Action definition
        """
        return self.get(name).definition
    
    def has_action(self, name: str) -> bool:
        """Check if action exists."""
        return name in self._actions
    
    def find_by_tag(self, tag: str) -> list[RegisteredAction]:
        """
        Find actions by tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of matching actions
        """
        names = self._tags_index.get(tag, set())
        return [self._actions[n] for n in names if n in self._actions]
    
    def find_by_type(self, action_type: ActionType) -> list[RegisteredAction]:
        """
        Find actions by type.
        
        Args:
            action_type: Action type
            
        Returns:
            List of matching actions
        """
        names = self._type_index.get(action_type, set())
        return [self._actions[n] for n in names if n in self._actions]
    
    def find_by_target_type(self, target_type: str) -> list[RegisteredAction]:
        """
        Find actions that can target a specific resource type.
        
        Args:
            target_type: Target type (pod, deployment, node, etc)
            
        Returns:
            List of matching actions
        """
        return [
            action for action in self._actions.values()
            if target_type in action.definition.target_types
        ]
    
    def find_by_risk_level(
        self,
        max_risk: RiskLevel,
    ) -> list[RegisteredAction]:
        """
        Find actions at or below a risk level.
        
        Args:
            max_risk: Maximum risk level
            
        Returns:
            List of matching actions
        """
        risk_order = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        max_index = risk_order.index(max_risk)
        
        return [
            action for action in self._actions.values()
            if risk_order.index(action.definition.risk_level) <= max_index
        ]
    
    def validate_parameters(
        self,
        name: str,
        parameters: dict[str, Any],
    ) -> list[str]:
        """
        Validate parameters for an action.
        
        Args:
            name: Action name
            parameters: Parameters to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        action = self.get(name)
        return action.definition.validate_parameters(parameters)
    
    async def execute(
        self,
        name: str,
        parameters: dict[str, Any],
        enforce_cooldown: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Execute an action.
        
        Args:
            name: Action name
            parameters: Action parameters
            enforce_cooldown: Whether to enforce cooldown
            timeout: Override timeout (defaults to action's timeout)
            
        Returns:
            Action result
            
        Raises:
            ActionNotFoundError: If action not found
            ActionValidationError: If parameters invalid
            ActionCooldownError: If action is in cooldown
        """
        action = self.get(name)
        
        # Validate parameters
        errors = action.definition.validate_parameters(parameters)
        if errors:
            raise ActionValidationError(name, errors)
        
        # Check cooldown
        if enforce_cooldown and action.is_in_cooldown:
            raise ActionCooldownError(name, action.cooldown_remaining_seconds)
        
        # Execute with timeout
        effective_timeout = timeout or action.definition.timeout_seconds
        
        async with self._lock:
            start_time = datetime.utcnow()
            try:
                # Apply defaults and remove internal parameters
                params_with_defaults = self._apply_defaults(action.definition, parameters)
                
                # Remove internal parameters (starting with _) before calling handler
                handler_params = {
                    k: v for k, v in params_with_defaults.items()
                    if not k.startswith("_")
                }
                
                result = await asyncio.wait_for(
                    action.handler(**handler_params),
                    timeout=effective_timeout,
                )
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                action.record_execution(success=True, duration_seconds=duration)
                
                logger.info(
                    f"Action {name} completed successfully in {duration:.2f}s"
                )
                
                return result
                
            except asyncio.TimeoutError:
                duration = (datetime.utcnow() - start_time).total_seconds()
                action.record_execution(success=False, duration_seconds=duration)
                
                logger.error(
                    f"Action {name} timed out after {effective_timeout}s"
                )
                raise
                
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                action.record_execution(success=False, duration_seconds=duration)
                
                logger.error(
                    f"Action {name} failed: {e}",
                    exc_info=True,
                )
                raise
    
    async def execute_rollback(
        self,
        name: str,
        rollback_data: dict[str, Any],
    ) -> bool:
        """
        Execute rollback for an action.
        
        Args:
            name: Action name
            rollback_data: Data needed for rollback
            
        Returns:
            True if rollback succeeded
        """
        action = self.get(name)
        
        if not action.rollback_handler:
            logger.warning(f"No rollback handler for action: {name}")
            return False
        
        try:
            result = await action.rollback_handler(rollback_data)
            logger.info(f"Rollback for {name} completed: {result}")
            return result
        except Exception as e:
            logger.error(f"Rollback for {name} failed: {e}", exc_info=True)
            return False
    
    def _infer_parameters(self, func: ActionHandler) -> list[ActionParameter]:
        """
        Infer action parameters from function signature.
        
        Args:
            func: Action handler function
            
        Returns:
            List of inferred parameters
        """
        sig = inspect.signature(func)
        parameters = []
        
        type_hints = {}
        try:
            type_hints = func.__annotations__ if hasattr(func, '__annotations__') else {}
        except Exception:
            pass
        
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            # Get type from hints or default to str
            param_type = type_hints.get(param_name, str)
            type_name = getattr(param_type, '__name__', 'str')
            
            # Check if required
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default
            
            parameters.append(ActionParameter(
                name=param_name,
                type=type_name,
                required=required,
                default=default,
                description=f"Parameter: {param_name}",
            ))
        
        return parameters
    
    def _apply_defaults(
        self,
        definition: ActionDefinition,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply default values to parameters."""
        result = dict(parameters)
        
        for param_def in definition.parameters:
            if param_def.name not in result:
                if param_def.default is not None:
                    result[param_def.name] = param_def.default
        
        return result
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get metrics for all registered actions.
        
        Returns:
            Dictionary of metrics
        """
        metrics = {
            "total_actions": len(self._actions),
            "actions_by_type": {},
            "actions_by_risk": {},
            "execution_stats": {},
        }
        
        for action in self._actions.values():
            # By type
            action_type = action.definition.action_type.value
            if action_type not in metrics["actions_by_type"]:
                metrics["actions_by_type"][action_type] = 0
            metrics["actions_by_type"][action_type] += 1
            
            # By risk
            risk = action.definition.risk_level.value
            if risk not in metrics["actions_by_risk"]:
                metrics["actions_by_risk"][risk] = 0
            metrics["actions_by_risk"][risk] += 1
            
            # Execution stats
            metrics["execution_stats"][action.name] = {
                "execution_count": action.execution_count,
                "success_count": action.success_count,
                "failure_count": action.failure_count,
                "success_rate": action.success_rate,
                "average_duration_seconds": action.average_duration_seconds,
                "in_cooldown": action.is_in_cooldown,
            }
        
        return metrics
    
    def to_catalog(self) -> list[dict[str, Any]]:
        """
        Export action catalog for documentation/UI.
        
        Returns:
            List of action definitions as dictionaries
        """
        return [
            {
                "name": action.definition.name,
                "display_name": action.definition.display_name,
                "description": action.definition.description,
                "type": action.definition.action_type.value,
                "risk_level": action.definition.risk_level.value,
                "is_destructive": action.definition.is_destructive,
                "is_reversible": action.definition.is_reversible,
                "requires_approval": action.definition.requires_approval,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                        "default": p.default,
                    }
                    for p in action.definition.parameters
                ],
                "target_types": action.definition.target_types,
                "tags": action.definition.tags,
                "estimated_duration_seconds": action.definition.estimated_duration_seconds,
                "cooldown_seconds": action.definition.cooldown_seconds,
                "documentation_url": action.definition.documentation_url,
                "stats": {
                    "execution_count": action.execution_count,
                    "success_rate": action.success_rate,
                },
            }
            for action in self._actions.values()
        ]


# Global registry instance
_global_registry: ActionRegistry | None = None


def get_registry() -> ActionRegistry:
    """Get the global action registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ActionRegistry()
    return _global_registry


def register_action(
    name: str,
    display_name: str,
    description: str,
    action_type: ActionType,
    **kwargs,
) -> Callable[[ActionHandler], ActionHandler]:
    """
    Decorator to register an action to the global registry.
    
    Usage:
        @register_action(
            name="restart_pod",
            display_name="Restart Pod",
            description="Restarts a pod",
            action_type=ActionType.RESTART,
        )
        async def restart_pod(namespace: str, name: str) -> dict:
            ...
    """
    return get_registry().register(
        name=name,
        display_name=display_name,
        description=description,
        action_type=action_type,
        **kwargs,
    )
