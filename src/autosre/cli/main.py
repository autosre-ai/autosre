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
from autosre.cli.commands import investigate, memory, config, demo, chat, doctor, runbook, tutorial

app.add_typer(investigate.app, name="investigate", help="Investigation commands")
app.add_typer(memory.app, name="memory", help="Episodic memory management")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(demo.app, name="demo", help="Demo and testing scenarios")
app.add_typer(chat.app, name="chat", help="Interactive AI chat assistant")
app.add_typer(doctor.app, name="doctor", help="Health check and diagnostics")
app.add_typer(runbook.app, name="runbook", help="Runbook management and execution")
app.add_typer(tutorial.app, name="tutorial", help="Interactive onboarding tutorial")


# Quick access to investigate run
@app.command("run")
def quick_run(
    alert: str = typer.Argument(..., help="Alert or incident description"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("high", "--severity", help="Severity level"),
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
        output=output,
        stream=True,
        save=None,
        demo=False,
        watch=False,
        watch_interval=60,
    )


@app.command()
def status(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output, just show readiness"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show additional details"),
):
    """
    Show comprehensive AutoSRE status and configuration.
    
    Displays:
    - Current configuration (provider, model)
    - Memory stats (investigations, episodes)
    - Last investigation summary
    - Connected services status
    - Version and environment info
    
    Examples:
        autosre status           # Full status display
        autosre status -q        # Quick readiness check
        autosre status -v        # Verbose with extra details
    """
    from autosre.cli.commands.status import run_status
    run_status(quiet=quiet, verbose=verbose)


def main():
    """Entry point for the CLI."""
    app()


# Backwards compatibility
cli = main


if __name__ == "__main__":
    main()
