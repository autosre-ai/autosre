#!/usr/bin/env python3
"""
OpenSRE Interactive Demo Script
================================

A bulletproof, production-ready demo for showcasing OpenSRE's AI-powered 
incident response capabilities.

Features:
- Rich terminal UI with panels, tables, and spinners
- Multiple fault scenarios (crash-loop, memory-leak, high-latency, OOM, CPU-spike)
- Real-time LLM analysis with timing information
- Robust error handling with retries and graceful degradation
- Mock mode for demos without LLM connectivity
- Idempotent - safe to run multiple times
- Works with local (Ollama) or cloud (OpenAI, Anthropic) LLMs

Usage:
    python demo.py                   # Interactive menu
    python demo.py --scenario 1      # Run specific scenario
    python demo.py --all             # Run all scenarios
    python demo.py --quick           # Quick demo (no interaction)
    python demo.py --mock            # Mock mode (no LLM required)
    python demo.py --diag            # Run diagnostics
"""

import argparse
import asyncio
import os
import platform
import random
import sys
import json
import time
from datetime import datetime
from typing import Optional

# Configure environment before imports
os.environ.setdefault('OPENSRE_LLM_PROVIDER', 'ollama')
os.environ.setdefault('OPENSRE_OLLAMA_HOST', 'http://localhost:11434')
os.environ.setdefault('OPENSRE_OLLAMA_MODEL', 'llama3:8b')

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Version info
__version__ = "1.0.0"
__date__ = "2026-04-22"

# ============================================================================
# SAFE IMPORTS WITH FALLBACKS
# ============================================================================

RICH_AVAILABLE = False
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.markdown import Markdown
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.box import ROUNDED, DOUBLE, HEAVY
    from rich.align import Align
    from rich.style import Style
    from rich.theme import Theme
    RICH_AVAILABLE = True
except ImportError:
    pass

# Fallback console for non-Rich environments
class FallbackConsole:
    """Simple console fallback when Rich is not available."""
    def print(self, *args, **kwargs):
        text = str(args[0]) if args else ""
        # Strip Rich markup
        import re
        text = re.sub(r'\[/?[^\]]+\]', '', text)
        print(text)
    
    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def input(self, prompt=""):
        import re
        prompt = re.sub(r'\[/?[^\]]+\]', '', prompt)
        return input(prompt)
    
    def status(self, text):
        class DummyContext:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return DummyContext()

if RICH_AVAILABLE:
    console = Console()
else:
    console = FallbackConsole()
    print("Warning: Rich library not found. Using fallback console.")
    print("For better experience: pip install rich")

# LLM adapter import
LLM_AVAILABLE = False
try:
    from opensre_core.adapters.llm import create_llm_adapter, LLMResponse
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_IMPORT_ERROR = str(e)

# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

class RetryConfig:
    """Configuration for retry behavior."""
    MAX_RETRIES = 3
    INITIAL_DELAY = 1.0
    MAX_DELAY = 30.0
    BACKOFF_FACTOR = 2.0
    TIMEOUT = 120.0  # 2 minutes per request


async def retry_with_backoff(func, *args, max_retries=None, **kwargs):
    """Execute function with exponential backoff retry."""
    max_retries = max_retries or RetryConfig.MAX_RETRIES
    delay = RetryConfig.INITIAL_DELAY
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=RetryConfig.TIMEOUT
            )
        except asyncio.TimeoutError:
            last_error = TimeoutError(f"Request timed out after {RetryConfig.TIMEOUT}s")
            if RICH_AVAILABLE:
                console.print(f"[yellow]⏱ Timeout on attempt {attempt + 1}/{max_retries}[/]")
            else:
                print(f"Timeout on attempt {attempt + 1}/{max_retries}")
        except Exception as e:
            last_error = e
            if RICH_AVAILABLE:
                console.print(f"[yellow]⚠ Error on attempt {attempt + 1}/{max_retries}: {e}[/]")
            else:
                print(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
        
        if attempt < max_retries - 1:
            jitter = random.uniform(0, delay * 0.1)
            wait_time = min(delay + jitter, RetryConfig.MAX_DELAY)
            if RICH_AVAILABLE:
                console.print(f"[dim]Retrying in {wait_time:.1f}s...[/]")
            else:
                print(f"Retrying in {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            delay *= RetryConfig.BACKOFF_FACTOR
    
    raise last_error or RuntimeError("All retries failed")


# ============================================================================
# MOCK LLM FOR DEMOS WITHOUT CONNECTIVITY
# ============================================================================

MOCK_RESPONSES = {
    1: """🎯 ROOT CAUSE:
Memory leak introduced in deployment v2.4.1 - likely an unclosed database connection or growing cache without eviction.

📊 CONFIDENCE: 94%

⚡ IMMEDIATE ACTION:
Execute rollback to v2.4.0 immediately: `kubectl rollout undo deployment/checkout-service -n production`

🔍 FOLLOW-UP:
1. Capture heap dump from affected pods before termination
2. Review v2.4.1 diff for connection handling changes
3. Add memory usage alerting at 70% threshold""",

    2: """🎯 ROOT CAUSE:
Slow/blocking database query causing connection pool exhaustion - likely a missing index or table lock from a long-running transaction.

📊 CONFIDENCE: 87%

⚡ IMMEDIATE ACTION:
1. Kill long-running queries: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE duration > interval '30 seconds'`
2. Temporarily increase pool size if possible

🔍 FOLLOW-UP:
1. Check pg_stat_statements for new slow queries
2. Review recent schema changes or data growth
3. Add query timeout limits""",

    3: """🎯 ROOT CAUSE:
TLS certificate expired due to failed auto-renewal - cert-manager renewal job failed silently 3 days ago.

📊 CONFIDENCE: 99%

⚡ IMMEDIATE ACTION:
1. Manually renew certificate: `kubectl cert-manager renew api-gateway-tls -n production`
2. Or apply emergency self-signed cert as temporary fix

🔍 FOLLOW-UP:
1. Fix cert-manager renewal job (check ACME/DNS configuration)
2. Add certificate expiry alerting (warn at 14 days, critical at 7 days)
3. Document manual renewal procedure""",

    4: """🎯 ROOT CAUSE:
Cascading failure - Redis image pull failure (ImagePullBackOff) causing catalog-service crash loops due to missing dependency.

📊 CONFIDENCE: 96%

⚡ IMMEDIATE ACTION:
1. Fix Redis image: `kubectl set image statefulset/redis redis=redis:7.0` (use known-good version)
2. Restart catalog-service pods after Redis is healthy

🔍 FOLLOW-UP:
1. Investigate why redis:7.2 image is unavailable (registry auth? image deleted?)
2. Pin image versions in production manifests
3. Add image pull alerting""",

    5: """🎯 ROOT CAUSE:
Traffic spike (12x normal) exceeding provisioned capacity - HPA at maximum replicas, CPU throttling active.

📊 CONFIDENCE: 91%

⚡ IMMEDIATE ACTION:
1. Increase HPA max replicas: `kubectl patch hpa frontend -p '{"spec":{"maxReplicas":20}}'`
2. Consider enabling CDN caching or rate limiting for protection

🔍 FOLLOW-UP:
1. Investigate traffic source (organic viral event? bot traffic?)
2. Review capacity planning for peak events
3. Consider auto-scaling node pool expansion"""
}


class MockLLMAdapter:
    """Mock LLM adapter for demos without real LLM connectivity."""
    
    def __init__(self):
        self.model = "mock-gpt-4"
        self.provider = "mock"
    
    async def health_check(self):
        return {
            "status": "healthy",
            "provider": "mock",
            "model": "mock-gpt-4",
            "details": "Mock mode - pre-recorded responses",
            "latency_ms": 1
        }
    
    async def generate(self, prompt: str, **kwargs):
        # Simulate thinking time
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Determine scenario from prompt keywords
        scenario_id = 1  # default
        if "connection pool" in prompt.lower() or "database" in prompt.lower():
            scenario_id = 2
        elif "ssl" in prompt.lower() or "certificate" in prompt.lower():
            scenario_id = 3
        elif "crashloop" in prompt.lower() or "redis" in prompt.lower():
            scenario_id = 4
        elif "cpu" in prompt.lower() or "traffic" in prompt.lower():
            scenario_id = 5
        
        content = MOCK_RESPONSES.get(scenario_id, MOCK_RESPONSES[1])
        
        # Create mock response object
        class MockResponse:
            pass
        
        response = MockResponse()
        response.content = content
        response.model = self.model
        response.provider = self.provider
        response.input_tokens = len(prompt.split()) * 2
        response.output_tokens = len(content.split()) * 2
        response.latency_ms = random.randint(500, 2000)
        response.cached = False
        
        return response


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

def create_header() -> "Panel":
    """Create the demo header panel."""
    if not RICH_AVAILABLE:
        return """
   ___                   ____  ____  _____ 
  / _ \\ _ __   ___ _ __ / ___||  _ \\| ____|
 | | | | '_ \\ / _ \\ '_ \\\\___ \\| |_) |  _|  
 | |_| | |_) |  __/ | | |___) |  _ <| |___ 
  \\___/| .__/ \\___|_| |_|____/|_| \\_\\_____|
       |_|                                  
                                            
  AI-Powered Incident Response for SRE Teams
"""
    
    header_text = (
        "[bold cyan]   ___                   ____  ____  _____ [/]\n"
        "[bold cyan]  / _ \\ _ __   ___ _ __ / ___||  _ \\| ____|[/]\n"
        "[bold cyan] | | | | '_ \\ / _ \\ '_ \\\\___ \\| |_) |  _|  [/]\n"
        "[bold cyan] | |_| | |_) |  __/ | | |___) |  _ <| |___ [/]\n"
        "[bold cyan]  \\___/| .__/ \\___|_| |_|____/|_| \\_\\_____|[/]\n"
        "[bold cyan]       |_|                                  [/]\n\n"
        "[dim]AI-Powered Incident Response for SRE Teams[/]"
    )
    return Panel(
        Align.center(header_text),
        box=DOUBLE,
        border_style="cyan",
        padding=(1, 0),
    )


def create_alert_panel(scenario: dict) -> "Panel":
    """Create an alert panel for a scenario."""
    if not RICH_AVAILABLE:
        alert = scenario["alert"]
        lines = [f"🚨 ALERT: {alert['title']}", "=" * 50]
        for metric, value, severity, info in alert["details"]:
            lines.append(f"  • {metric}: {value} ({info})")
        return "\n".join(lines)
    
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


def create_analysis_panel(response) -> "Panel":
    """Create a panel showing LLM analysis."""
    if not RICH_AVAILABLE:
        return f"\n🧠 AI Analysis\n{'=' * 40}\n{response.content}\n{'=' * 40}"
    
    return Panel(
        response.content,
        title="[bold green]🧠 AI Analysis[/]",
        border_style="green",
        box=ROUNDED,
    )


def create_stats_panel(response, elapsed: float) -> "Panel":
    """Create a panel showing analysis statistics."""
    if not RICH_AVAILABLE:
        return f"""
📊 Stats
  Model: {response.model}
  Provider: {response.provider}
  Latency: {elapsed:.2f}s
  Tokens: {response.input_tokens} in / {response.output_tokens} out
"""
    
    table = Table(show_header=False, box=None)
    table.add_column("Stat", style="dim")
    table.add_column("Value", style="bold cyan")
    
    table.add_row("Model:", response.model)
    table.add_row("Provider:", response.provider)
    table.add_row("Latency:", f"{elapsed:.2f}s")
    table.add_row("Input tokens:", str(response.input_tokens))
    table.add_row("Output tokens:", str(response.output_tokens))
    
    if hasattr(response, 'cached') and response.cached:
        table.add_row("Cache:", "[green]HIT[/]")
    
    return Panel(
        table,
        title="[bold blue]📊 Stats[/]",
        border_style="blue",
        box=ROUNDED,
    )


def create_action_panel() -> "Panel":
    """Create the action prompt panel."""
    if not RICH_AVAILABLE:
        return "\n⚡ ACTOR AGENT — Awaiting Approval\n[✅ Approve] [❌ Dismiss] [📝 Details]"
    
    return Panel(
        "[bold green]✅ Approve Action[/]  |  [bold red]❌ Dismiss[/]  |  [bold yellow]📝 View Details[/]",
        title="[bold]⚡ ACTOR AGENT — Awaiting Approval[/]",
        border_style="yellow",
        box=ROUNDED,
    )


def create_error_panel(error: str, hint: str = "") -> "Panel":
    """Create an error panel with recovery hint."""
    if not RICH_AVAILABLE:
        return f"\n❌ Error: {error}\n{hint}"
    
    content = f"[red]{error}[/]"
    if hint:
        content += f"\n\n[yellow]💡 {hint}[/]"
    
    return Panel(
        content,
        title="[bold red]❌ Error[/]",
        border_style="red",
        box=ROUNDED,
    )


# ============================================================================
# DIAGNOSTICS
# ============================================================================

async def run_diagnostics():
    """Run comprehensive diagnostics."""
    console.clear()
    
    if RICH_AVAILABLE:
        console.print(create_header())
        console.print()
        console.print("[bold]Running Diagnostics...[/]\n")
    else:
        print(create_header())
        print("\nRunning Diagnostics...\n")
    
    results = []
    
    # 1. Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    results.append(("Python Version", py_version, py_ok, "Requires 3.11+"))
    
    # 2. Platform
    results.append(("Platform", platform.platform(), True, ""))
    
    # 3. Rich library
    results.append(("Rich Library", "✓ Available" if RICH_AVAILABLE else "✗ Not found", RICH_AVAILABLE, "pip install rich"))
    
    # 4. OpenSRE core
    results.append(("OpenSRE Core", "✓ Imported" if LLM_AVAILABLE else "✗ Not found", LLM_AVAILABLE, "pip install -e ."))
    
    # 5. Ollama connectivity
    ollama_ok = False
    ollama_status = "Checking..."
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{os.environ.get('OPENSRE_OLLAMA_HOST', 'http://localhost:11434')}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])][:3]
                ollama_status = f"✓ Connected ({len(data.get('models', []))} models)"
                if models:
                    ollama_status += f" - {', '.join(models)}"
                ollama_ok = True
            else:
                ollama_status = f"✗ HTTP {response.status_code}"
    except Exception as e:
        ollama_status = f"✗ {type(e).__name__}: {str(e)[:50]}"
    
    results.append(("Ollama", ollama_status, ollama_ok, "ollama serve"))
    
    # 6. LLM Health Check
    if LLM_AVAILABLE and ollama_ok:
        try:
            llm = create_llm_adapter()
            health = await llm.health_check()
            if health["status"] == "healthy":
                results.append(("LLM Health", f"✓ {health['provider']} / {health['model']}", True, ""))
            else:
                results.append(("LLM Health", f"✗ {health.get('details', 'Unknown')}", False, ""))
        except Exception as e:
            results.append(("LLM Health", f"✗ {e}", False, ""))
    else:
        results.append(("LLM Health", "⊘ Skipped (dependencies missing)", None, ""))
    
    # Display results
    if RICH_AVAILABLE:
        table = Table(title="[bold]Diagnostic Results[/]", box=ROUNDED)
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Hint", style="dim")
        
        for name, status, ok, hint in results:
            if ok is True:
                style = "green"
            elif ok is False:
                style = "red"
            else:
                style = "yellow"
            table.add_row(name, Text(status, style=style), hint)
        
        console.print(table)
    else:
        print("=" * 60)
        for name, status, ok, hint in results:
            marker = "✓" if ok else ("✗" if ok is False else "?")
            print(f"  {marker} {name}: {status}")
            if hint and not ok:
                print(f"      Hint: {hint}")
        print("=" * 60)
    
    # Summary
    passed = sum(1 for _, _, ok, _ in results if ok is True)
    failed = sum(1 for _, _, ok, _ in results if ok is False)
    
    console.print()
    if failed == 0:
        if RICH_AVAILABLE:
            console.print("[bold green]✓ All checks passed! Demo ready.[/]")
        else:
            print("✓ All checks passed! Demo ready.")
    else:
        if RICH_AVAILABLE:
            console.print(f"[bold yellow]⚠ {failed} check(s) failed. Demo may not work correctly.[/]")
            console.print("[dim]Tip: Use --mock for demos without LLM connectivity[/]")
        else:
            print(f"⚠ {failed} check(s) failed. Demo may not work correctly.")
            print("Tip: Use --mock for demos without LLM connectivity")
    
    console.print()


# ============================================================================
# DEMO FLOW
# ============================================================================

async def check_llm_health(llm, silent: bool = False) -> bool:
    """Check if LLM is healthy with retry."""
    try:
        health = await retry_with_backoff(llm.health_check, max_retries=2)
        
        if health["status"] == "healthy":
            if not silent:
                if RICH_AVAILABLE:
                    console.print(f"[green]✓[/] LLM connected: {health['provider']} / {health['model']}")
                    if "details" in health:
                        console.print(f"[dim]  {health['details']}[/]")
                else:
                    print(f"✓ LLM connected: {health['provider']} / {health['model']}")
            return True
        else:
            if not silent:
                if RICH_AVAILABLE:
                    console.print(f"[red]✗[/] LLM error: {health.get('details', 'Unknown error')}")
                else:
                    print(f"✗ LLM error: {health.get('details', 'Unknown error')}")
            return False
    except Exception as e:
        if not silent:
            if RICH_AVAILABLE:
                console.print(f"[red]✗[/] LLM connection failed: {e}")
            else:
                print(f"✗ LLM connection failed: {e}")
        return False


async def run_scenario(scenario: dict, llm, interactive: bool = True) -> dict:
    """Run a single demo scenario with robust error handling."""
    start_time = time.time()
    result = {
        "scenario": scenario["name"],
        "scenario_id": scenario["id"],
        "success": False,
        "error": None,
        "latency": 0,
        "tokens": 0
    }
    
    try:
        # Clear screen and show header
        console.clear()
        if RICH_AVAILABLE:
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
        else:
            print(create_header())
            print(f"\n{'=' * 60}")
            print(f"Scenario {scenario['id']}: {scenario['name']}")
            print(f"Service: {scenario['service']} | Fault: {scenario['fault_type']}")
            print(f"{'=' * 60}\n")
            print(create_alert_panel(scenario))
            print()
        
        if interactive:
            console.input("[dim]Press Enter to start investigation...[/] " if RICH_AVAILABLE else "Press Enter to start investigation... ")
            if RICH_AVAILABLE:
                console.print()
        
        # Phase 1: Observer Agent
        if RICH_AVAILABLE:
            console.print("[bold cyan]🔍 OBSERVER AGENT[/] — Collecting signals...\n")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                for source, signal in scenario["signals"]:
                    task = progress.add_task(f"Querying {source}...", total=None)
                    await asyncio.sleep(random.uniform(0.3, 0.7))  # Simulate query time
                    progress.remove_task(task)
                    console.print(f"  [green]✓[/] [cyan]{source}[/]: {signal}")
            
            console.print()
        else:
            print("🔍 OBSERVER AGENT — Collecting signals...\n")
            for source, signal in scenario["signals"]:
                await asyncio.sleep(0.3)
                print(f"  ✓ {source}: {signal}")
            print()
        
        # Phase 2: Reasoner Agent
        if RICH_AVAILABLE:
            console.print("[bold green]🧠 REASONER AGENT[/] — Analyzing with LLM...\n")
        else:
            print("🧠 REASONER AGENT — Analyzing with LLM...\n")
        
        llm_start = time.time()
        
        try:
            # Try with retry
            if RICH_AVAILABLE:
                with console.status("[bold cyan]Generating analysis...[/]"):
                    response = await retry_with_backoff(
                        llm.generate,
                        scenario["prompt"],
                        max_retries=3
                    )
            else:
                print("Generating analysis...")
                response = await retry_with_backoff(
                    llm.generate,
                    scenario["prompt"],
                    max_retries=3
                )
            
            llm_elapsed = time.time() - llm_start
            
            if RICH_AVAILABLE:
                console.print(create_analysis_panel(response))
                console.print()
                console.print(create_stats_panel(response, llm_elapsed))
                console.print()
            else:
                print(create_analysis_panel(response))
                print(create_stats_panel(response, llm_elapsed))
            
            result["success"] = True
            result["latency"] = llm_elapsed
            result["tokens"] = response.input_tokens + response.output_tokens
            
        except Exception as e:
            llm_elapsed = time.time() - llm_start
            error_msg = str(e)
            
            if RICH_AVAILABLE:
                console.print(create_error_panel(
                    f"LLM analysis failed: {error_msg}",
                    "Try: --mock flag for demo without LLM, or check ollama status"
                ))
            else:
                print(f"\n❌ LLM analysis failed: {error_msg}")
                print("Tip: Try --mock flag for demo without LLM")
            
            result["error"] = error_msg
            result["latency"] = llm_elapsed
            return result
        
        # Phase 3: Actor Agent
        if RICH_AVAILABLE:
            console.print(create_action_panel())
            console.print()
        else:
            print(create_action_panel())
        
        total_elapsed = time.time() - start_time
        
        if RICH_AVAILABLE:
            console.print(f"[dim]Total time: {total_elapsed:.1f}s[/]\n")
        else:
            print(f"Total time: {total_elapsed:.1f}s\n")
        
        if interactive:
            console.input("[dim]Press Enter to continue...[/] " if RICH_AVAILABLE else "Press Enter to continue... ")
        
        return result
        
    except KeyboardInterrupt:
        result["error"] = "Interrupted by user"
        return result
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        if RICH_AVAILABLE:
            console.print(create_error_panel(str(e)))
        else:
            print(f"\n❌ Unexpected error: {e}")
        return result


async def run_demo_menu(llm) -> None:
    """Run the interactive demo menu."""
    while True:
        try:
            console.clear()
            if RICH_AVAILABLE:
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
                console.print("[dim]  d. Run diagnostics[/]")
                console.print("[dim]  q. Quit[/]")
                console.print()
            else:
                print(create_header())
                print("\nSelect a Scenario:")
                for s in SCENARIOS:
                    print(f"  {s['id']}. {s['name']} ({s['service']})")
                print("\n  a. Run all scenarios")
                print("  d. Run diagnostics")
                print("  q. Quit\n")
            
            choice = console.input("[bold cyan]Enter choice:[/] " if RICH_AVAILABLE else "Enter choice: ").strip().lower()
            
            if choice == "q":
                if RICH_AVAILABLE:
                    console.print("\n[bold cyan]👋 Thanks for trying OpenSRE![/]\n")
                else:
                    print("\n👋 Thanks for trying OpenSRE!\n")
                break
            elif choice == "a":
                await run_all_scenarios(llm)
            elif choice == "d":
                await run_diagnostics()
                console.input("[dim]Press Enter to continue...[/] " if RICH_AVAILABLE else "Press Enter to continue... ")
            else:
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(SCENARIOS):
                        await run_scenario(SCENARIOS[idx - 1], llm, interactive=True)
                    else:
                        if RICH_AVAILABLE:
                            console.print("[red]Invalid choice[/]")
                        else:
                            print("Invalid choice")
                        await asyncio.sleep(1)
                except ValueError:
                    if RICH_AVAILABLE:
                        console.print("[red]Invalid choice[/]")
                    else:
                        print("Invalid choice")
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            if RICH_AVAILABLE:
                console.print("\n[dim]Interrupted[/]")
            else:
                print("\nInterrupted")
            break


async def run_all_scenarios(llm) -> list:
    """Run all scenarios and show summary."""
    results = []
    
    for scenario in SCENARIOS:
        result = await run_scenario(scenario, llm, interactive=False)
        results.append(result)
        # Brief pause between scenarios
        await asyncio.sleep(0.5)
    
    # Show summary
    console.clear()
    if RICH_AVAILABLE:
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
        passed = 0
        
        for r in results:
            if r["success"]:
                status = "[green]✓ PASS[/]"
                latency = f"{r.get('latency', 0):.2f}s"
                tokens = str(r.get("tokens", 0))
                total_time += r.get("latency", 0)
                total_tokens += r.get("tokens", 0)
                passed += 1
            else:
                status = "[red]✗ FAIL[/]"
                latency = "-"
                tokens = "-"
            
            table.add_row(r["scenario"], status, latency, tokens)
        
        console.print(table)
        console.print()
        console.print(f"[bold]Results:[/] {passed}/{len(results)} passed | Total: {total_time:.1f}s | {total_tokens} tokens")
        console.print()
    else:
        print(create_header())
        print("\n" + "=" * 60)
        print("Demo Summary")
        print("=" * 60)
        
        total_time = 0
        total_tokens = 0
        passed = 0
        
        for r in results:
            status = "✓ PASS" if r["success"] else "✗ FAIL"
            latency = f"{r.get('latency', 0):.2f}s" if r["success"] else "-"
            print(f"  {status} | {r['scenario']} | {latency}")
            if r["success"]:
                total_time += r.get("latency", 0)
                total_tokens += r.get("tokens", 0)
                passed += 1
        
        print("=" * 60)
        print(f"Results: {passed}/{len(results)} passed | Total: {total_time:.1f}s | {total_tokens} tokens")
        print()
    
    console.input("[dim]Press Enter to continue...[/] " if RICH_AVAILABLE else "Press Enter to continue... ")
    
    return results


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point with comprehensive error handling."""
    parser = argparse.ArgumentParser(
        description="OpenSRE Interactive Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py                    # Interactive menu
  python demo.py --scenario 1       # Run memory leak scenario
  python demo.py --all --quick      # Run all scenarios non-interactively
  python demo.py --mock             # Demo without LLM (pre-recorded responses)
  python demo.py --diag             # Run diagnostics

Tips:
  - Use --mock for reliable demos without LLM connectivity
  - Use --quick to skip interactive prompts
  - Use --diag to troubleshoot issues
        """
    )
    parser.add_argument(
        "--scenario", "-s",
        type=int,
        choices=[1, 2, 3, 4, 5],
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
        "--mock", "-m",
        action="store_true",
        help="Mock mode (no LLM required, uses pre-recorded responses)",
    )
    parser.add_argument(
        "--diag",
        action="store_true",
        help="Run diagnostics and exit",
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
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export results to JSON file",
    )
    
    args = parser.parse_args()
    
    # Version
    if args.version:
        print(f"OpenSRE Demo v{__version__} ({__date__})")
        return
    
    # Diagnostics
    if args.diag:
        await run_diagnostics()
        return
    
    # Override provider/model if specified
    if args.provider:
        os.environ["OPENSRE_LLM_PROVIDER"] = args.provider
    if args.model:
        provider = args.provider or os.environ.get("OPENSRE_LLM_PROVIDER", "ollama")
        if provider == "openai":
            os.environ["OPENSRE_OPENAI_MODEL"] = args.model
        elif provider == "anthropic":
            os.environ["OPENSRE_ANTHROPIC_MODEL"] = args.model
        else:
            os.environ["OPENSRE_OLLAMA_MODEL"] = args.model
    
    # Show header
    console.clear()
    if RICH_AVAILABLE:
        console.print(create_header())
        console.print()
        console.print(f"[dim]v{__version__} | {datetime.now().strftime('%Y-%m-%d %H:%M')}[/]")
        console.print()
        console.print("[bold]Initializing...[/]\n")
    else:
        print(create_header())
        print(f"\nv{__version__} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("\nInitializing...\n")
    
    # Initialize LLM
    if args.mock:
        if RICH_AVAILABLE:
            console.print("[yellow]📋 Mock mode[/] — Using pre-recorded responses")
        else:
            print("📋 Mock mode — Using pre-recorded responses")
        llm = MockLLMAdapter()
    else:
        if not LLM_AVAILABLE:
            if RICH_AVAILABLE:
                console.print(create_error_panel(
                    f"OpenSRE core not available: {LLM_IMPORT_ERROR}",
                    "Use --mock for demos without LLM, or install: pip install -e ."
                ))
            else:
                print(f"❌ OpenSRE core not available: {LLM_IMPORT_ERROR}")
                print("Tip: Use --mock for demos without LLM")
            sys.exit(1)
        
        try:
            llm = create_llm_adapter()
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(create_error_panel(
                    f"Failed to create LLM adapter: {e}",
                    "Use --mock for demos without LLM"
                ))
            else:
                print(f"❌ Failed to create LLM adapter: {e}")
            sys.exit(1)
        
        # Health check
        if not await check_llm_health(llm):
            if RICH_AVAILABLE:
                console.print("\n[yellow]💡 Tips:[/]")
                console.print("  • Start Ollama: [cyan]ollama serve[/]")
                console.print("  • Pull a model: [cyan]ollama pull llama3:8b[/]")
                console.print("  • Use mock mode: [cyan]python demo.py --mock[/]")
            else:
                print("\n💡 Tips:")
                print("  • Start Ollama: ollama serve")
                print("  • Pull a model: ollama pull llama3:8b")
                print("  • Use mock mode: python demo.py --mock")
            sys.exit(1)
    
    if RICH_AVAILABLE:
        console.print()
    else:
        print()
    
    # Run demo based on args
    results = []
    try:
        if args.scenario:
            result = await run_scenario(SCENARIOS[args.scenario - 1], llm, interactive=not args.quick)
            results = [result]
        elif args.all:
            results = await run_all_scenarios(llm)
        else:
            await run_demo_menu(llm)
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            console.print("\n[dim]Demo interrupted[/]")
        else:
            print("\nDemo interrupted")
    
    # Export results if requested
    if args.export and results:
        import json
        export_data = {
            "version": __version__,
            "timestamp": datetime.now().isoformat(),
            "mode": "mock" if args.mock else "live",
            "provider": llm.provider if hasattr(llm, 'provider') else "mock",
            "model": llm.model if hasattr(llm, 'model') else "mock-gpt-4",
            "scenarios": results,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "total_latency_s": sum(r.get("latency", 0) for r in results),
                "total_tokens": sum(r.get("tokens", 0) for r in results),
            }
        }
        try:
            with open(args.export, 'w') as f:
                json.dump(export_data, f, indent=2)
            if RICH_AVAILABLE:
                console.print(f"[green]✓[/] Results exported to: {args.export}")
            else:
                print(f"✓ Results exported to: {args.export}")
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[red]✗[/] Export failed: {e}")
            else:
                print(f"✗ Export failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
