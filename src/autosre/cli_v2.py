"""
AutoSRE CLI (Typer)

Modern CLI for AutoSRE v2 built with Typer.
"""
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(
    name="autosre",
    help="AutoSRE - Open-source AI SRE Agent 🤖",
    add_completion=False,
)


@app.command()
def investigate(
    alert: str = typer.Argument(..., help="Alert ID or description to investigate"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Service name"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output report path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Start an investigation for an alert.
    
    Example:
        autosre investigate "High error rate" --service frontend
    """
    from rich.console import Console
    console = Console()
    
    console.print(f"[bold blue]🔍 Starting investigation[/bold blue]")
    console.print(f"Alert: {alert}")
    if service:
        console.print(f"Service: {service}")
    
    # TODO: Implement full investigation flow
    console.print("[yellow]Investigation flow not yet implemented[/yellow]")


@app.command()
def status():
    """Show AutoSRE status and configuration."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    table = Table(title="AutoSRE Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    table.add_row("Version", "0.1.0")
    table.add_row("Config", "~/.autosre/config.yaml")
    table.add_row("Memory", "Not configured")
    table.add_row("LLM", "Not configured")
    
    console.print(table)


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Directory to initialize"),
    demo: bool = typer.Option(False, "--demo", help="Include demo data"),
):
    """Initialize AutoSRE in a directory."""
    from rich.console import Console
    console = Console()
    
    config_dir = path / ".autosre"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[green]✓[/green] Created {config_dir}")
    console.print("[bold]AutoSRE initialized![/bold]")


@app.command()
def memory(
    action: str = typer.Argument(..., help="Action: list, search, clear"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
):
    """Manage episodic memory."""
    from rich.console import Console
    console = Console()
    
    if action == "list":
        console.print("[yellow]No episodes stored yet[/yellow]")
    elif action == "search":
        if not query:
            console.print("[red]Query required for search[/red]")
            raise typer.Exit(1)
        console.print(f"Searching for: {query}")
        console.print("[yellow]No matching episodes[/yellow]")
    elif action == "clear":
        console.print("[yellow]Memory cleared[/yellow]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command()
def topology(
    action: str = typer.Argument(..., help="Action: show, load, export"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Topology file"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Service to focus on"),
):
    """Manage service topology."""
    from rich.console import Console
    console = Console()
    
    if action == "show":
        console.print("[yellow]No topology loaded[/yellow]")
    elif action == "load":
        if not file:
            console.print("[red]File required for load[/red]")
            raise typer.Exit(1)
        console.print(f"Loading topology from: {file}")
    elif action == "export":
        console.print("[yellow]Exporting topology...[/yellow]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command()
def skills(
    action: str = typer.Argument("list", help="Action: list, test"),
    skill: Optional[str] = typer.Option(None, "--skill", "-s", help="Skill to test"),
):
    """Manage investigation skills."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    if action == "list":
        table = Table(title="Available Skills")
        table.add_column("Skill", style="cyan")
        table.add_column("Description")
        table.add_column("Status", style="green")
        
        table.add_row("kubernetes", "K8s cluster investigation", "Available")
        table.add_row("metrics", "Prometheus metrics", "Available")
        table.add_row("logs", "Log search (Loki)", "Available")
        
        console.print(table)
    elif action == "test":
        if not skill:
            console.print("[red]Skill name required for test[/red]")
            raise typer.Exit(1)
        console.print(f"Testing skill: {skill}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
