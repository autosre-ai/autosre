"""Context management commands for AutoSRE."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def context():
    """Manage context store data.
    
    Commands for managing services, ownership, changes, and runbooks
    in the context store.
    """
    pass


@context.command("show")
@click.option("--services", "-s", is_flag=True, help="Show services")
@click.option("--changes", "-c", is_flag=True, help="Show recent changes")
@click.option("--alerts", "-a", is_flag=True, help="Show active alerts")
def show(services: bool, changes: bool, alerts: bool):
    """Show context store contents.
    
    Without flags, shows a summary. With flags, shows specific data.
    """
    from pathlib import Path
    
    if not services and not changes and not alerts:
        # Show summary
        table = Table(title="Context Store Summary")
        table.add_column("Resource", style="cyan")
        table.add_column("Count")
        
        db_path = Path(".autosre/context.db")
        if db_path.exists():
            from autosre.foundation.context_store import ContextStore
            store = ContextStore(str(db_path))
            table.add_row("Services", str(len(store.list_services())))
            table.add_row("Recent Changes", str(len(store.get_recent_changes())))
            table.add_row("Active Alerts", str(len(store.get_firing_alerts())))
        else:
            table.add_row("Services", "0")
            table.add_row("Changes", "0")
            table.add_row("Alerts", "0")
        
        console.print(table)
        return
    
    if services:
        console.print("[cyan]Services:[/cyan]")
        # TODO: List services
    
    if changes:
        console.print("[cyan]Recent Changes:[/cyan]")
        # TODO: List changes
    
    if alerts:
        console.print("[cyan]Active Alerts:[/cyan]")
        # TODO: List alerts


@context.command("list")
@click.option("--type", "-t", "resource_type", 
              type=click.Choice(["services", "owners", "changes", "runbooks"]),
              default="services",
              help="Resource type to list")
def list_resources(resource_type: str):
    """List resources in the context store."""
    from autosre.foundation.context_store import ContextStore
    from pathlib import Path
    
    db_path = Path(".autosre/context.db")
    if not db_path.exists():
        console.print("[red]Context store not found. Run 'autosre init' first.[/red]")
        return
    
    store = ContextStore(str(db_path))
    
    if resource_type == "services":
        services = store.list_services()
        table = Table(title="Services")
        table.add_column("Name", style="cyan")
        table.add_column("Namespace")
        table.add_column("Status")
        table.add_column("Replicas")
        
        for svc in services:
            table.add_row(
                svc.name, 
                svc.namespace,
                svc.status.value,
                f"{svc.ready_replicas}/{svc.replicas}"
            )
        console.print(table)
    else:
        console.print(f"[yellow]Listing {resource_type} not yet implemented[/yellow]")


@context.command("sync")
@click.option("--all", "-a", "sync_all", is_flag=True, help="Sync from all sources")
@click.option("--kubernetes", "-k", is_flag=True, help="Sync from Kubernetes")
@click.option("--prometheus", "-p", is_flag=True, help="Sync from Prometheus")
def sync(sync_all: bool, kubernetes: bool, prometheus: bool):
    """Sync context from external sources."""
    if sync_all:
        kubernetes = prometheus = True
    
    if kubernetes:
        console.print("[yellow]Kubernetes sync not yet implemented[/yellow]")
    
    if prometheus:
        console.print("[yellow]Prometheus sync not yet implemented[/yellow]")
    
    if not (kubernetes or prometheus):
        console.print("[dim]Use --all, --kubernetes, or --prometheus to sync[/dim]")
