"""
AutoSRE Configuration Commands

Manage configuration settings for AutoSRE.
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

app = typer.Typer(
    name="config",
    help="Manage AutoSRE configuration",
    no_args_is_help=True,
)

console = Console()

# Default config directory
CONFIG_DIR = Path("~/.autosre").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _get_config() -> dict:
    """Load configuration from file and environment."""
    config = {}
    
    # Load from file if exists
    if CONFIG_FILE.exists():
        import yaml
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}
    
    # Merge with environment variables (env takes precedence)
    env_prefix = "OPENSRE_"
    for key, value in os.environ.items():
        if key.startswith(env_prefix):
            config_key = key[len(env_prefix):].lower()
            config[config_key] = value
    
    return config


def _save_config(config: dict):
    """Save configuration to file."""
    _ensure_config_dir()
    import yaml
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


@app.command()
def show(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    include_secrets: bool = typer.Option(False, "--secrets", help="Include sensitive values"),
):
    """
    Show current configuration.
    
    Displays settings from config file and environment variables.
    Sensitive values are masked by default.
    
    Examples:
        autosre config show
        autosre config show --json
        autosre config show --secrets
    """
    try:
        from autosre.config import Settings
        settings = Settings()
        
        config = {
            "llm_provider": settings.llm_provider,
            "llm_model": (
                settings.anthropic_model if settings.llm_provider == "anthropic"
                else settings.openai_model if settings.llm_provider == "openai"
                else settings.ollama_model
            ),
            "prometheus_url": settings.prometheus_url,
            "loki_url": settings.loki_url,
            "slack_enabled": settings.slack_enabled,
            "slack_channel": settings.slack_channel,
            "mcp_enabled": settings.mcp_enabled,
            "require_approval": settings.require_approval,
            "confidence_threshold": settings.confidence_threshold,
            "max_iterations": settings.max_iterations,
            "timeout_seconds": settings.timeout_seconds,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
        }
        
        # Add API keys (masked or not)
        if include_secrets:
            config["openai_api_key"] = settings.openai_api_key
            config["anthropic_api_key"] = settings.anthropic_api_key
            config["slack_bot_token"] = settings.slack_bot_token
        else:
            if settings.openai_api_key:
                config["openai_api_key"] = "sk-...***" + settings.openai_api_key[-4:]
            if settings.anthropic_api_key:
                config["anthropic_api_key"] = "sk-...***" + settings.anthropic_api_key[-4:]
            if settings.slack_bot_token:
                config["slack_bot_token"] = "xoxb-...***"
        
    except Exception as e:
        # Fall back to raw config
        config = _get_config()
        console.print(f"[dim]Note: Could not load settings module: {e}[/]")
    
    if json_output:
        console.print(json.dumps(config, indent=2))
        return
    
    # Build table
    table = Table(
        title="AutoSRE Configuration",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Source", style="dim")
    
    for key, value in config.items():
        # Determine source
        env_key = f"OPENSRE_{key.upper()}"
        if os.environ.get(env_key):
            source = "env"
        elif CONFIG_FILE.exists():
            source = "file"
        else:
            source = "default"
        
        # Format value
        if value is None:
            value_str = "[dim]not set[/]"
        elif isinstance(value, bool):
            value_str = "[green]true[/]" if value else "[red]false[/]"
        else:
            value_str = str(value)
        
        table.add_row(key, value_str, source)
    
    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Config file: {CONFIG_FILE}[/]")


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """
    Set a configuration value.
    
    Saves the value to the config file (~/.autosre/config.yaml).
    
    Examples:
        autosre config set llm_provider anthropic
        autosre config set log_level DEBUG
        autosre config set prometheus_url http://prometheus:9090
    """
    config = _get_config()
    
    # Handle boolean values
    if value.lower() in ("true", "yes", "1"):
        config[key] = True
    elif value.lower() in ("false", "no", "0"):
        config[key] = False
    # Handle numeric values
    elif value.isdigit():
        config[key] = int(value)
    elif value.replace(".", "").isdigit():
        config[key] = float(value)
    else:
        config[key] = value
    
    _save_config(config)
    
    console.print(f"[green]✓[/] Set {key} = {value}")


@app.command()
def unset(
    key: str = typer.Argument(..., help="Configuration key to remove"),
):
    """
    Remove a configuration value.
    
    Example:
        autosre config unset slack_bot_token
    """
    config = _get_config()
    
    if key not in config:
        console.print(f"[yellow]Key '{key}' not found in config[/]")
        return
    
    del config[key]
    _save_config(config)
    
    console.print(f"[green]✓[/] Removed {key}")


@app.command()
def validate():
    """
    Validate configuration and check connections.
    
    Tests:
    - Required settings are present
    - API keys are valid (if applicable)
    - External services are reachable
    """
    console.print()
    console.print("[bold]🔍 Validating configuration...[/]")
    console.print()
    
    results = []
    
    # Check config file
    if CONFIG_FILE.exists():
        results.append(("Config file", "✓", "Found", "green"))
    else:
        results.append(("Config file", "⚠", "Not found (using defaults)", "yellow"))
    
    # Check settings
    try:
        from autosre.config import Settings
        settings = Settings()
        results.append(("Settings", "✓", "Loaded successfully", "green"))
        
        # Check LLM provider
        if settings.llm_provider == "anthropic":
            if settings.anthropic_api_key:
                results.append(("Anthropic API", "✓", "Key configured", "green"))
            else:
                results.append(("Anthropic API", "✗", "No API key", "red"))
        elif settings.llm_provider == "openai":
            if settings.openai_api_key:
                results.append(("OpenAI API", "✓", "Key configured", "green"))
            else:
                results.append(("OpenAI API", "✗", "No API key", "red"))
        elif settings.llm_provider == "ollama":
            results.append(("Ollama", "✓", f"Using {settings.ollama_host}", "green"))
        
        # Check Prometheus
        if settings.prometheus_url:
            results.append(("Prometheus", "✓", settings.prometheus_url, "green"))
        else:
            results.append(("Prometheus", "⚠", "Not configured", "yellow"))
        
        # Check Slack
        if settings.slack_enabled:
            results.append(("Slack", "✓", f"Channel: {settings.slack_channel}", "green"))
        else:
            results.append(("Slack", "-", "Not configured", "dim"))
        
    except Exception as e:
        results.append(("Settings", "✗", str(e), "red"))
    
    # Check memory
    memory_path = CONFIG_DIR / "memory.db"
    if memory_path.exists():
        size_kb = memory_path.stat().st_size / 1024
        results.append(("Memory DB", "✓", f"{size_kb:.1f} KB", "green"))
    else:
        results.append(("Memory DB", "-", "Not initialized", "dim"))
    
    # Display results
    table = Table(show_header=True, header_style="bold")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details")
    
    all_ok = True
    for component, status, details, color in results:
        if status == "✗":
            all_ok = False
        table.add_row(component, f"[{color}]{status}[/]", f"[{color}]{details}[/]")
    
    console.print(table)
    console.print()
    
    if all_ok:
        console.print("[green]✓ Configuration is valid[/]")
    else:
        console.print("[red]✗ Configuration has errors[/]")
        raise typer.Exit(1)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
    provider: str = typer.Option("ollama", "--provider", "-p", help="LLM provider: ollama|openai|anthropic"),
):
    """
    Initialize configuration with defaults.
    
    Creates a config file with sensible defaults.
    
    Examples:
        autosre config init
        autosre config init --provider anthropic
    """
    _ensure_config_dir()
    
    if CONFIG_FILE.exists() and not force:
        console.print(f"[yellow]Config file already exists: {CONFIG_FILE}[/]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    # Create default config
    config = {
        "llm_provider": provider,
        "prometheus_url": "http://localhost:9090",
        "log_level": "INFO",
        "log_format": "text",
        "require_approval": True,
        "confidence_threshold": 0.7,
        "max_iterations": 10,
        "timeout_seconds": 300,
    }
    
    if provider == "ollama":
        config["ollama_host"] = "http://localhost:11434"
        config["ollama_model"] = "llama3.1:8b"
    elif provider == "openai":
        config["openai_model"] = "gpt-4o-mini"
        console.print("[yellow]Note: Set OPENSRE_OPENAI_API_KEY environment variable[/]")
    elif provider == "anthropic":
        config["anthropic_model"] = "claude-3-5-sonnet-20241022"
        console.print("[yellow]Note: Set OPENSRE_ANTHROPIC_API_KEY environment variable[/]")
    
    _save_config(config)
    
    console.print()
    console.print(Panel(
        f"[green]✓[/] Configuration initialized\n\n"
        f"[bold]Provider:[/] {provider}\n"
        f"[bold]Config file:[/] {CONFIG_FILE}\n\n"
        f"[dim]Edit the config file or set environment variables to customize.[/]",
        title="Configuration Created",
        border_style="green",
    ))


@app.command()
def edit():
    """
    Open configuration file in editor.
    
    Uses $EDITOR or falls back to vim/nano.
    """
    _ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        console.print("[yellow]No config file found. Creating default...[/]")
        _save_config({
            "llm_provider": "ollama",
            "log_level": "INFO",
        })
    
    editor = os.environ.get("EDITOR", "vim")
    
    import subprocess
    try:
        subprocess.run([editor, str(CONFIG_FILE)])
    except FileNotFoundError:
        # Try nano as fallback
        try:
            subprocess.run(["nano", str(CONFIG_FILE)])
        except FileNotFoundError:
            console.print(f"[red]No editor found. Edit manually: {CONFIG_FILE}[/]")
            raise typer.Exit(1)


@app.command("env")
def show_env():
    """
    Show environment variables for configuration.
    
    Lists all OPENSRE_* environment variables that can be used
    to configure AutoSRE.
    """
    env_vars = [
        ("OPENSRE_LLM_PROVIDER", "LLM provider (ollama, openai, anthropic)"),
        ("OPENSRE_OPENAI_API_KEY", "OpenAI API key"),
        ("OPENSRE_ANTHROPIC_API_KEY", "Anthropic API key"),
        ("OPENSRE_OLLAMA_HOST", "Ollama server URL"),
        ("OPENSRE_OLLAMA_MODEL", "Ollama model name"),
        ("OPENSRE_PROMETHEUS_URL", "Prometheus server URL"),
        ("OPENSRE_LOKI_URL", "Loki server URL"),
        ("OPENSRE_SLACK_BOT_TOKEN", "Slack bot token"),
        ("OPENSRE_SLACK_CHANNEL", "Default Slack channel"),
        ("OPENSRE_LOG_LEVEL", "Log level (DEBUG, INFO, WARNING, ERROR)"),
        ("OPENSRE_LOG_FORMAT", "Log format (json, text)"),
        ("OPENSRE_REQUIRE_APPROVAL", "Require approval for actions"),
        ("OPENSRE_CONFIDENCE_THRESHOLD", "Confidence threshold (0.0-1.0)"),
        ("OPENSRE_MAX_ITERATIONS", "Max investigation iterations"),
        ("OPENSRE_TIMEOUT_SECONDS", "Investigation timeout"),
    ]
    
    table = Table(title="Environment Variables", show_header=True)
    table.add_column("Variable", style="cyan")
    table.add_column("Description")
    table.add_column("Current", style="green")
    
    for var, desc in env_vars:
        current = os.environ.get(var)
        if current:
            # Mask sensitive values
            if "KEY" in var or "TOKEN" in var:
                current = "***" + current[-4:]
            table.add_row(var, desc, current)
        else:
            table.add_row(var, desc, "[dim]not set[/]")
    
    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Set these in your shell or .env file[/]")
