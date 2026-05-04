"""OpenSRE MCP Server - Exposes OpenSRE as an MCP tool server.

This module provides an MCP (Model Context Protocol) server that exposes
OpenSRE's incident investigation capabilities to any MCP-compatible AI
assistant (Claude Desktop, VS Code, etc.).

Usage:
    opensre mcp              # Run via CLI
    python -m opensre_core.mcp_server  # Run directly
"""

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

# Create server instance
server = Server("opensre")

# Global orchestrator (lazy-initialized)
_orchestrator = None
_prometheus = None
_kubernetes = None
_runbook_manager = None


def get_orchestrator():
    """Lazy-initialize the orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        from opensre_core.agents.orchestrator import Orchestrator
        _orchestrator = Orchestrator()
    return _orchestrator


def get_prometheus():
    """Lazy-initialize Prometheus adapter."""
    global _prometheus
    if _prometheus is None:
        from opensre_core.adapters.prometheus import PrometheusAdapter
        _prometheus = PrometheusAdapter()
    return _prometheus


def get_kubernetes():
    """Lazy-initialize Kubernetes adapter."""
    global _kubernetes
    if _kubernetes is None:
        from opensre_core.adapters.kubernetes import KubernetesAdapter
        _kubernetes = KubernetesAdapter()
    return _kubernetes


def get_runbook_manager():
    """Lazy-initialize runbook manager."""
    global _runbook_manager
    if _runbook_manager is None:
        from opensre_core.runbooks.manager import RunbookManager
        _runbook_manager = RunbookManager()
    return _runbook_manager


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available OpenSRE tools."""
    return [
        Tool(
            name="investigate",
            description="Investigate a Kubernetes incident using AI-powered analysis. Returns root cause, confidence score, observations, and recommended actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue": {
                        "type": "string",
                        "description": "Description of the issue to investigate (e.g., 'high memory usage in payment service', 'pod crashlooping', '5xx errors on API')"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace to investigate",
                        "default": "default"
                    },
                },
                "required": ["issue"],
            },
        ),
        Tool(
            name="status",
            description="Get the health status of OpenSRE connections (Prometheus, Kubernetes, LLM)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_namespaces",
            description="List all Kubernetes namespaces available in the cluster",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_pods",
            description="Get pods in a namespace with their status, ready state, and restart count",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace",
                        "default": "default"
                    },
                },
            },
        ),
        Tool(
            name="get_events",
            description="Get recent Kubernetes events (warnings) in a namespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace",
                        "default": "default"
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "Get events from last N minutes",
                        "default": 15
                    },
                },
            },
        ),
        Tool(
            name="get_pod_logs",
            description="Get logs from a specific pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Pod name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace",
                        "default": "default"
                    },
                    "container": {
                        "type": "string",
                        "description": "Container name (optional, uses first container if not specified)"
                    },
                    "tail_lines": {
                        "type": "integer",
                        "description": "Number of lines to return from end of logs",
                        "default": 100
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="describe_pod",
            description="Get detailed information about a specific pod including status, containers, and events",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Pod name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace",
                        "default": "default"
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="query_prometheus",
            description="Execute a PromQL query against Prometheus",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query (e.g., 'up', 'node_memory_MemAvailable_bytes')"
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_service_metrics",
            description="Get common metrics for a service (CPU, memory, request rate, error rate, latency)",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace",
                        "default": "default"
                    },
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="get_alerts",
            description="Get currently firing Prometheus alerts",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="search_runbooks",
            description="Search runbooks for a given issue or symptom",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'OOMKilled', 'high latency', 'crashloop')"
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_runbooks",
            description="List all available runbooks",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle tool calls."""
    try:
        if name == "investigate":
            return await _handle_investigate(arguments)
        elif name == "status":
            return await _handle_status()
        elif name == "list_namespaces":
            return await _handle_list_namespaces()
        elif name == "get_pods":
            return await _handle_get_pods(arguments)
        elif name == "get_events":
            return await _handle_get_events(arguments)
        elif name == "get_pod_logs":
            return await _handle_get_pod_logs(arguments)
        elif name == "describe_pod":
            return await _handle_describe_pod(arguments)
        elif name == "query_prometheus":
            return await _handle_query_prometheus(arguments)
        elif name == "get_service_metrics":
            return await _handle_get_service_metrics(arguments)
        elif name == "get_alerts":
            return await _handle_get_alerts()
        elif name == "search_runbooks":
            return await _handle_search_runbooks(arguments)
        elif name == "list_runbooks":
            return await _handle_list_runbooks()
        else:
            return _error_result(f"Unknown tool: {name}")
    except Exception as e:
        return _error_result(f"Error: {str(e)}")


def _text_result(text: str) -> CallToolResult:
    """Create a text result."""
    return CallToolResult(content=[TextContent(type="text", text=text)])


def _error_result(message: str) -> CallToolResult:
    """Create an error result."""
    return CallToolResult(content=[TextContent(type="text", text=f"❌ {message}")], isError=True)


async def _handle_investigate(arguments: dict) -> CallToolResult:
    """Handle the investigate tool."""
    orchestrator = get_orchestrator()

    result = await orchestrator.investigate(
        issue=arguments["issue"],
        namespace=arguments.get("namespace", "default"),
    )

    # Format result
    output = f"""## 🔍 Investigation: {result.issue}

**Root Cause:** {result.root_cause}
**Confidence:** {result.confidence:.0%}
**Status:** {result.status}
**Namespace:** {result.namespace}

### 📊 Key Observations ({len(result.observations)})
"""
    for obs in result.observations[:10]:
        severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(obs.severity, "⚪")
        output += f"- {severity_emoji} [{obs.source}] {obs.summary}\n"

    if result.contributing_factors:
        output += "\n### 📋 Contributing Factors\n"
        for factor in result.contributing_factors:
            output += f"- {factor}\n"

    output += f"\n### ⚡ Recommended Actions ({len(result.actions)})\n"
    for i, action in enumerate(result.actions, 1):
        risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(action.risk.value.upper(), "⚪")
        output += f"\n**{i}. {action.description}** {risk_emoji} {action.risk.value}\n"
        output += f"```bash\n{action.command}\n```\n"

    if result.similar_incidents:
        output += "\n### 📚 Similar Incidents / Runbooks\n"
        for incident in result.similar_incidents[:5]:
            output += f"- {incident}\n"

    return _text_result(output)


async def _handle_status() -> CallToolResult:
    """Handle the status tool."""
    prom = get_prometheus()
    k8s = get_kubernetes()

    output = "## 🛡️ OpenSRE Status\n\n"

    # Check Prometheus
    try:
        prom_health = await prom.health_check()
        output += f"**Prometheus:** ✅ {prom_health['status']} - {prom_health.get('details', '')}\n"
    except Exception as e:
        output += f"**Prometheus:** ❌ Error - {str(e)[:50]}\n"

    # Check Kubernetes
    try:
        k8s_health = await k8s.health_check()
        output += f"**Kubernetes:** ✅ {k8s_health['status']} - {k8s_health.get('details', '')}\n"
    except Exception as e:
        output += f"**Kubernetes:** ❌ Error - {str(e)[:50]}\n"

    # Check LLM
    try:
        from opensre_core.adapters.llm import LLMAdapter
        llm = LLMAdapter()
        llm_health = await llm.health_check()
        output += f"**LLM:** ✅ {llm_health['status']} - {llm_health.get('details', '')}\n"
    except Exception as e:
        output += f"**LLM:** ❌ Error - {str(e)[:50]}\n"

    return _text_result(output)


async def _handle_list_namespaces() -> CallToolResult:
    """Handle list_namespaces tool."""
    k8s = get_kubernetes()

    # Get all pods to extract namespaces
    pods = await k8s.get_pods(namespace="all")
    namespaces = sorted({p.namespace for p in pods})

    output = "## Kubernetes Namespaces\n\n"
    for ns in namespaces:
        output += f"- {ns}\n"

    return _text_result(output)


async def _handle_get_pods(arguments: dict) -> CallToolResult:
    """Handle get_pods tool."""
    k8s = get_kubernetes()
    namespace = arguments.get("namespace", "default")

    pods = await k8s.get_pods(namespace=namespace)

    if not pods:
        return _text_result(f"No pods found in namespace '{namespace}'")

    output = f"## Pods in {namespace}\n\n"
    for pod in pods:
        status_emoji = "✅" if pod.ready else "❌"
        output += f"- {status_emoji} **{pod.name}** - {pod.status} (restarts: {pod.restarts}, age: {pod.age})\n"

        # Show container states if any are not running
        for container in pod.containers:
            if not container.get("ready"):
                output += f"  - Container `{container['name']}`: {container['state']}\n"

    return _text_result(output)


async def _handle_get_events(arguments: dict) -> CallToolResult:
    """Handle get_events tool."""
    k8s = get_kubernetes()
    namespace = arguments.get("namespace", "default")
    minutes = arguments.get("minutes", 15)

    events = await k8s.get_events(namespace=namespace, minutes=minutes)

    # Filter to warnings only
    warning_events = [e for e in events if e.type == "Warning"]

    if not warning_events:
        return _text_result(f"No warning events in namespace '{namespace}' in the last {minutes} minutes.")

    output = f"## ⚠️ Warning Events in {namespace} (last {minutes} min)\n\n"
    for event in warning_events[:20]:
        output += f"- **{event.reason}**: {event.message}\n"
        output += f"  - Object: {event.involved_object} (count: {event.count})\n"

    return _text_result(output)


async def _handle_get_pod_logs(arguments: dict) -> CallToolResult:
    """Handle get_pod_logs tool."""
    k8s = get_kubernetes()

    name = arguments["name"]
    namespace = arguments.get("namespace", "default")
    container = arguments.get("container")
    tail_lines = arguments.get("tail_lines", 100)

    logs = await k8s.get_pod_logs(
        name=name,
        namespace=namespace,
        container=container,
        tail_lines=tail_lines,
    )

    container_str = f" (container: {container})" if container else ""
    output = f"## Logs: {name}{container_str}\n\n```\n{logs}\n```"

    return _text_result(output)


async def _handle_describe_pod(arguments: dict) -> CallToolResult:
    """Handle describe_pod tool."""
    k8s = get_kubernetes()

    name = arguments["name"]
    namespace = arguments.get("namespace", "default")

    pod = await k8s.get_pod(name=name, namespace=namespace)

    output = f"""## Pod: {pod.name}

**Namespace:** {pod.namespace}
**Status:** {pod.status}
**Ready:** {"✅ Yes" if pod.ready else "❌ No"}
**Restarts:** {pod.restarts}
**Age:** {pod.age}
**Node:** {pod.node or "N/A"}

### Containers
"""
    for container in pod.containers:
        ready_emoji = "✅" if container.get("ready") else "❌"
        output += f"- {ready_emoji} **{container['name']}**: {container['state']} (restarts: {container['restarts']})\n"

    if pod.events:
        output += "\n### Recent Events\n"
        for event in pod.events[-10:]:
            event_emoji = "⚠️" if event.get("type") == "Warning" else "ℹ️"
            output += f"- {event_emoji} **{event['reason']}**: {event['message']}\n"

    # Resource info
    if pod.memory_limit or pod.cpu_limit:
        output += "\n### Resources\n"
        if pod.cpu_request or pod.cpu_limit:
            output += f"- **CPU:** request={pod.cpu_request or 'N/A'} limit={pod.cpu_limit or 'N/A'}\n"
        if pod.memory_request or pod.memory_limit:
            mem_req = f"{pod.memory_request / (1024**2):.0f}Mi" if pod.memory_request else "N/A"
            mem_limit = f"{pod.memory_limit / (1024**2):.0f}Mi" if pod.memory_limit else "N/A"
            output += f"- **Memory:** request={mem_req} limit={mem_limit}\n"

    return _text_result(output)


async def _handle_query_prometheus(arguments: dict) -> CallToolResult:
    """Handle query_prometheus tool."""
    prom = get_prometheus()
    query = arguments["query"]

    results = await prom.query(query)

    if not results:
        return _text_result(f"No results for query: `{query}`")

    output = f"## Prometheus Query Results\n\n**Query:** `{query}`\n\n"

    for result in results[:20]:
        labels_str = ", ".join(f"{k}={v}" for k, v in result.labels.items())
        output += f"- **{result.metric_name}**{{{labels_str}}}: {result.current_value}\n"

    if len(results) > 20:
        output += f"\n*...and {len(results) - 20} more results*"

    return _text_result(output)


async def _handle_get_service_metrics(arguments: dict) -> CallToolResult:
    """Handle get_service_metrics tool."""
    prom = get_prometheus()
    service = arguments["service"]
    namespace = arguments.get("namespace", "default")

    metrics = await prom.get_service_metrics(service=service, namespace=namespace)

    output = f"## Metrics for {service} ({namespace})\n\n"

    if metrics.get("cpu_usage") is not None:
        output += f"- **CPU Usage:** {metrics['cpu_usage']:.2%}\n"
    if metrics.get("memory_usage") is not None:
        mem_mb = metrics['memory_usage'] / (1024**2)
        output += f"- **Memory Usage:** {mem_mb:.1f} MB\n"
    if metrics.get("request_rate") is not None:
        output += f"- **Request Rate:** {metrics['request_rate']:.2f} req/s\n"
    if metrics.get("error_rate") is not None:
        output += f"- **Error Rate:** {metrics['error_rate']:.2%}\n"
    if metrics.get("latency_p99") is not None:
        output += f"- **P99 Latency:** {metrics['latency_p99']*1000:.1f} ms\n"

    if not any(metrics.values()):
        output += "*No metrics available. Ensure the service has standard Kubernetes/Prometheus labels.*"

    return _text_result(output)


async def _handle_get_alerts() -> CallToolResult:
    """Handle get_alerts tool."""
    prom = get_prometheus()

    alerts = await prom.get_alerts()

    if not alerts:
        return _text_result("✅ No alerts currently firing.")

    # Group by state
    firing = [a for a in alerts if a.state == "firing"]
    pending = [a for a in alerts if a.state == "pending"]

    output = "## 🚨 Prometheus Alerts\n\n"

    if firing:
        output += f"### Firing ({len(firing)})\n"
        for alert in firing:
            severity = alert.labels.get("severity", "unknown")
            severity_emoji = {"critical": "🔴", "warning": "🟡"}.get(severity, "⚪")
            summary = alert.annotations.get("summary", alert.annotations.get("description", ""))
            output += f"- {severity_emoji} **{alert.alert_name}** ({severity})\n"
            if summary:
                output += f"  - {summary}\n"

    if pending:
        output += f"\n### Pending ({len(pending)})\n"
        for alert in pending:
            output += f"- ⏳ **{alert.alert_name}**\n"

    return _text_result(output)


async def _handle_search_runbooks(arguments: dict) -> CallToolResult:
    """Handle search_runbooks tool."""
    manager = get_runbook_manager()
    query = arguments["query"]

    results = manager.search(query)

    if not results:
        return _text_result(f"No runbooks matching '{query}'")

    output = f"## 📚 Runbooks matching '{query}'\n\n"

    for rb in results[:5]:
        output += f"### {rb.title}\n"
        output += f"*Tags: {', '.join(rb.tags)}*\n\n"
        # Include first ~500 chars of content
        content_preview = rb.content[:500].strip()
        if len(rb.content) > 500:
            content_preview += "..."
        output += f"{content_preview}\n\n---\n"

    return _text_result(output)


async def _handle_list_runbooks() -> CallToolResult:
    """Handle list_runbooks tool."""
    manager = get_runbook_manager()

    runbooks = manager.list_all()

    if not runbooks:
        return _text_result("No runbooks available. Add runbooks to the `runbooks/` directory.")

    output = "## 📚 Available Runbooks\n\n"

    for rb in runbooks:
        tags_str = ", ".join(rb.tags[:5])
        if len(rb.tags) > 5:
            tags_str += "..."
        output += f"- **{rb.title}** ({rb.name})\n"
        if tags_str:
            output += f"  - Tags: {tags_str}\n"

    output += f"\n*Total: {len(runbooks)} runbooks*"

    return _text_result(output)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
