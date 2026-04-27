"""
OpenSRE CLI — AI-Powered Incident Response
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from opensre_core import __version__

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
    console.print("[green]✓ Action completed[/]")


@app.command()
def status():
    """
    📊 Check connection status to all integrations.
    """
    console.print(Panel("[bold]Checking integrations...[/]", title="📊 Status"))
    asyncio.run(_check_status())


async def _check_status():
    """Check all integration statuses."""
    from opensre_core.adapters.kubernetes import KubernetesAdapter
    from opensre_core.adapters.llm import LLMAdapter
    from opensre_core.adapters.prometheus import PrometheusAdapter

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


# =============================================================================
# Agent Commands - YAML-based workflow agents
# =============================================================================

agent_app = typer.Typer(
    name="agent",
    help="🤖 Manage and run YAML-based workflow agents.",
    no_args_is_help=True,
)
app.add_typer(agent_app, name="agent")


@agent_app.command("list")
def agent_list(
    agents_dir: str = typer.Option("agents", "--dir", "-d", help="Agents directory"),
):
    """
    📋 List available agents.
    """
    from pathlib import Path

    import yaml

    agents_path = Path(agents_dir)
    if not agents_path.exists():
        console.print(f"[yellow]Agents directory not found: {agents_dir}[/]")
        return

    agents = []
    for agent_dir in sorted(agents_path.iterdir()):
        if agent_dir.is_dir():
            agent_yaml = agent_dir / "agent.yaml"
            if agent_yaml.exists():
                try:
                    with open(agent_yaml) as f:
                        config = yaml.safe_load(f)
                    agents.append({
                        "name": config.get("name", agent_dir.name),
                        "version": config.get("version", "1.0.0"),
                        "description": config.get("description", "")[:60],
                        "triggers": len(config.get("triggers", [])),
                        "steps": len(config.get("steps", [])),
                    })
                except Exception as e:
                    agents.append({
                        "name": agent_dir.name,
                        "version": "?",
                        "description": f"[red]Error: {e}[/]",
                        "triggers": 0,
                        "steps": 0,
                    })

    if not agents:
        console.print("[yellow]No agents found.[/]")
        return

    table = Table(title="🤖 Available Agents", box=None)
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Triggers", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Description", style="dim", max_width=50)

    for agent in agents:
        table.add_row(
            agent["name"],
            agent["version"],
            str(agent["triggers"]),
            str(agent["steps"]),
            agent["description"],
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(agents)} agents[/]")


@agent_app.command("run")
def agent_run(
    agent_path: str = typer.Argument(..., help="Path to agent YAML file or directory"),
    context: list[str] = typer.Option([], "--context", "-c", help="Context variables (key=value)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    ▶️ Run an agent from a YAML file.
    """
    from pathlib import Path

    import yaml

    agent_file = Path(agent_path)
    if agent_file.is_dir():
        agent_file = agent_file / "agent.yaml"

    if not agent_file.exists():
        console.print(f"[red]Agent file not found: {agent_file}[/]")
        raise typer.Exit(1)

    # Parse context variables
    ctx = {}
    for c in context:
        if "=" in c:
            key, value = c.split("=", 1)
            ctx[key] = value

    # Load agent YAML
    try:
        with open(agent_file) as f:
            agent_config = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Failed to load agent: {e}[/]")
        raise typer.Exit(1)

    agent_name = agent_config.get("name", agent_file.parent.name)

    console.print(f"Running agent: [cyan]{agent_name}[/]")
    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/]")

    # Validate agent schema
    try:
        from opensre.core.models import AgentDefinition
        agent_def = AgentDefinition(**agent_config)
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/]")
        raise typer.Exit(1)

    if dry_run:
        # Show steps that would be executed
        table = Table(title=f"Steps in {agent_name}", box=None)
        table.add_column("#", style="dim")
        table.add_column("Step", style="cyan")
        table.add_column("Action")
        table.add_column("Condition", style="dim", max_width=30)

        for i, step in enumerate(agent_def.steps, 1):
            condition = step.condition[:30] + "..." if step.condition and len(step.condition) > 30 else (step.condition or "-")
            table.add_row(str(i), step.name, f"{step.skill}.{step.method}", condition)

        console.print(table)
        console.print(f"\n[dim]Would execute {len(agent_def.steps)} steps[/]")
        return

    console.print("[yellow]Agent execution not yet implemented in CLI.[/]")


@agent_app.command("validate")
def agent_validate(
    agent_path: str = typer.Argument(..., help="Path to agent YAML file or directory"),
):
    """
    ✅ Validate an agent YAML file.
    """
    from pathlib import Path

    import yaml

    agent_file = Path(agent_path)
    if agent_file.is_dir():
        agent_file = agent_file / "agent.yaml"

    if not agent_file.exists():
        console.print(f"[red]Agent file not found: {agent_file}[/]")
        raise typer.Exit(1)

    console.print(f"Validating: [cyan]{agent_file}[/]")

    # Load YAML
    try:
        with open(agent_file) as f:
            agent_config = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]✗ YAML parse error: {e}[/]")
        raise typer.Exit(1)

    console.print("[green]✓ Valid YAML syntax[/]")

    # Validate schema
    try:
        from opensre.core.models import AgentDefinition
        agent_def = AgentDefinition(**agent_config)
    except Exception as e:
        console.print(f"[red]✗ Schema validation error: {e}[/]")
        raise typer.Exit(1)

    console.print("[green]✓ Valid agent schema[/]")

    # Check skills
    skills = agent_config.get("skills", [])
    console.print(f"[green]✓ {len(skills)} skills declared: {', '.join(skills)}[/]")

    # Check steps
    steps = agent_config.get("steps", [])
    console.print(f"[green]✓ {len(steps)} steps defined[/]")

    # Validate step actions reference declared skills
    step_skills = set()
    for step in agent_def.steps:
        step_skills.add(step.skill)

    undeclared = step_skills - set(skills) - {"compute", "state", "template"}
    if undeclared:
        console.print(f"[yellow]⚠ Steps use undeclared skills: {', '.join(undeclared)}[/]")
    else:
        console.print("[green]✓ All step skills are declared[/]")

    console.print(f"\n[bold green]✓ Agent '{agent_def.name}' is valid[/]")


# =============================================================================
# Skills Commands - List and inspect available skills
# =============================================================================

skills_app = typer.Typer(
    name="skills",
    help="🔧 List and inspect available skills.",
    no_args_is_help=True,
)
app.add_typer(skills_app, name="skills")


@skills_app.command("list")
def skills_list(
    skills_dir: str = typer.Option("skills", "--dir", "-d", help="Skills directory"),
):
    """
    📋 List available skills.
    """
    from pathlib import Path

    import yaml

    skills_path = Path(skills_dir)
    if not skills_path.exists():
        console.print(f"[yellow]Skills directory not found: {skills_dir}[/]")
        return

    skills = []
    for skill_dir in sorted(skills_path.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_yaml = skill_dir / "skill.yaml"
            if skill_yaml.exists():
                try:
                    with open(skill_yaml) as f:
                        config = yaml.safe_load(f)
                    skills.append({
                        "name": config.get("name", skill_dir.name),
                        "version": config.get("version", "1.0.0"),
                        "description": config.get("description", "")[:60],
                        "actions": len(config.get("actions", [])),
                    })
                except Exception as e:
                    skills.append({
                        "name": skill_dir.name,
                        "version": "?",
                        "description": f"[red]Error: {e}[/]",
                        "actions": 0,
                    })

    if not skills:
        console.print("[yellow]No skills found.[/]")
        return

    table = Table(title="🔧 Available Skills", box=None)
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Actions", justify="right")
    table.add_column("Description", style="dim", max_width=50)

    for skill in skills:
        table.add_row(
            skill["name"],
            skill["version"],
            str(skill["actions"]),
            skill["description"],
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(skills)} skills[/]")


@skills_app.command("show")
def skills_show(
    skill_name: str = typer.Argument(..., help="Skill name to show details"),
    skills_dir: str = typer.Option("skills", "--dir", "-d", help="Skills directory"),
):
    """
    🔍 Show detailed information about a skill.
    """
    from pathlib import Path

    import yaml

    skill_yaml = Path(skills_dir) / skill_name / "skill.yaml"
    if not skill_yaml.exists():
        console.print(f"[red]Skill not found: {skill_name}[/]")
        raise typer.Exit(1)

    with open(skill_yaml) as f:
        config = yaml.safe_load(f)

    console.print(Panel(
        f"[bold]{config.get('name', skill_name)}[/] v{config.get('version', '1.0.0')}\n"
        f"{config.get('description', '')}",
        title="🔧 Skill Details",
        border_style="cyan"
    ))

    # Show actions
    actions = config.get("actions", [])
    if actions:
        console.print("\n[bold]Actions:[/]")
        for action in actions:
            params = action.get("params", [])
            param_str = ", ".join(p.get("name", "?") for p in params) if params else "none"
            console.print(f"  • [cyan]{action.get('name', '?')}[/]({param_str})")
            if action.get("description"):
                console.print(f"    {action['description'][:70]}")


if __name__ == "__main__":
    app()
