"""Toil Budget Tracker - Monitor and manage team toil levels.

Key principle: Toil should never exceed 50% of team capacity.
When it does, engineering capacity suffers and the team becomes reactive.

"If a human needs to touch during normal ops, you have a bug."
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import json


# Maximum acceptable toil ratio
TOIL_CAP = 0.50  # 50%

# Warning threshold (start taking action)
TOIL_WARNING = 0.40  # 40%


class ToilCategory(Enum):
    """Categories of toil for tracking."""
    INCIDENT_RESPONSE = "incident_response"
    MANUAL_SCALING = "manual_scaling"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    ACCESS_REQUESTS = "access_requests"
    MAINTENANCE = "maintenance"
    ON_CALL = "on_call"
    DATA_TASKS = "data_tasks"
    OTHER = "other"


class AlertLevel(Enum):
    """Alert levels for toil budget violations."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ToilEntry:
    """A single toil work entry."""
    timestamp: datetime
    engineer: str
    category: ToilCategory
    description: str
    hours: float
    service: Optional[str] = None
    ticket_id: Optional[str] = None
    automatable: bool = True
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "engineer": self.engineer,
            "category": self.category.value,
            "description": self.description,
            "hours": self.hours,
            "service": self.service,
            "ticket_id": self.ticket_id,
            "automatable": self.automatable,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ToilEntry":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            engineer=data["engineer"],
            category=ToilCategory(data["category"]),
            description=data["description"],
            hours=data["hours"],
            service=data.get("service"),
            ticket_id=data.get("ticket_id"),
            automatable=data.get("automatable", True),
        )


@dataclass
class ToilBudgetStatus:
    """Current status of team toil budget."""
    team: str
    period_start: datetime
    period_end: datetime
    toil_hours: float
    total_hours: float
    toil_ratio: float
    alert_level: AlertLevel
    top_categories: list[tuple[str, float]]  # (category, hours)
    top_services: list[tuple[str, float]]  # (service, hours)
    automatable_hours: float
    
    @property
    def engineering_ratio(self) -> float:
        """Ratio of engineering (non-toil) work."""
        return 1.0 - self.toil_ratio
    
    @property
    def hours_over_budget(self) -> float:
        """Hours of toil over the budget cap."""
        budget_hours = self.total_hours * TOIL_CAP
        return max(0, self.toil_hours - budget_hours)
    
    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "toil_hours": self.toil_hours,
            "total_hours": self.total_hours,
            "toil_ratio": round(self.toil_ratio, 3),
            "engineering_ratio": round(self.engineering_ratio, 3),
            "alert_level": self.alert_level.value,
            "hours_over_budget": self.hours_over_budget,
            "top_categories": self.top_categories,
            "top_services": self.top_services,
            "automatable_hours": self.automatable_hours,
        }


@dataclass
class AutomationOpportunity:
    """An opportunity to reduce toil through automation."""
    category: ToilCategory
    description: str
    monthly_hours: float
    automation_effort_hours: float
    roi_months: float  # Months until automation pays off
    priority: str  # "high", "medium", "low"
    affected_engineers: int
    services: list[str]
    
    @property
    def annual_hours_saved(self) -> float:
        return self.monthly_hours * 12
    
    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "description": self.description,
            "monthly_hours": self.monthly_hours,
            "automation_effort_hours": self.automation_effort_hours,
            "roi_months": round(self.roi_months, 1),
            "priority": self.priority,
            "affected_engineers": self.affected_engineers,
            "services": self.services,
            "annual_hours_saved": self.annual_hours_saved,
        }


class ToilBudgetTracker:
    """Track and analyze team toil budgets."""
    
    def __init__(
        self,
        team: str,
        team_size: int,
        hours_per_week: float = 40.0,
    ):
        self.team = team
        self.team_size = team_size
        self.hours_per_week = hours_per_week
        self.entries: list[ToilEntry] = []
    
    def record_toil(
        self,
        engineer: str,
        category: ToilCategory,
        description: str,
        hours: float,
        service: Optional[str] = None,
        ticket_id: Optional[str] = None,
        automatable: bool = True,
        timestamp: Optional[datetime] = None,
    ) -> ToilEntry:
        """Record a toil entry."""
        entry = ToilEntry(
            timestamp=timestamp or datetime.now(),
            engineer=engineer,
            category=category,
            description=description,
            hours=hours,
            service=service,
            ticket_id=ticket_id,
            automatable=automatable,
        )
        self.entries.append(entry)
        return entry
    
    def get_team_toil_ratio(
        self,
        period_days: int = 30,
        end_date: Optional[datetime] = None,
    ) -> ToilBudgetStatus:
        """Get team toil ratio for a period."""
        end = end_date or datetime.now()
        start = end - timedelta(days=period_days)
        
        # Filter entries in period
        period_entries = [
            e for e in self.entries
            if start <= e.timestamp <= end
        ]
        
        # Calculate hours
        toil_hours = sum(e.hours for e in period_entries)
        
        # Total available hours
        weeks = period_days / 7
        total_hours = self.team_size * self.hours_per_week * weeks
        
        # Ratio
        toil_ratio = toil_hours / total_hours if total_hours > 0 else 0
        
        # Alert level
        if toil_ratio >= TOIL_CAP:
            alert_level = AlertLevel.CRITICAL
        elif toil_ratio >= TOIL_WARNING:
            alert_level = AlertLevel.WARNING
        else:
            alert_level = AlertLevel.OK
        
        # Top categories
        category_hours: dict[str, float] = {}
        for e in period_entries:
            cat = e.category.value
            category_hours[cat] = category_hours.get(cat, 0) + e.hours
        top_categories = sorted(
            category_hours.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        
        # Top services
        service_hours: dict[str, float] = {}
        for e in period_entries:
            if e.service:
                service_hours[e.service] = service_hours.get(e.service, 0) + e.hours
        top_services = sorted(
            service_hours.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        
        # Automatable hours
        automatable_hours = sum(e.hours for e in period_entries if e.automatable)
        
        return ToilBudgetStatus(
            team=self.team,
            period_start=start,
            period_end=end,
            toil_hours=toil_hours,
            total_hours=total_hours,
            toil_ratio=toil_ratio,
            alert_level=alert_level,
            top_categories=top_categories,
            top_services=top_services,
            automatable_hours=automatable_hours,
        )
    
    def check_budget(self, period_days: int = 30) -> tuple[bool, str]:
        """Check if team is within toil budget.
        
        Returns:
            (within_budget, message)
        """
        status = self.get_team_toil_ratio(period_days)
        
        if status.alert_level == AlertLevel.OK:
            return True, f"Toil at {status.toil_ratio:.1%}, within budget"
        elif status.alert_level == AlertLevel.WARNING:
            return True, (
                f"WARNING: Toil at {status.toil_ratio:.1%}, "
                f"approaching cap of {TOIL_CAP:.0%}"
            )
        else:
            return False, (
                f"CRITICAL: Toil at {status.toil_ratio:.1%}, "
                f"exceeds cap of {TOIL_CAP:.0%}! "
                f"Over budget by {status.hours_over_budget:.1f} hours"
            )
    
    def get_toil_reduction_opportunities(
        self,
        period_days: int = 30,
    ) -> list[AutomationOpportunity]:
        """Identify and rank opportunities to reduce toil."""
        end = datetime.now()
        start = end - timedelta(days=period_days)
        
        # Filter entries
        period_entries = [
            e for e in self.entries
            if start <= e.timestamp <= end and e.automatable
        ]
        
        # Group by category + description pattern
        groups: dict[tuple, list[ToilEntry]] = {}
        for e in period_entries:
            # Simple grouping by category
            key = (e.category,)
            if key not in groups:
                groups[key] = []
            groups[key].append(e)
        
        opportunities = []
        for (category,), entries in groups.items():
            total_hours = sum(e.hours for e in entries)
            monthly_hours = total_hours * (30 / period_days)  # Normalize to monthly
            
            # Estimate automation effort based on category
            effort_estimates = {
                ToilCategory.INCIDENT_RESPONSE: 40,  # Complex
                ToilCategory.MANUAL_SCALING: 16,
                ToilCategory.DEPLOYMENT: 24,
                ToilCategory.MONITORING: 8,
                ToilCategory.ACCESS_REQUESTS: 16,
                ToilCategory.MAINTENANCE: 20,
                ToilCategory.ON_CALL: 32,
                ToilCategory.DATA_TASKS: 12,
                ToilCategory.OTHER: 16,
            }
            effort = effort_estimates.get(category, 16)
            
            # ROI in months
            roi_months = effort / monthly_hours if monthly_hours > 0 else float('inf')
            
            # Priority based on ROI
            if roi_months <= 1:
                priority = "high"
            elif roi_months <= 3:
                priority = "medium"
            else:
                priority = "low"
            
            # Unique engineers and services
            engineers = set(e.engineer for e in entries)
            services = list(set(e.service for e in entries if e.service))
            
            # Build description
            desc = f"Automate {category.value.replace('_', ' ')} tasks"
            
            opportunities.append(AutomationOpportunity(
                category=category,
                description=desc,
                monthly_hours=round(monthly_hours, 1),
                automation_effort_hours=effort,
                roi_months=roi_months,
                priority=priority,
                affected_engineers=len(engineers),
                services=services,
            ))
        
        # Sort by ROI (lowest = fastest payback = best)
        opportunities.sort(key=lambda o: o.roi_months)
        
        return opportunities
    
    def get_engineer_breakdown(
        self,
        period_days: int = 30,
    ) -> dict[str, dict]:
        """Get toil breakdown by engineer."""
        end = datetime.now()
        start = end - timedelta(days=period_days)
        
        period_entries = [
            e for e in self.entries
            if start <= e.timestamp <= end
        ]
        
        breakdown: dict[str, dict] = {}
        for e in period_entries:
            if e.engineer not in breakdown:
                breakdown[e.engineer] = {
                    "total_hours": 0,
                    "categories": {},
                }
            
            breakdown[e.engineer]["total_hours"] += e.hours
            cat = e.category.value
            if cat not in breakdown[e.engineer]["categories"]:
                breakdown[e.engineer]["categories"][cat] = 0
            breakdown[e.engineer]["categories"][cat] += e.hours
        
        # Calculate ratios
        weeks = period_days / 7
        available_hours = self.hours_per_week * weeks
        
        for eng, data in breakdown.items():
            data["toil_ratio"] = round(data["total_hours"] / available_hours, 3)
            data["over_budget"] = data["toil_ratio"] > TOIL_CAP
        
        return breakdown
    
    def get_trend(
        self,
        weeks: int = 12,
        granularity: str = "weekly",
    ) -> list[dict]:
        """Get toil trend over time."""
        trends = []
        end = datetime.now()
        
        if granularity == "weekly":
            period = timedelta(weeks=1)
            periods = weeks
        else:  # monthly
            period = timedelta(days=30)
            periods = weeks // 4
        
        for i in range(periods):
            period_end = end - (period * i)
            period_start = period_end - period
            
            period_entries = [
                e for e in self.entries
                if period_start <= e.timestamp <= period_end
            ]
            
            toil_hours = sum(e.hours for e in period_entries)
            
            # Available hours for period
            if granularity == "weekly":
                available = self.team_size * self.hours_per_week
            else:
                available = self.team_size * self.hours_per_week * 4.3
            
            ratio = toil_hours / available if available > 0 else 0
            
            trends.append({
                "period_end": period_end.isoformat(),
                "toil_hours": round(toil_hours, 1),
                "toil_ratio": round(ratio, 3),
                "within_budget": ratio <= TOIL_CAP,
            })
        
        # Reverse to chronological order
        return list(reversed(trends))
    
    def export_entries(self) -> list[dict]:
        """Export all entries as dicts."""
        return [e.to_dict() for e in self.entries]
    
    def import_entries(self, entries: list[dict]) -> int:
        """Import entries from dicts."""
        count = 0
        for data in entries:
            try:
                entry = ToilEntry.from_dict(data)
                self.entries.append(entry)
                count += 1
            except (KeyError, ValueError):
                pass  # Skip malformed entries
        return count


def create_alert(status: ToilBudgetStatus) -> Optional[dict]:
    """Create an alert if toil budget is exceeded."""
    if status.alert_level == AlertLevel.OK:
        return None
    
    return {
        "type": "toil_budget",
        "severity": status.alert_level.value,
        "team": status.team,
        "message": (
            f"Team {status.team} toil ratio is {status.toil_ratio:.1%} "
            f"(cap: {TOIL_CAP:.0%})"
        ),
        "details": {
            "toil_hours": status.toil_hours,
            "total_hours": status.total_hours,
            "top_categories": status.top_categories[:3],
            "automatable_hours": status.automatable_hours,
        },
        "recommendations": [
            f"Automate top toil category: {status.top_categories[0][0]}"
            if status.top_categories else "Review toil sources",
            f"{status.automatable_hours:.1f} hours of automatable work identified",
        ],
    }
