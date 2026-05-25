# AutoSRE Plugin System

This directory contains sample plugins demonstrating the AutoSRE plugin architecture.

## Quick Start

```python
import asyncio
from autosre.plugins import get_registry, load_plugin

async def main():
    # Load a plugin from file
    plugin = await load_plugin("examples/plugins/sample_plugin.py", "SampleMetricsPlugin")
    
    # Or use the registry directly
    registry = get_registry()
    print(f"Active plugins: {len(registry.active_plugins)}")

asyncio.run(main())
```

## Plugin Types

AutoSRE supports several plugin types:

### SkillPlugin
Add custom investigation capabilities (metrics queries, log analysis, etc.)

```python
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
        # Your skill logic here
        return PluginResult.ok({"result": "success"})
```

### IntegrationPlugin
Connect to external services (monitoring systems, cloud providers, etc.)

```python
from autosre.plugins import IntegrationPlugin, PluginMetadata

class MyIntegration(IntegrationPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="my-integration",
            name="My Integration",
            version="1.0.0",
        )
    
    async def connect(self) -> bool:
        # Connect to external service
        return True
    
    async def disconnect(self) -> None:
        # Cleanup connection
        pass
```

### HookPlugin
React to system events (incident detection, investigation progress, etc.)

```python
from autosre.plugins import HookPlugin, PluginMetadata

class MyHookPlugin(HookPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="my-hook",
            name="My Hook",
            version="1.0.0",
        )
    
    @property
    def hook_events(self) -> list[str]:
        return ["investigation.started", "investigation.completed"]
    
    async def handle_event(self, event, data, context):
        print(f"Event received: {event}")
        return None
```

### MiddlewarePlugin
Intercept and process requests/responses

```python
from autosre.plugins import MiddlewarePlugin, PluginMetadata

class MyMiddleware(MiddlewarePlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="my-middleware",
            name="My Middleware",
            version="1.0.0",
        )
    
    async def process_request(self, request, context):
        # Modify request
        return request
    
    async def process_response(self, response, context):
        # Modify response
        return response
```

## Plugin Discovery

Plugins can be discovered from:

1. **Directories**: Place `.py` files in configured plugin directories
2. **Entry Points**: Install packages with `autosre.plugins` entry points
3. **Explicit Loading**: Load specific files or modules

```python
from autosre.plugins import PluginLoader, LoaderConfig

config = LoaderConfig(
    plugin_dirs=["~/.autosre/plugins", "./my_plugins"],
    entry_point_group="autosre.plugins",
)

loader = PluginLoader(config)
discovered = await loader.discover()
loaded = await loader.load_all()
```

## Sample Plugins

This directory includes:

- `sample_plugin.py`: Contains multiple example plugins:
  - `SampleMetricsPlugin`: Demonstrates skill plugin for metrics
  - `SampleAuditPlugin`: Demonstrates hook plugin for event auditing
  - `SampleLoggingMiddleware`: Demonstrates middleware plugin
  - `SampleSlackIntegration`: Demonstrates integration plugin

## Running the Demo

```bash
cd /path/to/autosre
python examples/plugins/sample_plugin.py
```

## Creating Your Own Plugin

1. Create a new Python file in your plugins directory
2. Import the appropriate base class from `autosre.plugins`
3. Implement the required methods (`metadata`, lifecycle hooks, etc.)
4. Register with the plugin registry

The plugin system handles:
- Lifecycle management (load, initialize, shutdown)
- Event routing to hook plugins
- Middleware chain execution
- Dependency resolution
- Health checks and monitoring
