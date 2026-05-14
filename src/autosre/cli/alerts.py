"""AutoSRE CLI - Alerts management commands."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autosre.core.models import Alert, AlertSeverity, AlertStatus

app = typer.Typer(
    name="alerts",
    help="Manage and investigate alerts",
    no_args_is_help=True,
)

console = Console()


def _get_severity_color(severity: AlertSeverity) -> str:
    """Get color for severity level."""
    colors = {
        AlertSeverity.CRITICAL: "bold red",
        AlertSeverity.HIGH: "red",
        AlertSeverity.MEDIUM: "yellow",
        AlertSeverity.LOW: "cyan",
        AlertSeverity.INFO: "dim",
    }
    return colors.get(severity, "white")


def _get_status_color(status: AlertStatus) -> str:
    """Get color for status."""
    colors = {
        AlertStatus.FIRING: "red",
        AlertStatus.RESOLVED: "green",
        AlertStatus.ACKNOWLEDGED: "yellow",
        AlertStatus.SILENCED: "dim",
    }
    return colors.get(status, "white")


def _format_duration(started_at: datetime) -> str:
    """Format duration since alert started."""
    delta = datetime.utcnow() - started_at
    total_seconds = int(delta.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = total_seconds // 86400
        return f"{days}d"


def _get_mock_alerts() -> list[Alert]:
    """Get mock alerts for demo purposes."""
    # TODO: Replace with actual alert store/API
    return [
        Alert(
            id=UUID("12345678-1234-1234-1234-123456789001"),
            name="HighCPUUsage",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.FIRING,
            source="prometheus",
            service="api-gateway",
            namespace="production",
            description="CPU usage above 90% for 5 minutes",
            labels={"team": "platform", "env": "prod"},
        ),
        Alert(
            id=UUID("12345678-1234-1234-1234-123456789002"),
            name="HighMemoryUsage",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACKNOWLEDGED,
            source="prometheus",
            service="user-service",
            namespace="production",
            description="Memory usage above 85%",
            labels={"team": "backend", "env": "prod"},
        ),
        Alert(
            id=UUID("12345678-1234-1234-1234-123456789003"),
            name="PodCrashLooping",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.FIRING,
            source="kubernetes",
            service="payment-service",
            namespace="production",
            description="Pod has restarted 5 times in the last hour",
            labels={"team": "payments", "env": "prod"},
        ),
    ]


@app.command("list")
def list_alerts(
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status (firing, resolved, acknowledged, silenced)"),
    ] = None,
    severity: Annotated[
        Optional[str],
        typer.Option("--severity", "-S", help="Filter by severity (critical, high, medium, low, info)"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of alerts to show"),
    ] = 50,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List alerts with optional filtering."""
    alerts = _get_mock_alerts()
    
    # Apply filters
    if status:
        try:
            status_enum = AlertStatus(status.lower())
            alerts = [a for a in alerts if a.status == status_enum]
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            raise typer.Exit(1)
    
    if severity:
        try:
            severity_enum = AlertSeverity(severity.lower())
            alerts = [a for a in alerts if a.severity == severity_enum]
        except ValueError:
            console.print(f"[red]Invalid severity: {severity}[/red]")
            raise typer.Exit(1)
    
    # Apply limit
    alerts = alerts[:limit]
    
    if json_output:
        output = [a.model_dump(mode="json") for a in alerts]
        console.print_json(json.dumps(output, default=str))
        return
    
    if not alerts:
        console.print("[dim]No alerts found matching criteria[/dim]")
        return
    
    # Create table
    table = Table(
        title="🚨 Active Alerts",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("ID", style="dim", width=8)
    table.add_column("Name", style="bold")
    table.add_column("Severity")
    table.add_column("Status")
    table.add_column("Service")
    table.add_column("Age")
    table.add_column("Source", style="dim")
    
    for alert in alerts:
        severity_text = Text(alert.severity.value.upper())
        severity_text.stylize(_get_severity_color(alert.severity))
        
        status_text = Text(alert.status.value)
        status_text.stylize(_get_status_color(alert.status))
        
        table.add_row(
            str(alert.id)[:8],
            alert.name,
            severity_text,
            status_text,
            alert.service or "-",
            _format_duration(alert.started_at),
            alert.source,
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {len(alerts)} alert(s)[/dim]")


@app.command("get")
def get_alert(
    alert_id: Annotated[str, typer.Argument(help="Alert ID (full or partial)")],
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Get detailed information about a specific alert."""
    alerts = _get_mock_alerts()
    
    # Find matching alert
    alert = None
    for a in alerts:
        if str(a.id).startswith(alert_id) or str(a.id) == alert_id:
            alert = a
            break
    
    if not alert:
        console.print(f"[red]Alert not found: {alert_id}[/red]")
        raise typer.Exit(1)
    
    if json_output:
        console.print_json(alert.model_dump_json())
        return
    
    # Display detailed view
    severity_text = Text(alert.severity.value.upper())
    severity_text.stylize(_get_severity_color(alert.severity))
    
    status_text = Text(alert.status.value)
    status_text.stylize(_get_status_color(alert.status))
    
    content = f"""[bold]Name:[/bold] {alert.name}
[bold]ID:[/bold] {alert.id}
[bold]Severity:[/bold] {severity_text}
[bold]Status:[/bold] {status_text}

[bold]Source:[/bold] {alert.source}
[bold]Service:[/bold] {alert.service or 'N/A'}
[bold]Namespace:[/bold] {alert.namespace or 'N/A'}
[bold]Cluster:[/bold] {alert.cluster or 'N/A'}

[bold]Description:[/bold]
{alert.description or 'No description'}

[bold]Started:[/bold] {alert.started_at.isoformat()}
[bold]Duration:[/bold] {_format_duration(alert.started_at)}

[bold]Labels:[/bold]"""
    
    panel = Panel(
        content,
        title=f"🚨 Alert: {alert.name}",
        border_style=_get_severity_color(alert.severity).replace("bold ", ""),
    )
    console.print(panel)
    
    if alert.labels:
        for key, value in alert.labels.items():
            console.print(f"  [cyan]{key}[/cyan]: {value}")
    
    if alert.runbook_url:
        console.print(f"\n[bold]📖 Runbook:[/bold] {alert.runbook_url}")


@app.command("ack")
def acknowledge_alert(
    alert_id: Annotated[str, typer.Argument(help="Alert ID to acknowledge")],
    comment: Annotated[
        Optional[str],
        typer.Option("--comment", "-c", help="Optional comment"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Acknowledge an alert."""
    alerts = _get_mock_alerts()
    
    # Find matching alert
    alert = None
    for a in alerts:
        if str(a.id).startswith(alert_id) or str(a.id) == alert_id:
            alert = a
            break
    
    if not alert:
        console.print(f"[red]Alert not found: {alert_id}[/red]")
        raise typer.Exit(1)
    
    # TODO: Actually acknowledge via API
    alert.status = AlertStatus.ACKNOWLEDGED
    
    if json_output:
        result = {
            "success": True,
            "alert_id": str(alert.id),
            "new_status": alert.status.value,
            "comment": comment,
        }
        console.print_json(json.dumps(result))
        return
    
    console.print(f"[green]✓[/green] Acknowledged alert [bold]{alert.name}[/bold] ({str(alert.id)[:8]})")
    if comment:
        console.print(f"  Comment: {comment}")


@app.command("resolve")
def resolve_alert(
    alert_id: Annotated[str, typer.Argument(help="Alert ID to resolve")],
    comment: Annotated[
        Optional[str],
        typer.Option("--comment", "-c", help="Resolution comment"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Manually resolve an alert."""
    alerts = _get_mock_alerts()
    
    # Find matching alert
    alert = None
    for a in alerts:
        if str(a.id).startswith(alert_id) or str(a.id) == alert_id:
            alert = a
            break
    
    if not alert:
        console.print(f"[red]Alert not found: {alert_id}[/red]")
        raise typer.Exit(1)
    
    # TODO: Actually resolve via API
    alert.status = AlertStatus.RESOLVED
    alert.ended_at = datetime.utcnow()
    
    if json_output:
        result = {
            "success": True,
            "alert_id": str(alert.id),
            "new_status": alert.status.value,
            "resolved_at": alert.ended_at.isoformat(),
            "comment": comment,
        }
        console.print_json(json.dumps(result))
        return
    
    console.print(f"[green]✓[/green] Resolved alert [bold]{alert.name}[/bold] ({str(alert.id)[:8]})")
    if comment:
        console.print(f"  Resolution: {comment}")


@app.command("investigate")
def investigate_alert(
    alert_id: Annotated[str, typer.Argument(help="Alert ID to investigate")],
    auto_remediate: Annotated[
        bool,
        typer.Option("--auto-remediate", "-a", help="Enable automatic remediation"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Simulate investigation without taking actions"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Start an automated investigation for an alert."""
    from uuid import uuid4
    
    alerts = _get_mock_alerts()
    
    # Find matching alert
    alert = None
    for a in alerts:
        if str(a.id).startswith(alert_id) or str(a.id) == alert_id:
            alert = a
            break
    
    if not alert:
        console.print(f"[red]Alert not found: {alert_id}[/red]")
        raise typer.Exit(1)
    
    investigation_id = uuid4()
    
    if json_output:
        result = {
            "success": True,
            "alert_id": str(alert.id),
            "investigation_id": str(investigation_id),
            "auto_remediate": auto_remediate,
            "dry_run": dry_run,
            "status": "started",
        }
        console.print_json(json.dumps(result))
        return
    
    console.print(Panel(
        f"""[bold]Alert:[/bold] {alert.name}
[bold]Alert ID:[/bold] {str(alert.id)[:8]}
[bold]Investigation ID:[/bold] {str(investigation_id)[:8]}

[bold]Options:[/bold]
  Auto-remediate: {'[green]Yes[/green]' if auto_remediate else '[yellow]No[/yellow]'}
  Dry run: {'[cyan]Yes[/cyan]' if dry_run else 'No'}

[dim]Use 'autosre investigate status {str(investigation_id)[:8]}' to check progress[/dim]""",
        title="🔍 Investigation Started",
        border_style="cyan",
    ))
    
    # TODO: Actually start investigation via coordinator
    console.print("\n[dim]Investigation running in background...[/dim]")
