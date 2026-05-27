"""Automation ROI Calculator - Evaluate the value of automation investments.

ROI factors (in order of IMPORTANCE, not just time saved):
1. Consistency improvement - Eliminates human error
2. Platform extensibility - Enables further automation
3. Reduced MTTR - Faster incident resolution
4. Decoupling operator from operation - Removes single points of failure
5. Time savings - The least important factor

"Time savings" is overrated. The real value of automation is:
- Reproducibility
- Speed at scale
- Knowledge capture
- 24/7 availability
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ROIFactor(Enum):
    """Factors that contribute to automation ROI."""
    CONSISTENCY = "consistency"  # Eliminates human error
    EXTENSIBILITY = "extensibility"  # Enables further automation
    MTTR_REDUCTION = "mttr_reduction"  # Faster incident resolution
    DECOUPLING = "decoupling"  # Removes operator dependency
    TIME_SAVINGS = "time_savings"  # Hours saved (least important)


# Weights for each factor (must sum to 1.0)
# Note: Time savings is intentionally low - it's the least valuable benefit
FACTOR_WEIGHTS = {
    ROIFactor.CONSISTENCY: 0.30,
    ROIFactor.EXTENSIBILITY: 0.25,
    ROIFactor.MTTR_REDUCTION: 0.20,
    ROIFactor.DECOUPLING: 0.15,
    ROIFactor.TIME_SAVINGS: 0.10,
}


@dataclass
class ROIFactors:
    """Input factors for ROI calculation."""
    # Time savings (least important)
    hours_per_month_manual: float = 10.0  # Current manual hours
    hours_to_automate: float = 40.0  # One-time automation cost
    maintenance_hours_per_month: float = 2.0  # Ongoing maintenance
    
    # Consistency improvement
    error_rate_manual: float = 0.05  # 5% error rate for manual
    error_rate_automated: float = 0.001  # 0.1% for automated
    cost_per_error: float = 1000.0  # $ cost of each error
    
    # MTTR reduction
    mttr_manual_minutes: float = 60.0  # MTTR with manual remediation
    mttr_automated_minutes: float = 5.0  # MTTR with automation
    incidents_per_month: float = 10.0  # Number of incidents
    downtime_cost_per_minute: float = 100.0  # $ cost per minute downtime
    
    # Decoupling (operator independence)
    required_operators_manual: int = 2  # People who can do this manually
    operator_hourly_cost: float = 75.0  # Cost per operator hour
    on_call_burden_hours: float = 10.0  # Monthly on-call hours for this
    
    # Platform extensibility
    enables_further_automation: bool = True
    dependent_automations: int = 0  # How many other automations this enables
    reusability_factor: float = 1.0  # 1.0 = single use, 2.0 = reused once, etc.
    
    # Strategic value
    supports_critical_service: bool = False
    regulatory_requirement: bool = False
    customer_facing_impact: bool = False


@dataclass
class ROIAssessment:
    """Assessment of automation ROI."""
    automation_name: str
    factors: ROIFactors
    
    # Calculated values
    time_savings_score: float = 0.0  # 0-1
    consistency_score: float = 0.0  # 0-1
    mttr_score: float = 0.0  # 0-1
    decoupling_score: float = 0.0  # 0-1
    extensibility_score: float = 0.0  # 0-1
    
    # Overall
    weighted_score: float = 0.0  # 0-1
    payback_months: float = 0.0
    annual_value: float = 0.0  # $ value
    recommendation: str = ""
    
    assessed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def priority(self) -> str:
        """Determine priority based on weighted score."""
        if self.weighted_score >= 0.7:
            return "high"
        elif self.weighted_score >= 0.4:
            return "medium"
        else:
            return "low"
    
    def to_dict(self) -> dict:
        return {
            "automation_name": self.automation_name,
            "scores": {
                "consistency": round(self.consistency_score, 3),
                "extensibility": round(self.extensibility_score, 3),
                "mttr_reduction": round(self.mttr_score, 3),
                "decoupling": round(self.decoupling_score, 3),
                "time_savings": round(self.time_savings_score, 3),
            },
            "weighted_score": round(self.weighted_score, 3),
            "payback_months": round(self.payback_months, 1),
            "annual_value_usd": round(self.annual_value, 2),
            "priority": self.priority,
            "recommendation": self.recommendation,
            "assessed_at": self.assessed_at.isoformat(),
        }
    
    def get_score_breakdown(self) -> list[dict]:
        """Get score breakdown with weights."""
        return [
            {
                "factor": "Consistency Improvement",
                "score": self.consistency_score,
                "weight": FACTOR_WEIGHTS[ROIFactor.CONSISTENCY],
                "weighted": self.consistency_score * FACTOR_WEIGHTS[ROIFactor.CONSISTENCY],
            },
            {
                "factor": "Platform Extensibility",
                "score": self.extensibility_score,
                "weight": FACTOR_WEIGHTS[ROIFactor.EXTENSIBILITY],
                "weighted": self.extensibility_score * FACTOR_WEIGHTS[ROIFactor.EXTENSIBILITY],
            },
            {
                "factor": "MTTR Reduction",
                "score": self.mttr_score,
                "weight": FACTOR_WEIGHTS[ROIFactor.MTTR_REDUCTION],
                "weighted": self.mttr_score * FACTOR_WEIGHTS[ROIFactor.MTTR_REDUCTION],
            },
            {
                "factor": "Operator Decoupling",
                "score": self.decoupling_score,
                "weight": FACTOR_WEIGHTS[ROIFactor.DECOUPLING],
                "weighted": self.decoupling_score * FACTOR_WEIGHTS[ROIFactor.DECOUPLING],
            },
            {
                "factor": "Time Savings",
                "score": self.time_savings_score,
                "weight": FACTOR_WEIGHTS[ROIFactor.TIME_SAVINGS],
                "weighted": self.time_savings_score * FACTOR_WEIGHTS[ROIFactor.TIME_SAVINGS],
                "note": "Least important factor",
            },
        ]


class AutomationROICalculator:
    """Calculate ROI for automation investments.
    
    Remember: The real value of automation is NOT time savings.
    It's consistency, extensibility, and removing human dependencies.
    """
    
    def calculate(
        self,
        name: str,
        factors: ROIFactors,
    ) -> ROIAssessment:
        """Calculate comprehensive ROI for an automation."""
        assessment = ROIAssessment(
            automation_name=name,
            factors=factors,
        )
        
        # Calculate individual scores
        assessment.time_savings_score = self._calc_time_savings_score(factors)
        assessment.consistency_score = self._calc_consistency_score(factors)
        assessment.mttr_score = self._calc_mttr_score(factors)
        assessment.decoupling_score = self._calc_decoupling_score(factors)
        assessment.extensibility_score = self._calc_extensibility_score(factors)
        
        # Calculate weighted score
        assessment.weighted_score = (
            assessment.consistency_score * FACTOR_WEIGHTS[ROIFactor.CONSISTENCY] +
            assessment.extensibility_score * FACTOR_WEIGHTS[ROIFactor.EXTENSIBILITY] +
            assessment.mttr_score * FACTOR_WEIGHTS[ROIFactor.MTTR_REDUCTION] +
            assessment.decoupling_score * FACTOR_WEIGHTS[ROIFactor.DECOUPLING] +
            assessment.time_savings_score * FACTOR_WEIGHTS[ROIFactor.TIME_SAVINGS]
        )
        
        # Calculate financial values
        assessment.annual_value = self._calc_annual_value(factors)
        assessment.payback_months = self._calc_payback_months(factors, assessment.annual_value)
        
        # Generate recommendation
        assessment.recommendation = self._generate_recommendation(assessment)
        
        return assessment
    
    def _calc_time_savings_score(self, f: ROIFactors) -> float:
        """Calculate time savings score (0-1)."""
        # Net hours saved per month
        net_savings = f.hours_per_month_manual - f.maintenance_hours_per_month
        
        if net_savings <= 0:
            return 0.0
        
        # Score based on ROI ratio (hours saved / hours to build)
        if f.hours_to_automate <= 0:
            return 1.0
        
        monthly_roi = net_savings / f.hours_to_automate
        
        # Map to 0-1 score
        # <0.1 = bad, 0.5+ = great
        return min(1.0, monthly_roi * 2)
    
    def _calc_consistency_score(self, f: ROIFactors) -> float:
        """Calculate consistency improvement score (0-1)."""
        if f.error_rate_manual <= 0:
            return 0.0
        
        # Error reduction ratio
        error_reduction = 1 - (f.error_rate_automated / f.error_rate_manual)
        
        # Weight by cost impact
        monthly_error_cost_before = f.error_rate_manual * f.hours_per_month_manual * f.cost_per_error
        
        # Normalize cost to score (assuming $1000/month is significant)
        cost_factor = min(1.0, monthly_error_cost_before / 1000)
        
        return error_reduction * (0.7 + 0.3 * cost_factor)
    
    def _calc_mttr_score(self, f: ROIFactors) -> float:
        """Calculate MTTR reduction score (0-1)."""
        if f.mttr_manual_minutes <= 0:
            return 0.0
        
        # MTTR reduction ratio
        mttr_reduction = 1 - (f.mttr_automated_minutes / f.mttr_manual_minutes)
        
        # Weight by incident frequency and cost
        monthly_downtime_before = f.mttr_manual_minutes * f.incidents_per_month
        monthly_downtime_after = f.mttr_automated_minutes * f.incidents_per_month
        downtime_saved = monthly_downtime_before - monthly_downtime_after
        
        # Normalize (100 minutes saved/month is significant)
        frequency_factor = min(1.0, downtime_saved / 100)
        
        return mttr_reduction * (0.6 + 0.4 * frequency_factor)
    
    def _calc_decoupling_score(self, f: ROIFactors) -> float:
        """Calculate operator decoupling score (0-1)."""
        score = 0.0
        
        # Few operators = higher decoupling value
        if f.required_operators_manual <= 1:
            score += 0.5  # Single point of failure - high value to automate
        elif f.required_operators_manual <= 2:
            score += 0.3
        else:
            score += 0.1
        
        # On-call burden
        # Normalize (20 hours/month is significant burden)
        on_call_factor = min(1.0, f.on_call_burden_hours / 20)
        score += 0.3 * on_call_factor
        
        # Cost of operator time
        monthly_operator_cost = f.on_call_burden_hours * f.operator_hourly_cost
        # Normalize (assuming $1000/month is significant)
        cost_factor = min(1.0, monthly_operator_cost / 1000)
        score += 0.2 * cost_factor
        
        return min(1.0, score)
    
    def _calc_extensibility_score(self, f: ROIFactors) -> float:
        """Calculate platform extensibility score (0-1)."""
        score = 0.0
        
        # Base score for enabling automation
        if f.enables_further_automation:
            score += 0.3
        
        # Dependent automations
        # Each dependent automation adds value
        score += min(0.4, f.dependent_automations * 0.1)
        
        # Reusability
        score += min(0.3, (f.reusability_factor - 1) * 0.15)
        
        return min(1.0, score)
    
    def _calc_annual_value(self, f: ROIFactors) -> float:
        """Calculate annual dollar value of automation."""
        value = 0.0
        
        # Time savings value
        hours_saved_monthly = f.hours_per_month_manual - f.maintenance_hours_per_month
        value += hours_saved_monthly * f.operator_hourly_cost * 12
        
        # Error reduction value
        errors_before = f.error_rate_manual * f.hours_per_month_manual / 10  # Per 10 hours
        errors_after = f.error_rate_automated * f.hours_per_month_manual / 10
        errors_avoided_monthly = errors_before - errors_after
        value += errors_avoided_monthly * f.cost_per_error * 12
        
        # MTTR reduction value
        downtime_saved_monthly = (
            (f.mttr_manual_minutes - f.mttr_automated_minutes) * f.incidents_per_month
        )
        value += downtime_saved_monthly * f.downtime_cost_per_minute * 12
        
        # Strategic multipliers
        if f.supports_critical_service:
            value *= 1.5
        if f.regulatory_requirement:
            value *= 1.3
        if f.customer_facing_impact:
            value *= 1.2
        
        return value
    
    def _calc_payback_months(self, f: ROIFactors, annual_value: float) -> float:
        """Calculate months until automation pays for itself."""
        if annual_value <= 0:
            return float('inf')
        
        # Cost is automation hours at operator rate
        automation_cost = f.hours_to_automate * f.operator_hourly_cost
        
        monthly_value = annual_value / 12
        
        if monthly_value <= 0:
            return float('inf')
        
        return automation_cost / monthly_value
    
    def _generate_recommendation(self, assessment: ROIAssessment) -> str:
        """Generate recommendation based on assessment."""
        priority = assessment.priority
        payback = assessment.payback_months
        
        # Find top scoring factors
        scores = [
            ("consistency", assessment.consistency_score),
            ("extensibility", assessment.extensibility_score),
            ("mttr_reduction", assessment.mttr_score),
            ("decoupling", assessment.decoupling_score),
            ("time_savings", assessment.time_savings_score),
        ]
        top_factor = max(scores, key=lambda x: x[1])[0]
        
        if priority == "high":
            rec = f"STRONGLY RECOMMENDED. "
            if payback < 3:
                rec += f"Payback in {payback:.1f} months. "
            rec += f"Primary value: {top_factor.replace('_', ' ')}. "
            rec += "Implement as soon as possible."
        
        elif priority == "medium":
            rec = f"RECOMMENDED when resources allow. "
            rec += f"Payback in {payback:.1f} months. "
            rec += f"Primary value: {top_factor.replace('_', ' ')}."
        
        else:  # low
            rec = "CONSIDER carefully. "
            if payback > 12:
                rec += f"Long payback period ({payback:.1f} months). "
            rec += "May be better to focus on higher-value automations first."
        
        return rec
    
    def compare(self, assessments: list[ROIAssessment]) -> list[dict]:
        """Compare multiple automation opportunities."""
        comparisons = []
        for a in assessments:
            comparisons.append({
                "name": a.automation_name,
                "weighted_score": a.weighted_score,
                "priority": a.priority,
                "payback_months": a.payback_months,
                "annual_value": a.annual_value,
            })
        
        # Sort by weighted score (highest first)
        return sorted(comparisons, key=lambda x: x["weighted_score"], reverse=True)
    
    def quick_estimate(
        self,
        name: str,
        hours_per_month: float,
        hours_to_automate: float,
        error_prone: bool = True,
        critical: bool = False,
    ) -> ROIAssessment:
        """Quick ROI estimate with minimal inputs."""
        factors = ROIFactors(
            hours_per_month_manual=hours_per_month,
            hours_to_automate=hours_to_automate,
            error_rate_manual=0.05 if error_prone else 0.01,
            supports_critical_service=critical,
        )
        return self.calculate(name, factors)
