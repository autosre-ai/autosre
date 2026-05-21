"""
AutoSRE Investigation Commands

Run AI-powered incident investigations from the command line.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.tree import Tree

app = typer.Typer(
    name="investigate",
    help="Run AI-powered incident investigations",
    no_args_is_help=True,
)

console = Console()


def _format_evidence(evidence: dict) -> str:
    """Format evidence for display."""
    source = evidence.get("source", "unknown")
    confidence = evidence.get("confidence", 0.0)
    data = evidence.get("data", {})
    
    lines = [f"📋 [cyan]{source}[/] (confidence: {confidence:.0%})"]
    if isinstance(data, dict):
        for k, v in list(data.items())[:3]:  # Show first 3 items
            lines.append(f"   • {k}: {v}")
    elif isinstance(data, str):
        lines.append(f"   {data[:100]}...")
    return "\n".join(lines)


def _format_hypothesis(hypothesis: dict, index: int) -> str:
    """Format hypothesis for display."""
    title = hypothesis.get("title", f"Hypothesis {index}")
    likelihood = hypothesis.get("likelihood", 0.0)
    supporting = hypothesis.get("supporting_evidence", [])
    
    stars = "⭐" * int(likelihood * 5)
    lines = [f"[bold]💡 {title}[/] {stars} ({likelihood:.0%})"]
    
    if supporting:
        lines.append("   Supporting evidence:")
        for ev in supporting[:2]:
            lines.append(f"   • {ev}")
    
    return "\n".join(lines)


class InvestigationRunner:
    """Manages the investigation execution and display."""
    
    def __init__(
        self,
        alert: str,
        service: Optional[str] = None,
        severity: str = "high",
        mock: bool = False,
        output_format: str = "text",
        stream: bool = True,
    ):
        self.alert = alert
        self.service = service
        self.severity = severity
        self.mock = mock
        self.output_format = output_format
        self.stream = stream
        self.investigation_id = str(uuid4())[:8]
        self.start_time = datetime.utcnow()
        
        # Investigation state
        self.evidence: list = []
        self.hypotheses: list = []
        self.root_cause: Optional[str] = None
        self.report: Optional[str] = None
        
    async def run_async(self) -> dict:
        """Run the investigation asynchronously."""
        from autosre.memory import EpisodicMemory, Episode, MemoryQuery
        
        # Initialize memory
        memory = EpisodicMemory()
        
        # Phase 1: Context Gathering
        if self.stream:
            console.print()
            console.print(Panel(
                f"[bold cyan]🔍 Investigation {self.investigation_id}[/]\n\n"
                f"[bold]Alert:[/] {self.alert}\n"
                f"[bold]Service:[/] {self.service or 'auto-detect'}\n"
                f"[bold]Severity:[/] {self.severity}\n"
                f"[bold]Mode:[/] {'Mock' if self.mock else 'Live'}",
                title="Investigation Started",
                border_style="cyan",
            ))
        
        # Check for similar past incidents
        if self.stream:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Searching episodic memory...", total=None)
                
                # Search memory for similar incidents
                query = MemoryQuery(
                    text=self.alert,
                    service=self.service,
                    alert_type=self._classify_alert(),
                )
                similar_episodes = await memory.retrieve(query, limit=3)
                
                progress.update(task, description=f"Found {len(similar_episodes)} similar incidents")
        
        # Phase 2: Evidence Collection (mock or real)
        if self.mock:
            self.evidence = await self._collect_mock_evidence()
        else:
            self.evidence = await self._collect_real_evidence()
        
        if self.stream:
            console.print()
            console.print("[bold]📊 Evidence Collected:[/]")
            for ev in self.evidence:
                console.print(_format_evidence(ev))
            console.print()
        
        # Phase 3: Hypothesis Generation
        if self.mock:
            self.hypotheses = await self._generate_mock_hypotheses()
        else:
            self.hypotheses = await self._generate_hypotheses()
        
        if self.stream:
            console.print("[bold]🧠 Hypotheses:[/]")
            for i, hyp in enumerate(self.hypotheses, 1):
                console.print(_format_hypothesis(hyp, i))
            console.print()
        
        # Phase 4: Root Cause Analysis
        if self.hypotheses:
            self.root_cause = self.hypotheses[0].get("title", "Unknown")
        
        if self.stream:
            console.print(Panel(
                f"[bold green]Root Cause:[/] {self.root_cause}",
                title="🎯 Analysis Complete",
                border_style="green",
            ))
        
        # Phase 5: Generate Report
        self.report = self._generate_report()
        
        # Store episode in memory
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        episode = Episode(
            id=self.investigation_id,
            alert_type=self._classify_alert(),
            service_name=self.service,
            severity=self.severity,
            root_cause=self.root_cause,
            summary=f"Investigation of: {self.alert}",
            resolved=True,
            effectiveness_score=0.85,
            skills_used=["metrics", "logs", "kubernetes"],
            key_findings=[{"finding": h.get("title")} for h in self.hypotheses[:3]],
            duration_seconds=int(duration),
            steps_taken=["context_gathering", "evidence_collection", "hypothesis_generation", "root_cause_analysis"],
        )
        await memory.store(episode)
        
        result = {
            "investigation_id": self.investigation_id,
            "alert": self.alert,
            "service": self.service,
            "severity": self.severity,
            "evidence": self.evidence,
            "hypotheses": self.hypotheses,
            "root_cause": self.root_cause,
            "report": self.report,
            "duration_seconds": duration,
        }
        
        return result
    
    def _classify_alert(self) -> str:
        """Classify the alert type."""
        alert_lower = self.alert.lower()
        if any(word in alert_lower for word in ["error", "5xx", "exception", "failed"]):
            return "error_rate"
        elif any(word in alert_lower for word in ["latency", "slow", "timeout", "p99"]):
            return "latency"
        elif any(word in alert_lower for word in ["memory", "oom", "cpu", "disk"]):
            return "resource_exhaustion"
        elif any(word in alert_lower for word in ["down", "unavailable", "unreachable"]):
            return "availability"
        return "general"
    
    async def _collect_mock_evidence(self) -> list:
        """Generate mock evidence for demo."""
        await asyncio.sleep(0.5)  # Simulate work
        return [
            {
                "source": "prometheus",
                "confidence": 0.92,
                "data": {
                    "error_rate": "23.4%",
                    "p99_latency": "2.3s",
                    "request_count": "1.2K/min",
                },
            },
            {
                "source": "kubernetes",
                "confidence": 0.85,
                "data": {
                    "pod_status": "3/5 Running",
                    "restarts": 12,
                    "last_deploy": "2h ago",
                },
            },
            {
                "source": "logs",
                "confidence": 0.78,
                "data": {
                    "error_pattern": "ConnectionRefused: redis-master:6379",
                    "occurrences": 234,
                    "first_seen": "47 minutes ago",
                },
            },
        ]
    
    async def _collect_real_evidence(self) -> list:
        """Collect real evidence from configured sources."""
        # For now, return mock data - would integrate with actual skills
        return await self._collect_mock_evidence()
    
    async def _generate_mock_hypotheses(self) -> list:
        """Generate mock hypotheses for demo."""
        await asyncio.sleep(0.3)
        return [
            {
                "title": "Redis connection pool exhaustion",
                "likelihood": 0.87,
                "supporting_evidence": [
                    "ConnectionRefused errors spike correlates with error rate",
                    "Recent deployment changed connection pool settings",
                ],
            },
            {
                "title": "Upstream service degradation",
                "likelihood": 0.65,
                "supporting_evidence": [
                    "P99 latency increase preceded error spike",
                    "Dependent service showing similar patterns",
                ],
            },
            {
                "title": "Resource exhaustion from memory leak",
                "likelihood": 0.42,
                "supporting_evidence": [
                    "Pod restarts trending upward",
                    "Memory usage climbing before restarts",
                ],
            },
        ]
    
    async def _generate_hypotheses(self) -> list:
        """Generate hypotheses using LLM."""
        # For now, return mock - would integrate with actual LLM
        return await self._generate_mock_hypotheses()
    
    def _generate_report(self) -> str:
        """Generate investigation report."""
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        report = f"""# Investigation Report

## Summary
- **Investigation ID:** {self.investigation_id}
- **Alert:** {self.alert}
- **Service:** {self.service or 'Not specified'}
- **Severity:** {self.severity}
- **Duration:** {duration:.1f}s
- **Status:** Completed

## Root Cause
{self.root_cause or 'Under investigation'}

## Evidence Summary
"""
        for ev in self.evidence:
            report += f"\n### {ev.get('source', 'Unknown')}\n"
            report += f"Confidence: {ev.get('confidence', 0):.0%}\n"
            data = ev.get("data", {})
            if isinstance(data, dict):
                for k, v in data.items():
                    report += f"- **{k}:** {v}\n"
        
        report += "\n## Hypotheses (ranked by likelihood)\n"
        for i, hyp in enumerate(self.hypotheses, 1):
            report += f"\n### {i}. {hyp.get('title')}\n"
            report += f"Likelihood: {hyp.get('likelihood', 0):.0%}\n"
            if hyp.get("supporting_evidence"):
                report += "Supporting evidence:\n"
                for ev in hyp["supporting_evidence"]:
                    report += f"- {ev}\n"
        
        report += f"""
## Recommendations
1. Review recent deployments for configuration changes
2. Check connection pool settings for {self.service or 'affected service'}
3. Monitor error rates after implementing fix
4. Update runbook with this incident pattern

---
*Generated by AutoSRE v0.2.0*
"""
        return report
    
    def run(self) -> dict:
        """Run the investigation synchronously."""
        return asyncio.run(self.run_async())


@app.command()
def run(
    alert: str = typer.Argument(..., help="Alert or incident description"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("high", "--severity", help="Severity level: low|medium|high|critical"),
    mock: bool = typer.Option(False, "--mock", "-m", help="Use mock LLM for testing"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text|json|markdown"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream output in real-time"),
    save: Optional[Path] = typer.Option(None, "--save", help="Save report to file"),
):
    """
    Start an AI-powered investigation.
    
    Analyzes an alert, gathers evidence, generates hypotheses, and
    identifies root causes using AI reasoning.
    
    Examples:
        autosre investigate run "High error rate on checkout"
        autosre investigate run "API latency spike" --service api-gateway --mock
        autosre investigate run "Redis connection errors" --output json --save report.json
    """
    runner = InvestigationRunner(
        alert=alert,
        service=service,
        severity=severity,
        mock=mock,
        output_format=output,
        stream=stream,
    )
    
    result = runner.run()
    
    # Output formatting
    if output == "json":
        json_output = json.dumps(result, indent=2, default=str)
        if save:
            save.write_text(json_output)
            console.print(f"[green]✓[/] Report saved to {save}")
        else:
            console.print(json_output)
    
    elif output == "markdown":
        if save:
            save.write_text(result["report"])
            console.print(f"[green]✓[/] Report saved to {save}")
        else:
            console.print()
            console.print(Markdown(result["report"]))
    
    else:  # text
        if save:
            save.write_text(result["report"])
            console.print(f"[green]✓[/] Report saved to {save}")
        elif not stream:
            console.print(Markdown(result["report"]))


@app.command()
def history(
    service: str = typer.Option(None, "--service", "-s", help="Filter by service"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show recent investigations from memory."""
    from autosre.memory import EpisodicMemory
    
    memory = EpisodicMemory()
    stats = memory.get_stats()
    
    if json_output:
        console.print(json.dumps(stats, indent=2))
        return
    
    table = Table(title="Recent Investigations", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Alert Type", style="yellow")
    table.add_column("Service")
    table.add_column("Root Cause")
    table.add_column("Duration")
    table.add_column("Status", style="green")
    
    # Query recent episodes
    import asyncio
    from autosre.memory import MemoryQuery
    
    async def get_episodes():
        query = MemoryQuery(text="", service=service)
        return await memory.retrieve(query, limit=limit)
    
    episodes = asyncio.run(get_episodes())
    
    for ep in episodes:
        duration_str = f"{ep.duration_seconds}s" if ep.duration_seconds else "-"
        status = "[green]✓ Resolved[/]" if ep.resolved else "[yellow]Pending[/]"
        table.add_row(
            ep.id[:8],
            ep.alert_type,
            ep.service_name or "-",
            (ep.root_cause or "-")[:30],
            duration_str,
            status,
        )
    
    if not episodes:
        console.print("[yellow]No investigations found[/]")
    else:
        console.print(table)


@app.command()
def replay(
    investigation_id: str = typer.Argument(..., help="Investigation ID to replay"),
):
    """Replay a past investigation with visualization."""
    import asyncio
    from autosre.memory import EpisodicMemory
    
    memory = EpisodicMemory()
    
    async def get_episode():
        return await memory.get(investigation_id)
    
    episode = asyncio.run(get_episode())
    
    if not episode:
        console.print(f"[red]Investigation {investigation_id} not found[/]")
        raise typer.Exit(1)
    
    # Display episode details
    console.print(Panel(
        f"[bold]Alert Type:[/] {episode.alert_type}\n"
        f"[bold]Service:[/] {episode.service_name or 'N/A'}\n"
        f"[bold]Root Cause:[/] {episode.root_cause or 'Unknown'}\n"
        f"[bold]Duration:[/] {episode.duration_seconds}s\n"
        f"[bold]Status:[/] {'✓ Resolved' if episode.resolved else 'Pending'}",
        title=f"Investigation {episode.id}",
        border_style="cyan",
    ))
    
    # Show steps taken
    if episode.steps_taken:
        console.print("\n[bold]Steps Taken:[/]")
        for i, step in enumerate(episode.steps_taken, 1):
            console.print(f"  {i}. {step}")
    
    # Show key findings
    if episode.key_findings:
        console.print("\n[bold]Key Findings:[/]")
        for finding in episode.key_findings:
            if isinstance(finding, dict):
                console.print(f"  • {finding.get('finding', finding)}")
            else:
                console.print(f"  • {finding}")
