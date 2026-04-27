"""Initialize AutoSRE in a directory."""

import os
from pathlib import Path
from rich.console import Console

console = Console()


def run_init(directory: str = ".", quiet: bool = False) -> None:
    """Initialize AutoSRE in the specified directory."""
    dir_path = Path(directory).resolve()
    
    # Create directories
    (dir_path / ".autosre").mkdir(parents=True, exist_ok=True)
    (dir_path / "runbooks").mkdir(exist_ok=True)
    
    # Create .env.example
    env_example = dir_path / ".env.example"
    if not env_example.exists():
        env_example.write_text("""# AutoSRE Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Kubernetes (optional)
# KUBECONFIG=~/.kube/config

# Prometheus (optional)
# PROMETHEUS_URL=http://localhost:9090

# PagerDuty (optional)
# PAGERDUTY_API_KEY=...

# Slack (optional)
# SLACK_BOT_TOKEN=xoxb-...
""")
    
    if not quiet:
        console.print(f"[green]✓[/green] Initialized AutoSRE in {dir_path}")
        console.print(f"  [dim]Created .autosre/ and runbooks/[/dim]")
        console.print(f"  [dim]See .env.example for configuration[/dim]")
