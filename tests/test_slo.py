"""
Tests for SLO Module

Tests error budget calculation, availability tracking, and SLO context.
"""

import pytest
from datetime import datetime, timedelta, timezone

from autosre.slo.error_budget import (
    ErrorBudget,
    ErrorBudgetCalculator,
    ErrorBudgetStatus,
    DeploymentDecision,
)
from autosre.slo.availability import (
    AvailabilityCalculator,
    ServiceAvailability,
    EndpointAvailability,
    AvailabilityTracker,
)
from autosre.slo.context import (
    SLOContextProvider,
    SLOContext,
    IncidentBudgetImpact,
)


class TestErrorBudget:
    """Tests for ErrorBudget class."""
    
    def test_error_budget_creation(self):
        """Test creating an error budget."""
        budget = ErrorBudget(
            slo=0.999,
            error_budget=0.001,
            consumed=0.0005,
            remaining=0.0005,
            percentage_remaining=50.0,
            status=ErrorBudgetStatus.WARNING,
            window_minutes=43200,
            allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=21.6,
            remaining_downtime_minutes=21.6,
            burn_rate=1.0,
            time_until_exhausted=timedelta(hours=12),
            service="api-gateway",
        )
        
        assert budget.slo == 0.999
        assert budget.error_budget == 0.001
        assert budget.percentage_remaining == 50.0
        assert budget.status == ErrorBudgetStatus.WARNING
        assert budget.can_deploy  # 50% > 20%
    
    def test_can_deploy_threshold(self):
        """Test deployment decision based on budget."""
        # Healthy budget - can deploy
        healthy = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.0001,
            remaining=0.0009, percentage_remaining=90.0,
            status=ErrorBudgetStatus.HEALTHY,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=4.32, remaining_downtime_minutes=38.88,
            burn_rate=0.1, time_until_exhausted=None, service="test",
        )
        assert healthy.can_deploy
        
        # Critical budget - cannot deploy
        critical = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.00085,
            remaining=0.00015, percentage_remaining=15.0,
            status=ErrorBudgetStatus.CRITICAL,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=36.72, remaining_downtime_minutes=6.48,
            burn_rate=2.0, time_until_exhausted=timedelta(hours=2), service="test",
        )
        assert not critical.can_deploy
    
    def test_deployment_decision_exhausted(self):
        """Test deployment blocked when budget exhausted."""
        budget = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.001,
            remaining=0, percentage_remaining=0,
            status=ErrorBudgetStatus.EXHAUSTED,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=43.2, remaining_downtime_minutes=0,
            burn_rate=5.0, time_until_exhausted=None, service="test",
        )
        
        decision = budget.get_deployment_decision()
        
        assert not decision.can_deploy
        assert decision.risk_level == "critical"
        assert "exhausted" in decision.reason.lower()
        assert len(decision.recommendations) > 0
    
    def test_deployment_decision_with_risk(self):
        """Test deployment decisions consider deploy risk."""
        budget = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.00085,
            remaining=0.00015, percentage_remaining=15.0,
            status=ErrorBudgetStatus.CRITICAL,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=36.72, remaining_downtime_minutes=6.48,
            burn_rate=2.0, time_until_exhausted=timedelta(hours=2), service="test",
        )
        
        # High-risk deploy blocked at critical budget
        high_risk = budget.get_deployment_decision(deploy_risk="high")
        assert not high_risk.can_deploy
        
        # Low-risk deploy allowed at critical budget
        low_risk = budget.get_deployment_decision(deploy_risk="low")
        assert low_risk.can_deploy
    
    def test_to_dict(self):
        """Test serialization."""
        budget = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.0005,
            remaining=0.0005, percentage_remaining=50.0,
            status=ErrorBudgetStatus.WARNING,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=21.6, remaining_downtime_minutes=21.6,
            burn_rate=1.0, time_until_exhausted=timedelta(hours=12), service="test",
        )
        
        d = budget.to_dict()
        
        assert d["slo"] == 0.999
        assert d["slo_percent"] == "99.900%"
        assert d["status"] == "warning"
        assert d["time_until_exhausted_hours"] == 12.0


class TestErrorBudgetCalculator:
    """Tests for ErrorBudgetCalculator."""
    
    def test_calculate_basic(self):
        """Test basic budget calculation."""
        calc = ErrorBudgetCalculator()
        
        budget = calc.calculate(
            service="api",
            total_requests=1000000,
            failed_requests=500,  # 0.05% error rate
            window_minutes=43200,
            slo=0.999,  # 0.1% error budget
        )
        
        assert budget.slo == 0.999
        assert abs(budget.error_budget - 0.001) < 1e-9  # Floating point comparison
        assert budget.status == ErrorBudgetStatus.HEALTHY  # 50% consumed is healthy
        assert 45 < budget.percentage_remaining < 55
    
    def test_calculate_healthy(self):
        """Test calculation with healthy budget."""
        calc = ErrorBudgetCalculator()
        
        budget = calc.calculate(
            service="api",
            total_requests=1000000,
            failed_requests=100,  # 0.01% error rate
            window_minutes=43200,
            slo=0.999,
        )
        
        assert budget.status == ErrorBudgetStatus.HEALTHY
        assert budget.percentage_remaining > 80
    
    def test_calculate_exhausted(self):
        """Test calculation with exhausted budget."""
        calc = ErrorBudgetCalculator()
        
        budget = calc.calculate(
            service="api",
            total_requests=1000000,
            failed_requests=2000,  # 0.2% error rate > 0.1% budget
            window_minutes=43200,
            slo=0.999,
        )
        
        assert budget.status == ErrorBudgetStatus.EXHAUSTED
        assert budget.percentage_remaining == 0
    
    def test_calculate_no_requests(self):
        """Test calculation with zero requests."""
        calc = ErrorBudgetCalculator()
        
        budget = calc.calculate(
            service="api",
            total_requests=0,
            failed_requests=0,
            window_minutes=43200,
        )
        
        # No requests = 100% available
        assert budget.status == ErrorBudgetStatus.HEALTHY
        assert budget.percentage_remaining == 100
    
    def test_configure_slo(self):
        """Test SLO configuration."""
        calc = ErrorBudgetCalculator()
        
        calc.configure_slo("critical-service", 0.9999)
        
        budget = calc.calculate(
            service="critical-service",
            total_requests=1000000,
            failed_requests=50,
            window_minutes=43200,
        )
        
        assert budget.slo == 0.9999
        assert abs(budget.error_budget - 0.0001) < 1e-9  # Floating point comparison
    
    def test_default_slos(self):
        """Test default SLOs by service type."""
        calc = ErrorBudgetCalculator()
        
        assert calc.get_slo("api", "api") == 0.999
        assert calc.get_slo("web", "web") == 0.995
        assert calc.get_slo("batch", "batch") == 0.99
        assert calc.get_slo("critical", "critical") == 0.9999
    
    def test_burn_rate(self):
        """Test burn rate calculation."""
        calc = ErrorBudgetCalculator()
        
        # Burning at 2x rate
        budget = calc.calculate(
            service="api",
            total_requests=1000000,
            failed_requests=2000,  # 0.2% vs 0.1% budget
            window_minutes=43200,
            slo=0.999,
            current_burn_rate=2.0,
        )
        
        assert budget.burn_rate == 2.0
    
    def test_downtime_calculation(self):
        """Test downtime calculations."""
        calc = ErrorBudgetCalculator()
        
        # 99.9% SLO over 30 days = ~43 minutes allowed downtime
        budget = calc.calculate(
            service="api",
            total_requests=1000000,
            failed_requests=500,
            window_minutes=43200,  # 30 days in minutes
            slo=0.999,
        )
        
        # 0.1% of 43200 minutes = 43.2 minutes
        assert 43 < budget.allowed_downtime_minutes < 44


class TestAvailabilityCalculator:
    """Tests for AvailabilityCalculator."""
    
    def test_calculate_basic(self):
        """Test basic availability calculation."""
        calc = AvailabilityCalculator()
        
        result = calc.calculate(
            service="api",
            total_requests=10000,
            successful_requests=9900,
        )
        
        assert result.availability == 0.99
        assert result.availability_percent == 99.0
        assert result.failed_requests == 100
    
    def test_calculate_with_slo(self):
        """Test availability with SLO comparison."""
        calc = AvailabilityCalculator()
        
        result = calc.calculate(
            service="api",
            total_requests=10000,
            successful_requests=9990,
            slo_target=0.999,
        )
        
        assert result.slo_met
        assert result.slo_margin == 0.0  # 99.9% exactly
        
        # Below SLO
        result2 = calc.calculate(
            service="api",
            total_requests=10000,
            successful_requests=9980,
            slo_target=0.999,
        )
        
        assert not result2.slo_met
        assert result2.slo_margin < 0
    
    def test_calculate_no_requests(self):
        """Test availability with zero requests."""
        calc = AvailabilityCalculator()
        
        result = calc.calculate(
            service="api",
            total_requests=0,
            successful_requests=0,
        )
        
        # No requests = 100% available (no failures)
        assert result.availability == 1.0
    
    def test_endpoint_breakdown(self):
        """Test per-endpoint availability."""
        calc = AvailabilityCalculator()
        
        endpoint_data = [
            {"endpoint": "/api/users", "method": "GET", "total": 1000, "successful": 990},
            {"endpoint": "/api/orders", "method": "POST", "total": 500, "successful": 450},
        ]
        
        result = calc.calculate(
            service="api",
            total_requests=1500,
            successful_requests=1440,
            endpoint_data=endpoint_data,
        )
        
        assert len(result.endpoints) == 2
        
        # Check worst endpoints
        worst = result.worst_endpoints
        assert worst[0].endpoint == "/api/orders"  # 90% vs 99%
        assert worst[0].availability == 0.9
    
    def test_get_summary(self):
        """Test human-readable summary."""
        calc = AvailabilityCalculator()
        
        endpoint_data = [
            {"endpoint": "/api/slow", "method": "GET", "total": 100, "successful": 80},
        ]
        
        result = calc.calculate(
            service="api",
            total_requests=10000,
            successful_requests=9900,
            slo_target=0.999,
            endpoint_data=endpoint_data,
        )
        
        summary = result.get_summary()
        
        assert "api" in summary
        assert "99.0" in summary or "99%" in summary
        assert "Below SLO" in summary or "Not Met" in summary


class TestAvailabilityTracker:
    """Tests for AvailabilityTracker."""
    
    def test_record_and_trend(self):
        """Test recording and trend analysis."""
        tracker = AvailabilityTracker()
        
        # Record declining availability
        tracker.record("api", 0.999)
        tracker.record("api", 0.998)
        tracker.record("api", 0.997)
        tracker.record("api", 0.996)
        tracker.record("api", 0.995)
        
        trend = tracker.get_trend("api", hours=24)
        
        assert trend["data_points"] == 5
        assert trend["trend"] == "degrading"
        assert trend["current"] == 0.995
        assert trend["max"] == 0.999
    
    def test_empty_trend(self):
        """Test trend with no data."""
        tracker = AvailabilityTracker()
        
        trend = tracker.get_trend("unknown", hours=24)
        
        assert trend["data_points"] == 0


class TestSLOContext:
    """Tests for SLOContext."""
    
    def test_investigation_context(self):
        """Test generating investigation context."""
        availability = ServiceAvailability(
            service="api",
            total_requests=10000,
            successful_requests=9900,
            failed_requests=100,
            availability=0.99,
            availability_percent=99.0,
            slo_target=0.999,
            slo_met=False,
            slo_margin=-0.009,
        )
        
        budget = ErrorBudget(
            slo=0.999, error_budget=0.001, consumed=0.001,
            remaining=0, percentage_remaining=0,
            status=ErrorBudgetStatus.EXHAUSTED,
            window_minutes=43200, allowed_downtime_minutes=43.2,
            consumed_downtime_minutes=43.2, remaining_downtime_minutes=0,
            burn_rate=3.0, time_until_exhausted=None, service="api",
        )
        
        context = SLOContext(
            service="api",
            current_availability=availability,
            current_budget=budget,
        )
        
        text = context.get_investigation_context()
        
        assert "api" in text
        assert "99" in text  # Availability
        assert "EXHAUSTED" in text
        assert "Deployments BLOCKED" in text


class TestIncidentBudgetImpact:
    """Tests for IncidentBudgetImpact."""
    
    def test_impact_calculation(self):
        """Test incident impact calculation."""
        impact = IncidentBudgetImpact(
            incident_id="INC001",
            service="api",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            ended_at=datetime.now(timezone.utc),
            duration_minutes=30,
            requests_affected=10000,
            requests_failed=500,
            budget_consumed_percent=25.0,
            budget_remaining_after=75.0,
            monthly_budget_minutes=43.2,
            severity="medium",
        )
        
        assert impact.budget_consumed_percent == 25.0
        assert impact.severity == "medium"
        
        summary = impact.get_summary()
        assert "30" in summary  # Duration
        assert "medium" in summary.lower() or "MEDIUM" in summary


class TestSLOContextProvider:
    """Tests for SLOContextProvider."""
    
    def test_configure_service_slo(self):
        """Test configuring service SLOs."""
        provider = SLOContextProvider()
        
        provider.configure_service_slo("critical-api", 0.9999, window_days=30)
        
        # The budget calculator should use the configured SLO
        assert provider.budget_calc.get_slo("critical-api") == 0.9999
    
    def test_get_context_with_incident(self):
        """Test getting context with incident information."""
        provider = SLOContextProvider()
        provider.configure_service_slo("api", 0.999)
        
        context = provider.get_context(
            service="api",
            incident_id="INC001",
            incident_start=datetime.now(timezone.utc) - timedelta(minutes=15),
            incident_end=datetime.now(timezone.utc),
            requests_failed=1000,
            requests_total=10000,
        )
        
        assert context.service == "api"
        assert context.incident_impact is not None
        assert abs(context.incident_impact.duration_minutes - 15) < 0.1  # Allow small timing variance
    
    def test_recommendations_generated(self):
        """Test that recommendations are generated."""
        provider = SLOContextProvider()
        
        context = SLOContext(
            service="api",
            current_budget=ErrorBudget(
                slo=0.999, error_budget=0.001, consumed=0.001,
                remaining=0, percentage_remaining=0,
                status=ErrorBudgetStatus.EXHAUSTED,
                window_minutes=43200, allowed_downtime_minutes=43.2,
                consumed_downtime_minutes=43.2, remaining_downtime_minutes=0,
                burn_rate=3.0, time_until_exhausted=None, service="api",
            ),
        )
        
        recommendations = provider._generate_recommendations(context)
        
        assert len(recommendations) > 0
        assert any("exhausted" in r.lower() or "halt" in r.lower() for r in recommendations)
