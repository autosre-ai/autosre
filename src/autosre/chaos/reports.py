"""
Report Generator for chaos experiments.

Generates detailed reports from chaos experiment results.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Experiment,
    ExperimentResult,
    GameDay,
    ResilienceScore,
)

logger = get_logger(__name__)


class ReportGenerator:
    """
    Generates reports from chaos experiments.
    
    Features:
    - Experiment reports
    - Game day reports
    - Trend reports
    - Executive summaries
    
    Example:
        generator = ReportGenerator()
        
        report = generator.generate_experiment_report(experiment)
        markdown = generator.to_markdown(report)
    """
    
    def __init__(self):
        pass
    
    def generate_experiment_report(
        self,
        experiment: Experiment,
    ) -> dict[str, Any]:
        """
        Generate report for a single experiment.
        
        Args:
            experiment: Experiment to report on
            
        Returns:
            Report data
        """
        result = experiment.result
        
        report = {
            "type": "experiment",
            "generated_at": datetime.utcnow().isoformat(),
            "experiment": {
                "id": str(experiment.id),
                "name": experiment.name,
                "description": experiment.description,
                "status": experiment.status.value,
                "owner": experiment.owner,
                "team": experiment.team,
                "tags": experiment.tags,
            },
            "execution": {
                "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
                "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
                "duration_seconds": (
                    (experiment.completed_at - experiment.started_at).total_seconds()
                    if experiment.started_at and experiment.completed_at else None
                ),
                "dry_run": experiment.dry_run,
            },
            "faults": [
                {
                    "type": f.type.value,
                    "target": f"{f.target.type.value}/{f.target.name}",
                    "severity": f.severity.value,
                    "duration_seconds": f.duration_seconds,
                    "parameters": f.parameters,
                }
                for f in experiment.faults
            ],
            "steady_state": [
                {
                    "name": h.name,
                    "probe_type": h.probe_type,
                    "endpoint": h.endpoint,
                }
                for h in experiment.steady_state
            ],
        }
        
        if result:
            report["result"] = {
                "success": result.success,
                "message": result.message,
                "steady_state": {
                    "met_before": result.steady_state_met_before,
                    "met_during": result.steady_state_met_during,
                    "met_after": result.steady_state_met_after,
                },
                "errors": result.errors,
                "was_rolled_back": result.was_rolled_back,
                "rollback_success": result.rollback_success,
                "duration_seconds": result.duration_seconds,
                "timeline": result.timeline,
                "impact_metrics": result.impact_metrics,
            }
        
        return report
    
    def generate_gameday_report(
        self,
        game_day: GameDay,
    ) -> dict[str, Any]:
        """
        Generate report for a game day.
        
        Args:
            game_day: Game day to report on
            
        Returns:
            Report data
        """
        report = {
            "type": "gameday",
            "generated_at": datetime.utcnow().isoformat(),
            "game_day": {
                "id": str(game_day.id),
                "name": game_day.name,
                "description": game_day.description,
                "status": game_day.status.value,
                "facilitator": game_day.facilitator,
                "participants": game_day.participants,
            },
            "execution": {
                "scheduled_date": game_day.scheduled_date.isoformat(),
                "started_at": game_day.started_at.isoformat() if game_day.started_at else None,
                "completed_at": game_day.completed_at.isoformat() if game_day.completed_at else None,
                "estimated_duration_hours": game_day.estimated_duration_hours,
            },
            "summary": {
                "total_experiments": len(game_day.experiments),
                "completed_experiments": game_day.completed_experiments,
                "successful_experiments": game_day.successful_experiments,
                "success_rate": (
                    game_day.successful_experiments / len(game_day.experiments) * 100
                    if game_day.experiments else 0
                ),
                "overall_success": game_day.overall_success,
            },
            "experiments": [
                self.generate_experiment_report(exp)
                for exp in game_day.experiments
            ],
            "findings": game_day.findings,
            "action_items": game_day.action_items,
        }
        
        return report
    
    def generate_trend_report(
        self,
        scores: list[ResilienceScore],
        service: str,
        namespace: str,
    ) -> dict[str, Any]:
        """
        Generate trend report from resilience scores.
        
        Args:
            scores: List of resilience scores over time
            service: Service name
            namespace: Namespace
            
        Returns:
            Report data
        """
        if not scores:
            return {"error": "No data available"}
        
        latest = scores[-1]
        
        # Calculate trends
        if len(scores) >= 2:
            prev = scores[-2]
            overall_change = latest.overall_score - prev.overall_score
            availability_change = latest.availability_score - prev.availability_score
            recovery_change = latest.recovery_score - prev.recovery_score
        else:
            overall_change = 0
            availability_change = 0
            recovery_change = 0
        
        return {
            "type": "trend",
            "generated_at": datetime.utcnow().isoformat(),
            "service": service,
            "namespace": namespace,
            "current_score": {
                "overall": latest.overall_score,
                "grade": latest.get_grade(),
                "availability": latest.availability_score,
                "recovery": latest.recovery_score,
                "degradation": latest.degradation_score,
                "blast_radius": latest.blast_radius_score,
            },
            "trends": {
                "overall_trend": latest.score_trend,
                "overall_change": overall_change,
                "availability_change": availability_change,
                "recovery_change": recovery_change,
            },
            "history": [
                {
                    "calculated_at": s.calculated_at.isoformat(),
                    "overall_score": s.overall_score,
                    "grade": s.get_grade(),
                }
                for s in scores
            ],
            "statistics": {
                "total_experiments": sum(s.experiments_run for s in scores),
                "avg_score": sum(s.overall_score for s in scores) / len(scores),
                "min_score": min(s.overall_score for s in scores),
                "max_score": max(s.overall_score for s in scores),
            },
            "recommendations": latest.recommendations,
        }
    
    def to_markdown(
        self,
        report: dict[str, Any],
    ) -> str:
        """
        Convert report to Markdown format.
        
        Args:
            report: Report data
            
        Returns:
            Markdown string
        """
        report_type = report.get("type", "unknown")
        
        if report_type == "experiment":
            return self._experiment_to_markdown(report)
        elif report_type == "gameday":
            return self._gameday_to_markdown(report)
        elif report_type == "trend":
            return self._trend_to_markdown(report)
        else:
            return f"Unknown report type: {report_type}"
    
    def _experiment_to_markdown(self, report: dict[str, Any]) -> str:
        """Convert experiment report to Markdown."""
        exp = report["experiment"]
        exec_info = report["execution"]
        result = report.get("result", {})
        
        status_emoji = "✅" if result.get("success") else "❌" if result else "⏳"
        
        lines = [
            f"# {status_emoji} Chaos Experiment Report: {exp['name']}",
            "",
            f"**ID:** `{exp['id']}`",
            f"**Status:** {exp['status']}",
            f"**Owner:** {exp.get('owner', 'N/A')}",
            f"**Team:** {exp.get('team', 'N/A')}",
            "",
            "## Description",
            "",
            exp.get("description", "No description"),
            "",
            "## Execution Details",
            "",
            f"- **Started:** {exec_info.get('started_at', 'N/A')}",
            f"- **Completed:** {exec_info.get('completed_at', 'N/A')}",
            f"- **Duration:** {exec_info.get('duration_seconds', 'N/A')}s",
            f"- **Dry Run:** {'Yes' if exec_info.get('dry_run') else 'No'}",
            "",
            "## Faults Injected",
            "",
        ]
        
        for fault in report.get("faults", []):
            lines.append(f"### {fault['type']}")
            lines.append(f"- **Target:** {fault['target']}")
            lines.append(f"- **Severity:** {fault['severity']}")
            lines.append(f"- **Duration:** {fault['duration_seconds']}s")
            lines.append("")
        
        if result:
            lines.extend([
                "## Results",
                "",
                f"**Success:** {'Yes ✅' if result['success'] else 'No ❌'}",
                f"**Message:** {result['message']}",
                "",
                "### Steady State Validation",
                "",
                f"| Phase | Met? |",
                f"|-------|------|",
                f"| Before | {'✅' if result['steady_state']['met_before'] else '❌'} |",
                f"| During | {'✅' if result['steady_state']['met_during'] else '❌'} |",
                f"| After | {'✅' if result['steady_state']['met_after'] else '❌'} |",
                "",
            ])
            
            if result.get("errors"):
                lines.append("### Errors")
                lines.append("")
                for error in result["errors"]:
                    lines.append(f"- {error}")
                lines.append("")
            
            if result.get("timeline"):
                lines.append("### Timeline")
                lines.append("")
                for event in result["timeline"][:10]:  # Limit to 10
                    lines.append(f"- **{event['timestamp']}**: {event['description']}")
                lines.append("")
        
        lines.extend([
            "---",
            f"*Generated at {report['generated_at']}*",
        ])
        
        return "\n".join(lines)
    
    def _gameday_to_markdown(self, report: dict[str, Any]) -> str:
        """Convert game day report to Markdown."""
        gd = report["game_day"]
        exec_info = report["execution"]
        summary = report["summary"]
        
        success_rate = summary["success_rate"]
        status_emoji = "🎉" if success_rate == 100 else "⚠️" if success_rate >= 50 else "🚨"
        
        lines = [
            f"# {status_emoji} Game Day Report: {gd['name']}",
            "",
            f"**ID:** `{gd['id']}`",
            f"**Status:** {gd['status']}",
            f"**Facilitator:** {gd.get('facilitator', 'N/A')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Experiments | {summary['total_experiments']} |",
            f"| Completed | {summary['completed_experiments']} |",
            f"| Successful | {summary['successful_experiments']} |",
            f"| Success Rate | {success_rate:.0f}% |",
            "",
            "## Execution",
            "",
            f"- **Scheduled:** {exec_info['scheduled_date']}",
            f"- **Started:** {exec_info.get('started_at', 'N/A')}",
            f"- **Completed:** {exec_info.get('completed_at', 'N/A')}",
            "",
            "## Participants",
            "",
        ]
        
        for participant in gd.get("participants", []):
            lines.append(f"- {participant}")
        
        lines.extend([
            "",
            "## Experiment Results",
            "",
        ])
        
        for exp_report in report.get("experiments", []):
            exp = exp_report["experiment"]
            result = exp_report.get("result", {})
            status = "✅" if result.get("success") else "❌" if result else "⏳"
            lines.append(f"### {status} {exp['name']}")
            lines.append(f"{result.get('message', 'No result')}")
            lines.append("")
        
        if report.get("findings"):
            lines.append("## Findings")
            lines.append("")
            for finding in report["findings"]:
                lines.append(f"- {finding}")
            lines.append("")
        
        if report.get("action_items"):
            lines.append("## Action Items")
            lines.append("")
            for item in report["action_items"]:
                lines.append(f"- [ ] {item}")
            lines.append("")
        
        lines.extend([
            "---",
            f"*Generated at {report['generated_at']}*",
        ])
        
        return "\n".join(lines)
    
    def _trend_to_markdown(self, report: dict[str, Any]) -> str:
        """Convert trend report to Markdown."""
        current = report["current_score"]
        trends = report["trends"]
        stats = report["statistics"]
        
        trend_emoji = {
            "improving": "📈",
            "declining": "📉",
            "stable": "➡️",
        }.get(trends["overall_trend"], "❓")
        
        lines = [
            f"# {trend_emoji} Resilience Trend Report",
            "",
            f"**Service:** {report['service']}",
            f"**Namespace:** {report['namespace']}",
            "",
            "## Current Score",
            "",
            f"**Overall:** {current['overall']:.0f}/100 (Grade: {current['grade']})",
            "",
            f"| Component | Score |",
            f"|-----------|-------|",
            f"| Availability | {current['availability']:.0f} |",
            f"| Recovery | {current['recovery']:.0f} |",
            f"| Degradation | {current['degradation']:.0f} |",
            f"| Blast Radius | {current['blast_radius']:.0f} |",
            "",
            "## Trends",
            "",
            f"- **Overall Trend:** {trends['overall_trend'].upper()} {trend_emoji}",
            f"- **Overall Change:** {trends['overall_change']:+.1f} points",
            "",
            "## Statistics",
            "",
            f"- **Total Experiments:** {stats['total_experiments']}",
            f"- **Average Score:** {stats['avg_score']:.0f}",
            f"- **Min Score:** {stats['min_score']:.0f}",
            f"- **Max Score:** {stats['max_score']:.0f}",
            "",
            "## Recommendations",
            "",
        ]
        
        for rec in report.get("recommendations", []):
            lines.append(rec)
            lines.append("")
        
        lines.extend([
            "---",
            f"*Generated at {report['generated_at']}*",
        ])
        
        return "\n".join(lines)
    
    def to_html(
        self,
        report: dict[str, Any],
    ) -> str:
        """
        Convert report to HTML format.
        
        Args:
            report: Report data
            
        Returns:
            HTML string
        """
        # Convert markdown to HTML using a simple converter
        markdown = self.to_markdown(report)
        
        # Basic conversion (would use a proper markdown library in production)
        html = markdown
        html = html.replace("# ", "<h1>").replace("\n\n", "</h1>\n")
        html = html.replace("## ", "<h2>").replace("\n\n", "</h2>\n")
        html = html.replace("**", "<strong>").replace("**", "</strong>")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Chaos Engineering Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
{html}
</body>
</html>
"""
