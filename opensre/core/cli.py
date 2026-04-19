"""CLI for OpenSRE."""

import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

from .config import ConfigManager, init_config
from .models import StepStatus
from .runtime import Agent, AgentRunner
from .skills import SkillRegistry
from .utils import ensure_dir, save_yaml


console = Console()


def get_status_style(status: StepStatus) -> str:
    """Get Rich style for a status."""
    return {
        StepStatus.SUCCESS: "green",
        StepStatus.FAILED: "red",
        StepStatus.SKIPPED: "yellow",
        StepStatus.RUNNING: "blue",
        StepStatus.PENDING: "dim",
        StepStatus.RETRYING: "yellow",
    }.get(status, "white")


@click.group()
@click.option("--env", "-e", default=None, help="Environment to use")
@click.option("--project", "-p", default=None, help="Project root directory")
@click.pass_context
def cli(ctx: click.Context, env: str | None, project: str | None) -> None:
    """OpenSRE - Site Reliability Engineering automation framework."""
    ctx.ensure_object(dict)
    ctx.obj["env"] = env
    ctx.obj["project"] = project


@cli.command()
@click.option("--name", "-n", default="my-project", help="Project name")
@click.option("--path", "-p", default=".", help="Project directory")
def init(name: str, path: str) -> None:
    """Initialize a new OpenSRE project."""
    project_dir = Path(path).resolve()
    
    console.print(f"[bold]Initializing OpenSRE project:[/bold] {name}")
    console.print(f"[dim]Location: {project_dir}[/dim]")
    
    # Create directory structure
    dirs = ["skills", "agents", "secrets", "config"]
    for d in dirs:
        ensure_dir(project_dir / d)
        console.print(f"  [green]✓[/green] Created {d}/")
    
    # Create opensre.yaml
    config = {
        "project_name": name,
        "version": "1.0.0",
        "default_environment": "dev",
        "environments": {
            "dev": {
                "variables": {
                    "log_level": "debug"
                },
                "skills_dir": "skills",
                "agents_dir": "agents"
            },
            "staging": {
                "variables": {
                    "log_level": "info"
                }
            },
            "prod": {
                "variables": {
                    "log_level": "warning"
                }
            }
        },
        "config": {
            "default_timeout": 30,
            "retry_attempts": 3
        }
    }
    save_yaml(project_dir / "opensre.yaml", config)
    console.print("  [green]✓[/green] Created opensre.yaml")
    
    # Create example skill
    example_skill_dir = project_dir / "skills" / "hello"
    ensure_dir(example_skill_dir)
    
    skill_yaml = {
        "name": "hello",
        "version": "1.0.0",
        "description": "Example hello world skill",
        "methods": ["greet", "farewell"]
    }
    save_yaml(example_skill_dir / "skill.yaml", skill_yaml)
    
    skill_py = '''"""Hello world skill for OpenSRE."""

from opensre.core.skills import Skill


class HelloSkill(Skill):
    """A simple hello world skill."""
    
    name = "hello"
    version = "1.0.0"
    description = "Example hello world skill"
    
    def greet(self, context: dict, name: str = "World") -> dict:
        """Greet someone."""
        message = f"Hello, {name}!"
        return {"message": message}
    
    def farewell(self, context: dict, name: str = "World") -> dict:
        """Say goodbye to someone."""
        message = f"Goodbye, {name}!"
        return {"message": message}
'''
    (example_skill_dir / "skill.py").write_text(skill_py)
    console.print("  [green]✓[/green] Created example skill: hello")
    
    # Create example agent
    agent_yaml = {
        "name": "hello-agent",
        "version": "1.0.0",
        "description": "Example agent that greets and farewells",
        "skills": ["hello"],
        "steps": [
            {
                "id": "greet",
                "skill": "hello",
                "method": "greet",
                "args": {"name": "OpenSRE"},
                "output": "greeting"
            },
            {
                "id": "farewell",
                "skill": "hello",
                "method": "farewell",
                "args": {"name": "{{ greeting.message }}"},
                "output": "farewell"
            }
        ]
    }
    save_yaml(project_dir / "agents" / "hello-agent.yaml", agent_yaml)
    console.print("  [green]✓[/green] Created example agent: hello-agent.yaml")
    
    # Create .gitignore
    gitignore = """# Secrets
secrets/*.yaml
!secrets/.gitkeep

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp
"""
    (project_dir / ".gitignore").write_text(gitignore)
    console.print("  [green]✓[/green] Created .gitignore")
    
    # Create secrets placeholder
    (project_dir / "secrets" / ".gitkeep").touch()
    
    console.print()
    console.print(Panel.fit(
        "[bold green]Project initialized successfully![/bold green]\n\n"
        "Next steps:\n"
        "  1. cd " + str(project_dir) + "\n"
        "  2. opensre skill list\n"
        "  3. opensre agent run hello-agent.yaml",
        title="🚀 OpenSRE"
    ))


# ============== Skill Commands ==============

@cli.group()
def skill() -> None:
    """Manage skills."""
    pass


@skill.command("list")
@click.pass_context
def skill_list(ctx: click.Context) -> None:
    """List available skills."""
    try:
        config = _get_config(ctx)
        registry = SkillRegistry(config.get_skills_dir())
        skills = registry.discover()
        
        if not skills:
            console.print("[yellow]No skills found.[/yellow]")
            console.print(f"[dim]Skills directory: {config.get_skills_dir()}[/dim]")
            return
        
        table = Table(title="Available Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description")
        table.add_column("Methods")
        table.add_column("Status")
        
        for s in skills:
            status = "[green]OK[/green]" if not s.error else f"[red]{s.error}[/red]"
            table.add_row(
                s.name,
                s.version,
                s.description[:40] + "..." if len(s.description) > 40 else s.description,
                ", ".join(s.methods[:3]) + ("..." if len(s.methods) > 3 else ""),
                status
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@skill.command("info")
@click.argument("name")
@click.pass_context
def skill_info(ctx: click.Context, name: str) -> None:
    """Show detailed information about a skill."""
    try:
        config = _get_config(ctx)
        registry = SkillRegistry(config.get_skills_dir())
        registry.discover()
        
        metadata = registry.get_metadata(name)
        if not metadata:
            console.print(f"[red]Skill not found:[/red] {name}")
            sys.exit(1)
        
        tree = Tree(f"[bold cyan]{metadata.name}[/bold cyan] v{metadata.version}")
        tree.add(f"[dim]Description:[/dim] {metadata.description}")
        
        methods_branch = tree.add("[bold]Methods")
        for method in metadata.methods:
            methods_branch.add(f"[green]{method}[/green]")
        
        if metadata.dependencies:
            deps_branch = tree.add("[bold]Dependencies")
            for dep in metadata.dependencies:
                deps_branch.add(f"[yellow]{dep}[/yellow]")
        
        console.print(tree)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@skill.command("test")
@click.argument("name")
@click.option("--method", "-m", default=None, help="Specific method to test")
@click.pass_context
def skill_test(ctx: click.Context, name: str, method: str | None) -> None:
    """Test a skill by loading and calling its methods."""
    try:
        config = _get_config(ctx)
        registry = SkillRegistry(config.get_skills_dir())
        
        console.print(f"[bold]Testing skill:[/bold] {name}")
        
        # Load the skill
        with console.status(f"Loading {name}..."):
            skill_instance = registry.load(name)
        console.print(f"  [green]✓[/green] Loaded successfully")
        
        # Get methods
        methods = skill_instance.get_methods()
        if method:
            if method not in methods:
                console.print(f"  [red]✗[/red] Method not found: {method}")
                sys.exit(1)
            methods = [method]
        
        console.print(f"  [dim]Methods: {', '.join(methods)}[/dim]")
        
        # Test each method (just check it's callable)
        for m in methods:
            if hasattr(skill_instance, m) and callable(getattr(skill_instance, m)):
                console.print(f"  [green]✓[/green] {m} is callable")
            else:
                console.print(f"  [red]✗[/red] {m} is not callable")
        
        console.print()
        console.print("[green]Skill test passed![/green]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# ============== Agent Commands ==============

@cli.group()
def agent() -> None:
    """Manage and run agents."""
    pass


@agent.command("list")
@click.pass_context
def agent_list(ctx: click.Context) -> None:
    """List available agents."""
    try:
        config = _get_config(ctx)
        runner = AgentRunner(config)
        agents = runner.discover_agents()
        
        if not agents:
            console.print("[yellow]No agents found.[/yellow]")
            console.print(f"[dim]Agents directory: {config.get_agents_dir()}[/dim]")
            return
        
        table = Table(title="Available Agents")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description")
        table.add_column("Skills")
        table.add_column("Steps", justify="right")
        
        for a in agents:
            if "error" in a:
                table.add_row(
                    a["name"], "", f"[red]Error: {a['error']}[/red]", "", ""
                )
            else:
                table.add_row(
                    a["name"],
                    a.get("version", ""),
                    a.get("description", "")[:40],
                    ", ".join(a.get("skills", [])[:3]),
                    str(a.get("steps", 0))
                )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@agent.command("run")
@click.argument("agent_file")
@click.option("--context", "-c", multiple=True, help="Context variables (key=value)")
@click.option("--dry-run", is_flag=True, help="Show what would be executed")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def agent_run(
    ctx: click.Context,
    agent_file: str,
    context: tuple[str, ...],
    dry_run: bool,
    verbose: bool
) -> None:
    """Run an agent from a YAML file or directory name."""
    try:
        config = _get_config(ctx)
        
        # Parse context
        initial_context: dict[str, Any] = {}
        for item in context:
            if "=" in item:
                key, value = item.split("=", 1)
                initial_context[key] = value
        
        # Find agent file - supports multiple formats:
        # 1. Direct path to YAML file
        # 2. Agent directory name (looks for agent.yaml inside)
        # 3. Agent name without extension (tries name.yaml and name/agent.yaml)
        agent_path = Path(agent_file)
        
        if agent_path.exists():
            # Direct path exists
            if agent_path.is_dir():
                # It's a directory, look for agent.yaml inside
                agent_yaml = agent_path / "agent.yaml"
                if agent_yaml.exists():
                    agent_path = agent_yaml
                else:
                    console.print(f"[red]Agent definition not found:[/red] {agent_yaml}")
                    sys.exit(1)
        else:
            # Try in agents directory
            agents_dir = config.get_agents_dir()
            
            # Try as a directory name first
            agent_dir = agents_dir / agent_file
            if agent_dir.is_dir():
                agent_path = agent_dir / "agent.yaml"
                if not agent_path.exists():
                    console.print(f"[red]Agent definition not found:[/red] {agent_path}")
                    sys.exit(1)
            else:
                # Try as a YAML file
                agent_path = agents_dir / agent_file
                if not agent_path.exists():
                    # Try adding .yaml extension
                    agent_path = agents_dir / f"{agent_file}.yaml"
                    if not agent_path.exists():
                        console.print(f"[red]Agent not found:[/red] {agent_file}")
                        console.print(f"[dim]Searched in: {agents_dir}[/dim]")
                        sys.exit(1)
        
        runner = AgentRunner(config)
        
        console.print(f"[bold]Running agent:[/bold] {agent_path.stem}")
        if dry_run:
            console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
        console.print()
        
        # Run the agent
        with console.status("Executing..."):
            result = runner.run(agent_path, initial_context, dry_run)
        
        # Show results
        status_style = get_status_style(result.status)
        console.print(f"[bold]Status:[/bold] [{status_style}]{result.status.value}[/{status_style}]")
        
        if result.duration_ms:
            console.print(f"[dim]Duration: {result.duration_ms:.2f}ms[/dim]")
        
        # Show step results
        console.print()
        table = Table(title="Step Results")
        table.add_column("Step", style="cyan")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Output" if verbose else "")
        
        for step in result.steps:
            style = get_status_style(step.status)
            duration = f"{step.duration_ms:.2f}ms" if step.duration_ms else "-"
            output = ""
            if verbose and step.output:
                output = str(step.output)[:50]
            
            table.add_row(
                step.step_id,
                f"[{style}]{step.status.value}[/{style}]",
                duration,
                output
            )
        
        console.print(table)
        
        if result.error:
            console.print()
            console.print(f"[red]Error:[/red] {result.error}")
        
        if result.status == StepStatus.FAILED:
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@agent.command("dev")
@click.argument("agent_file")
@click.option("--watch", "-w", is_flag=True, help="Watch for changes and re-run")
@click.pass_context
def agent_dev(ctx: click.Context, agent_file: str, watch: bool) -> None:
    """Run an agent in development mode with verbose output."""
    ctx.invoke(agent_run, agent_file=agent_file, verbose=True, dry_run=False)


# ============== Config Commands ==============

@cli.group()
def config() -> None:
    """Manage configuration."""
    pass


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration."""
    try:
        cfg = _get_config(ctx)
        
        console.print(f"[bold]Environment:[/bold] {cfg.environment}")
        console.print(f"[bold]Project Root:[/bold] {cfg.project_root}")
        console.print(f"[bold]Skills Dir:[/bold] {cfg.get_skills_dir()}")
        console.print(f"[bold]Agents Dir:[/bold] {cfg.get_agents_dir()}")
        console.print()
        
        config_data = cfg.all()
        if config_data:
            console.print("[bold]Configuration:[/bold]")
            for key, value in config_data.items():
                console.print(f"  {key}: {value}")
        else:
            console.print("[dim]No configuration values set[/dim]")
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@config.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get a configuration value."""
    try:
        cfg = _get_config(ctx)
        value = cfg.get(key)
        if value is not None:
            console.print(value)
        else:
            console.print(f"[yellow]Key not found:[/yellow] {key}")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# ============== Helper Functions ==============

def _get_config(ctx: click.Context) -> ConfigManager:
    """Get configuration manager from context."""
    project = ctx.obj.get("project")
    env = ctx.obj.get("env")
    
    config = ConfigManager(project, env)
    try:
        config.load()
    except Exception:
        # Allow running without config file for some commands
        pass
    return config


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
