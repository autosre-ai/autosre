# MCP Server Integration

OpenSRE can be used as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server, allowing any MCP-compatible AI assistant to use OpenSRE's incident investigation capabilities.

## What is MCP?

MCP is an open standard for connecting AI assistants to external tools and data sources. It enables AI assistants like Claude, VS Code Copilot, and others to:

- Query your Kubernetes cluster
- Analyze Prometheus metrics
- Investigate incidents
- Search your runbooks

All through a standardized protocol that works across different AI clients.

## Quick Start

### 1. Ensure OpenSRE is installed

```bash
# From the opensre directory
pip install -e .

# Or install directly
pip install opensre
```

### 2. Configure your MCP client

#### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "opensre": {
      "command": "opensre",
      "args": ["mcp"],
      "env": {
        "OPENSRE_PROMETHEUS_URL": "http://localhost:9090",
        "OPENSRE_OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

#### VS Code with Continue/Copilot

Add to your `.continue/config.json` or MCP settings:

```json
{
  "mcpServers": {
    "opensre": {
      "command": "opensre",
      "args": ["mcp"]
    }
  }
}
```

#### Running Directly

You can also run the MCP server directly for testing:

```bash
# Via CLI
opensre mcp

# Via Python module
python -m opensre_core.mcp_server
```

## Available Tools

### investigate

**AI-powered incident investigation.** Analyzes your infrastructure, correlates data from multiple sources, and provides root cause analysis with remediation suggestions.

```
Tool: investigate
Arguments:
  - issue: "high memory usage in payment service"
  - namespace: "production" (optional, default: "default")

Returns:
  - Root cause analysis with confidence score
  - Key observations from K8s and Prometheus
  - Contributing factors
  - Recommended actions with risk levels
```

### status

**Check OpenSRE connection health.** Verifies connectivity to Prometheus, Kubernetes, and the LLM backend.

```
Tool: status
Arguments: none

Returns:
  - Prometheus connection status
  - Kubernetes connection status  
  - LLM connection status
```

### get_pods

**List pods in a namespace.** Shows pod status, ready state, restart counts, and container states.

```
Tool: get_pods
Arguments:
  - namespace: "default" (optional)

Returns:
  - List of pods with status, restarts, and age
  - Container states for unhealthy pods
```

### get_events

**Get recent Kubernetes warning events.** Useful for spotting issues like OOMKilled, ImagePullBackOff, etc.

```
Tool: get_events
Arguments:
  - namespace: "default" (optional)
  - minutes: 15 (optional, how far back to look)

Returns:
  - Warning events with reason, message, and affected objects
```

### get_pod_logs

**Retrieve logs from a pod.** Supports container selection and tail lines.

```
Tool: get_pod_logs
Arguments:
  - name: "my-pod" (required)
  - namespace: "default" (optional)
  - container: "app" (optional)
  - tail_lines: 100 (optional)

Returns:
  - Log output from the specified pod/container
```

### describe_pod

**Get detailed pod information.** Like `kubectl describe pod` but formatted for AI consumption.

```
Tool: describe_pod
Arguments:
  - name: "my-pod" (required)
  - namespace: "default" (optional)

Returns:
  - Full pod details including containers, events, resources
```

### query_prometheus

**Execute PromQL queries.** Run any Prometheus query and get formatted results.

```
Tool: query_prometheus
Arguments:
  - query: "sum(rate(http_requests_total[5m]))" (required)

Returns:
  - Query results with metric names, labels, and values
```

### get_service_metrics

**Get standard service metrics.** CPU, memory, request rate, error rate, and latency for a service.

```
Tool: get_service_metrics
Arguments:
  - service: "payment-service" (required)
  - namespace: "default" (optional)

Returns:
  - CPU usage percentage
  - Memory usage in MB
  - Request rate (req/s)
  - Error rate percentage
  - P99 latency in ms
```

### get_alerts

**Get firing Prometheus alerts.** Shows all currently active alerts with severity and annotations.

```
Tool: get_alerts
Arguments: none

Returns:
  - Firing alerts with severity and summary
  - Pending alerts
```

### search_runbooks

**Search your runbooks.** Find relevant troubleshooting guides for an issue.

```
Tool: search_runbooks
Arguments:
  - query: "OOMKilled" (required)

Returns:
  - Matching runbooks with titles, tags, and content preview
```

### list_runbooks

**List all available runbooks.**

```
Tool: list_runbooks
Arguments: none

Returns:
  - All runbooks with titles and tags
```

### list_namespaces

**List Kubernetes namespaces.**

```
Tool: list_namespaces
Arguments: none

Returns:
  - All namespaces in the cluster
```

## Configuration

The MCP server uses the same configuration as the OpenSRE CLI. Set these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL | `http://localhost:9090` |
| `OPENSRE_OLLAMA_HOST` | Ollama LLM server URL | `http://localhost:11434` |
| `OPENSRE_OLLAMA_MODEL` | Model to use | `llama3.2` |
| `KUBECONFIG` | Path to kubeconfig | `~/.kube/config` |
| `OPENSRE_LOG_LEVEL` | Log level | `INFO` |

Or use a `.env` file in your working directory.

## Example Usage

Once configured, you can ask your AI assistant questions like:

> "Investigate why the payment-service pods are crashlooping in the production namespace"

> "Show me all warning events in the staging namespace"

> "What's the current CPU and memory usage for the api-gateway service?"

> "Are there any firing alerts right now?"

> "Search the runbooks for OOMKilled issues"

The AI will use the OpenSRE MCP tools to gather data from your infrastructure and provide intelligent analysis.

## Security Considerations

- The MCP server has read access to your Kubernetes cluster and Prometheus
- No destructive operations are exposed (actions require approval via CLI)
- The server runs locally and communicates via stdio
- Ensure your AI client is from a trusted source

## Troubleshooting

### Server not starting

1. Check that OpenSRE is installed: `opensre --version`
2. Verify your Python environment has the `mcp` package
3. Check logs for connection errors to Prometheus/K8s

### Tools not appearing

1. Restart your MCP client (Claude Desktop, VS Code)
2. Check the MCP client logs for errors
3. Try running `opensre mcp` directly to see startup messages

### Connection errors

1. Verify Prometheus is accessible: `curl http://localhost:9090/-/healthy`
2. Verify K8s access: `kubectl get pods`
3. Check environment variables are set correctly

## Architecture

```
┌─────────────────┐     stdio      ┌─────────────────┐
│   AI Assistant  │ ◄────────────► │  OpenSRE MCP    │
│ (Claude/VSCode) │                │     Server      │
└─────────────────┘                └────────┬────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
            │   Kubernetes  │       │  Prometheus   │       │    Ollama     │
            │    Cluster    │       │    Server     │       │     LLM       │
            └───────────────┘       └───────────────┘       └───────────────┘
```

## Development

To modify or extend the MCP server:

```python
# opensre_core/mcp_server.py

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Add your custom tools here."""
    return [
        Tool(
            name="my_custom_tool",
            description="What it does",
            inputSchema={
                "type": "object",
                "properties": {
                    "arg1": {"type": "string", "description": "..."}
                },
                "required": ["arg1"],
            },
        ),
        # ... existing tools
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle your custom tool."""
    if name == "my_custom_tool":
        # Your implementation
        return _text_result("Result")
```

For more information on MCP development, see the [MCP Documentation](https://modelcontextprotocol.io/docs).
