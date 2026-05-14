"""AutoSRE CLI - Configuration management commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from autosre.core.config import Settings, get_settings, reload_settings, LLMProviderType

app = typer.Typer(
    name="config",
    help="Configure AutoSRE settings",
    no_args_is_help=True,
)

console = Console()

# Default config locations
DEFAULT_CONFIG_PATH = Path.home() / ".autosre" / "config.yaml"
PROJECT_CONFIG_PATH = Path("autosre.yaml")


def _get_config_path() -> Path:
    """Get the active config file path."""
    if PROJECT_CONFIG_PATH.exists():
        return PROJECT_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def _load_config_file(path: Path) -> dict:
    """Load config from YAML file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_config_file(path: Path, config: dict) -> None:
    """Save config to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _mask_secret(value: str) -> str:
    """Mask a secret value for display."""
    if not value or len(value) < 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


@app.command("init")
def init_config(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Config file path"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Initialize a new configuration file."""
    config_path = path or DEFAULT_CONFIG_PATH
    
    if config_path.exists() and not force:
        if json_output:
            console.print_json(json.dumps({
                "success": False,
                "error": f"Config file already exists: {config_path}",
            }))
        else:
            console.print(f"[yellow]Config file already exists: {config_path}[/yellow]")
            console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    # Default configuration
    default_config = {
        "# AutoSRE Configuration": None,
        "debug": False,
        "log_level": "INFO",
        
        "# Default LLM provider (openai, anthropic, ollama, azure_openai, together)": None,
        "default_provider": "openai",
        "default_model": "gpt-4-turbo",
        
        "# OpenAI Configuration": None,
        "openai": {
            "enabled": True,
            "# api_key": "sk-...",
            "default_model": "gpt-4-turbo",
        },
        
        "# Anthropic Configuration": None,
        "anthropic": {
            "enabled": True,
            "# api_key": "sk-ant-...",
            "default_model": "claude-3-sonnet-20240229",
        },
        
        "# Ollama Configuration (local)": None,
        "ollama": {
            "enabled": False,
            "base_url": "http://localhost:11434",
            "default_model": "llama3",
        },
        
        "# Cache settings": None,
        "cache": {
            "enabled": True,
            "backend": "memory",
            "ttl_seconds": 3600,
        },
        
        "# Retry settings": None,
        "retry": {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 60.0,
        },
    }
    
    # Write config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with comments preserved
    with open(config_path, "w") as f:
        f.write("# AutoSRE Configuration\n")
        f.write("# See https://autosre.dev/docs/configuration for full options\n\n")
        
        yaml.dump({
            "debug": False,
            "log_level": "INFO",
            "default_provider": "openai",
            "default_model": "gpt-4-turbo",
            "openai": {
                "enabled": True,
                "default_model": "gpt-4-turbo",
            },
            "anthropic": {
                "enabled": True,
                "default_model": "claude-3-sonnet-20240229",
            },
            "ollama": {
                "enabled": False,
                "base_url": "http://localhost:11434",
                "default_model": "llama3",
            },
            "cache": {
                "enabled": True,
                "backend": "memory",
                "ttl_seconds": 3600,
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
            },
        }, f, default_flow_style=False, sort_keys=False)
    
    if json_output:
        console.print_json(json.dumps({
            "success": True,
            "path": str(config_path),
        }))
    else:
        console.print(f"[green]✓[/green] Created config file: [bold]{config_path}[/bold]")
        console.print("\n[dim]Next steps:[/dim]")
        console.print(f"  1. Edit {config_path} to add your API keys")
        console.print("  2. Or set environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY")
        console.print("  3. Run 'autosre config validate' to check configuration")


@app.command("show")
def show_config(
    secrets: Annotated[
        bool,
        typer.Option("--secrets", "-s", help="Show secret values (masked by default)"),
    ] = False,
    source: Annotated[
        bool,
        typer.Option("--source", help="Show where each value comes from"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show current configuration."""
    settings = get_settings()
    config_path = _get_config_path()
    
    if json_output:
        output = {
            "config_file": str(config_path) if config_path.exists() else None,
            "debug": settings.debug,
            "log_level": settings.log_level.value,
            "default_provider": settings.default_provider.value,
            "default_model": settings.default_model,
            "providers": {},
        }
        
        for provider in LLMProviderType:
            provider_settings = settings.get_provider_settings(provider)
            api_key = settings.get_api_key(provider)
            output["providers"][provider.value] = {
                "enabled": provider_settings.enabled,
                "default_model": provider_settings.default_model,
                "has_api_key": bool(api_key),
            }
        
        console.print_json(json.dumps(output))
        return
    
    # Show config file location
    if config_path.exists():
        console.print(f"[dim]Config file: {config_path}[/dim]\n")
    else:
        console.print("[dim]No config file found (using defaults + environment)[/dim]\n")
    
    # General settings
    console.print("[bold]General Settings[/bold]")
    console.print(f"  Debug: {settings.debug}")
    console.print(f"  Log level: {settings.log_level.value}")
    console.print()
    
    # LLM settings
    console.print("[bold]LLM Configuration[/bold]")
    console.print(f"  Default provider: [cyan]{settings.default_provider.value}[/cyan]")
    console.print(f"  Default model: [cyan]{settings.default_model}[/cyan]")
    console.print()
    
    # Provider details
    table = Table(
        title="Provider Status",
        show_header=True,
        header_style="bold",
    )
    
    table.add_column("Provider")
    table.add_column("Enabled")
    table.add_column("Model")
    table.add_column("API Key")
    table.add_column("Base URL", style="dim")
    
    for provider in LLMProviderType:
        provider_settings = settings.get_provider_settings(provider)
        api_key = settings.get_api_key(provider)
        
        enabled = "[green]✓[/green]" if provider_settings.enabled else "[dim]✗[/dim]"
        model = provider_settings.default_model or "-"
        
        if api_key:
            key_display = api_key if secrets else _mask_secret(api_key)
            key_status = f"[green]{key_display}[/green]"
        else:
            key_status = "[yellow]Not set[/yellow]"
        
        base_url = provider_settings.base_url or "-"
        
        table.add_row(
            provider.value,
            enabled,
            model,
            key_status,
            base_url[:40] if len(base_url) > 40 else base_url,
        )
    
    console.print(table)
    
    # Cache settings
    console.print(f"\n[bold]Cache[/bold]")
    console.print(f"  Enabled: {settings.cache.enabled}")
    console.print(f"  Backend: {settings.cache.backend.value}")
    console.print(f"  TTL: {settings.cache.ttl_seconds}s")
    
    # Retry settings
    console.print(f"\n[bold]Retry[/bold]")
    console.print(f"  Max retries: {settings.retry.max_retries}")
    console.print(f"  Base delay: {settings.retry.base_delay}s")


@app.command("set")
def set_config(
    key: Annotated[str, typer.Argument(help="Config key (e.g., 'openai.api_key')")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    config_file: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Config file to modify"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Set a configuration value."""
    config_path = config_file or DEFAULT_CONFIG_PATH
    
    # Load existing config
    config = _load_config_file(config_path)
    
    # Parse key path (e.g., "openai.api_key" -> ["openai", "api_key"])
    key_parts = key.split(".")
    
    # Navigate/create nested structure
    current = config
    for part in key_parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    # Set value (try to parse as JSON for complex values)
    final_key = key_parts[-1]
    try:
        # Try parsing as JSON for booleans, numbers, lists
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    
    old_value = current.get(final_key)
    current[final_key] = parsed_value
    
    # Save config
    _save_config_file(config_path, config)
    
    # Reload settings
    reload_settings()
    
    if json_output:
        console.print_json(json.dumps({
            "success": True,
            "key": key,
            "old_value": old_value,
            "new_value": parsed_value,
            "config_file": str(config_path),
        }))
    else:
        console.print(f"[green]✓[/green] Set [bold]{key}[/bold] = {parsed_value}")
        if old_value is not None:
            console.print(f"  [dim]Previous value: {old_value}[/dim]")


@app.command("validate")
def validate_config(
    config_file: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Config file to validate"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Validate configuration and check connectivity."""
    config_path = config_file or _get_config_path()
    
    issues = []
    warnings = []
    checks = []
    
    # Check config file
    if config_path.exists():
        checks.append(("Config file", "found", str(config_path)))
        try:
            with open(config_path) as f:
                yaml.safe_load(f)
            checks.append(("YAML syntax", "valid", None))
        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML: {e}")
    else:
        warnings.append("No config file found (using environment + defaults)")
    
    # Load settings
    try:
        settings = get_settings()
        checks.append(("Settings", "loaded", None))
    except Exception as e:
        issues.append(f"Failed to load settings: {e}")
        if json_output:
            console.print_json(json.dumps({"valid": False, "issues": issues}))
        else:
            console.print("[red]Configuration is invalid[/red]")
            for issue in issues:
                console.print(f"  • {issue}")
        raise typer.Exit(1)
    
    # Check default provider has API key
    default_key = settings.get_api_key(settings.default_provider)
    if default_key:
        checks.append(("Default provider API key", "configured", settings.default_provider.value))
    else:
        if settings.default_provider != LLMProviderType.OLLAMA:
            warnings.append(f"No API key for default provider: {settings.default_provider.value}")
    
    # Check enabled providers
    for provider in LLMProviderType:
        provider_settings = settings.get_provider_settings(provider)
        if provider_settings.enabled:
            api_key = settings.get_api_key(provider)
            if api_key or provider == LLMProviderType.OLLAMA:
                checks.append((f"{provider.value}", "ready", None))
            else:
                warnings.append(f"{provider.value} enabled but no API key")
    
    # Output
    is_valid = len(issues) == 0
    
    if json_output:
        console.print_json(json.dumps({
            "valid": is_valid,
            "config_file": str(config_path) if config_path.exists() else None,
            "checks": [{"name": c[0], "status": c[1], "detail": c[2]} for c in checks],
            "issues": issues,
            "warnings": warnings,
        }))
        return
    
    console.print(Panel(
        f"[bold]Config file:[/bold] {config_path if config_path.exists() else 'None (using defaults)'}",
        title="🔍 Configuration Validation",
        border_style="cyan",
    ))
    
    # Show checks
    console.print("\n[bold]Checks:[/bold]")
    for name, status, detail in checks:
        detail_str = f" ({detail})" if detail else ""
        console.print(f"  [green]✓[/green] {name}: {status}{detail_str}")
    
    # Show warnings
    if warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")
    
    # Show issues
    if issues:
        console.print("\n[bold red]Issues:[/bold red]")
        for issue in issues:
            console.print(f"  [red]✗[/red] {issue}")
        raise typer.Exit(1)
    
    console.print(f"\n[green]✓ Configuration is valid[/green]")


@app.command("env")
def show_env_vars(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show environment variables used by AutoSRE."""
    env_vars = {
        "AUTOSRE_DEBUG": ("Enable debug mode", os.getenv("AUTOSRE_DEBUG")),
        "AUTOSRE_LOG_LEVEL": ("Log level", os.getenv("AUTOSRE_LOG_LEVEL")),
        "AUTOSRE_DEFAULT_PROVIDER": ("Default LLM provider", os.getenv("AUTOSRE_DEFAULT_PROVIDER")),
        "AUTOSRE_DEFAULT_MODEL": ("Default model", os.getenv("AUTOSRE_DEFAULT_MODEL")),
        "AUTOSRE_CONFIG_FILE": ("Config file path", os.getenv("AUTOSRE_CONFIG_FILE")),
        "OPENAI_API_KEY": ("OpenAI API key", _mask_secret(os.getenv("OPENAI_API_KEY", "")) or None),
        "ANTHROPIC_API_KEY": ("Anthropic API key", _mask_secret(os.getenv("ANTHROPIC_API_KEY", "")) or None),
        "AZURE_OPENAI_API_KEY": ("Azure OpenAI API key", _mask_secret(os.getenv("AZURE_OPENAI_API_KEY", "")) or None),
        "TOGETHER_API_KEY": ("Together API key", _mask_secret(os.getenv("TOGETHER_API_KEY", "")) or None),
    }
    
    if json_output:
        output = {k: {"description": v[0], "value": v[1]} for k, v in env_vars.items()}
        console.print_json(json.dumps(output))
        return
    
    table = Table(
        title="Environment Variables",
        show_header=True,
        header_style="bold",
    )
    
    table.add_column("Variable")
    table.add_column("Description")
    table.add_column("Value")
    
    for var, (desc, value) in env_vars.items():
        if value:
            value_display = f"[green]{value}[/green]"
        else:
            value_display = "[dim]Not set[/dim]"
        
        table.add_row(var, desc, value_display)
    
    console.print(table)
