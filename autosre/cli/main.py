"""
AutoSRE CLI - Command-line interface for the AI SRE agent.

Usage:
    autosre init
    autosre context show
    autosre context sync
    autosre eval run --scenario <name>
    autosre eval list
    autosre sandbox create
    autosre agent analyze --alert <file>
"""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="autosre")
def cli():
    """AutoSRE - Open-source AI SRE Agent
    
    Built foundation-first for reliable incident response.
    """
    pass


@cli.command()
@click.option("--dir", "-d", "directory", default=".", help="Directory to initialize")
def init(directory: str):
    """Initialize AutoSRE in the current directory.
    
    Creates:
    - .autosre/ directory with databases
    - runbooks/ directory for runbook files
    - .env.example with configuration template
    """
    base_dir = Path(directory)
    autosre_dir = base_dir / ".autosre"
    runbooks_dir = base_dir / "runbooks"
    
    # Create directories
    console.print("[cyan]Initializing AutoSRE...[/]")
    
    autosre_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  [green]✓[/] Created {autosre_dir}")
    
    runbooks_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  [green]✓[/] Created {runbooks_dir}")
    
    # Create .env.example
    env_example = base_dir / ".env.example"
    if not env_example.exists():
        env_content = '''# AutoSRE Configuration
# Copy this to .env and fill in your values

# LLM Provider (ollama, openai, anthropic)
OPENSRE_LLM_PROVIDER=ollama

# Ollama (default, local)
OPENSRE_OLLAMA_HOST=http://localhost:11434
OPENSRE_OLLAMA_MODEL=llama3.1:8b

# OpenAI (optional)
# OPENSRE_OPENAI_API_KEY=sk-...
# OPENSRE_OPENAI_MODEL=gpt-4o-mini

# Anthropic (optional)
# OPENSRE_ANTHROPIC_API_KEY=sk-ant-...
# OPENSRE_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Prometheus
OPENSRE_PROMETHEUS_URL=http://localhost:9090

# Kubernetes
# OPENSRE_KUBECONFIG=~/.kube/config
OPENSRE_K8S_NAMESPACES=default

# Agent Behavior
OPENSRE_REQUIRE_APPROVAL=true
OPENSRE_AUTO_APPROVE_LOW_RISK=false
OPENSRE_CONFIDENCE_THRESHOLD=0.7

# Logging
OPENSRE_LOG_LEVEL=INFO
OPENSRE_LOG_FORMAT=text
'''
        env_example.write_text(env_content)
        console.print(f"  [green]✓[/] Created {env_example}")
    
    # Create sample runbook
    sample_runbook = runbooks_dir / "high-cpu.yaml"
    if not sample_runbook.exists():
        runbook_content = '''# Sample runbook for high CPU troubleshooting
id: high-cpu
title: High CPU Troubleshooting
description: Steps to investigate and resolve high CPU usage

alerts:
  - HighCPUUsage
  - ContainerCPUHigh

steps:
  - name: Check current CPU usage
    command: kubectl top pods -n {{ namespace }}
    
  - name: Check recent deployments
    command: kubectl rollout history deployment/{{ service }} -n {{ namespace }}
    
  - name: Check for memory pressure
    command: kubectl describe pod {{ pod }} -n {{ namespace }} | grep -A 5 "Resources:"
    
  - name: Check logs for errors
    command: kubectl logs {{ pod }} -n {{ namespace }} --tail=100
    
automated: false
tags:
  - cpu
  - performance
'''
        sample_runbook.write_text(runbook_content)
        console.print(f"  [green]✓[/] Created sample runbook at {sample_runbook}")
    
    console.print("\n[green]✓ AutoSRE initialized![/]")
    console.print("\nNext steps:")
    console.print("  1. Copy .env.example to .env and configure")
    console.print("  2. Run 'autosre context sync' to populate context")
    console.print("  3. Run 'autosre eval list' to see available scenarios")


@cli.group()
def context():
    """Manage context store (services, ownership, changes)."""
    pass


@context.command("show")
@click.option("--services", "-s", is_flag=True, help="Show services")
@click.option("--changes", "-c", is_flag=True, help="Show recent changes")
@click.option("--alerts", "-a", is_flag=True, help="Show firing alerts")
@click.option("--runbooks", "-r", is_flag=True, help="Show runbooks")
def context_show(services: bool, changes: bool, alerts: bool, runbooks: bool):
    """Show context store contents."""
    from autosre.foundation.context_store import ContextStore
    
    store = ContextStore()
    summary = store.get_context_summary()
    
    # If no specific flag, show summary
    if not any([services, changes, alerts, runbooks]):
        table = Table(title="Context Store Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="green")
        
        table.add_row("Services", str(summary["services"]))
        table.add_row("Ownership Mappings", str(summary["ownership_mappings"]))
        table.add_row("Changes (24h)", str(summary["changes_last_24h"]))
        table.add_row("Runbooks", str(summary["runbooks"]))
        table.add_row("Firing Alerts", str(summary["firing_alerts"]))
        table.add_row("Open Incidents", str(summary["open_incidents"]))
        
        console.print(table)
        return
    
    if services:
        svc_list = store.list_services()
        table = Table(title="Services")
        table.add_column("Name", style="cyan")
        table.add_column("Namespace", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Replicas", style="yellow")
        
        for svc in svc_list:
            status_style = {
                "healthy": "green",
                "degraded": "yellow",
                "down": "red",
                "unknown": "dim",
            }.get(svc.status.value, "dim")
            
            table.add_row(
                svc.name,
                svc.namespace,
                f"[{status_style}]{svc.status.value}[/]",
                f"{svc.ready_replicas}/{svc.replicas}",
            )
        
        console.print(table)
    
    if changes:
        change_list = store.get_recent_changes(hours=24)
        table = Table(title="Recent Changes (24h)")
        table.add_column("Time", style="dim")
        table.add_column("Service", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Description", style="white")
        table.add_column("Author", style="green")
        
        for change in change_list[:20]:
            table.add_row(
                change.timestamp.strftime("%Y-%m-%d %H:%M"),
                change.service_name,
                change.change_type.value,
                change.description[:50] + "..." if len(change.description) > 50 else change.description,
                change.author,
            )
        
        console.print(table)
    
    if alerts:
        alert_list = store.get_firing_alerts()
        table = Table(title="Firing Alerts")
        table.add_column("Name", style="cyan")
        table.add_column("Severity", style="red")
        table.add_column("Service", style="blue")
        table.add_column("Summary", style="white")
        
        for alert in alert_list:
            sev_style = {
                "critical": "red bold",
                "high": "red",
                "medium": "yellow",
                "low": "blue",
                "info": "dim",
            }.get(alert.severity.value, "dim")
            
            table.add_row(
                alert.name,
                f"[{sev_style}]{alert.severity.value}[/]",
                alert.service_name or "—",
                alert.summary[:60] + "..." if len(alert.summary) > 60 else alert.summary,
            )
        
        console.print(table)
    
    if runbooks:
        rb_list = store.find_runbook()
        table = Table(title="Runbooks")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Alerts", style="blue")
        table.add_column("Automated", style="green")
        
        for rb in rb_list:
            table.add_row(
                rb.id,
                rb.title,
                ", ".join(rb.alert_names[:3]) + ("..." if len(rb.alert_names) > 3 else ""),
                "✓" if rb.automated else "—",
            )
        
        console.print(table)


@context.command("sync")
@click.option("--kubernetes", "-k", is_flag=True, help="Sync from Kubernetes")
@click.option("--prometheus", "-p", is_flag=True, help="Sync from Prometheus")
@click.option("--github", "-g", is_flag=True, help="Sync from GitHub")
@click.option("--all", "-a", "sync_all", is_flag=True, help="Sync from all sources")
def context_sync(kubernetes: bool, prometheus: bool, github: bool, sync_all: bool):
    """Sync context from external sources."""
    import asyncio
    from autosre.foundation.context_store import ContextStore
    from autosre.foundation.connectors import (
        KubernetesConnector,
        PrometheusConnector,
        GitHubConnector,
    )
    
    store = ContextStore()
    
    async def do_sync():
        total = 0
        
        if kubernetes or sync_all:
            console.print("[cyan]Syncing from Kubernetes...[/]")
            connector = KubernetesConnector()
            if await connector.connect():
                count = await connector.safe_sync(store)
                console.print(f"  [green]✓[/] Synced {count} items from Kubernetes")
                total += count
                await connector.disconnect()
            else:
                console.print(f"  [red]✗[/] Failed to connect: {connector._last_error}")
        
        if prometheus or sync_all:
            console.print("[cyan]Syncing from Prometheus...[/]")
            connector = PrometheusConnector({"prometheus_url": "http://localhost:9090"})
            if await connector.connect():
                count = await connector.safe_sync(store)
                console.print(f"  [green]✓[/] Synced {count} items from Prometheus")
                total += count
                await connector.disconnect()
            else:
                console.print(f"  [yellow]![/] Prometheus not available: {connector._last_error}")
        
        if github or sync_all:
            console.print("[cyan]Syncing from GitHub...[/]")
            import os
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                console.print("  [yellow]![/] GITHUB_TOKEN not set, skipping")
            else:
                connector = GitHubConnector({"token": token})
                if await connector.connect():
                    count = await connector.safe_sync(store)
                    console.print(f"  [green]✓[/] Synced {count} items from GitHub")
                    total += count
                    await connector.disconnect()
                else:
                    console.print(f"  [red]✗[/] Failed to connect: {connector._last_error}")
        
        console.print(f"\n[green]Total items synced: {total}[/]")
    
    asyncio.run(do_sync())


@cli.group()
def eval():
    """Run evaluation scenarios."""
    pass


@eval.command("list")
def eval_list():
    """List available evaluation scenarios."""
    from autosre.evals import list_scenarios
    
    scenarios = list_scenarios()
    
    table = Table(title="Available Scenarios")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Difficulty", style="yellow")
    
    for scenario in scenarios:
        table.add_row(
            scenario["name"],
            scenario["description"],
            scenario.get("difficulty", "medium"),
        )
    
    console.print(table)


@eval.command("run")
@click.option("--scenario", "-s", required=True, help="Scenario name to run")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def eval_run(scenario: str, verbose: bool):
    """Run an evaluation scenario."""
    import asyncio
    from autosre.evals import run_scenario
    
    console.print(f"[cyan]Running scenario: {scenario}[/]\n")
    
    async def do_run():
        result = await run_scenario(scenario, verbose=verbose)
        
        if result["success"]:
            console.print(f"\n[green]✓ Scenario passed![/]")
        else:
            console.print(f"\n[red]✗ Scenario failed[/]")
        
        # Show metrics
        table = Table(title="Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in result.get("metrics", {}).items():
            table.add_row(key, str(value))
        
        console.print(table)
    
    asyncio.run(do_run())


@eval.command("report")
@click.option("--format", "-f", "fmt", type=click.Choice(["table", "json"]), default="table")
def eval_report(fmt: str):
    """Show evaluation results report."""
    from autosre.evals import get_results
    import json
    
    results = get_results()
    
    if fmt == "json":
        console.print(json.dumps(results, indent=2, default=str))
        return
    
    table = Table(title="Evaluation Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Time to Root Cause", style="yellow")
    table.add_column("Accuracy", style="blue")
    table.add_column("Run At", style="dim")
    
    for result in results:
        status = "[green]✓[/]" if result.get("success") else "[red]✗[/]"
        table.add_row(
            result.get("scenario", "unknown"),
            status,
            f"{result.get('time_to_root_cause', 'N/A')}s",
            f"{result.get('accuracy', 0) * 100:.0f}%",
            result.get("run_at", "N/A"),
        )
    
    console.print(table)


@cli.group()
def sandbox():
    """Manage sandbox environments."""
    pass


@sandbox.command("create")
@click.option("--name", "-n", default="autosre-sandbox", help="Sandbox name")
def sandbox_create(name: str):
    """Create a sandbox Kubernetes cluster."""
    console.print(f"[cyan]Creating sandbox: {name}[/]")
    console.print("[yellow]This feature is coming soon![/]")


@sandbox.command("destroy")
@click.option("--name", "-n", default="autosre-sandbox", help="Sandbox name")
def sandbox_destroy(name: str):
    """Destroy a sandbox cluster."""
    console.print(f"[cyan]Destroying sandbox: {name}[/]")
    console.print("[yellow]This feature is coming soon![/]")


@sandbox.command("inject")
@click.argument("chaos_type")
@click.option("--target", "-t", help="Target service")
def sandbox_inject(chaos_type: str, target: str):
    """Inject chaos into sandbox."""
    console.print(f"[cyan]Injecting {chaos_type} into {target or 'sandbox'}[/]")
    console.print("[yellow]This feature is coming soon![/]")


@cli.group()
def agent():
    """Run the AI SRE agent."""
    pass


@agent.command("analyze")
@click.option("--alert", "-a", type=click.Path(exists=True), help="Alert JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def agent_analyze(alert: str, verbose: bool):
    """Analyze an alert and suggest remediation."""
    import json
    import asyncio
    
    with open(alert) as f:
        alert_data = json.load(f)
    
    console.print(f"[cyan]Analyzing alert: {alert_data.get('name', 'unknown')}[/]\n")
    
    # TODO: Implement agent analysis
    console.print("[yellow]Agent analysis coming soon![/]")
    console.print("\nIn the meantime, here's what we'd check:")
    console.print("  1. Recent changes to affected service")
    console.print("  2. Related alerts and incidents")
    console.print("  3. Service dependencies")
    console.print("  4. Matching runbooks")


@agent.command("watch")
@click.option("--interval", "-i", default=30, help="Check interval in seconds")
def agent_watch(interval: int):
    """Watch for alerts and analyze automatically."""
    console.print(f"[cyan]Starting agent in watch mode (interval: {interval}s)[/]")
    console.print("[yellow]Watch mode coming soon![/]")
    console.print("Press Ctrl+C to stop")


@agent.command("history")
@click.option("--limit", "-l", default=20, help="Number of entries to show")
def agent_history(limit: int):
    """Show agent analysis history."""
    console.print("[yellow]Agent history coming soon![/]")


@cli.group()
def feedback():
    """Manage feedback and learning."""
    pass


@feedback.command("submit")
@click.option("--incident", "-i", required=True, help="Incident ID")
@click.option("--correct", "-c", is_flag=True, help="Agent was correct")
@click.option("--notes", "-n", help="Additional notes")
def feedback_submit(incident: str, correct: bool, notes: str):
    """Submit feedback on agent analysis."""
    console.print(f"[cyan]Recording feedback for incident: {incident}[/]")
    console.print(f"  Correct: {'Yes' if correct else 'No'}")
    if notes:
        console.print(f"  Notes: {notes}")
    console.print("[yellow]Feedback system coming soon![/]")


@feedback.command("report")
def feedback_report():
    """Show feedback summary."""
    console.print("[yellow]Feedback reporting coming soon![/]")


if __name__ == "__main__":
    cli()
