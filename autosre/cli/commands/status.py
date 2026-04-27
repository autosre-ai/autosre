"""Status command for AutoSRE."""

from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()


def run_status(quiet: bool = False) -> None:
    """Display AutoSRE status."""
    # Check for configuration
    autosre_dir = Path(".autosre")
    
    if not quiet:
        table = Table(title="AutoSRE Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details")
        
        # Config directory
        config_status = "✓" if autosre_dir.exists() else "✗"
        table.add_row(
            "Configuration", 
            config_status, 
            str(autosre_dir.resolve()) if autosre_dir.exists() else "Not initialized"
        )
        
        # Database
        db_path = autosre_dir / "context.db"
        db_status = "✓" if db_path.exists() else "✗"
        table.add_row("Context Store", db_status, "SQLite database")
        
        # LLM Provider
        import os
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        llm_status = "✓" if (has_openai or has_anthropic) else "✗"
        providers = []
        if has_openai:
            providers.append("OpenAI")
        if has_anthropic:
            providers.append("Anthropic")
        table.add_row("LLM Provider", llm_status, ", ".join(providers) if providers else "No API keys set")
        
        console.print(table)
