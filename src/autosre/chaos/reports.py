"""
Chaos Experiment Reports and Analytics

Provides report generation, metrics aggregation, and
trend analysis for chaos experiments.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportFormat(str, Enum):
    """Output formats for reports."""
    
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    SLACK = "slack"


@dataclass
class ExperimentMetrics:
    """Metrics collected during a chaos experiment."""
    
    experiment_id: str
    experiment_name: str
    
    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Impact
    pods_affected: int = 0
    services_affected: int = 0
    requests_impacted: int = 0
    
    # Availability
    availability_before: float = 100.0
    availability_during: float = 100.0
    availability_after: float = 100.0
    availability_recovered: bool = True
    recovery_time_seconds: float = 0.0
    
    # Latency (milliseconds)
    latency_p50_before: float = 0.0
    latency_p50_during: float = 0.0
    latency_p50_after: float = 0.0
    latency_p99_before: float = 0.0
    latency_p99_during: float = 0.0
    latency_p99_after: float = 0.0
    
    # Error rates
    error_rate_before: float = 0.0
    error_rate_during: float = 0.0
    error_rate_after: float = 0.0
    
    # SLO impact
    slo_violations: list[str] = field(default_factory=list)
    
    # Raw metrics data
    time_series: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)
    
    def calculate_latency_impact(self) -> dict[str, float]:
        """Calculate latency impact percentages."""
        return {
            "p50_increase_percent": self._percent_change(
                self.latency_p50_before, self.latency_p50_during
            ),
            "p99_increase_percent": self._percent_change(
                self.latency_p99_before, self.latency_p99_during
            ),
            "p50_recovery_percent": self._percent_change(
                self.latency_p50_during, self.latency_p50_after
            ),
            "p99_recovery_percent": self._percent_change(
                self.latency_p99_during, self.latency_p99_after
            ),
        }
    
    def calculate_availability_impact(self) -> dict[str, float]:
        """Calculate availability impact."""
        return {
            "availability_drop": self.availability_before - self.availability_during,
            "availability_recovered_to": self.availability_after,
            "recovery_time_seconds": self.recovery_time_seconds,
        }
    
    def _percent_change(self, before: float, after: float) -> float:
        """Calculate percentage change."""
        if before == 0:
            return 0.0 if after == 0 else 100.0
        return ((after - before) / before) * 100


@dataclass
class ImpactAnalysis:
    """Analysis of chaos experiment impact."""
    
    # Overall assessment
    severity: str = "low"  # low, medium, high, critical
    summary: str = ""
    
    # Categorized findings
    positive_findings: list[str] = field(default_factory=list)
    negative_findings: list[str] = field(default_factory=list)
    neutral_findings: list[str] = field(default_factory=list)
    
    # System behavior
    graceful_degradation: bool = True
    fast_recovery: bool = True
    cascading_failures: bool = False
    
    # SLO compliance
    slo_maintained: bool = True
    slo_violations: list[str] = field(default_factory=list)
    
    # Action items
    action_items: list[dict[str, Any]] = field(default_factory=list)
    
    def add_action_item(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        assignee: Optional[str] = None,
    ) -> None:
        """Add an action item."""
        self.action_items.append({
            "title": title,
            "description": description,
            "priority": priority,
            "assignee": assignee,
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
        })


@dataclass
class ResilienceScore:
    """Calculated resilience score for a service or system."""
    
    overall_score: float = 0.0  # 0-100
    
    # Component scores
    availability_score: float = 0.0
    recovery_score: float = 0.0
    degradation_score: float = 0.0
    
    # Breakdown
    experiments_passed: int = 0
    experiments_failed: int = 0
    experiments_total: int = 0
    
    # Trend
    trend: str = "stable"  # improving, stable, declining
    trend_percentage: float = 0.0
    
    # Historical
    previous_score: Optional[float] = None
    score_history: list[tuple[datetime, float]] = field(default_factory=list)
    
    def calculate(
        self,
        metrics_list: list[ExperimentMetrics],
    ) -> float:
        """Calculate overall resilience score from experiment metrics."""
        if not metrics_list:
            return 0.0
        
        # Availability score (40% weight)
        avg_availability = statistics.mean(
            m.availability_during for m in metrics_list
        )
        self.availability_score = avg_availability
        
        # Recovery score (30% weight)
        recovery_times = [m.recovery_time_seconds for m in metrics_list]
        avg_recovery = statistics.mean(recovery_times) if recovery_times else 0
        # Score: 100 if < 30s, 0 if > 300s, linear in between
        if avg_recovery <= 30:
            self.recovery_score = 100.0
        elif avg_recovery >= 300:
            self.recovery_score = 0.0
        else:
            self.recovery_score = 100 - ((avg_recovery - 30) / 270 * 100)
        
        # Degradation score (30% weight)
        # Based on latency increase during experiments
        latency_increases = [
            m.calculate_latency_impact()["p99_increase_percent"]
            for m in metrics_list
        ]
        avg_latency_increase = statistics.mean(latency_increases) if latency_increases else 0
        # Score: 100 if < 50% increase, 0 if > 500% increase
        if avg_latency_increase <= 50:
            self.degradation_score = 100.0
        elif avg_latency_increase >= 500:
            self.degradation_score = 0.0
        else:
            self.degradation_score = 100 - ((avg_latency_increase - 50) / 450 * 100)
        
        # Calculate overall score
        self.overall_score = (
            self.availability_score * 0.4 +
            self.recovery_score * 0.3 +
            self.degradation_score * 0.3
        )
        
        # Calculate pass/fail counts
        self.experiments_total = len(metrics_list)
        self.experiments_passed = sum(
            1 for m in metrics_list
            if m.availability_recovered and m.recovery_time_seconds < 120
        )
        self.experiments_failed = self.experiments_total - self.experiments_passed
        
        # Calculate trend
        if self.previous_score is not None:
            diff = self.overall_score - self.previous_score
            self.trend_percentage = diff
            if diff > 5:
                self.trend = "improving"
            elif diff < -5:
                self.trend = "declining"
            else:
                self.trend = "stable"
        
        # Add to history
        self.score_history.append((datetime.utcnow(), self.overall_score))
        
        return self.overall_score


@dataclass
class TrendAnalysis:
    """Trend analysis across multiple chaos experiments."""
    
    # Time range
    start_date: datetime = field(default_factory=lambda: datetime.utcnow() - timedelta(days=30))
    end_date: datetime = field(default_factory=datetime.utcnow)
    
    # Experiment counts
    total_experiments: int = 0
    successful_experiments: int = 0
    failed_experiments: int = 0
    
    # Trends
    resilience_trend: str = "stable"
    availability_trend: str = "stable"
    recovery_time_trend: str = "stable"
    
    # Statistics
    avg_availability: float = 0.0
    avg_recovery_time: float = 0.0
    avg_latency_increase: float = 0.0
    
    # Most common issues
    common_issues: list[dict[str, Any]] = field(default_factory=list)
    
    # Improvements observed
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    
    def analyze(
        self,
        metrics_list: list[ExperimentMetrics],
    ) -> None:
        """Analyze trends from a list of experiment metrics."""
        if not metrics_list:
            return
        
        self.total_experiments = len(metrics_list)
        
        # Sort by time
        sorted_metrics = sorted(metrics_list, key=lambda m: m.start_time)
        
        # Calculate success rate
        self.successful_experiments = sum(
            1 for m in metrics_list if m.availability_recovered
        )
        self.failed_experiments = self.total_experiments - self.successful_experiments
        
        # Calculate averages
        self.avg_availability = statistics.mean(
            m.availability_during for m in metrics_list
        )
        recovery_times = [m.recovery_time_seconds for m in metrics_list if m.recovery_time_seconds > 0]
        self.avg_recovery_time = statistics.mean(recovery_times) if recovery_times else 0
        
        latency_increases = [
            m.calculate_latency_impact()["p99_increase_percent"]
            for m in metrics_list
        ]
        self.avg_latency_increase = statistics.mean(latency_increases) if latency_increases else 0
        
        # Calculate trends (compare first half to second half)
        mid = len(sorted_metrics) // 2
        if mid > 0:
            first_half = sorted_metrics[:mid]
            second_half = sorted_metrics[mid:]
            
            first_avail = statistics.mean(m.availability_during for m in first_half)
            second_avail = statistics.mean(m.availability_during for m in second_half)
            
            if second_avail > first_avail + 2:
                self.availability_trend = "improving"
                self.improvements.append(
                    f"Availability improved from {first_avail:.1f}% to {second_avail:.1f}%"
                )
            elif second_avail < first_avail - 2:
                self.availability_trend = "declining"
                self.regressions.append(
                    f"Availability declined from {first_avail:.1f}% to {second_avail:.1f}%"
                )
            
            first_recovery = statistics.mean(
                m.recovery_time_seconds for m in first_half
                if m.recovery_time_seconds > 0
            ) if any(m.recovery_time_seconds > 0 for m in first_half) else 0
            second_recovery = statistics.mean(
                m.recovery_time_seconds for m in second_half
                if m.recovery_time_seconds > 0
            ) if any(m.recovery_time_seconds > 0 for m in second_half) else 0
            
            if second_recovery < first_recovery * 0.8 and first_recovery > 0:
                self.recovery_time_trend = "improving"
                self.improvements.append(
                    f"Recovery time improved from {first_recovery:.1f}s to {second_recovery:.1f}s"
                )
            elif second_recovery > first_recovery * 1.2 and first_recovery > 0:
                self.recovery_time_trend = "declining"
                self.regressions.append(
                    f"Recovery time increased from {first_recovery:.1f}s to {second_recovery:.1f}s"
                )


class ChaosReport(BaseModel):
    """A comprehensive chaos experiment report."""
    
    # Metadata
    id: str
    title: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "system"
    
    # Time range
    period_start: datetime
    period_end: datetime
    
    # Executive summary
    executive_summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    
    # Resilience score
    resilience_score: float = 0.0
    resilience_grade: str = "B"  # A, B, C, D, F
    
    # Experiments
    experiments_summary: dict[str, Any] = Field(default_factory=dict)
    experiment_details: list[dict[str, Any]] = Field(default_factory=list)
    
    # Impact analysis
    impact_analysis: dict[str, Any] = Field(default_factory=dict)
    
    # Trends
    trends: dict[str, Any] = Field(default_factory=dict)
    
    # Action items
    action_items: list[dict[str, Any]] = Field(default_factory=list)
    
    # Appendix
    raw_data: dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    def set_grade(self) -> str:
        """Set resilience grade based on score."""
        if self.resilience_score >= 90:
            self.resilience_grade = "A"
        elif self.resilience_score >= 80:
            self.resilience_grade = "B"
        elif self.resilience_score >= 70:
            self.resilience_grade = "C"
        elif self.resilience_score >= 60:
            self.resilience_grade = "D"
        else:
            self.resilience_grade = "F"
        return self.resilience_grade


class ReportGenerator:
    """Generates chaos experiment reports."""
    
    def __init__(
        self,
        template_dir: Optional[str] = None,
    ):
        self.template_dir = template_dir
    
    def generate(
        self,
        experiments: list[Any],  # List of ChaosExperiment
        metrics: list[ExperimentMetrics],
        period_start: datetime,
        period_end: datetime,
        title: str = "Chaos Engineering Report",
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> ChaosReport:
        """Generate a comprehensive chaos report."""
        import uuid
        
        report = ChaosReport(
            id=str(uuid.uuid4()),
            title=title,
            period_start=period_start,
            period_end=period_end,
        )
        
        # Calculate resilience score
        score = ResilienceScore()
        report.resilience_score = score.calculate(metrics)
        report.set_grade()
        
        # Generate experiments summary
        report.experiments_summary = {
            "total": len(experiments),
            "successful": sum(
                1 for e in experiments
                if getattr(e, "state", None) == "completed"
            ),
            "failed": sum(
                1 for e in experiments
                if getattr(e, "state", None) == "failed"
            ),
            "by_type": self._count_by_type(experiments),
        }
        
        # Generate experiment details
        for exp in experiments:
            exp_metrics = next(
                (m for m in metrics if m.experiment_id == getattr(exp, "id", "")),
                None,
            )
            report.experiment_details.append({
                "id": getattr(exp, "id", ""),
                "name": getattr(exp, "name", ""),
                "type": getattr(getattr(exp, "config", None), "experiment_type", "unknown"),
                "state": getattr(exp, "state", "unknown"),
                "metrics": self._metrics_summary(exp_metrics) if exp_metrics else {},
            })
        
        # Generate impact analysis
        impact = ImpactAnalysis()
        self._analyze_impact(metrics, impact)
        report.impact_analysis = {
            "severity": impact.severity,
            "summary": impact.summary,
            "positive_findings": impact.positive_findings,
            "negative_findings": impact.negative_findings,
            "graceful_degradation": impact.graceful_degradation,
            "fast_recovery": impact.fast_recovery,
            "slo_maintained": impact.slo_maintained,
        }
        
        # Generate trends
        trend_analysis = TrendAnalysis(start_date=period_start, end_date=period_end)
        trend_analysis.analyze(metrics)
        report.trends = {
            "resilience_trend": trend_analysis.resilience_trend,
            "availability_trend": trend_analysis.availability_trend,
            "recovery_time_trend": trend_analysis.recovery_time_trend,
            "improvements": trend_analysis.improvements,
            "regressions": trend_analysis.regressions,
        }
        
        # Generate executive summary
        report.executive_summary = self._generate_executive_summary(report)
        
        # Generate key findings
        report.key_findings = self._extract_key_findings(report, metrics)
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report, impact)
        
        # Copy action items
        report.action_items = impact.action_items
        
        return report
    
    def export(
        self,
        report: ChaosReport,
        format: ReportFormat = ReportFormat.MARKDOWN,
        output_path: Optional[str] = None,
    ) -> str:
        """Export report to specified format."""
        if format == ReportFormat.MARKDOWN:
            content = self._to_markdown(report)
        elif format == ReportFormat.JSON:
            content = report.model_dump_json(indent=2)
        elif format == ReportFormat.SLACK:
            content = self._to_slack(report)
        elif format == ReportFormat.HTML:
            content = self._to_html(report)
        else:
            content = self._to_markdown(report)
        
        if output_path:
            with open(output_path, "w") as f:
                f.write(content)
        
        return content
    
    def _count_by_type(self, experiments: list[Any]) -> dict[str, int]:
        """Count experiments by type."""
        counts: dict[str, int] = {}
        for exp in experiments:
            exp_type = str(getattr(
                getattr(exp, "config", None),
                "experiment_type",
                "unknown",
            ))
            counts[exp_type] = counts.get(exp_type, 0) + 1
        return counts
    
    def _metrics_summary(self, metrics: ExperimentMetrics) -> dict[str, Any]:
        """Generate metrics summary."""
        return {
            "duration_seconds": metrics.duration_seconds,
            "availability_during": metrics.availability_during,
            "recovery_time_seconds": metrics.recovery_time_seconds,
            "latency_impact": metrics.calculate_latency_impact(),
        }
    
    def _analyze_impact(
        self,
        metrics: list[ExperimentMetrics],
        impact: ImpactAnalysis,
    ) -> None:
        """Analyze overall impact from metrics."""
        if not metrics:
            return
        
        # Check graceful degradation
        degraded_gracefully = all(
            m.availability_during >= 90 or m.error_rate_during < 10
            for m in metrics
        )
        impact.graceful_degradation = degraded_gracefully
        if degraded_gracefully:
            impact.positive_findings.append(
                "System maintained graceful degradation during all experiments"
            )
        else:
            impact.negative_findings.append(
                "Some experiments caused significant service degradation"
            )
        
        # Check fast recovery
        fast_recovery = all(
            m.recovery_time_seconds < 60
            for m in metrics
            if m.recovery_time_seconds > 0
        )
        impact.fast_recovery = fast_recovery
        if fast_recovery:
            impact.positive_findings.append(
                "All services recovered within 60 seconds"
            )
        else:
            slow_recoveries = [
                m.experiment_name for m in metrics
                if m.recovery_time_seconds >= 60
            ]
            impact.negative_findings.append(
                f"Slow recovery observed: {', '.join(slow_recoveries)}"
            )
            impact.add_action_item(
                title="Improve recovery time",
                description=f"Services {', '.join(slow_recoveries)} had slow recovery",
                priority="high",
            )
        
        # Check SLO compliance
        all_slo_violations = []
        for m in metrics:
            all_slo_violations.extend(m.slo_violations)
        
        impact.slo_maintained = len(all_slo_violations) == 0
        impact.slo_violations = all_slo_violations
        if all_slo_violations:
            impact.negative_findings.append(
                f"SLO violations detected: {', '.join(set(all_slo_violations))}"
            )
        
        # Determine overall severity
        negative_count = len(impact.negative_findings)
        if negative_count >= 3 or not impact.slo_maintained:
            impact.severity = "high"
        elif negative_count >= 1:
            impact.severity = "medium"
        else:
            impact.severity = "low"
        
        # Generate summary
        impact.summary = (
            f"Overall impact severity: {impact.severity}. "
            f"{len(impact.positive_findings)} positive findings, "
            f"{len(impact.negative_findings)} areas for improvement."
        )
    
    def _generate_executive_summary(self, report: ChaosReport) -> str:
        """Generate executive summary."""
        total = report.experiments_summary.get("total", 0)
        successful = report.experiments_summary.get("successful", 0)
        
        summary = f"""
During the period from {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}, 
{total} chaos experiments were conducted to evaluate system resilience.

**Overall Resilience Score: {report.resilience_score:.1f}/100 (Grade: {report.resilience_grade})**

{successful} out of {total} experiments completed successfully ({(successful/total*100) if total > 0 else 0:.1f}% success rate).

Key Trends:
- Availability: {report.trends.get('availability_trend', 'stable')}
- Recovery Time: {report.trends.get('recovery_time_trend', 'stable')}

{len(report.action_items)} action items were identified for follow-up.
""".strip()
        
        return summary
    
    def _extract_key_findings(
        self,
        report: ChaosReport,
        metrics: list[ExperimentMetrics],
    ) -> list[str]:
        """Extract key findings."""
        findings = []
        
        # Add impact findings
        if report.impact_analysis.get("graceful_degradation"):
            findings.append("✅ System demonstrates graceful degradation under failure conditions")
        else:
            findings.append("⚠️ Graceful degradation needs improvement")
        
        if report.impact_analysis.get("fast_recovery"):
            findings.append("✅ Recovery times are within acceptable limits")
        else:
            findings.append("⚠️ Some services have slow recovery times")
        
        if report.impact_analysis.get("slo_maintained"):
            findings.append("✅ All SLOs were maintained during experiments")
        else:
            findings.append("❌ SLO violations detected during experiments")
        
        # Add trend findings
        if report.trends.get("resilience_trend") == "improving":
            findings.append("📈 Overall resilience is trending upward")
        elif report.trends.get("resilience_trend") == "declining":
            findings.append("📉 Overall resilience is trending downward - attention needed")
        
        return findings
    
    def _generate_recommendations(
        self,
        report: ChaosReport,
        impact: ImpactAnalysis,
    ) -> list[str]:
        """Generate recommendations."""
        recommendations = []
        
        if not impact.graceful_degradation:
            recommendations.append(
                "Implement circuit breakers and rate limiting to improve graceful degradation"
            )
        
        if not impact.fast_recovery:
            recommendations.append(
                "Review and optimize health checks and pod restart policies"
            )
        
        if not impact.slo_maintained:
            recommendations.append(
                "Review SLO budgets and implement error budget alerting"
            )
        
        if report.resilience_score < 70:
            recommendations.append(
                "Schedule focused resilience improvement sprint"
            )
        
        if report.trends.get("resilience_trend") == "declining":
            recommendations.append(
                "Investigate recent changes that may have impacted resilience"
            )
        
        # Add regular chaos recommendations
        recommendations.append(
            "Continue regular chaos experiments to maintain and improve resilience"
        )
        
        return recommendations
    
    def _to_markdown(self, report: ChaosReport) -> str:
        """Convert report to Markdown format."""
        md = f"""# {report.title}

**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Period:** {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}

## Executive Summary

{report.executive_summary}

## Resilience Score

| Metric | Value |
|--------|-------|
| Overall Score | {report.resilience_score:.1f}/100 |
| Grade | {report.resilience_grade} |

## Key Findings

"""
        for finding in report.key_findings:
            md += f"- {finding}\n"
        
        md += f"""
## Experiments Summary

| Metric | Value |
|--------|-------|
| Total Experiments | {report.experiments_summary.get('total', 0)} |
| Successful | {report.experiments_summary.get('successful', 0)} |
| Failed | {report.experiments_summary.get('failed', 0)} |

### By Type

"""
        for exp_type, count in report.experiments_summary.get("by_type", {}).items():
            md += f"- {exp_type}: {count}\n"
        
        md += """
## Recommendations

"""
        for i, rec in enumerate(report.recommendations, 1):
            md += f"{i}. {rec}\n"
        
        if report.action_items:
            md += """
## Action Items

| Priority | Title | Description |
|----------|-------|-------------|
"""
            for item in report.action_items:
                md += f"| {item.get('priority', 'medium')} | {item.get('title', '')} | {item.get('description', '')} |\n"
        
        return md
    
    def _to_slack(self, report: ChaosReport) -> str:
        """Convert report to Slack message format."""
        grade_emoji = {
            "A": "🏆",
            "B": "✅",
            "C": "⚠️",
            "D": "🔶",
            "F": "❌",
        }
        
        emoji = grade_emoji.get(report.resilience_grade, "📊")
        
        slack = f"""{emoji} *{report.title}*

*Resilience Score:* {report.resilience_score:.1f}/100 (Grade: {report.resilience_grade})
*Period:* {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}

*Experiments:* {report.experiments_summary.get('total', 0)} total, {report.experiments_summary.get('successful', 0)} successful

*Key Findings:*
"""
        for finding in report.key_findings[:5]:  # Limit for Slack
            slack += f"• {finding}\n"
        
        if report.action_items:
            slack += f"\n*Action Items:* {len(report.action_items)} items identified"
        
        return slack
    
    def _to_html(self, report: ChaosReport) -> str:
        """Convert report to HTML format."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{report.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        .score {{ font-size: 48px; font-weight: bold; color: #2196F3; }}
        .grade {{ font-size: 24px; padding: 10px 20px; border-radius: 5px; }}
        .grade-A {{ background: #4CAF50; color: white; }}
        .grade-B {{ background: #8BC34A; color: white; }}
        .grade-C {{ background: #FFC107; color: black; }}
        .grade-D {{ background: #FF9800; color: white; }}
        .grade-F {{ background: #F44336; color: white; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f5f5f5; }}
        .finding {{ padding: 10px; margin: 5px 0; border-left: 3px solid #2196F3; background: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <p>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    <p>Period: {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}</p>
    
    <h2>Resilience Score</h2>
    <div class="score">{report.resilience_score:.1f}</div>
    <span class="grade grade-{report.resilience_grade}">Grade: {report.resilience_grade}</span>
    
    <h2>Executive Summary</h2>
    <p>{report.executive_summary}</p>
    
    <h2>Key Findings</h2>
"""
        for finding in report.key_findings:
            html += f'    <div class="finding">{finding}</div>\n'
        
        html += """
    <h2>Recommendations</h2>
    <ol>
"""
        for rec in report.recommendations:
            html += f"        <li>{rec}</li>\n"
        
        html += """    </ol>
</body>
</html>"""
        
        return html
