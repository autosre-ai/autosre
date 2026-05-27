"""
AutoSRE History Commands

Browse and manage past incident investigations.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

app = typer.Typer(
    name="history",
    help="Browse past incident investigations",
    no_args_is_help=True,
)

console = Console()


def _get_memory():
    """Get memory instance."""
    from autosre.memory import EpisodicMemory
    return EpisodicMemory()


def _format_duration(seconds: Optional[int]) -> str:
    """Format duration in human-readable format."""
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


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


def _get_severity_style(severity: str) -> str:
    """Get Rich style for severity level."""
    styles = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "green",
        "info": "dim",
    }
    return styles.get(severity.lower(), "white")


@app.command("list")
def list_investigations(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of investigations to show"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service"),
    alert_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by alert type"),
    resolved_only: bool = typer.Option(False, "--resolved", "-r", help="Show only resolved investigations"),
    unresolved_only: bool = typer.Option(False, "--unresolved", "-u", help="Show only unresolved investigations"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity (critical/high/medium/low)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    compact: bool = typer.Option(False, "--compact", "-c", help="Compact view with less detail"),
):
    """
    List recent incident investigations.
    
    Shows investigation history with status, duration, and key findings.
    
    [bold]Examples:[/]
        autosre history list                        # List recent 20 investigations
        autosre history list --limit 50             # List more investigations
        autosre history list --service checkout     # Filter by service
        autosre history list --resolved             # Only resolved investigations
        autosre history list --type error_rate      # Filter by alert type
        autosre history list --severity critical    # Filter by severity
    """
    memory = _get_memory()
    
    from autosre.memory import MemoryQuery
    
    async def fetch_episodes():
        query = MemoryQuery(
            text="",
            service=service,
            alert_type=alert_type,
        )
        return await memory.retrieve(query, limit=limit * 2)  # Fetch more for filtering
    
    episodes = asyncio.run(fetch_episodes())
    
    # Apply filters
    if resolved_only:
        episodes = [ep for ep in episodes if ep.resolved]
    if unresolved_only:
        episodes = [ep for ep in episodes if not ep.resolved]
    if severity:
        episodes = [ep for ep in episodes if ep.severity.lower() == severity.lower()]
    
    # Limit after filtering
    episodes = episodes[:limit]
    
    if json_output:
        output = [
            {
                "id": ep.id,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
                "alert_type": ep.alert_type,
                "service": ep.service_name,
                "severity": ep.severity,
                "root_cause": ep.root_cause,
                "summary": ep.summary,
                "resolved": ep.resolved,
                "effectiveness_score": ep.effectiveness_score,
                "duration_seconds": ep.duration_seconds,
                "skills_used": ep.skills_used,
            }
            for ep in episodes
        ]
        console.print(json.dumps(output, indent=2))
        return
    
    if not episodes:
        console.print()
        console.print(Panel(
            "[yellow]No investigations found in history[/]\n\n"
            "[dim]Run an investigation to start building history:[/]\n"
            "[cyan]autosre investigate run \"High error rate on checkout\"[/]",
            title="📜 Investigation History",
            border_style="yellow",
        ))
        return
    
    # Build table
    table = Table(
        title=f"📜 Investigation History ({len(episodes)} records)",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    
    table.add_column("ID", style="cyan", width=12)
    table.add_column("When", style="dim", width=10)
    table.add_column("Alert", style="yellow", max_width=25)
    table.add_column("Service", width=15)
    table.add_column("Severity", width=10, justify="center")
    
    if not compact:
        table.add_column("Root Cause", max_width=30)
        table.add_column("Duration", justify="right", width=8)
        table.add_column("Score", justify="right", width=7)
    
    table.add_column("Status", justify="center", width=8)
    
    for ep in episodes:
        # Format values
        when = _format_time_ago(ep.created_at) if ep.created_at else "-"
        duration = _format_duration(ep.duration_seconds)
        score = f"{ep.effectiveness_score:.0%}" if ep.effectiveness_score else "-"
        status = "[green]✓[/]" if ep.resolved else "[yellow]⋯[/]"
        severity_text = Text(ep.severity.upper(), style=_get_severity_style(ep.severity))
        
        root_cause = ep.root_cause or "-"
        if len(root_cause) > 30:
            root_cause = root_cause[:27] + "..."
        
        alert_type = ep.alert_type
        if len(alert_type) > 25:
            alert_type = alert_type[:22] + "..."
        
        if compact:
            table.add_row(
                ep.id[:12],
                when,
                alert_type,
                ep.service_name or "-",
                severity_text,
                status,
            )
        else:
            table.add_row(
                ep.id[:12],
                when,
                alert_type,
                ep.service_name or "-",
                severity_text,
                root_cause,
                duration,
                score,
                status,
            )
    
    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Use [cyan]autosre history show <id>[/] to view full details[/]")
    console.print()


@app.command("show")
def show_investigation(
    investigation_id: str = typer.Argument(..., help="Investigation ID (partial match supported)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    raw: bool = typer.Option(False, "--raw", help="Show raw data including all fields"),
):
    """
    View detailed information about a specific investigation.
    
    Shows full investigation details including root cause, evidence,
    key findings, skills used, and timeline.
    
    [bold]Examples:[/]
        autosre history show abc12345        # Full details
        autosre history show abc1           # Partial ID match
        autosre history show abc12345 --json # JSON output
    """
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
    
    episode = asyncio.run(get_episode())
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        console.print("[dim]Use 'autosre history list' to see available investigations[/]")
        raise typer.Exit(1)
    
    if json_output:
        output = episode.model_dump()
        if output.get("created_at"):
            output["created_at"] = output["created_at"].isoformat()
        console.print(json.dumps(output, indent=2, default=str))
        return
    
    # Build detailed view
    console.print()
    
    # Header panel with main info
    severity_style = _get_severity_style(episode.severity)
    status_text = "[green]✓ Resolved[/]" if episode.resolved else "[yellow]⋯ Open[/]"
    
    header = f"""[bold cyan]Alert Type:[/] {episode.alert_type}
[bold cyan]Service:[/] {episode.service_name or 'N/A'}
[bold cyan]Severity:[/] [{severity_style}]{episode.severity.upper()}[/{severity_style}]
[bold cyan]Status:[/] {status_text}
[bold cyan]Created:[/] {episode.created_at.strftime('%Y-%m-%d %H:%M:%S') if episode.created_at else 'N/A'}
[bold cyan]Duration:[/] {_format_duration(episode.duration_seconds)}
[bold cyan]Effectiveness:[/] {episode.effectiveness_score:.0%}"""

    console.print(Panel(
        header,
        title=f"🔍 Investigation {episode.id}",
        border_style="cyan",
    ))
    
    # Root cause panel
    if episode.root_cause:
        console.print()
        console.print(Panel(
            episode.root_cause,
            title="[bold yellow]Root Cause[/]",
            border_style="yellow",
        ))
    
    # Summary panel
    if episode.summary:
        console.print()
        console.print(Panel(
            episode.summary,
            title="[bold blue]Summary[/]",
            border_style="blue",
        ))
    
    # Resolution panel
    if episode.resolution:
        console.print()
        console.print(Panel(
            episode.resolution,
            title="[bold green]Resolution[/]",
            border_style="green",
        ))
    
    # Skills used
    if episode.skills_used:
        console.print()
        skills_text = " • ".join(f"[cyan]{skill}[/]" for skill in episode.skills_used)
        console.print(Panel(
            skills_text,
            title="[bold]Skills Used[/]",
            border_style="dim",
        ))
    
    # Key findings
    if episode.key_findings:
        console.print()
        findings_table = Table(
            title="Key Findings",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        findings_table.add_column("#", width=4)
        findings_table.add_column("Finding", style="white")
        findings_table.add_column("Confidence", justify="right", width=12)
        
        for i, finding in enumerate(episode.key_findings, 1):
            if isinstance(finding, dict):
                finding_text = finding.get("finding", finding.get("description", str(finding)))
                confidence = finding.get("confidence", "-")
                if isinstance(confidence, (int, float)):
                    confidence = f"{confidence:.0%}"
            else:
                finding_text = str(finding)
                confidence = "-"
            findings_table.add_row(str(i), finding_text, str(confidence))
        
        console.print(findings_table)
    
    # Steps taken
    if episode.steps_taken:
        console.print()
        steps_text = "\n".join(f"[dim]{i}.[/] {step}" for i, step in enumerate(episode.steps_taken, 1))
        console.print(Panel(
            steps_text,
            title="[bold]Steps Taken[/]",
            border_style="dim",
        ))
    
    # Hypotheses
    if episode.hypotheses:
        console.print()
        hyp_text = "\n".join(f"• {hyp}" for hyp in episode.hypotheses)
        console.print(Panel(
            hyp_text,
            title="[bold]Hypotheses Explored[/]",
            border_style="dim",
        ))
    
    # Symptoms
    if episode.symptoms and raw:
        console.print()
        symptoms_text = "\n".join(f"• {symptom}" for symptom in episode.symptoms)
        console.print(Panel(
            symptoms_text,
            title="[bold]Symptoms[/]",
            border_style="dim",
        ))
    
    # Metrics (if raw mode)
    if episode.metrics and raw:
        console.print()
        metrics_json = json.dumps(episode.metrics, indent=2)
        console.print(Panel(
            Syntax(metrics_json, "json", theme="monokai"),
            title="[bold]Metrics Data[/]",
            border_style="dim",
        ))
    
    # Tags
    if episode.tags:
        console.print()
        console.print(f"[dim]Tags:[/] {' '.join(f'[cyan]#{tag}[/]' for tag in episode.tags)}")
    
    console.print()


@app.command("search")
def search_investigations(
    query: str = typer.Argument(..., help="Search query (matches alert type, service, root cause, summary)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to show"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Filter by service"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Search past investigations by text query.
    
    Searches across alert types, services, root causes, summaries, 
    and key findings.
    
    [bold]Examples:[/]
        autosre history search "redis"                # Search for redis-related
        autosre history search "timeout" --service api  # Timeouts in api service
        autosre history search "memory leak"          # Memory leak issues
        autosre history search "500 error"            # HTTP 500 errors
    """
    memory = _get_memory()
    
    from autosre.memory import MemoryQuery
    
    async def do_search():
        # Get all episodes and filter
        mq = MemoryQuery(text=query, service=service)
        all_episodes = await memory.retrieve(mq, limit=500)
        
        # Score and filter by relevance
        query_lower = query.lower()
        results = []
        
        for ep in all_episodes:
            score = 0
            
            # Check various fields for matches
            if ep.alert_type and query_lower in ep.alert_type.lower():
                score += 10
            if ep.service_name and query_lower in ep.service_name.lower():
                score += 8
            if ep.root_cause and query_lower in ep.root_cause.lower():
                score += 6
            if ep.summary and query_lower in ep.summary.lower():
                score += 4
            if ep.resolution and query_lower in ep.resolution.lower():
                score += 3
            
            # Check key findings
            for finding in ep.key_findings or []:
                if isinstance(finding, dict):
                    finding_text = str(finding.get("finding", finding.get("description", "")))
                else:
                    finding_text = str(finding)
                if query_lower in finding_text.lower():
                    score += 2
                    break
            
            # Check steps taken
            for step in ep.steps_taken or []:
                if query_lower in step.lower():
                    score += 1
                    break
            
            # Check symptoms
            for symptom in ep.symptoms or []:
                if query_lower in symptom.lower():
                    score += 1
                    break
            
            if score > 0:
                results.append((ep, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return [ep for ep, _ in results[:limit]]
    
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
                "resolved": ep.resolved,
            }
            for ep in episodes
        ]
        console.print(json.dumps(output, indent=2))
        return
    
    if not episodes:
        console.print()
        console.print(f"[yellow]No investigations matching '{query}'[/]")
        console.print("[dim]Try a different search term or check spelling[/]")
        return
    
    console.print()
    console.print(f"[bold]🔎 Search Results for '{query}'[/] ({len(episodes)} found)")
    console.print()
    
    for ep in episodes:
        # Create a mini-panel for each result
        content_lines = []
        content_lines.append(f"[bold]Alert:[/] {ep.alert_type}")
        content_lines.append(f"[bold]Service:[/] {ep.service_name or 'N/A'}")
        content_lines.append(f"[bold]Severity:[/] [{_get_severity_style(ep.severity)}]{ep.severity.upper()}[/]")
        content_lines.append(f"[bold]Status:[/] {'[green]✓ Resolved[/]' if ep.resolved else '[yellow]⋯ Open[/]'}")
        
        if ep.root_cause:
            root_cause = ep.root_cause[:100] + "..." if len(ep.root_cause) > 100 else ep.root_cause
            content_lines.append(f"[bold]Root Cause:[/] {root_cause}")
        
        if ep.summary:
            summary = ep.summary[:150] + "..." if len(ep.summary) > 150 else ep.summary
            content_lines.append(f"[bold]Summary:[/] {summary}")
        
        when = _format_time_ago(ep.created_at) if ep.created_at else "unknown"
        
        console.print(Panel(
            "\n".join(content_lines),
            title=f"[cyan]{ep.id}[/] [dim]({when})[/]",
            border_style="dim",
        ))
    
    console.print()
    console.print("[dim]Use [cyan]autosre history show <id>[/] for full details[/]")
    console.print()


@app.command("export")
def export_investigation(
    investigation_id: str = typer.Argument(..., help="Investigation ID to export"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("markdown", "--format", "-f", help="Export format: markdown|json|yaml|html"),
):
    """
    Export a specific investigation to a file.
    
    Generates a detailed report that can be shared or archived.
    
    [bold]Examples:[/]
        autosre history export abc123                      # Export as markdown
        autosre history export abc123 -o report.md        # Custom filename
        autosre history export abc123 --format json       # JSON format
        autosre history export abc123 --format html       # HTML report
    """
    memory = _get_memory()
    
    async def get_episode():
        episode = await memory.get(investigation_id)
        if episode:
            return episode
        
        from autosre.memory import MemoryQuery
        all_episodes = await memory.retrieve(MemoryQuery(text=""), limit=500)
        for ep in all_episodes:
            if ep.id.startswith(investigation_id):
                return ep
        return None
    
    episode = asyncio.run(get_episode())
    
    if not episode:
        console.print(f"[red]✗[/] Investigation [cyan]{investigation_id}[/] not found")
        raise typer.Exit(1)
    
    # Determine output path
    if output_path is None:
        ext_map = {"markdown": ".md", "json": ".json", "yaml": ".yaml", "html": ".html"}
        ext = ext_map.get(format, ".txt")
        output_path = f"investigation_{episode.id}{ext}"
    
    # Generate content based on format
    if format == "json":
        content = _export_json(episode)
    elif format == "yaml":
        content = _export_yaml(episode)
    elif format == "html":
        content = _export_html(episode)
    else:  # markdown
        content = _export_markdown(episode)
    
    # Write file
    Path(output_path).write_text(content)
    
    console.print()
    console.print(f"[green]✓[/] Exported investigation to [cyan]{output_path}[/]")
    console.print(f"[dim]Format: {format}[/]")
    console.print()


def _export_markdown(episode) -> str:
    """Export episode as Markdown."""
    lines = [
        f"# Investigation Report: {episode.id}",
        "",
        "## Overview",
        "",
        f"- **Alert Type:** {episode.alert_type}",
        f"- **Service:** {episode.service_name or 'N/A'}",
        f"- **Severity:** {episode.severity.upper()}",
        f"- **Status:** {'✓ Resolved' if episode.resolved else '⋯ Open'}",
        f"- **Created:** {episode.created_at.strftime('%Y-%m-%d %H:%M:%S') if episode.created_at else 'N/A'}",
        f"- **Duration:** {_format_duration(episode.duration_seconds)}",
        f"- **Effectiveness Score:** {episode.effectiveness_score:.0%}",
        "",
    ]
    
    if episode.root_cause:
        lines.extend([
            "## Root Cause",
            "",
            episode.root_cause,
            "",
        ])
    
    if episode.summary:
        lines.extend([
            "## Summary",
            "",
            episode.summary,
            "",
        ])
    
    if episode.resolution:
        lines.extend([
            "## Resolution",
            "",
            episode.resolution,
            "",
        ])
    
    if episode.key_findings:
        lines.extend([
            "## Key Findings",
            "",
        ])
        for i, finding in enumerate(episode.key_findings, 1):
            if isinstance(finding, dict):
                finding_text = finding.get("finding", finding.get("description", str(finding)))
                confidence = finding.get("confidence")
                if confidence:
                    lines.append(f"{i}. {finding_text} (confidence: {confidence:.0%})")
                else:
                    lines.append(f"{i}. {finding_text}")
            else:
                lines.append(f"{i}. {finding}")
        lines.append("")
    
    if episode.steps_taken:
        lines.extend([
            "## Investigation Steps",
            "",
        ])
        for i, step in enumerate(episode.steps_taken, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    
    if episode.hypotheses:
        lines.extend([
            "## Hypotheses Explored",
            "",
        ])
        for hyp in episode.hypotheses:
            lines.append(f"- {hyp}")
        lines.append("")
    
    if episode.skills_used:
        lines.extend([
            "## Skills Used",
            "",
            ", ".join(episode.skills_used),
            "",
        ])
    
    if episode.tags:
        lines.extend([
            "## Tags",
            "",
            " ".join(f"#{tag}" for tag in episode.tags),
            "",
        ])
    
    lines.extend([
        "---",
        f"*Generated by AutoSRE on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ])
    
    return "\n".join(lines)


def _export_json(episode) -> str:
    """Export episode as JSON."""
    data = episode.model_dump()
    if data.get("created_at"):
        data["created_at"] = data["created_at"].isoformat()
    return json.dumps(data, indent=2, default=str)


def _export_yaml(episode) -> str:
    """Export episode as YAML."""
    import yaml
    data = episode.model_dump()
    if data.get("created_at"):
        data["created_at"] = data["created_at"].isoformat()
    # Remove None and empty values for cleaner output
    data = {k: v for k, v in data.items() if v is not None and v != [] and v != {}}
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _export_html(episode) -> str:
    """Export episode as HTML."""
    status_color = "green" if episode.resolved else "orange"
    status_text = "Resolved" if episode.resolved else "Open"
    
    severity_colors = {
        "critical": "#dc3545",
        "high": "#fd7e14",
        "medium": "#ffc107",
        "low": "#28a745",
        "info": "#6c757d",
    }
    severity_color = severity_colors.get(episode.severity.lower(), "#6c757d")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investigation Report - {episode.id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .meta-item {{ }}
        .meta-label {{ font-weight: bold; color: #666; font-size: 0.85em; text-transform: uppercase; }}
        .meta-value {{ font-size: 1.1em; color: #333; }}
        .status {{ display: inline-block; padding: 4px 12px; border-radius: 12px; color: white; background: {status_color}; }}
        .severity {{ display: inline-block; padding: 4px 12px; border-radius: 12px; color: white; background: {severity_color}; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; border: 1px solid #e9ecef; margin: 20px 0; }}
        .section-title {{ color: #007bff; margin-top: 0; }}
        ol, ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
        .tags {{ margin-top: 20px; }}
        .tag {{ display: inline-block; background: #e9ecef; padding: 4px 10px; border-radius: 4px; margin: 2px; font-size: 0.9em; }}
        .skills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .skill {{ background: #007bff; color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.9em; }}
        footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e9ecef; color: #666; font-size: 0.9em; text-align: center; }}
    </style>
</head>
<body>
    <h1>🔍 Investigation Report</h1>
    
    <div class="meta">
        <div class="meta-item">
            <div class="meta-label">Investigation ID</div>
            <div class="meta-value"><code>{episode.id}</code></div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Alert Type</div>
            <div class="meta-value">{episode.alert_type}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Service</div>
            <div class="meta-value">{episode.service_name or 'N/A'}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Severity</div>
            <div class="meta-value"><span class="severity">{episode.severity.upper()}</span></div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Status</div>
            <div class="meta-value"><span class="status">{status_text}</span></div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Duration</div>
            <div class="meta-value">{_format_duration(episode.duration_seconds)}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Effectiveness</div>
            <div class="meta-value">{episode.effectiveness_score:.0%}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Created</div>
            <div class="meta-value">{episode.created_at.strftime('%Y-%m-%d %H:%M') if episode.created_at else 'N/A'}</div>
        </div>
    </div>
"""
    
    if episode.root_cause:
        html += f"""
    <div class="section">
        <h2 class="section-title">🎯 Root Cause</h2>
        <p>{episode.root_cause}</p>
    </div>
"""
    
    if episode.summary:
        html += f"""
    <div class="section">
        <h2 class="section-title">📋 Summary</h2>
        <p>{episode.summary}</p>
    </div>
"""
    
    if episode.resolution:
        html += f"""
    <div class="section">
        <h2 class="section-title">✅ Resolution</h2>
        <p>{episode.resolution}</p>
    </div>
"""
    
    if episode.key_findings:
        findings_html = "\n".join(
            f"<li>{f.get('finding', f.get('description', str(f))) if isinstance(f, dict) else f}</li>"
            for f in episode.key_findings
        )
        html += f"""
    <div class="section">
        <h2 class="section-title">🔑 Key Findings</h2>
        <ol>{findings_html}</ol>
    </div>
"""
    
    if episode.steps_taken:
        steps_html = "\n".join(f"<li>{step}</li>" for step in episode.steps_taken)
        html += f"""
    <div class="section">
        <h2 class="section-title">📝 Investigation Steps</h2>
        <ol>{steps_html}</ol>
    </div>
"""
    
    if episode.skills_used:
        skills_html = "\n".join(f'<span class="skill">{skill}</span>' for skill in episode.skills_used)
        html += f"""
    <div class="section">
        <h2 class="section-title">🛠️ Skills Used</h2>
        <div class="skills">{skills_html}</div>
    </div>
"""
    
    if episode.tags:
        tags_html = "\n".join(f'<span class="tag">#{tag}</span>' for tag in episode.tags)
        html += f"""
    <div class="tags">{tags_html}</div>
"""
    
    html += f"""
    <footer>
        Generated by AutoSRE on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </footer>
</body>
</html>
"""
    
    return html


@app.command("stats")
def investigation_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show statistics about past investigations.
    
    Displays metrics including resolution rates, average duration,
    common alert types, and trends.
    
    [bold]Examples:[/]
        autosre history stats            # Show statistics
        autosre history stats --json     # JSON output
    """
    memory = _get_memory()
    stats = memory.get_stats()
    
    # Get additional stats by querying all episodes
    from autosre.memory import MemoryQuery
    
    async def get_extended_stats():
        all_episodes = await memory.retrieve(MemoryQuery(text=""), limit=1000)
        
        # Calculate additional statistics
        services = {}
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        skills = {}
        recent_7d = 0
        recent_30d = 0
        now = datetime.now(timezone.utc)
        
        for ep in all_episodes:
            # Service counts
            if ep.service_name:
                services[ep.service_name] = services.get(ep.service_name, 0) + 1
            
            # Severity counts
            sev = ep.severity.lower() if ep.severity else "info"
            severities[sev] = severities.get(sev, 0) + 1
            
            # Skill usage
            for skill in ep.skills_used or []:
                skills[skill] = skills.get(skill, 0) + 1
            
            # Recent activity
            if ep.created_at:
                ep_time = ep.created_at if ep.created_at.tzinfo else ep.created_at.replace(tzinfo=timezone.utc)
                days_ago = (now - ep_time).days
                if days_ago <= 7:
                    recent_7d += 1
                if days_ago <= 30:
                    recent_30d += 1
        
        return {
            "services": dict(sorted(services.items(), key=lambda x: x[1], reverse=True)[:10]),
            "severities": severities,
            "skills": dict(sorted(skills.items(), key=lambda x: x[1], reverse=True)[:10]),
            "recent_7d": recent_7d,
            "recent_30d": recent_30d,
            "total": len(all_episodes),
        }
    
    extended = asyncio.run(get_extended_stats())
    
    if json_output:
        output = {
            **stats,
            "services": extended["services"],
            "severities": extended["severities"],
            "skills_used": extended["skills"],
            "recent_7_days": extended["recent_7d"],
            "recent_30_days": extended["recent_30d"],
        }
        console.print(json.dumps(output, indent=2))
        return
    
    console.print()
    
    # Main statistics panel
    main_stats = Table(show_header=False, box=None, padding=(0, 2))
    main_stats.add_column("Metric", style="cyan")
    main_stats.add_column("Value", style="bold green", justify="right")
    
    main_stats.add_row("Total Investigations", str(stats.get("total_episodes", 0)))
    main_stats.add_row("Resolved", str(stats.get("resolved_count", 0)))
    resolution_rate = stats.get("resolution_rate", 0)
    main_stats.add_row("Resolution Rate", f"{resolution_rate:.0%}")
    
    avg_eff = stats.get("avg_effectiveness_score", 0)
    main_stats.add_row("Avg Effectiveness", f"{avg_eff:.0%}")
    
    avg_duration = stats.get("avg_resolution_seconds")
    if avg_duration:
        main_stats.add_row("Avg Duration", _format_duration(int(avg_duration)))
    
    main_stats.add_row("Strategies Learned", str(stats.get("total_strategies", 0)))
    main_stats.add_row("", "")
    main_stats.add_row("Last 7 Days", str(extended["recent_7d"]))
    main_stats.add_row("Last 30 Days", str(extended["recent_30d"]))
    
    console.print(Panel(
        main_stats,
        title="📊 Investigation Statistics",
        border_style="cyan",
    ))
    
    # Top alert types
    top_types = stats.get("top_alert_types", [])
    if top_types:
        console.print()
        type_table = Table(
            title="Top Alert Types",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        type_table.add_column("Alert Type", style="yellow")
        type_table.add_column("Count", justify="right", width=8)
        type_table.add_column("Distribution", width=25)
        
        max_count = max(t["count"] for t in top_types) if top_types else 1
        total = extended["total"] or 1
        
        for t in top_types:
            bar_len = int((t["count"] / max_count) * 20)
            bar = "█" * bar_len
            pct = t["count"] / total * 100
            type_table.add_row(
                t["alert_type"],
                str(t["count"]),
                f"[cyan]{bar}[/] {pct:.0f}%"
            )
        
        console.print(type_table)
    
    # Top services
    if extended["services"]:
        console.print()
        svc_table = Table(
            title="Top Services",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        svc_table.add_column("Service", style="green")
        svc_table.add_column("Incidents", justify="right", width=10)
        
        for svc, count in list(extended["services"].items())[:5]:
            svc_table.add_row(svc, str(count))
        
        console.print(svc_table)
    
    # Severity distribution
    if any(extended["severities"].values()):
        console.print()
        sev_table = Table(
            title="Severity Distribution",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        sev_table.add_column("Severity", width=12)
        sev_table.add_column("Count", justify="right", width=8)
        sev_table.add_column("Percentage", justify="right", width=10)
        
        total = sum(extended["severities"].values()) or 1
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = extended["severities"].get(sev, 0)
            if count > 0:
                style = _get_severity_style(sev)
                sev_table.add_row(
                    Text(sev.upper(), style=style),
                    str(count),
                    f"{count/total*100:.0f}%"
                )
        
        console.print(sev_table)
    
    # Top skills
    if extended["skills"]:
        console.print()
        skills_list = " • ".join(f"[cyan]{skill}[/] ({count})" 
                                  for skill, count in list(extended["skills"].items())[:8])
        console.print(Panel(
            skills_list,
            title="[bold]Most Used Skills[/]",
            border_style="dim",
        ))
    
    console.print()


@app.command("diff")
def diff_investigations(
    id1: str = typer.Argument(..., help="First investigation ID"),
    id2: str = typer.Argument(..., help="Second investigation ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    fields_only: bool = typer.Option(False, "--fields", "-f", help="Show only field differences"),
):
    """
    Compare two investigations side-by-side.
    
    Shows what changed between investigations, identifies similar root causes,
    and highlights timeline differences.
    
    [bold]Examples:[/]
        autosre history diff abc123 def456     # Compare two investigations
        autosre history diff abc def --json    # JSON output
        autosre history diff abc def --fields  # Show only field differences
    
    [bold]Use cases:[/]
        • Compare recurring incidents to identify patterns
        • Review how root causes evolved over time
        • Analyze similar issues across different services
        • Audit investigation effectiveness changes
    """
    memory = _get_memory()
    
    async def get_episode_by_partial_id(partial_id: str):
        """Get episode by full or partial ID match."""
        episode = await memory.get(partial_id)
        if episode:
            return episode
        
        from autosre.memory import MemoryQuery
        all_episodes = await memory.retrieve(MemoryQuery(text=""), limit=500)
        for ep in all_episodes:
            if ep.id.startswith(partial_id):
                return ep
        return None
    
    async def get_both():
        ep1 = await get_episode_by_partial_id(id1)
        ep2 = await get_episode_by_partial_id(id2)
        return ep1, ep2
    
    ep1, ep2 = asyncio.run(get_both())
    
    # Validate both episodes exist
    if not ep1:
        console.print(f"[red]✗[/] Investigation [cyan]{id1}[/] not found")
        raise typer.Exit(1)
    if not ep2:
        console.print(f"[red]✗[/] Investigation [cyan]{id2}[/] not found")
        raise typer.Exit(1)
    
    # Build diff analysis
    diff_data = _build_diff_analysis(ep1, ep2)
    
    if json_output:
        console.print(json.dumps(diff_data, indent=2, default=str))
        return
    
    # Display side-by-side comparison
    _display_diff(ep1, ep2, diff_data, fields_only)


def _build_diff_analysis(ep1, ep2) -> dict:
    """Build comprehensive diff analysis between two episodes."""
    
    # Calculate root cause similarity (simple word overlap)
    def text_similarity(text1: Optional[str], text2: Optional[str]) -> float:
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0
    
    # Field comparisons
    field_changes = {}
    
    comparable_fields = [
        ("alert_type", "Alert Type"),
        ("service_name", "Service"),
        ("severity", "Severity"),
        ("resolved", "Status"),
        ("root_cause", "Root Cause"),
        ("resolution", "Resolution"),
    ]
    
    for field, label in comparable_fields:
        val1 = getattr(ep1, field, None)
        val2 = getattr(ep2, field, None)
        if val1 != val2:
            field_changes[field] = {
                "label": label,
                "old": val1,
                "new": val2,
            }
    
    # Skills comparison
    skills1 = set(ep1.skills_used or [])
    skills2 = set(ep2.skills_used or [])
    skills_added = skills2 - skills1
    skills_removed = skills1 - skills2
    skills_common = skills1 & skills2
    
    # Steps comparison
    steps1 = set(ep1.steps_taken or [])
    steps2 = set(ep2.steps_taken or [])
    steps_added = steps2 - steps1
    steps_removed = steps1 - steps2
    
    # Findings comparison
    findings1 = set()
    findings2 = set()
    for f in ep1.key_findings or []:
        if isinstance(f, dict):
            findings1.add(f.get("finding", f.get("description", str(f))))
        else:
            findings1.add(str(f))
    for f in ep2.key_findings or []:
        if isinstance(f, dict):
            findings2.add(f.get("finding", f.get("description", str(f))))
        else:
            findings2.add(str(f))
    findings_added = findings2 - findings1
    findings_removed = findings1 - findings2
    findings_common = findings1 & findings2
    
    # Timeline analysis
    time_diff = None
    if ep1.created_at and ep2.created_at:
        delta = ep2.created_at - ep1.created_at
        time_diff = {
            "days": delta.days,
            "total_seconds": int(delta.total_seconds()),
            "direction": "later" if delta.total_seconds() > 0 else "earlier",
        }
    
    # Duration comparison
    duration_diff = None
    if ep1.duration_seconds and ep2.duration_seconds:
        diff = ep2.duration_seconds - ep1.duration_seconds
        pct_change = (diff / ep1.duration_seconds * 100) if ep1.duration_seconds else 0
        duration_diff = {
            "diff_seconds": diff,
            "pct_change": pct_change,
            "direction": "longer" if diff > 0 else "shorter",
        }
    
    # Effectiveness comparison
    eff_diff = None
    if ep1.effectiveness_score is not None and ep2.effectiveness_score is not None:
        diff = ep2.effectiveness_score - ep1.effectiveness_score
        eff_diff = {
            "diff": diff,
            "direction": "improved" if diff > 0 else "declined",
        }
    
    return {
        "id1": ep1.id,
        "id2": ep2.id,
        "root_cause_similarity": text_similarity(ep1.root_cause, ep2.root_cause),
        "summary_similarity": text_similarity(ep1.summary, ep2.summary),
        "same_service": ep1.service_name == ep2.service_name,
        "same_alert_type": ep1.alert_type == ep2.alert_type,
        "field_changes": field_changes,
        "skills": {
            "added": list(skills_added),
            "removed": list(skills_removed),
            "common": list(skills_common),
        },
        "steps": {
            "added": list(steps_added),
            "removed": list(steps_removed),
        },
        "findings": {
            "added": list(findings_added),
            "removed": list(findings_removed),
            "common": list(findings_common),
        },
        "timeline": time_diff,
        "duration": duration_diff,
        "effectiveness": eff_diff,
    }


def _display_diff(ep1, ep2, diff_data: dict, fields_only: bool):
    """Display a rich side-by-side diff view."""
    from rich.box import ROUNDED
    
    console.print()
    
    # Header showing what we're comparing
    console.print(Panel(
        f"[bold cyan]{ep1.id}[/] ↔ [bold cyan]{ep2.id}[/]",
        title="🔄 Investigation Comparison",
        subtitle=f"Root cause similarity: [{'green' if diff_data['root_cause_similarity'] > 0.5 else 'yellow'}]{diff_data['root_cause_similarity']:.0%}[/]",
        border_style="cyan",
    ))
    
    # Metadata comparison table
    console.print()
    meta_table = Table(
        title="📋 Metadata Comparison",
        show_header=True,
        header_style="bold",
        border_style="dim",
        box=ROUNDED,
    )
    meta_table.add_column("Field", style="dim", width=15)
    meta_table.add_column(f"{ep1.id[:8]}...", width=30)
    meta_table.add_column(f"{ep2.id[:8]}...", width=30)
    meta_table.add_column("Changed?", justify="center", width=10)
    
    # Add metadata rows
    meta_fields = [
        ("Alert Type", ep1.alert_type, ep2.alert_type),
        ("Service", ep1.service_name or "-", ep2.service_name or "-"),
        ("Severity", ep1.severity.upper(), ep2.severity.upper()),
        ("Status", "✓ Resolved" if ep1.resolved else "⋯ Open", "✓ Resolved" if ep2.resolved else "⋯ Open"),
        ("Created", ep1.created_at.strftime("%Y-%m-%d %H:%M") if ep1.created_at else "-",
                    ep2.created_at.strftime("%Y-%m-%d %H:%M") if ep2.created_at else "-"),
        ("Duration", _format_duration(ep1.duration_seconds), _format_duration(ep2.duration_seconds)),
        ("Effectiveness", f"{ep1.effectiveness_score:.0%}", f"{ep2.effectiveness_score:.0%}"),
    ]
    
    for field, val1, val2 in meta_fields:
        changed = val1 != val2
        change_icon = "[red]✗[/]" if changed else "[green]=[/]"
        style1 = "yellow" if changed else ""
        style2 = "yellow" if changed else ""
        meta_table.add_row(
            field,
            Text(str(val1), style=style1),
            Text(str(val2), style=style2),
            change_icon,
        )
    
    console.print(meta_table)
    
    if not fields_only:
        # Root cause comparison
        if ep1.root_cause or ep2.root_cause:
            console.print()
            console.print("[bold]🎯 Root Cause Comparison[/]")
            console.print()
            
            root_table = Table(show_header=True, header_style="bold yellow", border_style="yellow")
            root_table.add_column(f"{ep1.id[:8]}...", width=45)
            root_table.add_column(f"{ep2.id[:8]}...", width=45)
            
            root1 = ep1.root_cause or "[dim]Not identified[/]"
            root2 = ep2.root_cause or "[dim]Not identified[/]"
            root_table.add_row(root1, root2)
            
            console.print(root_table)
            
            similarity = diff_data["root_cause_similarity"]
            if similarity > 0.7:
                console.print(f"[green]  ✓ High similarity ({similarity:.0%}) - likely related issues[/]")
            elif similarity > 0.3:
                console.print(f"[yellow]  ⚠ Moderate similarity ({similarity:.0%}) - possibly related[/]")
            else:
                console.print(f"[dim]  ○ Low similarity ({similarity:.0%}) - different root causes[/]")
        
        # Skills comparison
        skills_diff = diff_data["skills"]
        if skills_diff["added"] or skills_diff["removed"] or skills_diff["common"]:
            console.print()
            console.print("[bold]🛠️ Skills Used[/]")
            console.print()
            
            if skills_diff["common"]:
                common_text = " • ".join(f"[cyan]{s}[/]" for s in skills_diff["common"])
                console.print(f"  [dim]Common:[/] {common_text}")
            if skills_diff["added"]:
                added_text = " • ".join(f"[green]+{s}[/]" for s in skills_diff["added"])
                console.print(f"  [dim]Added in {ep2.id[:8]}:[/] {added_text}")
            if skills_diff["removed"]:
                removed_text = " • ".join(f"[red]-{s}[/]" for s in skills_diff["removed"])
                console.print(f"  [dim]Removed from {ep2.id[:8]}:[/] {removed_text}")
        
        # Findings comparison
        findings_diff = diff_data["findings"]
        if findings_diff["added"] or findings_diff["removed"]:
            console.print()
            console.print("[bold]🔑 Key Findings Differences[/]")
            console.print()
            
            if findings_diff["added"]:
                console.print(f"  [green]+[/] [bold]New findings in {ep2.id[:8]}:[/]")
                for f in findings_diff["added"]:
                    console.print(f"    [green]+ {f[:80]}{'...' if len(f) > 80 else ''}[/]")
            if findings_diff["removed"]:
                console.print(f"  [red]-[/] [bold]Findings not in {ep2.id[:8]}:[/]")
                for f in findings_diff["removed"]:
                    console.print(f"    [red]- {f[:80]}{'...' if len(f) > 80 else ''}[/]")
        
        # Steps comparison
        steps_diff = diff_data["steps"]
        if steps_diff["added"] or steps_diff["removed"]:
            console.print()
            console.print("[bold]📝 Steps Taken Differences[/]")
            console.print()
            
            if steps_diff["added"]:
                console.print(f"  [green]+[/] [bold]New steps in {ep2.id[:8]}:[/]")
                for s in list(steps_diff["added"])[:5]:
                    console.print(f"    [green]+ {s[:60]}{'...' if len(s) > 60 else ''}[/]")
                if len(steps_diff["added"]) > 5:
                    console.print(f"    [dim]... and {len(steps_diff['added']) - 5} more[/]")
            if steps_diff["removed"]:
                console.print(f"  [red]-[/] [bold]Steps not in {ep2.id[:8]}:[/]")
                for s in list(steps_diff["removed"])[:5]:
                    console.print(f"    [red]- {s[:60]}{'...' if len(s) > 60 else ''}[/]")
                if len(steps_diff["removed"]) > 5:
                    console.print(f"    [dim]... and {len(steps_diff['removed']) - 5} more[/]")
    
    # Timeline analysis
    timeline = diff_data["timeline"]
    duration = diff_data["duration"]
    effectiveness = diff_data["effectiveness"]
    
    if timeline or duration or effectiveness:
        console.print()
        console.print("[bold]📊 Timeline & Performance[/]")
        console.print()
        
        if timeline:
            days = abs(timeline["days"])
            direction = timeline["direction"]
            time_desc = f"{days} days" if days > 0 else f"{abs(timeline['total_seconds']) // 3600} hours"
            console.print(f"  ⏱️  Investigation {ep2.id[:8]} occurred [cyan]{time_desc}[/] [dim]{direction}[/]")
        
        if duration:
            diff_s = abs(duration["diff_seconds"])
            direction = duration["direction"]
            pct = abs(duration["pct_change"])
            duration_str = _format_duration(diff_s)
            style = "green" if direction == "shorter" else "red"
            console.print(f"  ⏳  Duration: [{style}]{duration_str} {direction}[/] ({pct:.0f}% change)")
        
        if effectiveness:
            diff = effectiveness["diff"]
            direction = effectiveness["direction"]
            style = "green" if direction == "improved" else "red"
            console.print(f"  📈  Effectiveness: [{style}]{abs(diff):.0%} {direction}[/]")
    
    # Summary panel
    console.print()
    summary_lines = []
    
    if diff_data["same_alert_type"] and diff_data["same_service"]:
        summary_lines.append("[green]✓[/] Same service and alert type - [bold]recurring incident pattern[/]")
    elif diff_data["same_alert_type"]:
        summary_lines.append("[yellow]⚠[/] Same alert type, different service - [bold]cross-service pattern[/]")
    elif diff_data["same_service"]:
        summary_lines.append("[yellow]⚠[/] Same service, different alert type - [bold]service-specific issues[/]")
    else:
        summary_lines.append("[dim]○[/] Different service and alert type")
    
    if diff_data["root_cause_similarity"] > 0.5:
        summary_lines.append("[green]✓[/] Similar root causes - consider common remediation")
    
    num_field_changes = len(diff_data["field_changes"])
    if num_field_changes == 0:
        summary_lines.append("[green]✓[/] Core fields unchanged")
    else:
        summary_lines.append(f"[yellow]⚠[/] {num_field_changes} field(s) changed")
    
    console.print(Panel(
        "\n".join(summary_lines),
        title="[bold]Summary[/]",
        border_style="dim",
    ))
    
    console.print()
    console.print("[dim]Tip: Use [cyan]autosre history show <id>[/] to view full investigation details[/]")
    console.print()


@app.callback(invoke_without_command=True)
def history_callback(ctx: typer.Context):
    """
    Browse past incident investigations.
    
    AutoSRE maintains episodic memory of all investigations. Use this
    command to review past incidents, search for similar issues, and
    export reports.
    
    [bold]Quick Examples:[/]
        autosre history list                 # List recent investigations
        autosre history show <id>            # View specific investigation
        autosre history search "redis"       # Search investigations
        autosre history diff <id1> <id2>     # Compare two investigations
        autosre history export <id>          # Export to file
        autosre history stats                # Show statistics
    """
    if ctx.invoked_subcommand is None:
        # Show help if no subcommand given
        console.print(ctx.get_help())
