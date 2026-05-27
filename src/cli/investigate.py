"""Investigation commands for AutoSRE CLI."""

import click

from .client import AutoSREClient
from .utils import (
    OutputFormatter,
    console,
    create_table,
    format_timestamp,
    get_formatter,
    print_investigation_panel,
    prompt_choice,
    prompt_input,
    severity_style,
    spinner,
    status_icon,
    status_style,
)


@click.group(invoke_without_command=True)
@click.argument("description", required=False)
@click.option("--service", "-s", help="Service to investigate")
@click.option(
    "--severity",
    "-S",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="medium",
    help="Investigation severity",
)
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--stream/--no-stream", default=True, help="Stream progress updates")
@click.option("--context", "-c", multiple=True, help="Additional context (key=value)")
@click.pass_context
def investigate(
    ctx: click.Context,
    description: str | None,
    service: str | None,
    severity: str,
    interactive: bool,
    stream: bool,
    context: tuple[str, ...],
):
    """Start an investigation.
    
    Examples:
        autosre investigate "checkout 500 errors" --service checkout-service
        autosre investigate --interactive
        autosre investigate "high latency" -s api-gateway -S high
    """
    # If subcommand invoked, let it handle
    if ctx.invoked_subcommand is not None:
        return
    
    formatter = get_formatter(ctx)
    
    # Interactive mode
    if interactive or description is None:
        description = prompt_input("Describe the issue")
        service = prompt_input("Service name (optional)", default="") or None
        severity = prompt_choice(
            "Severity",
            ["low", "medium", "high", "critical"],
            default="medium",
        )
    
    if not description:
        formatter.print_error("Description is required")
        ctx.exit(1)
    
    # Parse context key=value pairs
    ctx_dict = {}
    for item in context:
        if "=" in item:
            key, value = item.split("=", 1)
            ctx_dict[key] = value
    
    # Create investigation
    try:
        with AutoSREClient() as client:
            with spinner("Creating investigation...", formatter.json_mode):
                result = client.create_investigation(
                    description=description,
                    service=service,
                    severity=severity,
                    context=ctx_dict if ctx_dict else None,
                )
            
            investigation_id = result.get("id", result.get("investigation_id"))
            
            if formatter.json_mode:
                formatter.print_json(result)
                return
            
            formatter.print_success(f"Investigation created: {investigation_id}")
            
            print_investigation_panel(
                investigation_id=investigation_id,
                title=description[:50] + "..." if len(description) > 50 else description,
                status=result.get("status", "pending"),
                severity=severity,
                service=service,
            )
            
            # Stream progress if enabled
            if stream and result.get("status") in ("pending", "running"):
                console.print("\n[dim]Streaming investigation progress...[/dim]\n")
                _stream_investigation_progress(client, investigation_id, formatter)
    
    except Exception as e:
        formatter.print_error(f"Failed to create investigation: {e}")
        ctx.exit(1)


@investigate.command("status")
@click.argument("investigation_id")
@click.pass_context
def investigation_status(ctx: click.Context, investigation_id: str):
    """Check the status of an investigation.
    
    Example:
        autosre investigate status inv_abc123
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner(f"Fetching investigation {investigation_id}...", formatter.json_mode):
                result = client.get_investigation(investigation_id)
            
            if formatter.json_mode:
                formatter.print_json(result)
                return
            
            print_investigation_panel(
                investigation_id=investigation_id,
                title=result.get("description", "Investigation"),
                status=result.get("status", "unknown"),
                severity=result.get("severity", "unknown"),
                service=result.get("service"),
            )
            
            # Show findings if available
            findings = result.get("findings", [])
            if findings:
                console.print("\n[bold]Findings:[/bold]")
                for i, finding in enumerate(findings, 1):
                    console.print(f"  {i}. {finding}")
            
            # Show root cause if available
            root_cause = result.get("root_cause")
            if root_cause:
                console.print(f"\n[bold]Root Cause:[/bold] {root_cause}")
            
            # Show recommendations if available
            recommendations = result.get("recommendations", [])
            if recommendations:
                console.print("\n[bold]Recommendations:[/bold]")
                for i, rec in enumerate(recommendations, 1):
                    console.print(f"  {i}. {rec}")
    
    except Exception as e:
        formatter.print_error(f"Failed to get investigation status: {e}")
        ctx.exit(1)


@investigate.command("list")
@click.option("--limit", "-n", default=10, help="Number of investigations to show")
@click.option("--status", "-s", help="Filter by status")
@click.option("--service", help="Filter by service")
@click.pass_context
def list_investigations(
    ctx: click.Context,
    limit: int,
    status: str | None,
    service: str | None,
):
    """List recent investigations.
    
    Examples:
        autosre investigate list
        autosre investigate list --status running
        autosre investigate list --service checkout-service -n 20
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner("Fetching investigations...", formatter.json_mode):
                results = client.list_investigations(
                    limit=limit,
                    status=status,
                    service=service,
                )
            
            if formatter.json_mode:
                formatter.print_json(results)
                return
            
            if not results:
                formatter.print_info("No investigations found")
                return
            
            table = create_table(
                "Recent Investigations",
                [
                    ("ID", "cyan"),
                    ("Description", "white"),
                    ("Status", "white"),
                    ("Severity", "white"),
                    ("Service", "dim"),
                    ("Created", "dim"),
                ],
            )
            
            for inv in results:
                inv_status = inv.get("status", "unknown")
                inv_severity = inv.get("severity", "unknown")
                description = inv.get("description", "")
                if len(description) > 40:
                    description = description[:37] + "..."
                
                table.add_row(
                    inv.get("id", "N/A"),
                    description,
                    f"{status_icon(inv_status)} {inv_status}",
                    f"[{severity_style(inv_severity)}]{inv_severity}[/]",
                    inv.get("service", "N/A"),
                    format_timestamp(inv.get("created_at")),
                )
            
            console.print(table)
    
    except Exception as e:
        formatter.print_error(f"Failed to list investigations: {e}")
        ctx.exit(1)


def _stream_investigation_progress(
    client: AutoSREClient,
    investigation_id: str,
    formatter: OutputFormatter,
) -> None:
    """Stream and display investigation progress."""
    try:
        for event in client.stream_investigation(investigation_id):
            event_type = event.get("event", "message")
            data = event.get("data", {})
            
            if formatter.json_mode:
                formatter.print_json(event)
                continue
            
            if event_type == "step":
                step_name = data.get("name", "Processing")
                step_status = data.get("status", "running")
                icon = status_icon(step_status)
                style = status_style(step_status)
                console.print(f"  [{style}]{icon}[/] {step_name}")
            
            elif event_type == "finding":
                finding = data.get("finding", data)
                console.print(f"  [yellow]→[/yellow] Finding: {finding}")
            
            elif event_type == "hypothesis":
                hypothesis = data.get("hypothesis", data)
                console.print(f"  [blue]?[/blue] Hypothesis: {hypothesis}")
            
            elif event_type == "action":
                action = data.get("action", data)
                console.print(f"  [cyan]⚡[/cyan] Action: {action}")
            
            elif event_type == "complete":
                console.print("\n[green]✓ Investigation complete[/green]")
                root_cause = data.get("root_cause")
                if root_cause:
                    console.print(f"\n[bold]Root Cause:[/bold] {root_cause}")
                break
            
            elif event_type == "error":
                error = data.get("error", data)
                console.print(f"\n[red]✗ Error: {error}[/red]")
                break
    
    except KeyboardInterrupt:
        console.print("\n[dim]Streaming stopped[/dim]")
    except Exception as e:
        console.print(f"\n[red]Stream error: {e}[/red]")


# Alias commands at module level for direct invocation
status = investigation_status
list_cmd = list_investigations
