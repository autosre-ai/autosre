"""Shared utilities for CLI output formatting, spinners, and common operations."""

from contextlib import contextmanager
from datetime import datetime
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Global console for rich output
console = Console()
error_console = Console(stderr=True)


class OutputFormatter:
    """Handles output formatting with JSON mode support."""

    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode

    def print(self, message: str, style: str | None = None) -> None:
        """Print a message, respecting JSON mode."""
        if self.json_mode:
            return  # In JSON mode, only structured output
        if style:
            console.print(message, style=style)
        else:
            console.print(message)

    def print_json(self, data: Any) -> None:
        """Print JSON output."""
        import json
        click.echo(json.dumps(data, indent=2, default=str))

    def print_error(self, message: str) -> None:
        """Print an error message."""
        if self.json_mode:
            self.print_json({"error": message})
        else:
            error_console.print(f"[red]✗[/red] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        if self.json_mode:
            return
        console.print(f"[green]✓[/green] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        if self.json_mode:
            return
        console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        if self.json_mode:
            return
        console.print(f"[blue]ℹ[/blue] {message}")


def create_table(title: str, columns: list[tuple[str, str]]) -> Table:
    """Create a styled table with the given columns.
    
    Args:
        title: Table title
        columns: List of (header, style) tuples
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for header, style in columns:
        table.add_column(header, style=style)
    return table


def format_timestamp(ts: str | datetime | None) -> str:
    """Format a timestamp for display."""
    if ts is None:
        return "N/A"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float | None) -> str:
    """Format a duration in seconds for display."""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def severity_style(severity: str) -> str:
    """Get the rich style for a severity level."""
    styles = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "green",
        "info": "blue",
    }
    return styles.get(severity.lower(), "white")


def status_style(status: str) -> str:
    """Get the rich style for a status."""
    styles = {
        "running": "yellow",
        "pending": "cyan",
        "completed": "green",
        "failed": "red",
        "cancelled": "dim",
    }
    return styles.get(status.lower(), "white")


def status_icon(status: str) -> str:
    """Get an icon for a status."""
    icons = {
        "running": "⏳",
        "pending": "⏸",
        "completed": "✓",
        "failed": "✗",
        "cancelled": "⊘",
    }
    return icons.get(status.lower(), "•")


@contextmanager
def spinner(message: str, json_mode: bool = False):
    """Context manager for showing a spinner during long operations."""
    if json_mode:
        yield
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description=message, total=None)
        yield


def print_investigation_panel(
    investigation_id: str,
    title: str,
    status: str,
    severity: str,
    service: str | None = None,
) -> None:
    """Print a styled panel for an investigation."""
    content = Text()
    content.append("ID: ", style="dim")
    content.append(f"{investigation_id}\n", style="cyan")
    content.append("Status: ", style="dim")
    content.append(f"{status_icon(status)} {status}\n", style=status_style(status))
    content.append("Severity: ", style="dim")
    content.append(f"{severity}\n", style=severity_style(severity))
    if service:
        content.append("Service: ", style="dim")
        content.append(f"{service}\n", style="white")

    panel = Panel(
        content,
        title=f"[bold]{title}[/bold]",
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)


def confirm_action(message: str) -> bool:
    """Prompt for confirmation."""
    return click.confirm(message)


def prompt_input(message: str, default: str | None = None) -> str:
    """Prompt for text input."""
    return click.prompt(message, default=default)


def prompt_choice(message: str, choices: list[str], default: str | None = None) -> str:
    """Prompt for a choice from a list."""
    return click.prompt(
        message,
        type=click.Choice(choices),
        default=default,
    )


# Pass context through click
pass_formatter = click.make_pass_decorator(OutputFormatter)


def get_formatter(ctx: click.Context) -> OutputFormatter:
    """Get the output formatter from the click context."""
    return ctx.ensure_object(OutputFormatter)
