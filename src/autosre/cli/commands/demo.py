"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              ⚠️  DEMO MODE ONLY ⚠️                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This module contains DEMO/SIMULATION commands for testing and showcasing.   ║
║                                                                              ║
║  ALL DATA IN THIS MODULE IS SIMULATED - NOT REAL INCIDENTS!                  ║
║                                                                              ║
║  DO NOT use these commands for real incident investigation.                  ║
║  For real investigations, use: `autosre investigate`                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

AutoSRE Demo Commands

Run demo investigations and seed test data using SIMULATED data.

WARNING: This is for demonstration purposes only. All scenarios and data
are synthetic and do not represent real incidents or infrastructure.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.status import Status
from rich.table import Table

from autosre.scenarios import load_scenario

app = typer.Typer(
    name="demo",
    help="[DEMO MODE] Demo scenarios with SIMULATED data - NOT for real incidents!",
    no_args_is_help=True,
)

console = Console()

# Big warning banner for demo mode
DEMO_WARNING_BANNER = """
[bold yellow]╔══════════════════════════════════════════════════════════════════╗[/]
[bold yellow]║[/] [bold red]⚠️  DEMO MODE - SIMULATED DATA ONLY ⚠️[/]                            [bold yellow]║[/]
[bold yellow]╠══════════════════════════════════════════════════════════════════╣[/]
[bold yellow]║[/] All data shown is synthetic and for demonstration purposes.    [bold yellow]║[/]
[bold yellow]║[/] This does NOT represent real incidents or infrastructure.      [bold yellow]║[/]
[bold yellow]║[/]                                                                [bold yellow]║[/]
[bold yellow]║[/] [bold white]For real investigations, use:[/] [cyan]autosre investigate[/]            [bold yellow]║[/]
[bold yellow]╚══════════════════════════════════════════════════════════════════╝[/]
"""


def _print_demo_warning():
    """Print the demo mode warning banner."""
    console.print(DEMO_WARNING_BANNER)


# Epic ASCII art logo for the demo
AUTOSRE_LOGO = """
[bold cyan]
    ╔═══════════════════════════════════════════════════════════════════╗
    ║     █████╗ ██╗   ██╗████████╗ ██████╗ ███████╗██████╗ ███████╗    ║
    ║    ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔════╝██╔══██╗██╔════╝    ║
    ║    ███████║██║   ██║   ██║   ██║   ██║███████╗██████╔╝█████╗      ║
    ║    ██╔══██║██║   ██║   ██║   ██║   ██║╚════██║██╔══██╗██╔══╝      ║
    ║    ██║  ██║╚██████╔╝   ██║   ╚██████╔╝███████║██║  ██║███████╗    ║
    ║    ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝    ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║         [white]AI-Powered Incident Investigation[/white]         [yellow]v0.1.0[/yellow]            ║
    ╚═══════════════════════════════════════════════════════════════════╝
[/]
"""


def _print_logo():
    """Print the epic ASCII art logo."""
    console.print(AUTOSRE_LOGO)


class DemoInvestigationRunner:
    """
    DEMO ONLY: Simulated investigation runner that uses fake data.
    
    This class provides a completely simulated investigation experience
    WITHOUT connecting to any real infrastructure.
    
    For real investigations, use the InvestigationRunner from investigate.py.
    """
    
    def __init__(
        self,
        alert: str,
        service: str,
        severity: str,
        output_format: str = "text",
        stream: bool = True,
        scenario_id: str | None = None,
        scenario_data: dict[str, Any] | None = None,
    ):
        self.alert = alert
        self.service = service
        self.severity = severity
        self.output_format = output_format
        self.stream = stream
        self.investigation_id = f"demo-{str(uuid4())[:8]}"
        self.scenario_id = scenario_id
        
        # Load scenario data from JSON file if scenario_id provided
        if scenario_data:
            self.scenario = scenario_data
        elif scenario_id:
            try:
                self.scenario = load_scenario(scenario_id)
            except FileNotFoundError:
                self.scenario = None
        else:
            self.scenario = None
    
    def _phase_context_gathering(self):
        """Phase 1: Simulate context gathering with service topology."""
        import time
        from rich.tree import Tree
        from rich.status import Status
        
        with Status("[bold cyan]🔍 Phase 1: Gathering Context...[/]", spinner="dots", console=console):
            time.sleep(0.8)
        
        # Show simulated service topology
        tree = Tree(f"[bold]{self.service}[/] [dim](target)[/]")
        tree.add("[dim]→ redis-cache[/]")
        tree.add("[dim]→ postgresql-db[/]")
        tree.add("[dim]→ payment-provider (external)[/]")
        
        console.print(Panel(
            tree,
            title="[bold]📊 Service Context[/]",
            border_style="cyan",
            padding=(0, 2),
        ))
        console.print()
    
    def _phase_evidence_collection(self):
        """Phase 2: Simulate evidence collection with live metrics."""
        import time
        from rich.table import Table
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Phase 2: Collecting Evidence...", total=100)
            
            for i in range(10):
                time.sleep(0.1)
                progress.update(task, advance=10)
        
        # Show simulated metrics
        table = Table(title="[bold]📈 Collected Metrics[/]", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")
        
        table.add_row("Error Rate", "23.4%", "[red]⚠ HIGH[/]")
        table.add_row("P99 Latency", "2.3s", "[yellow]⚠ ELEVATED[/]")
        table.add_row("CPU Usage", "78%", "[yellow]⚠ ELEVATED[/]")
        table.add_row("Memory Usage", "45%", "[green]✓ OK[/]")
        table.add_row("Active Connections", "847/100", "[red]⚠ EXHAUSTED[/]")
        
        console.print(table)
        console.print()
    
    def _phase_hypothesis_generation(self):
        """Phase 3: Simulate AI hypothesis generation with streaming effect."""
        import time
        
        with Status("[bold magenta]🤖 Phase 3: Generating Hypotheses...[/]", spinner="dots", console=console):
            time.sleep(0.5)
        
        hypotheses = [
            ("Redis connection pool exhaustion", 87),
            ("Database query timeout cascade", 45),
            ("Memory pressure from traffic spike", 32),
            ("Network partition or DNS issues", 12),
        ]
        
        console.print("[bold]🧠 AI-Generated Hypotheses:[/]")
        for hyp, confidence in hypotheses:
            bar_width = int(confidence / 5)
            bar = "█" * bar_width + "░" * (20 - bar_width)
            color = "green" if confidence > 70 else "yellow" if confidence > 40 else "dim"
            console.print(f"  [{color}]{bar}[/] {confidence}% - {hyp}")
            time.sleep(0.15)
        console.print()
    
    def _phase_root_cause_analysis(self) -> tuple:
        """Phase 4: Simulate root cause analysis with confidence animation."""
        import time
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[red]Phase 4: Analyzing Root Cause...", total=100)
            
            for i in range(10):
                time.sleep(0.08)
                progress.update(task, advance=10)
        
        # Return placeholder - actual values set in run() method
        return ("", [])
    
    def _phase_report_generation(self):
        """Phase 5: Simulate report generation."""
        import time
        
        with Status("[bold green]📝 Phase 5: Generating Report...[/]", spinner="dots", console=console):
            time.sleep(0.4)
        
    def run(self) -> dict:
        """Run a SIMULATED investigation (no real infrastructure)."""
        import time
        from rich.rule import Rule
        from rich.live import Live
        from rich.text import Text
        
        if not self.stream:
            # Quiet/benchmark mode - just a quick sleep
            time.sleep(0.1)
            root_cause = self.scenario["root_cause"] if self.scenario else "Redis connection pool exhaustion due to traffic spike"
            return {
                "investigation_id": self.investigation_id,
                "duration_seconds": 0.1,
                "root_cause": root_cause,
                "recommendations": [],
                "simulated": True,
            }
        
        start_time = time.time()
        
        # Epic logo
        _print_logo()
        
        # Dramatic "INITIATING" sequence
        console.print()
        init_steps = [
            ("🔐 Authenticating with infrastructure...", "green"),
            ("📡 Connecting to telemetry sources...", "cyan"),
            ("🧠 Loading AI investigation model...", "magenta"),
            ("⚡ Ready.", "bold green"),
        ]
        for step, color in init_steps:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn(f"[{color}]{step}[/]"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("", total=None)
                time.sleep(0.08)  # Snappy init sequence
            console.print(f"  [green]✓[/] {step}")
        
        console.print()
        console.print(Rule("[bold cyan]🔍 INVESTIGATION STARTED[/]", style="cyan"))
        console.print()
        
        # Investigation ID badge
        console.print(Panel(
            f"[bold white on blue] ID: {self.investigation_id} [/]  "
            f"[bold white on red] {self.severity.upper()} [/]  "
            f"[bold white on green] {self.service} [/]",
            title="[bold]Investigation Session[/]",
            border_style="bright_blue",
            padding=(0, 2),
        ))
        console.print()
        
        # Phase 1: Context Gathering with service topology visualization
        self._phase_context_gathering()
        
        # Phase 2: Evidence Collection with live metrics
        self._phase_evidence_collection()
        
        # Phase 3: AI Hypothesis Generation with streaming effect
        self._phase_hypothesis_generation()
        
        # Phase 4: Root Cause Analysis with confidence animation
        root_cause, recommendations = self._phase_root_cause_analysis()
        
        # Phase 5: Report Generation
        self._phase_report_generation()
        
        duration_seconds = time.time() - start_time
        
        # Dramatic confidence build-up before reveal
        from rich.live import Live
        from rich.text import Text
        
        console.print()
        console.print("[bold]🎯 Calculating Confidence...[/]")
        
        # Dramatic percentage counter with snappy acceleration
        with Live(Text(""), console=console, refresh_per_second=60, transient=True) as live:
            # Even faster: only key frames for maximum impact
            keyframes = [0, 25, 50, 70, 85, 92]
            for pct in keyframes:
                bar_filled = int(pct / 5)
                bar_empty = 20 - bar_filled
                color = "yellow" if pct < 60 else "cyan" if pct < 80 else "green"
                bar_text = Text()
                bar_text.append("   [", style="dim")
                bar_text.append("█" * bar_filled, style=color)
                bar_text.append("░" * bar_empty, style="dim")
                bar_text.append(f"] {pct}%", style=color)
                live.update(bar_text)
                # Very snappy - just enough to see the animation
                time.sleep(0.08)
        
        # Final flash effect - show 92% with emphasis
        console.print(f"   [bold green]████████████████████[/] [bold white on green] 92% [/] [bold green]HIGH CONFIDENCE ✨[/]")
        
        # Show impressive findings panel with dramatic effect
        console.print()
        
        # Flash effect for root cause reveal
        import os
        if os.environ.get("TERM"):
            # Terminal bell for dramatic effect (optional)
            pass
        
        console.print(Rule("[bold green]✅ ROOT CAUSE IDENTIFIED[/]", style="green"))
        console.print()
        
        # Root cause panel with pulsing border effect
        console.print(Panel(
            f"[bold white on red] 🎯 {root_cause} [/]",
            title="[bold blink]ROOT CAUSE FOUND[/]",
            border_style="bold red",
            padding=(1, 2),
        ))
        
        # Evidence summary - use scenario data if available
        if self.scenario and "evidence_summary" in self.scenario:
            es = self.scenario["evidence_summary"]
            evidence_text = (
                "[bold]Key Evidence:[/]\n"
                f"• Error rate spike: [yellow]{es.get('error_rate', 'N/A')}[/] (threshold: {es.get('threshold', 'N/A')})\n"
                f"• First occurrence: [cyan]{es.get('first_occurrence', 'N/A')} UTC[/]\n"
                f"• Affected pods: [cyan]{es.get('affected_pods', 'N/A')}[/]\n"
                f"• Correlation: [green]{es.get('correlation_confidence', 'N/A')} confidence[/]"
            )
        else:
            evidence_text = (
                "[bold]Key Evidence:[/]\n"
                f"• Error rate spike: [yellow]23% 5xx errors[/] (threshold: 1%)\n"
                f"• First occurrence: [cyan]14:32:17 UTC[/]\n"
                f"• Affected pods: [cyan]{self.service}-7d4f8b6c9-xxxxx[/] (3 replicas)\n"
                f"• Correlation: [green]92% confidence[/] with traffic spike"
            )
        console.print(Panel(evidence_text, title="📊 Evidence Summary", border_style="yellow"))
        
        # Recommendations
        rec_text = "\n".join([f"[green]{i+1}.[/] {rec}" for i, rec in enumerate(recommendations)])
        console.print(Panel(rec_text, title="💡 Recommended Actions", border_style="green"))
        
        # Timeline - use scenario data if available
        if self.scenario and "timeline" in self.scenario:
            timeline_lines = []
            for event in self.scenario["timeline"]:
                time_str = event["time"]
                event_text = event["event"]
                if event.get("success"):
                    timeline_lines.append(f"[dim]{time_str}[/] [green]{event_text}[/]")
                elif event.get("highlight"):
                    timeline_lines.append(f"[dim]{time_str}[/] [red]{event_text}[/]")
                else:
                    timeline_lines.append(f"[dim]{time_str}[/] {event_text}")
            timeline_text = "\n".join(timeline_lines)
        else:
            timeline_text = (
                "[dim]14:30:17[/] Traffic spike detected (3x baseline)\n"
                "[dim]14:32:17[/] [red]First 5xx errors recorded[/]\n"
                "[dim]14:32:45[/] PagerDuty alert triggered\n"
                "[dim]14:33:02[/] AutoSRE investigation started\n"
                f"[dim]14:33:{int(duration_seconds):02d}[/] [green]Root cause identified[/]"
            )
        console.print(Panel(timeline_text, title="⏱️  Incident Timeline", border_style="cyan"))
        
        return {
            "investigation_id": self.investigation_id,
            "duration_seconds": duration_seconds,
            "root_cause": root_cause,
            "recommendations": recommendations,
            "simulated": True,
        }
    
    def _phase_context_gathering(self):
        """Phase 1: Context Gathering with service topology visualization."""
        import time
        from rich.tree import Tree
        
        console.print(f"\n[bold white on blue] PHASE 1/5 [/] [bold]📊 Context Gathering[/]")
        console.print("[dim]Collecting alert metadata and service context...[/]\n")
        
        # Show service topology with animated spinner
        with Progress(
            SpinnerColumn(spinner_name="dots12"),
            TextColumn("[cyan]Building service topology...[/]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=None)
            time.sleep(0.1)  # Quick topology build
        
        # Service topology tree - use scenario data if available
        tree = Tree(f"🎯 [bold cyan]{self.service}[/]")
        
        if self.scenario and "service_topology" in self.scenario:
            topology = self.scenario["service_topology"]
            
            # Add dependencies
            deps = tree.add("[dim]Dependencies[/]")
            for dep in topology.get("dependencies", []):
                icon = {"cache": "📦", "database": "🐘", "messaging": "📨", "service": "⚙️", "external": "🌐", "config": "⚙️", "middleware": "🔧", "secrets": "🔐"}.get(dep.get("type", ""), "📦")
                note = f" [yellow]({dep['note']})[/]" if dep.get("note") else ""
                deps.add(f"{icon} {dep['name']}{note}")
            
            # Add upstream
            upstreams = tree.add("[dim]Upstream[/]")
            for upstream in topology.get("upstream", []):
                icon = {"gateway": "🌐", "bff": "📱", "service": "⚙️", "frontend": "💻", "ingress": "🚪", "cdn": "☁️"}.get(upstream.get("type", ""), "🌐")
                upstreams.add(f"{icon} {upstream['name']}")
        else:
            # Fallback to default topology
            deps = tree.add("[dim]Dependencies[/]")
            deps.add("📦 redis-primary [yellow](connection pool: 10)[/]")
            deps.add("🐘 postgres-orders")
            deps.add("📨 kafka-events")
            upstreams = tree.add("[dim]Upstream[/]")
            upstreams.add("🌐 api-gateway")
            upstreams.add("📱 mobile-bff")
        
        console.print(Panel(tree, title="Service Topology", border_style="cyan"))
        
        # Gather context items with progress - use scenario data if available
        if self.scenario and "context_items" in self.scenario:
            context_items = [(item["action"], item["result"]) for item in self.scenario["context_items"]]
        else:
            context_items = [
                ("Fetching service topology", f"Found 5 dependencies for {self.service}"),
                ("Loading alert history", "Retrieved 47 related alerts from last 24h"),
                ("Checking deployments", "3 deployments in last 48h (latest: v2.4.1)"),
                ("Analyzing traffic patterns", "Current traffic: 3.2x baseline"),
            ]
        
        for action, result in context_items:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn(f"[dim]{action}...[/]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("", total=None)
                time.sleep(0.05)  # Lightning fast
            console.print(f"  [green]✓[/] {result}")
        
        console.print()
    
    def _phase_evidence_collection(self):
        """Phase 2: Evidence Collection with live metrics."""
        import time
        
        console.print(f"[bold white on blue] PHASE 2/5 [/] [bold]🔬 Evidence Collection[/]")
        console.print("[dim]Querying metrics, logs, and traces from multiple sources...[/]\n")
        
        # Data sources with simulated queries - use scenario data if available
        if self.scenario and "data_sources" in self.scenario:
            sources = [(s["name"], s["query"], s.get("duration", 0.3)) for s in self.scenario["data_sources"]]
        else:
            sources = [
                ("📊 Prometheus", "rate(http_requests_total{service=\"" + self.service + "\",status=~\"5..\"}[5m])", 0.4),
                ("📜 Elasticsearch", f"service:{self.service} AND level:error | last 15m", 0.5),
                ("🔗 Jaeger", f"service={self.service} minDuration=1s", 0.3),
                ("☸️  Kubernetes", f"kubectl get pods -l app={self.service} -o json", 0.25),
            ]
        
        for source_name, query, duration in sources:
            with Progress(
                SpinnerColumn(spinner_name="dots12"),
                TextColumn(f"[cyan]{source_name}[/] querying..."),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("", total=None)
                time.sleep(duration * 0.3)  # Quick queries
            console.print(f"  [green]✓[/] [bold]{source_name}[/]")
            console.print(f"    [dim]└─ {query[:60]}{'...' if len(query) > 60 else ''}[/]")
        
        console.print()
        
        # Metrics table with key findings - use scenario data if available
        metrics_table = Table(title="📈 Key Metrics Snapshot", show_header=True, header_style="bold cyan")
        metrics_table.add_column("Metric", style="bold")
        metrics_table.add_column("Current", justify="right")
        metrics_table.add_column("Baseline", justify="right")
        metrics_table.add_column("Status")
        
        if self.scenario and "metrics" in self.scenario:
            for metric in self.scenario["metrics"]:
                color = metric.get("status_color", "white")
                metrics_table.add_row(
                    metric["name"],
                    f"[{color}]{metric['current']}[/]",
                    metric["baseline"],
                    f"[{color}]{metric['status']}[/]"
                )
        else:
            metrics_table.add_row("Error Rate (5xx)", "[red]23.4%[/]", "0.1%", "[red]🔴 CRITICAL[/]")
            metrics_table.add_row("P99 Latency", "[yellow]2,340ms[/]", "45ms", "[yellow]⚠️  HIGH[/]")
            metrics_table.add_row("Request Rate", "[cyan]3,200/s[/]", "1,000/s", "[cyan]↑ 3.2x[/]")
            metrics_table.add_row("Redis Connections", "[red]250/250[/]", "45/250", "[red]🔴 EXHAUSTED[/]")
            metrics_table.add_row("Pod Restarts (1h)", "[yellow]3[/]", "0", "[yellow]⚠️  ELEVATED[/]")
        
        console.print(metrics_table)
        console.print()
        
        # Streaming log analysis effect - use scenario data if available
        console.print("[bold]📜 Recent Error Logs[/] [dim](streaming...)[/]")
        
        if self.scenario and "logs" in self.scenario:
            logs = [
                (f"[{'red' if log['level'] == 'ERROR' else 'yellow'}]{log['level']}[/]", log["timestamp"], log["message"])
                for log in self.scenario["logs"]
            ]
        else:
            logs = [
                ("[red]ERROR[/]", "14:32:15.234", "Redis connection timeout after 30000ms - pool exhausted"),
                ("[red]ERROR[/]", "14:32:15.456", "Failed to acquire connection from pool: max connections reached"),
                ("[yellow]WARN[/]", "14:32:16.012", "Circuit breaker OPEN for redis-primary after 10 failures"),
                ("[red]ERROR[/]", "14:32:16.789", "CheckoutService.processOrder failed: RedisConnectionException"),
                ("[yellow]WARN[/]", "14:32:17.001", "Fallback triggered: returning cached inventory data"),
            ]
        
        log_panel_lines = []
        for level, ts, msg in logs:
            log_panel_lines.append(f"[dim]{ts}[/] {level} {msg}")
            time.sleep(0.02)  # Quick streaming effect
        
        console.print(Panel(
            "\n".join(log_panel_lines),
            border_style="red",
            padding=(0, 1),
        ))
        console.print()
        
        # Dramatic trace span visualization 
        console.print("[bold]🔗 Distributed Trace Analysis[/] [dim](sampling slow requests...)[/]")
        time.sleep(0.05)
        
        # Build trace visualization
        trace_lines = [
            "[cyan]▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔[/]",
            "[bold]api-gateway[/]     [dim]├[/][cyan]████[/][dim]┤[/] [dim]42ms[/]",
            "[bold]checkout-svc[/]    [dim]│   ├[/][green]████████[/][dim]┤[/] [dim]89ms[/]",
            f"[bold]redis-primary[/]   [dim]│   │       ├[/][red]{'█' * 40}[/][dim]┤[/] [red]30,000ms TIMEOUT[/] [bold red]⚠[/]",
            "[bold]postgres[/]        [dim]│   │   ├[/][green]██[/][dim]┤[/] [dim]12ms[/]",
            "[cyan]▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁[/]",
            "[dim]Trace ID: [/][cyan]abc123def456[/]  [dim]•  Total: [/][red]30,143ms[/]  [dim]•  Spans: [/]5",
        ]
        console.print(Panel(
            "\n".join(trace_lines),
            title="[bold]Sampled Trace[/]",
            border_style="cyan",
            padding=(0, 1),
        ))
        console.print()
    
    def _phase_hypothesis_generation(self):
        """Phase 3: AI Hypothesis Generation with streaming effect."""
        import time
        from rich.live import Live
        from rich.text import Text
        
        console.print(f"[bold white on blue] PHASE 3/5 [/] [bold]🧠 Hypothesis Generation[/]")
        console.print("[dim]AI analyzing patterns and generating hypotheses...[/]\n")
        
        # AI "thinking" animation with streaming text effect
        thinking_phrases = [
            "Correlating error patterns with metrics",
            "Analyzing temporal relationships", 
            "Checking historical incident patterns",
            "Evaluating deployment proximity",
            "Running inference on hypothesis model",
        ]
        
        for phrase in thinking_phrases:
            with Progress(
                SpinnerColumn(spinner_name="dots12"),
                TextColumn(f"[cyan]{phrase}...[/]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("", total=None)
                time.sleep(0.03)  # Snappy thinking
        
        # Dramatic AI streaming insight effect - use scenario data if available
        if self.scenario and "ai_insight" in self.scenario:
            ai_insight = self.scenario["ai_insight"]
        else:
            ai_insight = "Pattern detected: Redis connection exhaustion correlates with 3.2x traffic spike. Confidence: HIGH."
        console.print("[bold magenta]🤖 AI Reasoning:[/]")
        
        # Use Live for smooth streaming effect
        from rich.live import Live
        from rich.text import Text
        
        with Live(Text("", style="dim italic"), console=console, refresh_per_second=60, transient=False) as live:
            displayed = ""
            # Type faster in chunks for snappier feel
            for i, char in enumerate(ai_insight):
                displayed += char
                # Only update every 3rd character for speed, but always show final
                if i % 3 == 0 or i == len(ai_insight) - 1:
                    live.update(Text(displayed, style="dim italic"))
                    time.sleep(0.003)  # Rapid typing effect
        
        console.print()
        
        # Dramatic AI insight reveal
        console.print("[bold green]✨ Analysis Complete[/]\n")
        
        # Use scenario hypotheses if available
        if self.scenario and "hypotheses" in self.scenario:
            hypotheses = [
                (h["title"], h["confidence"], h["status"], h["color"])
                for h in self.scenario["hypotheses"]
            ]
        else:
            hypotheses = [
                ("Redis connection pool exhaustion", 0.92, "HIGH", "green"),
                ("Downstream service degradation", 0.15, "LOW", "yellow"),
                ("Recent deployment regression", 0.08, "LOW", "dim"),
                ("Database query timeout", 0.05, "RULED OUT", "dim"),
            ]
        
        # Dramatic animated hypothesis ranking
        console.print("[bold]📊 Hypothesis Ranking:[/]")
        
        from rich.live import Live
        from rich.text import Text
        
        for title, confidence, status, color in hypotheses:
            # Animate the bar filling up using Live
            final_filled = int(confidence * 20)
            
            # Single frame animation - just show the bar building once
            with Live(Text(""), console=console, refresh_per_second=30, transient=True) as live:
                # Just show the final state with a brief reveal
                bar_text = Text()
                bar_text.append("█" * final_filled, style=color)
                bar_text.append("░" * (20 - final_filled), style="dim")
                current_pct = int(confidence * 100)
                bar_text.append(f"  {current_pct:>3}%  {title}")
                live.update(bar_text)
                time.sleep(0.02)  # Brief flash
            
            # Print final state
            console.print(f" [{color}]{'█' * final_filled}[/][dim]{'░' * (20 - final_filled)}[/]  [bold]{confidence:.0%}[/]  {title}  [{color}]{status}[/]")
        
        console.print()
        time.sleep(0.02)  # Brief pause before next phase
    
    def _phase_root_cause_analysis(self) -> tuple:
        """Phase 4: Root Cause Analysis with evidence correlation."""
        import time
        
        console.print(f"[bold white on blue] PHASE 4/5 [/] [bold]🎯 Root Cause Analysis[/]")
        console.print("[dim]Validating top hypothesis against collected evidence...[/]\n")
        
        # Evidence correlation animation - use scenario data if available
        if self.scenario and "correlations" in self.scenario:
            correlations = [
                (c["evidence"], c["status"], c["color"])
                for c in self.scenario["correlations"]
            ]
        else:
            correlations = [
                ("Redis pool at max capacity", "CONFIRMED", "green"),
                ("Traffic spike coincides with errors", "CONFIRMED", "green"),
                ("No circuit breaker configured", "CONFIRMED", "green"),
                ("Recent deployment causation", "RULED OUT", "dim"),
            ]
        
        for evidence, status, color in correlations:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn(f"[cyan]Checking: {evidence}...[/]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("", total=None)
                time.sleep(0.03)  # Instant checks
            
            if status == "CONFIRMED":
                console.print(f"  [green]✓[/] {evidence} [{color}]{status}[/]")
            else:
                console.print(f"  [dim]✗[/] {evidence} [{color}]{status}[/]")
        
        console.print()
        
        # Determine root cause - use scenario data if available
        if self.scenario and "root_cause" in self.scenario and "recommendations" in self.scenario:
            root_cause_data = (self.scenario["root_cause"], self.scenario["recommendations"])
        else:
            # Fallback to service-based root causes
            root_causes = {
                "checkout-service": ("Redis connection pool exhaustion due to traffic spike", [
                    "Increase Redis connection pool max_connections from 10 to 50",
                    "Implement connection pool circuit breaker with 5s timeout",
                    "Add auto-scaling rule based on Redis connection utilization",
                    "Set up PagerDuty alert for connection pool usage > 80%",
                ]),
                "api-gateway": ("Memory leak in request handler causing OOMKills", [
                    "Deploy hotfix v2.3.1 with patched request handler",
                    "Increase pod memory limit from 512Mi to 1Gi temporarily",
                    "Enable memory profiling in staging environment",
                ]),
                "order-service": ("Missing database index on order_items table", [
                    "CREATE INDEX idx_order_items_order_id ON order_items(order_id)",
                    "Enable slow query logging with 100ms threshold",
                    "Review query patterns for N+1 issues",
                ]),
                "payment-service": ("Upstream payment provider timeout causing cascade", [
                    "Increase payment provider timeout from 5s to 15s",
                    "Implement async payment processing with retry queue",
                    "Add fallback payment provider configuration",
                ]),
                "user-service": ("Configuration drift: AUTH_SECRET_KEY mismatch", [
                    "Sync AUTH_SECRET_KEY across all user-service pods",
                    "Migrate secrets to HashiCorp Vault with versioning",
                ]),
            }
            
            root_cause_data = root_causes.get(self.service, (
                f"Simulated root cause for {self.service}",
                ["Review service logs", "Check recent deployments"]
            ))
        
        time.sleep(0.1)
        return root_cause_data
    
    def _phase_report_generation(self):
        """Phase 5: Report Generation."""
        import time
        
        console.print(f"[bold white on blue] PHASE 5/5 [/] [bold]📝 Report Generation[/]")
        console.print("[dim]Compiling findings and recommendations...[/]\n")
        
        report_items = [
            "Generating incident timeline",
            "Creating remediation checklist",
            "Drafting post-mortem template",
            "Computing MTTR estimate",
        ]
        
        for item in report_items:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn(f"[dim]{item}...[/]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("", total=None)
                time.sleep(0.02)  # Instant report generation
            console.print(f"  [green]✓[/] {item}")
        
        console.print()


# Demo scenarios
DEMO_SCENARIOS = [
    {
        "id": "redis-connection",
        "name": "Redis Connection Pool Exhaustion",
        "alert": "High error rate on checkout-service: 23% 5xx errors",
        "service": "checkout-service",
        "severity": "high",
        "description": "Classic connection pool exhaustion after a traffic spike",
    },
    {
        "id": "memory-leak",
        "name": "Memory Leak in API Gateway",
        "alert": "API Gateway pod restarts: 12 restarts in last hour",
        "service": "api-gateway",
        "severity": "critical",
        "description": "Gradual memory increase leading to OOMKills",
    },
    {
        "id": "latency-spike",
        "name": "Database Query Latency",
        "alert": "P99 latency spike: order-service at 2.3s (threshold: 500ms)",
        "service": "order-service",
        "severity": "high",
        "description": "Slow queries due to missing index after schema migration",
    },
    {
        "id": "cascading-failure",
        "name": "Cascading Failure",
        "alert": "Multiple services degraded: payment, checkout, order",
        "service": "payment-service",
        "severity": "critical",
        "description": "Upstream timeout causing downstream failures",
    },
    {
        "id": "config-drift",
        "name": "Configuration Drift",
        "alert": "Intermittent authentication failures: user-service",
        "service": "user-service",
        "severity": "medium",
        "description": "Environment variable mismatch between pods",
    },
]


@app.command()
def run(
    scenario_id: Optional[str] = typer.Argument(
        None, 
        help="Scenario ID to run (e.g., redis-connection, memory-leak). Default: redis-connection"
    ),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario ID to run (alternative to positional arg)"),
    list_scenarios: bool = typer.Option(False, "--list", "-l", help="List available scenarios"),
    random_scenario: bool = typer.Option(False, "--random", "-r", help="Run a random scenario"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip all confirmations (non-interactive)"),
    interactive: bool = typer.Option(False, "--interactive/--batch", "-i", help="Interactive mode (prompts for input)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output, suppress demo warnings"),
    wow: bool = typer.Option(False, "--wow", "-w", help="Clean demo mode - no warnings, maximum impressiveness"),
):
    """
    [DEMO MODE] Run a demo investigation with SIMULATED data.
    
    ⚠️  WARNING: This uses FAKE/MOCK data for demonstration only!
    
    Simulates an incident investigation with synthetic data to demonstrate
    AutoSRE's capabilities. This does NOT query real infrastructure.
    
    For REAL incident investigations, use: `autosre investigate`
    
    Examples:
        autosre demo run                           # Run default (redis-connection)
        autosre demo run redis-connection          # Run specific scenario
        autosre demo run redis-connection -y       # Skip confirmations
        autosre demo run --list                    # List available scenarios
        autosre demo run --random                  # Run random scenario
        autosre demo run -s memory-leak --quiet    # Quiet mode
    """
    # Merge scenario from positional arg or option
    effective_scenario = scenario_id or scenario
    
    # --wow implies no warnings and non-interactive
    if wow:
        quiet = True
        yes = True
        interactive = False
    
    # -y flag implies non-interactive
    if yes:
        interactive = False
    
    # If scenario is explicitly provided, default to "wow" mode (cleaner demos)
    # This makes `autosre demo run redis-connection` show the impressive output
    if effective_scenario and not interactive:
        yes = True
        quiet = True  # Skip warning banner for cleaner demo experience
    
    # Show demo warning unless quiet mode
    if not quiet:
        _print_demo_warning()
    
    if list_scenarios:
        _list_scenarios()
        return
    
    # Select scenario
    if random_scenario:
        selected = random.choice(DEMO_SCENARIOS)
    elif effective_scenario:
        selected = next((s for s in DEMO_SCENARIOS if s["id"] == effective_scenario), None)
        if not selected:
            console.print(f"[red][DEMO MODE] Scenario '{effective_scenario}' not found[/]")
            console.print("[DEMO MODE] Use --list to see available scenarios")
            _list_scenarios()
            raise typer.Exit(1)
    elif interactive and not yes:
        # Interactive selection - only in interactive mode
        _list_scenarios()
        console.print()
        selected_id = typer.prompt("[DEMO MODE] Select scenario ID", default="redis-connection")
        selected = next((s for s in DEMO_SCENARIOS if s["id"] == selected_id), None)
        if not selected:
            console.print(f"[red][DEMO MODE] Scenario '{selected_id}' not found[/]")
            raise typer.Exit(1)
    else:
        # Default to redis-connection for non-interactive mode
        selected = DEMO_SCENARIOS[0]  # redis-connection
    
    # Show scenario info
    console.print()
    if wow or quiet:
        # Clean mode - no DEMO MODE labels, just the scenario (for demos)
        console.print(Panel(
            f"[bold]{selected['name']}[/]\n\n"
            f"[bold]Alert:[/] {selected['alert']}\n"
            f"[bold]Service:[/] {selected['service']}\n"
            f"[bold]Severity:[/] {selected['severity']}\n\n"
            f"[dim]{selected['description']}[/]",
            title="🚨 [bold]Incoming Alert[/]",
            border_style="red",
        ))
    else:
        console.print(Panel(
            f"[bold]{selected['name']}[/]\n\n"
            f"[bold]Alert:[/] {selected['alert']}\n"
            f"[bold]Service:[/] {selected['service']}\n"
            f"[bold]Severity:[/] {selected['severity']}\n\n"
            f"[dim]{selected['description']}[/]\n\n"
            f"[yellow]⚠️  All data is SIMULATED - not real infrastructure[/]",
            title="🎭 [DEMO MODE] Demo Scenario (SIMULATED)",
            border_style="magenta",
        ))
    
    # Only prompt in interactive mode (and not if -y flag used)
    if interactive and not yes:
        if not typer.confirm("\n[DEMO MODE] Start simulated investigation?", default=True):
            raise typer.Abort()
    
    # Use the DEMO runner (not the real InvestigationRunner!)
    # The real investigate command uses InvestigationRunner from investigate.py
    # which connects to real infrastructure. This demo runner is completely simulated.
    
    console.print()
    
    runner = DemoInvestigationRunner(
        alert=selected["alert"],
        service=selected["service"],
        severity=selected["severity"],
        output_format="text",
        stream=True,
        scenario_id=selected["id"],
    )
    
    result = runner.run()
    
    # Show impressive completion summary
    console.print()
    
    # Dramatic completion banner
    console.print()
    console.print("[bold green]" + "═" * 78 + "[/]")
    console.print("[bold green]" + " " * 25 + "🎉 INVESTIGATION COMPLETE 🎉" + " " * 25 + "[/]")
    console.print("[bold green]" + "═" * 78 + "[/]")
    console.print()
    
    # Final summary panel with stats
    # Calculate the "wow" multiplier
    manual_triage_time = 1800  # 30 minutes typical manual triage
    speed_multiplier = manual_triage_time / max(result['duration_seconds'], 1)
    
    # Calculate estimated savings (based on industry averages)
    # Avg SRE salary: $150k/yr = ~$72/hr, assume 2 engineers for 30min = $72
    # Plus revenue impact: $10k/min for high-severity, so 30 min saved = $300k  
    engineer_cost_saved = 72  # 2 engineers x 30 min at $72/hr
    revenue_protected = 15000  # Conservative: $500/min for 30 min faster resolution
    total_savings = engineer_cost_saved + revenue_protected
    
    # Error rate sparkline (shows the spike and current state)
    sparkline = "▁▁▂▃▅█▇▅▃▂▁"  # Visual representation of error spike
    
    summary_text = (
        f"[bold green]✅ Investigation Successful[/]\n\n"
        f"[bold]📋 Investigation ID:[/]  [cyan]{result['investigation_id']}[/]\n"
        f"[bold]⏱️  Time to Resolution:[/] [bold yellow]{result['duration_seconds']:.1f}s[/] [dim](vs ~30min manual)[/]\n"
        f"[bold]⚡ Speed:[/]             [bold green]🚀 {speed_multiplier:.0f}x FASTER THAN MANUAL[/]\n"
        f"[bold]💰 Est. Savings:[/]      [bold green]${total_savings:,}[/] [dim](eng time + revenue protected)[/]\n"
        f"[bold]📈 Error Trend:[/]       [red]{sparkline}[/] [green]→ resolving[/]\n"
        f"[bold]🎯 Root Cause:[/]        [bold red]{result['root_cause']}[/]\n\n"
        f"[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n\n"
        f"[bold cyan]⚡ AutoSRE - AI-Powered Incident Investigation[/]\n\n"
        f"[bold]Next Steps:[/]\n"
        f"  [green]1.[/] Review recommended actions above\n"
        f"  [green]2.[/] Implement critical fixes first\n"
        f"  [green]3.[/] Schedule post-mortem within 48h\n\n"
        f"[dim]Run [cyan]autosre investigate[/dim] [dim]for real incident analysis[/]"
    )
    console.print(Panel(
        summary_text,
        title="[bold white on green] 📋 SUMMARY [/]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()


def _list_scenarios():
    """Display available scenarios."""
    table = Table(title="[DEMO MODE] Available Demo Scenarios (SIMULATED)", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Service")
    table.add_column("Severity")
    
    for s in DEMO_SCENARIOS:
        severity_color = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue",
        }.get(s["severity"], "white")
        
        table.add_row(
            s["id"],
            s["name"],
            s["service"],
            f"[{severity_color}]{s['severity']}[/]",
        )
    
    console.print()
    console.print(table)
    console.print("\n[dim][DEMO MODE] All scenarios use simulated data - not real incidents[/]")


@app.command()
def seed(
    count: int = typer.Option(10, "--count", "-n", help="Number of episodes to seed"),
    clear_first: bool = typer.Option(False, "--clear", help="Clear existing memory first"),
):
    """
    [DEMO MODE] Seed episodic memory with SIMULATED demo data.
    
    ⚠️  WARNING: This populates memory with FAKE/SYNTHETIC data!
    
    Populates the memory database with synthetic incident episodes
    for testing memory search and pattern matching.
    
    This data is NOT from real incidents - it's generated for demos only.
    
    Examples:
        autosre demo seed
        autosre demo seed --count 50
        autosre demo seed --clear --count 20
    """
    from autosre.memory import EpisodicMemory, Episode
    
    # Show demo warning
    _print_demo_warning()
    
    console.print("[bold yellow][DEMO MODE] Seeding memory with SIMULATED data...[/]\n")
    
    memory = EpisodicMemory()
    
    if clear_first:
        memory.clear()
        console.print("[yellow][DEMO MODE] Cleared existing memory[/]")
    
    # Demo episode templates
    templates = [
        {
            "alert_type": "error_rate",
            "services": ["checkout-service", "payment-service", "order-service"],
            "root_causes": [
                "Redis connection pool exhaustion",
                "Database connection limit reached",
                "Downstream service timeout",
                "Invalid configuration after deployment",
            ],
            "skills": ["prometheus", "logs", "kubernetes"],
        },
        {
            "alert_type": "latency",
            "services": ["api-gateway", "search-service", "recommendation-service"],
            "root_causes": [
                "Missing database index",
                "N+1 query pattern",
                "Cache miss storm",
                "Network congestion",
            ],
            "skills": ["prometheus", "traces", "database"],
        },
        {
            "alert_type": "resource_exhaustion",
            "services": ["worker-service", "batch-processor", "ml-inference"],
            "root_causes": [
                "Memory leak in connection handling",
                "Unbounded queue growth",
                "Log file rotation failure",
                "Goroutine leak",
            ],
            "skills": ["kubernetes", "prometheus", "logs"],
        },
        {
            "alert_type": "availability",
            "services": ["user-service", "auth-service", "notification-service"],
            "root_causes": [
                "DNS resolution failure",
                "Certificate expiration",
                "Load balancer misconfiguration",
                "Kubernetes node failure",
            ],
            "skills": ["kubernetes", "networking", "dns"],
        },
    ]
    
    episodes_created = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[DEMO MODE] Seeding simulated episodes...", total=count)
        
        for i in range(count):
            template = random.choice(templates)
            service = random.choice(template["services"])
            root_cause = random.choice(template["root_causes"])
            
            # Random timestamp in last 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            created_at = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
            
            # Random duration (5 min to 2 hours)
            duration = random.randint(300, 7200)
            
            # Random effectiveness (0.6 to 1.0)
            effectiveness = random.uniform(0.6, 1.0)
            
            episode = Episode(
                id=str(uuid4())[:8],
                created_at=created_at,
                alert_type=template["alert_type"],
                service_name=service,
                severity=random.choice(["high", "critical", "medium"]),
                root_cause=root_cause,
                summary=f"Investigation of {template['alert_type']} on {service}",
                resolved=random.random() > 0.1,  # 90% resolved
                effectiveness_score=effectiveness,
                skills_used=template["skills"],
                key_findings=[
                    {"finding": root_cause},
                    {"finding": f"Affected service: {service}"},
                ],
                duration_seconds=duration,
                steps_taken=[
                    "context_gathering",
                    "evidence_collection",
                    "hypothesis_generation",
                    "root_cause_analysis",
                ],
                tags=[service, template["alert_type"]],
            )
            
            memory.store_episode(episode)
            episodes_created.append(episode)
            
            progress.update(task, advance=1)
    
    # Show summary
    stats = memory.get_stats()
    
    console.print()
    console.print(Panel(
        f"[green]✓[/] Seeded {count} SIMULATED episodes\n\n"
        f"[bold]Total Episodes:[/] {stats['total_episodes']}\n"
        f"[bold]Alert Types:[/] {len(stats.get('top_alert_types', []))}\n"
        f"[bold]Resolution Rate:[/] {stats.get('resolution_rate', 0):.0%}\n\n"
        f"[yellow]⚠️  This data is SIMULATED - not from real incidents![/]",
        title="[DEMO MODE] Demo Data Seeded (SIMULATED)",
        border_style="green",
    ))


@app.command()
def scenarios():
    """[DEMO MODE] List all available demo scenarios with SIMULATED data."""
    _print_demo_warning()
    _list_scenarios()


@app.command()
def benchmark(
    iterations: int = typer.Option(5, "--iterations", "-n", help="Number of iterations"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Specific scenario"),
):
    """
    [DEMO MODE] Benchmark investigation performance with SIMULATED data.
    
    ⚠️  WARNING: This uses FAKE/MOCK scenarios for benchmarking only!
    
    Runs multiple simulated investigations and reports timing statistics.
    Results are based on synthetic demo data, not real incidents.
    
    Examples:
        autosre demo benchmark
        autosre demo benchmark --iterations 10
    """
    # NOTE: We DON'T import InvestigationRunner here - we use DemoInvestigationRunner
    # which is completely simulated and does not connect to real infrastructure.
    import time
    
    # Show demo warning
    _print_demo_warning()
    
    scenarios_to_run = [next((s for s in DEMO_SCENARIOS if s["id"] == scenario), None)] if scenario else DEMO_SCENARIOS
    scenarios_to_run = [s for s in scenarios_to_run if s]
    
    if not scenarios_to_run:
        console.print("[red][DEMO MODE] No scenarios to run[/]")
        raise typer.Exit(1)
    
    results = []
    
    console.print()
    console.print(f"[bold][DEMO MODE] Running benchmark: {iterations} iterations with SIMULATED data[/]")
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        total = iterations * len(scenarios_to_run)
        task = progress.add_task("[DEMO] Running...", total=total)
        
        for i in range(iterations):
            for s in scenarios_to_run:
                start = time.time()
                
                # Use DemoInvestigationRunner - NEVER the real InvestigationRunner!
                runner = DemoInvestigationRunner(
                    alert=s["alert"],
                    service=s["service"],
                    severity=s["severity"],
                    output_format="text",
                    stream=False,  # Quiet mode for benchmark
                    scenario_id=s["id"],
                )
                
                runner.run()
                
                elapsed = time.time() - start
                results.append({
                    "scenario": s["id"],
                    "iteration": i + 1,
                    "duration": elapsed,
                })
                
                progress.update(task, advance=1, description=f"[DEMO] {s['id']} ({elapsed:.2f}s)")
    
    # Calculate statistics
    durations = [r["duration"] for r in results]
    avg_duration = sum(durations) / len(durations)
    min_duration = min(durations)
    max_duration = max(durations)
    
    # Group by scenario
    by_scenario = {}
    for r in results:
        if r["scenario"] not in by_scenario:
            by_scenario[r["scenario"]] = []
        by_scenario[r["scenario"]].append(r["duration"])
    
    console.print()
    
    # Results table
    table = Table(title="[DEMO MODE] Benchmark Results (SIMULATED)", show_header=True)
    table.add_column("Scenario", style="cyan")
    table.add_column("Avg", justify="right")
    table.add_column("Min", justify="right", style="green")
    table.add_column("Max", justify="right", style="yellow")
    table.add_column("Runs", justify="right")
    
    for scenario_id, durations in by_scenario.items():
        table.add_row(
            scenario_id,
            f"{sum(durations)/len(durations):.3f}s",
            f"{min(durations):.3f}s",
            f"{max(durations):.3f}s",
            str(len(durations)),
        )
    
    console.print(table)
    
    # Summary
    console.print()
    console.print(Panel(
        f"[bold]Total Runs:[/] {len(results)}\n"
        f"[bold]Average:[/] {avg_duration:.3f}s\n"
        f"[bold]Min:[/] {min_duration:.3f}s\n"
        f"[bold]Max:[/] {max_duration:.3f}s\n\n"
        f"[yellow]⚠️  Results based on SIMULATED demo scenarios[/]",
        title="[DEMO MODE] Benchmark Summary (SIMULATED)",
        border_style="cyan",
    ))


@app.command()
def topology():
    """
    [DEMO MODE] Show demo service topology with SIMULATED architecture.
    
    Displays a sample microservices topology used in demo scenarios.
    This is a FICTIONAL architecture for demonstration purposes only.
    """
    from rich.tree import Tree
    
    # Show demo warning
    _print_demo_warning()
    
    # Build topology tree
    tree = Tree("🏢 [bold]Demo Platform[/] [dim](SIMULATED)[/]")
    
    # Frontend tier
    frontend = tree.add("📱 [cyan]Frontend Tier[/]")
    frontend.add("web-frontend")
    frontend.add("mobile-bff")
    
    # API tier
    api = tree.add("🔌 [cyan]API Tier[/]")
    api.add("api-gateway")
    api.add("auth-service")
    
    # Business logic tier
    business = tree.add("⚙️ [cyan]Business Logic[/]")
    checkout = business.add("checkout-service")
    checkout.add("[dim]→ payment-service[/]")
    checkout.add("[dim]→ inventory-service[/]")
    
    order = business.add("order-service")
    order.add("[dim]→ notification-service[/]")
    
    business.add("user-service")
    business.add("search-service")
    
    # Data tier
    data = tree.add("🗄️ [cyan]Data Tier[/]")
    data.add("postgresql (primary)")
    data.add("redis (cache)")
    data.add("elasticsearch (search)")
    
    # Infrastructure
    infra = tree.add("🔧 [cyan]Infrastructure[/]")
    infra.add("kubernetes")
    infra.add("prometheus")
    infra.add("grafana")
    
    console.print()
    console.print(Panel(tree, title="[DEMO MODE] Demo Service Topology (FICTIONAL)", border_style="cyan"))
    console.print("\n[dim][DEMO MODE] This is a simulated architecture - not real infrastructure[/]")
    console.print()
