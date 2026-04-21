#!/usr/bin/env python3
"""
OpenSRE Interactive Demo Script
================================

A polished, production-ready demo for showcasing OpenSRE's AI-powered 
incident response capabilities.

Features:
- Rich terminal UI with panels, tables, and spinners
- Multiple fault scenarios (crash-loop, memory-leak, high-latency, OOM, CPU-spike)
- Real-time LLM analysis with timing information
- Idempotent - safe to run multiple times
- Works with local (Ollama) or cloud (OpenAI, Anthropic) LLMs

Usage:
    python demo.py                   # Interactive menu
    python demo.py --scenario 1      # Run specific scenario
    python demo.py --all             # Run all scenarios
    python demo.py --quick           # Quick demo (no interaction)
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

# Configure environment before imports
os.environ.setdefault('OPENSRE_LLM_PROVIDER', 'ollama')
os.environ.setdefault('OPENSRE_OLLAMA_HOST', 'http://localhost:11434')
os.environ.setdefault('OPENSRE_OLLAMA_MODEL', 'llama3:8b')

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.markdown import Markdown
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.box import ROUNDED, DOUBLE, HEAVY
    from rich.align import Align
except ImportError:
    print("Error: Rich library required. Run: pip install rich")
    sys.exit(1)

try:
    from opensre_core.adapters.llm import create_llm_adapter, LLMResponse
except ImportError as e:
    print(f"Error importing OpenSRE core: {e}")
    print("Ensure you're running from the opensre directory with venv activated")
    sys.exit(1)

# Initialize Rich console
console = Console()

# ============================================================================
# DEMO SCENARIOS
# ============================================================================

SCENARIOS = [
    {
        "id": 1,
        "name": "Memory Leak After Deployment",
        "service": "checkout-service",
        "fault_type": "memory-leak",
        "severity": "critical",
        "alert": {
            "title": "checkout-service Memory Alert",
            "details": [
                ("Error Rate", "8.3%", "critical", "threshold: 1%"),
                ("Memory", "1.8GB", "warning", "baseline: 500MB"),
                ("OOMKilled", "3 pods", "critical", "last 10 min"),
                ("Recent Deploy", "v2.4.1", "info", "12 min ago"),
            ]
        },
        "signals": [
            ("prometheus", "memory_working_set_bytes trending +15% over 10m"),
            ("kubernetes", "3x OOMKilled events in checkout-service namespace"),
            ("deploy", "v2.4.1 rolled out 12 minutes ago by deploy-bot"),
            ("baseline", "Normal memory ~500MB, current 1.8GB (+260%)"),
        ],
        "prompt": """You are an expert SRE investigating a production incident.

SITUATION:
- checkout-service error rate spiked to 8.3%
- Memory usage trending up across all pods
- 3 pods OOMKilled in last 10 minutes
- Deployment v2.4.1 rolled out 12 minutes ago

METRICS COLLECTED:
- memory_working_set_bytes: 1.8GB (baseline: 500MB)
- container_restart_count: 3 in 10 min
- http_request_duration_p99: 2.3s (baseline: 200ms)

Provide your analysis in this EXACT format:

🎯 ROOT CAUSE:
[One sentence diagnosis]

📊 CONFIDENCE: [X]%

⚡ IMMEDIATE ACTION:
[What to do RIGHT NOW]

🔍 FOLLOW-UP:
[What to investigate next]""",
    },
    {
        "id": 2,
        "name": "Database Connection Pool Exhaustion",
        "service": "payment-service",
        "fault_type": "high-latency",
        "severity": "high",
        "alert": {
            "title": "payment-service Latency Alert",
            "details": [
                ("P99 Latency", "2.3s", "critical", "threshold: 500ms"),
                ("DB Pool", "95%", "critical", "utilized"),
                ("Active Queries", "847", "warning", "normal: ~50"),
                ("Recent Deploy", "None", "info", "24h clean"),
            ]
        },
        "signals": [
            ("prometheus", "db_pool_active_connections at 95% (95/100)"),
            ("postgres", "Multiple queries taking >30s in slow query log"),
            ("kubernetes", "No deployment events in last 24h"),
            ("traffic", "Normal request volume - not a traffic spike"),
        ],
        "prompt": """You are an expert SRE investigating a production incident.

SITUATION:
- payment-service P99 latency spiked to 2.3s
- Database connection pool at 95% utilized
- Active queries: 847 (normal: ~50)
- No recent deployments
- Issue started 8 minutes ago

METRICS COLLECTED:
- db_pool_active_connections: 95/100
- pg_stat_activity_count: 847 active queries
- http_request_duration_p99: 2.3s
- No deployment events in last 24h

Provide your analysis in this EXACT format:

🎯 ROOT CAUSE:
[One sentence diagnosis]

📊 CONFIDENCE: [X]%

⚡ IMMEDIATE ACTION:
[What to do RIGHT NOW]

🔍 FOLLOW-UP:
[What to investigate next]""",
    },
    {
        "id": 3,
        "name": "Certificate Expiry",
        "service": "api-gateway",
        "fault_type": "ssl-error",
        "severity": "critical",
        "alert": {
            "title": "api-gateway SSL Alert",
            "details": [
                ("SSL Errors", "100%", "critical", "all HTTPS failing"),
                ("Cert Status", "EXPIRED", "critical", "2h ago"),
                ("Last Renewal", "90 days", "info", "auto-renew failed"),
                ("Impact", "Total outage", "critical", "all endpoints"),
            ]
        },
        "signals": [
            ("cert-manager", "Certificate expired: api-gateway-tls"),
            ("cert-manager", "Renewal job FAILED 3 days ago (silent failure)"),
            ("alerting", "Gap detected: no cert expiry alert configured"),
            ("downstream", "All services healthy - only gateway affected"),
        ],
        "prompt": """You are an expert SRE investigating a production incident.

SITUATION:
- api-gateway SSL handshake failures at 100%
- All HTTPS endpoints returning errors
- Certificate expired 2 hours ago
- Last successful renewal was 90 days ago

METRICS COLLECTED:
- ssl_certificate_expiry_seconds: -7200 (expired 2h ago)
- nginx_ssl_handshake_errors_total: 50000+ in 2h
- cert-manager renewal job: FAILED 3 days ago

Provide your analysis in this EXACT format:

🎯 ROOT CAUSE:
[One sentence diagnosis]

📊 CONFIDENCE: [X]%

⚡ IMMEDIATE ACTION:
[What to do RIGHT NOW]

🔍 FOLLOW-UP:
[What to investigate next]""",
    },
    {
        "id": 4,
        "name": "Pod Crash Loop",
        "service": "catalog-service",
        "fault_type": "crash-loop",
        "severity": "high",
        "alert": {
            "title": "catalog-service Pod Crash Alert",
            "details": [
                ("Status", "CrashLoopBackOff", "critical", "all replicas"),
                ("Restarts", "12", "critical", "last 5 min"),
                ("Exit Code", "1", "warning", "application error"),
                ("Impact", "Service degraded", "high", "50% capacity"),
            ]
        },
        "signals": [
            ("kubernetes", "Pod catalog-service-7f8d9 in CrashLoopBackOff"),
            ("logs", "Exception: Failed to connect to Redis at redis:6379"),
            ("kubernetes", "Redis pod redis-0 status: ImagePullBackOff"),
            ("events", "Failed to pull image: redis:7.2 - not found"),
        ],
        "prompt": """You are an expert SRE investigating a production incident.

SITUATION:
- catalog-service pods in CrashLoopBackOff
- 12 restarts in last 5 minutes
- Application logs show "Failed to connect to Redis"
- Redis pod in ImagePullBackOff state

METRICS COLLECTED:
- container_restart_count: 12 in 5 min
- pod_status: CrashLoopBackOff
- redis_connection_errors: 100%
- Application log: "Exception: Failed to connect to Redis at redis:6379"

Provide your analysis in this EXACT format:

🎯 ROOT CAUSE:
[One sentence diagnosis]

📊 CONFIDENCE: [X]%

⚡ IMMEDIATE ACTION:
[What to do RIGHT NOW]

🔍 FOLLOW-UP:
[What to investigate next]""",
    },
    {
        "id": 5,
        "name": "CPU Spike Under Load",
        "service": "frontend",
        "fault_type": "cpu-spike",
        "severity": "medium",
        "alert": {
            "title": "frontend CPU Throttling Alert",
            "details": [
                ("CPU Usage", "98%", "critical", "throttled"),
                ("Request Rate", "12x normal", "warning", "traffic spike"),
                ("Latency", "5.2s", "high", "degraded"),
                ("HPA Status", "Scaling", "info", "max replicas hit"),
            ]
        },
        "signals": [
            ("prometheus", "container_cpu_usage_seconds at 98% of limit"),
            ("kubernetes", "HPA: frontend scaled to 10/10 replicas (max)"),
            ("traffic", "Inbound requests 12x normal (viral event)"),
            ("throttle", "cpu_cfs_throttled_periods_total increasing rapidly"),
        ],
        "prompt": """You are an expert SRE investigating a production incident.

SITUATION:
- frontend service at 98% CPU utilization (throttled)
- HPA scaled to maximum replicas (10/10)
- Request rate 12x normal (viral traffic event)
- Response latency degraded to 5.2s

METRICS COLLECTED:
- container_cpu_usage_seconds_total: 98% of 500m limit
- horizontal_pod_autoscaler_status_desired_replicas: 10 (max)
- http_requests_total: 12x baseline
- container_cpu_cfs_throttled_periods_total: increasing

Provide your analysis in this EXACT format:

🎯 ROOT CAUSE:
[One sentence diagnosis]

📊 CONFIDENCE: [X]%

⚡ IMMEDIATE ACTION:
[What to do RIGHT NOW]

🔍 FOLLOW-UP:
[What to investigate next]""",
    },
]


# ============================================================================
# UI COMPONENTS
# ============================================================================

def create_header() -> Panel:
    """Create the demo header panel."""
    header_text = """
[bold cyan]   ___                   ____  ____  _____ [/]
[bold cyan]  / _ \ _ __   ___ _ __ / ___||  _ \| ____|[/]
[bold cyan] | | | | '_ \ / _ \ '_ \\\\___ \| |_) |  _|  [/]
[bold cyan] | |_| | |_) |  __/ | | |___) |  _ <| |___ [/]
[bold cyan]  \___/| .__/ \___|_| |_|____/|_| \_\_____|[/]
[bold cyan]       |_|                                  [/]

[dim]AI-Powered Incident Response for SRE Teams[/]
    """
    return Panel(
        Align.center(header_text.strip()),
        box=DOUBLE,
        border_style="cyan",
        padding=(1, 0),
    )


def create_alert_panel(scenario: dict) -> Panel:
    """Create an alert panel for a scenario."""
    alert = scenario["alert"]
    
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")
    table.add_column("Info", style="dim")
    
    for metric, value, severity, info in alert["details"]:
        if severity == "critical":
            style = "bold red"
        elif severity == "high":
            style = "bold yellow"
        elif severity == "warning":
            style = "yellow"
        else:
            style = "dim"
        table.add_row(f"• {metric}:", Text(value, style=style), f"({info})")
    
    return Panel(
        table,
        title=f"[bold red]🚨 ALERT: {alert['title']}[/]",
        border_style="red",
        box=HEAVY,
    )


def create_signals_table(signals: list) -> Table:
    """Create a table showing collected signals."""
    table = Table(
        title="[bold cyan]📡 Collected Signals[/]",
        box=ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Source", style="cyan", width=12)
    table.add_column("Signal", style="white")
    
    for source, signal in signals:
        table.add_row(f"[bold]{source}[/]", signal)
    
    return table


def create_analysis_panel(response: LLMResponse) -> Panel:
    """Create a panel showing LLM analysis."""
    return Panel(
        response.content,
        title="[bold green]🧠 AI Analysis[/]",
        border_style="green",
        box=ROUNDED,
    )


def create_stats_panel(response: LLMResponse, elapsed: float) -> Panel:
    """Create a panel showing analysis statistics."""
    table = Table(show_header=False, box=None)
    table.add_column("Stat", style="dim")
    table.add_column("Value", style="bold cyan")
    
    table.add_row("Model:", response.model)
    table.add_row("Provider:", response.provider)
    table.add_row("Latency:", f"{elapsed:.2f}s")
    table.add_row("Input tokens:", str(response.input_tokens))
    table.add_row("Output tokens:", str(response.output_tokens))
    
    if response.cached:
        table.add_row("Cache:", "[green]HIT[/]")
    
    return Panel(
        table,
        title="[bold blue]📊 Stats[/]",
        border_style="blue",
        box=ROUNDED,
    )


def create_action_panel() -> Panel:
    """Create the action prompt panel."""
    return Panel(
        "[bold green]✅ Approve Action[/]  |  [bold red]❌ Dismiss[/]  |  [bold yellow]📝 View Details[/]",
        title="[bold]⚡ ACTOR AGENT — Awaiting Approval[/]",
        border_style="yellow",
        box=ROUNDED,
    )


# ============================================================================
# DEMO FLOW
# ============================================================================

async def check_llm_health(llm) -> bool:
    """Check if LLM is healthy."""
    with console.status("[bold cyan]Checking LLM connection...[/]"):
        health = await llm.health_check()
    
    if health["status"] == "healthy":
        console.print(f"[green]✓[/] LLM connected: {health['provider']} / {health['model']}")
        if "details" in health:
            console.print(f"[dim]  {health['details']}[/]")
        return True
    else:
        console.print(f"[red]✗[/] LLM error: {health.get('details', 'Unknown error')}")
        return False


async def run_scenario(scenario: dict, llm, interactive: bool = True) -> dict:
    """Run a single demo scenario."""
    start_time = time.time()
    result = {"scenario": scenario["name"], "success": False, "error": None}
    
    # Clear screen and show header
    console.clear()
    console.print(create_header())
    console.print()
    
    # Scenario title
    console.print(Panel(
        f"[bold]{scenario['name']}[/]\n[dim]Service: {scenario['service']} | Fault: {scenario['fault_type']} | Severity: {scenario['severity']}[/]",
        title=f"[bold]Scenario {scenario['id']} of {len(SCENARIOS)}[/]",
        border_style="cyan",
    ))
    console.print()
    
    # Show alert
    console.print(create_alert_panel(scenario))
    console.print()
    
    if interactive:
        console.input("[dim]Press Enter to start investigation...[/] ")
        console.print()
    
    # Phase 1: Observer Agent
    console.print("[bold cyan]🔍 OBSERVER AGENT[/] — Collecting signals...\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for source, signal in scenario["signals"]:
            task = progress.add_task(f"Querying {source}...", total=None)
            await asyncio.sleep(0.5)  # Simulate query time
            progress.remove_task(task)
            console.print(f"  [green]✓[/] [cyan]{source}[/]: {signal}")
    
    console.print()
    
    # Phase 2: Reasoner Agent
    console.print("[bold green]🧠 REASONER AGENT[/] — Analyzing with LLM...\n")
    
    llm_start = time.time()
    try:
        with console.status("[bold cyan]Generating analysis...[/]"):
            response = await llm.generate(scenario["prompt"])
        llm_elapsed = time.time() - llm_start
        
        console.print(create_analysis_panel(response))
        console.print()
        console.print(create_stats_panel(response, llm_elapsed))
        console.print()
        
        result["success"] = True
        result["latency"] = llm_elapsed
        result["tokens"] = response.input_tokens + response.output_tokens
        
    except Exception as e:
        llm_elapsed = time.time() - llm_start
        console.print(f"[red]✗ LLM Error: {e}[/]")
        result["error"] = str(e)
        return result
    
    # Phase 3: Actor Agent
    console.print(create_action_panel())
    console.print()
    
    total_elapsed = time.time() - start_time
    console.print(f"[dim]Total time: {total_elapsed:.1f}s[/]\n")
    
    if interactive:
        console.input("[dim]Press Enter to continue...[/] ")
    
    return result


async def run_demo_menu(llm) -> None:
    """Run the interactive demo menu."""
    while True:
        console.clear()
        console.print(create_header())
        console.print()
        
        # Scenario menu
        table = Table(
            title="[bold]Select a Scenario[/]",
            box=ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("#", style="bold", width=3)
        table.add_column("Scenario", style="white")
        table.add_column("Service", style="cyan")
        table.add_column("Severity", style="white")
        
        for s in SCENARIOS:
            severity_style = {
                "critical": "bold red",
                "high": "yellow", 
                "medium": "green",
            }.get(s["severity"], "white")
            table.add_row(
                str(s["id"]),
                s["name"],
                s["service"],
                Text(s["severity"].upper(), style=severity_style),
            )
        
        console.print(table)
        console.print()
        console.print("[dim]  a. Run all scenarios[/]")
        console.print("[dim]  q. Quit[/]")
        console.print()
        
        choice = console.input("[bold cyan]Enter choice:[/] ").strip().lower()
        
        if choice == "q":
            console.print("\n[bold cyan]👋 Thanks for trying OpenSRE![/]\n")
            break
        elif choice == "a":
            await run_all_scenarios(llm)
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(SCENARIOS):
                    await run_scenario(SCENARIOS[idx - 1], llm, interactive=True)
                else:
                    console.print("[red]Invalid choice[/]")
                    await asyncio.sleep(1)
            except ValueError:
                console.print("[red]Invalid choice[/]")
                await asyncio.sleep(1)


async def run_all_scenarios(llm) -> list:
    """Run all scenarios and show summary."""
    results = []
    
    for scenario in SCENARIOS:
        result = await run_scenario(scenario, llm, interactive=False)
        results.append(result)
    
    # Show summary
    console.clear()
    console.print(create_header())
    console.print()
    
    table = Table(
        title="[bold]Demo Summary[/]",
        box=ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Scenario", style="white")
    table.add_column("Status", style="white", justify="center")
    table.add_column("Latency", style="cyan", justify="right")
    table.add_column("Tokens", style="dim", justify="right")
    
    total_time = 0
    total_tokens = 0
    
    for r in results:
        if r["success"]:
            status = "[green]✓ PASS[/]"
            latency = f"{r.get('latency', 0):.2f}s"
            tokens = str(r.get("tokens", 0))
            total_time += r.get("latency", 0)
            total_tokens += r.get("tokens", 0)
        else:
            status = "[red]✗ FAIL[/]"
            latency = "-"
            tokens = "-"
        
        table.add_row(r["scenario"], status, latency, tokens)
    
    console.print(table)
    console.print()
    console.print(f"[bold]Total:[/] {total_time:.1f}s | {total_tokens} tokens")
    console.print()
    
    console.input("[dim]Press Enter to continue...[/] ")
    
    return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OpenSRE Interactive Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario", "-s",
        type=int,
        help="Run a specific scenario (1-5)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all scenarios",
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode (no interaction prompts)",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "anthropic", "azure"],
        help="LLM provider to use",
    )
    parser.add_argument(
        "--model",
        help="Model name to use",
    )
    
    args = parser.parse_args()
    
    # Override provider/model if specified
    if args.provider:
        os.environ["OPENSRE_LLM_PROVIDER"] = args.provider
    if args.model:
        if args.provider == "openai":
            os.environ["OPENSRE_OPENAI_MODEL"] = args.model
        elif args.provider == "anthropic":
            os.environ["OPENSRE_ANTHROPIC_MODEL"] = args.model
        else:
            os.environ["OPENSRE_OLLAMA_MODEL"] = args.model
    
    # Show header
    console.clear()
    console.print(create_header())
    console.print()
    
    # Initialize LLM
    console.print("[bold]Initializing...[/]\n")
    
    try:
        llm = create_llm_adapter()
    except Exception as e:
        console.print(f"[red]✗ Failed to create LLM adapter: {e}[/]")
        sys.exit(1)
    
    # Health check
    if not await check_llm_health(llm):
        console.print("\n[yellow]Tip: Start Ollama with: ollama serve[/]")
        console.print("[yellow]Then pull a model: ollama pull llama3:8b[/]")
        sys.exit(1)
    
    console.print()
    
    # Run demo based on args
    if args.scenario:
        if 1 <= args.scenario <= len(SCENARIOS):
            await run_scenario(SCENARIOS[args.scenario - 1], llm, interactive=not args.quick)
        else:
            console.print(f"[red]Invalid scenario: {args.scenario}. Choose 1-{len(SCENARIOS)}[/]")
            sys.exit(1)
    elif args.all:
        await run_all_scenarios(llm)
    else:
        await run_demo_menu(llm)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/]")
        sys.exit(0)
