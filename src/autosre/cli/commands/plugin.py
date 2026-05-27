"""
AutoSRE Plugin Commands

Manage plugins for extending AutoSRE functionality.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="plugin",
    help="Manage AutoSRE plugins",
    no_args_is_help=True,
)

console = Console()

# Plugin directories
PLUGINS_DIR = Path("~/.autosre/plugins").expanduser()
CONFIG_DIR = Path("~/.autosre").expanduser()
PLUGIN_CONFIG_FILE = CONFIG_DIR / "plugins.yaml"


def _ensure_plugin_dirs():
    """Ensure plugin directories exist."""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_plugin_config() -> dict:
    """Load plugin configuration."""
    if PLUGIN_CONFIG_FILE.exists():
        import yaml
        with open(PLUGIN_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {"enabled": {}, "disabled": []}


def _save_plugin_config(config: dict):
    """Save plugin configuration."""
    _ensure_plugin_dirs()
    import yaml
    with open(PLUGIN_CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def _run_async(coro):
    """Run async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _get_loader():
    """Get plugin loader instance."""
    from autosre.plugins import PluginLoader, LoaderConfig
    config = LoaderConfig(
        plugin_dirs=[str(PLUGINS_DIR)],
        auto_discover=True,
        auto_load=False,  # We'll control loading manually
    )
    return PluginLoader(config=config)


async def _discover_all_plugins():
    """Discover all plugins from all sources."""
    loader = _get_loader()
    discovered = await loader.discover(force=True)
    return discovered


@app.command("list")
def list_plugins(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    all_sources: bool = typer.Option(False, "--all", "-a", help="Show plugins from all sources"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show additional details"),
):
    """
    Show installed plugins.
    
    Lists all plugins discovered in ~/.autosre/plugins/ and via entry points.
    
    Examples:
        autosre plugin list              # List all plugins
        autosre plugin list --json       # JSON output
        autosre plugin list --all -v     # Verbose with all sources
    """
    _ensure_plugin_dirs()
    
    # Discover plugins
    try:
        discovered = _run_async(_discover_all_plugins())
    except Exception as e:
        console.print(f"[red]Error discovering plugins: {e}[/]")
        discovered = []
    
    # Load config to check enabled/disabled status
    plugin_config = _load_plugin_config()
    disabled_plugins = plugin_config.get("disabled", [])
    
    if json_output:
        output = []
        for dp in discovered:
            plugin_info = {
                "id": dp.plugin_id or dp.class_name,
                "name": dp.plugin_name or dp.class_name,
                "version": dp.plugin_version or "unknown",
                "type": dp.plugin_type.value if dp.plugin_type else "unknown",
                "source": dp.source.value,
                "path": dp.path,
                "validated": dp.validated,
                "enabled": (dp.plugin_id or dp.class_name) not in disabled_plugins,
            }
            if dp.validation_error:
                plugin_info["error"] = dp.validation_error
            output.append(plugin_info)
        console.print(json.dumps(output, indent=2))
        return
    
    if not discovered:
        console.print()
        console.print("[yellow]No plugins found.[/]")
        console.print()
        console.print("[dim]Plugin locations:[/]")
        console.print(f"  • {PLUGINS_DIR}")
        console.print()
        console.print("[dim]To install a plugin:[/]")
        console.print("  autosre plugin install <source>")
        console.print()
        return
    
    console.print()
    
    # Group by source
    by_source = {}
    for dp in discovered:
        source = dp.source.value
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(dp)
    
    # Create table
    table = Table(
        title="[bold cyan]Installed Plugins[/]",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Plugin", style="cyan")
    table.add_column("Version")
    table.add_column("Type")
    table.add_column("Status")
    if verbose:
        table.add_column("Source")
        table.add_column("Path")
    
    for source, plugins in sorted(by_source.items()):
        for dp in sorted(plugins, key=lambda x: x.plugin_name or x.class_name or ""):
            plugin_id = dp.plugin_id or dp.class_name
            name = dp.plugin_name or dp.class_name
            version = dp.plugin_version or "[dim]unknown[/]"
            ptype = dp.plugin_type.value if dp.plugin_type else "[dim]unknown[/]"
            
            # Determine status
            if dp.validation_error:
                status = "[red]✗ error[/]"
            elif plugin_id in disabled_plugins:
                status = "[yellow]○ disabled[/]"
            elif dp.validated:
                status = "[green]● enabled[/]"
            else:
                status = "[dim]? unknown[/]"
            
            row = [name, version, ptype, status]
            if verbose:
                row.append(source)
                path_short = dp.path if len(dp.path) < 40 else f"...{dp.path[-37:]}"
                row.append(f"[dim]{path_short}[/]")
            
            table.add_row(*row)
    
    console.print(table)
    console.print()
    console.print(f"[dim]Plugin directory: {PLUGINS_DIR}[/]")
    console.print()


@app.command("info")
def plugin_info(
    name: str = typer.Argument(..., help="Plugin name or ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show detailed plugin information.
    
    Displays metadata, capabilities, and configuration for a specific plugin.
    
    Examples:
        autosre plugin info my-plugin
        autosre plugin info my-plugin --json
    """
    # Discover plugins
    try:
        discovered = _run_async(_discover_all_plugins())
    except Exception as e:
        console.print(f"[red]Error discovering plugins: {e}[/]")
        raise typer.Exit(1)
    
    # Find the plugin
    plugin = None
    for dp in discovered:
        if dp.plugin_id == name or dp.class_name == name or (dp.plugin_name and dp.plugin_name.lower() == name.lower()):
            plugin = dp
            break
    
    if not plugin:
        console.print(f"[red]Plugin not found: {name}[/]")
        console.print()
        console.print("[dim]Available plugins:[/]")
        for dp in discovered[:5]:
            console.print(f"  • {dp.plugin_id or dp.class_name}")
        if len(discovered) > 5:
            console.print(f"  [dim]... and {len(discovered) - 5} more[/]")
        raise typer.Exit(1)
    
    # Load config
    plugin_config = _load_plugin_config()
    disabled_plugins = plugin_config.get("disabled", [])
    plugin_id = plugin.plugin_id or plugin.class_name
    is_enabled = plugin_id not in disabled_plugins
    
    # Try to get full metadata if plugin class is available
    metadata_dict = {}
    if plugin.plugin_class:
        try:
            instance = plugin.plugin_class()
            metadata = instance.metadata
            metadata_dict = metadata.to_dict()
        except Exception:
            pass
    
    if json_output:
        output = {
            "id": plugin.plugin_id or plugin.class_name,
            "name": plugin.plugin_name or plugin.class_name,
            "version": plugin.plugin_version or "unknown",
            "type": plugin.plugin_type.value if plugin.plugin_type else "unknown",
            "source": plugin.source.value,
            "path": plugin.path,
            "module": plugin.module_name,
            "class": plugin.class_name,
            "validated": plugin.validated,
            "enabled": is_enabled,
            "discovered_at": plugin.discovered_at.isoformat(),
        }
        if metadata_dict:
            output["metadata"] = metadata_dict
        if plugin.validation_error:
            output["error"] = plugin.validation_error
        console.print(json.dumps(output, indent=2))
        return
    
    console.print()
    
    # Build info panel
    status = "[green]● Enabled[/]" if is_enabled else "[yellow]○ Disabled[/]"
    if plugin.validation_error:
        status = f"[red]✗ Error[/]"
    
    info_lines = [
        f"[bold]Name:[/] {plugin.plugin_name or plugin.class_name}",
        f"[bold]ID:[/] {plugin.plugin_id or plugin.class_name}",
        f"[bold]Version:[/] {plugin.plugin_version or 'unknown'}",
        f"[bold]Type:[/] {plugin.plugin_type.value if plugin.plugin_type else 'unknown'}",
        f"[bold]Status:[/] {status}",
        "",
        f"[bold]Source:[/] {plugin.source.value}",
        f"[bold]Path:[/] {plugin.path}",
        f"[bold]Module:[/] {plugin.module_name}",
        f"[bold]Class:[/] {plugin.class_name}",
    ]
    
    if metadata_dict:
        info_lines.append("")
        if metadata_dict.get("description"):
            info_lines.append(f"[bold]Description:[/] {metadata_dict['description']}")
        if metadata_dict.get("author"):
            info_lines.append(f"[bold]Author:[/] {metadata_dict['author']}")
        if metadata_dict.get("license"):
            info_lines.append(f"[bold]License:[/] {metadata_dict['license']}")
        if metadata_dict.get("homepage"):
            info_lines.append(f"[bold]Homepage:[/] {metadata_dict['homepage']}")
        
        if metadata_dict.get("capabilities"):
            info_lines.append("")
            info_lines.append(f"[bold]Capabilities:[/]")
            for cap in metadata_dict["capabilities"]:
                info_lines.append(f"  • {cap}")
        
        if metadata_dict.get("dependencies"):
            info_lines.append("")
            info_lines.append(f"[bold]Dependencies:[/]")
            for dep in metadata_dict["dependencies"]:
                info_lines.append(f"  • {dep}")
        
        if metadata_dict.get("required_permissions"):
            info_lines.append("")
            info_lines.append(f"[bold]Required Permissions:[/]")
            for perm in metadata_dict["required_permissions"]:
                info_lines.append(f"  • {perm}")
    
    if plugin.validation_error:
        info_lines.append("")
        info_lines.append(f"[bold red]Error:[/] {plugin.validation_error}")
    
    console.print(Panel(
        "\n".join(info_lines),
        title=f"[bold cyan]Plugin: {plugin.plugin_name or plugin.class_name}[/]",
        border_style="cyan",
    ))
    console.print()


@app.command("enable")
def enable_plugin(
    name: str = typer.Argument(..., help="Plugin name or ID to enable"),
):
    """
    Enable a plugin.
    
    Removes the plugin from the disabled list, allowing it to be loaded.
    
    Examples:
        autosre plugin enable my-plugin
    """
    # Discover plugins to validate the name
    try:
        discovered = _run_async(_discover_all_plugins())
    except Exception as e:
        console.print(f"[red]Error discovering plugins: {e}[/]")
        raise typer.Exit(1)
    
    # Find the plugin
    plugin = None
    for dp in discovered:
        if dp.plugin_id == name or dp.class_name == name or (dp.plugin_name and dp.plugin_name.lower() == name.lower()):
            plugin = dp
            break
    
    if not plugin:
        console.print(f"[red]Plugin not found: {name}[/]")
        raise typer.Exit(1)
    
    plugin_id = plugin.plugin_id or plugin.class_name
    plugin_name = plugin.plugin_name or plugin.class_name
    
    # Update config
    config = _load_plugin_config()
    disabled = config.get("disabled", [])
    
    if plugin_id not in disabled:
        console.print(f"[yellow]Plugin '{plugin_name}' is already enabled[/]")
        return
    
    disabled.remove(plugin_id)
    config["disabled"] = disabled
    _save_plugin_config(config)
    
    console.print()
    console.print(f"[green]✓[/] Plugin '[bold]{plugin_name}[/]' enabled")
    console.print()


@app.command("disable")
def disable_plugin(
    name: str = typer.Argument(..., help="Plugin name or ID to disable"),
):
    """
    Disable a plugin.
    
    Adds the plugin to the disabled list, preventing it from being loaded.
    
    Examples:
        autosre plugin disable my-plugin
    """
    # Discover plugins to validate the name
    try:
        discovered = _run_async(_discover_all_plugins())
    except Exception as e:
        console.print(f"[red]Error discovering plugins: {e}[/]")
        raise typer.Exit(1)
    
    # Find the plugin
    plugin = None
    for dp in discovered:
        if dp.plugin_id == name or dp.class_name == name or (dp.plugin_name and dp.plugin_name.lower() == name.lower()):
            plugin = dp
            break
    
    if not plugin:
        console.print(f"[red]Plugin not found: {name}[/]")
        raise typer.Exit(1)
    
    plugin_id = plugin.plugin_id or plugin.class_name
    plugin_name = plugin.plugin_name or plugin.class_name
    
    # Update config
    config = _load_plugin_config()
    disabled = config.get("disabled", [])
    
    if plugin_id in disabled:
        console.print(f"[yellow]Plugin '{plugin_name}' is already disabled[/]")
        return
    
    disabled.append(plugin_id)
    config["disabled"] = disabled
    _save_plugin_config(config)
    
    console.print()
    console.print(f"[yellow]○[/] Plugin '[bold]{plugin_name}[/]' disabled")
    console.print()


@app.command("install")
def install_plugin(
    source: str = typer.Argument(..., help="Plugin source (path, git URL, or package name)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override plugin directory name"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if already exists"),
):
    """
    Install a plugin from a source.
    
    Supports multiple source types:
    - Local path: /path/to/plugin or ./plugin
    - Git URL: https://github.com/user/plugin.git
    - PyPI package: pip:package-name
    
    Examples:
        autosre plugin install ./my-plugin
        autosre plugin install https://github.com/user/autosre-plugin.git
        autosre plugin install pip:autosre-prometheus-plugin
        autosre plugin install /path/to/plugin --name custom-name
    """
    _ensure_plugin_dirs()
    
    console.print()
    
    # Determine source type and install
    if source.startswith("pip:"):
        # PyPI package installation
        package_name = source[4:]
        console.print(f"[bold]Installing PyPI package:[/] {package_name}")
        
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓[/] Package '{package_name}' installed successfully")
            console.print()
            console.print("[dim]The plugin will be discovered via entry points.[/]")
            console.print("[dim]Run 'autosre plugin list' to verify.[/]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to install package: {e.stderr}[/]")
            raise typer.Exit(1)
    
    elif source.startswith("https://") or source.startswith("git@"):
        # Git repository
        repo_url = source
        
        # Determine plugin name
        if name:
            plugin_name = name
        else:
            # Extract from URL
            plugin_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
        
        target_dir = PLUGINS_DIR / plugin_name
        
        if target_dir.exists():
            if force:
                console.print(f"[yellow]Removing existing plugin directory...[/]")
                shutil.rmtree(target_dir)
            else:
                console.print(f"[red]Plugin directory already exists: {target_dir}[/]")
                console.print("[dim]Use --force to overwrite[/]")
                raise typer.Exit(1)
        
        console.print(f"[bold]Cloning repository:[/] {repo_url}")
        console.print(f"[dim]Target: {target_dir}[/]")
        
        try:
            subprocess.run(
                ["git", "clone", repo_url, str(target_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓[/] Repository cloned successfully")
            
            # Check if there's a requirements.txt
            req_file = target_dir / "requirements.txt"
            if req_file.exists():
                console.print("[dim]Installing dependencies...[/]")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    console.print("[green]✓[/] Dependencies installed")
                except subprocess.CalledProcessError:
                    console.print("[yellow]⚠ Failed to install some dependencies[/]")
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to clone repository: {e.stderr}[/]")
            raise typer.Exit(1)
        except FileNotFoundError:
            console.print("[red]✗ Git is not installed or not in PATH[/]")
            raise typer.Exit(1)
    
    elif os.path.exists(source):
        # Local path
        source_path = Path(source).resolve()
        
        if not source_path.exists():
            console.print(f"[red]Source path does not exist: {source}[/]")
            raise typer.Exit(1)
        
        # Determine plugin name
        if name:
            plugin_name = name
        else:
            plugin_name = source_path.name
        
        target_dir = PLUGINS_DIR / plugin_name
        
        if target_dir.exists():
            if force:
                console.print(f"[yellow]Removing existing plugin directory...[/]")
                shutil.rmtree(target_dir)
            else:
                console.print(f"[red]Plugin directory already exists: {target_dir}[/]")
                console.print("[dim]Use --force to overwrite[/]")
                raise typer.Exit(1)
        
        console.print(f"[bold]Copying plugin:[/] {source_path}")
        console.print(f"[dim]Target: {target_dir}[/]")
        
        if source_path.is_file():
            # Single file plugin
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_dir / source_path.name)
        else:
            # Directory plugin
            shutil.copytree(source_path, target_dir)
        
        console.print(f"[green]✓[/] Plugin copied successfully")
        
        # Check if there's a requirements.txt
        req_file = target_dir / "requirements.txt"
        if req_file.exists():
            console.print("[dim]Installing dependencies...[/]")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print("[green]✓[/] Dependencies installed")
            except subprocess.CalledProcessError:
                console.print("[yellow]⚠ Failed to install some dependencies[/]")
    
    else:
        console.print(f"[red]Unknown source format: {source}[/]")
        console.print()
        console.print("[dim]Supported formats:[/]")
        console.print("  • Local path: /path/to/plugin or ./plugin")
        console.print("  • Git URL: https://github.com/user/plugin.git")
        console.print("  • PyPI package: pip:package-name")
        raise typer.Exit(1)
    
    console.print()
    console.print("[dim]Run 'autosre plugin list' to see installed plugins.[/]")
    console.print()


@app.command("uninstall")
def uninstall_plugin(
    name: str = typer.Argument(..., help="Plugin name to uninstall"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Uninstall a plugin.
    
    Removes the plugin from the plugins directory.
    
    Examples:
        autosre plugin uninstall my-plugin
        autosre plugin uninstall my-plugin --yes
    """
    # Find the plugin directory
    plugin_dir = PLUGINS_DIR / name
    
    if not plugin_dir.exists():
        # Try to find by discovering plugins
        try:
            discovered = _run_async(_discover_all_plugins())
            for dp in discovered:
                if dp.plugin_id == name or dp.class_name == name or (dp.plugin_name and dp.plugin_name.lower() == name.lower()):
                    if dp.source.value == "directory":
                        plugin_dir = Path(dp.path).parent
                        if not str(plugin_dir).startswith(str(PLUGINS_DIR)):
                            # Plugin is not in the managed directory
                            if "entry_point" in dp.source.value.lower():
                                console.print(f"[yellow]Plugin '{name}' was installed via pip.[/]")
                                console.print("[dim]Use 'pip uninstall <package>' to remove it.[/]")
                            else:
                                console.print(f"[yellow]Plugin '{name}' is not in the managed plugins directory.[/]")
                                console.print(f"[dim]Location: {dp.path}[/]")
                            raise typer.Exit(1)
                        break
        except Exception:
            pass
    
    if not plugin_dir.exists():
        console.print(f"[red]Plugin not found: {name}[/]")
        console.print(f"[dim]Checked: {plugin_dir}[/]")
        raise typer.Exit(1)
    
    if not yes:
        console.print()
        console.print(f"[yellow]This will remove:[/] {plugin_dir}")
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[dim]Cancelled.[/]")
            raise typer.Exit(0)
    
    try:
        shutil.rmtree(plugin_dir)
        console.print()
        console.print(f"[green]✓[/] Plugin '{name}' uninstalled successfully")
        console.print()
    except Exception as e:
        console.print(f"[red]✗ Failed to uninstall: {e}[/]")
        raise typer.Exit(1)


@app.command("create")
def create_plugin(
    name: str = typer.Argument(..., help="Plugin name"),
    plugin_type: str = typer.Option("skill", "--type", "-t", help="Plugin type: skill, integration, hook, middleware"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory (default: current directory)"),
):
    """
    Create a new plugin from template.
    
    Generates a plugin scaffold with boilerplate code.
    
    Examples:
        autosre plugin create my-metrics-plugin
        autosre plugin create my-alerting --type integration
        autosre plugin create my-hook --type hook -o ./plugins
    """
    valid_types = ["skill", "integration", "hook", "middleware"]
    if plugin_type not in valid_types:
        console.print(f"[red]Invalid plugin type: {plugin_type}[/]")
        console.print(f"[dim]Valid types: {', '.join(valid_types)}[/]")
        raise typer.Exit(1)
    
    # Normalize name
    plugin_name = name.lower().replace(" ", "-").replace("_", "-")
    class_name = "".join(word.title() for word in plugin_name.split("-")) + "Plugin"
    
    # Determine output directory
    if output:
        output_dir = Path(output) / plugin_name
    else:
        output_dir = Path.cwd() / plugin_name
    
    if output_dir.exists():
        console.print(f"[red]Directory already exists: {output_dir}[/]")
        raise typer.Exit(1)
    
    # Create directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate plugin code based on type
    base_class = {
        "skill": "SkillPlugin",
        "integration": "IntegrationPlugin",
        "hook": "HookPlugin",
        "middleware": "MiddlewarePlugin",
    }[plugin_type]
    
    plugin_code = f'''"""
{plugin_name} - AutoSRE Plugin

A custom {plugin_type} plugin for AutoSRE.
"""

from typing import Any, Optional

from autosre.plugins import (
    {base_class},
    PluginConfig,
    PluginContext,
    PluginMetadata,
    PluginResult,
    PluginType,
    PluginCapability,
)


class {class_name}Config(PluginConfig):
    """Configuration for {class_name}."""
    
    # Add your configuration options here
    example_option: str = "default_value"


class {class_name}({base_class}[{class_name}Config]):
    """
    {plugin_name} - {plugin_type.title()} Plugin
    
    Description of what this plugin does.
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            id="{plugin_name}",
            name="{plugin_name.replace('-', ' ').title()}",
            version="0.1.0",
            description="Description of your plugin",
            author="Your Name",
            type=PluginType.{plugin_type.upper()},
            capabilities=[
                # Add relevant capabilities
                # PluginCapability.METRICS_QUERY,
            ],
            tags=["{plugin_type}", "custom"],
        )
    
    def _default_config(self) -> {class_name}Config:
        """Return default configuration."""
        return {class_name}Config()
    
    async def on_initialize(self) -> None:
        """Initialize the plugin."""
        # Setup code here
        pass
    
    async def on_shutdown(self) -> None:
        """Cleanup when plugin shuts down."""
        # Cleanup code here
        pass
'''
    
    # Add type-specific methods
    if plugin_type == "skill":
        plugin_code += '''
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
        if action == "example_action":
            # Implement your action logic here
            return PluginResult.ok({"message": "Action completed"})
        
        return PluginResult.fail(f"Unknown action: {action}")
    
    def get_actions(self) -> list[dict[str, Any]]:
        """Return list of available actions."""
        return [
            {
                "name": "example_action",
                "description": "An example action",
                "parameters": {
                    "param1": {"type": "string", "required": True},
                },
            },
        ]
'''
    elif plugin_type == "integration":
        plugin_code += '''
    async def connect(self) -> bool:
        """
        Establish connection to the external service.
        
        Returns:
            True if connection successful
        """
        # Implement connection logic
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from the external service."""
        # Implement disconnection logic
        pass
'''
    elif plugin_type == "hook":
        plugin_code += '''
    @property
    def hook_events(self) -> list[str]:
        """Return list of events this hook handles."""
        return [
            "incident.detected",
            "investigation.started",
            "investigation.completed",
        ]
    
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
            Optional result
        """
        if event == "incident.detected":
            # Handle incident detection
            pass
        
        return None
'''
    elif plugin_type == "middleware":
        plugin_code += '''
    @property
    def priority(self) -> int:
        """Return middleware priority (lower = higher priority)."""
        return 50
    
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
        # Modify request as needed
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
        # Modify response as needed
        return response
'''
    
    # Write plugin file
    plugin_file = output_dir / f"{plugin_name.replace('-', '_')}.py"
    plugin_file.write_text(plugin_code)
    
    # Create __init__.py
    init_code = f'''"""
{plugin_name} Plugin Package
"""

from .{plugin_name.replace('-', '_')} import {class_name}, {class_name}Config

__all__ = ["{class_name}", "{class_name}Config"]
'''
    (output_dir / "__init__.py").write_text(init_code)
    
    # Create requirements.txt
    (output_dir / "requirements.txt").write_text("# Add plugin dependencies here\n")
    
    # Create README.md
    readme = f'''# {plugin_name.replace('-', ' ').title()}

A custom AutoSRE {plugin_type} plugin.

## Installation

```bash
autosre plugin install ./{plugin_name}
```

## Configuration

Add configuration in your AutoSRE config file:

```yaml
plugins:
  {plugin_name}:
    example_option: "value"
```

## Usage

Once installed, the plugin will be automatically discovered and loaded.

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Test locally
python -c "from {plugin_name.replace('-', '_')} import {class_name}; print({class_name}().metadata)"
```
'''
    (output_dir / "README.md").write_text(readme)
    
    console.print()
    console.print(Panel(
        f"[green]✓[/] Plugin scaffold created!\n\n"
        f"[bold]Location:[/] {output_dir}\n"
        f"[bold]Type:[/] {plugin_type}\n"
        f"[bold]Class:[/] {class_name}\n\n"
        f"[dim]Files created:[/]\n"
        f"  • {plugin_name.replace('-', '_')}.py - Plugin implementation\n"
        f"  • __init__.py - Package init\n"
        f"  • requirements.txt - Dependencies\n"
        f"  • README.md - Documentation\n\n"
        f"[dim]To install:[/]\n"
        f"  autosre plugin install {output_dir}",
        title="[bold cyan]Plugin Created[/]",
        border_style="green",
    ))
    console.print()
