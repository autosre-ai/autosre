"""
AutoSRE Demo Commands

Run demo investigations and seed test data.
"""

import asyncio
import json
import random
from datetime import datetime, timedelta
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
    help="Demo scenarios and test data",
    no_args_is_help=True,
)

console = Console()


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
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario ID to run"),
    list_scenarios: bool = typer.Option(False, "--list", "-l", help="List available scenarios"),
    random_scenario: bool = typer.Option(False, "--random", "-r", help="Run a random scenario"),
    interactive: bool = typer.Option(True, "--interactive/--batch", help="Interactive mode"),
):
    """
    Run a demo investigation.
    
    Simulates an incident investigation with mock data to demonstrate
    AutoSRE's capabilities.
    
    Examples:
        autosre demo run --list
        autosre demo run --scenario redis-connection
        autosre demo run --random
    """
    if list_scenarios:
        _list_scenarios()
        return
    
    # Select scenario
    if random_scenario:
        selected = random.choice(DEMO_SCENARIOS)
    elif scenario:
        selected = next((s for s in DEMO_SCENARIOS if s["id"] == scenario), None)
        if not selected:
            console.print(f"[red]Scenario '{scenario}' not found[/]")
            console.print("Use --list to see available scenarios")
            raise typer.Exit(1)
    else:
        # Interactive selection
        _list_scenarios()
        console.print()
        scenario_id = typer.prompt("Select scenario ID", default="redis-connection")
        selected = next((s for s in DEMO_SCENARIOS if s["id"] == scenario_id), None)
        if not selected:
            console.print(f"[red]Scenario '{scenario_id}' not found[/]")
            raise typer.Exit(1)
    
    # Show scenario info
    console.print()
    console.print(Panel(
        f"[bold]{selected['name']}[/]\n\n"
        f"[bold]Alert:[/] {selected['alert']}\n"
        f"[bold]Service:[/] {selected['service']}\n"
        f"[bold]Severity:[/] {selected['severity']}\n\n"
        f"[dim]{selected['description']}[/]",
        title="🎭 Demo Scenario",
        border_style="magenta",
    ))
    
    if interactive:
        if not typer.confirm("\nStart investigation?", default=True):
            raise typer.Abort()
    
    # Run the investigation
    from autosre.cli.commands.investigate import InvestigationRunner
    
    runner = InvestigationRunner(
        alert=selected["alert"],
        service=selected["service"],
        severity=selected["severity"],
        mock=True,
        output_format="text",
        stream=True,
    )
    
    result = runner.run()
    
    # Show completion
    console.print()
    console.print(Panel(
        f"[green]✓ Demo investigation completed[/]\n\n"
        f"[bold]Investigation ID:[/] {result['investigation_id']}\n"
        f"[bold]Duration:[/] {result['duration_seconds']:.1f}s\n"
        f"[bold]Root Cause:[/] {result['root_cause']}",
        title="Demo Complete",
        border_style="green",
    ))


def _list_scenarios():
    """Display available scenarios."""
    table = Table(title="Available Demo Scenarios", show_header=True)
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


@app.command()
def seed(
    count: int = typer.Option(10, "--count", "-n", help="Number of episodes to seed"),
    clear_first: bool = typer.Option(False, "--clear", help="Clear existing memory first"),
):
    """
    Seed episodic memory with demo data.
    
    Populates the memory database with realistic incident episodes
    for testing memory search and pattern matching.
    
    Examples:
        autosre demo seed
        autosre demo seed --count 50
        autosre demo seed --clear --count 20
    """
    from autosre.memory import EpisodicMemory, Episode
    
    memory = EpisodicMemory()
    
    if clear_first:
        memory.clear()
        console.print("[yellow]Cleared existing memory[/]")
    
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
        task = progress.add_task("Seeding episodes...", total=count)
        
        for i in range(count):
            template = random.choice(templates)
            service = random.choice(template["services"])
            root_cause = random.choice(template["root_causes"])
            
            # Random timestamp in last 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            created_at = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)
            
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
        f"[green]✓[/] Seeded {count} episodes\n\n"
        f"[bold]Total Episodes:[/] {stats['total_episodes']}\n"
        f"[bold]Alert Types:[/] {len(stats.get('top_alert_types', []))}\n"
        f"[bold]Resolution Rate:[/] {stats.get('resolution_rate', 0):.0%}",
        title="Demo Data Seeded",
        border_style="green",
    ))


@app.command()
def scenarios():
    """List all available demo scenarios."""
    _list_scenarios()


@app.command()
def benchmark(
    iterations: int = typer.Option(5, "--iterations", "-n", help="Number of iterations"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Specific scenario"),
):
    """
    Benchmark investigation performance.
    
    Runs multiple investigations and reports timing statistics.
    
    Examples:
        autosre demo benchmark
        autosre demo benchmark --iterations 10
    """
    from autosre.cli.commands.investigate import InvestigationRunner
    import time
    
    scenarios_to_run = [next((s for s in DEMO_SCENARIOS if s["id"] == scenario), None)] if scenario else DEMO_SCENARIOS
    scenarios_to_run = [s for s in scenarios_to_run if s]
    
    if not scenarios_to_run:
        console.print("[red]No scenarios to run[/]")
        raise typer.Exit(1)
    
    results = []
    
    console.print()
    console.print(f"[bold]Running benchmark: {iterations} iterations[/]")
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        total = iterations * len(scenarios_to_run)
        task = progress.add_task("Running...", total=total)
        
        for i in range(iterations):
            for s in scenarios_to_run:
                start = time.time()
                
                runner = InvestigationRunner(
                    alert=s["alert"],
                    service=s["service"],
                    severity=s["severity"],
                    mock=True,
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
                
                progress.update(task, advance=1, description=f"{s['id']} ({elapsed:.2f}s)")
    
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
    table = Table(title="Benchmark Results", show_header=True)
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
        f"[bold]Max:[/] {max_duration:.3f}s",
        title="Summary",
        border_style="cyan",
    ))


@app.command()
def topology():
    """
    Show demo service topology.
    
    Displays a sample microservices topology used in demo scenarios.
    """
    from rich.tree import Tree
    
    # Build topology tree
    tree = Tree("🏢 [bold]Demo Platform[/]")
    
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
    console.print(Panel(tree, title="Demo Service Topology", border_style="cyan"))
    console.print()
