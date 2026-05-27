"""
AutoSRE Team Commands

Team collaboration for incident investigations.
Share investigations, add comments, assign to team members.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="team",
    help="Team collaboration for investigations",
    no_args_is_help=True,
)

console = Console()

# Team data storage path
TEAM_DATA_DIR = Path("~/.autosre/team").expanduser()


def _ensure_team_dir():
    """Ensure team data directory exists."""
    TEAM_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_shares_file() -> Path:
    """Get path to shared investigations file."""
    return TEAM_DATA_DIR / "shares.json"


def _get_comments_file() -> Path:
    """Get path to comments file."""
    return TEAM_DATA_DIR / "comments.json"


def _get_assignments_file() -> Path:
    """Get path to assignments file."""
    return TEAM_DATA_DIR / "assignments.json"


def _load_json(path: Path) -> dict:
    """Load JSON file, returning empty dict if not exists."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict):
    """Save data to JSON file."""
    _ensure_team_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _get_memory():
    """Get memory instance."""
    from autosre.memory import EpisodicMemory
    return EpisodicMemory()


def _get_investigation(investigation_id: str):
    """Get an investigation by ID (supports partial match)."""
    memory = _get_memory()
    
    async def get_episode():
        # Try exact match first
        episode = await memory.get(investigation_id)
        if episode:
            return episode
        
        # Try partial match
        from autosre.memory import MemoryQuery
        all_episodes = await memory.retrieve(MemoryQuery(text=""), limit=500)
        for ep in all_episodes:
            if ep.id.startswith(investigation_id):
                return ep
        return None
    
    return asyncio.run(get_episode())


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2h ago')."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    
    if delta.days > 30:
        return dt.strftime("%Y-%m-%d")
    elif delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def _get_current_user() -> str:
    """Get current user name from environment or system."""
    import os
    import getpass
    return os.environ.get("USER", os.environ.get("USERNAME", getpass.getuser()))


@app.command("share")
def share_investigation(
    investigation_id: str = typer.Argument(..., help="Investigation ID to share (partial match supported)"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Optional message to include with share"),
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Slack channel to share to (if configured)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Share an investigation with the team.
    
    Makes an investigation visible to team members and optionally
    posts to Slack.
    
    [bold]Examples:[/]
        autosre team share abc123                           # Share by ID
        autosre team share abc123 -m "Need help with this"  # With message
        autosre team share abc123 --channel #incidents      # Share to Slack
    """
    # Find the investigation
    episode = _get_investigation(investigation_id)
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        console.print("[dim]Use 'autosre history list' to see available investigations[/]")
        raise typer.Exit(1)
    
    # Load existing shares
    shares = _load_json(_get_shares_file())
    
    # Create share record
    share_id = str(uuid.uuid4())[:8]
    share_record = {
        "id": share_id,
        "investigation_id": episode.id,
        "alert_type": episode.alert_type,
        "service": episode.service_name,
        "shared_by": _get_current_user(),
        "shared_at": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "channel": channel,
    }
    
    shares[episode.id] = share_record
    _save_json(_get_shares_file(), shares)
    
    if json_output:
        console.print(json.dumps(share_record, indent=2))
        return
    
    # Display share confirmation
    console.print()
    
    share_details = f"""[bold cyan]Investigation ID:[/] {episode.id[:12]}
[bold cyan]Alert Type:[/] {episode.alert_type}
[bold cyan]Service:[/] {episode.service_name or 'N/A'}
[bold cyan]Shared By:[/] {share_record['shared_by']}"""

    if message:
        share_details += f"\n[bold cyan]Message:[/] {message}"
    
    console.print(Panel(
        share_details,
        title="[bold green]✓ Investigation Shared[/]",
        border_style="green",
    ))
    
    # Attempt Slack notification if channel provided
    if channel:
        try:
            from autosre.config import Settings
            settings = Settings()
            if settings.slack_enabled and settings.slack_bot_token:
                console.print(f"[dim]Posted to Slack channel {channel}[/]")
            else:
                console.print(f"[yellow]Slack not configured - skipping notification[/]")
        except Exception:
            console.print(f"[yellow]Slack notification skipped[/]")
    
    console.print()
    console.print("[dim]Team members can view with 'autosre team list'[/]")
    console.print()


@app.command("comment")
def add_comment(
    investigation_id: str = typer.Argument(..., help="Investigation ID to comment on"),
    message: str = typer.Argument(..., help="Comment message"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Add a comment to an investigation.
    
    Comments are visible to all team members viewing the investigation.
    
    [bold]Examples:[/]
        autosre team comment abc123 "Checked the database - looks fine"
        autosre team comment abc1 "This might be related to INC-456"
    """
    # Find the investigation
    episode = _get_investigation(investigation_id)
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        console.print("[dim]Use 'autosre history list' to see available investigations[/]")
        raise typer.Exit(1)
    
    # Load existing comments
    comments = _load_json(_get_comments_file())
    
    # Initialize comments list for this investigation if needed
    if episode.id not in comments:
        comments[episode.id] = []
    
    # Create comment record
    comment_id = str(uuid.uuid4())[:8]
    comment_record = {
        "id": comment_id,
        "author": _get_current_user(),
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    comments[episode.id].append(comment_record)
    _save_json(_get_comments_file(), comments)
    
    if json_output:
        console.print(json.dumps(comment_record, indent=2))
        return
    
    console.print()
    console.print(Panel(
        f"[bold]{comment_record['author']}[/] commented:\n\n{message}",
        title=f"[bold green]✓ Comment Added[/] to {episode.id[:12]}",
        border_style="green",
    ))
    
    # Show total comments
    total_comments = len(comments[episode.id])
    console.print(f"[dim]Total comments on this investigation: {total_comments}[/]")
    console.print()


@app.command("assign")
def assign_investigation(
    investigation_id: str = typer.Argument(..., help="Investigation ID to assign"),
    user: str = typer.Argument(..., help="User to assign to (username or email)"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Priority level (high/medium/low)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Assign an investigation to a team member.
    
    Assigns ownership of an investigation to a specific user.
    
    [bold]Examples:[/]
        autosre team assign abc123 alice                    # Assign to alice
        autosre team assign abc123 bob@example.com          # Assign by email
        autosre team assign abc123 alice --priority high    # With priority
    """
    # Find the investigation
    episode = _get_investigation(investigation_id)
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        console.print("[dim]Use 'autosre history list' to see available investigations[/]")
        raise typer.Exit(1)
    
    # Load existing assignments
    assignments = _load_json(_get_assignments_file())
    
    # Create assignment record
    assignment_record = {
        "investigation_id": episode.id,
        "alert_type": episode.alert_type,
        "service": episode.service_name,
        "assigned_to": user,
        "assigned_by": _get_current_user(),
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "priority": priority or "medium",
        "status": "assigned",
    }
    
    assignments[episode.id] = assignment_record
    _save_json(_get_assignments_file(), assignments)
    
    if json_output:
        console.print(json.dumps(assignment_record, indent=2))
        return
    
    console.print()
    
    priority_style = {
        "high": "[bold red]HIGH[/]",
        "medium": "[yellow]MEDIUM[/]",
        "low": "[green]LOW[/]",
    }.get((priority or "medium").lower(), priority)
    
    assign_details = f"""[bold cyan]Investigation:[/] {episode.id[:12]}
[bold cyan]Alert Type:[/] {episode.alert_type}
[bold cyan]Service:[/] {episode.service_name or 'N/A'}
[bold cyan]Assigned To:[/] [bold]{user}[/]
[bold cyan]Assigned By:[/] {assignment_record['assigned_by']}
[bold cyan]Priority:[/] {priority_style}"""
    
    console.print(Panel(
        assign_details,
        title="[bold green]✓ Investigation Assigned[/]",
        border_style="green",
    ))
    console.print()


@app.command("list")
def list_team_investigations(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of investigations to show"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by assigned user"),
    mine: bool = typer.Option(False, "--mine", "-m", help="Show only my assignments"),
    shared: bool = typer.Option(False, "--shared", "-s", help="Show only shared investigations"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show team investigations.
    
    Lists shared investigations, assignments, and recent comments.
    
    [bold]Examples:[/]
        autosre team list                    # List all team investigations
        autosre team list --mine             # Show my assignments
        autosre team list --user alice       # Show alice's assignments
        autosre team list --shared           # Show shared investigations only
    """
    # Load team data
    shares = _load_json(_get_shares_file())
    assignments = _load_json(_get_assignments_file())
    comments = _load_json(_get_comments_file())
    
    current_user = _get_current_user()
    
    # Combine all team investigations
    team_investigations = {}
    
    # Add shares
    for inv_id, share in shares.items():
        if inv_id not in team_investigations:
            team_investigations[inv_id] = {
                "id": inv_id,
                "alert_type": share.get("alert_type", "Unknown"),
                "service": share.get("service"),
                "shared": True,
                "shared_by": share.get("shared_by"),
                "shared_at": share.get("shared_at"),
            }
    
    # Add assignments
    for inv_id, assignment in assignments.items():
        if inv_id not in team_investigations:
            team_investigations[inv_id] = {
                "id": inv_id,
                "alert_type": assignment.get("alert_type", "Unknown"),
                "service": assignment.get("service"),
                "shared": False,
            }
        team_investigations[inv_id]["assigned_to"] = assignment.get("assigned_to")
        team_investigations[inv_id]["assigned_by"] = assignment.get("assigned_by")
        team_investigations[inv_id]["assigned_at"] = assignment.get("assigned_at")
        team_investigations[inv_id]["priority"] = assignment.get("priority")
        team_investigations[inv_id]["status"] = assignment.get("status")
    
    # Add comment counts
    for inv_id in team_investigations:
        team_investigations[inv_id]["comment_count"] = len(comments.get(inv_id, []))
    
    # Apply filters
    results = list(team_investigations.values())
    
    if mine:
        results = [r for r in results if r.get("assigned_to") == current_user]
    elif user:
        results = [r for r in results if r.get("assigned_to") == user]
    
    if shared:
        results = [r for r in results if r.get("shared")]
    
    # Sort by most recent activity
    def get_latest_time(item):
        times = []
        if item.get("shared_at"):
            times.append(item["shared_at"])
        if item.get("assigned_at"):
            times.append(item["assigned_at"])
        return max(times) if times else ""
    
    results.sort(key=get_latest_time, reverse=True)
    results = results[:limit]
    
    if json_output:
        console.print(json.dumps(results, indent=2))
        return
    
    if not results:
        console.print()
        filter_msg = ""
        if mine:
            filter_msg = " assigned to you"
        elif user:
            filter_msg = f" assigned to {user}"
        elif shared:
            filter_msg = " shared"
        
        console.print(Panel(
            f"[yellow]No team investigations{filter_msg} found[/]\n\n"
            "[dim]Share an investigation with:[/]\n"
            "[cyan]autosre team share <investigation_id>[/]",
            title="👥 Team Investigations",
            border_style="yellow",
        ))
        return
    
    # Build table
    table = Table(
        title=f"👥 Team Investigations ({len(results)} records)",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Alert", style="yellow", max_width=25)
    table.add_column("Service", width=12)
    table.add_column("Assigned To", width=12)
    table.add_column("Priority", width=8, justify="center")
    table.add_column("Comments", width=8, justify="center")
    table.add_column("Shared", width=6, justify="center")
    
    for inv in results:
        # Format priority
        priority = inv.get("priority", "")
        if priority:
            priority_style = {
                "high": "[bold red]HIGH[/]",
                "medium": "[yellow]MED[/]",
                "low": "[green]LOW[/]",
            }.get(priority.lower(), priority)
        else:
            priority_style = "[dim]-[/]"
        
        # Format assigned
        assigned = inv.get("assigned_to", "")
        if assigned == current_user:
            assigned = f"[bold green]{assigned}[/]"
        elif not assigned:
            assigned = "[dim]-[/]"
        
        # Format comments
        comment_count = inv.get("comment_count", 0)
        comments_display = f"[cyan]{comment_count}[/]" if comment_count > 0 else "[dim]0[/]"
        
        # Format shared
        shared_display = "[green]✓[/]" if inv.get("shared") else "[dim]-[/]"
        
        # Truncate alert type
        alert_type = inv.get("alert_type", "Unknown")
        if len(alert_type) > 25:
            alert_type = alert_type[:22] + "..."
        
        table.add_row(
            inv["id"][:12],
            alert_type,
            inv.get("service") or "-",
            assigned,
            priority_style,
            comments_display,
            shared_display,
        )
    
    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Use [cyan]autosre history show <id>[/] to view investigation details[/]")
    console.print("[dim]Use [cyan]autosre team comment <id> <message>[/] to add a comment[/]")
    console.print()


@app.command("comments")
def show_comments(
    investigation_id: str = typer.Argument(..., help="Investigation ID to show comments for"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of comments to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show comments on an investigation.
    
    [bold]Examples:[/]
        autosre team comments abc123
        autosre team comments abc123 --limit 50
    """
    # Find the investigation
    episode = _get_investigation(investigation_id)
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        console.print("[dim]Use 'autosre history list' to see available investigations[/]")
        raise typer.Exit(1)
    
    # Load comments
    all_comments = _load_json(_get_comments_file())
    inv_comments = all_comments.get(episode.id, [])
    
    # Sort by newest first
    inv_comments = sorted(inv_comments, key=lambda c: c.get("created_at", ""), reverse=True)
    inv_comments = inv_comments[:limit]
    
    if json_output:
        console.print(json.dumps(inv_comments, indent=2))
        return
    
    if not inv_comments:
        console.print()
        console.print(Panel(
            "[dim]No comments yet[/]\n\n"
            f"Add one with: [cyan]autosre team comment {episode.id[:12]} \"Your comment\"[/]",
            title=f"💬 Comments on {episode.id[:12]}",
            border_style="dim",
        ))
        return
    
    console.print()
    console.print(f"[bold]💬 Comments on investigation {episode.id[:12]}[/]")
    console.print()
    
    for comment in inv_comments:
        created_at = comment.get("created_at", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                time_ago = _format_time_ago(dt)
            except Exception:
                time_ago = created_at
        else:
            time_ago = "Unknown"
        
        console.print(Panel(
            comment.get("message", ""),
            title=f"[bold]{comment.get('author', 'Unknown')}[/] • [dim]{time_ago}[/]",
            border_style="cyan",
        ))
        console.print()
