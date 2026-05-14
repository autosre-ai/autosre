"""SLO Reporter for AutoSRE V2."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, List, Optional
from .definition import SLODefinition
from .budget import ErrorBudgetTracker, BudgetStatus

class ReportFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"

@dataclass
class ReportConfig:
    format: ReportFormat = ReportFormat.MARKDOWN
    include_charts: bool = False
    include_recommendations: bool = True

@dataclass
class SLOReport:
    """SLO status report."""
    title: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    slo_statuses: List[BudgetStatus] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    
    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"Generated: {self.generated_at.isoformat()}", ""]
        lines.append("## Summary")
        lines.append(f"- Total SLOs: {len(self.slo_statuses)}")
        healthy = sum(1 for s in self.slo_statuses if s.is_healthy)
        critical = sum(1 for s in self.slo_statuses if s.is_critical)
        lines.append(f"- Healthy: {healthy}")
        lines.append(f"- Critical: {critical}")
        lines.append("")
        lines.append("## SLO Details")
        for status in self.slo_statuses:
            emoji = "✅" if status.is_healthy else "⚠️" if not status.is_critical else "🔴"
            lines.append(f"\n### {emoji} {status.slo_name}")
            lines.append(f"- Budget remaining: {status.remaining_percent:.1f}%")
            lines.append(f"- Burn rate (1h): {status.burn_rate_1h.rate:.2f}x")
            lines.append(f"- Health: {status.health.value}")
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        return {"title": self.title, "generated_at": self.generated_at.isoformat(),
            "period": {"start": self.period_start.isoformat(), "end": self.period_end.isoformat()},
            "slo_statuses": [s.to_dict() for s in self.slo_statuses], "summary": self.summary}

class SLOReporter:
    """Generates SLO reports."""
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self._tracker = ErrorBudgetTracker()
    
    def generate_report(self, slos: List[SLODefinition], current_values: dict[str, float],
                        title: str = "SLO Status Report") -> SLOReport:
        statuses = self._tracker.compare_slos(slos, current_values)
        return SLOReport(title=title, slo_statuses=statuses,
            summary={"total": len(statuses), "healthy": sum(1 for s in statuses if s.is_healthy),
                    "critical": sum(1 for s in statuses if s.is_critical)})
    
    def export(self, report: SLOReport, format: Optional[ReportFormat] = None) -> str:
        fmt = format or self.config.format
        if fmt == ReportFormat.MARKDOWN:
            return report.to_markdown()
        return str(report.to_dict())

# Convenience classes
class WeeklyReport(SLOReporter):
    def generate(self, slos: List[SLODefinition], values: dict[str, float]) -> SLOReport:
        return self.generate_report(slos, values, "Weekly SLO Report")

class MonthlyReport(SLOReporter):
    def generate(self, slos: List[SLODefinition], values: dict[str, float]) -> SLOReport:
        return self.generate_report(slos, values, "Monthly SLO Report")
