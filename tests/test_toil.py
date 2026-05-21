"""Tests for toil tracking and automation modules."""

import pytest
from datetime import datetime, timedelta

from autosre.toil.classifier import (
    ToilClassifier,
    ToilAssessment,
    TaskInput,
    TOIL_CRITERIA,
    is_toil,
)
from autosre.toil.budget import (
    ToilBudgetTracker,
    ToilCategory,
    ToilEntry,
    TOIL_CAP,
    TOIL_WARNING,
    AlertLevel,
)
from autosre.toil.dashboard import ToilDashboard
from autosre.automation.maturity import (
    AutomationMaturityModel,
    MaturityLevel,
    MaturityIndicators,
)
from autosre.automation.roi import (
    AutomationROICalculator,
    ROIFactors,
)


class TestToilClassifier:
    """Tests for ToilClassifier."""
    
    def test_toil_criteria_defined(self):
        """Test that all 6 toil criteria are defined."""
        assert len(TOIL_CRITERIA) == 6
        assert "manual" in TOIL_CRITERIA
        assert "repetitive" in TOIL_CRITERIA
        assert "automatable" in TOIL_CRITERIA
        assert "tactical" in TOIL_CRITERIA
        assert "no_enduring_value" in TOIL_CRITERIA
        assert "scales_with_growth" in TOIL_CRITERIA
    
    def test_obvious_toil_task(self):
        """Test classification of obvious toil task."""
        classifier = ToilClassifier()
        
        task = TaskInput(
            name="Restart failing pods",
            description="Manually restart pods when memory alerts fire",
            frequency="daily",
            duration_minutes=15,
            triggered_by="alert",
            has_runbook=True,
        )
        
        assessment = classifier.is_toil(task)
        
        assert assessment.is_toil is True
        assert assessment.score > 0.5
        assert len(assessment.criteria_matched) >= 3
        assert assessment.automation_potential in ["high", "medium"]
    
    def test_engineering_work_not_toil(self):
        """Test that engineering work is not classified as toil."""
        classifier = ToilClassifier()
        
        task = TaskInput(
            name="Investigate memory leak in auth service",
            description="Debug and analyze memory growth patterns",
            frequency="ad-hoc",
            duration_minutes=240,
            requires_human_judgment=True,
            triggered_by="manual",
        )
        
        assessment = classifier.is_toil(task)
        
        # Should not be classified as toil
        assert assessment.is_toil is False
        assert "engineering pattern detected" in assessment.reasoning.lower() or assessment.score < 0.5
    
    def test_capacity_planning_not_toil(self):
        """Test that capacity planning is not toil (has enduring value)."""
        classifier = ToilClassifier()
        
        task = TaskInput(
            name="Capacity planning review",
            description="Analyze growth trends and plan infrastructure scaling",
            frequency="monthly",
            duration_minutes=120,
            requires_human_judgment=True,
        )
        
        assessment = classifier.is_toil(task)
        
        # Has enduring value, not toil
        assert assessment.is_toil is False
    
    def test_hours_per_month_calculation(self):
        """Test that hours per month is calculated correctly."""
        classifier = ToilClassifier()
        
        # Daily 30-min task = ~15 hours/month
        task = TaskInput(
            name="Daily health check",
            frequency="daily",
            duration_minutes=30,
        )
        
        assessment = classifier.is_toil(task)
        
        # 30 min * 30 days / 60 = 15 hours
        assert 14 <= assessment.estimated_hours_per_month <= 16
    
    def test_automation_roi_calculation(self):
        """Test automation ROI calculation."""
        classifier = ToilClassifier()
        
        task = TaskInput(
            name="Clear cache",
            frequency="weekly",
            duration_minutes=60,
            automation_hours_estimate=4.0,  # 4 hours to automate
        )
        
        assessment = classifier.is_toil(task)
        
        # ~4.3 hours/month saved, 4 hours to automate
        # ROI should be ~1.0 (pays off in 1 month)
        assert assessment.automation_roi > 0.5
    
    def test_convenience_function(self):
        """Test the is_toil() convenience function."""
        task = TaskInput(
            name="Manual deployment",
            frequency="weekly",
        )
        
        assessment = is_toil(task)
        
        assert isinstance(assessment, ToilAssessment)


class TestToilBudgetTracker:
    """Tests for ToilBudgetTracker."""
    
    def test_toil_cap_defined(self):
        """Test that TOIL_CAP is 50%."""
        assert TOIL_CAP == 0.50
    
    def test_record_toil(self):
        """Test recording toil entries."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=5)
        
        entry = tracker.record_toil(
            engineer="alice",
            category=ToilCategory.INCIDENT_RESPONSE,
            description="Responded to alert",
            hours=2.0,
            service="api-gateway",
        )
        
        assert entry.engineer == "alice"
        assert entry.hours == 2.0
        assert len(tracker.entries) == 1
    
    def test_toil_ratio_calculation(self):
        """Test team toil ratio calculation."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=5, hours_per_week=40)
        
        # Add 100 hours of toil over 30 days
        # Team capacity: 5 people * 40 hours * 4.3 weeks = 860 hours
        for i in range(10):
            tracker.record_toil(
                engineer=f"eng{i % 5}",
                category=ToilCategory.MAINTENANCE,
                description="Maintenance task",
                hours=10.0,
                timestamp=datetime.now() - timedelta(days=i),
            )
        
        status = tracker.get_team_toil_ratio(period_days=30)
        
        # 100 hours / ~860 hours ≈ 11.6%
        assert 0.10 <= status.toil_ratio <= 0.15
        assert status.alert_level == AlertLevel.OK
    
    def test_budget_exceeded_alert(self):
        """Test alert when toil exceeds budget."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=2, hours_per_week=40)
        
        # Add enough toil to exceed 50%
        # Team capacity: 2 * 40 * 4.3 ≈ 344 hours/month
        # Need > 172 hours of toil
        for i in range(20):
            tracker.record_toil(
                engineer="eng1",
                category=ToilCategory.INCIDENT_RESPONSE,
                description="Incident work",
                hours=10.0,
                timestamp=datetime.now() - timedelta(days=i % 30),
            )
        
        status = tracker.get_team_toil_ratio(period_days=30)
        
        assert status.toil_ratio > TOIL_CAP
        assert status.alert_level == AlertLevel.CRITICAL
    
    def test_warning_threshold(self):
        """Test warning alert at 40%."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=2, hours_per_week=40)
        
        # Team capacity ≈ 344 hours/month
        # 40% = 137.6 hours, 50% = 172 hours
        # Add 150 hours
        for i in range(15):
            tracker.record_toil(
                engineer="eng1",
                category=ToilCategory.MAINTENANCE,
                description="Maintenance",
                hours=10.0,
                timestamp=datetime.now() - timedelta(days=i % 30),
            )
        
        status = tracker.get_team_toil_ratio(period_days=30)
        
        # Should be in warning range
        assert TOIL_WARNING <= status.toil_ratio <= TOIL_CAP
        assert status.alert_level == AlertLevel.WARNING
    
    def test_reduction_opportunities(self):
        """Test identifying toil reduction opportunities."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=5)
        
        # Add varied toil
        categories = [
            (ToilCategory.INCIDENT_RESPONSE, 20),
            (ToilCategory.MANUAL_SCALING, 15),
            (ToilCategory.DEPLOYMENT, 10),
        ]
        
        for cat, hours in categories:
            tracker.record_toil(
                engineer="eng1",
                category=cat,
                description=f"{cat.value} work",
                hours=hours,
            )
        
        opportunities = tracker.get_toil_reduction_opportunities()
        
        assert len(opportunities) > 0
        # Should be sorted by ROI
        for i in range(len(opportunities) - 1):
            assert opportunities[i].roi_months <= opportunities[i + 1].roi_months
    
    def test_check_budget(self):
        """Test budget check function."""
        tracker = ToilBudgetTracker(team="sre-team", team_size=5)
        
        within, message = tracker.check_budget()
        
        assert within is True
        assert "within budget" in message.lower()


class TestToilDashboard:
    """Tests for ToilDashboard."""
    
    def test_dashboard_summary(self):
        """Test dashboard summary generation."""
        tracker = ToilBudgetTracker(team="platform", team_size=3)
        tracker.record_toil(
            engineer="eng1",
            category=ToilCategory.DEPLOYMENT,
            description="Manual deploy",
            hours=5.0,
        )
        
        dashboard = ToilDashboard(tracker)
        summary = dashboard.get_summary()
        
        assert summary.team == "platform"
        assert summary.current_toil_ratio >= 0
        assert summary.target_ratio == TOIL_CAP
        assert summary.health_status in ["healthy", "warning", "critical"]
    
    def test_full_dashboard_data(self):
        """Test full dashboard data export."""
        tracker = ToilBudgetTracker(team="platform", team_size=3)
        tracker.record_toil(
            engineer="eng1",
            category=ToilCategory.MAINTENANCE,
            description="Maintenance",
            hours=5.0,
        )
        
        dashboard = ToilDashboard(tracker)
        data = dashboard.get_full_dashboard_data()
        
        assert "summary" in data
        assert "toil_vs_engineering" in data
        assert "toil_by_category" in data
        assert "automation_opportunities" in data
        assert "generated_at" in data
    
    def test_generate_report(self):
        """Test text report generation."""
        tracker = ToilBudgetTracker(team="platform", team_size=3)
        tracker.record_toil(
            engineer="eng1",
            category=ToilCategory.DEPLOYMENT,
            description="Deploy",
            hours=10.0,
        )
        
        dashboard = ToilDashboard(tracker)
        report = dashboard.generate_report()
        
        assert "Toil Report" in report
        assert "platform" in report
        assert "Toil Ratio" in report


class TestAutomationMaturityModel:
    """Tests for AutomationMaturityModel."""
    
    def test_maturity_levels_defined(self):
        """Test all 5 maturity levels are defined."""
        assert MaturityLevel.MANUAL_OPS == 1
        assert MaturityLevel.PERSONAL_SCRIPTS == 2
        assert MaturityLevel.GENERIC_SHARED == 3
        assert MaturityLevel.SHIPS_WITH_AUTOMATION == 4
        assert MaturityLevel.SELF_HEALING == 5
    
    def test_assess_manual_ops(self):
        """Test assessment of manual operations level."""
        model = AutomationMaturityModel()
        
        indicators = MaturityIndicators(
            has_runbooks=True,
            runbooks_are_primary_tool=True,
            manual_intervention_rate=0.9,
            automation_coverage=0.05,
        )
        
        assessment = model.assess("legacy-service", indicators=indicators)
        
        assert assessment.current_level == MaturityLevel.MANUAL_OPS
        assert len(assessment.gaps) > 0
        assert len(assessment.recommendations) > 0
    
    def test_assess_self_healing(self):
        """Test assessment of self-healing level."""
        model = AutomationMaturityModel()
        
        indicators = MaturityIndicators(
            has_runbooks=True,
            runbooks_are_primary_tool=False,
            has_personal_scripts=True,
            scripts_are_shared=True,
            has_shared_repo=True,
            has_documentation=True,
            has_code_review=True,
            has_monitoring_integration=True,
            automation_in_design=True,
            operators_in_design=True,
            automation_in_dod=True,
            auto_detection=True,
            auto_remediation=True,
            chaos_engineering=True,
            human_for_novel_only=True,
            manual_intervention_rate=0.05,
            automation_coverage=0.95,
            incident_recurrence_rate=0.05,
        )
        
        assessment = model.assess("modern-service", indicators=indicators)
        
        assert assessment.current_level == MaturityLevel.SELF_HEALING
        assert assessment.score >= 4.5
    
    def test_upgrade_plan(self):
        """Test upgrade plan generation."""
        model = AutomationMaturityModel()
        
        indicators = MaturityIndicators(
            has_runbooks=True,
            has_personal_scripts=True,
            scripts_are_shared=False,
        )
        
        model.assess(
            "mid-service",
            indicators=indicators,
            target_level=MaturityLevel.SHIPS_WITH_AUTOMATION,
        )
        
        plan = model.get_upgrade_plan("mid-service")
        
        assert "phases" in plan
        assert len(plan["phases"]) > 0
    
    def test_default_target_level(self):
        """Test default target level is Level 4."""
        model = AutomationMaturityModel()
        
        indicators = MaturityIndicators()
        assessment = model.assess("test-service", indicators=indicators)
        
        assert assessment.target_level == MaturityLevel.SHIPS_WITH_AUTOMATION


class TestAutomationROICalculator:
    """Tests for AutomationROICalculator."""
    
    def test_time_savings_least_important(self):
        """Test that time savings has lowest weight."""
        from autosre.automation.roi import FACTOR_WEIGHTS, ROIFactor
        
        weights = list(FACTOR_WEIGHTS.values())
        time_weight = FACTOR_WEIGHTS[ROIFactor.TIME_SAVINGS]
        
        # Time savings should be the lowest weight
        assert time_weight == min(weights)
        assert time_weight == 0.10
    
    def test_consistency_most_important(self):
        """Test that consistency has highest weight."""
        from autosre.automation.roi import FACTOR_WEIGHTS, ROIFactor
        
        assert FACTOR_WEIGHTS[ROIFactor.CONSISTENCY] == 0.30
    
    def test_calculate_roi(self):
        """Test ROI calculation."""
        calc = AutomationROICalculator()
        
        factors = ROIFactors(
            hours_per_month_manual=20.0,
            hours_to_automate=40.0,
            error_rate_manual=0.10,
            error_rate_automated=0.001,
            mttr_manual_minutes=60,
            mttr_automated_minutes=5,
            incidents_per_month=10,
        )
        
        assessment = calc.calculate("test-automation", factors)
        
        assert assessment.weighted_score >= 0
        assert assessment.weighted_score <= 1
        assert assessment.payback_months > 0
        assert assessment.priority in ["high", "medium", "low"]
    
    def test_quick_estimate(self):
        """Test quick ROI estimate."""
        calc = AutomationROICalculator()
        
        assessment = calc.quick_estimate(
            name="Quick automation",
            hours_per_month=10.0,
            hours_to_automate=20.0,
            error_prone=True,
        )
        
        assert assessment.automation_name == "Quick automation"
        assert assessment.weighted_score >= 0
    
    def test_score_breakdown(self):
        """Test score breakdown includes all factors."""
        calc = AutomationROICalculator()
        
        factors = ROIFactors()
        assessment = calc.calculate("test", factors)
        
        breakdown = assessment.get_score_breakdown()
        
        assert len(breakdown) == 5
        factor_names = {b["factor"] for b in breakdown}
        assert "Consistency Improvement" in factor_names
        assert "Platform Extensibility" in factor_names
        assert "MTTR Reduction" in factor_names
        assert "Operator Decoupling" in factor_names
        assert "Time Savings" in factor_names
    
    def test_compare_automations(self):
        """Test comparing multiple automation opportunities."""
        calc = AutomationROICalculator()
        
        assessments = [
            calc.quick_estimate("Low value", hours_per_month=2, hours_to_automate=40),
            calc.quick_estimate("High value", hours_per_month=40, hours_to_automate=20),
            calc.quick_estimate("Medium value", hours_per_month=10, hours_to_automate=20),
        ]
        
        comparison = calc.compare(assessments)
        
        assert len(comparison) == 3
        # Should be sorted by weighted score
        assert comparison[0]["weighted_score"] >= comparison[1]["weighted_score"]
        assert comparison[1]["weighted_score"] >= comparison[2]["weighted_score"]


class TestIntegration:
    """Integration tests across modules."""
    
    def test_toil_to_automation_opportunity(self):
        """Test flow from toil identification to automation ROI."""
        # 1. Classify task as toil
        classifier = ToilClassifier()
        task = TaskInput(
            name="Manual certificate rotation",
            description="Rotate SSL certificates when they expire",
            frequency="monthly",
            duration_minutes=120,
            automation_hours_estimate=16.0,
        )
        
        toil_assessment = classifier.is_toil(task)
        
        # 2. Track it
        tracker = ToilBudgetTracker(team="security", team_size=3)
        tracker.record_toil(
            engineer="alice",
            category=ToilCategory.MAINTENANCE,
            description=task.name,
            hours=toil_assessment.estimated_hours_per_month,
        )
        
        # 3. Calculate automation ROI
        calc = AutomationROICalculator()
        roi = calc.quick_estimate(
            name=task.name,
            hours_per_month=toil_assessment.estimated_hours_per_month,
            hours_to_automate=task.automation_hours_estimate,
        )
        
        # Verify flow
        assert toil_assessment.is_toil is True
        assert roi.weighted_score > 0
    
    def test_dashboard_with_maturity(self):
        """Test dashboard data alongside maturity assessment."""
        # Setup tracker with data
        tracker = ToilBudgetTracker(team="platform", team_size=4)
        for _ in range(5):
            tracker.record_toil(
                engineer="eng1",
                category=ToilCategory.DEPLOYMENT,
                description="Manual deploy",
                hours=3.0,
            )
        
        # Get dashboard
        dashboard = ToilDashboard(tracker)
        summary = dashboard.get_summary()
        
        # Assess maturity
        model = AutomationMaturityModel()
        maturity = model.assess(
            "platform-team",
            subject_type="team",
            indicators=MaturityIndicators(
                has_runbooks=True,
                has_personal_scripts=True,
                manual_intervention_rate=0.6,
            ),
        )
        
        # Both should provide useful insights
        assert summary.current_toil_ratio >= 0
        assert maturity.current_level >= MaturityLevel.MANUAL_OPS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
