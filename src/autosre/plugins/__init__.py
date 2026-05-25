"""
Plugin System for AutoSRE

Provides extensible plugin architecture for adding custom functionality:
- Skills for new investigation capabilities
- Integrations with external services
- Custom reporters and validators
- Event hooks and middleware

Features:
- Dynamic plugin discovery and loading
- Lifecycle management (load, init, shutdown)
- Event-driven architecture
- Middleware chain processing
- Plugin dependencies and priorities

Example:
    # Create a custom skill plugin
    from autosre.plugins import SkillPlugin, PluginMetadata, PluginResult
    
    class MySkillPlugin(SkillPlugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                id="my-skill",
                name="My Custom Skill",
                version="1.0.0",
            )
        
        async def execute(self, action, parameters, context):
            # Implement skill logic
            return PluginResult.ok({"result": "success"})
    
    # Register and use
    from autosre.plugins import get_registry
    
    registry = get_registry()
    await registry.register(MySkillPlugin())
"""

from autosre.plugins.base import (
    # Base classes
    Plugin,
    SkillPlugin,
    IntegrationPlugin,
    HookPlugin,
    MiddlewarePlugin,
    # Configuration
    PluginConfig,
    PluginContext,
    PluginResult,
    # Metadata
    PluginMetadata,
    PluginState,
    PluginType,
    PluginPriority,
    PluginCapability,
)

from autosre.plugins.registry import (
    # Registry
    PluginRegistry,
    RegistryConfig,
    RegistryEvent,
    PluginEntry,
    # Global access
    get_registry,
    set_registry,
    register_plugin,
    unregister_plugin,
)

from autosre.plugins.loader import (
    # Loader
    PluginLoader,
    LoaderConfig,
    DiscoveredPlugin,
    DiscoveryMethod,
    # Exceptions
    LoaderError,
    PluginNotFoundError,
    PluginLoadError,
    PluginValidationError,
    # Convenience functions
    discover_plugins,
    load_plugin,
    load_plugins_from_directory,
)

__all__ = [
    # Base classes
    "Plugin",
    "SkillPlugin",
    "IntegrationPlugin",
    "HookPlugin",
    "MiddlewarePlugin",
    # Configuration
    "PluginConfig",
    "PluginContext",
    "PluginResult",
    # Metadata
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "PluginPriority",
    "PluginCapability",
    # Registry
    "PluginRegistry",
    "RegistryConfig",
    "RegistryEvent",
    "PluginEntry",
    "get_registry",
    "set_registry",
    "register_plugin",
    "unregister_plugin",
    # Loader
    "PluginLoader",
    "LoaderConfig",
    "DiscoveredPlugin",
    "DiscoveryMethod",
    "LoaderError",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginValidationError",
    "discover_plugins",
    "load_plugin",
    "load_plugins_from_directory",
]
