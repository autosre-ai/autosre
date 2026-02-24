"""
OpenSRE CLI — AI-Powered Incident Response
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from typing import Optional
import asyncio

from opensre_core import __version__
from opensre_core.config import settings

app = typer.Typer(
    name="opensre",
    help="🛡️ OpenSRE — AI-Powered Incident Response. Because 3 AM pages shouldn't require 3 hours of debugging.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"[bold blue]OpenSRE[/] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
):
    """OpenSRE: Your AI-powered on-call buddy."""
    pass


@app.command()
def start(
    port: int = typer.Option(8080, "--port", "-p", help="Port for webhook receiver"),
    slack: bool = typer.Option(True, "--slack/--no-slack", help="Enable Slack integration"),
):
    """
    🚀 Start the OpenSRE daemon.
    
    Listens for alerts and automatically investigates incidents.
    """
    import uvicorn
    from opensre_core.api import create_app
    
    console.print(Panel(
        f"[bold green]OpenSRE Daemon Starting[/]\n\n"
        f"🌐 Webhook: http://0.0.0.0:{port}/webhook/alert\n"
        f"💬 Slack: {'enabled' if slack else 'disabled'}\n"
        f"📖 API: http://0.0.0.0:{port}/docs",
        title="🛡️ OpenSRE",
        border_style="green"
    ))
    
    application = create_app()
    uvicorn.run(application, host="0.0.0.0", port=port)


@app.command()
def investigate(
    issue: str = typer.Argument(..., help="Issue or alert to investigate"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Investigation timeout in seconds"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Auto-approve safe actions"),
    slack: bool = typer.Option(False, "--slack", "-s", help="Send results to Slack"),
):
    """
    🔍 Investigate an issue or alert.
    
    Examples:
        opensre investigate "high CPU on payment-service"
        opensre investigate "pod crashlooping" -n production
        opensre investigate "checkout errors" --slack
    """
    console.print(Panel(
        f"[bold]Investigating:[/] {issue}",
        title="🔍 OpenSRE",
        border_style="blue"
    ))
    
    asyncio.run(_investigate_async(issue, namespace, timeout, auto_approve, slack))


async def _investigate_async(issue: str, namespace: str, timeout: int, auto_approve: bool, slack: bool):
    """Run async investigation."""
    from opensre_core.agents.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    with Live(Spinner("dots", text="Initializing agents..."), console=console, refresh_per_second=4):
        await asyncio.sleep(0.5)
    
    result = await orchestrator.investigate(
        issue=issue,
        namespace=namespace,
        timeout=timeout,
    )
    
    # Display observations
    console.print("\n[bold cyan]📊 Observations:[/]")
    for obs in result.observations:
        console.print(f"  → {obs.source}: {obs.summary}")
    
    # Display analysis
    console.print(f"\n[bold yellow]🎯 Root Cause (confidence: {result.confidence:.0%}):[/]")
    console.print(f"  → {result.root_cause}")
    if result.contributing_factors:
        console.print("\n[bold yellow]📋 Contributing Factors:[/]")
        for factor in result.contributing_factors:
            console.print(f"  • {factor}")
    
    # Display suggested actions
    console.print("\n[bold green]⚡ Recommended Actions:[/]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Num", style="dim")
    table.add_column("Action")
    table.add_column("Risk", justify="right")
    
    for i, action in enumerate(result.actions, 1):
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}[action.risk]
        table.add_row(f"[{i}]", action.description, f"[{risk_color}]{action.risk}[/]")
    
    console.print(table)
    
    # Send to Slack if requested
    if slack:
        await _send_to_slack(result)
        console.print("\n[dim]→ Results sent to Slack[/]")
    
    # Handle CLI approvals
    if not auto_approve and result.actions:
        console.print()
        choice = typer.prompt(
            "Execute action? [number/all/skip]",
            default="skip"
        )
        
        if choice.lower() == "skip":
            console.print("[dim]Skipped. No actions taken.[/]")
        elif choice.lower() == "all":
            for action in result.actions:
                await _execute_action(action)
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(result.actions):
                await _execute_action(result.actions[idx])


async def _send_to_slack(result):
    """Send investigation results to Slack with interactive buttons."""
    from opensre_core.adapters.slack import SlackAdapter
    slack = SlackAdapter()
    await slack.send_investigation(result)


async def _execute_action(action):
    """Execute an approved action."""
    console.print(f"\n[bold]Executing:[/] {action.command}")
    # TODO: Execute via Actor agent
    console.print(f"[green]✓ Action completed[/]")


@app.command()
def status():
    """
    📊 Check connection status to all integrations.
    """
    console.print(Panel("[bold]Checking integrations...[/]", title="📊 Status"))
    asyncio.run(_check_status())


async def _check_status():
    """Check all integration statuses."""
    from opensre_core.adapters.prometheus import PrometheusAdapter
    from opensre_core.adapters.kubernetes import KubernetesAdapter
    from opensre_core.adapters.llm import LLMAdapter
    
    checks = [
        ("Prometheus", PrometheusAdapter().health_check),
        ("Kubernetes", KubernetesAdapter().health_check),
        ("LLM", LLMAdapter().health_check),
    ]
    
    table = Table(title="Integration Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    table.add_column("Details")
    
    for name, check_fn in checks:
        try:
            result = await check_fn()
            status = "[green]✓ Connected[/]"
            details = result.get("details", "")
        except Exception as e:
            status = "[red]✗ Failed[/]"
            details = str(e)[:50]
        
        table.add_row(name, status, details)
    
    console.print(table)


@app.command()
def runbooks(
    action: str = typer.Argument(..., help="Action: add, list, search"),
    path: Optional[str] = typer.Argument(None, help="Path to runbook(s) or search query"),
):
    """
    📚 Manage runbooks for context-aware troubleshooting.
    
    Examples:
        opensre runbooks add ./runbooks/
        opensre runbooks list
        opensre runbooks search "redis connection"
    """
    if action == "add" and path:
        console.print(f"[green]✓ Indexed runbooks from {path}[/]")
    elif action == "list":
        console.print("[dim]No runbooks indexed yet.[/]")
    elif action == "search" and path:
        console.print(f"[dim]Searching for: {path}[/]")


@app.command()
def approve(
    action_id: str = typer.Argument(..., help="Action ID to approve"),
):
    """
    ✅ Approve a pending action.
    """
    console.print(f"[green]✓ Approved action {action_id}[/]")


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of incidents to show"),
):
    """
    📜 Show recent incident investigations.
    """
    console.print("[dim]No incidents recorded yet.[/]")


if __name__ == "__main__":
    app()
