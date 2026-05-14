"""AutoSRE CLI - Runbook management commands."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID, uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="runbook",
    help="Manage and execute runbooks",
    no_args_is_help=True,
)

console = Console()


def _get_status_color(status: str) -> str:
    """Get color for runbook status."""
    colors = {
        "ready": "green",
        "running": "cyan",
        "completed": "green",
        "failed": "red",
        "draft": "yellow",
        "deprecated": "dim",
    }
    return colors.get(status, "white")


def _get_mock_runbooks() -> list[dict]:
    """Get mock runbooks for demo purposes."""
    return [
        {
            "id": "high-cpu",
            "name": "High CPU Investigation",
            "description": "Investigate and remediate high CPU usage",
            "version": "1.2.0",
            "status": "ready",
            "author": "platform-team",
            "tags": ["cpu", "performance", "kubernetes"],
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-03-20T14:30:00Z",
            "steps": [
                {"name": "Check CPU metrics", "action": "prometheus_query", "params": {"query": "process_cpu_seconds_total"}},
                {"name": "Get top processes", "action": "exec", "params": {"command": "top -bn1 | head -20"}},
                {"name": "Check for throttling", "action": "kubernetes", "params": {"resource": "pods", "field": "status.containerStatuses"}},
                {"name": "Scale if needed", "action": "kubernetes_scale", "params": {"min_replicas": 3, "max_replicas": 10}},
            ],
        },
        {
            "id": "pod-restart",
            "name": "Pod Crash Loop Debug",
            "description": "Debug and fix crash looping pods",
            "version": "2.0.0",
            "status": "ready",
            "author": "sre-team",
            "tags": ["kubernetes", "pods", "crashloop"],
            "created_at": "2024-02-01T09:00:00Z",
            "updated_at": "2024-04-10T11:00:00Z",
            "steps": [
                {"name": "Get pod events", "action": "kubernetes", "params": {"resource": "events"}},
                {"name": "Check pod logs", "action": "kubernetes_logs", "params": {"tail": 100}},
                {"name": "Describe pod", "action": "kubernetes", "params": {"resource": "pod", "verb": "describe"}},
                {"name": "Check resource limits", "action": "kubernetes", "params": {"resource": "pod", "field": "spec.containers"}},
            ],
        },
        {
            "id": "disk-space",
            "name": "Disk Space Cleanup",
            "description": "Clean up disk space on nodes",
            "version": "1.0.0",
            "status": "ready",
            "author": "platform-team",
            "tags": ["disk", "storage", "cleanup"],
            "created_at": "2024-03-01T12:00:00Z",
            "updated_at": "2024-03-15T16:00:00Z",
            "steps": [
                {"name": "Check disk usage", "action": "exec", "params": {"command": "df -h"}},
                {"name": "Find large files", "action": "exec", "params": {"command": "find /var -size +100M"}},
                {"name": "Clean docker", "action": "exec", "params": {"command": "docker system prune -f"}},
                {"name": "Clean old logs", "action": "exec", "params": {"command": "find /var/log -mtime +7 -delete"}},
            ],
        },
        {
            "id": "db-connection",
            "name": "Database Connection Issues",
            "description": "Diagnose database connection problems",
            "version": "1.1.0",
            "status": "draft",
            "author": "dba-team",
            "tags": ["database", "postgresql", "connections"],
            "created_at": "2024-04-01T08:00:00Z",
            "updated_at": "2024-04-05T10:00:00Z",
            "steps": [
                {"name": "Check connection count", "action": "sql_query", "params": {"query": "SELECT count(*) FROM pg_stat_activity"}},
                {"name": "Find blocked queries", "action": "sql_query", "params": {"query": "SELECT * FROM pg_stat_activity WHERE wait_event IS NOT NULL"}},
                {"name": "Check replication lag", "action": "sql_query", "params": {"query": "SELECT pg_last_wal_replay_lsn()"}},
            ],
        },
    ]


@app.command("list")
def list_runbooks(
    tag: Annotated[
        Optional[str],
        typer.Option("--tag", "-t", help="Filter by tag"),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List available runbooks."""
    runbooks = _get_mock_runbooks()
    
    # Apply filters
    if tag:
        runbooks = [r for r in runbooks if tag.lower() in [t.lower() for t in r["tags"]]]
    
    if status:
        runbooks = [r for r in runbooks if r["status"].lower() == status.lower()]
    
    if json_output:
        console.print_json(json.dumps(runbooks))
        return
    
    if not runbooks:
        console.print("[dim]No runbooks found matching criteria[/dim]")
        return
    
    table = Table(
        title="📖 Available Runbooks",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Version", style="dim")
    table.add_column("Status")
    table.add_column("Steps", justify="right")
    table.add_column("Tags", style="dim")
    
    for rb in runbooks:
        status_text = Text(rb["status"])
        status_text.stylize(_get_status_color(rb["status"]))
        
        tags = ", ".join(rb["tags"][:3])
        if len(rb["tags"]) > 3:
            tags += f" (+{len(rb['tags']) - 3})"
        
        table.add_row(
            rb["id"],
            rb["name"],
            rb["version"],
            status_text,
            str(len(rb["steps"])),
            tags,
        )
    
    console.print(table)
    console.print(f"\n[dim]Use 'autosre runbook get <id>' for details[/dim]")


@app.command("get")
def get_runbook(
    runbook_id: Annotated[str, typer.Argument(help="Runbook ID")],
    show_steps: Annotated[
        bool,
        typer.Option("--steps", "-s", help="Show detailed steps"),
    ] = True,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Get detailed information about a runbook."""
    runbooks = _get_mock_runbooks()
    
    # Find runbook
    runbook = None
    for rb in runbooks:
        if rb["id"] == runbook_id:
            runbook = rb
            break
    
    if not runbook:
        console.print(f"[red]Runbook not found: {runbook_id}[/red]")
        raise typer.Exit(1)
    
    if json_output:
        console.print_json(json.dumps(runbook))
        return
    
    status_text = Text(runbook["status"])
    status_text.stylize(_get_status_color(runbook["status"]))
    
    content = f"""[bold]Name:[/bold] {runbook['name']}
[bold]ID:[/bold] {runbook['id']}
[bold]Version:[/bold] {runbook['version']}
[bold]Status:[/bold] {status_text}

[bold]Description:[/bold]
{runbook['description']}

[bold]Author:[/bold] {runbook['author']}
[bold]Tags:[/bold] {', '.join(runbook['tags'])}

[bold]Created:[/bold] {runbook['created_at'][:10]}
[bold]Updated:[/bold] {runbook['updated_at'][:10]}"""
    
    console.print(Panel(
        content,
        title=f"📖 Runbook: {runbook['name']}",
        border_style="cyan",
    ))
    
    if show_steps and runbook.get("steps"):
        console.print("\n[bold]Steps:[/bold]")
        for i, step in enumerate(runbook["steps"], 1):
            console.print(f"\n  [cyan]{i}.[/cyan] [bold]{step['name']}[/bold]")
            console.print(f"      Action: [dim]{step['action']}[/dim]")
            if step.get("params"):
                for key, value in step["params"].items():
                    console.print(f"      {key}: [dim]{value}[/dim]")


@app.command("run")
def run_runbook(
    runbook_id: Annotated[str, typer.Argument(help="Runbook ID to run")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Simulate without executing"),
    ] = False,
    target: Annotated[
        Optional[str],
        typer.Option("--target", "-t", help="Target service/resource"),
    ] = None,
    params: Annotated[
        Optional[str],
        typer.Option("--params", "-p", help="JSON parameters to pass"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Execute a runbook."""
    runbooks = _get_mock_runbooks()
    
    # Find runbook
    runbook = None
    for rb in runbooks:
        if rb["id"] == runbook_id:
            runbook = rb
            break
    
    if not runbook:
        console.print(f"[red]Runbook not found: {runbook_id}[/red]")
        raise typer.Exit(1)
    
    if runbook["status"] == "draft":
        console.print(f"[yellow]Warning: Runbook '{runbook_id}' is in draft status[/yellow]")
        if not dry_run:
            confirm = typer.confirm("Continue anyway?")
            if not confirm:
                raise typer.Exit(0)
    
    # Parse parameters
    extra_params = {}
    if params:
        try:
            extra_params = json.loads(params)
        except json.JSONDecodeError:
            console.print(f"[red]Invalid JSON parameters: {params}[/red]")
            raise typer.Exit(1)
    
    execution_id = str(uuid4())[:8]
    
    if json_output:
        results = {
            "execution_id": execution_id,
            "runbook_id": runbook_id,
            "dry_run": dry_run,
            "target": target,
            "params": extra_params,
            "status": "completed" if dry_run else "running",
            "steps": [],
        }
        
        for i, step in enumerate(runbook["steps"]):
            results["steps"].append({
                "index": i + 1,
                "name": step["name"],
                "action": step["action"],
                "status": "simulated" if dry_run else "pending",
            })
        
        console.print_json(json.dumps(results))
        return
    
    mode_text = "[cyan]DRY RUN[/cyan]" if dry_run else "[yellow]EXECUTING[/yellow]"
    console.print(Panel(
        f"""[bold]Runbook:[/bold] {runbook['name']}
[bold]Execution ID:[/bold] {execution_id}
[bold]Mode:[/bold] {mode_text}
[bold]Target:[/bold] {target or 'default'}""",
        title="🚀 Runbook Execution",
        border_style="cyan",
    ))
    
    # Execute steps with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing runbook...", total=len(runbook["steps"]))
        
        for i, step in enumerate(runbook["steps"]):
            progress.update(task, description=f"Step {i+1}: {step['name']}")
            
            # Simulate execution time
            import time
            time.sleep(0.5 if dry_run else 1.0)
            
            if dry_run:
                console.print(f"  [dim]→[/dim] [cyan]SIMULATED[/cyan] {step['name']}")
            else:
                console.print(f"  [dim]→[/dim] [green]COMPLETED[/green] {step['name']}")
            
            progress.advance(task)
    
    console.print(f"\n[green]✓[/green] Runbook execution {'simulated' if dry_run else 'completed'}")
    console.print(f"[dim]Execution ID: {execution_id}[/dim]")


@app.command("create")
def create_runbook(
    file: Annotated[Path, typer.Argument(help="YAML file with runbook definition")],
    validate_only: Annotated[
        bool,
        typer.Option("--validate", "-v", help="Only validate, don't create"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Create a new runbook from a YAML file."""
    import yaml
    
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    
    try:
        with open(file) as f:
            runbook_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        console.print(f"[red]Invalid YAML: {e}[/red]")
        raise typer.Exit(1)
    
    # Validate required fields
    errors = []
    required_fields = ["id", "name", "description", "steps"]
    
    for field in required_fields:
        if field not in runbook_data:
            errors.append(f"Missing required field: {field}")
    
    if "steps" in runbook_data:
        for i, step in enumerate(runbook_data["steps"]):
            if "name" not in step:
                errors.append(f"Step {i+1}: missing 'name'")
            if "action" not in step:
                errors.append(f"Step {i+1}: missing 'action'")
    
    if errors:
        if json_output:
            console.print_json(json.dumps({"valid": False, "errors": errors}))
        else:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  • {error}")
        raise typer.Exit(1)
    
    if validate_only:
        if json_output:
            console.print_json(json.dumps({"valid": True, "runbook": runbook_data}))
        else:
            console.print(f"[green]✓[/green] Runbook '{runbook_data['id']}' is valid")
        return
    
    # TODO: Actually save to runbook store
    runbook_data["status"] = "draft"
    runbook_data["version"] = runbook_data.get("version", "1.0.0")
    runbook_data["created_at"] = datetime.utcnow().isoformat()
    runbook_data["updated_at"] = datetime.utcnow().isoformat()
    
    if json_output:
        console.print_json(json.dumps({"success": True, "runbook": runbook_data}))
    else:
        console.print(f"[green]✓[/green] Created runbook '[bold]{runbook_data['id']}[/bold]'")
        console.print(f"[dim]Status: draft (use 'autosre runbook publish {runbook_data['id']}' to activate)[/dim]")


@app.command("validate")
def validate_runbook(
    file: Annotated[Path, typer.Argument(help="YAML file to validate")],
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Validate a runbook YAML file."""
    # Delegate to create with validate_only=True
    create_runbook(file, validate_only=True, json_output=json_output)


@app.command("template")
def show_template(
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write template to file"),
    ] = None,
) -> None:
    """Show a runbook template."""
    template = """# AutoSRE Runbook Template
id: my-runbook
name: My Runbook
description: |
  Description of what this runbook does and when to use it.

version: 1.0.0
author: your-team
tags:
  - category
  - relevant-tag

# Variables that can be passed at runtime
variables:
  service_name:
    description: Name of the service to investigate
    required: true
  threshold:
    description: Alert threshold percentage
    default: 80

# Runbook steps
steps:
  - name: Check service metrics
    description: Query Prometheus for service metrics
    action: prometheus_query
    params:
      query: "up{service='{{ service_name }}'}"
    
  - name: Get recent logs
    description: Fetch recent error logs
    action: elasticsearch_query
    params:
      index: "logs-*"
      query: "service:{{ service_name }} AND level:ERROR"
      limit: 100
    
  - name: Scale if needed
    description: Scale up the service
    action: kubernetes_scale
    params:
      deployment: "{{ service_name }}"
      replicas: 3
    requires_approval: true
    
  - name: Notify team
    description: Send notification
    action: slack_message
    params:
      channel: "#sre-alerts"
      message: "Runbook executed for {{ service_name }}"
"""
    
    if output:
        with open(output, "w") as f:
            f.write(template)
        console.print(f"[green]✓[/green] Template written to {output}")
    else:
        console.print(Syntax(template, "yaml", theme="monokai", line_numbers=True))
