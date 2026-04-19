# OpenSRE MCP Integration Guide

OpenSRE supports the Model Context Protocol (MCP) for seamless integration with AI assistants like Claude Desktop, VS Code with Continue, and other MCP-compatible clients.

## OpenSRE as MCP Server

OpenSRE exposes its investigation and Kubernetes capabilities as an MCP server, allowing any MCP client to use OpenSRE tools.

### Installation

```bash
# Install with MCP support
pip install opensre[mcp]

# Or install all dependencies
pip install opensre[all]
```

### Running the MCP Server

```bash
# Run via CLI
opensre mcp

# Or run directly
python -m opensre_core.mcp_server
```

### Claude Desktop Configuration

Add OpenSRE to your Claude Desktop configuration (`~/.config/claude/claude_desktop_config.json` on Linux/macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "opensre": {
      "command": "opensre",
      "args": ["mcp"],
      "env": {
        "OPENSRE_PROMETHEUS_URL": "http://localhost:9090",
        "OPENSRE_LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### VS Code / Continue Configuration

Add to your Continue config:

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

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `investigate` | AI-powered incident investigation with root cause analysis |
| `status` | Check OpenSRE health (Prometheus, Kubernetes, LLM) |
| `list_namespaces` | List Kubernetes namespaces |
| `get_pods` | Get pods with status and restart counts |
| `get_events` | Get recent warning events |
| `get_pod_logs` | Retrieve pod logs |
| `describe_pod` | Get detailed pod information |
| `query_prometheus` | Execute PromQL queries |
| `get_service_metrics` | Get CPU, memory, request rate, latency |
| `get_alerts` | Get firing Prometheus alerts |
| `search_runbooks` | Search runbooks by symptom |
| `list_runbooks` | List all available runbooks |

### Example Usage (from Claude)

```
"Investigate high memory usage in the payment-service namespace"
"Get the logs from pod payment-api-abc123 in production"
"What alerts are currently firing?"
"Search runbooks for OOMKilled errors"
```

## OpenSRE as MCP Client

OpenSRE can also act as an MCP client, connecting to other MCP servers to extend its capabilities.

### Configuration

Create `mcp-clients.json` in your OpenSRE config directory:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "@anthropic/kubernetes-mcp"],
      "description": "Extended Kubernetes operations"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
      },
      "description": "GitHub for incident tracking"
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-..."
      },
      "description": "Slack notifications"
    }
  }
}
```

### Programmatic Usage

```python
from opensre_core.mcp_client import MCPClientManager, connect_preset

# Create manager and connect
manager = MCPClientManager()

# Connect to servers from config
await manager.load_config("mcp-clients.json")

# Or connect to presets
await connect_preset(manager, "kubernetes")
await connect_preset(manager, "github", {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."})

# List available tools
tools = await manager.list_all_tools()
for tool in tools:
    print(f"{tool.server}.{tool.name}: {tool.description}")

# Call a tool
result = await manager.call_tool("kubernetes", "get_pods", {"namespace": "default"})
print(result)

# Auto-find which server has a tool
result = await manager.call_tool_auto("create_issue", {
    "repo": "myorg/myrepo",
    "title": "Incident: High latency",
    "body": "Investigation in progress..."
})
```

### Available Presets

| Preset | Description |
|--------|-------------|
| `kubernetes` | Kubernetes cluster operations via kubectl |
| `prometheus` | Prometheus metrics and alerting |
| `github` | GitHub API operations |
| `filesystem` | Filesystem operations |
| `postgres` | PostgreSQL database operations |
| `slack` | Slack messaging |
| `grafana` | Grafana dashboards and alerts |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL | `http://localhost:9090` |
| `OPENSRE_LLM_PROVIDER` | LLM provider (ollama, anthropic, openai) | `ollama` |
| `OPENSRE_OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `SLACK_BOT_TOKEN` | Slack bot token | - |
| `KUBECONFIG` | Kubernetes config path | `~/.kube/config` |

## Docker Usage

Run OpenSRE MCP server in Docker:

```bash
docker run -it --rm \
  -v ~/.kube/config:/app/.kube/config:ro \
  -e OPENSRE_PROMETHEUS_URL=http://host.docker.internal:9090 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  ghcr.io/srisainath/opensre:latest \
  opensre mcp
```

For Claude Desktop with Docker:

```json
{
  "mcpServers": {
    "opensre": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "~/.kube/config:/app/.kube/config:ro",
        "-e", "ANTHROPIC_API_KEY",
        "ghcr.io/srisainath/opensre:latest",
        "opensre", "mcp"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```
