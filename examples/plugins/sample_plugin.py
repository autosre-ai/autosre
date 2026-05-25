"""
Sample Plugin for AutoSRE

This example demonstrates how to create custom plugins for AutoSRE.
It includes examples of:
- A skill plugin for custom investigation capabilities
- A hook plugin for event handling
- A middleware plugin for request/response processing

Usage:
    # Load the sample plugin
    from autosre.plugins import load_plugin, get_registry
    
    # Load from file
    plugin = await load_plugin("/path/to/sample_plugin.py", "SampleMetricsPlugin")
    
    # Or manually register
    from sample_plugin import SampleMetricsPlugin
    from autosre.plugins import get_registry
    
    registry = get_registry()
    await registry.register(SampleMetricsPlugin())
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any, Optional

from autosre.plugins import (
    # Base classes
    Plugin,
    SkillPlugin,
    HookPlugin,
    MiddlewarePlugin,
    IntegrationPlugin,
    # Configuration
    PluginConfig,
    PluginContext,
    PluginResult,
    # Metadata
    PluginMetadata,
    PluginType,
    PluginPriority,
    PluginCapability,
)

from pydantic import Field


# =============================================================================
# Example 1: Skill Plugin
# =============================================================================

class SampleMetricsConfig(PluginConfig):
    """Configuration for the sample metrics plugin."""
    
    # Custom settings
    default_time_range: str = Field(
        default="1h",
        description="Default time range for metrics queries",
    )
    max_data_points: int = Field(
        default=1000,
        description="Maximum data points to return",
    )
    simulate_latency: bool = Field(
        default=False,
        description="Simulate network latency for testing",
    )


class SampleMetricsPlugin(SkillPlugin[SampleMetricsConfig]):
    """
    A sample skill plugin that demonstrates custom metrics capabilities.
    
    This plugin simulates querying metrics from a custom monitoring system.
    Use this as a template for creating real integration plugins.
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="sample-metrics",
            name="Sample Metrics Plugin",
            version="1.0.0",
            description="Sample plugin demonstrating custom metrics integration",
            author="AutoSRE Team",
            type=PluginType.SKILL,
            capabilities=[
                PluginCapability.METRICS_QUERY,
                PluginCapability.MONITORING,
            ],
            tags=["sample", "metrics", "monitoring"],
            priority=PluginPriority.NORMAL,
        )
    
    def _default_config(self) -> SampleMetricsConfig:
        return SampleMetricsConfig()
    
    async def on_initialize(self) -> None:
        """Initialize the metrics connection."""
        # In a real plugin, you would connect to your metrics backend here
        print(f"[{self.metadata.id}] Initializing metrics plugin...")
        await asyncio.sleep(0.1)  # Simulate connection
        print(f"[{self.metadata.id}] Connected to metrics backend")
    
    async def on_shutdown(self) -> None:
        """Cleanup metrics connection."""
        print(f"[{self.metadata.id}] Shutting down metrics plugin...")
        await asyncio.sleep(0.1)
        print(f"[{self.metadata.id}] Disconnected from metrics backend")
    
    async def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        context: PluginContext,
    ) -> PluginResult:
        """
        Execute a metrics action.
        
        Supported actions:
        - query: Query metrics by name
        - list: List available metrics
        - aggregate: Get aggregated statistics
        """
        if self.config.simulate_latency:
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        if action == "query":
            return await self._query_metrics(parameters)
        elif action == "list":
            return await self._list_metrics(parameters)
        elif action == "aggregate":
            return await self._aggregate_metrics(parameters)
        else:
            return PluginResult.fail(f"Unknown action: {action}")
    
    async def _query_metrics(self, params: dict[str, Any]) -> PluginResult:
        """Query metrics by name."""
        metric_name = params.get("metric_name", "cpu_usage")
        time_range = params.get("time_range", self.config.default_time_range)
        
        # Simulate metric data
        now = datetime.utcnow()
        data_points = []
        for i in range(min(60, self.config.max_data_points)):
            timestamp = now - timedelta(minutes=60 - i)
            value = 50 + random.uniform(-20, 30)  # Simulated values
            data_points.append({
                "timestamp": timestamp.isoformat(),
                "value": round(value, 2),
            })
        
        return PluginResult.ok({
            "metric_name": metric_name,
            "time_range": time_range,
            "data_points": data_points,
            "unit": "percent",
        })
    
    async def _list_metrics(self, params: dict[str, Any]) -> PluginResult:
        """List available metrics."""
        prefix = params.get("prefix", "")
        
        # Simulated metrics list
        all_metrics = [
            {"name": "cpu_usage", "type": "gauge", "unit": "percent"},
            {"name": "memory_usage", "type": "gauge", "unit": "bytes"},
            {"name": "disk_io_read", "type": "counter", "unit": "bytes/sec"},
            {"name": "disk_io_write", "type": "counter", "unit": "bytes/sec"},
            {"name": "network_rx", "type": "counter", "unit": "bytes/sec"},
            {"name": "network_tx", "type": "counter", "unit": "bytes/sec"},
            {"name": "request_count", "type": "counter", "unit": "requests"},
            {"name": "request_latency", "type": "histogram", "unit": "ms"},
            {"name": "error_rate", "type": "gauge", "unit": "percent"},
        ]
        
        if prefix:
            all_metrics = [m for m in all_metrics if m["name"].startswith(prefix)]
        
        return PluginResult.ok({
            "metrics": all_metrics,
            "total": len(all_metrics),
        })
    
    async def _aggregate_metrics(self, params: dict[str, Any]) -> PluginResult:
        """Get aggregated statistics for a metric."""
        metric_name = params.get("metric_name", "cpu_usage")
        
        # Simulated aggregation
        return PluginResult.ok({
            "metric_name": metric_name,
            "aggregations": {
                "min": round(random.uniform(10, 30), 2),
                "max": round(random.uniform(70, 95), 2),
                "avg": round(random.uniform(40, 60), 2),
                "p50": round(random.uniform(45, 55), 2),
                "p95": round(random.uniform(75, 85), 2),
                "p99": round(random.uniform(85, 92), 2),
            },
            "sample_count": random.randint(1000, 5000),
        })
    
    def get_actions(self) -> list[dict[str, Any]]:
        """Document available actions."""
        return [
            {
                "name": "query",
                "description": "Query metrics by name",
                "parameters": {
                    "metric_name": {"type": "string", "required": True},
                    "time_range": {"type": "string", "default": "1h"},
                },
            },
            {
                "name": "list",
                "description": "List available metrics",
                "parameters": {
                    "prefix": {"type": "string", "default": ""},
                },
            },
            {
                "name": "aggregate",
                "description": "Get aggregated statistics",
                "parameters": {
                    "metric_name": {"type": "string", "required": True},
                },
            },
        ]


# =============================================================================
# Example 2: Hook Plugin
# =============================================================================

class SampleAuditPlugin(HookPlugin[PluginConfig]):
    """
    A sample hook plugin that logs all investigation events.
    
    This demonstrates how to create plugins that respond to system events
    for auditing, monitoring, or custom integrations.
    """
    
    def __init__(self):
        super().__init__()
        self._event_log: list[dict[str, Any]] = []
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="sample-audit",
            name="Sample Audit Plugin",
            version="1.0.0",
            description="Sample plugin demonstrating event auditing",
            author="AutoSRE Team",
            type=PluginType.HOOK,
            tags=["sample", "audit", "logging"],
            priority=PluginPriority.LOW,
        )
    
    @property
    def hook_events(self) -> list[str]:
        """Events this plugin handles."""
        return [
            "investigation.started",
            "investigation.completed",
            "hypothesis.created",
            "evidence.collected",
            "action.executed",
            "*",  # Catch-all for any event
        ]
    
    async def handle_event(
        self,
        event: str,
        data: dict[str, Any],
        context: PluginContext,
    ) -> Optional[PluginResult]:
        """Handle an event by logging it."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data,
            "request_id": context.request_id,
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
        }
        
        self._event_log.append(entry)
        
        # Keep only last 1000 events
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-1000:]
        
        print(f"[AUDIT] {event}: {data}")
        
        return PluginResult.ok({"logged": True, "entry_id": len(self._event_log)})
    
    def get_event_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent event log entries."""
        return self._event_log[-limit:]


# =============================================================================
# Example 3: Middleware Plugin
# =============================================================================

class SampleLoggingMiddleware(MiddlewarePlugin[PluginConfig]):
    """
    A sample middleware plugin that logs all requests and responses.
    
    This demonstrates how to intercept and process data flowing
    through the system.
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="sample-logging-middleware",
            name="Sample Logging Middleware",
            version="1.0.0",
            description="Sample middleware that logs requests/responses",
            author="AutoSRE Team",
            type=PluginType.MIDDLEWARE,
            tags=["sample", "logging", "middleware"],
            priority=PluginPriority.HIGH,  # Run early in the chain
        )
    
    async def process_request(
        self,
        request: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any]:
        """Log and potentially modify incoming requests."""
        print(f"[REQUEST] {context.request_id}: {request.get('action', 'unknown')}")
        
        # Add timing metadata
        request["_middleware_timestamp"] = datetime.utcnow().isoformat()
        request["_middleware_request_id"] = context.request_id
        
        return request
    
    async def process_response(
        self,
        response: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any]:
        """Log and potentially modify outgoing responses."""
        # Calculate processing time if timestamp available
        if "_middleware_timestamp" in response:
            start = datetime.fromisoformat(response["_middleware_timestamp"])
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            print(f"[RESPONSE] {context.request_id}: completed in {duration:.2f}ms")
            response["_processing_time_ms"] = duration
        
        return response


# =============================================================================
# Example 4: Integration Plugin
# =============================================================================

class SampleSlackIntegration(IntegrationPlugin[PluginConfig]):
    """
    A sample integration plugin for Slack notifications.
    
    This demonstrates how to create plugins that connect to external services.
    """
    
    def __init__(self, webhook_url: str = ""):
        super().__init__()
        self._webhook_url = webhook_url
        self._connected = False
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="sample-slack",
            name="Sample Slack Integration",
            version="1.0.0",
            description="Sample plugin demonstrating Slack integration",
            author="AutoSRE Team",
            type=PluginType.INTEGRATION,
            capabilities=[
                PluginCapability.NOTIFICATION,
                PluginCapability.ALERTING,
            ],
            tags=["sample", "slack", "notification"],
        )
    
    async def connect(self) -> bool:
        """Connect to Slack."""
        print(f"[{self.metadata.id}] Connecting to Slack...")
        
        # In a real plugin, you would validate the webhook URL
        # and potentially fetch workspace info
        await asyncio.sleep(0.1)  # Simulate connection
        
        self._connected = True
        print(f"[{self.metadata.id}] Connected to Slack workspace")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        print(f"[{self.metadata.id}] Disconnecting from Slack...")
        self._connected = False
    
    async def send_message(
        self,
        channel: str,
        message: str,
        blocks: Optional[list[dict]] = None,
    ) -> PluginResult:
        """Send a message to a Slack channel."""
        if not self._connected:
            return PluginResult.fail("Not connected to Slack")
        
        # In a real plugin, you would make an HTTP request to Slack
        print(f"[Slack] Sending to #{channel}: {message}")
        
        return PluginResult.ok({
            "channel": channel,
            "message": message,
            "sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    async def send_alert(
        self,
        channel: str,
        alert_name: str,
        severity: str,
        description: str,
    ) -> PluginResult:
        """Send a formatted alert to Slack."""
        emoji = {
            "critical": ":red_circle:",
            "warning": ":large_orange_circle:",
            "info": ":large_blue_circle:",
        }.get(severity.lower(), ":white_circle:")
        
        message = f"{emoji} *{alert_name}* ({severity})\n{description}"
        return await self.send_message(channel, message)


# =============================================================================
# Registration Helper
# =============================================================================

def get_all_sample_plugins() -> list[Plugin]:
    """Get all sample plugins for easy registration."""
    return [
        SampleMetricsPlugin(),
        SampleAuditPlugin(),
        SampleLoggingMiddleware(),
        SampleSlackIntegration(),
    ]


async def register_all_samples() -> None:
    """Register all sample plugins with the global registry."""
    from autosre.plugins import get_registry
    
    registry = get_registry()
    for plugin in get_all_sample_plugins():
        await registry.register(plugin)
    
    print(f"Registered {len(get_all_sample_plugins())} sample plugins")


# =============================================================================
# Main - Demo usage
# =============================================================================

async def main():
    """Demonstrate sample plugin usage."""
    from autosre.plugins import get_registry, PluginContext
    
    print("=" * 60)
    print("AutoSRE Sample Plugin Demo")
    print("=" * 60)
    
    # Get registry
    registry = get_registry()
    
    # Register sample plugins
    await register_all_samples()
    
    # List registered plugins
    print("\nRegistered plugins:")
    for plugin_info in registry.list_plugins():
        print(f"  - {plugin_info['name']} ({plugin_info['id']}) [{plugin_info['state']}]")
    
    # Use the metrics plugin
    print("\n--- Metrics Plugin Demo ---")
    metrics_plugin = registry.get("sample-metrics")
    if metrics_plugin and isinstance(metrics_plugin, SampleMetricsPlugin):
        # List metrics
        result = await metrics_plugin.execute(
            "list",
            {"prefix": ""},
            PluginContext(request_id="demo-001"),
        )
        print(f"Available metrics: {result.data['total']}")
        
        # Query metrics
        result = await metrics_plugin.execute(
            "query",
            {"metric_name": "cpu_usage"},
            PluginContext(request_id="demo-002"),
        )
        print(f"CPU usage data points: {len(result.data['data_points'])}")
    
    # Emit events for the hook plugin
    print("\n--- Hook Plugin Demo ---")
    await registry.emit_event(
        "investigation.started",
        {"alert_id": "ALERT-123", "severity": "critical"},
        PluginContext(request_id="demo-003", user_id="admin"),
    )
    
    # Use middleware
    print("\n--- Middleware Demo ---")
    request = {"action": "investigate", "alert_id": "ALERT-123"}
    request = await registry.process_request(
        request,
        PluginContext(request_id="demo-004"),
    )
    print(f"Request with middleware: {request}")
    
    # Shutdown all plugins
    print("\n--- Shutting down ---")
    await registry.shutdown_all()
    
    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(main())
