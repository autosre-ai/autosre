"""Toil Dashboard Data - Generate dashboard data for toil tracking.

Provides:
- Toil vs engineering time ratio
- Toil trends over time
- Top toil sources
- Automation opportunities ranked by ROI
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from .classifier import ToilClassifier
from .budget import (
    ToilBudgetTracker,
    TOIL_CAP,
    TOIL_WARNING,
)


@dataclass
class DashboardSummary:
    """Summary data for the toil dashboard header."""
    team: str
    current_toil_ratio: float
    target_ratio: float
    trend: str  # "improving", "stable", "degrading"
    toil_hours_month: float
    engineering_hours_month: float
    automatable_hours: float
    alert_count: int
    
    @property
    def health_status(self) -> str:
        if self.current_toil_ratio <= TOIL_WARNING:
            return "healthy"
        elif self.current_toil_ratio <= TOIL_CAP:
            return "warning"
        else:
            return "critical"
    
    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "current_toil_ratio": round(self.current_toil_ratio, 3),
            "target_ratio": self.target_ratio,
            "trend": self.trend,
            "health_status": self.health_status,
            "toil_hours_month": round(self.toil_hours_month, 1),
            "engineering_hours_month": round(self.engineering_hours_month, 1),
            "automatable_hours": round(self.automatable_hours, 1),
            "alert_count": self.alert_count,
            "potential_recovery": round(self.automatable_hours / self.toil_hours_month, 2)
            if self.toil_hours_month > 0 else 0,
        }


@dataclass
class ToilSource:
    """A source of toil for the dashboard."""
    name: str
    category: str
    hours_per_month: float
    percentage_of_toil: float
    trend: str  # "increasing", "stable", "decreasing"
    automation_potential: str
    estimated_automation_hours: float
    roi_months: float
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "hours_per_month": round(self.hours_per_month, 1),
            "percentage_of_toil": round(self.percentage_of_toil, 1),
            "trend": self.trend,
            "automation_potential": self.automation_potential,
            "estimated_automation_hours": round(self.estimated_automation_hours, 1),
            "roi_months": round(self.roi_months, 1),
        }


class ToilDashboard:
    """Generate dashboard data for toil tracking and visualization."""
    
    def __init__(self, tracker: ToilBudgetTracker):
        self.tracker = tracker
        self.classifier = ToilClassifier()
    
    def get_summary(self) -> DashboardSummary:
        """Get dashboard summary data."""
        # Current status
        status = self.tracker.get_team_toil_ratio(period_days=30)
        
        # Calculate trend by comparing last 2 weeks vs previous 2 weeks
        recent = self.tracker.get_team_toil_ratio(period_days=14)
        end_previous = datetime.now() - timedelta(days=14)
        previous = self.tracker.get_team_toil_ratio(
            period_days=14,
            end_date=end_previous,
        )
        
        if recent.toil_ratio < previous.toil_ratio - 0.05:
            trend = "improving"
        elif recent.toil_ratio > previous.toil_ratio + 0.05:
            trend = "degrading"
        else:
            trend = "stable"
        
        # Alert count
        alert_count = 1 if status.alert_level.value != "ok" else 0
        
        return DashboardSummary(
            team=self.tracker.team,
            current_toil_ratio=status.toil_ratio,
            target_ratio=TOIL_CAP,
            trend=trend,
            toil_hours_month=status.toil_hours,
            engineering_hours_month=status.total_hours - status.toil_hours,
            automatable_hours=status.automatable_hours,
            alert_count=alert_count,
        )
    
    def get_toil_vs_engineering_chart(
        self,
        weeks: int = 12,
    ) -> list[dict]:
        """Get time series data for toil vs engineering chart."""
        trend_data = self.tracker.get_trend(weeks=weeks, granularity="weekly")
        
        # Add engineering hours
        available_per_week = self.tracker.team_size * self.tracker.hours_per_week
        
        chart_data = []
        for point in trend_data:
            toil_hours = point["toil_hours"]
            eng_hours = available_per_week - toil_hours
            
            chart_data.append({
                "period": point["period_end"][:10],  # Just date
                "toil_hours": toil_hours,
                "engineering_hours": round(max(0, eng_hours), 1),
                "toil_ratio": point["toil_ratio"],
                "target_line": TOIL_CAP,
                "warning_line": TOIL_WARNING,
            })
        
        return chart_data
    
    def get_toil_by_category(self, period_days: int = 30) -> list[dict]:
        """Get toil breakdown by category for pie chart."""
        status = self.tracker.get_team_toil_ratio(period_days)
        
        return [
            {
                "category": cat.replace("_", " ").title(),
                "hours": hours,
                "percentage": round(hours / status.toil_hours * 100, 1)
                if status.toil_hours > 0 else 0,
            }
            for cat, hours in status.top_categories
        ]
    
    def get_toil_by_service(self, period_days: int = 30) -> list[dict]:
        """Get toil breakdown by service."""
        status = self.tracker.get_team_toil_ratio(period_days)
        
        return [
            {
                "service": service,
                "hours": hours,
                "percentage": round(hours / status.toil_hours * 100, 1)
                if status.toil_hours > 0 else 0,
            }
            for service, hours in status.top_services
        ]
    
    def get_top_toil_sources(
        self,
        limit: int = 10,
    ) -> list[ToilSource]:
        """Get top toil sources with automation analysis."""
        opportunities = self.tracker.get_toil_reduction_opportunities(period_days=30)
        status = self.tracker.get_team_toil_ratio(period_days=30)
        
        sources = []
        for opp in opportunities[:limit]:
            # Determine trend (would need historical data, using placeholder)
            trend = "stable"
            
            pct = (opp.monthly_hours / status.toil_hours * 100) if status.toil_hours > 0 else 0
            
            sources.append(ToilSource(
                name=opp.description,
                category=opp.category.value,
                hours_per_month=opp.monthly_hours,
                percentage_of_toil=pct,
                trend=trend,
                automation_potential=opp.priority,
                estimated_automation_hours=opp.automation_effort_hours,
                roi_months=opp.roi_months,
            ))
        
        return sources
    
    def get_automation_opportunities_ranked(
        self,
        limit: int = 10,
    ) -> list[dict]:
        """Get automation opportunities ranked by ROI."""
        opportunities = self.tracker.get_toil_reduction_opportunities()
        
        ranked = []
        for i, opp in enumerate(opportunities[:limit], 1):
            ranked.append({
                "rank": i,
                "category": opp.category.value.replace("_", " ").title(),
                "description": opp.description,
                "monthly_hours_saved": opp.monthly_hours,
                "annual_hours_saved": opp.annual_hours_saved,
                "automation_effort_hours": opp.automation_effort_hours,
                "roi_months": opp.roi_months,
                "priority": opp.priority,
                "affected_engineers": opp.affected_engineers,
                "services": opp.services,
            })
        
        return ranked
    
    def get_engineer_toil_distribution(self) -> list[dict]:
        """Get toil distribution across team members."""
        breakdown = self.tracker.get_engineer_breakdown(period_days=30)
        
        distribution = []
        for engineer, data in sorted(
            breakdown.items(),
            key=lambda x: x[1]["total_hours"],
            reverse=True,
        ):
            distribution.append({
                "engineer": engineer,
                "toil_hours": round(data["total_hours"], 1),
                "toil_ratio": data["toil_ratio"],
                "over_budget": data["over_budget"],
                "top_category": max(
                    data["categories"].items(),
                    key=lambda x: x[1],
                )[0] if data["categories"] else None,
            })
        
        return distribution
    
    def get_full_dashboard_data(self) -> dict:
        """Get all dashboard data in one call."""
        return {
            "summary": self.get_summary().to_dict(),
            "toil_vs_engineering": self.get_toil_vs_engineering_chart(),
            "toil_by_category": self.get_toil_by_category(),
            "toil_by_service": self.get_toil_by_service(),
            "top_toil_sources": [s.to_dict() for s in self.get_top_toil_sources()],
            "automation_opportunities": self.get_automation_opportunities_ranked(),
            "engineer_distribution": self.get_engineer_toil_distribution(),
            "generated_at": datetime.now().isoformat(),
        }
    
    def export_json(self, filepath: str) -> None:
        """Export dashboard data to JSON file."""
        data = self.get_full_dashboard_data()
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    def generate_report(self) -> str:
        """Generate a text report of toil status."""
        summary = self.get_summary()
        opportunities = self.get_automation_opportunities_ranked(limit=5)
        
        lines = [
            f"# Toil Report: {summary.team}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary",
            f"- Current Toil Ratio: {summary.current_toil_ratio:.1%} (target: <{summary.target_ratio:.0%})",
            f"- Health Status: {summary.health_status.upper()}",
            f"- Trend: {summary.trend}",
            f"- Toil Hours (30d): {summary.toil_hours_month:.1f}h",
            f"- Engineering Hours (30d): {summary.engineering_hours_month:.1f}h",
            f"- Automatable Hours: {summary.automatable_hours:.1f}h",
            "",
        ]
        
        if summary.health_status == "critical":
            lines.extend([
                "## ⚠️ ALERT: Toil Budget Exceeded",
                f"Team is at {summary.current_toil_ratio:.1%} toil, exceeding the {TOIL_CAP:.0%} cap.",
                "Immediate action required to reduce toil and restore engineering capacity.",
                "",
            ])
        
        lines.extend([
            "## Top Automation Opportunities",
            "",
        ])
        
        for opp in opportunities:
            lines.append(
                f"{opp['rank']}. **{opp['description']}** ({opp['priority']} priority)\n"
                f"   - Hours saved/month: {opp['monthly_hours_saved']:.1f}h\n"
                f"   - Automation effort: {opp['automation_effort_hours']:.0f}h\n"
                f"   - ROI: {opp['roi_months']:.1f} months\n"
            )
        
        lines.extend([
            "",
            "## Recommendations",
            "",
        ])
        
        if summary.automatable_hours > 0:
            lines.append(
                f"1. Automating identified toil could recover {summary.automatable_hours:.1f}h/month "
                f"({summary.automatable_hours / summary.toil_hours_month * 100:.0f}% of current toil)"
            )
        
        if opportunities:
            lines.append(
                f"2. Start with '{opportunities[0]['description']}' - "
                f"best ROI at {opportunities[0]['roi_months']:.1f} months payback"
            )
        
        lines.append(
            "3. Remember: The best automation is a system that needs neither automation nor manual operation"
        )
        
        return "\n".join(lines)
