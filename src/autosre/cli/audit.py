"""AutoSRE CLI - Audit command for viewing audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autosre.core.audit import (
    AuditEventType,
    AuditQuery,
    AuditSeverity,
    AuditTrail,
    get_audit_trail,
)

app = typer.Typer(
    name="audit",
    help="Query and manage the audit trail",
    no_args_is_help=True,
)

console = Console()


def _get_severity_style(severity: AuditSeverity) -> str:
    """Get style for severity."""
    styles = {
        AuditSeverity.INFO: "dim",
        AuditSeverity.WARNING: "yellow",
        AuditSeverity.ERROR: "red",
        AuditSeverity.CRITICAL: "bold red",
    }
    return styles.get(severity, "white")


def _get_event_type_style(event_type: AuditEventType) -> str:
    """Get style for event type."""
    if "approval" in event_type.value.lower():
        return "cyan"
    elif "action" in event_type.value.lower():
        return "green"
    elif "alert" in event_type.value.lower():
        return "yellow"
    elif "error" in event_type.value.lower():
        return "red"
    return "white"


def _format_time(dt: datetime) -> str:
    """Format datetime for display."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    
    if delta.total_seconds() < 60:
        return f"{int(delta.total_seconds())}s ago"
    elif delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() / 60)}m ago"
    elif delta.total_seconds() < 86400:
        return dt.strftime("%H:%M")
    elif delta.total_seconds() < 604800:  # 7 days
        return dt.strftime("%a %H:%M")
    else:
        return dt.strftime("%Y-%m-%d")


@app.command("list")
def list_events(
    hours: Annotated[
        int,
        typer.Option("--hours", "-H", help="Show events from last N hours"),
    ] = 24,
    event_type: Annotated[
        Optional[str],
        typer.Option("--type", "-t", help="Filter by event type"),
    ] = None,
    severity: Annotated[
        Optional[str],
        typer.Option("--severity", "-s", help="Filter by severity (info/warning/error/critical)"),
    ] = None,
    alert_id: Annotated[
        Optional[str],
        typer.Option("--alert", "-a", help="Filter by alert ID"),
    ] = None,
    action_id: Annotated[
        Optional[str],
        typer.Option("--action", help="Filter by action ID"),
    ] = None,
    actor: Annotated[
        Optional[str],
        typer.Option("--actor", help="Filter by actor"),
    ] = None,
    search: Annotated[
        Optional[str],
        typer.Option("--search", "-q", help="Full-text search"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum events to show"),
    ] = 50,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List audit events with filtering."""
    audit = get_audit_trail()
    
    # Build query
    query = AuditQuery(
        start_time=datetime.now(timezone.utc) - timedelta(hours=hours),
        limit=limit,
        search_text=search,
    )
    
    if event_type:
        try:
            query.event_types = [AuditEventType(event_type)]
        except ValueError:
            console.print(f"[red]Invalid event type: {event_type}[/red]")
            console.print(f"Valid types: {', '.join(e.value for e in AuditEventType)}")
            raise typer.Exit(1)
    
    if severity:
        try:
            query.severities = [AuditSeverity(severity.lower())]
        except ValueError:
            console.print(f"[red]Invalid severity: {severity}[/red]")
            raise typer.Exit(1)
    
    if alert_id:
        try:
            query.alert_id = UUID(alert_id)
        except ValueError:
            console.print(f"[red]Invalid alert ID: {alert_id}[/red]")
            raise typer.Exit(1)
    
    if action_id:
        try:
            query.action_id = UUID(action_id)
        except ValueError:
            console.print(f"[red]Invalid action ID: {action_id}[/red]")
            raise typer.Exit(1)
    
    if actor:
        query.actor = actor
    
    result = audit.query(query)
    
    if json_output:
        output = [e.to_dict() for e in result.events]
        console.print_json(json.dumps(output, default=str))
        return
    
    if not result.events:
        console.print("[dim]No audit events found matching criteria[/dim]")
        return
    
    table = Table(
        title=f"📋 Audit Trail (last {hours}h)",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("Time", style="dim", width=10)
    table.add_column("Event", width=25)
    table.add_column("Summary")
    table.add_column("Confidence", width=10)
    table.add_column("Actor", style="dim", width=12)
    
    for event in result.events:
        event_text = Text(event.event_type.value)
        event_text.stylize(_get_event_type_style(event.event_type))
        
        severity_prefix = ""
        if event.severity != AuditSeverity.INFO:
            severity_prefix = f"[{_get_severity_style(event.severity)}]{event.severity.value.upper()}[/] "
        
        confidence = ""
        if event.confidence_score is not None:
            confidence = f"{event.confidence_score:.0f}%"
        
        table.add_row(
            _format_time(event.timestamp),
            event_text,
            f"{severity_prefix}{event.summary[:50]}{'...' if len(event.summary) > 50 else ''}",
            confidence,
            event.actor,
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {len(result.events)} of {result.total_count} events[/dim]")


@app.command("show")
def show_event(
    event_id: Annotated[str, typer.Argument(help="Event ID to show")],
) -> None:
    """Show detailed information about an audit event."""
    audit = get_audit_trail()
    
    result = audit.query(AuditQuery(limit=1000))
    
    event = None
    for e in result.events:
        if str(e.id).startswith(event_id) or str(e.id) == event_id:
            event = e
            break
    
    if not event:
        console.print(f"[red]Event not found: {event_id}[/red]")
        raise typer.Exit(1)
    
    content = f"""[bold]Event Type:[/bold] {event.event_type.value}
[bold]ID:[/bold] {event.id}
[bold]Timestamp:[/bold] {event.timestamp.isoformat()}
[bold]Severity:[/bold] [{_get_severity_style(event.severity)}]{event.severity.value.upper()}[/]

[bold]Summary:[/bold]
{event.summary}

[bold]Actor:[/bold] {event.actor} ({event.actor_type})
"""
    
    if event.alert_id:
        content += f"[bold]Alert ID:[/bold] {event.alert_id}\n"
    
    if event.investigation_id:
        content += f"[bold]Investigation ID:[/bold] {event.investigation_id}\n"
    
    if event.action_id:
        content += f"[bold]Action ID:[/bold] {event.action_id}\n"
    
    if event.confidence_score is not None:
        content += f"\n[bold]Confidence:[/bold] {event.confidence_score:.1f}%"
        if event.confidence_level:
            content += f" ({event.confidence_level})"
        content += "\n"
    
    if event.reasoning:
        content += f"\n[bold]Reasoning:[/bold]\n{event.reasoning}\n"
    
    if event.model_used:
        content += f"\n[bold]Model Used:[/bold] {event.model_used}\n"
    
    if event.details:
        content += "\n[bold]Details:[/bold]\n"
        content += json.dumps(event.details, indent=2, default=str)
        content += "\n"
    
    if event.evidence:
        content += f"\n[bold]Evidence ({len(event.evidence)} items):[/bold]\n"
        for ev in event.evidence[:5]:
            content += f"  • {ev.get('type', 'unknown')}: {ev.get('summary', 'N/A')}\n"
    
    panel = Panel(
        content,
        title=f"📋 Audit Event: {str(event.id)[:8]}",
        border_style=_get_severity_style(event.severity),
    )
    console.print(panel)


@app.command("timeline")
def alert_timeline(
    alert_id: Annotated[str, typer.Argument(help="Alert ID to show timeline for")],
) -> None:
    """Show complete timeline for an alert."""
    audit = get_audit_trail()
    
    try:
        uuid = UUID(alert_id)
    except ValueError:
        console.print(f"[red]Invalid alert ID: {alert_id}[/red]")
        raise typer.Exit(1)
    
    events = audit.get_alert_timeline(uuid)
    
    if not events:
        console.print(f"[dim]No events found for alert {alert_id}[/dim]")
        return
    
    console.print(Panel(f"📋 Timeline for Alert {alert_id[:8]}", style="cyan"))
    
    for i, event in enumerate(events):
        prefix = "├─" if i < len(events) - 1 else "└─"
        
        event_text = Text(event.event_type.value)
        event_text.stylize(_get_event_type_style(event.event_type))
        
        time_str = event.timestamp.strftime("%H:%M:%S")
        
        console.print(f"  {prefix} [{time_str}] {event_text}: {event.summary}")
        
        if event.confidence_score is not None:
            console.print(f"  │     Confidence: {event.confidence_score:.0f}%")
        
        if event.reasoning:
            reasoning_short = event.reasoning[:100] + "..." if len(event.reasoning) > 100 else event.reasoning
            console.print(f"  │     Reasoning: {reasoning_short}")


@app.command("decisions")
def recent_decisions(
    hours: Annotated[
        int,
        typer.Option("--hours", "-H", help="Show decisions from last N hours"),
    ] = 24,
) -> None:
    """Show recent AI decisions with confidence scores."""
    audit = get_audit_trail()
    
    events = audit.get_recent_decisions(hours=hours)
    
    if not events:
        console.print("[dim]No AI decisions found[/dim]")
        return
    
    table = Table(
        title=f"🤖 AI Decisions (last {hours}h)",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("Time", style="dim")
    table.add_column("Decision")
    table.add_column("Confidence")
    table.add_column("Level")
    table.add_column("Model", style="dim")
    
    for event in events:
        confidence = f"{event.confidence_score:.0f}%" if event.confidence_score else "-"
        
        conf_style = "white"
        if event.confidence_score:
            if event.confidence_score >= 80:
                conf_style = "green"
            elif event.confidence_score >= 60:
                conf_style = "yellow"
            else:
                conf_style = "red"
        
        table.add_row(
            _format_time(event.timestamp),
            event.summary[:40] + "..." if len(event.summary) > 40 else event.summary,
            f"[{conf_style}]{confidence}[/]",
            event.confidence_level or "-",
            event.model_used or "-",
        )
    
    console.print(table)


@app.command("approvals")
def approval_history(
    hours: Annotated[
        int,
        typer.Option("--hours", "-H", help="Show approvals from last N hours"),
    ] = 24,
) -> None:
    """Show approval history."""
    audit = get_audit_trail()
    
    events = audit.get_approval_history(hours=hours)
    
    if not events:
        console.print("[dim]No approval events found[/dim]")
        return
    
    table = Table(
        title=f"🔐 Approval History (last {hours}h)",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("Time", style="dim")
    table.add_column("Event")
    table.add_column("Summary")
    table.add_column("Actor")
    
    for event in events:
        event_style = {
            AuditEventType.APPROVAL_REQUESTED: "yellow",
            AuditEventType.APPROVAL_GRANTED: "green",
            AuditEventType.APPROVAL_DENIED: "red",
            AuditEventType.APPROVAL_EXPIRED: "dim",
        }.get(event.event_type, "white")
        
        table.add_row(
            _format_time(event.timestamp),
            f"[{event_style}]{event.event_type.value}[/]",
            event.summary[:50] + "..." if len(event.summary) > 50 else event.summary,
            event.actor,
        )
    
    console.print(table)


@app.command("stats")
def show_stats() -> None:
    """Show audit trail statistics."""
    audit = get_audit_trail()
    stats = audit.get_stats()
    
    table = Table(title="📊 Audit Statistics", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    
    table.add_row("Total Events", str(stats["total_events"]))
    table.add_row("Database Path", stats["db_path"])
    
    if stats["oldest_event"]:
        table.add_row("Oldest Event", stats["oldest_event"])
    if stats["newest_event"]:
        table.add_row("Newest Event", stats["newest_event"])
    
    if stats["average_confidence"]:
        table.add_row("Avg Confidence", f"{stats['average_confidence']:.1f}%")
    
    console.print(table)
    
    if stats["by_type"]:
        console.print("\n[bold]Events by Type:[/bold]")
        for event_type, count in sorted(stats["by_type"].items(), key=lambda x: x[1], reverse=True)[:10]:
            console.print(f"  {event_type}: {count}")
    
    if stats["by_severity"]:
        console.print("\n[bold]Events by Severity:[/bold]")
        for severity, count in stats["by_severity"].items():
            style = _get_severity_style(AuditSeverity(severity))
            console.print(f"  [{style}]{severity}[/]: {count}")


@app.command("export")
def export_audit(
    output: Annotated[
        Path,
        typer.Argument(help="Output file path"),
    ],
    hours: Annotated[
        int,
        typer.Option("--hours", "-H", help="Export events from last N hours"),
    ] = 168,  # 1 week
) -> None:
    """Export audit trail to JSON."""
    audit = get_audit_trail()
    
    query = AuditQuery(
        start_time=datetime.now(timezone.utc) - timedelta(hours=hours),
        limit=10000,
    )
    
    count = audit.export_json(output, query)
    
    console.print(f"[green]✓ Exported {count} events to {output}[/green]")


@app.command("cleanup")
def cleanup_old(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Delete events older than N days"),
    ] = 90,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be deleted"),
    ] = False,
) -> None:
    """Clean up old audit events."""
    audit = get_audit_trail()
    
    if dry_run:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = audit.query(AuditQuery(end_time=cutoff, limit=1))
        console.print(f"Would delete approximately {result.total_count} events older than {days} days")
        return
    
    confirm = typer.confirm(f"Delete audit events older than {days} days?")
    if not confirm:
        console.print("[dim]Cancelled[/dim]")
        return
    
    deleted = audit.cleanup_old(days)
    console.print(f"[green]✓ Deleted {deleted} old events[/green]")
