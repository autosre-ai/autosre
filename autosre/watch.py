"""
Continuous monitoring and auto-investigation for OpenSRE.

This module provides watch mode functionality that:
- Continuously monitors a Kubernetes namespace
- Detects issues from Prometheus alerts, pod health, and events
- Auto-investigates when issue threshold is reached
- Provides a rich live terminal dashboard
- Optionally sends notifications to Slack
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from opensre_core.adapters.kubernetes import KubernetesAdapter
from opensre_core.adapters.prometheus import PrometheusAdapter
from opensre_core.agents.orchestrator import InvestigationResult, Orchestrator


@dataclass
class WatchConfig:
    """Configuration for watch mode."""
    namespace: str = "default"
    interval_seconds: int = 60
    auto_investigate: bool = True
    alert_threshold: int = 3  # Number of issues before auto-investigating
    notify_slack: bool = False
    max_investigations_per_hour: int = 5  # Rate limit investigations
    cooldown_seconds: int = 300  # Cooldown after investigation


@dataclass
class Issue:
    """Represents a detected issue."""
    type: str  # alert, pod_unhealthy, high_restarts, critical_event
    severity: str  # critical, warning, info
    message: str
    source: str = ""  # e.g., pod name, alert name
    detected_at: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash((self.type, self.message))

    def __eq__(self, other):
        if not isinstance(other, Issue):
            return False
        return self.type == other.type and self.message == other.message


@dataclass
class WatchState:
    """Current state of the watcher."""
    last_check: Optional[datetime] = None
    issues_detected: list[Issue] = field(default_factory=list)
    active_investigation: Optional[str] = None
    investigations_today: int = 0
    investigations_this_hour: int = 0
    last_investigation_at: Optional[datetime] = None
    last_investigation_result: Optional[InvestigationResult] = None
    total_checks: int = 0
    total_issues_found: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

    def reset_hourly_count(self):
        """Reset hourly investigation count if hour changed."""
        now = datetime.now()
        if self.last_investigation_at:
            if now.hour != self.last_investigation_at.hour:
                self.investigations_this_hour = 0


class Watcher:
    """
    Continuous cluster monitoring with auto-investigation.

    Features:
    - Real-time monitoring of namespace health
    - Prometheus alert integration
    - Pod health checks (restarts, ready state)
    - Kubernetes event monitoring
    - Automatic investigation triggering
    - Rich terminal dashboard
    - Slack notifications
    """

    def __init__(self, config: WatchConfig):
        self.config = config
        self.state = WatchState()
        self.prometheus = PrometheusAdapter()
        self.kubernetes = KubernetesAdapter()
        self.orchestrator = Orchestrator()
        self.console = Console()
        self._stop_event = asyncio.Event()
        self._seen_issues: set[Issue] = set()

    async def start(self):
        """Start the watch loop."""
        self._print_banner()

        with Live(
            self._render_status(),
            refresh_per_second=1,
            console=self.console,
            transient=False,
        ) as live:
            while not self._stop_event.is_set():
                try:
                    # Reset hourly count if needed
                    self.state.reset_hourly_count()

                    # Check for issues
                    issues = await self._check_for_issues()
                    self.state.total_checks += 1

                    if issues:
                        self.state.issues_detected = issues
                        self.state.total_issues_found += len(issues)

                        # Check if we should auto-investigate
                        if self._should_investigate(issues):
                            await self._auto_investigate(issues)
                    else:
                        # Clear issues if none found
                        self.state.issues_detected = []

                    self.state.last_check = datetime.now()
                    self.state.last_error = None
                    live.update(self._render_status())

                    # Wait for next check interval
                    await asyncio.sleep(self.config.interval_seconds)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.state.error_count += 1
                    self.state.last_error = str(e)[:100]
                    self.console.print(f"[red]Error: {e}[/red]")
                    live.update(self._render_status())
                    await asyncio.sleep(5)  # Short wait on error

    def _print_banner(self):
        """Print startup banner."""
        self.console.print()
        self.console.print(Panel(
            f"[bold green]🔍 OpenSRE Watch Mode[/bold green]\n\n"
            f"   Namespace: [cyan]{self.config.namespace}[/cyan]\n"
            f"   Interval: [cyan]{self.config.interval_seconds}s[/cyan]\n"
            f"   Auto-investigate: [cyan]{self.config.auto_investigate}[/cyan]\n"
            f"   Alert threshold: [cyan]{self.config.alert_threshold}[/cyan]\n"
            f"   Slack notifications: [cyan]{self.config.notify_slack}[/cyan]\n\n"
            f"   Press Ctrl+C to stop",
            title="[bold]OpenSRE[/bold]",
            border_style="green",
        ))
        self.console.print()

    async def _check_for_issues(self) -> list[Issue]:
        """Check for issues in the namespace."""
        issues: list[Issue] = []

        # Check Prometheus alerts
        try:
            alerts = await self.prometheus.get_alerts()
            for alert in alerts:
                # Filter to namespace if possible
                if self.config.namespace != "all":
                    alert_namespace = alert.labels.get("namespace", "")
                    if alert_namespace and alert_namespace != self.config.namespace:
                        continue

                severity = self._map_alert_severity(alert)
                issues.append(Issue(
                    type="alert",
                    severity=severity,
                    message=alert.annotations.get("summary", alert.alert_name),
                    source=alert.alert_name,
                ))
        except Exception as e:
            # Prometheus might not be available - that's okay
            if "Connection refused" not in str(e):
                issues.append(Issue(
                    type="prometheus_error",
                    severity="warning",
                    message=f"Could not fetch Prometheus alerts: {str(e)[:50]}",
                ))

        # Check pod health
        try:
            pods = await self.kubernetes.get_pods(self.config.namespace)
            for pod in pods:
                if not pod.ready and pod.status not in ("Succeeded", "Completed"):
                    issues.append(Issue(
                        type="pod_unhealthy",
                        severity="warning",
                        message=f"Pod {pod.name} is not ready ({pod.status})",
                        source=pod.name,
                    ))

                if pod.restarts > 5:
                    severity = "critical" if pod.restarts > 10 else "warning"
                    issues.append(Issue(
                        type="high_restarts",
                        severity=severity,
                        message=f"Pod {pod.name} has {pod.restarts} restarts",
                        source=pod.name,
                    ))
        except Exception as e:
            issues.append(Issue(
                type="kubernetes_error",
                severity="critical",
                message=f"Could not fetch pods: {str(e)[:50]}",
            ))

        # Check recent events
        try:
            events = await self.kubernetes.get_events(self.config.namespace, minutes=5)
            critical_reasons = [
                "OOMKilled", "CrashLoopBackOff", "Failed", "FailedScheduling",
                "FailedMount", "FailedAttachVolume", "NodeNotReady", "Evicted"
            ]

            for event in events:
                if event.reason in critical_reasons:
                    severity = "critical" if event.reason in ("OOMKilled", "CrashLoopBackOff") else "warning"
                    issues.append(Issue(
                        type="critical_event",
                        severity=severity,
                        message=f"{event.reason}: {event.message[:100]}",
                        source=event.involved_object,
                    ))
        except Exception:
            # Events are best-effort
            pass

        # Deduplicate issues
        unique_issues = list(dict.fromkeys(issues))
        return unique_issues

    def _map_alert_severity(self, alert) -> str:
        """Map Prometheus alert severity to our severity levels."""
        labels = alert.labels
        severity = labels.get("severity", "warning").lower()

        if severity in ("critical", "page", "emergency"):
            return "critical"
        elif severity in ("warning", "warn"):
            return "warning"
        else:
            return "info"

    def _should_investigate(self, issues: list[Issue]) -> bool:
        """Determine if we should trigger an auto-investigation."""
        if not self.config.auto_investigate:
            return False

        # Check rate limit first (always enforced)
        if self.state.investigations_this_hour >= self.config.max_investigations_per_hour:
            return False

        # Check cooldown (always enforced)
        if self.state.last_investigation_at:
            elapsed = (datetime.now() - self.state.last_investigation_at).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return False

        # Check if any issues are critical - critical issues bypass threshold
        has_critical = any(i.severity == "critical" for i in issues)
        if has_critical:
            return True

        # Check issue threshold for non-critical issues
        if len(issues) < self.config.alert_threshold:
            return False

        return True

    async def _auto_investigate(self, issues: list[Issue]):
        """Run auto-investigation on detected issues."""
        self.state.active_investigation = "Starting..."

        # Build issue description
        critical_issues = [i for i in issues if i.severity == "critical"]
        priority_issues = critical_issues if critical_issues else issues[:3]
        issue_summary = "; ".join([i.message[:50] for i in priority_issues])

        try:
            self.state.active_investigation = "Running investigation..."

            result = await self.orchestrator.investigate(
                issue=f"Auto-detected issues: {issue_summary}",
                namespace=self.config.namespace,
            )

            # Update state
            self.state.investigations_today += 1
            self.state.investigations_this_hour += 1
            self.state.last_investigation_at = datetime.now()
            self.state.last_investigation_result = result

            # Format result summary
            if result.root_cause:
                self.state.active_investigation = f"✓ {result.root_cause[:60]}"
            else:
                self.state.active_investigation = "✓ Investigation complete (no root cause found)"

            # Send Slack notification if enabled
            if self.config.notify_slack:
                await self._notify_slack(result)

        except Exception as e:
            self.state.active_investigation = f"✗ Error: {str(e)[:40]}"

    async def _notify_slack(self, result: InvestigationResult):
        """Send notification to Slack."""
        try:
            from opensre_core.adapters.slack import SlackAdapter
            slack = SlackAdapter()
            await slack.post_investigation(result)
        except Exception as e:
            # Slack notification is best-effort
            self.console.print(f"[yellow]Slack notification failed: {e}[/yellow]")

    def _render_status(self) -> Panel:
        """Render current status panel for Rich Live display."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim", width=24)
        table.add_column("Value")

        # Status info
        last_check_str = self.state.last_check.strftime("%H:%M:%S") if self.state.last_check else "Never"
        table.add_row("Last Check:", last_check_str)

        # Issues count with color
        issue_count = len(self.state.issues_detected)
        issue_color = "green" if issue_count == 0 else ("yellow" if issue_count < 3 else "red")
        table.add_row("Issues Detected:", f"[{issue_color}]{issue_count}[/{issue_color}]")

        # Investigation status
        investigation_status = self.state.active_investigation or "[dim]None[/dim]"
        table.add_row("Last Investigation:", investigation_status)

        # Statistics
        table.add_row("Investigations Today:", str(self.state.investigations_today))
        table.add_row("Total Checks:", str(self.state.total_checks))

        # Error status
        if self.state.last_error:
            table.add_row("Last Error:", f"[red]{self.state.last_error}[/red]")

        # Show recent issues
        if self.state.issues_detected:
            table.add_row("", "")
            table.add_row("[bold]Recent Issues:[/bold]", "")

            for issue in self.state.issues_detected[:7]:
                severity_colors = {
                    "critical": "red",
                    "warning": "yellow",
                    "info": "blue"
                }
                color = severity_colors.get(issue.severity, "white")
                icon = "●" if issue.severity == "critical" else "○"

                message = issue.message[:55]
                if len(issue.message) > 55:
                    message += "..."

                table.add_row(
                    f"  [{color}]{icon}[/{color}]",
                    f"[{color}]{message}[/{color}]"
                )

            if len(self.state.issues_detected) > 7:
                remaining = len(self.state.issues_detected) - 7
                table.add_row("", f"[dim]... and {remaining} more[/dim]")

        # Show last investigation result summary
        if self.state.last_investigation_result and self.state.last_investigation_result.actions:
            table.add_row("", "")
            table.add_row("[bold]Suggested Actions:[/bold]", "")
            for action in self.state.last_investigation_result.actions[:3]:
                risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
                    action.risk.value.lower() if hasattr(action.risk, 'value') else str(action.risk).lower(),
                    "white"
                )
                desc = action.description[:50]
                table.add_row(f"  [{risk_color}]→[/{risk_color}]", desc)

        # Build title with status indicator
        status_icon = "🟢" if not self.state.issues_detected else ("🟡" if len(self.state.issues_detected) < 3 else "🔴")
        title = f"{status_icon} [bold]OpenSRE Watch - {self.config.namespace}[/bold]"

        border_color = "green" if not self.state.issues_detected else ("yellow" if len(self.state.issues_detected) < 3 else "red")

        return Panel(
            table,
            title=title,
            border_style=border_color,
            subtitle=f"[dim]Interval: {self.config.interval_seconds}s | Auto: {'on' if self.config.auto_investigate else 'off'}[/dim]"
        )

    def stop(self):
        """Stop the watch loop."""
        self._stop_event.set()

    async def check_once(self) -> list[Issue]:
        """Run a single check and return issues (useful for testing)."""
        return await self._check_for_issues()
