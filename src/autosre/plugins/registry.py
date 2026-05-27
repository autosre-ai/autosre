"""
Plugin Registry for AutoSRE

Provides centralized plugin management:
- Plugin registration and discovery
- Dependency resolution
- Plugin lifecycle coordination
- Event routing to plugins
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from autosre.plugins.base import (
    Plugin,
    PluginCapability,
    PluginContext,
    PluginMetadata,
    PluginResult,
    PluginState,
    PluginType,
    HookPlugin,
    MiddlewarePlugin,
    SkillPlugin,
    IntegrationPlugin,
)


class RegistryEvent(str, Enum):
    """Events emitted by the registry."""
    
    PLUGIN_REGISTERED = "plugin.registered"
    PLUGIN_UNREGISTERED = "plugin.unregistered"
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_INITIALIZED = "plugin.initialized"
    PLUGIN_SHUTDOWN = "plugin.shutdown"
    PLUGIN_ERROR = "plugin.error"
    PLUGIN_STATE_CHANGED = "plugin.state_changed"


@dataclass
class PluginEntry:
    """Internal entry for a registered plugin."""
    
    plugin: Plugin
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    load_order: int = 0
    enabled: bool = True
    error_count: int = 0
    last_error: Optional[str] = None
    
    @property
    def metadata(self) -> PluginMetadata:
        return self.plugin.metadata
    
    @property
    def state(self) -> PluginState:
        return self.plugin.state


class RegistryConfig(BaseModel):
    """Configuration for the plugin registry."""
    
    # Lifecycle
    auto_initialize: bool = Field(default=True, description="Auto-initialize on registration")
    parallel_init: bool = Field(default=True, description="Initialize plugins in parallel")
    shutdown_timeout: float = Field(default=30.0, description="Shutdown timeout in seconds")
    
    # Error handling
    max_error_count: int = Field(default=3, description="Max errors before disabling")
    disable_on_error: bool = Field(default=True, description="Disable plugin on repeated errors")
    
    # Hooks
    enable_hooks: bool = Field(default=True, description="Enable event hooks")
    hook_timeout: float = Field(default=10.0, description="Hook execution timeout")
    
    # Middleware
    enable_middleware: bool = Field(default=True, description="Enable middleware processing")


class PluginRegistry:
    """
    Central registry for managing AutoSRE plugins.
    
    The registry handles:
    - Plugin registration and lifecycle management
    - Event routing to hook plugins
    - Middleware chain execution
    - Dependency resolution
    
    Example:
        registry = PluginRegistry()
        
        # Register a plugin
        plugin = MyPlugin()
        await registry.register(plugin)
        
        # Get a plugin by ID
        my_plugin = registry.get("my-plugin")
        
        # Emit an event to all hook plugins
        await registry.emit_event("incident.detected", {"alert_id": "123"})
    """
    
    def __init__(self, config: Optional[RegistryConfig] = None):
        """Initialize the plugin registry."""
        self._config = config or RegistryConfig()
        self._plugins: dict[str, PluginEntry] = {}
        self._load_counter = 0
        self._event_listeners: dict[str, list[Callable]] = {}
        self._shutdown_hooks: list[Callable] = []
        self._initialized = False
    
    @property
    def config(self) -> RegistryConfig:
        """Get registry configuration."""
        return self._config
    
    @property
    def plugin_count(self) -> int:
        """Get number of registered plugins."""
        return len(self._plugins)
    
    @property
    def active_plugins(self) -> list[Plugin]:
        """Get all active plugins."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if entry.plugin.state == PluginState.ACTIVE
        ]
    
    # Plugin registration
    
    async def register(
        self,
        plugin: Plugin,
        *,
        enabled: bool = True,
        auto_initialize: Optional[bool] = None,
    ) -> bool:
        """
        Register a plugin with the registry.
        
        Args:
            plugin: The plugin instance to register
            enabled: Whether the plugin should be enabled
            auto_initialize: Override auto-initialization setting
            
        Returns:
            True if registration successful
        """
        plugin_id = plugin.metadata.id
        
        # Check for duplicate
        if plugin_id in self._plugins:
            if plugin.metadata.singleton:
                raise ValueError(f"Plugin {plugin_id} is already registered (singleton)")
            # For non-singletons, append instance number
            instance = 1
            while f"{plugin_id}#{instance}" in self._plugins:
                instance += 1
            plugin_id = f"{plugin_id}#{instance}"
        
        # Create entry
        self._load_counter += 1
        entry = PluginEntry(
            plugin=plugin,
            load_order=self._load_counter,
            enabled=enabled,
        )
        self._plugins[plugin_id] = entry
        
        # Emit registration event
        await self._emit_internal(RegistryEvent.PLUGIN_REGISTERED, plugin_id=plugin_id)
        
        # Auto-initialize if enabled
        should_init = auto_initialize if auto_initialize is not None else self._config.auto_initialize
        if should_init and enabled:
            try:
                await plugin.load()
                await self._emit_internal(RegistryEvent.PLUGIN_LOADED, plugin_id=plugin_id)
                
                await plugin.initialize()
                await self._emit_internal(RegistryEvent.PLUGIN_INITIALIZED, plugin_id=plugin_id)
            except Exception as e:
                entry.error_count += 1
                entry.last_error = str(e)
                await self._emit_internal(
                    RegistryEvent.PLUGIN_ERROR,
                    plugin_id=plugin_id,
                    error=str(e),
                )
                raise
        
        return True
    
    async def unregister(self, plugin_id: str) -> bool:
        """
        Unregister a plugin from the registry.
        
        Args:
            plugin_id: The plugin ID to unregister
            
        Returns:
            True if unregistration successful
        """
        if plugin_id not in self._plugins:
            return False
        
        entry = self._plugins[plugin_id]
        
        # Shutdown if active
        if entry.plugin.state in (PluginState.ACTIVE, PluginState.PAUSED):
            try:
                await asyncio.wait_for(
                    entry.plugin.shutdown(),
                    timeout=self._config.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                pass  # Force unregister anyway
        
        del self._plugins[plugin_id]
        await self._emit_internal(RegistryEvent.PLUGIN_UNREGISTERED, plugin_id=plugin_id)
        
        return True
    
    # Plugin access
    
    def get(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID."""
        entry = self._plugins.get(plugin_id)
        return entry.plugin if entry else None
    
    def get_by_type(self, plugin_type: PluginType) -> list[Plugin]:
        """Get all plugins of a specific type."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if entry.plugin.metadata.type == plugin_type
        ]
    
    def get_by_capability(self, capability: PluginCapability) -> list[Plugin]:
        """Get all plugins with a specific capability."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if capability in entry.plugin.metadata.capabilities
        ]
    
    def get_skills(self) -> list[SkillPlugin]:
        """Get all skill plugins."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if isinstance(entry.plugin, SkillPlugin) and entry.enabled
        ]
    
    def get_integrations(self) -> list[IntegrationPlugin]:
        """Get all integration plugins."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if isinstance(entry.plugin, IntegrationPlugin) and entry.enabled
        ]
    
    def get_hooks(self) -> list[HookPlugin]:
        """Get all hook plugins."""
        return [
            entry.plugin
            for entry in self._plugins.values()
            if isinstance(entry.plugin, HookPlugin) and entry.enabled
        ]
    
    def get_middleware(self) -> list[MiddlewarePlugin]:
        """Get all middleware plugins sorted by priority."""
        plugins = [
            entry.plugin
            for entry in self._plugins.values()
            if isinstance(entry.plugin, MiddlewarePlugin) and entry.enabled
        ]
        return sorted(plugins, key=lambda p: p.priority)
    
    def list_plugins(self) -> list[dict[str, Any]]:
        """List all registered plugins with their status."""
        return [
            {
                "id": plugin_id,
                "name": entry.metadata.name,
                "version": entry.metadata.version,
                "type": entry.metadata.type.value,
                "state": entry.state.value,
                "enabled": entry.enabled,
                "load_order": entry.load_order,
                "registered_at": entry.registered_at.isoformat(),
                "error_count": entry.error_count,
                "last_error": entry.last_error,
            }
            for plugin_id, entry in sorted(
                self._plugins.items(),
                key=lambda x: x[1].load_order,
            )
        ]
    
    # Lifecycle management
    
    async def initialize_all(self) -> dict[str, bool]:
        """Initialize all registered plugins."""
        results = {}
        
        # Sort by priority
        sorted_entries = sorted(
            self._plugins.items(),
            key=lambda x: x[1].metadata.priority.value,
        )
        
        if self._config.parallel_init:
            # Parallel initialization
            tasks = []
            for plugin_id, entry in sorted_entries:
                if entry.enabled and entry.plugin.state == PluginState.UNLOADED:
                    tasks.append(self._init_plugin(plugin_id, entry))
            
            if tasks:
                init_results = await asyncio.gather(*tasks, return_exceptions=True)
                for (plugin_id, _), result in zip(sorted_entries, init_results):
                    results[plugin_id] = not isinstance(result, Exception)
        else:
            # Sequential initialization
            for plugin_id, entry in sorted_entries:
                if entry.enabled and entry.plugin.state == PluginState.UNLOADED:
                    try:
                        await self._init_plugin(plugin_id, entry)
                        results[plugin_id] = True
                    except Exception:
                        results[plugin_id] = False
        
        self._initialized = True
        return results
    
    async def _init_plugin(self, plugin_id: str, entry: PluginEntry) -> None:
        """Initialize a single plugin."""
        try:
            await entry.plugin.load()
            await entry.plugin.initialize()
        except Exception as e:
            entry.error_count += 1
            entry.last_error = str(e)
            await self._emit_internal(
                RegistryEvent.PLUGIN_ERROR,
                plugin_id=plugin_id,
                error=str(e),
            )
            raise
    
    async def shutdown_all(self) -> dict[str, bool]:
        """Shutdown all registered plugins."""
        results = {}
        
        # Run shutdown hooks first
        for hook in self._shutdown_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception:
                pass  # Continue with shutdown
        
        # Shutdown in reverse load order
        sorted_entries = sorted(
            self._plugins.items(),
            key=lambda x: x[1].load_order,
            reverse=True,
        )
        
        for plugin_id, entry in sorted_entries:
            if entry.plugin.state in (PluginState.ACTIVE, PluginState.PAUSED):
                try:
                    await asyncio.wait_for(
                        entry.plugin.shutdown(),
                        timeout=self._config.shutdown_timeout,
                    )
                    results[plugin_id] = True
                    await self._emit_internal(
                        RegistryEvent.PLUGIN_SHUTDOWN,
                        plugin_id=plugin_id,
                    )
                except Exception:
                    results[plugin_id] = False
        
        self._initialized = False
        return results
    
    def add_shutdown_hook(self, hook: Callable) -> None:
        """Add a hook to be called before shutdown."""
        self._shutdown_hooks.append(hook)
    
    # Event system
    
    async def emit_event(
        self,
        event: str,
        data: dict[str, Any],
        context: Optional[PluginContext] = None,
    ) -> list[PluginResult]:
        """
        Emit an event to all hook plugins.
        
        Args:
            event: Event name
            data: Event data
            context: Event context
            
        Returns:
            Results from all handlers
        """
        if not self._config.enable_hooks:
            return []
        
        context = context or PluginContext()
        results = []
        
        for hook_plugin in self.get_hooks():
            if event in hook_plugin.hook_events or "*" in hook_plugin.hook_events:
                try:
                    result = await asyncio.wait_for(
                        hook_plugin.handle_event(event, data, context),
                        timeout=self._config.hook_timeout,
                    )
                    if result:
                        results.append(result)
                except asyncio.TimeoutError:
                    results.append(PluginResult.fail(f"Hook timeout: {hook_plugin.metadata.id}"))
                except Exception as e:
                    results.append(PluginResult.fail(str(e)))
        
        return results
    
    def on(self, event: RegistryEvent, callback: Callable) -> None:
        """Register a callback for registry events."""
        event_name = event.value
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(callback)
    
    def off(self, event: RegistryEvent, callback: Callable) -> bool:
        """Unregister a callback from registry events."""
        event_name = event.value
        if event_name in self._event_listeners:
            try:
                self._event_listeners[event_name].remove(callback)
                return True
            except ValueError:
                pass
        return False
    
    async def _emit_internal(self, event: RegistryEvent, **data) -> None:
        """Emit an internal registry event."""
        event_name = event.value
        for callback in self._event_listeners.get(event_name, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_name, data)
                else:
                    callback(event_name, data)
            except Exception:
                pass  # Don't let listener errors break registry
    
    # Middleware processing
    
    async def process_request(
        self,
        request: dict[str, Any],
        context: Optional[PluginContext] = None,
    ) -> dict[str, Any]:
        """
        Process a request through all middleware.
        
        Args:
            request: The request data
            context: Request context
            
        Returns:
            Modified request data
        """
        if not self._config.enable_middleware:
            return request
        
        context = context or PluginContext()
        result = request
        
        for middleware in self.get_middleware():
            try:
                result = await middleware.process_request(result, context)
            except Exception:
                # Log error but continue with other middleware
                pass
        
        return result
    
    async def process_response(
        self,
        response: dict[str, Any],
        context: Optional[PluginContext] = None,
    ) -> dict[str, Any]:
        """
        Process a response through all middleware (reverse order).
        
        Args:
            response: The response data
            context: Response context
            
        Returns:
            Modified response data
        """
        if not self._config.enable_middleware:
            return response
        
        context = context or PluginContext()
        result = response
        
        # Process in reverse order for responses
        for middleware in reversed(self.get_middleware()):
            try:
                result = await middleware.process_response(result, context)
            except Exception:
                # Log error but continue with other middleware
                pass
        
        return result
    
    # Plugin control
    
    async def enable(self, plugin_id: str) -> bool:
        """Enable a disabled plugin."""
        entry = self._plugins.get(plugin_id)
        if not entry:
            return False
        
        entry.enabled = True
        if entry.plugin.state == PluginState.DISABLED:
            # Re-initialize
            try:
                await entry.plugin.load()
                await entry.plugin.initialize()
            except Exception:
                return False
        
        return True
    
    async def disable(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        entry = self._plugins.get(plugin_id)
        if not entry:
            return False
        
        entry.enabled = False
        if entry.plugin.state in (PluginState.ACTIVE, PluginState.PAUSED):
            try:
                await entry.plugin.shutdown()
            except Exception:
                pass
        
        entry.plugin._state = PluginState.DISABLED
        return True
    
    async def restart(self, plugin_id: str) -> bool:
        """Restart a plugin."""
        entry = self._plugins.get(plugin_id)
        if not entry:
            return False
        
        # Shutdown first
        if entry.plugin.state in (PluginState.ACTIVE, PluginState.PAUSED, PluginState.ERROR):
            try:
                await entry.plugin.shutdown()
            except Exception:
                pass
        
        # Reset state and re-initialize
        entry.plugin._state = PluginState.UNLOADED
        entry.error_count = 0
        entry.last_error = None
        
        try:
            await entry.plugin.load()
            await entry.plugin.initialize()
            return True
        except Exception as e:
            entry.error_count += 1
            entry.last_error = str(e)
            return False
    
    # Health checks
    
    async def health_check(self) -> dict[str, bool]:
        """Run health checks on all active plugins."""
        results = {}
        
        for plugin_id, entry in self._plugins.items():
            if entry.plugin.state == PluginState.ACTIVE:
                try:
                    results[plugin_id] = await asyncio.wait_for(
                        entry.plugin.health_check(),
                        timeout=5.0,
                    )
                except Exception:
                    results[plugin_id] = False
        
        return results
    
    def get_status(self) -> dict[str, Any]:
        """Get overall registry status."""
        by_state: dict[str, int] = {}
        for entry in self._plugins.values():
            state = entry.state.value
            by_state[state] = by_state.get(state, 0) + 1
        
        return {
            "initialized": self._initialized,
            "total_plugins": len(self._plugins),
            "active_plugins": len(self.active_plugins),
            "plugins_by_state": by_state,
            "config": {
                "auto_initialize": self._config.auto_initialize,
                "parallel_init": self._config.parallel_init,
                "enable_hooks": self._config.enable_hooks,
                "enable_middleware": self._config.enable_middleware,
            },
        }


# Global registry instance
_global_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def set_registry(registry: PluginRegistry) -> None:
    """Set the global plugin registry."""
    global _global_registry
    _global_registry = registry


async def register_plugin(plugin: Plugin, **kwargs) -> bool:
    """Register a plugin with the global registry."""
    return await get_registry().register(plugin, **kwargs)


async def unregister_plugin(plugin_id: str) -> bool:
    """Unregister a plugin from the global registry."""
    return await get_registry().unregister(plugin_id)
