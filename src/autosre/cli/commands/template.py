"""
AutoSRE Template Commands

Manage investigation templates for common incident types.

Usage:
    autosre template list                  # List all available templates
    autosre template show <name>           # Show template details
    autosre template use <name>            # Start investigation from template
    autosre template create                # Create new template interactively
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

app = typer.Typer(
    name="template",
    help="Manage investigation templates for common incident types",
    no_args_is_help=True,
)

console = Console()


# =============================================================================
# Built-in Investigation Templates
# =============================================================================

BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "high-latency": {
        "id": "high-latency",
        "name": "High Latency Investigation",
        "description": "Investigate service latency spikes and slow response times",
        "category": "performance",
        "severity": "high",
        "alert_patterns": [
            "high latency",
            "slow response",
            "p99 latency",
            "response time",
            "timeout",
        ],
        "investigation_steps": [
            "Check service metrics for latency distribution",
            "Analyze database query performance",
            "Review recent deployments for changes",
            "Check downstream service health",
            "Examine resource utilization (CPU, memory)",
            "Look for connection pool exhaustion",
        ],
        "data_sources": ["prometheus", "kubernetes", "logs"],
        "promql_queries": [
            'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="$SERVICE"}[5m]))',
            'rate(http_requests_total{service="$SERVICE", status=~"5.."}[5m])',
        ],
        "common_causes": [
            "Database query performance degradation",
            "Connection pool exhaustion",
            "Resource contention (CPU/memory)",
            "Network latency to downstream services",
            "Garbage collection pauses",
            "Lock contention in application",
        ],
        "runbook_refs": ["high-cpu", "database-slowdown"],
    },
    "oom": {
        "id": "oom",
        "name": "Out of Memory Investigation",
        "description": "Investigate OOM kills and memory pressure issues",
        "category": "resources",
        "severity": "critical",
        "alert_patterns": [
            "OOM",
            "out of memory",
            "OOMKilled",
            "memory pressure",
            "memory exhaustion",
        ],
        "investigation_steps": [
            "Check container/pod OOM events",
            "Analyze memory usage trends",
            "Identify memory leak patterns",
            "Review heap dumps if available",
            "Check for memory limits misconfiguration",
            "Examine recent code changes affecting memory",
        ],
        "data_sources": ["kubernetes", "prometheus", "logs"],
        "promql_queries": [
            'container_memory_usage_bytes{pod=~"$SERVICE.*"}',
            'kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}',
            'container_memory_working_set_bytes{pod=~"$SERVICE.*"} / container_spec_memory_limit_bytes{pod=~"$SERVICE.*"}',
        ],
        "common_causes": [
            "Memory leak in application code",
            "Undersized memory limits",
            "Large data processing without streaming",
            "Cache growing unbounded",
            "Connection object accumulation",
            "Thread/goroutine leak",
        ],
        "runbook_refs": ["crashloop", "high-memory"],
    },
    "disk-full": {
        "id": "disk-full",
        "name": "Disk Full Investigation",
        "description": "Investigate disk space exhaustion and storage issues",
        "category": "resources",
        "severity": "critical",
        "alert_patterns": [
            "disk full",
            "no space left",
            "storage exhausted",
            "disk pressure",
            "volume full",
        ],
        "investigation_steps": [
            "Check disk usage by mount point",
            "Identify large files and directories",
            "Review log rotation configuration",
            "Check for orphaned PVCs",
            "Analyze disk usage growth rate",
            "Verify backup/snapshot cleanup",
        ],
        "data_sources": ["kubernetes", "prometheus", "logs"],
        "promql_queries": [
            'node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}',
            'kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes',
            'predict_linear(node_filesystem_avail_bytes[6h], 24*3600)',
        ],
        "common_causes": [
            "Log files growing unbounded",
            "Temporary files not cleaned up",
            "Database/cache storage growth",
            "Failed backup cleanup",
            "Container image layer accumulation",
            "Orphaned volumes",
        ],
        "runbook_refs": ["disk-cleanup", "log-rotation"],
    },
    "5xx-errors": {
        "id": "5xx-errors",
        "name": "5xx Error Rate Investigation",
        "description": "Investigate elevated 5xx error rates and service failures",
        "category": "availability",
        "severity": "high",
        "alert_patterns": [
            "5xx errors",
            "500 errors",
            "502 bad gateway",
            "503 unavailable",
            "error rate",
        ],
        "investigation_steps": [
            "Check error rate by endpoint",
            "Analyze error logs for stack traces",
            "Review recent deployments",
            "Check upstream/downstream service health",
            "Verify configuration changes",
            "Check for rate limiting or circuit breaker trips",
        ],
        "data_sources": ["prometheus", "logs", "kubernetes"],
        "promql_queries": [
            'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))',
            'topk(5, sum by (endpoint) (rate(http_requests_total{status=~"5.."}[5m])))',
            'rate(http_requests_total{status="503"}[5m])',
        ],
        "common_causes": [
            "Deployment with bugs",
            "Database connection failures",
            "Downstream service outage",
            "Configuration error",
            "Resource exhaustion",
            "Network connectivity issues",
        ],
        "runbook_refs": ["5xx-errors", "deployment-rollback"],
    },
    "crashloop": {
        "id": "crashloop",
        "name": "CrashLoopBackOff Investigation",
        "description": "Investigate pods stuck in CrashLoopBackOff state",
        "category": "availability",
        "severity": "critical",
        "alert_patterns": [
            "CrashLoopBackOff",
            "crash loop",
            "pod restarting",
            "container crash",
            "restart count",
        ],
        "investigation_steps": [
            "Get pod status and restart count",
            "Check container logs for crash reason",
            "Examine pod events",
            "Review recent configuration changes",
            "Check resource limits",
            "Verify readiness/liveness probes",
        ],
        "data_sources": ["kubernetes", "logs", "prometheus"],
        "promql_queries": [
            'kube_pod_container_status_restarts_total{pod=~"$SERVICE.*"}',
            'kube_pod_status_phase{phase!="Running"}',
            'changes(kube_pod_container_status_restarts_total[1h])',
        ],
        "common_causes": [
            "Application startup failure",
            "Missing configuration/secrets",
            "Failed health checks",
            "OOM during startup",
            "Dependency not available",
            "Permission/security context issues",
        ],
        "runbook_refs": ["crashloop", "pod-debugging"],
    },
    "cpu-throttling": {
        "id": "cpu-throttling",
        "name": "CPU Throttling Investigation",
        "description": "Investigate CPU throttling and high CPU utilization",
        "category": "performance",
        "severity": "medium",
        "alert_patterns": [
            "CPU throttling",
            "high CPU",
            "CPU limit",
            "CPU saturation",
            "slow processing",
        ],
        "investigation_steps": [
            "Check CPU utilization vs limits",
            "Analyze throttling metrics",
            "Identify CPU-intensive processes",
            "Review CPU limit configuration",
            "Check for noisy neighbors",
            "Profile application CPU usage",
        ],
        "data_sources": ["prometheus", "kubernetes"],
        "promql_queries": [
            'rate(container_cpu_cfs_throttled_seconds_total{pod=~"$SERVICE.*"}[5m])',
            'sum(rate(container_cpu_usage_seconds_total{pod=~"$SERVICE.*"}[5m])) / sum(container_spec_cpu_quota{pod=~"$SERVICE.*"} / container_spec_cpu_period{pod=~"$SERVICE.*"})',
            'topk(5, sum by (pod) (rate(container_cpu_usage_seconds_total[5m])))',
        ],
        "common_causes": [
            "Undersized CPU limits",
            "Inefficient code paths",
            "Unbounded parallelism",
            "Expensive computations",
            "Regex/parsing bottlenecks",
            "Serialization overhead",
        ],
        "runbook_refs": ["high-cpu", "resource-tuning"],
    },
    "connection-pool": {
        "id": "connection-pool",
        "name": "Connection Pool Exhaustion",
        "description": "Investigate database/HTTP connection pool issues",
        "category": "performance",
        "severity": "high",
        "alert_patterns": [
            "connection pool",
            "pool exhausted",
            "connection timeout",
            "max connections",
            "connection wait",
        ],
        "investigation_steps": [
            "Check connection pool metrics",
            "Analyze connection acquisition times",
            "Review connection leak patterns",
            "Check pool configuration",
            "Identify long-running connections",
            "Verify connection timeout settings",
        ],
        "data_sources": ["prometheus", "logs"],
        "promql_queries": [
            'hikaricp_connections_active{service="$SERVICE"}',
            'hikaricp_connections_pending{service="$SERVICE"}',
            'histogram_quantile(0.99, rate(hikaricp_connections_acquire_seconds_bucket[5m]))',
        ],
        "common_causes": [
            "Connection leak in application",
            "Slow database queries holding connections",
            "Pool size misconfiguration",
            "Burst traffic exceeding pool capacity",
            "Missing connection timeout",
            "Transaction not closed properly",
        ],
        "runbook_refs": ["database-slowdown", "connection-pool"],
    },
}


def _get_templates_dir() -> Path:
    """Get the custom templates directory path."""
    # Check for environment variable first
    if templates_path := os.environ.get("AUTOSRE_TEMPLATES_PATH"):
        return Path(templates_path)
    
    # Default to ~/.autosre/templates
    return Path.home() / ".autosre" / "templates"


def _load_custom_templates() -> List[Dict[str, Any]]:
    """Load custom templates from the templates directory."""
    templates_dir = _get_templates_dir()
    templates = []
    
    if not templates_dir.exists():
        return templates
    
    for path in sorted(templates_dir.iterdir()):
        if path.suffix in [".yaml", ".yml", ".json"]:
            try:
                with open(path) as f:
                    if path.suffix == ".json":
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)
                data["path"] = str(path)
                data["source"] = "custom"
                templates.append(data)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse {path.name}: {e}[/]")
    
    return templates


def _get_all_templates() -> List[Dict[str, Any]]:
    """Get all templates (built-in + custom)."""
    templates = []
    
    # Add built-in templates
    for template in BUILTIN_TEMPLATES.values():
        t = template.copy()
        t["source"] = "builtin"
        templates.append(t)
    
    # Add custom templates
    templates.extend(_load_custom_templates())
    
    return templates


def _find_template(name: str) -> Optional[Dict[str, Any]]:
    """Find a template by name or ID."""
    name_lower = name.lower()
    
    # Check built-in templates first
    if name_lower in BUILTIN_TEMPLATES:
        t = BUILTIN_TEMPLATES[name_lower].copy()
        t["source"] = "builtin"
        return t
    
    # Search all templates
    for template in _get_all_templates():
        if template.get("id", "").lower() == name_lower:
            return template
        if template.get("name", "").lower() == name_lower:
            return template
    
    return None


@app.command("list")
def list_templates(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, simple"),
):
    """
    List all available investigation templates.
    
    Examples:
        autosre template list
        autosre template list --category performance
        autosre template list --format json
    """
    templates = _get_all_templates()
    
    if not templates:
        console.print("[yellow]No templates found.[/]")
        return
    
    # Filter by category if specified
    if category:
        templates = [t for t in templates if t.get("category", "").lower() == category.lower()]
    
    if format == "json":
        output = [{
            "id": t.get("id"),
            "name": t.get("name"),
            "category": t.get("category"),
            "severity": t.get("severity"),
            "source": t.get("source"),
        } for t in templates]
        console.print(json.dumps(output, indent=2))
        return
    
    if format == "simple":
        for t in templates:
            source_icon = "📦" if t.get("source") == "builtin" else "📝"
            console.print(f"{source_icon} {t.get('id', 'unknown')} - {t.get('name', '')}")
        return
    
    # Table format (default)
    table = Table(title="📋 Investigation Templates", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Category", style="dim")
    table.add_column("Severity", justify="center")
    table.add_column("Source", justify="center")
    
    severity_colors = {
        "critical": "[red]●[/] critical",
        "high": "[yellow]●[/] high",
        "medium": "[blue]●[/] medium",
        "low": "[green]●[/] low",
    }
    
    for t in templates:
        severity = t.get("severity", "medium")
        severity_display = severity_colors.get(severity, severity)
        source = "📦 builtin" if t.get("source") == "builtin" else "📝 custom"
        
        table.add_row(
            t.get("id", "unknown"),
            t.get("name", ""),
            t.get("category", ""),
            severity_display,
            source,
        )
    
    console.print(table)
    console.print(f"\n[dim]Use 'autosre template show <id>' for details[/]")


@app.command("show")
def show_template(
    name: str = typer.Argument(..., help="Template name or ID"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw template data"),
):
    """
    Show details of a specific investigation template.
    
    Examples:
        autosre template show high-latency
        autosre template show oom --raw
    """
    template = _find_template(name)
    
    if not template:
        console.print(f"[red]Error: Template '{name}' not found.[/]")
        console.print("\n[dim]Available templates:[/]")
        for t in _get_all_templates():
            console.print(f"  • {t.get('id')}")
        raise typer.Exit(1)
    
    if raw:
        console.print(json.dumps(template, indent=2))
        return
    
    # Show formatted template
    severity_colors = {
        "critical": "red",
        "high": "yellow",
        "medium": "blue",
        "low": "green",
    }
    severity = template.get("severity", "medium")
    severity_color = severity_colors.get(severity, "white")
    
    # Header panel
    console.print(Panel(
        f"[bold]{template.get('name', name)}[/]\n\n"
        f"[dim]{template.get('description', 'No description')}[/]",
        title=f"📋 Template: {template.get('id')}",
        border_style="cyan",
    ))
    
    # Metadata
    meta_table = Table(show_header=False, box=None, padding=(0, 2))
    meta_table.add_column("Key", style="dim")
    meta_table.add_column("Value")
    meta_table.add_row("Category:", template.get("category", "N/A"))
    meta_table.add_row("Severity:", f"[{severity_color}]{severity}[/]")
    meta_table.add_row("Source:", template.get("source", "builtin"))
    console.print(meta_table)
    console.print()
    
    # Alert patterns
    if template.get("alert_patterns"):
        console.print("[bold]Alert Patterns:[/]")
        for pattern in template.get("alert_patterns", []):
            console.print(f"  • [cyan]{pattern}[/]")
        console.print()
    
    # Investigation steps
    if template.get("investigation_steps"):
        console.print("[bold]Investigation Steps:[/]")
        for i, step in enumerate(template.get("investigation_steps", []), 1):
            console.print(f"  {i}. {step}")
        console.print()
    
    # Data sources
    if template.get("data_sources"):
        console.print(f"[bold]Data Sources:[/] {', '.join(template.get('data_sources', []))}")
        console.print()
    
    # PromQL queries
    if template.get("promql_queries"):
        console.print("[bold]PromQL Queries:[/]")
        for query in template.get("promql_queries", []):
            console.print(f"  [green]{query}[/]")
        console.print()
    
    # Common causes
    if template.get("common_causes"):
        console.print("[bold]Common Causes:[/]")
        for cause in template.get("common_causes", []):
            console.print(f"  • {cause}")
        console.print()
    
    # Related runbooks
    if template.get("runbook_refs"):
        console.print(f"[bold]Related Runbooks:[/] {', '.join(template.get('runbook_refs', []))}")
    
    console.print(f"\n[dim]Use 'autosre template use {template.get('id')}' to start an investigation[/]")


@app.command("use")
def use_template(
    name: str = typer.Argument(..., help="Template name or ID"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Target service name"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Kubernetes namespace"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without executing"),
):
    """
    Start an investigation using a template.
    
    Launches an investigation with pre-configured steps and queries
    based on the template's incident type.
    
    Examples:
        autosre template use high-latency --service api-gateway
        autosre template use oom --service worker --namespace production
        autosre template use 5xx-errors --dry-run
    """
    template = _find_template(name)
    
    if not template:
        console.print(f"[red]Error: Template '{name}' not found.[/]")
        raise typer.Exit(1)
    
    # Build alert description from template
    alert_desc = template.get("name", name)
    if service:
        alert_desc = f"{alert_desc} on {service}"
    
    severity = template.get("severity", "high")
    
    console.print(Panel(
        f"[bold]Template:[/] {template.get('name')}\n"
        f"[bold]Service:[/] {service or 'Not specified'}\n"
        f"[bold]Namespace:[/] {namespace or 'default'}\n"
        f"[bold]Severity:[/] {severity}",
        title="🚀 Starting Template-Based Investigation",
        border_style="green",
    ))
    
    if dry_run:
        console.print("\n[yellow]DRY RUN - Would execute the following:[/]\n")
        console.print("[bold]Investigation Steps:[/]")
        for i, step in enumerate(template.get("investigation_steps", []), 1):
            console.print(f"  {i}. {step}")
        console.print("\n[bold]PromQL Queries to run:[/]")
        for query in template.get("promql_queries", []):
            # Substitute service name
            q = query.replace("$SERVICE", service or "<service>")
            console.print(f"  [green]{q}[/]")
        console.print("\n[dim]Remove --dry-run to execute[/]")
        return
    
    # Confirm before starting
    if not Confirm.ask(f"\n[bold]Start investigation for '{alert_desc}'?[/]"):
        console.print("[dim]Cancelled.[/]")
        raise typer.Exit(0)
    
    # Import and run investigation
    try:
        from autosre.cli.commands.investigate import run as investigate_run
        
        # Run investigation with template context
        investigate_run(
            alert=alert_desc,
            service=service,
            severity=severity,
            output="text",
            stream=True,
            save=None,
            demo=False,
            watch=False,
            watch_interval=60,
        )
    except ImportError:
        console.print("[yellow]Investigation module not available.[/]")
        console.print("\n[dim]Would run:[/]")
        console.print(f"  autosre investigate run \"{alert_desc}\" --service {service or 'N/A'} --severity {severity}")


@app.command("create")
def create_template(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Template name"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Create a new investigation template interactively.
    
    Guides you through creating a custom template that can be
    reused for similar incidents.
    
    Examples:
        autosre template create
        autosre template create --name my-template
        autosre template create --output ~/templates/custom.yaml
    """
    console.print(Panel(
        "[bold]Create New Investigation Template[/]\n\n"
        "This wizard will help you create a custom template\n"
        "for investigating a specific type of incident.",
        title="📝 Template Creator",
        border_style="cyan",
    ))
    
    # Gather template info
    template_id = Prompt.ask(
        "\n[bold]Template ID[/] (lowercase, hyphenated)",
        default=name or "custom-template",
    )
    
    template_name = Prompt.ask(
        "[bold]Template Name[/]",
        default=template_id.replace("-", " ").title() + " Investigation",
    )
    
    description = Prompt.ask(
        "[bold]Description[/]",
        default="Custom investigation template",
    )
    
    category = Prompt.ask(
        "[bold]Category[/]",
        default="custom",
        choices=["performance", "availability", "resources", "security", "custom"],
    )
    
    severity = Prompt.ask(
        "[bold]Default Severity[/]",
        default="high",
        choices=["critical", "high", "medium", "low"],
    )
    
    console.print("\n[bold]Alert Patterns[/] (comma-separated keywords)")
    patterns_input = Prompt.ask("Patterns", default="")
    alert_patterns = [p.strip() for p in patterns_input.split(",") if p.strip()]
    
    console.print("\n[bold]Investigation Steps[/] (enter each step, empty line to finish)")
    steps = []
    while True:
        step = Prompt.ask(f"Step {len(steps) + 1}", default="")
        if not step:
            break
        steps.append(step)
    
    console.print("\n[bold]Data Sources[/] (comma-separated)")
    sources_input = Prompt.ask("Sources", default="prometheus,kubernetes,logs")
    data_sources = [s.strip() for s in sources_input.split(",") if s.strip()]
    
    console.print("\n[bold]Common Causes[/] (enter each cause, empty line to finish)")
    causes = []
    while True:
        cause = Prompt.ask(f"Cause {len(causes) + 1}", default="")
        if not cause:
            break
        causes.append(cause)
    
    # Build template
    template = {
        "id": template_id,
        "name": template_name,
        "description": description,
        "category": category,
        "severity": severity,
        "alert_patterns": alert_patterns if alert_patterns else [template_id],
        "investigation_steps": steps if steps else ["Gather initial context", "Check metrics", "Analyze logs"],
        "data_sources": data_sources,
        "promql_queries": [],
        "common_causes": causes if causes else ["Unknown - investigate further"],
        "runbook_refs": [],
        "created_at": datetime.now().isoformat(),
    }
    
    # Determine output path
    if output:
        output_path = Path(output)
    else:
        templates_dir = _get_templates_dir()
        templates_dir.mkdir(parents=True, exist_ok=True)
        output_path = templates_dir / f"{template_id}.yaml"
    
    # Show preview
    console.print(Panel(
        yaml.dump(template, default_flow_style=False, sort_keys=False),
        title="📄 Template Preview",
        border_style="green",
    ))
    
    # Confirm save
    if Confirm.ask(f"\n[bold]Save template to {output_path}?[/]"):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)
        console.print(f"\n[green]✓[/] Template saved to [bold]{output_path}[/]")
        console.print(f"[dim]Use 'autosre template use {template_id}' to start an investigation[/]")
    else:
        console.print("[dim]Template not saved.[/]")


if __name__ == "__main__":
    app()
