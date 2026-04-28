"""AutoSRE agent commands - Run the AI SRE agent."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich import box

console = Console()


@click.group()
def agent():
    """Run and manage the AI SRE agent.
    
    The agent is the core of AutoSRE - it analyzes alerts, correlates
    context, and suggests remediation actions.
    
    \b
    Modes:
      run       Run continuous agent (watch mode)
      analyze   One-shot analysis of an alert
      config    View/edit agent configuration
      history   View past analyses
    
    \b
    Examples:
      $ autosre agent run                    # Start watching
      $ autosre agent analyze --alert a.json # Analyze single alert
      $ autosre agent config                 # View configuration
    """
    pass


@agent.command("run")
@click.option("--interval", "-i", default=30, help="Poll interval in seconds")
@click.option("--once", is_flag=True, help="Run once and exit")
@click.option("--dry-run", is_flag=True, help="Don't execute remediation")
@click.option("--model", "-m", help="Override LLM model")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def agent_run(interval: int, once: bool, dry_run: bool, model: str, verbose: bool):
    """Start the AI SRE agent in watch mode.
    
    Continuously monitors for alerts and automatically analyzes them.
    Requires approval (configurable) before executing remediation.
    
    \b
    Examples:
      $ autosre agent run
      $ autosre agent run --interval 60 --dry-run
      $ autosre agent run --once
    """
    import asyncio
    import signal
    import sys
    
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🤖 AutoSRE Agent[/bold cyan]\n\n"
        f"Mode: {'Single run' if once else 'Watch mode'}\n"
        f"Interval: {interval}s\n"
        f"Dry run: {'Yes' if dry_run else 'No'}",
        border_style="cyan"
    ))
    console.print()
    
    if dry_run:
        console.print("[yellow]⚠ Dry run mode - no remediation will be executed[/yellow]")
        console.print()
    
    # Signal handler for graceful shutdown
    stop_event = asyncio.Event()
    
    def handle_signal(sig, frame):
        console.print("\n[yellow]Shutting down...[/yellow]")
        stop_event.set()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    async def run_agent():
        from autosre.foundation.context_store import ContextStore
        from autosre.agent import AlertWatcher, Reasoner, Actor
        
        store = ContextStore()
        
        iteration = 0
        while not stop_event.is_set():
            iteration += 1
            
            console.print(f"[dim]─── Iteration {iteration} ───[/dim]")
            
            # Check for alerts
            alerts = store.get_firing_alerts()
            
            if alerts:
                console.print(f"[yellow]Found {len(alerts)} firing alert(s)[/yellow]")
                
                for alert in alerts[:3]:  # Process up to 3 alerts per iteration
                    await _analyze_alert(alert, store, dry_run, verbose)
            else:
                console.print("[green]No firing alerts[/green]")
            
            if once:
                break
            
            console.print(f"[dim]Next check in {interval}s...[/dim]")
            console.print()
            
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
        
        console.print("[green]Agent stopped[/green]")
    
    asyncio.run(run_agent())


@agent.command("analyze")
@click.option("--alert", "-a", "alert_file", type=click.Path(exists=True), help="Alert JSON file")
@click.option("--alert-name", help="Analyze alert by name from context store")
@click.option("--service", "-s", help="Analyze a specific service")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--model", "-m", help="Override LLM model")
def agent_analyze(alert_file: str, alert_name: str, service: str, verbose: bool, as_json: bool, model: str):
    """Analyze an alert and suggest remediation.
    
    Performs a one-shot analysis of the given alert, correlating it
    with context (changes, dependencies, runbooks) to identify root
    cause and suggest remediation.
    
    \b
    Examples:
      $ autosre agent analyze --alert alert.json
      $ autosre agent analyze --alert-name HighCPUUsage
      $ autosre agent analyze --service frontend
    """
    import asyncio
    import json
    
    console.print()
    
    # Load alert data
    if alert_file:
        try:
            with open(alert_file) as f:
                alert_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: Invalid JSON in alert file[/red]")
            console.print(f"[dim]{e}[/dim]")
            return
        except Exception as e:
            console.print(f"[red]Error reading alert file: {e}[/red]")
            return
    elif alert_name:
        from autosre.foundation.context_store import ContextStore
        store = ContextStore()
        alerts = [a for a in store.get_firing_alerts() if a.name == alert_name]
        if not alerts:
            console.print(f"[red]Alert '{alert_name}' not found in context store[/red]")
            return
        alert_data = alerts[0].model_dump()
    elif service:
        alert_data = {
            "name": f"ServiceAnalysis-{service}",
            "severity": "info",
            "summary": f"Manual analysis request for service: {service}",
            "service_name": service,
        }
    else:
        console.print("[red]Please provide --alert, --alert-name, or --service[/red]")
        return
    
    if not as_json:
        console.print(Panel.fit(
            f"[bold cyan]🔍 Analyzing: {alert_data.get('name', 'Unknown')}[/bold cyan]\n\n"
            f"[dim]{alert_data.get('summary', 'No summary')}[/dim]",
            border_style="cyan"
        ))
        console.print()
    
    async def do_analyze():
        from autosre.foundation.context_store import ContextStore
        
        store = ContextStore()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=as_json,
        ) as progress:
            task = progress.add_task("Gathering context...", total=None)
            
            # Gather context
            service_name = alert_data.get("service_name")
            context = {
                "alert": alert_data,
                "services": [],
                "changes": [],
                "runbooks": [],
                "related_alerts": [],
            }
            
            if service_name:
                svc = store.get_service(service_name)
                if svc:
                    context["services"].append(svc.model_dump())
                    
                    # Get dependencies
                    for dep_name in svc.dependencies:
                        dep = store.get_service(dep_name)
                        if dep:
                            context["services"].append(dep.model_dump())
                
                # Get recent changes
                changes = store.get_recent_changes(service_name=service_name, hours=24)
                context["changes"] = [c.model_dump() for c in changes]
                
                # Get runbooks
                runbooks = store.find_runbook(
                    alert_name=alert_data.get("name"),
                    service_name=service_name,
                )
                context["runbooks"] = [r.model_dump() for r in runbooks]
            
            progress.update(task, description="Analyzing...")
            
            # Use offline analysis (heuristics) when no LLM is configured
            import os
            has_llm = (
                os.environ.get("OPENAI_API_KEY") or
                os.environ.get("ANTHROPIC_API_KEY") or
                os.environ.get("OLLAMA_HOST")
            )
            
            if has_llm:
                # TODO: Actually call the LLM reasoner
                analysis_method = "LLM"
                root_cause = "Analysis requires LLM integration (coming soon)"
                confidence = 0.0
                reasoning = "LLM integration pending"
            else:
                # Use heuristic-based analysis
                analysis_method = "Offline (heuristic)"
                
                # Simple heuristics based on alert data
                alert_name_lower = alert_data.get("name", "").lower()
                alert_summary_lower = alert_data.get("summary", "").lower()
                full_text = f"{alert_name_lower} {alert_summary_lower}"
                
                # Identify issue type
                if "cpu" in full_text:
                    root_cause = "High CPU utilization - check for CPU-intensive operations"
                    suggested_actions = ["Check for CPU-heavy processes", "Review recent deployments", "Consider scaling up"]
                elif "memory" in full_text or "oom" in full_text:
                    root_cause = "Memory pressure or leak - application using excessive memory"
                    suggested_actions = ["Check memory usage trends", "Look for memory leaks", "Review heap dumps"]
                elif "disk" in full_text or "storage" in full_text:
                    root_cause = "Disk space or I/O issue"
                    suggested_actions = ["Check disk usage", "Clean up old logs/data", "Consider expanding volume"]
                elif "connection" in full_text or "timeout" in full_text:
                    root_cause = "Connection or timeout issue - check network and dependencies"
                    suggested_actions = ["Check network connectivity", "Review connection pool settings", "Check downstream services"]
                elif "error" in full_text or "5xx" in full_text or "exception" in full_text:
                    root_cause = "Application errors - review logs for exception details"
                    suggested_actions = ["Check application logs", "Review recent deployments", "Check error rates"]
                elif "latency" in full_text or "slow" in full_text:
                    root_cause = "Latency degradation - check performance bottlenecks"
                    suggested_actions = ["Review request traces", "Check database query times", "Profile application"]
                else:
                    root_cause = "Issue detected - review alert details and recent changes"
                    suggested_actions = ["Review alert details", "Check recent changes", "Examine service logs"]
                
                # Look at changes for more context
                if context["changes"]:
                    recent_change = context["changes"][0].get("description", "")
                    root_cause += f" (Recent change: {recent_change})"
                    confidence = 0.5
                else:
                    confidence = 0.3
                
                reasoning = f"Heuristic analysis based on alert name and summary"
            
            analysis = {
                "root_cause": root_cause,
                "confidence": confidence,
                "analysis_method": analysis_method,
                "affected_services": [service_name] if service_name else [],
                "related_changes": [c.get("description") for c in context["changes"][:3]],
                "recommended_runbooks": [r.get("id") for r in context["runbooks"][:2]],
                "suggested_actions": suggested_actions if 'suggested_actions' in dir() else [
                    "Check recent deployments",
                    "Review resource utilization",
                    "Examine application logs",
                ],
                "context_summary": {
                    "services_analyzed": len(context["services"]),
                    "changes_in_window": len(context["changes"]),
                    "matching_runbooks": len(context["runbooks"]),
                },
            }
            
            progress.update(task, description="Complete!")
        
        return analysis
    
    analysis = asyncio.run(do_analyze())
    
    if as_json:
        import json
        console.print_json(data=analysis)
        return
    
    console.print()
    
    # Root cause
    console.print("[bold]Root Cause Analysis:[/bold]")
    console.print(Panel(
        analysis["root_cause"],
        border_style="blue" if analysis["confidence"] > 0.7 else "yellow"
    ))
    
    confidence = analysis.get("confidence", 0)
    confidence_color = "green" if confidence > 0.7 else "yellow" if confidence > 0.4 else "red"
    console.print(f"Confidence: [{confidence_color}]{confidence * 100:.0f}%[/{confidence_color}]")
    console.print()
    
    # Related changes
    if analysis.get("related_changes"):
        console.print("[bold]Recent Changes:[/bold]")
        for change in analysis["related_changes"]:
            console.print(f"  • {change}")
        console.print()
    
    # Recommended runbooks
    if analysis.get("recommended_runbooks"):
        console.print("[bold]Recommended Runbooks:[/bold]")
        for rb in analysis["recommended_runbooks"]:
            console.print(f"  📖 {rb}")
        console.print()
    
    # Suggested actions
    if analysis.get("suggested_actions"):
        console.print("[bold]Suggested Actions:[/bold]")
        for i, action in enumerate(analysis["suggested_actions"], 1):
            console.print(f"  {i}. {action}")
        console.print()
    
    # Context summary
    ctx = analysis.get("context_summary", {})
    console.print(f"[dim]Context: {ctx.get('services_analyzed', 0)} services, "
                  f"{ctx.get('changes_in_window', 0)} changes, "
                  f"{ctx.get('matching_runbooks', 0)} runbooks[/dim]")
    console.print()


@agent.command("config")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--set", "set_value", nargs=2, multiple=True, help="Set a config value")
def agent_config(as_json: bool, set_value: tuple):
    """View or edit agent configuration.
    
    Shows current agent settings. Use --set to modify values.
    
    \b
    Examples:
      $ autosre agent config
      $ autosre agent config --set require_approval false
      $ autosre agent config --set confidence_threshold 0.8
    """
    from autosre.config import settings
    
    if set_value:
        console.print("[yellow]Configuration editing not yet implemented[/yellow]")
        console.print("Edit .env file directly for now.")
        return
    
    config_data = {
        "llm": {
            "provider": settings.llm_provider,
            "model": _get_active_model(settings),
        },
        "behavior": {
            "require_approval": settings.require_approval,
            "auto_approve_low_risk": settings.auto_approve_low_risk,
            "confidence_threshold": settings.confidence_threshold,
            "max_iterations": settings.max_iterations,
            "timeout_seconds": settings.timeout_seconds,
        },
        "integrations": {
            "prometheus_url": settings.prometheus_url,
            "slack_enabled": settings.slack_enabled,
            "mcp_enabled": settings.mcp_enabled,
        },
    }
    
    if as_json:
        console.print_json(data=config_data)
        return
    
    console.print()
    console.print(Panel.fit(
        "[bold cyan]⚙️ Agent Configuration[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # LLM section
    console.print("[bold]LLM Provider[/bold]")
    console.print(f"  Provider: [cyan]{config_data['llm']['provider']}[/cyan]")
    console.print(f"  Model: [cyan]{config_data['llm']['model']}[/cyan]")
    console.print()
    
    # Behavior section
    console.print("[bold]Agent Behavior[/bold]")
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Setting")
    table.add_column("Value", justify="right")
    
    behavior = config_data["behavior"]
    table.add_row("Require Approval", _bool_display(behavior["require_approval"]))
    table.add_row("Auto-approve Low Risk", _bool_display(behavior["auto_approve_low_risk"]))
    table.add_row("Confidence Threshold", f"{behavior['confidence_threshold'] * 100:.0f}%")
    table.add_row("Max Iterations", str(behavior["max_iterations"]))
    table.add_row("Timeout", f"{behavior['timeout_seconds']}s")
    
    console.print(table)
    console.print()
    
    # Integrations section
    console.print("[bold]Integrations[/bold]")
    integrations = config_data["integrations"]
    console.print(f"  Prometheus: [dim]{integrations['prometheus_url']}[/dim]")
    console.print(f"  Slack: {_bool_display(integrations['slack_enabled'])}")
    console.print(f"  MCP: {_bool_display(integrations['mcp_enabled'])}")
    console.print()


@agent.command("history")
@click.option("--limit", "-l", default=20, help="Number of entries")
@click.option("--service", "-s", help="Filter by service")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def agent_history(limit: int, service: str, as_json: bool):
    """Show agent analysis history.
    
    Displays past analyses and their outcomes.
    
    \b
    Examples:
      $ autosre agent history
      $ autosre agent history --service frontend
      $ autosre agent history --limit 50 --json
    """
    from autosre.foundation.context_store import ContextStore
    
    store = ContextStore()
    incidents = store.get_open_incidents()  # TODO: Get closed incidents too
    
    if as_json:
        console.print_json(data=[i.model_dump() for i in incidents])
        return
    
    console.print()
    
    if not incidents:
        console.print(Panel.fit(
            "[dim]No analysis history found[/dim]\n\n"
            "Run 'autosre agent analyze' to create entries",
            border_style="dim"
        ))
        return
    
    table = Table(title="📜 Agent History", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Services", style="blue")
    table.add_column("Confidence", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Time", style="dim")
    
    for inc in incidents[:limit]:
        services = ", ".join(inc.services[:2])
        if len(inc.services) > 2:
            services += f" (+{len(inc.services) - 2})"
        
        confidence = inc.agent_confidence
        if confidence:
            conf_str = f"{confidence * 100:.0f}%"
            conf_color = "green" if confidence > 0.7 else "yellow" if confidence > 0.4 else "red"
            conf_str = f"[{conf_color}]{conf_str}[/{conf_color}]"
        else:
            conf_str = "[dim]—[/dim]"
        
        status = "[green]✓ Resolved[/]" if inc.resolved_at else "[yellow]○ Open[/]"
        
        table.add_row(
            inc.id[:8],
            inc.title[:40] + "..." if len(inc.title) > 40 else inc.title,
            services or "—",
            conf_str,
            status,
            inc.started_at.strftime("%m/%d %H:%M"),
        )
    
    console.print(table)
    console.print()


async def _analyze_alert(alert, store, dry_run: bool, verbose: bool):
    """Analyze a single alert."""
    console.print()
    console.print(f"[bold]Analyzing:[/bold] {alert.name}")
    console.print(f"[dim]{alert.summary}[/dim]")
    
    # TODO: Implement actual analysis
    console.print("[yellow]Analysis implementation coming soon[/yellow]")
    console.print()


def _get_active_model(settings) -> str:
    """Get the currently active model name."""
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    elif settings.llm_provider == "openai":
        return settings.openai_model
    elif settings.llm_provider == "anthropic":
        return settings.anthropic_model
    elif settings.llm_provider == "azure":
        return settings.azure_openai_deployment
    return "unknown"


def _bool_display(value: bool) -> str:
    """Display a boolean as a colored icon."""
    return "[green]✓ enabled[/]" if value else "[dim]○ disabled[/]"
