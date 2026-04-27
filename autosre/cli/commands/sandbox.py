"""AutoSRE sandbox commands - Manage local test environments."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box

console = Console()


@click.group()
def sandbox():
    """Manage sandbox Kubernetes environments.
    
    The sandbox provides a local Kind cluster pre-configured with:
    
    \b
    - Prometheus for metrics
    - Grafana for dashboards
    - Sample applications
    - Chaos injection capabilities
    
    Perfect for testing AutoSRE without touching production.
    
    \b
    Examples:
      $ autosre sandbox start            # Create and start cluster
      $ autosre sandbox status           # Check cluster status
      $ autosre sandbox inject cpu-hog   # Inject chaos
      $ autosre sandbox stop             # Destroy cluster
    """
    pass


@sandbox.command("start")
@click.option("--name", "-n", default="autosre-sandbox", help="Cluster name")
@click.option("--nodes", default=1, help="Number of worker nodes (1-3)")
@click.option("--k8s-version", default="v1.29.0", help="Kubernetes version")
@click.option("--skip-observability", is_flag=True, help="Skip Prometheus/Grafana setup")
@click.option("--skip-sample-apps", is_flag=True, help="Skip sample application deployment")
@click.pass_context
def sandbox_start(ctx, name: str, nodes: int, k8s_version: str, skip_observability: bool, skip_sample_apps: bool):
    """Create and start a sandbox Kubernetes cluster.
    
    Creates a Kind cluster with observability stack and sample apps.
    Requires: Docker, kind CLI
    
    \b
    Examples:
      $ autosre sandbox start
      $ autosre sandbox start --nodes 2
      $ autosre sandbox start --name my-test --skip-observability
    """
    from autosre.sandbox import SandboxCluster, ObservabilityStack
    
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🚀 Creating Sandbox: {name}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Check prerequisites
    if not _check_prerequisites():
        return
    
    cluster = SandboxCluster(name=name)
    
    # Check if already exists
    if cluster.exists():
        console.print(f"[yellow]Cluster '{name}' already exists.[/yellow]")
        if not click.confirm("Recreate it?"):
            console.print("[dim]Use 'autosre sandbox status' to check current state[/dim]")
            return
        
        console.print()
        console.print("[dim]Destroying existing cluster...[/dim]")
        cluster.destroy()
    
    # Create cluster
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Create Kind cluster
        task = progress.add_task("Creating Kind cluster...", total=None)
        success = cluster.create(nodes=nodes, kubernetes_version=k8s_version)
        
        if not success:
            progress.update(task, description="[red]✗ Failed to create cluster[/red]")
            console.print("\n[red]Failed to create cluster. Check Docker is running.[/red]")
            return
        
        progress.update(task, description="[green]✓ Kind cluster created[/green]")
        progress.remove_task(task)
        
        # Deploy observability
        if not skip_observability:
            task = progress.add_task("Deploying observability stack...", total=None)
            try:
                obs = ObservabilityStack()
                obs.deploy(cluster.kubeconfig)
                progress.update(task, description="[green]✓ Observability stack deployed[/green]")
            except Exception as e:
                progress.update(task, description=f"[yellow]⚠ Observability: {e}[/yellow]")
            progress.remove_task(task)
        
        # Deploy sample apps
        if not skip_sample_apps:
            task = progress.add_task("Deploying sample applications...", total=None)
            try:
                cluster.deploy_sample_app("podinfo")
                cluster.deploy_sample_app("bookstore")
                progress.update(task, description="[green]✓ Sample applications deployed[/green]")
            except Exception as e:
                progress.update(task, description=f"[yellow]⚠ Sample apps: {e}[/yellow]")
            progress.remove_task(task)
    
    console.print()
    console.print(Panel.fit(
        "[bold green]✓ Sandbox ready![/bold green]\n\n"
        f"Kubeconfig: {cluster.kubeconfig}\n"
        "Prometheus: http://localhost:9090\n"
        "Grafana:    http://localhost:3000 (admin/admin)",
        border_style="green"
    ))
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  [cyan]export KUBECONFIG={cluster.kubeconfig}[/cyan]")
    console.print("  [cyan]autosre context sync --kubernetes[/cyan]")
    console.print("  [cyan]autosre sandbox inject cpu-hog[/cyan]")
    console.print()


@sandbox.command("stop")
@click.option("--name", "-n", default="autosre-sandbox", help="Cluster name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def sandbox_stop(name: str, force: bool):
    """Stop and destroy a sandbox cluster.
    
    Completely removes the Kind cluster and associated resources.
    
    \b
    Examples:
      $ autosre sandbox stop
      $ autosre sandbox stop --force
    """
    from autosre.sandbox import SandboxCluster
    
    cluster = SandboxCluster(name=name)
    
    if not cluster.exists():
        console.print(f"[yellow]Cluster '{name}' does not exist.[/yellow]")
        return
    
    if not force:
        if not click.confirm(f"Destroy cluster '{name}'?"):
            return
    
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Destroying cluster...", total=None)
        
        success = cluster.destroy()
        
        if success:
            progress.update(task, description="[green]✓ Cluster destroyed[/green]")
        else:
            progress.update(task, description="[red]✗ Failed to destroy cluster[/red]")
    
    console.print()
    
    if success:
        console.print(f"[green]✓[/] Cluster '{name}' destroyed")
    else:
        console.print(f"[red]Failed to destroy cluster '{name}'[/red]")


@sandbox.command("status")
@click.option("--name", "-n", default="autosre-sandbox", help="Cluster name")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sandbox_status(name: str, as_json: bool):
    """Show sandbox cluster status.
    
    Displays cluster health, node status, and deployed components.
    
    \b
    Examples:
      $ autosre sandbox status
      $ autosre sandbox status --json
    """
    from autosre.sandbox import SandboxCluster
    
    cluster = SandboxCluster(name=name)
    status = cluster.get_status()
    
    if as_json:
        console.print_json(data=status)
        return
    
    console.print()
    
    if status["status"] == "not_found":
        console.print(Panel.fit(
            f"[yellow]Cluster '{name}' not found[/yellow]\n\n"
            "Create one with: autosre sandbox start",
            border_style="yellow"
        ))
        return
    
    if status["status"] == "error":
        console.print(Panel.fit(
            f"[red]Error checking cluster status[/red]\n\n{status.get('error', 'Unknown error')}",
            border_style="red"
        ))
        return
    
    # Cluster info
    console.print(Panel.fit(
        f"[bold cyan]📊 Sandbox Status: {name}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Nodes table
    table = Table(title="Nodes", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Roles", style="blue")
    table.add_column("Status", justify="center")
    
    for node in status.get("nodes", []):
        ready = "[green]✓ Ready[/]" if node["ready"] else "[red]✗ Not Ready[/]"
        roles = ", ".join(node["roles"]) or "worker"
        table.add_row(node["name"], roles, ready)
    
    console.print(table)
    console.print()
    
    # Summary
    ready_nodes = status.get("ready_nodes", 0)
    total_nodes = len(status.get("nodes", []))
    
    if ready_nodes == total_nodes:
        console.print(f"[green]✓ All nodes ready ({ready_nodes}/{total_nodes})[/green]")
    else:
        console.print(f"[yellow]⚠ {ready_nodes}/{total_nodes} nodes ready[/yellow]")
    
    if status.get("kubeconfig"):
        console.print(f"\n[dim]KUBECONFIG: {status['kubeconfig']}[/dim]")
    
    console.print()


@sandbox.command("inject")
@click.argument("chaos_type", type=click.Choice([
    "cpu-hog", "memory-hog", "io-stress", "network-latency",
    "pod-kill", "pod-failure", "disk-fill"
]))
@click.option("--target", "-t", help="Target service/pod")
@click.option("--namespace", "-n", default="default", help="Target namespace")
@click.option("--duration", "-d", default="60s", help="Chaos duration")
@click.option("--dry-run", is_flag=True, help="Show what would be injected")
def sandbox_inject(chaos_type: str, target: str, namespace: str, duration: str, dry_run: bool):
    """Inject chaos into the sandbox for testing.
    
    Creates controlled failures to test AutoSRE's diagnostic
    capabilities.
    
    \b
    Chaos types:
      cpu-hog         Consume CPU resources
      memory-hog      Consume memory
      io-stress       Stress disk I/O
      network-latency Add network latency
      pod-kill        Kill a pod
      pod-failure     Make pod fail health checks
      disk-fill       Fill up disk space
    
    \b
    Examples:
      $ autosre sandbox inject cpu-hog
      $ autosre sandbox inject pod-kill --target podinfo
      $ autosre sandbox inject network-latency --duration 120s
    """
    from autosre.sandbox import ChaosInjector
    
    console.print()
    
    if dry_run:
        console.print(Panel.fit(
            f"[bold yellow]🔬 DRY RUN: Would inject {chaos_type}[/bold yellow]\n\n"
            f"Target: {target or 'random'}\n"
            f"Namespace: {namespace}\n"
            f"Duration: {duration}",
            border_style="yellow"
        ))
        return
    
    console.print(Panel.fit(
        f"[bold cyan]💥 Injecting Chaos: {chaos_type}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Injecting {chaos_type}...", total=None)
        
        try:
            injector = ChaosInjector()
            result = injector.inject(
                chaos_type=chaos_type,
                target=target,
                namespace=namespace,
                duration=duration,
            )
            
            if result["success"]:
                progress.update(task, description=f"[green]✓ {chaos_type} injected[/green]")
            else:
                progress.update(task, description=f"[red]✗ Failed: {result.get('error')}[/red]")
            
        except Exception as e:
            progress.update(task, description=f"[red]✗ Error: {e}[/red]")
            result = {"success": False, "error": str(e)}
    
    console.print()
    
    if result.get("success"):
        console.print(f"[green]✓[/] Chaos injected: {chaos_type}")
        console.print(f"[dim]Duration: {duration}[/dim]")
        
        if result.get("target"):
            console.print(f"[dim]Target: {result['target']}[/dim]")
        
        console.print()
        console.print("[bold]Now try:[/bold]")
        console.print("  [cyan]autosre context sync --kubernetes[/cyan]")
        console.print("  [cyan]autosre agent analyze[/cyan]")
    else:
        console.print(f"[red]Failed to inject chaos: {result.get('error', 'Unknown error')}[/red]")
    
    console.print()


@sandbox.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sandbox_list(as_json: bool):
    """List all sandbox clusters.
    
    Shows all Kind clusters created by AutoSRE.
    
    \b
    Example:
      $ autosre sandbox list
    """
    import subprocess
    import json
    
    result = subprocess.run(
        ["kind", "get", "clusters"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        console.print("[red]Failed to list clusters. Is kind installed?[/red]")
        return
    
    clusters = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    
    if as_json:
        console.print_json(data={"clusters": clusters})
        return
    
    console.print()
    
    if not clusters:
        console.print(Panel.fit(
            "[yellow]No clusters found[/yellow]\n\n"
            "Create one with: autosre sandbox start",
            border_style="yellow"
        ))
        return
    
    table = Table(title="🎪 Kind Clusters", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("AutoSRE", justify="center")
    
    for cluster in clusters:
        is_autosre = cluster.startswith("autosre") 
        icon = "[green]✓[/]" if is_autosre else "[dim]—[/]"
        table.add_row(cluster, icon)
    
    console.print(table)
    console.print()


def _check_prerequisites() -> bool:
    """Check if Docker and kind are available."""
    import subprocess
    
    # Check Docker
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        console.print(Panel.fit(
            "[red]Docker is not running[/red]\n\n"
            "Please start Docker and try again.",
            border_style="red"
        ))
        return False
    
    # Check kind
    result = subprocess.run(["kind", "version"], capture_output=True)
    if result.returncode != 0:
        console.print(Panel.fit(
            "[red]kind is not installed[/red]\n\n"
            "Install it with: brew install kind\n"
            "Or: go install sigs.k8s.io/kind@latest",
            border_style="red"
        ))
        return False
    
    return True
