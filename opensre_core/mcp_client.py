"""OpenSRE MCP Client - Connect to external MCP tool servers.

This module allows OpenSRE to consume tools from any MCP-compatible server,
enabling integration with:
- kubernetes-mcp (kubectl operations)
- prometheus-mcp (PromQL queries)
- github-mcp (issue/PR management)
- slack-mcp (notifications)
- Any custom MCP server

Usage:
    from opensre_core.mcp_client import MCPClientManager

    manager = MCPClientManager()
    await manager.connect("kubernetes", command=["npx", "kubernetes-mcp"])

    # List available tools
    tools = await manager.list_tools("kubernetes")

    # Call a tool
    result = await manager.call_tool("kubernetes", "get_pods", {"namespace": "default"})
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    command: list[str]
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True


@dataclass
class MCPTool:
    """Representation of an MCP tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    server: str


@dataclass
class MCPConnection:
    """Active connection to an MCP server."""
    config: MCPServerConfig
    session: ClientSession
    tools: list[MCPTool] = field(default_factory=list)
    connected: bool = False


class MCPClientManager:
    """Manages connections to multiple MCP servers.

    Example:
        manager = MCPClientManager()

        # Load servers from config file
        await manager.load_config("mcp-clients.json")

        # Or add servers programmatically
        await manager.connect("k8s", command=["npx", "kubernetes-mcp"])

        # List all available tools across all servers
        all_tools = await manager.list_all_tools()

        # Call a specific tool
        result = await manager.call_tool("k8s", "get_pods", {"namespace": "default"})
    """

    def __init__(self, config_path: Optional[str] = None):
        self.connections: dict[str, MCPConnection] = {}
        self.config_path = config_path
        self._lock = asyncio.Lock()

    async def load_config(self, config_path: str) -> list[str]:
        """Load MCP server configurations from a JSON file.

        Config format:
        {
            "mcpServers": {
                "kubernetes": {
                    "command": "npx",
                    "args": ["kubernetes-mcp"],
                    "env": {"KUBECONFIG": "/path/to/kubeconfig"}
                },
                "prometheus": {
                    "command": "prometheus-mcp",
                    "args": ["--url", "http://localhost:9090"]
                }
            }
        }

        Returns:
            List of connected server names.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"MCP config not found: {config_path}")

        with open(path) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        connected = []

        for name, server_config in servers.items():
            try:
                command = server_config.get("command", "")
                args = server_config.get("args", [])
                env = server_config.get("env", {})

                # Build full command
                if isinstance(command, str):
                    full_command = [command] + args
                else:
                    full_command = command + args

                await self.connect(
                    name=name,
                    command=full_command,
                    env=env,
                    description=server_config.get("description", ""),
                )
                connected.append(name)

            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{name}': {e}")

        return connected

    async def connect(
        self,
        name: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        description: str = "",
    ) -> MCPConnection:
        """Connect to an MCP server.

        Args:
            name: Unique identifier for this server connection.
            command: Command to start the MCP server (e.g., ["npx", "kubernetes-mcp"]).
            env: Environment variables for the server process.
            description: Human-readable description.

        Returns:
            MCPConnection object with session and available tools.
        """
        async with self._lock:
            if name in self.connections:
                existing = self.connections[name]
                if existing.connected:
                    logger.info(f"Already connected to '{name}'")
                    return existing

        config = MCPServerConfig(
            name=name,
            command=command[:1],
            args=command[1:] if len(command) > 1 else [],
            env=env or {},
            description=description,
        )

        server_params = StdioServerParameters(
            command=command[0],
            args=command[1:] if len(command) > 1 else [],
            env=env,
        )

        logger.info(f"Connecting to MCP server '{name}': {' '.join(command)}")

        # Create stdio client connection
        read, write = await stdio_client(server_params).__aenter__()
        session = ClientSession(read, write)
        await session.initialize()

        # Fetch available tools
        tools_response = await session.list_tools()
        tools = [
            MCPTool(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
                server=name,
            )
            for tool in tools_response.tools
        ]

        connection = MCPConnection(
            config=config,
            session=session,
            tools=tools,
            connected=True,
        )

        async with self._lock:
            self.connections[name] = connection

        logger.info(f"Connected to '{name}' with {len(tools)} tools: {[t.name for t in tools]}")
        return connection

    async def disconnect(self, name: str) -> bool:
        """Disconnect from an MCP server.

        Args:
            name: Server name to disconnect.

        Returns:
            True if disconnected, False if not found.
        """
        async with self._lock:
            if name not in self.connections:
                return False

            connection = self.connections[name]
            if connection.session:
                try:
                    await connection.session.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing session for '{name}': {e}")

            connection.connected = False
            del self.connections[name]

        logger.info(f"Disconnected from '{name}'")
        return True

    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        names = list(self.connections.keys())
        for name in names:
            await self.disconnect(name)

    def list_servers(self) -> list[dict[str, Any]]:
        """List all connected MCP servers.

        Returns:
            List of server info dicts.
        """
        return [
            {
                "name": name,
                "connected": conn.connected,
                "tools": len(conn.tools),
                "description": conn.config.description,
            }
            for name, conn in self.connections.items()
        ]

    async def list_tools(self, server_name: str) -> list[MCPTool]:
        """List tools available from a specific server.

        Args:
            server_name: Name of the server.

        Returns:
            List of MCPTool objects.
        """
        if server_name not in self.connections:
            raise ValueError(f"Server '{server_name}' not connected")

        return self.connections[server_name].tools

    async def list_all_tools(self) -> list[MCPTool]:
        """List all tools from all connected servers.

        Returns:
            List of MCPTool objects with server info.
        """
        all_tools = []
        for connection in self.connections.values():
            all_tools.extend(connection.tools)
        return all_tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Call a tool on an MCP server.

        Args:
            server_name: Name of the server.
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            Tool result (typically text content).
        """
        if server_name not in self.connections:
            raise ValueError(f"Server '{server_name}' not connected")

        connection = self.connections[server_name]
        if not connection.connected:
            raise RuntimeError(f"Server '{server_name}' is disconnected")

        logger.debug(f"Calling {server_name}.{tool_name} with {arguments}")

        result = await connection.session.call_tool(tool_name, arguments)

        # Extract text content from result
        if result.content:
            texts = []
            for content in result.content:
                if hasattr(content, 'text'):
                    texts.append(content.text)
            return "\n".join(texts) if texts else result

        return result

    async def call_tool_auto(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Call a tool, automatically finding which server has it.

        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool result.

        Raises:
            ValueError: If tool not found on any server.
        """
        for name, connection in self.connections.items():
            tool_names = [t.name for t in connection.tools]
            if tool_name in tool_names:
                return await self.call_tool(name, tool_name, arguments)

        raise ValueError(f"Tool '{tool_name}' not found on any connected server")

    def get_tool_schema(self, server_name: str, tool_name: str) -> Optional[dict]:
        """Get the input schema for a tool.

        Args:
            server_name: Server name.
            tool_name: Tool name.

        Returns:
            JSON Schema dict or None.
        """
        if server_name not in self.connections:
            return None

        for tool in self.connections[server_name].tools:
            if tool.name == tool_name:
                return tool.input_schema

        return None


class MCPToolAdapter:
    """Adapter that wraps MCP tools for use in OpenSRE agents.

    This bridges MCP tools with OpenSRE's internal tool interface,
    allowing agents to seamlessly use MCP tools alongside native tools.

    Example:
        manager = MCPClientManager()
        await manager.connect("k8s", ["npx", "kubernetes-mcp"])

        adapter = MCPToolAdapter(manager)

        # Use in agent context
        result = await adapter.execute("k8s.get_pods", {"namespace": "default"})
    """

    def __init__(self, manager: MCPClientManager):
        self.manager = manager

    async def execute(self, tool_path: str, arguments: dict[str, Any]) -> str:
        """Execute an MCP tool.

        Args:
            tool_path: Tool path in format "server.tool_name" or just "tool_name".
            arguments: Tool arguments.

        Returns:
            Tool result as string.
        """
        if "." in tool_path:
            server_name, tool_name = tool_path.split(".", 1)
            result = await self.manager.call_tool(server_name, tool_name, arguments)
        else:
            result = await self.manager.call_tool_auto(tool_path, arguments)

        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2, default=str)

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get all available MCP tools formatted for agent use.

        Returns:
            List of tool definitions.
        """
        tools = []
        for connection in self.manager.connections.values():
            for tool in connection.tools:
                tools.append({
                    "name": f"{connection.config.name}.{tool.name}",
                    "description": tool.description,
                    "parameters": tool.input_schema,
                    "source": "mcp",
                    "server": connection.config.name,
                })
        return tools


# Convenience function for quick setup
async def create_mcp_manager(config_path: str = "mcp-clients.json") -> MCPClientManager:
    """Create and initialize an MCP client manager from config.

    Args:
        config_path: Path to MCP clients config file.

    Returns:
        Initialized MCPClientManager.
    """
    manager = MCPClientManager()

    if Path(config_path).exists():
        await manager.load_config(config_path)

    return manager


# Common MCP server presets
MCP_PRESETS = {
    "kubernetes": {
        "command": ["npx", "-y", "@anthropic/kubernetes-mcp"],
        "description": "Kubernetes cluster operations via kubectl",
    },
    "prometheus": {
        "command": ["npx", "-y", "prometheus-mcp"],
        "env": {"PROMETHEUS_URL": "http://localhost:9090"},
        "description": "Prometheus metrics and alerting",
    },
    "github": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
        "description": "GitHub API operations",
    },
    "filesystem": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/"],
        "description": "Filesystem operations",
    },
    "postgres": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-postgres"],
        "description": "PostgreSQL database operations",
    },
    "slack": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": ""},
        "description": "Slack messaging",
    },
    "grafana": {
        "command": ["npx", "-y", "grafana-mcp"],
        "env": {"GRAFANA_URL": "http://localhost:3000", "GRAFANA_API_KEY": ""},
        "description": "Grafana dashboards and alerts",
    },
}


async def connect_preset(
    manager: MCPClientManager,
    preset_name: str,
    env_overrides: Optional[dict[str, str]] = None,
) -> MCPConnection:
    """Connect to a preset MCP server.

    Args:
        manager: MCPClientManager instance.
        preset_name: Name of preset (kubernetes, github, etc.).
        env_overrides: Environment variable overrides.

    Returns:
        MCPConnection.
    """
    if preset_name not in MCP_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(MCP_PRESETS.keys())}")

    preset = MCP_PRESETS[preset_name]
    env = {**preset.get("env", {}), **(env_overrides or {})}

    return await manager.connect(
        name=preset_name,
        command=preset["command"],
        env=env if env else None,
        description=preset.get("description", ""),
    )
