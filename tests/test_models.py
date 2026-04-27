"""
Tests for foundation models.
"""

import pytest
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from autosre.foundation.models import (
    Service,
    ServiceStatus,
    Ownership,
    ChangeEvent,
    ChangeType,
    Runbook,
    Alert,
    Incident,
    Severity,
)


class TestService:
    """Tests for Service model."""
    
    def test_service_creation(self):
        """Test basic service creation."""
        service = Service(
            name="api-gateway",
            namespace="production",
            cluster="main",
            status=ServiceStatus.HEALTHY,
            replicas=3,
            ready_replicas=3,
        )
        
        assert service.name == "api-gateway"
        assert service.namespace == "production"
        assert service.is_healthy is True
    
    def test_service_unhealthy(self):
        """Test unhealthy service detection."""
        service = Service(
            name="broken-service",
            status=ServiceStatus.DEGRADED,
            replicas=3,
            ready_replicas=2,
        )
        
        assert service.is_healthy is False
    
    def test_service_dependencies(self):
        """Test service with dependencies."""
        service = Service(
            name="frontend",
            dependencies=["api-gateway", "auth-service"],
            dependents=["cdn"],
        )
        
        assert len(service.dependencies) == 2
        assert "api-gateway" in service.dependencies


class TestOwnership:
    """Tests for Ownership model."""
    
    def test_ownership_creation(self):
        """Test basic ownership creation."""
        ownership = Ownership(
            service_name="payment-service",
            team="payments",
            slack_channel="#payments-alerts",
            tier=1,
            slo_target=99.99,
        )
        
        assert ownership.service_name == "payment-service"
        assert ownership.team == "payments"
        assert ownership.tier == 1
    
    def test_ownership_with_escalation(self):
        """Test ownership with escalation contacts."""
        ownership = Ownership(
            service_name="critical-service",
            team="platform",
            escalation_contacts=["manager@example.com", "director@example.com"],
        )
        
        assert len(ownership.escalation_contacts) == 2


class TestChangeEvent:
    """Tests for ChangeEvent model."""
    
    def test_change_event_creation(self):
        """Test basic change event creation."""
        change = ChangeEvent(
            id="change-001",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-gateway",
            description="Deployed v2.0.0",
            author="developer@example.com",
            commit_sha="abc123",
        )
        
        assert change.id == "change-001"
        assert change.change_type == ChangeType.DEPLOYMENT
        assert change.successful is True
    
    def test_rollback_change(self):
        """Test rolled back change."""
        change = ChangeEvent(
            id="change-002",
            change_type=ChangeType.ROLLBACK,
            service_name="broken-service",
            description="Rollback to v1.9.0",
            author="ops@example.com",
            previous_version="v2.0.0",
            new_version="v1.9.0",
            rolled_back=True,
        )
        
        assert change.rolled_back is True
        assert change.change_type == ChangeType.ROLLBACK


class TestAlert:
    """Tests for Alert model."""
    
    def test_alert_creation(self):
        """Test basic alert creation."""
        alert = Alert(
            id="alert-001",
            name="HighCPUUsage",
            severity=Severity.HIGH,
            service_name="api-gateway",
            summary="CPU usage above 90%",
        )
        
        assert alert.name == "HighCPUUsage"
        assert alert.is_firing is True
    
    def test_resolved_alert(self):
        """Test resolved alert."""
        alert = Alert(
            id="alert-002",
            name="HighLatency",
            summary="Latency above threshold",
            resolved_at=utcnow(),
        )
        
        assert alert.is_firing is False


class TestIncident:
    """Tests for Incident model."""
    
    def test_incident_creation(self):
        """Test basic incident creation."""
        incident = Incident(
            id="inc-001",
            title="Payment processing failure",
            severity=Severity.CRITICAL,
            services=["payment-service", "checkout-service"],
        )
        
        assert incident.id == "inc-001"
        assert incident.is_resolved is False
    
    def test_incident_metrics(self):
        """Test incident timing metrics."""
        started = datetime(2024, 1, 15, 10, 0, 0)
        detected = datetime(2024, 1, 15, 10, 5, 0)
        resolved = datetime(2024, 1, 15, 10, 30, 0)
        
        incident = Incident(
            id="inc-002",
            title="Database outage",
            started_at=started,
            detected_at=detected,
            resolved_at=resolved,
        )
        
        assert incident.is_resolved is True
        assert incident.time_to_detect == 300  # 5 minutes
        assert incident.time_to_resolve == 1800  # 30 minutes
