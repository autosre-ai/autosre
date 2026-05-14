"""AutoSRE CLI - Investigation management commands."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from autosre.core.models import (
    Investigation,
    InvestigationStatus,
    Observation,
    ObservationType,
    Hypothesis,
    HypothesisStatus,
    Action,
    ActionType,
    ActionStatus,
)

app = typer.Typer(
    name="investigate",
    help="Run and manage investigations",
    no_args_is_help=True,
)

console = Console()


def _get_status_color(status: InvestigationStatus) -> str:
    """Get color for investigation status."""
    colors = {
        InvestigationStatus.PENDING: "yellow",
        InvestigationStatus.IN_PROGRESS: "cyan",
        InvestigationStatus.WAITING_FOR_DATA: "yellow",
        InvestigationStatus.WAITING_FOR_APPROVAL: "magenta",
        InvestigationStatus.COMPLETED: "green",
        InvestigationStatus.FAILED: "red",
        InvestigationStatus.CANCELLED: "dim",
    }
    return colors.get(status, "white")


def _get_hypothesis_icon(status: HypothesisStatus) -> str:
    """Get icon for hypothesis status."""
    icons = {
        HypothesisStatus.PROPOSED: "💭",
        HypothesisStatus.INVESTIGATING: "🔍",
        HypothesisStatus.CONFIRMED: "✅",
        HypothesisStatus.REJECTED: "❌",
        HypothesisStatus.INCONCLUSIVE: "❓",
    }
    return icons.get(status, "•")


def _get_mock_investigations() -> list[Investigation]:
    """Get mock investigations for demo purposes."""
    # TODO: Replace with actual investigation store
    inv1 = Investigation(
        id=UUID("abcdef12-1234-1234-1234-123456789001"),
        alert_id=UUID("12345678-1234-1234-1234-123456789001"),
        status=InvestigationStatus.IN_PROGRESS,
        title="Investigating HighCPUUsage on api-gateway",
        objective="Determine root cause of sustained high CPU usage",
    )
    inv1.observations = [
        Observation(
            id=uuid4(),
            type=ObservationType.METRIC,
            source="prometheus",
            query="rate(process_cpu_seconds_total{service='api-gateway'}[5m])",
            description="CPU utilization at 95% for the past 10 minutes",
            data={"value": 0.95},
            is_anomalous=True,
            relevance_score=0.9,
        ),
        Observation(
            id=uuid4(),
            type=ObservationType.LOG,
            source="elasticsearch",
            query="service:api-gateway AND level:ERROR",
            description="Found 150 error logs in the past 5 minutes",
            data={"error_count": 150},
            is_anomalous=True,
            relevance_score=0.85,
        ),
    ]
    inv1.hypotheses = [
        Hypothesis(
            id=uuid4(),
            status=HypothesisStatus.INVESTIGATING,
            statement="High traffic causing resource exhaustion",
            reasoning="Request rate increased 3x in the past hour",
            confidence=0.7,
        ),
        Hypothesis(
            id=uuid4(),
            status=HypothesisStatus.REJECTED,
            statement="Memory leak causing GC thrashing",
            reasoning="No significant memory increase observed",
            confidence=0.2,
        ),
    ]
    
    inv2 = Investigation(
        id=UUID("abcdef12-1234-1234-1234-123456789002"),
        alert_id=UUID("12345678-1234-1234-1234-123456789003"),
        status=InvestigationStatus.COMPLETED,
        title="Investigating PodCrashLooping on payment-service",
        objective="Identify cause of repeated pod restarts",
    )
    
    return [inv1, inv2]


@app.command("start")
def start_investigation(
    alert_id: Annotated[str, typer.Argument(help="Alert ID to investigate")],
    auto_remediate: Annotated[
        bool,
        typer.Option("--auto-remediate", "-a", help="Enable automatic remediation"),
    ] = False,
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", "-d", help="Maximum investigation depth"),
    ] = 5,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Investigation timeout in seconds"),
    ] = 300,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Start a new investigation for an alert."""
    investigation_id = uuid4()
    
    if json_output:
        result = {
            "success": True,
            "alert_id": alert_id,
            "investigation_id": str(investigation_id),
            "status": "started",
            "config": {
                "auto_remediate": auto_remediate,
                "max_depth": max_depth,
                "timeout": timeout,
            },
        }
        console.print_json(json.dumps(result))
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Starting investigation...", total=None)
        # TODO: Actually start investigation
        import time
        time.sleep(1)
    
    console.print(Panel(
        f"""[bold]Investigation ID:[/bold] {investigation_id}
[bold]Alert ID:[/bold] {alert_id}

[bold]Configuration:[/bold]
  Max depth: {max_depth} levels
  Timeout: {timeout}s
  Auto-remediate: {'[green]Yes[/green]' if auto_remediate else '[yellow]No[/yellow]'}

[dim]Track progress with:[/dim]
  autosre investigate status {str(investigation_id)[:8]}
  autosre investigate timeline {str(investigation_id)[:8]}""",
        title="🔍 Investigation Started",
        border_style="cyan",
    ))


@app.command("status")
def get_status(
    investigation_id: Annotated[str, typer.Argument(help="Investigation ID")],
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch for status updates"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Get the current status of an investigation."""
    investigations = _get_mock_investigations()
    
    # Find matching investigation
    investigation = None
    for inv in investigations:
        if str(inv.id).startswith(investigation_id) or str(inv.id) == investigation_id:
            investigation = inv
            break
    
    if not investigation:
        console.print(f"[red]Investigation not found: {investigation_id}[/red]")
        raise typer.Exit(1)
    
    if json_output:
        output = {
            "id": str(investigation.id),
            "alert_id": str(investigation.alert_id),
            "status": investigation.status.value,
            "title": investigation.title,
            "observations_count": len(investigation.observations),
            "hypotheses_count": len(investigation.hypotheses),
            "actions_count": len(investigation.actions),
            "started_at": investigation.started_at.isoformat(),
            "llm_calls": investigation.llm_calls,
            "total_tokens": investigation.total_tokens,
        }
        console.print_json(json.dumps(output))
        return
    
    status_text = Text(investigation.status.value.replace("_", " ").upper())
    status_text.stylize(_get_status_color(investigation.status))
    
    # Build status panel
    content = f"""[bold]Title:[/bold] {investigation.title}
[bold]Status:[/bold] {status_text}
[bold]Alert ID:[/bold] {str(investigation.alert_id)[:8]}

[bold]Progress:[/bold]
  📊 Observations: {len(investigation.observations)}
  💭 Hypotheses: {len(investigation.hypotheses)} ({len(investigation.get_active_hypotheses())} active)
  ⚡ Actions: {len(investigation.actions)}

[bold]Resources:[/bold]
  LLM calls: {investigation.llm_calls}
  Tokens used: {investigation.total_tokens:,}

[bold]Started:[/bold] {investigation.started_at.isoformat()}"""
    
    if investigation.completed_at:
        content += f"\n[bold]Completed:[/bold] {investigation.completed_at.isoformat()}"
    
    console.print(Panel(
        content,
        title=f"🔍 Investigation {str(investigation.id)[:8]}",
        border_style=_get_status_color(investigation.status),
    ))
    
    # Show hypotheses summary
    if investigation.hypotheses:
        console.print("\n[bold]Hypotheses:[/bold]")
        for hyp in investigation.hypotheses:
            icon = _get_hypothesis_icon(hyp.status)
            confidence = f"[dim]({hyp.confidence:.0%} confidence)[/dim]"
            console.print(f"  {icon} {hyp.statement} {confidence}")


@app.command("timeline")
def get_timeline(
    investigation_id: Annotated[str, typer.Argument(help="Investigation ID")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum events to show"),
    ] = 50,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """View the timeline of an investigation."""
    investigations = _get_mock_investigations()
    
    # Find matching investigation
    investigation = None
    for inv in investigations:
        if str(inv.id).startswith(investigation_id) or str(inv.id) == investigation_id:
            investigation = inv
            break
    
    if not investigation:
        console.print(f"[red]Investigation not found: {investigation_id}[/red]")
        raise typer.Exit(1)
    
    # Build timeline from observations, hypotheses, and actions
    events = []
    
    for obs in investigation.observations:
        events.append({
            "timestamp": obs.observed_at,
            "type": "observation",
            "icon": "📊",
            "description": obs.description,
            "source": obs.source,
        })
    
    for hyp in investigation.hypotheses:
        events.append({
            "timestamp": hyp.proposed_at,
            "type": "hypothesis",
            "icon": _get_hypothesis_icon(hyp.status),
            "description": hyp.statement,
            "status": hyp.status.value,
        })
    
    for action in investigation.actions:
        events.append({
            "timestamp": action.created_at,
            "type": "action",
            "icon": "⚡",
            "description": action.description,
            "status": action.status.value,
        })
    
    # Sort by timestamp
    events.sort(key=lambda e: e["timestamp"])
    events = events[:limit]
    
    if json_output:
        for e in events:
            e["timestamp"] = e["timestamp"].isoformat()
        console.print_json(json.dumps(events))
        return
    
    if not events:
        console.print("[dim]No events recorded yet[/dim]")
        return
    
    console.print(Panel(
        f"[bold]{investigation.title}[/bold]\nID: {str(investigation.id)[:8]}",
        title="📅 Investigation Timeline",
        border_style="cyan",
    ))
    
    # Create tree view
    tree = Tree("🔍 Investigation Start")
    
    for event in events:
        time_str = event["timestamp"].strftime("%H:%M:%S")
        event_text = f"[dim]{time_str}[/dim] {event['icon']} {event['description']}"
        if "source" in event:
            event_text += f" [dim]({event['source']})[/dim]"
        tree.add(event_text)
    
    console.print(tree)


@app.command("report")
def get_report(
    investigation_id: Annotated[str, typer.Argument(help="Investigation ID")],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (markdown, html, json)"),
    ] = "markdown",
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Generate or view an investigation report."""
    investigations = _get_mock_investigations()
    
    # Find matching investigation
    investigation = None
    for inv in investigations:
        if str(inv.id).startswith(investigation_id) or str(inv.id) == investigation_id:
            investigation = inv
            break
    
    if not investigation:
        console.print(f"[red]Investigation not found: {investigation_id}[/red]")
        raise typer.Exit(1)
    
    # Generate mock report
    from autosre.core.models import Report
    
    report = Report(
        investigation_id=investigation.id,
        title=investigation.title,
        executive_summary=f"Investigation of {investigation.title}. "
            f"Analyzed {len(investigation.observations)} data points and evaluated "
            f"{len(investigation.hypotheses)} hypotheses.",
        root_cause="High traffic causing resource exhaustion due to unexpected viral content",
        root_cause_confidence=0.85,
        timeline=[
            {"timestamp": "14:00", "description": "Alert triggered"},
            {"timestamp": "14:02", "description": "Investigation started"},
            {"timestamp": "14:05", "description": "High CPU confirmed via metrics"},
            {"timestamp": "14:08", "description": "Root cause identified"},
        ],
        impact_summary="API response times degraded to 2s+ for 15 minutes",
        affected_services=["api-gateway", "user-service"],
        downtime_seconds=900,
        resolution_summary="Scaled up replicas from 3 to 6",
        actions_taken=["Horizontal scale up", "Traffic analysis"],
        recommendations=[
            "Implement predictive auto-scaling",
            "Add traffic spike alerts",
        ],
        preventive_measures=[
            "Configure HPA with lower thresholds",
            "Add rate limiting for public endpoints",
        ],
    )
    
    if json_output or format == "json":
        output_data = report.model_dump(mode="json")
        if output:
            with open(output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)
            console.print(f"[green]✓[/green] Report saved to {output}")
        else:
            console.print_json(json.dumps(output_data, default=str))
        return
    
    if format == "markdown":
        markdown = report.to_markdown()
        if output:
            with open(output, "w") as f:
                f.write(markdown)
            console.print(f"[green]✓[/green] Report saved to {output}")
        else:
            from rich.markdown import Markdown
            console.print(Markdown(markdown))
        return
    
    if format == "html":
        # Simple HTML conversion
        markdown = report.to_markdown()
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{report.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif; 
               max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        ul {{ padding-left: 20px; }}
        .meta {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
<pre>{markdown}</pre>
</body>
</html>"""
        if output:
            with open(output, "w") as f:
                f.write(html)
            console.print(f"[green]✓[/green] Report saved to {output}")
        else:
            console.print(html)
        return
    
    console.print(f"[red]Unknown format: {format}[/red]")
    raise typer.Exit(1)


@app.command("list")
def list_investigations(
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum investigations to show"),
    ] = 20,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List all investigations."""
    investigations = _get_mock_investigations()
    
    if status:
        try:
            status_enum = InvestigationStatus(status.lower())
            investigations = [i for i in investigations if i.status == status_enum]
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            raise typer.Exit(1)
    
    investigations = investigations[:limit]
    
    if json_output:
        output = [{
            "id": str(inv.id),
            "alert_id": str(inv.alert_id),
            "status": inv.status.value,
            "title": inv.title,
            "started_at": inv.started_at.isoformat(),
        } for inv in investigations]
        console.print_json(json.dumps(output))
        return
    
    if not investigations:
        console.print("[dim]No investigations found[/dim]")
        return
    
    table = Table(
        title="🔍 Investigations",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Status")
    table.add_column("Obs", justify="right")
    table.add_column("Hyp", justify="right")
    table.add_column("Started")
    
    for inv in investigations:
        status_text = Text(inv.status.value.replace("_", " "))
        status_text.stylize(_get_status_color(inv.status))
        
        table.add_row(
            str(inv.id)[:8],
            inv.title[:40] + ("..." if len(inv.title) > 40 else ""),
            status_text,
            str(len(inv.observations)),
            str(len(inv.hypotheses)),
            inv.started_at.strftime("%Y-%m-%d %H:%M"),
        )
    
    console.print(table)
