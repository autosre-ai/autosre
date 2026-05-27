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
from typing import Optional
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.status import Status
from rich.table import Table

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
    ):
        self.alert = alert
        self.service = service
        self.severity = severity
        self.output_format = output_format
        self.stream = stream
        self.investigation_id = f"demo-{str(uuid4())[:8]}"
    
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
        
        if not self.stream:
            # Quiet/benchmark mode - just a quick sleep
            time.sleep(0.1)
            return {
                "investigation_id": self.investigation_id,
                "duration_seconds": 0.1,
                "root_cause": "Redis connection pool exhaustion due to traffic spike",
                "recommendations": [],
                "simulated": True,
            }
        
        start_time = time.time()
        
        # Epic logo
        _print_logo()
        
        # Show impressive header
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
        
        # Show impressive findings panel
        console.print()
        console.print(Rule("[bold green]✅ ROOT CAUSE IDENTIFIED[/]", style="green"))
        console.print()
        
        # Root cause panel
        console.print(Panel(
            f"[bold red]{root_cause}[/]",
            title="[bold white on red] 🎯 ROOT CAUSE [/]",
            border_style="red",
            padding=(1, 2),
        ))
        
        # Evidence summary
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
        
        # Timeline
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
            time.sleep(0.4)  # Faster topology build
        
        # Service topology tree
        tree = Tree(f"🎯 [bold cyan]{self.service}[/]")
        deps = tree.add("[dim]Dependencies[/]")
        deps.add("📦 redis-primary [yellow](connection pool: 10)[/]")
        deps.add("🐘 postgres-orders")
        deps.add("📨 kafka-events")
        upstreams = tree.add("[dim]Upstream[/]")
        upstreams.add("🌐 api-gateway")
        upstreams.add("📱 mobile-bff")
        
        console.print(Panel(tree, title="Service Topology", border_style="cyan"))
        
        # Gather context items with progress
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
                time.sleep(0.15)  # Faster - snappy feel
            console.print(f"  [green]✓[/] {result}")
        
        console.print()
        time.sleep(0.1)  # Quicker transition
    
    def _phase_evidence_collection(self):
        """Phase 2: Evidence Collection with live metrics."""
        import time
        
        console.print(f"[bold white on blue] PHASE 2/5 [/] [bold]🔬 Evidence Collection[/]")
        console.print("[dim]Querying metrics, logs, and traces from multiple sources...[/]\n")
        
        # Data sources with simulated queries
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
                time.sleep(duration)
            console.print(f"  [green]✓[/] [bold]{source_name}[/]")
            console.print(f"    [dim]└─ {query[:60]}{'...' if len(query) > 60 else ''}[/]")
        
        console.print()
        
        # Metrics table with key findings
        metrics_table = Table(title="📈 Key Metrics Snapshot", show_header=True, header_style="bold cyan")
        metrics_table.add_column("Metric", style="bold")
        metrics_table.add_column("Current", justify="right")
        metrics_table.add_column("Baseline", justify="right")
        metrics_table.add_column("Status")
        
        metrics_table.add_row("Error Rate (5xx)", "[red]23.4%[/]", "0.1%", "[red]🔴 CRITICAL[/]")
        metrics_table.add_row("P99 Latency", "[yellow]2,340ms[/]", "45ms", "[yellow]⚠️  HIGH[/]")
        metrics_table.add_row("Request Rate", "[cyan]3,200/s[/]", "1,000/s", "[cyan]↑ 3.2x[/]")
        metrics_table.add_row("Redis Connections", "[red]250/250[/]", "45/250", "[red]🔴 EXHAUSTED[/]")
        metrics_table.add_row("Pod Restarts (1h)", "[yellow]3[/]", "0", "[yellow]⚠️  ELEVATED[/]")
        
        console.print(metrics_table)
        console.print()
        
        # Streaming log analysis effect
        console.print("[bold]📜 Recent Error Logs[/] [dim](streaming...)[/]")
        
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
            time.sleep(0.08)  # Faster streaming effect
        
        console.print(Panel(
            "\n".join(log_panel_lines),
            border_style="red",
            padding=(0, 1),
        ))
        console.print()
        time.sleep(0.15)  # Quicker transition
    
    def _phase_hypothesis_generation(self):
        """Phase 3: AI Hypothesis Generation with streaming effect."""
        import time
        from rich.table import Table
        
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
                time.sleep(0.12)  # Fast thinking
        
        # Dramatic AI insight reveal
        console.print("[bold green]🤖 AI Analysis Complete[/]\n")
        
        hypotheses = [
            ("Redis connection pool exhaustion", 0.92, "HIGH", "green"),
            ("Downstream service degradation", 0.15, "LOW", "yellow"),
            ("Recent deployment regression", 0.08, "LOW", "dim"),
            ("Database query timeout", 0.05, "RULED OUT", "dim"),
        ]
        
        # Build hypothesis table for clean display
        hyp_table = Table(show_header=False, box=None, padding=(0, 1))
        hyp_table.add_column("Bar", width=22)
        hyp_table.add_column("Conf", width=5)
        hyp_table.add_column("Hypothesis")
        hyp_table.add_column("Status")
        
        for title, confidence, status, color in hypotheses:
            bar_filled = int(confidence * 20)
            bar_empty = 20 - bar_filled
            bar = f"[{color}]{'█' * bar_filled}[/][dim]{'░' * bar_empty}[/]"
            status_display = f"[{color}]{status}[/]"
            hyp_table.add_row(bar, f"[bold]{confidence:.0%}[/]", title, status_display)
            time.sleep(0.08)  # Small delay for effect
        
        console.print(hyp_table)
        console.print()
        time.sleep(0.1)  # Brief pause before next phase
    
    def _phase_root_cause_analysis(self) -> tuple:
        """Phase 4: Root Cause Analysis with evidence correlation."""
        import time
        
        console.print(f"[bold white on blue] PHASE 4/5 [/] [bold]🎯 Root Cause Analysis[/]")
        console.print("[dim]Validating top hypothesis against collected evidence...[/]\n")
        
        # Evidence correlation animation
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
                time.sleep(0.2)  # Faster checks
            
            if status == "CONFIRMED":
                console.print(f"  [green]✓[/] {evidence} [{color}]{status}[/]")
            else:
                console.print(f"  [dim]✗[/] {evidence} [{color}]{status}[/]")
        
        console.print()
        
        # Determine root cause based on service
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
        
        time.sleep(0.2)
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
                time.sleep(0.12)  # Snappy report generation
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
    
    # -y flag implies non-interactive
    if yes:
        interactive = False
    
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
    )
    
    result = runner.run()
    
    # Show impressive completion summary
    console.print()
    from rich.rule import Rule
    console.print(Rule("[bold green]🎉 INVESTIGATION COMPLETE[/]", style="green"))
    console.print()
    
    # Final summary panel with stats
    # Calculate the "wow" multiplier
    manual_triage_time = 1800  # 30 minutes typical manual triage
    speed_multiplier = manual_triage_time / max(result['duration_seconds'], 1)
    
    summary_text = (
        f"[bold green]✅ Investigation Successful[/]\n\n"
        f"[bold]Investigation ID:[/]  [cyan]{result['investigation_id']}[/]\n"
        f"[bold]Time to Resolution:[/] [yellow]{result['duration_seconds']:.1f}s[/] [dim](vs ~30min manual)[/]\n"
        f"[bold]Speed:[/]             [bold green]⚡ {speed_multiplier:.0f}x FASTER[/]\n"
        f"[bold]Root Cause:[/]        [red]{result['root_cause']}[/]\n\n"
        f"[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n\n"
        f"[bold]Next Steps:[/]\n"
        f"  1. Review recommended actions above\n"
        f"  2. Implement critical fixes first\n"
        f"  3. Schedule post-mortem within 48h\n\n"
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
