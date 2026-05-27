"""
AutoSRE Tutorial Command

Interactive onboarding tutorial to help new users get started with AutoSRE.
"""

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.rule import Rule
from rich.tree import Tree
from rich.syntax import Syntax
from rich.markdown import Markdown

app = typer.Typer(
    name="tutorial",
    help="Interactive onboarding tutorial for AutoSRE",
    no_args_is_help=False,
)

console = Console()

# Tutorial sections
SECTIONS = [
    "welcome",
    "commands",
    "investigation",
    "configuration",
    "resources",
]


def _print_header():
    """Print the tutorial header with ASCII art."""
    header = """
[bold cyan]
   █████╗ ██╗   ██╗████████╗ ██████╗ ███████╗██████╗ ███████╗
  ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔════╝██╔══██╗██╔════╝
  ███████║██║   ██║   ██║   ██║   ██║███████╗██████╔╝█████╗  
  ██╔══██║██║   ██║   ██║   ██║   ██║╚════██║██╔══██╗██╔══╝  
  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝███████║██║  ██║███████╗
  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝
[/]
    """
    console.print(header)
    console.print("[bold white]  AI-Powered Site Reliability Engineering Agent[/]")
    console.print("[dim]  Autonomous incident investigation and resolution[/]\n")


def _section_welcome():
    """Section 1: Welcome message."""
    console.print(Rule("[bold cyan]Welcome to AutoSRE[/]", style="cyan"))
    console.print()
    
    welcome_text = """
AutoSRE is your AI-powered SRE assistant that helps you:

[bold green]🔍 Investigate incidents autonomously[/]
   AutoSRE collects metrics, logs, and traces to identify root causes

[bold green]🧠 Learn from your infrastructure[/]
   Episodic memory helps it understand your services better over time

[bold green]💬 Chat interactively[/]
   Ask questions about your systems in natural language

[bold green]⚡ Accelerate MTTR[/]
   Get actionable recommendations in minutes, not hours
"""
    console.print(Panel(
        welcome_text,
        title="[bold white]What is AutoSRE?[/]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()
    
    # Quick stats
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column("stat", style="bold cyan")
    stats_table.add_column("value", style="white")
    stats_table.add_row("📊", "Integrates with Prometheus, Loki, Kubernetes, and more")
    stats_table.add_row("🤖", "Uses Claude, GPT-4, or local LLMs for analysis")
    stats_table.add_row("📝", "Generates detailed incident reports automatically")
    stats_table.add_row("🔄", "Improves with each investigation through memory")
    
    console.print(stats_table)
    console.print()


def _section_commands():
    """Section 2: Walk through basic commands."""
    console.print(Rule("[bold cyan]Core Commands[/]", style="cyan"))
    console.print()
    
    console.print("[bold]AutoSRE provides several commands to help you manage incidents:[/]\n")
    
    # Commands table
    commands_table = Table(
        title="📋 Essential Commands",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
    )
    commands_table.add_column("Command", style="bold green")
    commands_table.add_column("Description")
    commands_table.add_column("Example", style="dim")
    
    commands_table.add_row(
        "autosre run",
        "Quick-start an investigation",
        "autosre run \"High error rate\""
    )
    commands_table.add_row(
        "autosre investigate",
        "Advanced investigation options",
        "autosre investigate run \"Alert\""
    )
    commands_table.add_row(
        "autosre chat",
        "Interactive AI chat assistant",
        "autosre chat start"
    )
    commands_table.add_row(
        "autosre status",
        "Check system status",
        "autosre status -v"
    )
    commands_table.add_row(
        "autosre doctor",
        "Health check & diagnostics",
        "autosre doctor check"
    )
    commands_table.add_row(
        "autosre memory",
        "Manage episodic memory",
        "autosre memory list"
    )
    commands_table.add_row(
        "autosre config",
        "Configuration management",
        "autosre config show"
    )
    commands_table.add_row(
        "autosre demo",
        "Demo scenarios (simulated)",
        "autosre demo run"
    )
    
    console.print(commands_table)
    console.print()
    
    # Command examples
    console.print("[bold]🔥 Quick Examples:[/]\n")
    
    examples = [
        ("Start a quick investigation", "autosre run \"API latency spike on checkout-service\""),
        ("Investigate with options", "autosre investigate run \"DB connection errors\" --service postgres --severity critical"),
        ("Check configuration", "autosre config show"),
        ("Run health diagnostics", "autosre doctor check"),
        ("List past investigations", "autosre memory list --limit 5"),
    ]
    
    for description, command in examples:
        console.print(f"  [dim]# {description}[/]")
        console.print(Syntax(f"  $ {command}", "bash", theme="monokai", background_color="default"))
        console.print()


def _section_investigation():
    """Section 3: Demo investigation walkthrough."""
    console.print(Rule("[bold cyan]Investigation Demo[/]", style="cyan"))
    console.print()
    
    console.print("[bold]Let's walk through what happens during an investigation:[/]\n")
    
    # Investigation phases
    phases = [
        ("1️⃣", "Context Gathering", "Collect alert metadata, service topology, and recent deployments", 0.5),
        ("2️⃣", "Evidence Collection", "Query Prometheus metrics, search logs, fetch traces", 0.8),
        ("3️⃣", "Hypothesis Generation", "AI analyzes patterns and generates hypotheses", 0.6),
        ("4️⃣", "Root Cause Analysis", "Validate hypotheses against evidence", 0.7),
        ("5️⃣", "Report Generation", "Create actionable incident report", 0.4),
    ]
    
    console.print(Panel(
        "[bold cyan]Simulating investigation phases...[/]",
        border_style="cyan",
    ))
    console.print()
    
    for icon, phase, description, duration in phases:
        with Progress(
            SpinnerColumn(spinner_name="dots12"),
            TextColumn(f"[cyan]{icon} {phase}[/] - {description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=None)
            time.sleep(duration)
        
        console.print(f"  [green]✓[/] [bold]{icon} {phase}[/] - {description}")
    
    console.print()
    
    # Show example output
    console.print("[bold]📊 Example Investigation Output:[/]\n")
    
    output_example = """
┌─────────────────────────────────────────────────────────────┐
│ 🎯 ROOT CAUSE IDENTIFIED                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Redis connection pool exhaustion due to traffic spike       │
│                                                             │
│ Confidence: 92%                                             │
│ Duration: 4.2s                                              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ 💡 Recommendations:                                         │
│  1. Increase Redis connection pool size from 10 to 50       │
│  2. Add circuit breaker for Redis connections               │
│  3. Enable connection pool metrics alerting                 │
└─────────────────────────────────────────────────────────────┘
"""
    console.print(Panel(output_example.strip(), border_style="green"))
    console.print()


def _section_configuration():
    """Section 4: Configuration options."""
    console.print(Rule("[bold cyan]Configuration[/]", style="cyan"))
    console.print()
    
    console.print("[bold]AutoSRE can be configured through environment variables or config files:[/]\n")
    
    # Config tree
    tree = Tree("📁 [bold cyan]~/.autosre/[/]")
    tree.add("📄 config.yaml [dim]- Main configuration file[/]")
    tree.add("📁 memory/ [dim]- Episodic memory storage[/]")
    tree.add("📁 reports/ [dim]- Investigation reports[/]")
    
    console.print(tree)
    console.print()
    
    # Key environment variables
    console.print("[bold]🔑 Key Environment Variables:[/]\n")
    
    env_table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    env_table.add_column("Variable", style="green")
    env_table.add_column("Description")
    env_table.add_column("Default", style="dim")
    
    env_vars = [
        ("OPENSRE_LLM_PROVIDER", "LLM provider (anthropic/openai/ollama)", "anthropic"),
        ("OPENSRE_ANTHROPIC_API_KEY", "Anthropic API key for Claude", "-"),
        ("OPENSRE_OPENAI_API_KEY", "OpenAI API key for GPT-4", "-"),
        ("OPENSRE_PROMETHEUS_URL", "Prometheus server URL", "http://localhost:9090"),
        ("OPENSRE_LOKI_URL", "Loki server URL (optional)", "-"),
        ("OPENSRE_SLACK_BOT_TOKEN", "Slack bot token (optional)", "-"),
    ]
    
    for var, desc, default in env_vars:
        env_table.add_row(var, desc, default)
    
    console.print(env_table)
    console.print()
    
    # Config file example
    console.print("[bold]📄 Example config.yaml:[/]\n")
    
    config_example = """# AutoSRE Configuration
llm_provider: anthropic
anthropic_model: claude-sonnet-4-20250514

# Infrastructure
prometheus_url: http://prometheus:9090
loki_url: http://loki:3100

# Memory settings
memory_enabled: true
memory_retention_days: 30

# Alert thresholds
error_rate_threshold: 0.01
latency_p99_threshold_ms: 500
"""
    
    console.print(Syntax(config_example, "yaml", theme="monokai", background_color="default"))
    console.print()
    
    # Quick setup steps
    console.print("[bold]⚡ Quick Setup:[/]\n")
    setup_steps = [
        "export OPENSRE_ANTHROPIC_API_KEY=sk-ant-...",
        "autosre config init",
        "autosre doctor check",
        "autosre run \"Test investigation\"",
    ]
    
    for i, step in enumerate(setup_steps, 1):
        console.print(f"  [cyan]{i}.[/] [dim]$[/] {step}")
    console.print()


def _section_resources():
    """Section 5: Resources and next steps."""
    console.print(Rule("[bold cyan]Resources & Next Steps[/]", style="cyan"))
    console.print()
    
    # Resources panel
    resources_md = """
## 📚 Documentation

- **Quick Start Guide**: Get up and running in minutes
- **Configuration Guide**: Detailed configuration options
- **API Reference**: For integrating AutoSRE into your tools

## 🔗 Links

- GitHub: https://github.com/autosre/autosre
- Documentation: https://docs.autosre.io
- Community Slack: https://autosre-community.slack.com

## 💬 Getting Help

- `autosre doctor check` - Run diagnostics
- `autosre chat start` - Ask the AI assistant
- GitHub Issues - Report bugs and request features
"""
    
    console.print(Panel(
        Markdown(resources_md),
        title="[bold white]Resources[/]",
        border_style="cyan",
    ))
    console.print()
    
    # Next steps
    console.print("[bold]🚀 Next Steps:[/]\n")
    
    next_steps = [
        ("Run health check", "autosre doctor check"),
        ("Configure your environment", "autosre config init"),
        ("Try a demo investigation", "autosre demo run"),
        ("Start a real investigation", "autosre run \"Your alert here\""),
        ("Explore memory features", "autosre memory list"),
    ]
    
    for i, (description, command) in enumerate(next_steps, 1):
        console.print(f"  [bold cyan]{i}.[/] {description}")
        console.print(f"     [dim]$[/] [green]{command}[/]")
        console.print()


def _show_section(section: str):
    """Show a specific tutorial section."""
    section_funcs = {
        "welcome": _section_welcome,
        "commands": _section_commands,
        "investigation": _section_investigation,
        "configuration": _section_configuration,
        "resources": _section_resources,
    }
    
    if section in section_funcs:
        section_funcs[section]()
    else:
        console.print(f"[red]Unknown section: {section}[/]")


@app.callback(invoke_without_command=True)
def tutorial(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        "-i/-n",
        help="Run in interactive mode with prompts",
    ),
    section: Optional[str] = typer.Option(
        None,
        "--section",
        "-s",
        help=f"Jump to specific section: {', '.join(SECTIONS)}",
    ),
    quick: bool = typer.Option(
        False,
        "--quick",
        "-q",
        help="Quick mode - show all sections without pausing",
    ),
):
    """
    Interactive onboarding tutorial for AutoSRE.
    
    Learn how to use AutoSRE through a guided walkthrough that covers:
    
    - Core commands and their usage
    - How investigations work
    - Configuration options
    - Helpful resources
    
    Examples:
        autosre tutorial                    # Full interactive tutorial
        autosre tutorial --quick            # Quick mode, no pauses
        autosre tutorial -s commands        # Jump to commands section
        autosre tutorial --no-interactive   # Non-interactive mode
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return
    
    console.clear()
    _print_header()
    
    # Jump to specific section
    if section:
        if section not in SECTIONS:
            console.print(f"[red]Unknown section: {section}[/]")
            console.print(f"[dim]Available sections: {', '.join(SECTIONS)}[/]")
            raise typer.Exit(1)
        _show_section(section)
        return
    
    # Run through all sections
    for i, sec in enumerate(SECTIONS):
        _show_section(sec)
        
        # Interactive prompts between sections
        if interactive and not quick and i < len(SECTIONS) - 1:
            console.print()
            try:
                next_section = SECTIONS[i + 1].title()
                if not Confirm.ask(
                    f"[cyan]Continue to {next_section}?[/]",
                    default=True,
                ):
                    console.print("\n[dim]Tutorial paused. Run 'autosre tutorial' to continue.[/]")
                    raise typer.Exit(0)
            except KeyboardInterrupt:
                console.print("\n[dim]Tutorial cancelled.[/]")
                raise typer.Exit(0)
            
            console.print()
    
    # Final message
    console.print(Rule("[bold green]Tutorial Complete! 🎉[/]", style="green"))
    console.print()
    console.print(Panel(
        "[bold]You're all set to use AutoSRE![/]\n\n"
        "Start with [green]autosre doctor check[/] to verify your setup,\n"
        "then try [green]autosre run \"Your first investigation\"[/]\n\n"
        "[dim]Run 'autosre tutorial -s <section>' to revisit any section.[/]",
        title="[bold white]What's Next?[/]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()


@app.command("sections")
def list_sections():
    """List all available tutorial sections."""
    console.print("\n[bold]📚 Tutorial Sections[/]\n")
    
    section_descriptions = {
        "welcome": "Introduction to AutoSRE and its capabilities",
        "commands": "Overview of core commands and usage examples",
        "investigation": "Demo walkthrough of the investigation process",
        "configuration": "Configuration options and environment setup",
        "resources": "Documentation links and next steps",
    }
    
    for i, section in enumerate(SECTIONS, 1):
        desc = section_descriptions.get(section, "")
        console.print(f"  [cyan]{i}.[/] [bold]{section}[/] - {desc}")
    
    console.print()
    console.print("[dim]Run 'autosre tutorial -s <section>' to view a specific section.[/]")
    console.print()


@app.command("reset")
def reset_progress():
    """Reset tutorial progress (for future use with progress tracking)."""
    console.print("[yellow]Tutorial progress tracking is not yet implemented.[/]")
    console.print("[dim]Run 'autosre tutorial' to start the tutorial from the beginning.[/]")
