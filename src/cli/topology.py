"""Topology commands for AutoSRE CLI."""

import click
from rich.tree import Tree

from .client import AutoSREClient
from .utils import (
    console,
    create_table,
    get_formatter,
    spinner,
)


@click.group()
@click.pass_context
def topology(ctx: click.Context):
    """View and analyze service topology.
    
    Explore service dependencies, understand blast radius,
    and visualize your infrastructure.
    """
    pass


@topology.command("show")
@click.option("--service", "-s", help="Focus on a specific service")
@click.option("--depth", "-d", default=3, help="Depth of dependencies to show")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["tree", "list", "graph"]),
              default="tree",
              help="Output format")
@click.pass_context
def show_topology(
    ctx: click.Context,
    service: str | None,
    depth: int,
    output_format: str,
):
    """Show service topology.
    
    Examples:
        autosre topology show
        autosre topology show --service checkout-service
        autosre topology show --format list --depth 2
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner("Fetching topology...", formatter.json_mode):
                topology_data = client.get_topology(service=service)
        
        if formatter.json_mode:
            formatter.print_json(topology_data)
            return
        
        services = topology_data.get("services", [])
        edges = topology_data.get("edges", [])
        
        if not services:
            formatter.print_info("No services found in topology")
            return
        
        if output_format == "tree":
            _print_topology_tree(services, edges, service, depth)
        elif output_format == "list":
            _print_topology_list(services, edges)
        elif output_format == "graph":
            _print_topology_graph(services, edges)
    
    except Exception as e:
        formatter.print_error(f"Failed to fetch topology: {e}")
        ctx.exit(1)


def _print_topology_tree(
    services: list[dict],
    edges: list[dict],
    root_service: str | None,
    max_depth: int,
) -> None:
    """Print topology as a tree structure."""
    # Build adjacency list
    deps = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source:
            if source not in deps:
                deps[source] = []
            deps[source].append(target)
    
    # Service info lookup
    service_info = {s.get("name"): s for s in services}
    
    def add_children(tree_node: Tree, service_name: str, depth: int, visited: set):
        if depth >= max_depth or service_name in visited:
            return
        visited.add(service_name)
        
        for dep in deps.get(service_name, []):
            info = service_info.get(dep, {})
            label = _format_service_label(dep, info)
            child = tree_node.add(label)
            add_children(child, dep, depth + 1, visited.copy())
    
    # Find root services (services with no incoming edges)
    targets = {e.get("target") for e in edges}
    sources = {e.get("source") for e in edges}
    roots = sources - targets
    
    if root_service:
        roots = {root_service} if root_service in service_info else set()
    
    if not roots:
        # No clear root, use all services
        roots = {s.get("name") for s in services}
    
    console.print("[bold cyan]Service Topology[/bold cyan]\n")
    
    for root in sorted(roots):
        info = service_info.get(root, {})
        label = _format_service_label(root, info)
        tree = Tree(f"[bold]{label}[/bold]")
        add_children(tree, root, 0, set())
        console.print(tree)
        console.print()


def _format_service_label(name: str, info: dict) -> str:
    """Format a service label with type and status."""
    service_type = info.get("type", "")
    status = info.get("status", "")
    
    label = f"[cyan]{name}[/cyan]"
    
    parts = []
    if service_type:
        parts.append(f"[dim]{service_type}[/dim]")
    if status:
        color = "green" if status == "healthy" else "red" if status == "unhealthy" else "yellow"
        parts.append(f"[{color}]{status}[/]")
    
    if parts:
        label += f" ({', '.join(parts)})"
    
    return label


def _print_topology_list(services: list[dict], edges: list[dict]) -> None:
    """Print topology as a table."""
    table = create_table(
        "Services",
        [
            ("Name", "cyan"),
            ("Type", "dim"),
            ("Dependencies", "white"),
            ("Dependents", "white"),
            ("Status", "white"),
        ],
    )
    
    # Count dependencies
    outgoing = {}
    incoming = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        outgoing[source] = outgoing.get(source, 0) + 1
        incoming[target] = incoming.get(target, 0) + 1
    
    for service in services:
        name = service.get("name", "unknown")
        status = service.get("status", "unknown")
        
        status_color = "green" if status == "healthy" else "red" if status == "unhealthy" else "yellow"
        status_display = f"[{status_color}]{status}[/]"
        
        table.add_row(
            name,
            service.get("type", "unknown"),
            str(outgoing.get(name, 0)),
            str(incoming.get(name, 0)),
            status_display,
        )
    
    console.print(table)


def _print_topology_graph(services: list[dict], edges: list[dict]) -> None:
    """Print topology edges as ASCII graph representation."""
    console.print("[bold cyan]Service Dependencies[/bold cyan]\n")
    
    for edge in edges:
        source = edge.get("source", "?")
        target = edge.get("target", "?")
        edge_type = edge.get("type", "depends_on")
        
        arrow = "──▶" if edge_type == "depends_on" else "──○"
        console.print(f"  [cyan]{source}[/cyan] {arrow} [green]{target}[/green]")


@topology.command("blast-radius")
@click.argument("service")
@click.option("--depth", "-d", default=3, help="Depth of impact analysis")
@click.option("--direction", "-D",
              type=click.Choice(["downstream", "upstream", "both"]),
              default="both",
              help="Direction of impact analysis")
@click.pass_context
def blast_radius(
    ctx: click.Context,
    service: str,
    depth: int,
    direction: str,
):
    """Analyze the blast radius of a service failure.
    
    Shows which services would be affected if the given service fails.
    
    Examples:
        autosre topology blast-radius checkout-service
        autosre topology blast-radius database --direction upstream
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner(f"Analyzing blast radius for {service}...", formatter.json_mode):
                result = client.get_blast_radius(service)
        
        if formatter.json_mode:
            formatter.print_json(result)
            return
        
        console.print(f"[bold cyan]Blast Radius: {service}[/bold cyan]\n")
        
        # Affected services
        affected = result.get("affected_services", [])
        if affected:
            console.print("[bold]Affected Services:[/bold]")
            
            # Group by impact level
            by_level = {}
            for svc in affected:
                level = svc.get("impact_level", "unknown")
                if level not in by_level:
                    by_level[level] = []
                by_level[level].append(svc)
            
            level_order = ["critical", "high", "medium", "low"]
            level_colors = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "green",
            }
            
            for level in level_order:
                if level in by_level:
                    color = level_colors.get(level, "white")
                    console.print(f"\n  [{color}]{level.upper()}[/] ({len(by_level[level])} services):")
                    for svc in by_level[level]:
                        name = svc.get("name", "unknown")
                        reason = svc.get("reason", "")
                        if reason:
                            console.print(f"    • {name} [dim]({reason})[/dim]")
                        else:
                            console.print(f"    • {name}")
        else:
            formatter.print_info(f"No services directly affected by {service}")
        
        # Summary
        summary = result.get("summary", {})
        if summary:
            console.print("\n[bold]Impact Summary:[/bold]")
            console.print(f"  Total affected: {summary.get('total_affected', 0)}")
            console.print(f"  Max depth: {summary.get('max_depth', 0)}")
            
            risk = summary.get("risk_score", 0)
            risk_color = "red" if risk > 0.7 else "yellow" if risk > 0.4 else "green"
            console.print(f"  Risk score: [{risk_color}]{risk:.1%}[/]")
    
    except Exception as e:
        formatter.print_error(f"Failed to analyze blast radius: {e}")
        ctx.exit(1)


@topology.command("dependencies")
@click.argument("service")
@click.option("--direct-only", "-d", is_flag=True, help="Show only direct dependencies")
@click.pass_context
def service_dependencies(
    ctx: click.Context,
    service: str,
    direct_only: bool,
):
    """List dependencies for a service.
    
    Example:
        autosre topology dependencies checkout-service
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner(f"Fetching dependencies for {service}...", formatter.json_mode):
                topology_data = client.get_topology(service=service)
        
        if formatter.json_mode:
            formatter.print_json(topology_data)
            return
        
        edges = topology_data.get("edges", [])
        
        # Find dependencies (outgoing edges from this service)
        deps = [e.get("target") for e in edges if e.get("source") == service]
        
        # Find dependents (incoming edges to this service)  
        dependents = [e.get("source") for e in edges if e.get("target") == service]
        
        console.print(f"[bold cyan]Dependencies for {service}[/bold cyan]\n")
        
        if deps:
            console.print("[bold]Depends on:[/bold]")
            for dep in sorted(deps):
                console.print(f"  → [green]{dep}[/green]")
        else:
            console.print("[dim]No dependencies[/dim]")
        
        console.print()
        
        if dependents:
            console.print("[bold]Required by:[/bold]")
            for dep in sorted(dependents):
                console.print(f"  ← [yellow]{dep}[/yellow]")
        else:
            console.print("[dim]No dependents[/dim]")
    
    except Exception as e:
        formatter.print_error(f"Failed to fetch dependencies: {e}")
        ctx.exit(1)
