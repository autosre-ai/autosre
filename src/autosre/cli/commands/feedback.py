"""AutoSRE feedback commands - Manage learning and feedback."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


@click.group()
def feedback():
    """Manage feedback and learning.
    
    AutoSRE learns from feedback to improve over time. Submit
    feedback on analyses, view learning metrics, and manage
    the feedback loop.
    
    \b
    Examples:
      $ autosre feedback submit -i INC-123 --correct
      $ autosre feedback report
      $ autosre feedback export
    """
    pass


@feedback.command("submit")
@click.option("--incident", "-i", required=True, help="Incident ID")
@click.option("--correct", "-c", is_flag=True, help="Agent analysis was correct")
@click.option("--incorrect", is_flag=True, help="Agent analysis was incorrect")
@click.option("--partial", is_flag=True, help="Partially correct")
@click.option("--actual-cause", help="Actual root cause (if different)")
@click.option("--notes", "-n", help="Additional notes")
def feedback_submit(incident: str, correct: bool, incorrect: bool, partial: bool, actual_cause: str, notes: str):
    """Submit feedback on an agent analysis.
    
    Feedback helps AutoSRE learn and improve. Mark analyses as
    correct, incorrect, or partially correct with optional notes.
    
    \b
    Examples:
      $ autosre feedback submit -i INC-123 --correct
      $ autosre feedback submit -i INC-123 --incorrect --actual-cause "DNS timeout"
      $ autosre feedback submit -i INC-456 --partial --notes "Right service, wrong cause"
    """
    from autosre.feedback import FeedbackStore, Feedback
    from datetime import datetime, timezone
    
    # Determine rating
    if sum([correct, incorrect, partial]) != 1:
        console.print("[red]Please specify exactly one of: --correct, --incorrect, --partial[/red]")
        return
    
    if correct:
        rating = "correct"
    elif incorrect:
        rating = "incorrect"
    else:
        rating = "partial"
    
    console.print()
    
    try:
        store = FeedbackStore()
        
        feedback_obj = Feedback(
            incident_id=incident,
            rating=rating,
            actual_root_cause=actual_cause,
            notes=notes,
            submitted_at=datetime.now(timezone.utc),
        )
        
        store.save(feedback_obj)
        
        console.print(Panel.fit(
            f"[bold green]✓ Feedback submitted[/bold green]\n\n"
            f"Incident: {incident}\n"
            f"Rating: {rating}\n"
            + (f"Notes: {notes}" if notes else ""),
            border_style="green"
        ))
        
    except Exception as e:
        console.print(f"[red]Error submitting feedback: {e}[/red]")
    
    console.print()


@feedback.command("report")
@click.option("--days", "-d", default=30, help="Number of days to include")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def feedback_report(days: int, as_json: bool):
    """Show feedback summary and trends.
    
    Displays statistics on agent accuracy based on submitted
    feedback.
    
    \b
    Examples:
      $ autosre feedback report
      $ autosre feedback report --days 7
    """
    from autosre.feedback import FeedbackStore
    
    console.print()
    
    try:
        store = FeedbackStore()
        stats = store.get_stats(days=days)
        
        if as_json:
            console.print_json(data=stats)
            return
        
        console.print(Panel.fit(
            f"[bold cyan]📊 Feedback Report ({days} days)[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
        
        if stats["total"] == 0:
            console.print("[dim]No feedback submitted yet[/dim]")
            console.print()
            return
        
        # Summary table
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        
        total = stats["total"]
        correct = stats["correct"]
        incorrect = stats["incorrect"]
        partial = stats["partial"]
        
        accuracy = (correct + partial * 0.5) / total * 100 if total > 0 else 0
        
        table.add_row("Total Analyses", f"[cyan]{total}[/cyan]")
        table.add_row("Correct", f"[green]{correct}[/green] ({correct/total*100:.0f}%)")
        table.add_row("Partial", f"[yellow]{partial}[/yellow] ({partial/total*100:.0f}%)")
        table.add_row("Incorrect", f"[red]{incorrect}[/red] ({incorrect/total*100:.0f}%)")
        table.add_row("Accuracy Score", f"[bold]{accuracy:.1f}%[/bold]")
        
        console.print(table)
        console.print()
        
        # Trend
        if stats.get("trend"):
            trend = stats["trend"]
            if trend > 0:
                console.print(f"[green]↑ Improving (+{trend:.1f}% vs previous period)[/green]")
            elif trend < 0:
                console.print(f"[red]↓ Declining ({trend:.1f}% vs previous period)[/red]")
            else:
                console.print("[dim]→ Stable[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
    
    console.print()


@feedback.command("list")
@click.option("--limit", "-l", default=20, help="Number of entries")
@click.option("--rating", "-r", type=click.Choice(["correct", "incorrect", "partial"]), help="Filter by rating")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def feedback_list(limit: int, rating: str, as_json: bool):
    """List submitted feedback.
    
    Shows recent feedback entries with details.
    
    \b
    Examples:
      $ autosre feedback list
      $ autosre feedback list --rating incorrect
    """
    from autosre.feedback import FeedbackStore
    
    console.print()
    
    try:
        store = FeedbackStore()
        entries = store.list_feedback(limit=limit, rating=rating)
        
        if as_json:
            console.print_json(data=[e.model_dump() for e in entries])
            return
        
        if not entries:
            console.print("[dim]No feedback entries found[/dim]")
            console.print()
            return
        
        table = Table(title="📝 Feedback Entries", box=box.ROUNDED)
        table.add_column("Incident", style="cyan", no_wrap=True)
        table.add_column("Rating", justify="center")
        table.add_column("Notes")
        table.add_column("Submitted", style="dim")
        
        rating_styles = {
            "correct": "[green]✓ Correct[/]",
            "incorrect": "[red]✗ Incorrect[/]",
            "partial": "[yellow]◐ Partial[/]",
        }
        
        for entry in entries:
            rating_display = rating_styles.get(entry.rating, entry.rating)
            notes = entry.notes[:40] + "..." if entry.notes and len(entry.notes) > 40 else (entry.notes or "—")
            
            table.add_row(
                entry.incident_id,
                rating_display,
                notes,
                entry.submitted_at.strftime("%Y-%m-%d %H:%M"),
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing feedback: {e}[/red]")
    
    console.print()


@feedback.command("export")
@click.option("--output", "-o", default="feedback-export.json", help="Output file")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "csv"]), default="json", help="Export format")
def feedback_export(output: str, fmt: str):
    """Export feedback data.
    
    Exports all feedback data for analysis or backup.
    
    \b
    Examples:
      $ autosre feedback export
      $ autosre feedback export -o backup.csv --format csv
    """
    from autosre.feedback import FeedbackStore
    import json
    import csv
    
    console.print()
    
    try:
        store = FeedbackStore()
        entries = store.list_feedback(limit=10000)  # Get all
        
        if fmt == "json":
            with open(output, "w") as f:
                json.dump([e.model_dump() for e in entries], f, indent=2, default=str)
        else:
            with open(output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["incident_id", "rating", "actual_root_cause", "notes", "submitted_at"])
                for entry in entries:
                    writer.writerow([
                        entry.incident_id,
                        entry.rating,
                        entry.actual_root_cause,
                        entry.notes,
                        entry.submitted_at.isoformat(),
                    ])
        
        console.print(f"[green]✓[/] Exported {len(entries)} entries to {output}")
        
    except Exception as e:
        console.print(f"[red]Error exporting feedback: {e}[/red]")
    
    console.print()
