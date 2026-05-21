"""
AutoSRE Memory Commands

Manage episodic memory - the AI's learned experience from past incidents.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="memory",
    help="Manage episodic memory for incident learning",
    no_args_is_help=True,
)

console = Console()


def _get_memory():
    """Get memory instance."""
    from autosre.memory import EpisodicMemory
    return EpisodicMemory()


@app.command("list")
def list_episodes(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of episodes to show"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service"),
    alert_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by alert type"),
    resolved_only: bool = typer.Option(False, "--resolved", help="Show only resolved episodes"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    List past investigation episodes.
    
    Examples:
        autosre memory list
        autosre memory list --service checkout --limit 5
        autosre memory list --type error_rate --resolved
    """
    memory = _get_memory()
    
    # Query episodes
    from autosre.memory import MemoryQuery
    
    async def fetch_episodes():
        query = MemoryQuery(
            text="",
            service=service,
            alert_type=alert_type,
        )
        return await memory.retrieve(query, limit=limit)
    
    episodes = asyncio.run(fetch_episodes())
    
    # Filter resolved if needed
    if resolved_only:
        episodes = [ep for ep in episodes if ep.resolved]
    
    if json_output:
        output = [
            {
                "id": ep.id,
                "alert_type": ep.alert_type,
                "service": ep.service_name,
                "severity": ep.severity,
                "root_cause": ep.root_cause,
                "resolved": ep.resolved,
                "duration_seconds": ep.duration_seconds,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
            }
            for ep in episodes
        ]
        console.print(json.dumps(output, indent=2))
        return
    
    if not episodes:
        console.print("[yellow]No episodes found in memory[/]")
        console.print("[dim]Run some investigations to build episodic memory[/]")
        return
    
    table = Table(
        title=f"Episodic Memory ({len(episodes)} episodes)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Type", style="yellow")
    table.add_column("Service")
    table.add_column("Root Cause", max_width=35)
    table.add_column("Duration", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    
    for ep in episodes:
        duration_str = f"{ep.duration_seconds}s" if ep.duration_seconds else "-"
        score_str = f"{ep.effectiveness_score:.0%}" if ep.effectiveness_score else "-"
        status = "[green]✓[/]" if ep.resolved else "[yellow]⋯[/]"
        
        root_cause = ep.root_cause or "-"
        if len(root_cause) > 35:
            root_cause = root_cause[:32] + "..."
        
        table.add_row(
            ep.id[:10],
            ep.alert_type,
            ep.service_name or "-",
            root_cause,
            duration_str,
            score_str,
            status,
        )
    
    console.print()
    console.print(table)
    console.print()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Search episodes by text query.
    
    Searches alert types, root causes, and key findings.
    
    Examples:
        autosre memory search "redis connection"
        autosre memory search "timeout" --service api-gateway
    """
    memory = _get_memory()
    
    from autosre.memory import MemoryQuery
    
    async def do_search():
        mq = MemoryQuery(
            text=query,
            service=service,
            alert_type=query if query in ["error_rate", "latency", "resource_exhaustion", "availability"] else None,
        )
        return await memory.retrieve(mq, limit=limit)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Searching for '{query}'...", total=None)
        episodes = asyncio.run(do_search())
        progress.update(task, description=f"Found {len(episodes)} results")
    
    if json_output:
        output = [
            {
                "id": ep.id,
                "alert_type": ep.alert_type,
                "service": ep.service_name,
                "root_cause": ep.root_cause,
                "summary": ep.summary,
            }
            for ep in episodes
        ]
        console.print(json.dumps(output, indent=2))
        return
    
    if not episodes:
        console.print(f"[yellow]No episodes matching '{query}'[/]")
        return
    
    console.print()
    for ep in episodes:
        # Create a mini-panel for each result
        content = f"[bold]Type:[/] {ep.alert_type}\n"
        content += f"[bold]Service:[/] {ep.service_name or 'N/A'}\n"
        content += f"[bold]Root Cause:[/] {ep.root_cause or 'Unknown'}\n"
        if ep.summary:
            content += f"[bold]Summary:[/] {ep.summary}\n"
        if ep.key_findings:
            content += "[bold]Key Findings:[/]\n"
            for finding in ep.key_findings[:3]:
                if isinstance(finding, dict):
                    content += f"  • {finding.get('finding', str(finding))}\n"
                else:
                    content += f"  • {finding}\n"
        
        console.print(Panel(
            content.strip(),
            title=f"[cyan]{ep.id}[/]",
            border_style="dim",
        ))
    console.print()


@app.command()
def stats():
    """
    Show memory statistics and insights.
    
    Displays metrics about stored episodes, resolution rates,
    and common incident patterns.
    """
    memory = _get_memory()
    stats = memory.get_stats()
    
    # Main stats panel
    main_stats = Table(show_header=False, box=None)
    main_stats.add_column("Metric", style="cyan")
    main_stats.add_column("Value", style="green")
    
    main_stats.add_row("Total Episodes", str(stats.get("total_episodes", 0)))
    main_stats.add_row("Resolved", str(stats.get("resolved_count", 0)))
    resolution_rate = stats.get("resolution_rate", 0)
    main_stats.add_row("Resolution Rate", f"{resolution_rate:.0%}")
    main_stats.add_row("Strategies", str(stats.get("total_strategies", 0)))
    
    avg_eff = stats.get("avg_effectiveness_score", 0)
    main_stats.add_row("Avg Effectiveness", f"{avg_eff:.0%}")
    
    avg_duration = stats.get("avg_resolution_seconds")
    if avg_duration:
        if avg_duration > 60:
            main_stats.add_row("Avg Resolution Time", f"{avg_duration/60:.1f} min")
        else:
            main_stats.add_row("Avg Resolution Time", f"{avg_duration:.0f}s")
    
    console.print()
    console.print(Panel(main_stats, title="🧠 Memory Statistics", border_style="cyan"))
    
    # Top alert types
    top_types = stats.get("top_alert_types", [])
    if top_types:
        type_table = Table(title="Top Alert Types", show_header=True)
        type_table.add_column("Alert Type", style="yellow")
        type_table.add_column("Count", justify="right", style="green")
        type_table.add_column("Graph")
        
        max_count = max(t["count"] for t in top_types) if top_types else 1
        for t in top_types:
            bar_len = int((t["count"] / max_count) * 20)
            bar = "█" * bar_len
            type_table.add_row(t["alert_type"], str(t["count"]), f"[cyan]{bar}[/]")
        
        console.print()
        console.print(type_table)
    
    console.print()


@app.command()
def show(
    episode_id: str = typer.Argument(..., help="Episode ID to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show detailed information about a specific episode.
    
    Example:
        autosre memory show abc12345
    """
    memory = _get_memory()
    
    async def get_ep():
        return await memory.get(episode_id)
    
    episode = asyncio.run(get_ep())
    
    if not episode:
        console.print(f"[red]Episode {episode_id} not found[/]")
        raise typer.Exit(1)
    
    if json_output:
        console.print(json.dumps(episode.model_dump(), indent=2, default=str))
        return
    
    # Build detailed view
    content = f"""[bold cyan]Alert Type:[/] {episode.alert_type}
[bold cyan]Service:[/] {episode.service_name or 'N/A'}
[bold cyan]Severity:[/] {episode.severity}
[bold cyan]Created:[/] {episode.created_at}
[bold cyan]Duration:[/] {episode.duration_seconds or 'N/A'}s
[bold cyan]Status:[/] {'✓ Resolved' if episode.resolved else 'Pending'}
[bold cyan]Effectiveness:[/] {episode.effectiveness_score:.0%}

[bold yellow]Root Cause:[/]
{episode.root_cause or 'Unknown'}

[bold yellow]Summary:[/]
{episode.summary or 'No summary available'}
"""
    
    console.print()
    console.print(Panel(content, title=f"Episode {episode.id}", border_style="cyan"))
    
    # Skills used
    if episode.skills_used:
        console.print("\n[bold]Skills Used:[/]")
        for skill in episode.skills_used:
            console.print(f"  • {skill}")
    
    # Key findings
    if episode.key_findings:
        console.print("\n[bold]Key Findings:[/]")
        for finding in episode.key_findings:
            if isinstance(finding, dict):
                console.print(f"  • {finding.get('finding', str(finding))}")
            else:
                console.print(f"  • {finding}")
    
    # Steps taken
    if episode.steps_taken:
        console.print("\n[bold]Steps Taken:[/]")
        for i, step in enumerate(episode.steps_taken, 1):
            console.print(f"  {i}. {step}")
    
    console.print()


@app.command()
def clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    keep_strategies: bool = typer.Option(False, "--keep-strategies", help="Keep learned strategies"),
):
    """
    Clear all memory data.
    
    ⚠️  This permanently deletes all stored episodes and learned strategies.
    
    Example:
        autosre memory clear --force
    """
    if not force:
        console.print("[yellow]⚠️  This will delete all episodic memory![/]")
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            console.print("[dim]Cancelled[/]")
            raise typer.Abort()
    
    memory = _get_memory()
    
    # Get stats before clearing
    stats_before = memory.get_stats()
    episode_count = stats_before.get("total_episodes", 0)
    strategy_count = stats_before.get("total_strategies", 0)
    
    memory.clear()
    
    console.print()
    console.print(Panel(
        f"[green]✓[/] Cleared {episode_count} episodes" + 
        (f" and {strategy_count} strategies" if not keep_strategies else ""),
        title="Memory Cleared",
        border_style="red",
    ))


@app.command()
def export(
    output_path: str = typer.Argument("memory_export.json", help="Output file path"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json|csv"),
):
    """
    Export memory to a file.
    
    Example:
        autosre memory export backup.json
        autosre memory export incidents.csv --format csv
    """
    import json
    from pathlib import Path
    
    memory = _get_memory()
    
    from autosre.memory import MemoryQuery
    
    async def get_all():
        query = MemoryQuery(text="")
        return await memory.retrieve(query, limit=1000)
    
    episodes = asyncio.run(get_all())
    
    if not episodes:
        console.print("[yellow]No episodes to export[/]")
        return
    
    output = Path(output_path)
    
    if format == "json":
        data = [ep.model_dump() for ep in episodes]
        # Convert datetime to string
        for item in data:
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
        output.write_text(json.dumps(data, indent=2, default=str))
    
    elif format == "csv":
        import csv
        with open(output, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                "id", "created_at", "alert_type", "service", "severity",
                "root_cause", "resolved", "duration_seconds", "effectiveness_score"
            ])
            # Data
            for ep in episodes:
                writer.writerow([
                    ep.id,
                    ep.created_at.isoformat() if ep.created_at else "",
                    ep.alert_type,
                    ep.service_name or "",
                    ep.severity,
                    ep.root_cause or "",
                    ep.resolved,
                    ep.duration_seconds or "",
                    ep.effectiveness_score,
                ])
    
    console.print(f"[green]✓[/] Exported {len(episodes)} episodes to {output_path}")


@app.command("import")
def import_memory(
    input_path: str = typer.Argument(..., help="Input file path"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing or replace"),
):
    """
    Import memory from a file.
    
    Example:
        autosre memory import backup.json
        autosre memory import backup.json --replace
    """
    import json
    from pathlib import Path
    from autosre.memory import Episode
    
    input_file = Path(input_path)
    if not input_file.exists():
        console.print(f"[red]File not found: {input_path}[/]")
        raise typer.Exit(1)
    
    memory = _get_memory()
    
    if not merge:
        memory.clear()
    
    data = json.loads(input_file.read_text())
    
    imported = 0
    for item in data:
        try:
            # Handle datetime parsing
            if isinstance(item.get("created_at"), str):
                item["created_at"] = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            
            episode = Episode(**item)
            memory.store_episode(episode)
            imported += 1
        except Exception as e:
            console.print(f"[yellow]Warning: Could not import episode {item.get('id', '?')}: {e}[/]")
    
    console.print(f"[green]✓[/] Imported {imported} episodes")
