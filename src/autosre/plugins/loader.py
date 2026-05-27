"""
Plugin Loader for AutoSRE

Provides dynamic plugin discovery and loading:
- Filesystem-based plugin discovery
- Entry point based loading (setuptools)
- Dynamic import and instantiation
- Plugin validation and verification
"""

import asyncio
import importlib
import importlib.metadata
import importlib.util
import inspect
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Type

from pydantic import BaseModel, Field

from autosre.plugins.base import (
    Plugin,
    PluginConfig,
    PluginMetadata,
    PluginState,
    PluginType,
)
from autosre.plugins.registry import PluginRegistry, get_registry


class LoaderError(Exception):
    """Base exception for plugin loader errors."""
    pass


class PluginNotFoundError(LoaderError):
    """Plugin could not be found."""
    pass


class PluginLoadError(LoaderError):
    """Plugin could not be loaded."""
    pass


class PluginValidationError(LoaderError):
    """Plugin failed validation."""
    pass


class DiscoveryMethod(str, Enum):
    """Methods for discovering plugins."""
    
    DIRECTORY = "directory"       # Scan directories for plugins
    ENTRY_POINT = "entry_point"   # Use setuptools entry points
    MODULE = "module"             # Import specific modules
    PACKAGE = "package"           # Scan packages for plugins


class LoaderConfig(BaseModel):
    """Configuration for the plugin loader."""
    
    # Discovery
    plugin_dirs: list[str] = Field(
        default_factory=lambda: ["plugins", "~/.autosre/plugins"],
        description="Directories to scan for plugins",
    )
    entry_point_group: str = Field(
        default="autosre.plugins",
        description="Entry point group for setuptools plugins",
    )
    
    # Loading
    auto_discover: bool = Field(default=True, description="Auto-discover on init")
    auto_load: bool = Field(default=True, description="Auto-load discovered plugins")
    validate_plugins: bool = Field(default=True, description="Validate plugins on load")
    
    # Safety
    sandbox_plugins: bool = Field(default=False, description="Run plugins in sandbox")
    allowed_imports: list[str] = Field(
        default_factory=list,
        description="Allowed import patterns for sandboxed plugins",
    )
    
    # Caching
    enable_cache: bool = Field(default=True, description="Cache discovered plugins")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL")


@dataclass
class DiscoveredPlugin:
    """Information about a discovered plugin."""
    
    # Source
    source: DiscoveryMethod
    path: str                       # File path or module path
    module_name: str               # Python module name
    class_name: str                # Plugin class name
    
    # Metadata (extracted if possible)
    plugin_id: Optional[str] = None
    plugin_name: Optional[str] = None
    plugin_version: Optional[str] = None
    plugin_type: Optional[PluginType] = None
    
    # Status
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validated: bool = False
    validation_error: Optional[str] = None
    loaded: bool = False
    load_error: Optional[str] = None
    
    # Reference to loaded plugin
    plugin_class: Optional[Type[Plugin]] = None
    plugin_instance: Optional[Plugin] = None


class PluginLoader:
    """
    Dynamic plugin loader for AutoSRE.
    
    Discovers and loads plugins from:
    - Local directories
    - Installed packages (entry points)
    - Specific modules
    
    Example:
        loader = PluginLoader()
        
        # Discover plugins
        discovered = await loader.discover()
        
        # Load all discovered plugins
        loaded = await loader.load_all()
        
        # Load a specific plugin
        plugin = await loader.load_from_path("/path/to/plugin.py")
        
        # Load from entry points
        plugins = await loader.load_from_entry_points()
    """
    
    def __init__(
        self,
        config: Optional[LoaderConfig] = None,
        registry: Optional[PluginRegistry] = None,
    ):
        """Initialize the plugin loader."""
        self._config = config or LoaderConfig()
        self._registry = registry or get_registry()
        self._discovered: dict[str, DiscoveredPlugin] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    @property
    def config(self) -> LoaderConfig:
        """Get loader configuration."""
        return self._config
    
    @property
    def discovered_plugins(self) -> list[DiscoveredPlugin]:
        """Get list of discovered plugins."""
        return list(self._discovered.values())
    
    # Discovery
    
    async def discover(self, force: bool = False) -> list[DiscoveredPlugin]:
        """
        Discover all available plugins.
        
        Args:
            force: Force re-discovery even if cached
            
        Returns:
            List of discovered plugins
        """
        # Check cache
        if not force and self._config.enable_cache and self._cache_timestamp:
            cache_age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
            if cache_age < self._config.cache_ttl_seconds:
                return list(self._discovered.values())
        
        self._discovered.clear()
        
        # Discover from directories
        for plugin_dir in self._config.plugin_dirs:
            discovered = await self._discover_from_directory(plugin_dir)
            for dp in discovered:
                key = f"{dp.module_name}.{dp.class_name}"
                self._discovered[key] = dp
        
        # Discover from entry points
        entry_point_plugins = await self._discover_from_entry_points()
        for dp in entry_point_plugins:
            key = f"{dp.module_name}.{dp.class_name}"
            self._discovered[key] = dp
        
        self._cache_timestamp = datetime.now(timezone.utc)
        return list(self._discovered.values())
    
    async def _discover_from_directory(self, directory: str) -> list[DiscoveredPlugin]:
        """Discover plugins in a directory."""
        discovered = []
        
        # Expand path
        dir_path = Path(os.path.expanduser(directory))
        if not dir_path.exists() or not dir_path.is_dir():
            return discovered
        
        # Scan for Python files
        for file_path in dir_path.glob("**/*.py"):
            if file_path.name.startswith("_"):
                continue
            
            try:
                plugins = await self._scan_file(file_path)
                discovered.extend(plugins)
            except Exception:
                # Skip files that can't be scanned
                pass
        
        return discovered
    
    async def _scan_file(self, file_path: Path) -> list[DiscoveredPlugin]:
        """Scan a Python file for plugin classes."""
        discovered = []
        
        # Generate module name
        module_name = f"autosre_plugin_{file_path.stem}_{hash(str(file_path)) & 0xFFFFFFFF:08x}"
        
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return discovered
        
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            # Record discovery with error
            discovered.append(DiscoveredPlugin(
                source=DiscoveryMethod.DIRECTORY,
                path=str(file_path),
                module_name=module_name,
                class_name="<unknown>",
                validation_error=str(e),
            ))
            return discovered
        
        # Find Plugin subclasses
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if self._is_plugin_class(obj):
                dp = DiscoveredPlugin(
                    source=DiscoveryMethod.DIRECTORY,
                    path=str(file_path),
                    module_name=module_name,
                    class_name=name,
                    plugin_class=obj,
                )
                
                # Try to extract metadata
                try:
                    instance = obj()
                    dp.plugin_id = instance.metadata.id
                    dp.plugin_name = instance.metadata.name
                    dp.plugin_version = instance.metadata.version
                    dp.plugin_type = instance.metadata.type
                    dp.validated = True
                except Exception as e:
                    dp.validation_error = str(e)
                
                discovered.append(dp)
        
        return discovered
    
    async def _discover_from_entry_points(self) -> list[DiscoveredPlugin]:
        """Discover plugins from setuptools entry points."""
        discovered = []
        
        try:
            eps = importlib.metadata.entry_points()
            
            # Handle both old and new entry_points API
            if hasattr(eps, 'select'):
                # Python 3.10+
                plugin_eps = eps.select(group=self._config.entry_point_group)
            else:
                # Older Python
                plugin_eps = eps.get(self._config.entry_point_group, [])
            
            for ep in plugin_eps:
                dp = DiscoveredPlugin(
                    source=DiscoveryMethod.ENTRY_POINT,
                    path=f"{ep.group}:{ep.name}",
                    module_name=ep.value.split(":")[0] if ":" in ep.value else ep.value,
                    class_name=ep.value.split(":")[1] if ":" in ep.value else ep.name,
                )
                
                # Try to load and validate
                try:
                    plugin_class = ep.load()
                    if self._is_plugin_class(plugin_class):
                        dp.plugin_class = plugin_class
                        
                        # Extract metadata
                        instance = plugin_class()
                        dp.plugin_id = instance.metadata.id
                        dp.plugin_name = instance.metadata.name
                        dp.plugin_version = instance.metadata.version
                        dp.plugin_type = instance.metadata.type
                        dp.validated = True
                except Exception as e:
                    dp.validation_error = str(e)
                
                discovered.append(dp)
                
        except Exception:
            # Entry points not available
            pass
        
        return discovered
    
    def _is_plugin_class(self, obj: Any) -> bool:
        """Check if an object is a Plugin subclass."""
        if not inspect.isclass(obj):
            return False
        if obj is Plugin:
            return False
        return issubclass(obj, Plugin)
    
    # Loading
    
    async def load_all(self) -> dict[str, Plugin]:
        """
        Load all discovered plugins.
        
        Returns:
            Dictionary of plugin_id -> plugin instance
        """
        if not self._discovered:
            await self.discover()
        
        loaded = {}
        
        for key, dp in self._discovered.items():
            if dp.plugin_class and not dp.load_error:
                try:
                    plugin = await self._load_plugin(dp)
                    if plugin:
                        loaded[plugin.metadata.id] = plugin
                        dp.loaded = True
                        dp.plugin_instance = plugin
                except Exception as e:
                    dp.load_error = str(e)
        
        return loaded
    
    async def _load_plugin(self, discovered: DiscoveredPlugin) -> Optional[Plugin]:
        """Load a discovered plugin."""
        if not discovered.plugin_class:
            return None
        
        # Validate if required
        if self._config.validate_plugins and not discovered.validated:
            if not await self._validate_plugin(discovered):
                raise PluginValidationError(
                    f"Plugin validation failed: {discovered.validation_error}"
                )
        
        # Instantiate
        try:
            plugin = discovered.plugin_class()
        except Exception as e:
            raise PluginLoadError(f"Failed to instantiate plugin: {e}")
        
        # Register with registry
        if self._config.auto_load:
            await self._registry.register(plugin)
        
        return plugin
    
    async def _validate_plugin(self, discovered: DiscoveredPlugin) -> bool:
        """Validate a discovered plugin."""
        if not discovered.plugin_class:
            discovered.validation_error = "No plugin class"
            return False
        
        try:
            # Try to instantiate
            instance = discovered.plugin_class()
            
            # Check required metadata
            metadata = instance.metadata
            if not metadata.id:
                discovered.validation_error = "Missing plugin ID"
                return False
            if not metadata.name:
                discovered.validation_error = "Missing plugin name"
                return False
            if not metadata.version:
                discovered.validation_error = "Missing plugin version"
                return False
            
            discovered.validated = True
            return True
            
        except Exception as e:
            discovered.validation_error = str(e)
            return False
    
    async def load_from_path(
        self,
        path: str,
        class_name: Optional[str] = None,
    ) -> Plugin:
        """
        Load a plugin from a file path.
        
        Args:
            path: Path to the plugin file
            class_name: Optional specific class name to load
            
        Returns:
            Loaded plugin instance
        """
        file_path = Path(os.path.expanduser(path))
        if not file_path.exists():
            raise PluginNotFoundError(f"Plugin file not found: {path}")
        
        # Scan the file
        discovered_list = await self._scan_file(file_path)
        if not discovered_list:
            raise PluginNotFoundError(f"No plugins found in: {path}")
        
        # Find the right plugin
        for dp in discovered_list:
            if class_name is None or dp.class_name == class_name:
                if dp.plugin_class:
                    plugin = await self._load_plugin(dp)
                    if plugin:
                        return plugin
                elif dp.validation_error:
                    raise PluginValidationError(dp.validation_error)
        
        raise PluginNotFoundError(
            f"Plugin class {class_name or '<any>'} not found in: {path}"
        )
    
    async def load_from_module(
        self,
        module_name: str,
        class_name: str,
    ) -> Plugin:
        """
        Load a plugin from a module.
        
        Args:
            module_name: Python module name
            class_name: Plugin class name
            
        Returns:
            Loaded plugin instance
        """
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise PluginNotFoundError(f"Module not found: {module_name}") from e
        
        if not hasattr(module, class_name):
            raise PluginNotFoundError(
                f"Class {class_name} not found in module {module_name}"
            )
        
        plugin_class = getattr(module, class_name)
        if not self._is_plugin_class(plugin_class):
            raise PluginValidationError(
                f"{class_name} is not a Plugin subclass"
            )
        
        # Create discovered entry
        dp = DiscoveredPlugin(
            source=DiscoveryMethod.MODULE,
            path=f"{module_name}:{class_name}",
            module_name=module_name,
            class_name=class_name,
            plugin_class=plugin_class,
        )
        
        return await self._load_plugin(dp)
    
    async def load_from_entry_points(self) -> dict[str, Plugin]:
        """
        Load all plugins from entry points.
        
        Returns:
            Dictionary of plugin_id -> plugin instance
        """
        discovered = await self._discover_from_entry_points()
        loaded = {}
        
        for dp in discovered:
            if dp.plugin_class and not dp.validation_error:
                try:
                    plugin = await self._load_plugin(dp)
                    if plugin:
                        loaded[plugin.metadata.id] = plugin
                except Exception:
                    pass
        
        return loaded
    
    # Unloading
    
    async def unload(self, plugin_id: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            plugin_id: ID of the plugin to unload
            
        Returns:
            True if unloaded successfully
        """
        # Unregister from registry
        result = await self._registry.unregister(plugin_id)
        
        # Update discovered entry
        for dp in self._discovered.values():
            if dp.plugin_id == plugin_id:
                dp.loaded = False
                dp.plugin_instance = None
                break
        
        return result
    
    async def reload(self, plugin_id: str) -> Optional[Plugin]:
        """
        Reload a plugin.
        
        Args:
            plugin_id: ID of the plugin to reload
            
        Returns:
            Reloaded plugin instance
        """
        # Find the discovered entry
        dp_to_reload = None
        for dp in self._discovered.values():
            if dp.plugin_id == plugin_id:
                dp_to_reload = dp
                break
        
        if not dp_to_reload:
            raise PluginNotFoundError(f"Plugin not found: {plugin_id}")
        
        # Unload first
        await self.unload(plugin_id)
        
        # Re-scan the file if it's from a directory
        if dp_to_reload.source == DiscoveryMethod.DIRECTORY:
            new_discovered = await self._scan_file(Path(dp_to_reload.path))
            for new_dp in new_discovered:
                if new_dp.class_name == dp_to_reload.class_name:
                    dp_to_reload = new_dp
                    break
        
        # Reload
        if dp_to_reload.plugin_class:
            return await self._load_plugin(dp_to_reload)
        
        return None
    
    # Utilities
    
    def get_discovery_status(self) -> dict[str, Any]:
        """Get discovery status and statistics."""
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}
        errors = []
        
        for dp in self._discovered.values():
            by_source[dp.source.value] = by_source.get(dp.source.value, 0) + 1
            if dp.plugin_type:
                by_type[dp.plugin_type.value] = by_type.get(dp.plugin_type.value, 0) + 1
            if dp.validation_error:
                errors.append({
                    "path": dp.path,
                    "error": dp.validation_error,
                })
            if dp.load_error:
                errors.append({
                    "path": dp.path,
                    "error": dp.load_error,
                })
        
        return {
            "total_discovered": len(self._discovered),
            "validated": sum(1 for dp in self._discovered.values() if dp.validated),
            "loaded": sum(1 for dp in self._discovered.values() if dp.loaded),
            "by_source": by_source,
            "by_type": by_type,
            "errors": errors,
            "cache_timestamp": self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            "config": {
                "plugin_dirs": self._config.plugin_dirs,
                "entry_point_group": self._config.entry_point_group,
                "auto_discover": self._config.auto_discover,
                "auto_load": self._config.auto_load,
            },
        }
    
    def clear_cache(self) -> None:
        """Clear the discovery cache."""
        self._discovered.clear()
        self._cache_timestamp = None


# Convenience functions

async def discover_plugins(
    plugin_dirs: Optional[list[str]] = None,
) -> list[DiscoveredPlugin]:
    """
    Discover plugins from directories.
    
    Args:
        plugin_dirs: Optional list of directories to scan
        
    Returns:
        List of discovered plugins
    """
    config = LoaderConfig()
    if plugin_dirs:
        config.plugin_dirs = plugin_dirs
    
    loader = PluginLoader(config)
    return await loader.discover()


async def load_plugin(path: str, class_name: Optional[str] = None) -> Plugin:
    """
    Load a plugin from a file path.
    
    Args:
        path: Path to the plugin file
        class_name: Optional specific class name to load
        
    Returns:
        Loaded plugin instance
    """
    loader = PluginLoader()
    return await loader.load_from_path(path, class_name)


async def load_plugins_from_directory(directory: str) -> dict[str, Plugin]:
    """
    Load all plugins from a directory.
    
    Args:
        directory: Directory path to scan
        
    Returns:
        Dictionary of plugin_id -> plugin instance
    """
    config = LoaderConfig(plugin_dirs=[directory])
    loader = PluginLoader(config)
    await loader.discover()
    return await loader.load_all()
