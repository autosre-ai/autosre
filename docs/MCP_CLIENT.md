# MCP Client Integration

OpenSRE can connect to external MCP (Model Context Protocol) servers to extend its capabilities. This allows you to:

- Use specialized MCP tools for Kubernetes, Prometheus, GitHub, etc.
- Connect to custom MCP servers
- Standardize tool interfaces across different backends

## Quick Start

### 1. Enable MCP Client Mode

```bash
# Set environment variable
export OPENSRE_MCP_ENABLED=true

# Or in .env file
OPENSRE_MCP_ENABLED=true
OPENSRE_MCP_CONFIG_PATH=./mcp-clients.json
```

### 2. Configure MCP Servers

Create `mcp-clients.json`:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "@anthropic/kubernetes-mcp"],
      "description": "Kubernetes cluster operations"
    },
    "prometheus": {
      "command": "npx",
      "args": ["-y", "prometheus-mcp", "--url", "http://localhost:9090"],
      "description": "Prometheus metrics queries"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub operations"
    }
  }
}
```

### 3. Use MCP Tools

```bash
# List available presets
opensre mcp-client list

# Connect to a server
opensre mcp-client connect kubernetes

# List all available tools
opensre mcp-client tools

# Call a specific tool
opensre mcp-client call kubernetes get_pods --args '{"namespace": "default"}'
```

## Available Presets

| Preset | Package | Description |
|--------|---------|-------------|
| `kubernetes` | `@anthropic/kubernetes-mcp` | kubectl operations |
| `github` | `@modelcontextprotocol/server-github` | GitHub API |
| `filesystem` | `@modelcontextprotocol/server-filesystem` | File operations |
| `postgres` | `@modelcontextprotocol/server-postgres` | PostgreSQL |
| `slack` | `@modelcontextprotocol/server-slack` | Slack messaging |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       OpenSRE                                 │
│                                                               │
│  ┌─────────────┐      ┌─────────────────────┐                │
│  │   Observer  │ ─────│   HybridAdapter     │                │
│  │   Agent     │      │                     │                │
│  └─────────────┘      │  ┌───────────────┐  │                │
│                       │  │ MCP Adapters  │──┼──► MCP Servers │
│  ┌─────────────┐      │  └───────────────┘  │                │
│  │   Reasoner  │      │         OR          │                │
│  │   Agent     │      │  ┌───────────────┐  │                │
│  └─────────────┘      │  │Native Adapters│──┼──► Direct APIs │
│                       │  └───────────────┘  │                │
│  ┌─────────────┐      └─────────────────────┘                │
│  │    Actor    │                                              │
│  │   Agent     │                                              │
│  └─────────────┘                                              │
└──────────────────────────────────────────────────────────────┘
```

## Python API

### Basic Usage

```python
from opensre_core.mcp_client import MCPClientManager, connect_preset

# Create manager
manager = MCPClientManager()

# Connect to preset
await connect_preset(manager, "kubernetes")

# List tools
tools = await manager.list_tools("kubernetes")
for tool in tools:
    print(f"{tool.name}: {tool.description}")

# Call a tool
result = await manager.call_tool(
    "kubernetes",
    "get_pods",
    {"namespace": "production"}
)
print(result)

# Disconnect
await manager.disconnect_all()
```

### Using Hybrid Adapter

```python
from opensre_core.mcp_client import MCPClientManager
from opensre_core.adapters.mcp_adapters import HybridAdapter

manager = MCPClientManager()
await manager.load_config("mcp-clients.json")

adapter = HybridAdapter(manager)

# Automatically uses MCP if connected, else native
pods = await adapter.kubernetes.get_pods("default")
alerts = await adapter.prometheus.get_alerts()

# Check which backend is being used
if adapter.using_mcp("kubernetes"):
    print("Using kubernetes-mcp")
else:
    print("Using native kubernetes client")
```

### Loading from Config

```python
manager = MCPClientManager()
connected = await manager.load_config("mcp-clients.json")
print(f"Connected to: {connected}")

# Auto-discover all tools
all_tools = await manager.list_all_tools()
```

## Custom MCP Servers

You can connect to any MCP-compatible server:

```python
await manager.connect(
    name="my-server",
    command=["python", "-m", "my_mcp_server"],
    env={"API_KEY": "secret"},
    description="My custom MCP server"
)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSRE_MCP_ENABLED` | Enable MCP client mode | `false` |
| `OPENSRE_MCP_CONFIG_PATH` | Path to mcp-clients.json | `./mcp-clients.json` |
| `OPENSRE_MCP_KUBERNETES` | Use kubernetes-mcp when available | `true` |
| `OPENSRE_MCP_PROMETHEUS` | Use prometheus-mcp when available | `true` |

## Comparison: MCP vs Native

| Feature | MCP Mode | Native Mode |
|---------|----------|-------------|
| Setup | Requires MCP servers | Direct API access |
| Consistency | Standardized interface | Adapter-specific |
| Flexibility | Easy to swap backends | Hardcoded adapters |
| Overhead | Process spawning | Direct calls |
| Best for | Multi-tool workflows | Simple deployments |

## Troubleshooting

### Server won't connect

```bash
# Test MCP server directly
npx -y @anthropic/kubernetes-mcp

# Check if npx is available
which npx

# Try manual connection
opensre mcp-client connect kubernetes
```

### Tool not found

```bash
# List available tools
opensre mcp-client tools

# Check specific server
opensre mcp-client call kubernetes list_tools --args '{}'
```

### Performance issues

MCP servers are spawned as child processes. For high-throughput scenarios, consider:

1. Keeping servers connected (don't reconnect per-request)
2. Using native adapters for hot paths
3. Batching tool calls when possible

## See Also

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Server List](https://github.com/modelcontextprotocol/servers)
- [OpenSRE Architecture](ARCHITECTURE.md)
