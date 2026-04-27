"""
AutoSRE CLI - Command-line interface for the AI SRE agent.

A rich, user-friendly CLI for managing all aspects of AutoSRE.
"""

import click
from rich.console import Console

from autosre.cli.commands import context, eval, sandbox, agent, feedback

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="autosre")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, quiet: bool, debug: bool):
    """AutoSRE - Open-source AI SRE Agent 🤖
    
    Built foundation-first for reliable incident response.
    
    \b
    Quick Start:
      $ autosre init                    # Initialize in current directory
      $ autosre sandbox start           # Start local Kind cluster
      $ autosre context sync --all      # Sync context from all sources
      $ autosre agent run               # Start the agent
    
    \b
    Documentation: https://github.com/opensre/autosre
    """
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet
    ctx.obj["debug"] = debug
    
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option("--dir", "-d", "directory", default=".", help="Directory to initialize")
@click.pass_context
def init(ctx: click.Context, directory: str):
    """Initialize AutoSRE in the current directory.
    
    Creates the necessary directory structure and configuration files
    to get started with AutoSRE.
    
    \b
    Creates:
      .autosre/        Configuration and database directory
      runbooks/        Runbook YAML files
      .env.example     Configuration template
    
    \b
    Example:
      $ autosre init
      $ autosre init --dir ./my-project
    """
    from autosre.cli.commands.init import run_init
    run_init(directory, quiet=ctx.obj.get("quiet", False))


@cli.command()
@click.pass_context
def status(ctx: click.Context):
    """Show AutoSRE status and health.
    
    Displays the current state of:
    - Configuration
    - Context store
    - LLM provider
    - Connected integrations
    
    \b
    Example:
      $ autosre status
    """
    from autosre.cli.commands.status import run_status
    run_status(quiet=ctx.obj.get("quiet", False))


# Register command groups
cli.add_command(context.context)
cli.add_command(eval.eval)
cli.add_command(sandbox.sandbox)
cli.add_command(agent.agent)
cli.add_command(feedback.feedback)


if __name__ == "__main__":
    cli()
