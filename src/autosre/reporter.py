"""
SRE Agent - Terminal Reporter

Pretty-prints situation reports to terminal.
"""
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import HealthStatus, SituationReport


class TerminalReporter:
    """Outputs situation reports to terminal with rich formatting"""

    def __init__(self, verbose: bool = False):
        self.console = Console()
        self.verbose = verbose

    def print_report(self, report: SituationReport):
        """Print a complete situation report"""

        self.console.print()

        # Header
        self._print_header(report)

        # Situation Summary
        self._print_situation(report)

        # Root Cause Signals
        self._print_signals(report)

        # Recommended Actions
        self._print_actions(report)

        # Runbooks (if any)
        if report.runbooks:
            self._print_runbooks(report)

        # Footer
        self._print_footer(report)

        self.console.print()

    def _print_header(self, report: SituationReport):
        """Print incident header"""
        severity_colors = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "blue",
            "info": "white"
        }

        severity = report.alert.severity.value
        color = severity_colors.get(severity, "white")

        header = Text()
        header.append("🚨 INCIDENT: ", style="bold")
        header.append(report.alert.title, style=color)

        self.console.print(Panel(
            header,
            title="[bold white]SRE Agent Analysis[/]",
            subtitle=f"[dim]{report.alert.id}[/]",
            border_style="red" if severity in ["critical", "high"] else "yellow",
            box=box.DOUBLE
        ))

    def _print_situation(self, report: SituationReport):
        """Print situation summary"""

        # Metrics table
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("⏰ Started", report.alert.started_at.strftime("%H:%M:%S"))
        table.add_row("⏱️ Duration", f"{report.duration_minutes:.0f} minutes")

        if report.affected_customers_estimate:
            table.add_row("👥 Affected", f"~{report.affected_customers_estimate} customers")

        # Add metrics if available
        if report.raw_context and report.raw_context.prometheus:
            prom = report.raw_context.prometheus

            error_style = "red bold" if prom.error_rate.current > 5 else "yellow" if prom.error_rate.current > 1 else "green"
            table.add_row("📈 Error Rate", f"[{error_style}]{prom.error_rate.current}%[/] (baseline: {prom.error_rate.baseline}%)")

            latency_style = "red bold" if prom.latency_p99.current > 2000 else "yellow" if prom.latency_p99.current > 500 else "green"
            table.add_row("⚡ P99 Latency", f"[{latency_style}]{prom.latency_p99.current}ms[/] (baseline: {prom.latency_p99.baseline}ms)")

        self.console.print(Panel(table, title="[bold]📊 SITUATION[/]", border_style="blue"))

    def _print_signals(self, report: SituationReport):
        """Print root cause signals"""

        content = []

        # Likely root cause
        confidence_colors = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}
        conf_color = confidence_colors.get(report.confidence, "white")

        content.append(Text.assemble(
            ("🎯 LIKELY CAUSE: ", "bold"),
            (report.likely_root_cause or "Unknown", "bold white"),
            ("\n"),
            ("   Confidence: ", "dim"),
            (report.confidence, f"bold {conf_color}")
        ))
        content.append(Text(""))

        # Individual signals
        if report.root_cause_signals:
            content.append(Text("Signals:", style="bold"))

            for signal in report.root_cause_signals:
                icon = "⚠️" if signal.is_likely_cause else "ℹ️"
                conf_pct = int(signal.confidence * 100)

                signal_text = Text()
                signal_text.append(f"\n{icon} ", style="bold")
                signal_text.append(f"[{signal.source.upper()}] ", style="dim")
                signal_text.append(signal.description)
                signal_text.append(f" ({conf_pct}%)", style="dim")

                if signal.evidence:
                    for ev in signal.evidence[:2]:
                        signal_text.append(f"\n   • {ev}", style="dim italic")

                content.append(signal_text)

        # Check what's NOT the cause
        if report.raw_context:
            not_causes = []

            # Traffic OK?
            if report.raw_context.traffic:
                traffic = report.raw_context.traffic
                if not traffic.is_malicious and not traffic.is_ddos:
                    not_causes.append("Akamai/Traffic (normal)")

            # Infra OK?
            if report.raw_context.kubernetes:
                k8s = report.raw_context.kubernetes
                if not k8s.resource_pressure and all(p.status == "Running" for p in k8s.pods):
                    not_causes.append("OpenShift/Pods (healthy)")

            # Dependencies OK?
            if report.raw_context.dependencies:
                healthy_deps = [d for d in report.raw_context.dependencies if d.status == HealthStatus.HEALTHY]
                for dep in healthy_deps[:2]:
                    not_causes.append(f"{dep.name} (healthy)")

            if not_causes:
                content.append(Text(""))
                content.append(Text("Ruled Out:", style="bold green"))
                for nc in not_causes:
                    content.append(Text(f"  ✅ NOT {nc}", style="green"))

        combined = Text("\n").join(content)
        self.console.print(Panel(combined, title="[bold]🔍 ROOT CAUSE ANALYSIS[/]", border_style="yellow"))

    def _print_actions(self, report: SituationReport):
        """Print recommended actions"""

        if not report.recommended_actions:
            return

        table = Table(show_header=True, box=box.SIMPLE, expand=True)
        table.add_column("#", style="bold cyan", width=3)
        table.add_column("Action", style="white")
        table.add_column("Command", style="dim italic", max_width=50)

        for i, action in enumerate(report.recommended_actions, 1):
            cmd = action.command or "-"
            if len(cmd) > 47:
                cmd = cmd[:47] + "..."
            table.add_row(str(i), action.action, cmd)

        self.console.print(Panel(table, title="[bold]📋 RECOMMENDED ACTIONS[/]", border_style="green"))

    def _print_runbooks(self, report: SituationReport):
        """Print relevant runbooks"""

        content = Text()
        for rb in report.runbooks:
            content.append(f"📚 {rb.get('title', 'Runbook')}\n", style="bold")
            content.append(f"   {rb.get('link', '')}\n", style="blue underline")

        self.console.print(Panel(content, title="[bold]📚 RUNBOOKS[/]", border_style="magenta"))

    def _print_footer(self, report: SituationReport):
        """Print report footer"""

        footer = Text()
        footer.append("Generated by ", style="dim")
        footer.append("SRE Agent", style="bold cyan")
        footer.append(f" | {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}", style="dim")

        if self.verbose and report.analysis_reasoning:
            footer.append("\n\n")
            footer.append("Analysis Reasoning:\n", style="bold")
            footer.append(report.analysis_reasoning[:500], style="dim italic")

        self.console.print(Panel(footer, border_style="dim"))
