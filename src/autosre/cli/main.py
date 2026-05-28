"""
AutoSRE CLI - AI SRE Agent command-line interface.

Production CLI built with Typer and Rich for beautiful output.

Shell Completion Support:
    AutoSRE supports shell completion for bash, zsh, and fish.
    Use the built-in --install-completion or --show-completion options,
    or use the dedicated 'completion' command for more control.
"""

import typer
from enum import Enum
from typing import Optional
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
from autosre.cli.commands import investigate, memory, config, demo, chat, doctor, runbook, tutorial, serve, benchmark, model, plugin, history, team, template, agent

app.add_typer(investigate.app, name="investigate", help="Investigation commands")
app.add_typer(memory.app, name="memory", help="Episodic memory management")
app.add_typer(history.app, name="history", help="Browse past investigations")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(demo.app, name="demo", help="Demo and testing scenarios")
app.add_typer(chat.app, name="chat", help="Interactive AI chat assistant")
app.add_typer(doctor.app, name="doctor", help="Health check and diagnostics")
app.add_typer(runbook.app, name="runbook", help="Runbook management and execution")
app.add_typer(tutorial.app, name="tutorial", help="Interactive onboarding tutorial")
app.add_typer(serve.app, name="serve", help="Webhook server for alert-driven investigations")
app.add_typer(benchmark.app, name="benchmark", help="Performance benchmarking")
app.add_typer(model.app, name="model", help="Configure AI model settings")
app.add_typer(plugin.app, name="plugin", help="Manage AutoSRE plugins")
app.add_typer(team.app, name="team", help="Team collaboration")
app.add_typer(template.app, name="template", help="Investigation templates for common incidents")

# Import click-based agent command and adapt it
from autosre.cli.commands.agent import agent as agent_click
from click.testing import CliRunner as ClickRunner

# Create a wrapper for the click-based agent command
import subprocess
import sys

agent_app = typer.Typer(name="agent", help="Autonomous agent for monitoring and remediation")

@agent_app.command("run")
def agent_run_wrapper(
    interval: int = typer.Option(30, help="Check interval in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't execute remediation actions"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    once: bool = typer.Option(False, "--once", help="Run once then exit"),
):
    """Run the agent in watch mode, continuously monitoring for alerts."""
    from autosre.cli.commands.agent import agent_run
    # Use the callback directly to bypass Click's argument parsing
    agent_run.callback(interval, once, dry_run, None, verbose)

@agent_app.command("analyze")
def agent_analyze_wrapper(
    alert_file: str = typer.Option(None, "--alert", "-a", help="Alert JSON file"),
    alert_name: str = typer.Option(None, "--alert-name", help="Analyze alert by name"),
    service: str = typer.Option(None, "--service", "-s", help="Service to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    model: str = typer.Option(None, "--model", "-m", help="Override LLM model"),
):
    """Analyze an alert and suggest remediation."""
    from autosre.cli.commands.agent import agent_analyze
    
    # Click commands need to be invoked with standalone_mode=False to avoid sys.exit
    # and pass parameters as keyword arguments matching the decorator options
    agent_analyze.callback(alert_file, alert_name, service, verbose, as_json, model)

app.add_typer(agent_app, name="agent")


# Quick access to investigate run
@app.command("run")
def quick_run(
    alert: str = typer.Argument(..., help="Alert or incident description"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("high", "--severity", help="Severity level"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text|json|markdown|html"),
    demo: bool = typer.Option(False, "--demo", "-d", help="Run with simulated data (no infrastructure required)"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Continuously monitor (re-run every 60s, show diff)"),
):
    """
    Quick start an investigation (alias for 'investigate run').
    
    Examples:
        autosre run "High error rate on checkout"
        autosre run "API latency spike" --service api-gateway
        autosre run "API latency spike" --demo  # Run without infrastructure
        autosre run "High error rate" --watch   # Continuous monitoring
    """
    from autosre.cli.commands.investigate import run as investigate_run
    investigate_run(
        alert=alert,
        service=service,
        severity=severity,
        output=output,
        stream=True,
        save=None,
        demo=demo,
        watch=watch,
        watch_interval=60,
    )


@app.command("diff")
def quick_diff(
    id1: str = typer.Argument(..., help="First investigation ID"),
    id2: str = typer.Argument(..., help="Second investigation ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    fields_only: bool = typer.Option(False, "--fields", "-f", help="Show only field differences"),
):
    """
    Compare two investigations side-by-side (alias for 'history diff').
    
    Shows what changed between investigations, identifies similar root causes,
    and highlights timeline differences.
    
    Examples:
        autosre diff abc123 def456       # Compare two investigations
        autosre diff abc def --json      # JSON output
        autosre diff abc def --fields    # Show only field differences
    """
    from autosre.cli.commands.history import diff_investigations
    diff_investigations(
        id1=id1,
        id2=id2,
        json_output=json_output,
        fields_only=fields_only,
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


class ShellType(str, Enum):
    """Supported shell types for completion."""
    bash = "bash"
    zsh = "zsh"
    fish = "fish"


@app.command()
def completion(
    shell: Optional[ShellType] = typer.Argument(
        None,
        help="Shell type: bash, zsh, or fish. Auto-detects if not specified.",
    ),
    install: bool = typer.Option(
        False,
        "--install",
        "-i",
        help="Install completion script to shell config file.",
    ),
):
    """
    Shell completion for bash, zsh, and fish.
    
    [bold]Show completion script:[/]
        autosre completion bash     # Output bash completion script
        autosre completion zsh      # Output zsh completion script
        autosre completion fish     # Output fish completion script
    
    [bold]Install completion:[/]
        autosre completion bash --install
        autosre completion zsh --install
        autosre completion fish --install
    
    [bold]Manual installation:[/]
        Bash:  autosre completion bash >> ~/.bashrc
        Zsh:   autosre completion zsh >> ~/.zshrc
        Fish:  autosre completion fish > ~/.config/fish/completions/autosre.fish
    
    After installation, restart your shell or run:
        source ~/.bashrc   # (or ~/.zshrc for zsh)
    """
    from typer.completion import get_completion_script, install as install_completion
    
    # Detect shell if not specified
    if shell is None:
        try:
            import shellingham
            detected_shell, _ = shellingham.detect_shell()
            shell_name = detected_shell.lower()
            if shell_name in ["bash", "zsh", "fish"]:
                shell = ShellType(shell_name)
            else:
                console.print(f"[yellow]Detected shell '{detected_shell}' is not supported.[/]")
                console.print("Please specify: [cyan]autosre completion bash|zsh|fish[/]")
                raise typer.Exit(1)
        except Exception:
            console.print("[yellow]Could not detect shell.[/]")
            console.print("Please specify: [cyan]autosre completion bash|zsh|fish[/]")
            raise typer.Exit(1)
    
    shell_value = shell.value
    
    if install:
        # Use Typer's built-in installation mechanism
        try:
            install_completion(shell_value)
            console.print(f"[green]✓[/] Completion installed for {shell_value}")
            console.print("[dim]Restart your shell or source your config file to activate.[/]")
        except Exception as e:
            console.print(f"[red]Installation failed:[/] {e}")
            console.print(f"\n[yellow]Manual installation:[/]")
            if shell_value == "bash":
                console.print("  autosre completion bash >> ~/.bashrc")
            elif shell_value == "zsh":
                console.print("  autosre completion zsh >> ~/.zshrc")
            else:
                console.print("  autosre completion fish > ~/.config/fish/completions/autosre.fish")
            raise typer.Exit(1)
    else:
        # Output the completion script
        script = get_completion_script(
            prog_name="autosre",
            complete_var="_AUTOSRE_COMPLETE",
            shell=shell_value,
        )
        console.print(script, highlight=False)


def main():
    """Entry point for the CLI."""
    app()


# Backwards compatibility
cli = main


if __name__ == "__main__":
    main()
