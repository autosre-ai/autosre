"""
Plugin Base Classes for AutoSRE

Provides the foundation for creating extensible plugins:
- Plugin base class with lifecycle hooks
- Plugin metadata and versioning
- Event handling and hooks
- Configuration management
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Generic

from pydantic import BaseModel, ConfigDict, Field


class PluginState(str, Enum):
    """Plugin lifecycle states."""
    
    UNLOADED = "unloaded"       # Not yet loaded
    LOADING = "loading"         # Currently loading
    LOADED = "loaded"           # Loaded but not initialized
    INITIALIZING = "initializing"  # Currently initializing
    ACTIVE = "active"           # Running and active
    PAUSED = "paused"           # Temporarily paused
    STOPPING = "stopping"       # Currently stopping
    STOPPED = "stopped"         # Stopped but can restart
    ERROR = "error"             # Error state
    DISABLED = "disabled"       # Explicitly disabled


class PluginPriority(int, Enum):
    """Plugin execution priority (lower = higher priority)."""
    
    CRITICAL = 0        # System-critical plugins
    HIGH = 10           # High priority integrations
    NORMAL = 50         # Standard plugins
    LOW = 100           # Background/optional plugins
    LOWEST = 200        # Lowest priority


class PluginType(str, Enum):
    """Types of plugins supported by AutoSRE."""
    
    SKILL = "skill"                 # New investigation skills
    INTEGRATION = "integration"     # External service integrations
    REPORTER = "reporter"           # Output/reporting plugins
    VALIDATOR = "validator"         # Input/output validators
    HOOK = "hook"                   # Event hooks/callbacks
    MIDDLEWARE = "middleware"       # Request/response middleware
    PROVIDER = "provider"           # Data/service providers
    CUSTOM = "custom"               # Custom plugin type


class PluginCapability(str, Enum):
    """Capabilities a plugin can provide."""
    
    # Investigation capabilities
    METRICS_QUERY = "metrics_query"
    LOGS_QUERY = "logs_query"
    TRACES_QUERY = "traces_query"
    TOPOLOGY_DISCOVERY = "topology_discovery"
    INCIDENT_DETECTION = "incident_detection"
    
    # Action capabilities
    REMEDIATION = "remediation"
    SCALING = "scaling"
    RESTART = "restart"
    ROLLBACK = "rollback"
    
    # Communication capabilities
    NOTIFICATION = "notification"
    ALERTING = "alerting"
    REPORTING = "reporting"
    
    # Integration capabilities
    CLOUD_PROVIDER = "cloud_provider"
    CONTAINER_RUNTIME = "container_runtime"
    ORCHESTRATOR = "orchestrator"
    MONITORING = "monitoring"
    LOGGING = "logging"
    
    # Other
    CUSTOM = "custom"


class PluginMetadata(BaseModel):
    """Metadata describing a plugin."""
    
    # Identification
    id: str = Field(..., description="Unique plugin identifier")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Semantic version string")
    
    # Description
    description: str = Field(default="", description="Plugin description")
    author: str = Field(default="", description="Plugin author")
    license: str = Field(default="MIT", description="Plugin license")
    homepage: str = Field(default="", description="Plugin homepage URL")
    
    # Classification
    type: PluginType = Field(default=PluginType.CUSTOM)
    capabilities: list[PluginCapability] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    
    # Dependencies
    autosre_version: str = Field(default=">=0.2.0", description="Compatible AutoSRE versions")
    dependencies: list[str] = Field(default_factory=list, description="Plugin dependencies")
    python_requires: str = Field(default=">=3.10", description="Python version requirement")
    
    # Execution
    priority: PluginPriority = Field(default=PluginPriority.NORMAL)
    singleton: bool = Field(default=True, description="Only one instance allowed")
    
    # Permissions
    required_permissions: list[str] = Field(default_factory=list)
    optional_permissions: list[str] = Field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "type": self.type.value,
            "capabilities": [c.value for c in self.capabilities],
            "tags": self.tags,
            "autosre_version": self.autosre_version,
            "dependencies": self.dependencies,
            "priority": self.priority.value,
            "singleton": self.singleton,
            "required_permissions": self.required_permissions,
        }


class PluginConfig(BaseModel):
    """Base configuration for plugins."""
    
    enabled: bool = Field(default=True, description="Whether plugin is enabled")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    timeout_seconds: int = Field(default=30, ge=1, description="Operation timeout")
    retry_attempts: int = Field(default=3, ge=0, description="Retry attempts on failure")
    
    # Custom configuration storage
    settings: dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(extra="allow")


@dataclass
class PluginContext:
    """Runtime context passed to plugins."""
    
    # Request context
    request_id: str = ""
    correlation_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    
    # Runtime
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Services (injected at runtime)
    services: dict[str, Any] = field(default_factory=dict)
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get an injected service by name."""
        return self.services.get(name)


@dataclass
class PluginResult:
    """Result of a plugin operation."""
    
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, data: Any = None, **metadata) -> "PluginResult":
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, **metadata) -> "PluginResult":
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


ConfigT = TypeVar("ConfigT", bound=PluginConfig)


class Plugin(ABC, Generic[ConfigT]):
    """
    Base class for all AutoSRE plugins.
    
    Provides lifecycle management, configuration, and hook support.
    Subclass this to create custom plugins.
    
    Example:
        class MyPlugin(Plugin[MyPluginConfig]):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    id="my-plugin",
                    name="My Plugin",
                    version="1.0.0",
                )
            
            async def initialize(self) -> None:
                # Setup code here
                pass
            
            async def shutdown(self) -> None:
                # Cleanup code here
                pass
    """
    
    def __init__(self, config: Optional[ConfigT] = None):
        """Initialize plugin with optional configuration."""
        self._config = config or self._default_config()
        self._state = PluginState.UNLOADED
        self._error: Optional[str] = None
        self._initialized_at: Optional[datetime] = None
        self._hooks: dict[str, list[Callable]] = {}
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata. Must be implemented by subclasses."""
        pass
    
    @property
    def config(self) -> ConfigT:
        """Get plugin configuration."""
        return self._config
    
    @property
    def state(self) -> PluginState:
        """Get current plugin state."""
        return self._state
    
    @property
    def is_active(self) -> bool:
        """Check if plugin is active."""
        return self._state == PluginState.ACTIVE
    
    @property
    def error(self) -> Optional[str]:
        """Get error message if in error state."""
        return self._error
    
    def _default_config(self) -> ConfigT:
        """Create default configuration. Override for custom config classes."""
        return PluginConfig()  # type: ignore
    
    # Lifecycle methods
    
    async def load(self) -> None:
        """
        Called when the plugin is loaded.
        
        Override to perform initial loading (e.g., import dependencies).
        """
        self._state = PluginState.LOADING
        try:
            await self.on_load()
            self._state = PluginState.LOADED
        except Exception as e:
            self._state = PluginState.ERROR
            self._error = str(e)
            raise
    
    async def initialize(self) -> None:
        """
        Called when the plugin is initialized.
        
        Override to perform setup (e.g., connect to services, load data).
        """
        if self._state not in (PluginState.LOADED, PluginState.STOPPED):
            raise RuntimeError(f"Cannot initialize plugin in state: {self._state}")
        
        self._state = PluginState.INITIALIZING
        try:
            await self.on_initialize()
            self._state = PluginState.ACTIVE
            self._initialized_at = datetime.now(timezone.utc)
            self._error = None
        except Exception as e:
            self._state = PluginState.ERROR
            self._error = str(e)
            raise
    
    async def shutdown(self) -> None:
        """
        Called when the plugin is being shut down.
        
        Override to perform cleanup (e.g., close connections, flush buffers).
        """
        if self._state not in (PluginState.ACTIVE, PluginState.PAUSED, PluginState.ERROR):
            return  # Nothing to shutdown
        
        self._state = PluginState.STOPPING
        try:
            await self.on_shutdown()
            self._state = PluginState.STOPPED
        except Exception as e:
            self._state = PluginState.ERROR
            self._error = str(e)
            raise
    
    async def pause(self) -> None:
        """Temporarily pause the plugin."""
        if self._state != PluginState.ACTIVE:
            return
        
        await self.on_pause()
        self._state = PluginState.PAUSED
    
    async def resume(self) -> None:
        """Resume a paused plugin."""
        if self._state != PluginState.PAUSED:
            return
        
        await self.on_resume()
        self._state = PluginState.ACTIVE
    
    # Lifecycle hooks - override these in subclasses
    
    async def on_load(self) -> None:
        """Hook called during load phase."""
        pass
    
    async def on_initialize(self) -> None:
        """Hook called during initialization phase."""
        pass
    
    async def on_shutdown(self) -> None:
        """Hook called during shutdown phase."""
        pass
    
    async def on_pause(self) -> None:
        """Hook called when pausing."""
        pass
    
    async def on_resume(self) -> None:
        """Hook called when resuming."""
        pass
    
    # Event hooks
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a callback for an event."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
    
    def unregister_hook(self, event: str, callback: Callable) -> bool:
        """Unregister a callback from an event."""
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)
            return True
        return False
    
    async def emit(self, event: str, *args, **kwargs) -> list[Any]:
        """Emit an event to all registered callbacks."""
        results = []
        for callback in self._hooks.get(event, []):
            if asyncio.iscoroutinefunction(callback):
                result = await callback(*args, **kwargs)
            else:
                result = callback(*args, **kwargs)
            results.append(result)
        return results
    
    # Health and status
    
    async def health_check(self) -> bool:
        """
        Check if the plugin is healthy.
        
        Override to implement custom health checks.
        """
        return self._state == PluginState.ACTIVE
    
    def get_status(self) -> dict[str, Any]:
        """Get plugin status information."""
        return {
            "id": self.metadata.id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "state": self._state.value,
            "error": self._error,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "config_enabled": self._config.enabled,
        }
    
    # String representation
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.metadata.id} state={self._state.value}>"


class SkillPlugin(Plugin[ConfigT]):
    """
    Base class for skill plugins that add investigation capabilities.
    
    Skill plugins can:
    - Query metrics, logs, and traces
    - Perform remediation actions
    - Provide domain-specific knowledge
    """
    
    @property
    def skill_name(self) -> str:
        """Get the skill name for registration."""
        return self.metadata.id
    
    @abstractmethod
    async def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        context: PluginContext,
    ) -> PluginResult:
        """
        Execute a skill action.
        
        Args:
            action: The action to perform
            parameters: Action parameters
            context: Execution context
            
        Returns:
            PluginResult with the action outcome
        """
        pass
    
    def get_actions(self) -> list[dict[str, Any]]:
        """
        Get list of available actions.
        
        Override to provide action documentation.
        """
        return []


class IntegrationPlugin(Plugin[ConfigT]):
    """
    Base class for integration plugins that connect to external services.
    
    Integration plugins can:
    - Connect to cloud providers
    - Integrate with monitoring systems
    - Connect to ticketing systems
    """
    
    @property
    def integration_name(self) -> str:
        """Get the integration name for registration."""
        return self.metadata.id
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the external service.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the external service."""
        pass
    
    async def on_initialize(self) -> None:
        """Connect to service during initialization."""
        connected = await self.connect()
        if not connected:
            raise RuntimeError(f"Failed to connect to {self.integration_name}")
    
    async def on_shutdown(self) -> None:
        """Disconnect from service during shutdown."""
        await self.disconnect()


class HookPlugin(Plugin[ConfigT]):
    """
    Base class for hook plugins that respond to system events.
    
    Hook plugins can:
    - React to incidents
    - Monitor investigation progress
    - Log and audit actions
    """
    
    @property
    def hook_events(self) -> list[str]:
        """
        List of events this plugin handles.
        
        Override to specify which events to subscribe to.
        """
        return []
    
    @abstractmethod
    async def handle_event(
        self,
        event: str,
        data: dict[str, Any],
        context: PluginContext,
    ) -> Optional[PluginResult]:
        """
        Handle an event.
        
        Args:
            event: Event name
            data: Event data
            context: Event context
            
        Returns:
            Optional result to pass to other handlers
        """
        pass


class MiddlewarePlugin(Plugin[ConfigT]):
    """
    Base class for middleware plugins that intercept requests/responses.
    
    Middleware plugins can:
    - Transform inputs before processing
    - Modify outputs before delivery
    - Add validation or enrichment
    """
    
    @property
    def priority(self) -> int:
        """Middleware execution priority (lower = earlier)."""
        return self.metadata.priority.value
    
    async def process_request(
        self,
        request: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any]:
        """
        Process an incoming request.
        
        Args:
            request: The request data
            context: Request context
            
        Returns:
            Modified request data
        """
        return request
    
    async def process_response(
        self,
        response: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any]:
        """
        Process an outgoing response.
        
        Args:
            response: The response data
            context: Response context
            
        Returns:
            Modified response data
        """
        return response
