"""Main CLI entry point for AutoSRE."""

import click

from .config import config
from .investigate import investigate
from .memory import memory
from .topology import topology
from .utils import OutputFormatter, console


@click.group()
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.version_option(package_name="autosre")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, quiet: bool, debug: bool):
    """AutoSRE - AI-powered incident investigation and SRE automation.
    
    \b
    Examples:
        autosre investigate "checkout 500 errors" --service checkout-service
        autosre investigate --interactive
        autosre status inv_abc123
        autosre list
        autosre memory search "database timeout"
        autosre config show
        autosre topology show
    
    Configuration is stored in ~/.autosre/config.yaml
    """
    ctx.ensure_object(dict)
    ctx.obj = OutputFormatter(json_mode=json_mode)
    
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)


# Add subcommand groups
cli.add_command(investigate)
cli.add_command(memory)
cli.add_command(config)
cli.add_command(topology)


# Top-level shortcuts for common investigate commands
@cli.command("status")
@click.argument("investigation_id")
@click.pass_context
def status(ctx: click.Context, investigation_id: str):
    """Check investigation status (shortcut for 'investigate status').
    
    Example:
        autosre status inv_abc123
    """
    # Invoke the investigate status command
    ctx.invoke(investigate.commands["status"], investigation_id=investigation_id)


@cli.command("list")
@click.option("--limit", "-n", default=10, help="Number of investigations to show")
@click.option("--status", "-s", "filter_status", help="Filter by status")
@click.option("--service", help="Filter by service")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    limit: int,
    filter_status: str | None,
    service: str | None,
):
    """List recent investigations (shortcut for 'investigate list').
    
    Examples:
        autosre list
        autosre list --status running
        autosre list --service checkout-service
    """
    ctx.invoke(
        investigate.commands["list"],
        limit=limit,
        status=filter_status,
        service=service,
    )


@cli.command("version")
def version():
    """Show version information."""
    try:
        from importlib.metadata import version as get_version
        ver = get_version("autosre")
    except Exception:
        ver = "unknown"
    
    console.print(f"[bold cyan]AutoSRE[/bold cyan] version [green]{ver}[/green]")


@cli.command("doctor")
@click.pass_context
def doctor(ctx: click.Context):
    """Check AutoSRE health and configuration.
    
    Verifies that:
    - Configuration is valid
    - API server is reachable
    - Required services are available
    """
    from .client import AutoSREClient, APIConfig
    from .utils import get_formatter
    from pathlib import Path
    
    formatter = get_formatter(ctx)
    checks = []
    
    # Check config file
    config_path = Path.home() / ".autosre" / "config.yaml"
    if config_path.exists():
        checks.append(("Config file", True, str(config_path)))
    else:
        checks.append(("Config file", False, "Not found (using defaults)"))
    
    # Check API connectivity
    try:
        config = APIConfig.load()
        with AutoSREClient(config) as client:
            # Try to reach the API
            client.client.get("/api/v1/health", timeout=5)
            checks.append(("API server", True, config.base_url))
    except Exception as e:
        checks.append(("API server", False, str(e)[:50]))
    
    # Output results
    if formatter.json_mode:
        formatter.print_json({
            "checks": [
                {"name": name, "passed": passed, "details": details}
                for name, passed, details in checks
            ]
        })
        return
    
    console.print("[bold cyan]AutoSRE Health Check[/bold cyan]\n")
    
    all_passed = True
    for name, passed, details in checks:
        icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
        status = "[green]OK[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {icon} {name}: {status}")
        if details:
            console.print(f"      [dim]{details}[/dim]")
        if not passed:
            all_passed = False
    
    console.print()
    if all_passed:
        console.print("[green]All checks passed![/green]")
    else:
        console.print("[yellow]Some checks failed. Run 'autosre config init' to set up configuration.[/yellow]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
