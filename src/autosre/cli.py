"""
AutoSRE CLI - AI SRE Agent command-line interface.

Built with Typer for a rich, user-friendly experience.
"""

import typer
from rich.console import Console
from rich.table import Table

from autosre.memory import EpisodicMemory
from autosre.memory.models import MemoryQuery

app = typer.Typer(
    name="autosre",
    help="AI SRE Agent - Investigate production incidents autonomously",
    no_args_is_help=True,
)
console = Console()

# Shared memory instance
_memory: EpisodicMemory | None = None

def get_memory() -> EpisodicMemory:
    """Get or create the shared memory instance."""
    global _memory
    if _memory is None:
        _memory = EpisodicMemory()
    return _memory


@app.command()
def investigate(
    alert: str = typer.Argument(..., help="Alert description (e.g., 'checkout-service 5xx spike')"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    topology: str = typer.Option(None, "--topology", "-t", help="Path to topology.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
):
    """Investigate an incident and generate a situation report."""
    console.print(f"[bold cyan]🔍 Investigating:[/] {alert}")
    if service:
        console.print(f"[dim]Service:[/] {service}")
    if topology:
        console.print(f"[dim]Topology:[/] {topology}")
    if dry_run:
        console.print("[yellow]📋 Dry run mode - showing plan only[/]")
    if verbose:
        console.print("[dim]Verbose output enabled[/]")
    # TODO: Implement investigation flow
    console.print("[yellow]⚠️ Investigation not yet implemented[/]")


@app.command()
def history(
    service: str = typer.Option(None, "--service", "-s", help="Filter by service"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
):
    """Show investigation history."""
    import asyncio
    
    memory = get_memory()
    console.print("[bold]📜 Investigation History[/]")
    if service:
        console.print(f"[dim]Filtering by service:[/] {service}")
    console.print(f"[dim]Showing up to {limit} results[/]\n")
    
    # Query all episodes, optionally filtered by service
    mq = MemoryQuery(text="*", service=service)
    episodes = asyncio.run(memory.retrieve(mq, limit=limit))
    
    if not episodes:
        console.print("[yellow]No investigation history found[/]")
        return
    
    # Display as a table
    table = Table()
    table.add_column("Date", style="dim")
    table.add_column("Alert", style="cyan")
    table.add_column("Service", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Score", justify="right")
    
    for ep in episodes:
        date_str = ep.created_at.strftime("%Y-%m-%d %H:%M")
        status = "[green]✅[/]" if ep.resolved else "[red]❌[/]"
        score = f"{ep.effectiveness_score:.2f}"
        table.add_row(
            date_str,
            ep.alert_type[:30],
            ep.service_name or "—",
            status,
            score
        )
    
    console.print(table)


# Memory subcommand group
memory_app = typer.Typer(help="Manage episodic memory")
app.add_typer(memory_app, name="memory")


@memory_app.command("stats")
def memory_stats():
    """Show memory statistics."""
    memory = get_memory()
    stats = memory.get_stats()
    
    console.print("[bold]🧠 Memory Statistics[/]\n")
    
    # Main stats table
    table = Table(title="Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Episodes", str(stats['total_episodes']))
    table.add_row("Resolved", str(stats['resolved_count']))
    table.add_row("Resolution Rate", f"{stats['resolution_rate']:.1%}")
    table.add_row("Avg Effectiveness", f"{stats['avg_effectiveness_score']:.2f}")
    if stats['avg_resolution_seconds']:
        minutes = stats['avg_resolution_seconds'] / 60
        table.add_row("Avg Resolution Time", f"{minutes:.1f} min")
    table.add_row("Strategies", str(stats['total_strategies']))
    console.print(table)
    
    # Top alert types
    if stats['top_alert_types']:
        console.print()
        alert_table = Table(title="Top Alert Types")
        alert_table.add_column("Alert Type", style="yellow")
        alert_table.add_column("Count", style="magenta", justify="right")
        for item in stats['top_alert_types']:
            alert_table.add_row(item['alert_type'], str(item['count']))
        console.print(alert_table)


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, "--limit", "-n"),
):
    """Search past investigations."""
    import asyncio
    
    memory = get_memory()
    console.print(f"[bold]🔎 Searching:[/] {query}")
    console.print(f"[dim]Limit: {limit} results[/]\n")
    
    # Create a memory query - treat the query as alert_type for matching
    mq = MemoryQuery(
        text=query,
        alert_type=query,
        service=None,
    )
    
    # Run the async retrieve method
    episodes = asyncio.run(memory.retrieve(mq, limit=limit))
    
    if not episodes:
        console.print("[yellow]No results found[/]")
        return
    
    # Display results
    for i, ep in enumerate(episodes, 1):
        console.print(f"\n[bold cyan]#{i}[/] [bold]{ep.alert_type}[/] on [yellow]{ep.service_name or 'unknown'}[/]")
        console.print(f"   [dim]ID: {ep.id}[/]")
        console.print(f"   [dim]Date: {ep.created_at.strftime('%Y-%m-%d %H:%M')}[/]")
        if ep.summary:
            console.print(f"   {ep.summary[:100]}{'...' if len(ep.summary) > 100 else ''}")
        if ep.root_cause:
            console.print(f"   [green]Root cause:[/] {ep.root_cause[:80]}{'...' if len(ep.root_cause) > 80 else ''}")
        console.print(f"   [dim]Resolved: {'✅' if ep.resolved else '❌'} | Effectiveness: {ep.effectiveness_score:.2f}[/]")


@memory_app.command("clear")
def memory_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all memory (use with caution)."""
    memory = get_memory()
    stats = memory.get_stats()
    
    if stats['total_episodes'] == 0:
        console.print("[yellow]Memory is already empty[/]")
        return
    
    console.print(f"[bold red]⚠️  This will delete {stats['total_episodes']} episodes and {stats['total_strategies']} strategies![/]")
    
    if not force:
        confirm = typer.confirm("Are you sure you want to clear all memory?")
        if not confirm:
            raise typer.Abort()
    
    memory.clear()
    console.print("[red]🗑️ Memory cleared[/]")


# Topology subcommand group
topology_app = typer.Typer(help="Manage service topology")
app.add_typer(topology_app, name="topology")


@topology_app.command("show")
def topology_show(
    service: str = typer.Option(None, "--service", "-s", help="Show specific service"),
):
    """Show service topology."""
    console.print("[bold]🗺️ Service Topology[/]")
    if service:
        console.print(f"[dim]Filtering by service:[/] {service}")
    # TODO: Load and display topology
    console.print("[yellow]No topology loaded (use 'autosre topology validate' first)[/]")


@topology_app.command("validate")
def topology_validate(
    path: str = typer.Argument("topology.yaml", help="Path to topology file"),
):
    """Validate topology file."""
    console.print(f"[bold]✅ Validating:[/] {path}")
    # TODO: Validate topology
    console.print("[yellow]Topology validation not yet implemented[/]")


@topology_app.command("blast-radius")
def topology_blast_radius(
    service: str = typer.Argument(..., help="Service to check"),
):
    """Show blast radius for a service."""
    console.print(f"[bold]💥 Blast radius for:[/] {service}")
    # TODO: Calculate and show blast radius
    console.print("[yellow]Blast radius calculation not yet implemented[/]")


# Eval command
@app.command("eval")
def run_eval(
    scenarios: str = typer.Option("tests/scenarios/", "--scenarios", "-s"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run evaluation against test scenarios."""
    console.print("[bold]🧪 Running evaluation...[/]")
    console.print(f"[dim]Scenarios path:[/] {scenarios}")
    if verbose:
        console.print("[dim]Verbose output enabled[/]")
    # TODO: Run evaluation framework
    console.print("[yellow]Evaluation framework not yet implemented[/]")


# Serve command (for API/Slack)
@app.command()
def serve(
    port: int = typer.Option(8001, "--port", "-p"),
    host: str = typer.Option("0.0.0.0", "--host", "-H"),
):
    """Start API server for Slack/webhook integration."""
    console.print(f"[bold]🚀 Starting server on {host}:{port}[/]")
    # TODO: Start FastAPI server
    console.print("[yellow]API server not yet implemented[/]")


@app.command()
def version():
    """Show version information."""
    from autosre import __version__
    console.print(f"[bold]AutoSRE[/] v{__version__}")


def main():
    app()


if __name__ == "__main__":
    main()
