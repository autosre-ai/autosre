"""
Terminal Reporter

Rich terminal output for investigation progress and results.
"""
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..agents.state_machine import InvestigationContext, InvestigationState as InvestigationStateMachine
from ..agents.synthesizer import Synthesis


class TerminalReporter:
    """
    Reports investigation progress and results to the terminal.
    
    Uses Rich for beautiful terminal output.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def report_start(self, alert: dict):
        """Report investigation start."""
        self.console.print(Panel(
            f"[bold blue]Starting Investigation[/bold blue]\n\n"
            f"Alert: {alert.get('title', 'Unknown')}\n"
            f"Service: {alert.get('service', 'Unknown')}\n"
            f"Severity: {alert.get('severity', 'Unknown')}",
            title="🔍 AutoSRE",
        ))
    
    def report_state_change(self, old_state: InvestigationStateMachine, new_state: InvestigationStateMachine):
        """Report state transition."""
        state_emoji = {
            InvestigationStateMachine.PENDING: "⏳",
            InvestigationStateMachine.GATHERING: "📊",
            InvestigationStateMachine.ANALYZING: "🔬",
            InvestigationStateMachine.HYPOTHESIZING: "💡",
            InvestigationStateMachine.VALIDATING: "✅",
            InvestigationStateMachine.SYNTHESIZING: "🧩",
            InvestigationStateMachine.WRITING: "📝",
            InvestigationStateMachine.COMPLETED: "✨",
            InvestigationStateMachine.FAILED: "❌",
            InvestigationStateMachine.BLOCKED: "🚫",
        }
        
        emoji = state_emoji.get(new_state, "➡️")
        self.console.print(f"{emoji} {old_state.name} → [bold]{new_state.name}[/bold]")
    
    def report_finding(self, category: str, finding: str):
        """Report a finding during investigation."""
        self.console.print(f"  • [cyan]{category}[/cyan]: {finding}")
    
    def report_hypothesis(self, hypothesis: str, confidence: float):
        """Report a hypothesis."""
        bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
        self.console.print(f"  💡 {hypothesis}")
        self.console.print(f"     Confidence: [{bar}] {confidence:.0%}")
    
    def report_synthesis(self, synthesis: Synthesis):
        """Report synthesis results."""
        self.console.print("\n")
        self.console.print(Panel(
            synthesis.summary,
            title="🧩 Synthesis",
        ))
        
        if synthesis.hypotheses:
            table = Table(title="Hypotheses")
            table.add_column("Hypothesis", style="cyan")
            table.add_column("Confidence", style="green")
            table.add_column("Evidence", style="dim")
            
            for h in synthesis.hypotheses:
                table.add_row(
                    h.description,
                    f"{h.confidence:.0%}",
                    ", ".join(h.evidence[:2]) + ("..." if len(h.evidence) > 2 else ""),
                )
            
            self.console.print(table)
    
    def report_completion(self, context: InvestigationContext):
        """Report investigation completion."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold green]Investigation Complete[/bold green]\n\n"
            f"Root Cause: {context.root_cause or 'Unknown'}\n\n"
            f"Summary: {context.summary or 'No summary available'}",
            title="✨ Results",
        ))
        
        if context.recommendations:
            self.console.print("\n[bold]Recommendations:[/bold]")
            for rec in context.recommendations:
                self.console.print(f"  • {rec}")
    
    def create_progress(self) -> Progress:
        """Create a progress display."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
