"""AutoSRE CLI - Approve command for human approval workflow."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autosre.core.approval_gate import (
    ApprovalState,
    HumanApprovalGate,
    get_approval_gate,
)

app = typer.Typer(
    name="approve",
    help="Human approval workflow for proposed actions",
    no_args_is_help=True,
)

console = Console()


def _get_state_style(state: ApprovalState) -> str:
    """Get style for approval state."""
    styles = {
        ApprovalState.PENDING: "yellow",
        ApprovalState.APPROVED: "green",
        ApprovalState.REJECTED: "red",
        ApprovalState.MODIFIED: "cyan",
        ApprovalState.TIMEOUT: "dim",
        ApprovalState.ESCALATED: "magenta",
        ApprovalState.EXECUTED: "bold green",
        ApprovalState.SKIPPED: "dim",
    }
    return styles.get(state, "white")


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    
    if delta.total_seconds() < 60:
        return f"{int(delta.total_seconds())}s ago"
    elif delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() / 60)}m ago"
    elif delta.total_seconds() < 86400:
        return f"{int(delta.total_seconds() / 3600)}h ago"
    else:
        return f"{int(delta.total_seconds() / 86400)}d ago"


def _format_time_remaining(dt: datetime) -> str:
    """Format time remaining."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - now
    
    if delta.total_seconds() <= 0:
        return "expired"
    elif delta.total_seconds() < 60:
        return f"{int(delta.total_seconds())}s"
    elif delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() / 60)}m"
    else:
        return f"{int(delta.total_seconds() / 3600)}h {int((delta.total_seconds() % 3600) / 60)}m"


@app.command("list")
def list_pending(
    all_: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include historical (decided) proposals"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number to show"),
    ] = 20,
) -> None:
    """List pending approval requests."""
    gate = get_approval_gate()
    
    async def _list():
        pending = await gate.get_pending()
        
        if all_:
            history = await gate.get_history(limit=limit)
            all_proposals = pending + history
        else:
            all_proposals = pending
        
        return all_proposals
    
    proposals = asyncio.run(_list())
    
    if not proposals:
        console.print("[dim]No pending approval requests[/dim]")
        return
    
    table = Table(
        title="🔐 Approval Requests",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("ID", style="dim", width=10)
    table.add_column("Action", style="bold")
    table.add_column("Target")
    table.add_column("Confidence")
    table.add_column("Risk")
    table.add_column("State")
    table.add_column("Expires/Decided")
    
    for p in proposals:
        state_text = Text(p.state.value.upper())
        state_text.stylize(_get_state_style(p.state))
        
        confidence = f"{p.confidence.score:.0f}%" if p.confidence else "-"
        
        if p.is_pending and p.expires_at:
            time_col = f"in {_format_time_remaining(p.expires_at)}"
        elif p.approved_at:
            time_col = _format_time_ago(p.approved_at)
        else:
            time_col = _format_time_ago(p.created_at)
        
        risk_style = {
            "low": "green",
            "medium": "yellow", 
            "high": "red",
            "critical": "bold red",
        }.get(p.risk_level, "white")
        
        table.add_row(
            str(p.id)[:8],
            p.action_name,
            f"{p.target_type}/{p.target_name}",
            confidence,
            f"[{risk_style}]{p.risk_level.upper()}[/{risk_style}]",
            state_text,
            time_col,
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {len(proposals)} request(s)[/dim]")


@app.command("show")
def show_proposal(
    proposal_id: Annotated[str, typer.Argument(help="Proposal ID (full or short)")],
) -> None:
    """Show detailed information about a proposal."""
    gate = get_approval_gate()
    
    async def _get():
        pending = await gate.get_pending()
        history = await gate.get_history(limit=100)
        
        for p in pending + history:
            if str(p.id).startswith(proposal_id) or str(p.id) == proposal_id:
                return p
        return None
    
    proposal = asyncio.run(_get())
    
    if not proposal:
        console.print(f"[red]Proposal not found: {proposal_id}[/red]")
        raise typer.Exit(1)
    
    state_text = Text(proposal.state.value.upper())
    state_text.stylize(_get_state_style(proposal.state))
    
    content = f"""[bold]Action:[/bold] {proposal.action_name}
[bold]ID:[/bold] {proposal.id}
[bold]State:[/bold] {state_text}

[bold]Target:[/bold] {proposal.target_type}/{proposal.target_namespace or 'default'}/{proposal.target_name}
[bold]Risk Level:[/bold] {proposal.risk_level.upper()}

[bold]Description:[/bold]
{proposal.action_description}
"""
    
    if proposal.confidence:
        content += f"""
[bold]AI Confidence:[/bold] {proposal.confidence.score:.1f}% ({proposal.confidence.level.value})

[bold]Reasoning:[/bold]
{proposal.confidence.reasoning}
"""
        
        if proposal.confidence.positive_factors:
            content += "\n[bold]Positive Factors:[/bold]\n"
            for f in proposal.confidence.positive_factors:
                content += f"  ✓ {f}\n"
        
        if proposal.confidence.negative_factors:
            content += "\n[bold]Concerns:[/bold]\n"
            for f in proposal.confidence.negative_factors:
                content += f"  ⚠ {f}\n"
    
    if proposal.alert_name:
        content += f"\n[bold]Alert:[/bold] {proposal.alert_name}"
    
    if proposal.runbook_name:
        content += f"\n[bold]Runbook:[/bold] {proposal.runbook_name}"
    
    if proposal.blast_radius_summary:
        content += f"\n[bold]Blast Radius:[/bold] {proposal.blast_radius_summary}"
    
    content += f"\n\n[bold]Created:[/bold] {proposal.created_at.isoformat()}"
    
    if proposal.approved_by:
        content += f"\n[bold]Decided by:[/bold] {proposal.approved_by}"
        if proposal.approved_at:
            content += f" at {proposal.approved_at.isoformat()}"
    
    if proposal.rejection_reason:
        content += f"\n[bold red]Rejection Reason:[/bold red] {proposal.rejection_reason}"
    
    if proposal.modification_notes:
        content += f"\n[bold cyan]Notes:[/bold cyan] {proposal.modification_notes}"
    
    panel = Panel(
        content,
        title=f"🔐 Proposal: {str(proposal.id)[:8]}",
        border_style=_get_state_style(proposal.state),
    )
    console.print(panel)
    
    if proposal.is_pending:
        console.print("\n[bold]Actions:[/bold]")
        console.print(f"  autosre approve accept {str(proposal.id)[:8]}")
        console.print(f"  autosre approve reject {str(proposal.id)[:8]} --reason 'your reason'")


@app.command("accept")
def accept_proposal(
    proposal_id: Annotated[str, typer.Argument(help="Proposal ID to approve")],
    approver: Annotated[
        str,
        typer.Option("--approver", "-u", help="Your user ID/name"),
    ] = "cli-user",
    notes: Annotated[
        Optional[str],
        typer.Option("--notes", "-n", help="Optional approval notes"),
    ] = None,
) -> None:
    """Approve a proposed action."""
    gate = get_approval_gate()
    
    async def _approve():
        return await gate.approve(proposal_id, approver, notes)
    
    success = asyncio.run(_approve())
    
    if success:
        console.print(f"[green]✓ Approved proposal {proposal_id}[/green]")
        if notes:
            console.print(f"  Notes: {notes}")
    else:
        console.print(f"[red]✗ Failed to approve proposal {proposal_id}[/red]")
        console.print("[dim]Proposal may not exist or already decided[/dim]")
        raise typer.Exit(1)


@app.command("reject")
def reject_proposal(
    proposal_id: Annotated[str, typer.Argument(help="Proposal ID to reject")],
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help="Rejection reason (required)"),
    ] = ...,
    rejector: Annotated[
        str,
        typer.Option("--rejector", "-u", help="Your user ID/name"),
    ] = "cli-user",
) -> None:
    """Reject a proposed action."""
    if not reason:
        console.print("[red]Rejection reason is required[/red]")
        raise typer.Exit(1)
    
    gate = get_approval_gate()
    
    async def _reject():
        return await gate.reject(proposal_id, rejector, reason)
    
    success = asyncio.run(_reject())
    
    if success:
        console.print(f"[yellow]✗ Rejected proposal {proposal_id}[/yellow]")
        console.print(f"  Reason: {reason}")
    else:
        console.print(f"[red]✗ Failed to reject proposal {proposal_id}[/red]")
        raise typer.Exit(1)


@app.command("modify")
def modify_proposal(
    proposal_id: Annotated[str, typer.Argument(help="Proposal ID to modify")],
    param: Annotated[
        list[str],
        typer.Option("--param", "-p", help="Parameter to modify (key=value)"),
    ] = None,
    approver: Annotated[
        str,
        typer.Option("--approver", "-u", help="Your user ID/name"),
    ] = "cli-user",
    notes: Annotated[
        Optional[str],
        typer.Option("--notes", "-n", help="Modification notes"),
    ] = None,
) -> None:
    """Modify parameters and approve a proposal."""
    if not param:
        console.print("[red]At least one --param required[/red]")
        console.print("Example: autosre approve modify abc123 --param replicas=3")
        raise typer.Exit(1)
    
    # Parse parameters
    modifications = {}
    for p in param:
        if "=" not in p:
            console.print(f"[red]Invalid parameter format: {p}[/red]")
            console.print("Use: key=value")
            raise typer.Exit(1)
        key, value = p.split("=", 1)
        # Try to parse as number
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string
        modifications[key] = value
    
    gate = get_approval_gate()
    
    async def _modify():
        return await gate.modify_and_approve(proposal_id, approver, modifications, notes)
    
    success = asyncio.run(_modify())
    
    if success:
        console.print(f"[cyan]✓ Modified and approved proposal {proposal_id}[/cyan]")
        console.print(f"  Modifications: {modifications}")
    else:
        console.print(f"[red]✗ Failed to modify proposal {proposal_id}[/red]")
        raise typer.Exit(1)


@app.command("stats")
def show_stats() -> None:
    """Show approval statistics."""
    gate = get_approval_gate()
    stats = gate.get_stats()
    
    table = Table(title="📊 Approval Statistics", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    
    table.add_row("Pending", str(stats["pending"]))
    table.add_row("Total Decisions", str(stats["total_decisions"]))
    table.add_row("Approved", f"[green]{stats['approved']}[/green]")
    table.add_row("Rejected", f"[red]{stats['rejected']}[/red]")
    table.add_row("Modified", f"[cyan]{stats['modified']}[/cyan]")
    table.add_row("Timeout", f"[dim]{stats['timeout']}[/dim]")
    table.add_row("Approval Rate", f"{stats['approval_rate']*100:.1f}%")
    table.add_row("Avg Decision Time", f"{stats['avg_decision_time_seconds']:.0f}s")
    
    console.print(table)
