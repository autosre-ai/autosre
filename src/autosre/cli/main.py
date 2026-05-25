"""
AutoSRE CLI - AI SRE Agent command-line interface.

Production CLI built with Typer and Rich for beautiful output.
"""

import typer
from rich.console import Console

# Create main Typer app
app = typer.Typer(
    name="autosre",
    help="AI SRE Agent for incident investigation 🤖",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            from autosre import __version__
        except ImportError:
            __version__ = "0.2.0"
        console.print(f"[bold cyan]AutoSRE[/] v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """AI SRE Agent for autonomous incident investigation."""
    pass


# Import and register command groups
from autosre.cli.commands import investigate, memory, config, demo, chat

app.add_typer(investigate.app, name="investigate", help="Investigation commands")
app.add_typer(memory.app, name="memory", help="Episodic memory management")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(demo.app, name="demo", help="Demo and testing scenarios")
app.add_typer(chat.app, name="chat", help="Interactive AI chat assistant")


# Quick access to investigate run
@app.command("run")
def quick_run(
    alert: str = typer.Argument(..., help="Alert or incident description"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("high", "--severity", help="Severity level"),
    mock: bool = typer.Option(False, "--mock", "-m", help="Use mock LLM"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text|json|markdown"),
):
    """
    Quick start an investigation (alias for 'investigate run').
    
    Examples:
        autosre run "High error rate on checkout"
        autosre run "API latency spike" --service api-gateway
    """
    from autosre.cli.commands.investigate import run as investigate_run
    investigate_run(
        alert=alert,
        service=service,
        severity=severity,
        mock=mock,
        output=output,
        stream=True,
        save=None,
    )


@app.command()
def status():
    """Show AutoSRE status and configuration."""
    from rich.table import Table
    from rich.panel import Panel
    from pathlib import Path
    
    try:
        from autosre import __version__
    except ImportError:
        __version__ = "0.2.0"
    
    # Create status table
    table = Table(title="AutoSRE Status", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan", width=20)
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    # Version
    table.add_row("Version", __version__, "")
    
    # Config file
    config_path = Path("~/.autosre/config.yaml").expanduser()
    if config_path.exists():
        table.add_row("Config", "✓ Found", str(config_path))
    else:
        table.add_row("Config", "[yellow]Not found[/]", str(config_path))
    
    # Memory database
    memory_path = Path("~/.autosre/memory.db").expanduser()
    if memory_path.exists():
        size_kb = memory_path.stat().st_size / 1024
        table.add_row("Memory", "✓ Available", f"{size_kb:.1f} KB")
    else:
        table.add_row("Memory", "[yellow]Not initialized[/]", "")
    
    # LLM Configuration
    try:
        from autosre.config import Settings
        settings = Settings()
        table.add_row("LLM Provider", settings.llm_provider, settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_model if settings.llm_provider == "openai" else settings.ollama_model)
    except Exception:
        table.add_row("LLM", "[yellow]Not configured[/]", "Set OPENSRE_LLM_PROVIDER")
    
    # Environment
    import os
    table.add_row("Python", os.sys.version.split()[0], "")
    
    console.print()
    console.print(Panel(table, title="[bold]🤖 AutoSRE[/]", border_style="cyan"))
    console.print()


def main():
    """Entry point for the CLI."""
    app()


# Backwards compatibility
cli = main


if __name__ == "__main__":
    main()
