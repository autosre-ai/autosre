"""
SRE Agent - Main CLI

AI-powered incident context gatherer for on-call SREs.
"""
import sys
from pathlib import Path
from datetime import datetime

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gatherer import ContextGatherer
from src.analyzer import LLMAnalyzer
from src.reporter import TerminalReporter


app = typer.Typer(
    name="sre-agent",
    help="AI-powered incident context gatherer for on-call SREs"
)
console = Console()


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file"""
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


@app.command()
def analyze(
    alert: str = typer.Argument(..., help="Alert description (e.g., 'checkout-service 5xx spike')"),
    service: str = typer.Option(None, "--service", "-s", help="Service name (auto-detected from alert if not provided)"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Path to config file"),
    mock_data: Path = typer.Option(None, "--mock-data", "-m", help="Path to mock data JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed analysis"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM analysis, use rule-based only"),
):
    """
    Analyze an incident and generate a situation report.
    
    Example:
        python src/main.py analyze "checkout-service 5xx spike"
    """
    
    # Load config
    cfg = load_config(config)
    
    # Auto-detect service from alert if not provided
    if not service:
        service = cfg.get("service", {}).get("name", "checkout-service")
        # Try to extract from alert text
        for word in alert.lower().split():
            if "service" in word or "-svc" in word:
                service = word.replace("-svc", "-service")
                break
    
    # Set default mock data path if not provided
    if not mock_data:
        mock_data = Path(__file__).parent.parent / "data" / "mock" / "checkout-incident.json"
    
    console.print(f"\n[bold cyan]🤖 SRE Agent[/] analyzing incident...")
    console.print(f"[dim]Service: {service} | Alert: {alert}[/]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        # Gather context
        task = progress.add_task("Gathering context from data sources...", total=None)
        
        gatherer = ContextGatherer(cfg, mock_data)
        context = gatherer.gather(alert, service)
        
        progress.update(task, description="Context gathered ✓")
        
        # Analyze with LLM
        progress.update(task, description="Analyzing with LLM (this may take a minute)...")
        
        analyzer = LLMAnalyzer(cfg)
        
        if no_llm:
            # Use rule-based analysis only
            analysis = analyzer._rule_based_analysis(context)
            report = analyzer._build_report(context, analysis)
        else:
            report = analyzer.analyze(context)
        
        progress.update(task, description="Analysis complete ✓")
    
    # Print report
    reporter = TerminalReporter(verbose=verbose)
    reporter.print_report(report)


@app.command()
def test():
    """
    Run with test data to verify setup.
    """
    console.print("[bold cyan]🧪 Running test analysis...[/]\n")
    
    # Run with default mock data
    analyze(
        alert="checkout-service 5xx spike",
        service="checkout-service",
        config=Path("config.yaml"),
        mock_data=Path(__file__).parent.parent / "data" / "mock" / "checkout-incident.json",
        verbose=False,
        no_llm=False
    )


@app.command()
def quick(
    alert: str = typer.Argument(..., help="Alert description"),
):
    """
    Quick analysis without LLM (faster, rule-based only).
    """
    analyze(
        alert=alert,
        service=None,
        config=Path("config.yaml"),
        mock_data=None,
        verbose=False,
        no_llm=True
    )


if __name__ == "__main__":
    app()
