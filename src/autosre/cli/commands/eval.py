"""AutoSRE eval commands - Run and manage evaluations."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box
from pathlib import Path

console = Console()


@click.group()
def eval():
    """Run evaluation scenarios and track results.
    
    The evaluation framework lets you test AutoSRE's diagnostic
    capabilities against synthetic incidents. Use it to:
    
    \b
    - Validate agent accuracy before production
    - Benchmark improvements over time
    - Create custom scenarios for your environment
    
    \b
    Examples:
      $ autosre eval list                      # See available scenarios
      $ autosre eval run -s deployment-failure # Run a scenario
      $ autosre eval report                    # View results history
      $ autosre eval create -f scenario.yaml   # Create custom scenario
    """
    pass


@eval.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show additional details")
def eval_list(as_json: bool, verbose: bool):
    """List available evaluation scenarios.
    
    Shows all built-in and custom scenarios available for testing.
    Custom scenarios are loaded from ~/.autosre/scenarios/
    
    \b
    Examples:
      $ autosre eval list
      $ autosre eval list --verbose
    """
    from autosre.evals import list_scenarios
    
    scenarios = list_scenarios()
    
    if as_json:
        console.print_json(data=scenarios)
        return
    
    console.print()
    
    if not scenarios:
        console.print(Panel.fit(
            "[yellow]No scenarios found[/yellow]\n\n"
            "Run 'autosre init' to create sample scenarios,\n"
            "or add your own to ~/.autosre/scenarios/",
            border_style="yellow"
        ))
        return
    
    table = Table(title="📋 Available Scenarios", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Difficulty", justify="center")
    if verbose:
        table.add_column("Custom", justify="center")
    
    difficulty_styles = {
        "easy": "[green]Easy[/]",
        "medium": "[yellow]Medium[/]",
        "hard": "[red]Hard[/]",
    }
    
    for scenario in scenarios:
        diff = difficulty_styles.get(scenario.get("difficulty", "medium"), scenario.get("difficulty"))
        custom = "[cyan]✓[/]" if scenario.get("custom") else "[dim]—[/]"
        
        row = [scenario["name"], scenario["description"], diff]
        if verbose:
            row.append(custom)
        
        table.add_row(*row)
    
    console.print(table)
    console.print()
    console.print(f"[dim]Run a scenario: autosre eval run --scenario <name>[/dim]")
    console.print()


@eval.command("run")
@click.option("--scenario", "-s", required=True, help="Scenario name to run")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--timeout", "-t", default=300, help="Timeout in seconds")
@click.option("--model", "-m", help="Override LLM model for this run")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def eval_run(scenario: str, verbose: bool, timeout: int, model: str, as_json: bool):
    """Run an evaluation scenario.
    
    Executes a scenario and measures the agent's ability to:
    - Identify the root cause
    - Recommend the correct service
    - Suggest appropriate runbooks
    - Propose remediation actions
    
    \b
    Examples:
      $ autosre eval run --scenario deployment-failure
      $ autosre eval run -s high-cpu --verbose
      $ autosre eval run -s memory-leak --model gpt-4
    """
    import asyncio
    from autosre.evals import run_scenario, load_scenario
    
    # Verify scenario exists
    scenario_data = load_scenario(scenario)
    if not scenario_data:
        console.print(f"[red]Error:[/red] Scenario '{scenario}' not found")
        console.print("Run 'autosre eval list' to see available scenarios")
        return
    
    if not as_json:
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]🧪 Running Scenario: {scenario}[/bold cyan]\n\n"
            f"[dim]{scenario_data.description}[/dim]",
            border_style="cyan"
        ))
        console.print()
    
    async def do_run():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            disable=as_json,
        ) as progress:
            task = progress.add_task("Running analysis...", total=None)
            
            result = await run_scenario(scenario, verbose=verbose)
            
            progress.update(task, description="Complete!")
            progress.remove_task(task)
        
        return result
    
    result = asyncio.run(do_run())
    
    if as_json:
        console.print_json(data=result)
        return
    
    console.print()
    
    # Show result
    if result["success"]:
        console.print(Panel.fit(
            "[bold green]✓ Scenario PASSED[/bold green]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]✗ Scenario FAILED[/bold red]",
            border_style="red"
        ))
    
    console.print()
    
    # Show metrics
    table = Table(title="📊 Results", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Status", justify="center")
    
    metrics = result.get("metrics", {})
    
    ttrc = metrics.get("time_to_root_cause")
    table.add_row(
        "Time to Root Cause",
        f"{ttrc:.1f}s" if ttrc else "—",
        _status_icon(ttrc is not None and ttrc < 60)
    )
    
    accuracy = metrics.get("accuracy", 0)
    table.add_row(
        "Overall Accuracy",
        f"{accuracy * 100:.0f}%",
        _status_icon(accuracy >= 0.7)
    )
    
    table.add_row(
        "Root Cause Correct",
        "Yes" if metrics.get("root_cause_correct") else "No",
        _status_icon(metrics.get("root_cause_correct"))
    )
    
    table.add_row(
        "Service Correct",
        "Yes" if metrics.get("service_correct") else "No",
        _status_icon(metrics.get("service_correct"))
    )
    
    console.print(table)
    
    # Show agent output if verbose
    if verbose and "agent_output" in result:
        console.print()
        console.print("[bold]Agent Analysis:[/bold]")
        output = result["agent_output"]
        console.print(f"  Root Cause: {output.get('root_cause', '—')}")
        console.print(f"  Confidence: {output.get('confidence', 0) * 100:.0f}%")
        if output.get("reasoning"):
            console.print(f"  Reasoning: {output['reasoning'][:200]}...")
    
    console.print()


@eval.command("create")
@click.option("--file", "-f", "filepath", type=click.Path(), help="Output file path")
@click.option("--template", "-t", is_flag=True, help="Create from interactive template")
@click.option("--name", "-n", help="Scenario name")
@click.option("--description", "-d", help="Scenario description")
def eval_create(filepath: str, template: bool, name: str, description: str):
    """Create a new evaluation scenario.
    
    Creates a YAML scenario file that can be used to test the agent.
    Use --template for an interactive wizard.
    
    \b
    Examples:
      $ autosre eval create --template
      $ autosre eval create -f custom.yaml -n my-scenario
    """
    import yaml
    
    if template:
        # Interactive creation
        console.print()
        console.print(Panel.fit(
            "[bold cyan]📝 Create New Scenario[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
        
        name = name or click.prompt("Scenario name", type=str)
        description = description or click.prompt("Description", type=str)
        difficulty = click.prompt("Difficulty", type=click.Choice(["easy", "medium", "hard"]), default="medium")
        
        expected_root_cause = click.prompt("Expected root cause", type=str)
        expected_service = click.prompt("Expected affected service (optional)", default="", type=str) or None
        
        scenario_data = {
            "name": name,
            "description": description,
            "difficulty": difficulty,
            "alert": {
                "name": "CustomAlert",
                "severity": "high",
                "summary": "Alert triggered for investigation",
            },
            "services": [],
            "changes": [],
            "expected_root_cause": expected_root_cause,
            "expected_service": expected_service,
            "max_time_seconds": 300,
        }
    else:
        # Create template
        scenario_data = {
            "name": name or "custom-scenario",
            "description": description or "Custom evaluation scenario",
            "difficulty": "medium",
            "alert": {
                "name": "ExampleAlert",
                "severity": "high",
                "source": "prometheus",
                "summary": "Example alert for testing",
                "labels": {},
            },
            "services": [
                {
                    "name": "example-service",
                    "namespace": "default",
                    "status": "degraded",
                    "replicas": 3,
                    "ready_replicas": 2,
                },
            ],
            "changes": [
                {
                    "type": "deployment",
                    "service_name": "example-service",
                    "description": "Example change",
                    "author": "user",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            ],
            "expected_root_cause": "Description of the expected root cause",
            "expected_service": "example-service",
            "expected_runbook": None,
            "expected_action": "Description of expected action",
            "max_time_seconds": 300,
        }
    
    # Determine output path
    if filepath:
        output_path = Path(filepath)
    else:
        scenarios_dir = Path.home() / ".autosre" / "scenarios"
        scenarios_dir.mkdir(parents=True, exist_ok=True)
        output_path = scenarios_dir / f"{scenario_data['name']}.yaml"
    
    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(scenario_data, f, default_flow_style=False, sort_keys=False)
    
    console.print()
    console.print(f"[green]✓[/] Created scenario at: {output_path}")
    console.print(f"[dim]Run it with: autosre eval run --scenario {scenario_data['name']}[/dim]")
    console.print()


@eval.command("report")
@click.option("--scenario", "-s", help="Filter by scenario name")
@click.option("--limit", "-l", default=20, help="Number of results to show")
@click.option("--format", "-f", "fmt", type=click.Choice(["table", "json", "summary"]), default="table")
def eval_report(scenario: str, limit: int, fmt: str):
    """Show evaluation results and history.
    
    Displays past evaluation runs with metrics and trends.
    
    \b
    Examples:
      $ autosre eval report
      $ autosre eval report --scenario deployment-failure
      $ autosre eval report --format summary
    """
    from autosre.evals import get_results
    import json
    
    results = get_results(scenario=scenario, limit=limit)
    
    if fmt == "json":
        console.print(json.dumps(results, indent=2, default=str))
        return
    
    console.print()
    
    if not results:
        console.print(Panel.fit(
            "[yellow]No evaluation results found[/yellow]\n\n"
            "Run 'autosre eval run --scenario <name>' to generate results",
            border_style="yellow"
        ))
        return
    
    if fmt == "summary":
        _show_summary(results)
        return
    
    table = Table(title="📈 Evaluation Results", box=box.ROUNDED)
    table.add_column("Scenario", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Time to RC", justify="right")
    table.add_column("Accuracy", justify="right")
    table.add_column("Run At", style="dim")
    
    for result in results:
        status = "[green]✓ PASS[/]" if result.get("success") else "[red]✗ FAIL[/]"
        ttrc = result.get("time_to_root_cause")
        ttrc_str = f"{ttrc:.1f}s" if ttrc else "—"
        accuracy = result.get("accuracy", 0)
        accuracy_str = f"{accuracy * 100:.0f}%"
        
        if accuracy >= 0.8:
            accuracy_str = f"[green]{accuracy_str}[/]"
        elif accuracy >= 0.5:
            accuracy_str = f"[yellow]{accuracy_str}[/]"
        else:
            accuracy_str = f"[red]{accuracy_str}[/]"
        
        table.add_row(
            result.get("scenario", "unknown"),
            status,
            ttrc_str,
            accuracy_str,
            result.get("run_at", "—")[:16] if result.get("run_at") else "—",
        )
    
    console.print(table)
    console.print()


def _show_summary(results: list):
    """Show summary statistics."""
    if not results:
        console.print("[dim]No results to summarize[/dim]")
        return
    
    total = len(results)
    passed = sum(1 for r in results if r.get("success"))
    avg_accuracy = sum(r.get("accuracy", 0) for r in results) / total
    avg_ttrc = sum(r.get("time_to_root_cause", 0) or 0 for r in results) / total
    
    console.print(Panel.fit(
        "[bold cyan]📊 Evaluation Summary[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    
    table.add_row("Total Runs", f"[cyan]{total}[/cyan]")
    table.add_row("Passed", f"[green]{passed}[/green] ({passed/total*100:.0f}%)")
    table.add_row("Failed", f"[red]{total - passed}[/red] ({(total-passed)/total*100:.0f}%)")
    table.add_row("Avg Accuracy", f"{avg_accuracy*100:.1f}%")
    table.add_row("Avg Time to RC", f"{avg_ttrc:.1f}s")
    
    console.print(table)
    console.print()
    
    # Per-scenario breakdown
    scenarios: dict[str, dict] = {}
    for r in results:
        name = r.get("scenario", "unknown")
        if name not in scenarios:
            scenarios[name] = {"total": 0, "passed": 0, "accuracy": []}
        scenarios[name]["total"] += 1
        if r.get("success"):
            scenarios[name]["passed"] += 1
        accuracy_list: list[float] = scenarios[name]["accuracy"]
        accuracy_list.append(r.get("accuracy", 0))
    
    console.print("[bold]Per-Scenario Breakdown:[/bold]")
    for name, data in scenarios.items():
        acc_list: list[float] = data["accuracy"]
        avg = sum(acc_list) / len(acc_list) if acc_list else 0
        console.print(f"  {name}: {data['passed']}/{data['total']} passed, {avg*100:.0f}% avg accuracy")
    
    console.print()


def _status_icon(condition: bool) -> str:
    """Return status icon based on condition."""
    return "[green]✓[/]" if condition else "[red]✗[/]"
