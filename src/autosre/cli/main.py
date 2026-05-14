"""AutoSRE CLI Main Entry Point."""

import typer
from rich.console import Console

from . import alerts, approve, audit, chat, config, investigate, runbook, serve

app = typer.Typer(
    name="autosre",
    help="🤖 AutoSRE - LLM-powered incident investigation and remediation",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Register subcommands
app.add_typer(alerts.app, name="alerts", help="Manage and investigate alerts")
app.add_typer(investigate.app, name="investigate", help="Run and manage investigations")
app.add_typer(chat.app, name="chat", help="Interactive chat with AutoSRE")
app.add_typer(runbook.app, name="runbook", help="Manage and execute runbooks")
app.add_typer(config.app, name="config", help="Configure AutoSRE settings")
app.add_typer(serve.app, name="serve", help="Start the AutoSRE API server")
app.add_typer(approve.app, name="approve", help="Human approval workflow for actions")
app.add_typer(audit.app, name="audit", help="Query and manage audit trail")


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
) -> None:
    """AutoSRE - Automated Site Reliability Engineering."""
    if version:
        from autosre import __version__
        console.print(f"[bold blue]AutoSRE[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()


def cli() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    cli()
