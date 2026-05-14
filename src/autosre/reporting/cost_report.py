"""Cost Reports for AutoSRE V2.

Provides infrastructure cost reporting:
- Cost breakdown by service
- Trend analysis
- Optimization recommendations
- Budget tracking
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.reporting.report_generator import (
    Report,
    ReportFormat,
    ReportGenerator,
    ReportType,
    TableData,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class CostCategory(str, Enum):
    """Cost categories."""
    
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    MONITORING = "monitoring"
    SECURITY = "security"
    AI_ML = "ai_ml"
    OTHER = "other"


class CostItem(BaseModel):
    """A single cost item."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Resource info
    resource_type: str
    resource_id: str
    resource_name: Optional[str] = None
    
    # Service/project
    service: str
    project: Optional[str] = None
    environment: str = "production"
    
    # Cost
    cost_usd: float
    cost_currency: str = "USD"
    
    # Category
    category: CostCategory
    
    # Usage
    usage_quantity: Optional[float] = None
    usage_unit: Optional[str] = None
    
    # Tags
    tags: Dict[str, str] = Field(default_factory=dict)


class CostBreakdown(BaseModel):
    """Cost breakdown by dimension."""
    
    dimension: str  # service, category, environment, etc.
    items: Dict[str, float] = Field(default_factory=dict)
    total: float = 0.0
    
    def add_item(self, key: str, amount: float) -> None:
        """Add an item to the breakdown."""
        if key in self.items:
            self.items[key] += amount
        else:
            self.items[key] = amount
        self.total += amount


class BudgetStatus(BaseModel):
    """Budget tracking status."""
    
    budget_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float
    
    # Forecast
    forecasted_spend: Optional[float] = None
    forecasted_overage: Optional[float] = None
    
    # Status
    on_track: bool = True
    alert_threshold_reached: bool = False


class CostReportData(BaseModel):
    """Data for generating a cost report."""
    
    # Scope
    services: List[str] = Field(default_factory=list)
    environment: str = "production"
    
    # Total costs
    total_cost: float = 0.0
    previous_period_cost: Optional[float] = None
    cost_change_percentage: Optional[float] = None
    
    # Breakdowns
    by_service: CostBreakdown = Field(default_factory=lambda: CostBreakdown(dimension="service"))
    by_category: CostBreakdown = Field(default_factory=lambda: CostBreakdown(dimension="category"))
    by_environment: CostBreakdown = Field(default_factory=lambda: CostBreakdown(dimension="environment"))
    
    # Detailed items
    cost_items: List[CostItem] = Field(default_factory=list)
    
    # Budget tracking
    budgets: List[BudgetStatus] = Field(default_factory=list)
    
    # Trends
    daily_costs: List[Dict[str, Any]] = Field(default_factory=list)
    monthly_costs: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Optimization opportunities
    optimization_opportunities: List[Dict[str, Any]] = Field(default_factory=list)
    potential_savings: float = 0.0


class CostReport:
    """
    Generates infrastructure cost reports.
    
    Provides:
    - Cost summary
    - Breakdown by dimension
    - Budget tracking
    - Trend analysis
    - Optimization recommendations
    
    Example:
        report_gen = CostReport(generator)
        
        data = CostReportData(
            total_cost=15000.00,
            previous_period_cost=14000.00,
        )
        
        data.by_service.add_item("api-gateway", 3000.00)
        data.by_service.add_item("database", 5000.00)
        
        report = await report_gen.generate(
            tenant_id="tenant-123",
            data=data,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
        )
    """
    
    def __init__(self, generator: ReportGenerator):
        self.generator = generator
    
    async def generate(
        self,
        tenant_id: str,
        data: CostReportData,
        period_start: datetime,
        period_end: datetime,
        format: ReportFormat = ReportFormat.HTML,
    ) -> Report:
        """Generate a cost report."""
        key_metrics = self._calculate_metrics(data)
        
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.COST,
            title="Infrastructure Cost Report",
            subtitle=f"Environment: {data.environment}",
            period_start=period_start,
            period_end=period_end,
            summary=self._generate_summary(data),
            key_metrics=key_metrics,
        )
        
        self._add_overview_section(report, data)
        self._add_service_breakdown_section(report, data)
        self._add_category_breakdown_section(report, data)
        self._add_budget_section(report, data)
        self._add_optimization_section(report, data)
        
        await self.generator.generate(report, format)
        
        return report
    
    def _calculate_metrics(self, data: CostReportData) -> Dict[str, Any]:
        """Calculate key metrics."""
        metrics = {
            "Total Cost": f"${data.total_cost:,.2f}",
        }
        
        if data.cost_change_percentage is not None:
            change_str = f"{data.cost_change_percentage:+.1f}%"
            metrics["vs Last Period"] = change_str
        
        if data.potential_savings > 0:
            metrics["Potential Savings"] = f"${data.potential_savings:,.2f}"
        
        # Top service
        if data.by_service.items:
            top_service = max(data.by_service.items.items(), key=lambda x: x[1])
            metrics["Top Service"] = f"{top_service[0]} (${top_service[1]:,.0f})"
        
        return metrics
    
    def _generate_summary(self, data: CostReportData) -> str:
        """Generate executive summary."""
        change_text = ""
        if data.cost_change_percentage is not None:
            direction = "increased" if data.cost_change_percentage > 0 else "decreased"
            change_text = f" This represents a {abs(data.cost_change_percentage):.1f}% {direction} from the previous period."
        
        return f"""
        <p>Total infrastructure costs for this period were <strong>${data.total_cost:,.2f}</strong>.{change_text}</p>
        <p>Costs are distributed across {len(data.by_service.items)} services and {len(data.by_category.items)} categories.</p>
        """
    
    def _add_overview_section(
        self,
        report: Report,
        data: CostReportData,
    ) -> None:
        """Add cost overview section."""
        change_class = "positive" if (data.cost_change_percentage or 0) <= 0 else "negative"
        change_arrow = "↓" if (data.cost_change_percentage or 0) <= 0 else "↑"
        
        content = f"""
        <div class="cost-overview">
            <div class="total-cost">
                <div class="amount">${data.total_cost:,.2f}</div>
                <div class="period">Total Cost</div>
                {f'<div class="change {change_class}">{change_arrow} {abs(data.cost_change_percentage or 0):.1f}%</div>' if data.cost_change_percentage else ''}
            </div>
            
            <style>
            .cost-overview {{ text-align: center; margin: 30px 0; }}
            .total-cost .amount {{ font-size: 3em; font-weight: bold; color: #007bff; }}
            .total-cost .period {{ color: #666; }}
            .total-cost .change {{ margin-top: 10px; font-size: 1.2em; }}
            .change.positive {{ color: #28a745; }}
            .change.negative {{ color: #dc3545; }}
            </style>
        </div>
        """
        
        report.add_section(
            title="Cost Overview",
            content=content,
        )
    
    def _add_service_breakdown_section(
        self,
        report: Report,
        data: CostReportData,
    ) -> None:
        """Add cost by service section."""
        if not data.by_service.items:
            return
        
        # Sort by cost descending
        sorted_items = sorted(
            data.by_service.items.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        rows = []
        for service, cost in sorted_items:
            percentage = (cost / data.total_cost * 100) if data.total_cost > 0 else 0
            bar_width = min(100, percentage * 2)  # Scale for visual
            
            rows.append([
                service,
                f"${cost:,.2f}",
                f"{percentage:.1f}%",
                f'<div style="background: #007bff; height: 15px; width: {bar_width}%;"></div>',
            ])
        
        table = TableData(
            headers=["Service", "Cost", "% of Total", ""],
            rows=rows,
        )
        
        content = self.generator.render_table(table)
        
        report.add_section(
            title="Cost by Service",
            content=content,
        )
    
    def _add_category_breakdown_section(
        self,
        report: Report,
        data: CostReportData,
    ) -> None:
        """Add cost by category section."""
        if not data.by_category.items:
            return
        
        content = '<div class="category-breakdown">'
        
        # Create a simple chart representation
        sorted_items = sorted(
            data.by_category.items.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        colors = {
            "compute": "#007bff",
            "storage": "#28a745",
            "network": "#17a2b8",
            "database": "#ffc107",
            "monitoring": "#6f42c1",
            "security": "#e83e8c",
            "ai_ml": "#fd7e14",
            "other": "#6c757d",
        }
        
        for category, cost in sorted_items:
            percentage = (cost / data.total_cost * 100) if data.total_cost > 0 else 0
            color = colors.get(category.lower(), "#6c757d")
            
            content += f"""
            <div class="category-item">
                <div class="category-label">{category.replace('_', ' ').title()}</div>
                <div class="category-bar" style="width: {percentage}%; background: {color};"></div>
                <div class="category-value">${cost:,.2f} ({percentage:.1f}%)</div>
            </div>
            """
        
        content += """
            <style>
            .category-item { margin: 15px 0; }
            .category-label { font-weight: bold; margin-bottom: 5px; }
            .category-bar { height: 20px; border-radius: 4px; min-width: 5px; }
            .category-value { font-size: 0.9em; color: #666; margin-top: 5px; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Cost by Category",
            content=content,
        )
    
    def _add_budget_section(
        self,
        report: Report,
        data: CostReportData,
    ) -> None:
        """Add budget tracking section."""
        if not data.budgets:
            return
        
        content = '<div class="budget-tracking">'
        
        for budget in data.budgets:
            bar_color = "#28a745" if budget.percentage_used < 80 else ("#ffc107" if budget.percentage_used < 100 else "#dc3545")
            bar_width = min(100, budget.percentage_used)
            
            content += f"""
            <div class="budget-card">
                <h4>{budget.budget_name}</h4>
                <div class="budget-amounts">
                    <span>Spent: ${budget.spent_amount:,.2f}</span>
                    <span>Budget: ${budget.budget_amount:,.2f}</span>
                </div>
                <div class="budget-bar">
                    <div class="budget-fill" style="width: {bar_width}%; background: {bar_color};"></div>
                </div>
                <div class="budget-status">
                    {budget.percentage_used:.1f}% used
                    {'⚠️ Over budget!' if budget.percentage_used > 100 else ''}
                </div>
            </div>
            """
        
        content += """
            <style>
            .budget-card { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
            .budget-amounts { display: flex; justify-content: space-between; margin: 10px 0; }
            .budget-bar { height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }
            .budget-fill { height: 100%; }
            .budget-status { margin-top: 10px; font-weight: bold; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Budget Tracking",
            content=content,
        )
    
    def _add_optimization_section(
        self,
        report: Report,
        data: CostReportData,
    ) -> None:
        """Add optimization recommendations section."""
        if not data.optimization_opportunities:
            return
        
        content = f"""
        <div class="optimization">
            <div class="savings-potential">
                <div class="amount">${data.potential_savings:,.2f}</div>
                <div class="label">Potential Monthly Savings</div>
            </div>
            
            <h3>Optimization Opportunities</h3>
        """
        
        for opp in data.optimization_opportunities:
            savings = opp.get("savings", 0)
            effort = opp.get("effort", "medium")
            effort_color = {"low": "#28a745", "medium": "#ffc107", "high": "#dc3545"}.get(effort, "#6c757d")
            
            content += f"""
            <div class="opportunity">
                <div class="opp-header">
                    <h4>{opp.get('title', 'Optimization')}</h4>
                    <span class="savings">${savings:,.2f}/mo</span>
                </div>
                <p>{opp.get('description', '')}</p>
                <div class="opp-meta">
                    <span>Effort: <span style="color: {effort_color}; font-weight: bold;">{effort.title()}</span></span>
                    <span>Category: {opp.get('category', 'General')}</span>
                </div>
            </div>
            """
        
        content += """
            <style>
            .savings-potential { text-align: center; margin: 30px 0; }
            .savings-potential .amount { font-size: 2.5em; font-weight: bold; color: #28a745; }
            .opportunity { padding: 15px; border: 1px solid #dee2e6; border-radius: 8px; margin: 15px 0; }
            .opp-header { display: flex; justify-content: space-between; align-items: center; }
            .opp-header h4 { margin: 0; }
            .savings { color: #28a745; font-weight: bold; }
            .opp-meta { font-size: 0.9em; color: #666; margin-top: 10px; display: flex; gap: 20px; }
            </style>
        </div>
        """
        
        report.add_section(
            title="Cost Optimization",
            content=content,
            page_break_before=True,
        )
