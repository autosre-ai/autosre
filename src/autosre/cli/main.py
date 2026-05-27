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
from autosre.cli.commands import investigate, memory, config, demo, chat, doctor, runbook, tutorial, serve, benchmark, model, plugin, history

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
    import os
    
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
