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

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
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
        
    def run(self) -> dict:
        """Run a SIMULATED investigation (no real infrastructure)."""
        import time
        from rich.text import Text
        from rich.rule import Rule
        from rich.status import Status
        from rich.columns import Columns
        
        if self.stream:
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
        
        # Simulate investigation phases with rich output
        if self.stream:
            phases = [
                ("📊 Context Gathering", "Collecting alert metadata and service context...", 1.2, [
                    "• Fetched service topology for checkout-service",
                    "• Retrieved 47 related alerts from last 24h", 
                    "• Loaded deployment history (3 deploys in 48h)",
                ]),
                ("🔬 Evidence Collection", "Querying metrics, logs, and traces...", 1.8, [
                    "• Prometheus: 23% error rate spike detected at 14:32 UTC",
                    "• Logs: 1,247 connection timeout errors in redis-pool",
                    "• Traces: P99 latency jumped from 45ms → 2.3s",
                ]),
                ("🧠 Hypothesis Generation", "AI analyzing patterns and generating hypotheses...", 1.0, [
                    "• H1: Redis connection pool exhaustion (confidence: 87%)",
                    "• H2: Downstream service degradation (confidence: 12%)",
                    "• H3: Recent deployment regression (confidence: 8%)",
                ]),
                ("🎯 Root Cause Analysis", "Validating hypotheses against evidence...", 1.5, [
                    "• ✓ Confirmed: Redis pool max connections = 10 (insufficient)",
                    "• ✓ Confirmed: Traffic spike 3x normal at 14:30 UTC",
                    "• ✓ Confirmed: No circuit breaker on redis connections",
                ]),
                ("📝 Report Generation", "Compiling findings and recommendations...", 0.8, [
                    "• Generated incident timeline",
                    "• Created remediation checklist",
                    "• Drafted post-mortem template",
                ]),
            ]
            
            total_duration = 0
            
            for phase_name, description, duration, findings in phases:
                # Phase header
                console.print(f"\n[bold]{phase_name}[/]")
                console.print(f"[dim]{description}[/]")
                
                # Progress bar for this phase
                with Progress(
                    SpinnerColumn(spinner_name="dots12"),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=40, complete_style="green", finished_style="green"),
                    TaskProgressColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("Processing...", total=100)
                    steps = int(duration * 20)
                    for step in range(steps):
                        time.sleep(duration / steps)
                        progress.update(task, advance=100 / steps)
                
                # Show findings for this phase
                for finding in findings:
                    console.print(f"  [cyan]{finding}[/]")
                    time.sleep(0.05)  # Small delay for effect
                
                total_duration += duration
            
            duration_seconds = total_duration
        else:
            # Quiet/benchmark mode - just a quick sleep
            time.sleep(0.1)
            duration_seconds = 0.1
        
        # Generate simulated root cause based on scenario
        root_causes = {
            "checkout-service": ("Redis connection pool exhaustion due to traffic spike", [
                "Increase Redis connection pool max_connections from 10 to 50",
                "Implement connection pool circuit breaker with 5s timeout",
                "Add auto-scaling rule for checkout-service based on Redis connection utilization",
                "Set up PagerDuty alert for connection pool usage > 80%",
            ]),
            "api-gateway": ("Memory leak in request handler causing OOMKills", [
                "Deploy hotfix v2.3.1 with patched request handler",
                "Increase pod memory limit from 512Mi to 1Gi temporarily",
                "Enable memory profiling in staging environment",
                "Schedule follow-up for memory leak root cause analysis",
            ]),
            "order-service": ("Missing database index on order_items table", [
                "Apply migration: CREATE INDEX idx_order_items_order_id ON order_items(order_id)",
                "Enable slow query logging with 100ms threshold",
                "Review query patterns from ORM for N+1 issues",
                "Set up automated index recommendation alerts",
            ]),
            "payment-service": ("Upstream payment provider timeout triggering cascading failures", [
                "Increase payment provider timeout from 5s to 15s",
                "Implement async payment processing with retry queue",
                "Add fallback payment provider configuration",
                "Create runbook for payment provider degradation",
            ]),
            "user-service": ("Configuration drift: AUTH_SECRET_KEY mismatch between pods", [
                "Sync AUTH_SECRET_KEY across all user-service pods",
                "Migrate secrets to HashiCorp Vault with versioning",
                "Implement config drift detection in CI/CD pipeline",
                "Add pod configuration hash to deployment manifest",
            ]),
        }
        
        root_cause_data = root_causes.get(
            self.service, 
            (f"Simulated root cause for {self.service}", [
                "Review service logs for anomalies",
                "Check recent deployments",
                "Verify configuration consistency",
            ])
        )
        root_cause = root_cause_data[0]
        recommendations = root_cause_data[1]
        
        # Show impressive findings panel (only in stream mode)
        if self.stream:
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
                f"• Affected pods: [cyan]checkout-service-7d4f8b6c9-{'{xxxxx}'[:5]}[/] (3 replicas)\n"
                f"• Correlation: [green]87% confidence[/] with traffic spike"
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
            "simulated": True,  # Flag indicating this is demo data
        }


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
    summary_text = (
        f"[bold green]✅ Investigation Successful[/]\n\n"
        f"[bold]Investigation ID:[/]  [cyan]{result['investigation_id']}[/]\n"
        f"[bold]Time to Resolution:[/] [yellow]{result['duration_seconds']:.1f}s[/]\n"
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
