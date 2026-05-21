"""Configuration commands for AutoSRE CLI."""

from pathlib import Path

import click
import yaml

from .client import AutoSREClient
from .utils import (
    console,
    create_table,
    get_formatter,
    spinner,
)


CONFIG_PATH = Path.home() / ".autosre" / "config.yaml"


def load_config() -> dict:
    """Load the local config file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config: dict) -> None:
    """Save config to file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def get_nested(data: dict, key: str, default=None):
    """Get a nested key like 'llm.model' from a dict."""
    keys = key.split(".")
    for k in keys:
        if isinstance(data, dict) and k in data:
            data = data[k]
        else:
            return default
    return data


def set_nested(data: dict, key: str, value) -> None:
    """Set a nested key like 'llm.model' in a dict."""
    keys = key.split(".")
    for k in keys[:-1]:
        if k not in data:
            data[k] = {}
        data = data[k]
    data[keys[-1]] = value


def delete_nested(data: dict, key: str) -> bool:
    """Delete a nested key. Returns True if deleted."""
    keys = key.split(".")
    for k in keys[:-1]:
        if k not in data:
            return False
        data = data[k]
    if keys[-1] in data:
        del data[keys[-1]]
        return True
    return False


@click.group()
@click.pass_context
def config(ctx: click.Context):
    """Manage AutoSRE configuration.
    
    Configuration is stored in ~/.autosre/config.yaml
    """
    pass


@config.command("show")
@click.option("--key", "-k", help="Show specific key (e.g., llm.model)")
@click.option("--server", "-s", is_flag=True, help="Show server config instead of local")
@click.pass_context
def show_config(ctx: click.Context, key: str | None, server: bool):
    """Show current configuration.
    
    Examples:
        autosre config show
        autosre config show --key llm.model
        autosre config show --server
    """
    formatter = get_formatter(ctx)
    
    try:
        if server:
            with AutoSREClient() as client:
                with spinner("Fetching server config...", formatter.json_mode):
                    config_data = client.get_config()
        else:
            config_data = load_config()
        
        if key:
            value = get_nested(config_data, key)
            if formatter.json_mode:
                formatter.print_json({key: value})
            else:
                if value is None:
                    formatter.print_info(f"Key '{key}' not set")
                else:
                    console.print(f"[cyan]{key}[/cyan] = [green]{value}[/green]")
            return
        
        if formatter.json_mode:
            formatter.print_json(config_data)
            return
        
        if not config_data:
            formatter.print_info("No configuration set")
            console.print(f"\nConfig file: [dim]{CONFIG_PATH}[/dim]")
            return
        
        source = "Server" if server else "Local"
        console.print(f"[bold cyan]{source} Configuration[/bold cyan]\n")
        _print_config_tree(config_data)
        
        if not server:
            console.print(f"\nConfig file: [dim]{CONFIG_PATH}[/dim]")
    
    except Exception as e:
        formatter.print_error(f"Failed to show config: {e}")
        ctx.exit(1)


def _print_config_tree(data: dict, prefix: str = "") -> None:
    """Print config as an indented tree."""
    for key, value in data.items():
        full_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            console.print(f"  [cyan]{key}[/cyan]:")
            _print_config_tree(value, prefix=f"  ")
        else:
            # Mask sensitive values
            display_value = value
            if any(s in key.lower() for s in ["key", "secret", "password", "token"]):
                if value:
                    display_value = value[:4] + "****" if len(str(value)) > 4 else "****"
            console.print(f"  [cyan]{key}[/cyan]: [green]{display_value}[/green]")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def set_config(ctx: click.Context, key: str, value: str):
    """Set a configuration value.
    
    Examples:
        autosre config set llm.model claude-3-5-sonnet
        autosre config set api.base_url http://localhost:8000
        autosre config set api.timeout 60
    """
    formatter = get_formatter(ctx)
    
    try:
        config_data = load_config()
        
        # Try to parse as appropriate type
        parsed_value: str | int | float | bool = value
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        else:
            try:
                parsed_value = int(value)
            except ValueError:
                try:
                    parsed_value = float(value)
                except ValueError:
                    pass
        
        set_nested(config_data, key, parsed_value)
        save_config(config_data)
        
        if formatter.json_mode:
            formatter.print_json({"key": key, "value": parsed_value})
        else:
            formatter.print_success(f"Set {key} = {parsed_value}")
    
    except Exception as e:
        formatter.print_error(f"Failed to set config: {e}")
        ctx.exit(1)


@config.command("unset")
@click.argument("key")
@click.pass_context
def unset_config(ctx: click.Context, key: str):
    """Remove a configuration value.
    
    Example:
        autosre config unset llm.temperature
    """
    formatter = get_formatter(ctx)
    
    try:
        config_data = load_config()
        
        if delete_nested(config_data, key):
            save_config(config_data)
            formatter.print_success(f"Removed {key}")
        else:
            formatter.print_info(f"Key '{key}' not found")
    
    except Exception as e:
        formatter.print_error(f"Failed to unset config: {e}")
        ctx.exit(1)


@config.command("init")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config")
@click.pass_context
def init_config(ctx: click.Context, force: bool):
    """Initialize a new configuration file.
    
    Creates ~/.autosre/config.yaml with default values.
    """
    formatter = get_formatter(ctx)
    
    if CONFIG_PATH.exists() and not force:
        formatter.print_warning(f"Config already exists at {CONFIG_PATH}")
        formatter.print_info("Use --force to overwrite")
        return
    
    default_config = {
        "api": {
            "base_url": "http://localhost:8000",
            "timeout": 30,
        },
        "llm": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.0,
        },
        "output": {
            "color": True,
            "format": "rich",
        },
    }
    
    try:
        save_config(default_config)
        formatter.print_success(f"Created config at {CONFIG_PATH}")
        
        if not formatter.json_mode:
            console.print("\n[bold]Default configuration:[/bold]")
            _print_config_tree(default_config)
    
    except Exception as e:
        formatter.print_error(f"Failed to create config: {e}")
        ctx.exit(1)


@config.command("path")
@click.pass_context
def config_path(ctx: click.Context):
    """Show the config file path."""
    formatter = get_formatter(ctx)
    
    if formatter.json_mode:
        formatter.print_json({
            "path": str(CONFIG_PATH),
            "exists": CONFIG_PATH.exists(),
        })
    else:
        exists = "[green]exists[/green]" if CONFIG_PATH.exists() else "[dim]not found[/dim]"
        console.print(f"{CONFIG_PATH} ({exists})")
