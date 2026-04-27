"""AutoSRE context commands - Manage context sources."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from pathlib import Path
import json

console = Console()


@click.group()
def context():
    """Manage context store (services, ownership, changes).
    
    The context store is the foundation of AutoSRE's intelligence.
    It maintains current state of your infrastructure including:
    
    \b
    - Services and their dependencies
    - Ownership information (teams, on-call)
    - Recent changes (deployments, config updates)
    - Runbooks for incident response
    - Active alerts and incidents
    
    \b
    Examples:
      $ autosre context show                # Show summary
      $ autosre context show --services     # List all services
      $ autosre context sync --all          # Sync from all sources
      $ autosre context add service --name api --namespace prod
    """
    pass


@context.command("show")
@click.option("--services", "-s", is_flag=True, help="Show services")
@click.option("--changes", "-c", is_flag=True, help="Show recent changes")
@click.option("--alerts", "-a", is_flag=True, help="Show firing alerts")
@click.option("--runbooks", "-r", is_flag=True, help="Show runbooks")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def context_show(services: bool, changes: bool, alerts: bool, runbooks: bool, as_json: bool):
    """Display context store contents.
    
    Shows a summary of what's in the context store. Use flags to
    view specific categories in detail.
    
    \b
    Examples:
      $ autosre context show                    # Summary
      $ autosre context show --services         # All services
      $ autosre context show --services --json  # Services as JSON
      $ autosre context show -sc                # Services and changes
    """
    from autosre.foundation.context_store import ContextStore
    
    store = ContextStore()
    summary = store.get_context_summary()
    
    # If no specific flag, show summary
    if not any([services, changes, alerts, runbooks]):
        if as_json:
            console.print_json(data=summary)
            return
        
        console.print()
        console.print(Panel.fit(
            "[bold cyan]📚 Context Store Summary[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
        
        table = Table(box=box.ROUNDED)
        table.add_column("Category", style="bold")
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Status", justify="center")
        
        def status_icon(count: int, type_: str = "info") -> str:
            if type_ == "alert" and count > 0:
                return "[red]⚠[/]"
            elif count > 0:
                return "[green]✓[/]"
            return "[dim]○[/]"
        
        table.add_row("Services", str(summary["services"]), status_icon(summary["services"]))
        table.add_row("Ownership Mappings", str(summary["ownership_mappings"]), status_icon(summary["ownership_mappings"]))
        table.add_row("Changes (24h)", str(summary["changes_last_24h"]), status_icon(summary["changes_last_24h"]))
        table.add_row("Runbooks", str(summary["runbooks"]), status_icon(summary["runbooks"]))
        table.add_row("Firing Alerts", str(summary["firing_alerts"]), status_icon(summary["firing_alerts"], "alert"))
        table.add_row("Open Incidents", str(summary["open_incidents"]), status_icon(summary["open_incidents"], "alert"))
        
        console.print(table)
        console.print()
        
        if summary["services"] == 0:
            console.print("[dim]Tip: Run 'autosre context sync --kubernetes' to populate services[/dim]")
        
        return
    
    if services:
        _show_services(store, as_json)
    
    if changes:
        _show_changes(store, as_json)
    
    if alerts:
        _show_alerts(store, as_json)
    
    if runbooks:
        _show_runbooks(store, as_json)


def _show_services(store, as_json: bool):
    """Display services table."""
    svc_list = store.list_services()
    
    if as_json:
        console.print_json(data=[s.model_dump() for s in svc_list])
        return
    
    console.print()
    table = Table(title="🔧 Services", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Namespace", style="blue")
    table.add_column("Status", justify="center")
    table.add_column("Replicas", justify="center")
    table.add_column("Dependencies", style="dim")
    
    for svc in svc_list:
        status_style = {
            "healthy": "[green]● healthy[/]",
            "degraded": "[yellow]◐ degraded[/]",
            "down": "[red]○ down[/]",
            "unknown": "[dim]? unknown[/]",
        }.get(svc.status.value, "[dim]? unknown[/]")
        
        replicas = f"{svc.ready_replicas}/{svc.replicas}"
        if svc.ready_replicas < svc.replicas:
            replicas = f"[yellow]{replicas}[/]"
        else:
            replicas = f"[green]{replicas}[/]"
        
        deps = ", ".join(svc.dependencies[:3])
        if len(svc.dependencies) > 3:
            deps += f" (+{len(svc.dependencies) - 3})"
        
        table.add_row(
            svc.name,
            svc.namespace,
            status_style,
            replicas,
            deps or "-",
        )
    
    console.print(table)
    console.print()


def _show_changes(store, as_json: bool):
    """Display recent changes."""
    change_list = store.get_recent_changes(hours=24)
    
    if as_json:
        console.print_json(data=[c.model_dump() for c in change_list])
        return
    
    console.print()
    table = Table(title="📝 Recent Changes (24h)", box=box.ROUNDED)
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Service", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Description")
    table.add_column("Author", style="green")
    
    type_icons = {
        "deployment": "🚀",
        "config_change": "⚙️",
        "scale": "📊",
        "rollback": "⏪",
        "feature_flag": "🚩",
    }
    
    for change in change_list[:20]:
        icon = type_icons.get(change.change_type.value, "•")
        desc = change.description[:50] + "..." if len(change.description) > 50 else change.description
        
        table.add_row(
            change.timestamp.strftime("%Y-%m-%d %H:%M"),
            change.service_name,
            f"{icon} {change.change_type.value}",
            desc,
            change.author,
        )
    
    console.print(table)
    
    if len(change_list) > 20:
        console.print(f"[dim]Showing 20 of {len(change_list)} changes[/dim]")
    
    console.print()


def _show_alerts(store, as_json: bool):
    """Display firing alerts."""
    alert_list = store.get_firing_alerts()
    
    if as_json:
        console.print_json(data=[a.model_dump() for a in alert_list])
        return
    
    console.print()
    
    if not alert_list:
        console.print(Panel.fit(
            "[green]✓ No firing alerts[/green]",
            border_style="green"
        ))
        return
    
    table = Table(title="🚨 Firing Alerts", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Severity", justify="center")
    table.add_column("Service", style="cyan")
    table.add_column("Summary")
    table.add_column("Since", style="dim")
    
    severity_styles = {
        "critical": "[red bold]🔴 CRITICAL[/]",
        "high": "[red]🟠 HIGH[/]",
        "medium": "[yellow]🟡 MEDIUM[/]",
        "low": "[blue]🔵 LOW[/]",
        "info": "[dim]ℹ INFO[/]",
    }
    
    for alert in alert_list:
        sev = severity_styles.get(alert.severity.value, f"[dim]{alert.severity.value}[/]")
        summary = alert.summary[:60] + "..." if len(alert.summary) > 60 else alert.summary
        since = alert.fired_at.strftime("%H:%M")
        
        table.add_row(
            alert.name,
            sev,
            alert.service_name or "—",
            summary,
            since,
        )
    
    console.print(table)
    console.print()


def _show_runbooks(store, as_json: bool):
    """Display runbooks."""
    rb_list = store.find_runbook()
    
    if as_json:
        console.print_json(data=[r.model_dump() for r in rb_list])
        return
    
    console.print()
    table = Table(title="📖 Runbooks", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Alerts", style="blue")
    table.add_column("Auto", justify="center")
    table.add_column("Success Rate", justify="right")
    
    for rb in rb_list:
        alerts = ", ".join(rb.alert_names[:2])
        if len(rb.alert_names) > 2:
            alerts += f" (+{len(rb.alert_names) - 2})"
        
        auto = "[green]✓[/]" if rb.automated else "[dim]—[/]"
        rate = f"{rb.success_rate * 100:.0f}%" if rb.success_rate else "—"
        
        table.add_row(
            rb.id,
            rb.title,
            alerts or "—",
            auto,
            rate,
        )
    
    console.print(table)
    console.print()


@context.command("sync")
@click.option("--kubernetes", "-k", is_flag=True, help="Sync from Kubernetes")
@click.option("--prometheus", "-p", is_flag=True, help="Sync from Prometheus")
@click.option("--github", "-g", is_flag=True, help="Sync from GitHub")
@click.option("--all", "-a", "sync_all", is_flag=True, help="Sync from all sources")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without syncing")
def context_sync(kubernetes: bool, prometheus: bool, github: bool, sync_all: bool, dry_run: bool):
    """Sync context from external sources.
    
    Populates the context store with data from your infrastructure.
    Run this periodically or set up automated sync via cron.
    
    \b
    Examples:
      $ autosre context sync --all          # Sync from all sources
      $ autosre context sync --kubernetes   # Just Kubernetes
      $ autosre context sync --dry-run      # Preview without syncing
    """
    import asyncio
    from autosre.foundation.context_store import ContextStore
    
    if not any([kubernetes, prometheus, github, sync_all]):
        console.print("[yellow]No sources specified. Use --all or select specific sources.[/yellow]")
        console.print("Run 'autosre context sync --help' for options.")
        return
    
    store = ContextStore()
    
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🔄 Syncing Context[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        console.print()
    
    async def do_sync():
        total = 0
        sources = []
        
        if kubernetes or sync_all:
            sources.append(("Kubernetes", _sync_kubernetes))
        
        if prometheus or sync_all:
            sources.append(("Prometheus", _sync_prometheus))
        
        if github or sync_all:
            sources.append(("GitHub", _sync_github))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Syncing...", total=len(sources))
            
            for name, sync_fn in sources:
                progress.update(task, description=f"Syncing from {name}...")
                
                try:
                    if dry_run:
                        count = 0
                        console.print(f"  [dim]Would sync from {name}[/dim]")
                    else:
                        count = await sync_fn(store)
                        total += count
                        console.print(f"  [green]✓[/] Synced {count} items from {name}")
                except Exception as e:
                    console.print(f"  [red]✗[/] Failed to sync from {name}: {e}")
                
                progress.advance(task)
        
        return total
    
    total = asyncio.run(do_sync())
    
    console.print()
    if dry_run:
        console.print("[yellow]Dry run complete. No changes made.[/yellow]")
    else:
        console.print(f"[bold green]✓ Sync complete! {total} items synced.[/bold green]")
    console.print()


async def _sync_kubernetes(store):
    """Sync from Kubernetes."""
    from autosre.foundation.connectors import KubernetesConnector
    
    connector = KubernetesConnector()
    if await connector.connect():
        count = await connector.safe_sync(store)
        await connector.disconnect()
        return count
    else:
        raise Exception(connector._last_error or "Failed to connect")


async def _sync_prometheus(store):
    """Sync from Prometheus."""
    from autosre.foundation.connectors import PrometheusConnector
    from autosre.config import settings
    
    connector = PrometheusConnector({"prometheus_url": settings.prometheus_url})
    if await connector.connect():
        count = await connector.safe_sync(store)
        await connector.disconnect()
        return count
    else:
        raise Exception(connector._last_error or "Not available")


async def _sync_github(store):
    """Sync from GitHub."""
    import os
    from autosre.foundation.connectors import GitHubConnector
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise Exception("GITHUB_TOKEN not set")
    
    connector = GitHubConnector({"token": token})
    if await connector.connect():
        count = await connector.safe_sync(store)
        await connector.disconnect()
        return count
    else:
        raise Exception(connector._last_error or "Failed to connect")


@context.group()
def add():
    """Add items to the context store.
    
    Manually add services, ownership, runbooks, or changes.
    
    \b
    Examples:
      $ autosre context add service --name api --namespace prod
      $ autosre context add runbook --file ./my-runbook.yaml
    """
    pass


@add.command("service")
@click.option("--name", "-n", required=True, help="Service name")
@click.option("--namespace", default="default", help="Kubernetes namespace")
@click.option("--cluster", default="default", help="Cluster name")
@click.option("--team", "-t", help="Owning team")
@click.option("--dependencies", "-d", multiple=True, help="Dependencies (can repeat)")
def add_service(name: str, namespace: str, cluster: str, team: str, dependencies: tuple):
    """Add a service to the context store.
    
    \b
    Examples:
      $ autosre context add service --name api --namespace production
      $ autosre context add service --name frontend --team platform -d api -d redis
    """
    from autosre.foundation.context_store import ContextStore
    from autosre.foundation.models import Service, ServiceStatus, Ownership
    
    store = ContextStore()
    
    service = Service(
        name=name,
        namespace=namespace,
        cluster=cluster,
        dependencies=list(dependencies),
        status=ServiceStatus.UNKNOWN,
    )
    store.add_service(service)
    
    if team:
        ownership = Ownership(
            service_name=name,
            team=team,
        )
        store.set_ownership(ownership)
    
    console.print(f"[green]✓[/] Added service '{name}' to context store")


@add.command("runbook")
@click.option("--file", "-f", "filepath", required=True, type=click.Path(exists=True), help="Runbook YAML file")
def add_runbook(filepath: str):
    """Add a runbook from a YAML file.
    
    \b
    Example:
      $ autosre context add runbook --file ./runbooks/high-cpu.yaml
    """
    import yaml
    from autosre.foundation.context_store import ContextStore
    from autosre.foundation.models import Runbook
    
    with open(filepath) as f:
        data = yaml.safe_load(f)
    
    store = ContextStore()
    
    runbook = Runbook(
        id=data.get("id"),
        title=data.get("title"),
        alert_names=data.get("alerts", []),
        services=data.get("services", []),
        keywords=data.get("keywords", []),
        description=data.get("description", ""),
        steps=data.get("steps", []),
        automated=data.get("automated", False),
        requires_approval=data.get("requires_approval", True),
        author=data.get("author"),
    )
    
    store.add_runbook(runbook)
    console.print(f"[green]✓[/] Added runbook '{runbook.id}' to context store")


@context.command("list")
@click.argument("type_", type=click.Choice(["services", "changes", "alerts", "runbooks", "incidents"]))
@click.option("--limit", "-l", default=20, help="Maximum items to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def context_list(type_: str, limit: int, as_json: bool):
    """List items from the context store.
    
    \b
    Examples:
      $ autosre context list services
      $ autosre context list changes --limit 50
      $ autosre context list alerts --json
    """
    from autosre.foundation.context_store import ContextStore
    
    store = ContextStore()
    
    if type_ == "services":
        _show_services(store, as_json)
    elif type_ == "changes":
        _show_changes(store, as_json)
    elif type_ == "alerts":
        _show_alerts(store, as_json)
    elif type_ == "runbooks":
        _show_runbooks(store, as_json)
    elif type_ == "incidents":
        _show_incidents(store, as_json)


def _show_incidents(store, as_json: bool):
    """Display incidents."""
    incidents = store.get_open_incidents()
    
    if as_json:
        console.print_json(data=[i.model_dump() for i in incidents])
        return
    
    console.print()
    
    if not incidents:
        console.print(Panel.fit(
            "[green]✓ No open incidents[/green]",
            border_style="green"
        ))
        return
    
    table = Table(title="🔥 Open Incidents", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Severity", justify="center")
    table.add_column("Services", style="blue")
    table.add_column("Started", style="dim")
    
    for inc in incidents:
        sev_style = {
            "critical": "[red bold]CRITICAL[/]",
            "high": "[red]HIGH[/]",
            "medium": "[yellow]MEDIUM[/]",
            "low": "[blue]LOW[/]",
        }.get(inc.severity.value, inc.severity.value)
        
        services = ", ".join(inc.services[:2])
        if len(inc.services) > 2:
            services += f" (+{len(inc.services) - 2})"
        
        table.add_row(
            inc.id[:12],
            inc.title[:40] + "..." if len(inc.title) > 40 else inc.title,
            sev_style,
            services or "—",
            inc.started_at.strftime("%Y-%m-%d %H:%M"),
        )
    
    console.print(table)
    console.print()
