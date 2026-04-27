"""
Tests for the context store.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from autosre.foundation.context_store import ContextStore
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


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create a context store with temporary database."""
    return ContextStore(db_path=temp_db)


class TestContextStoreServices:
    """Tests for service operations."""
    
    def test_add_and_get_service(self, store):
        """Test adding and retrieving a service."""
        service = Service(
            name="test-service",
            namespace="default",
            status=ServiceStatus.HEALTHY,
            replicas=2,
            ready_replicas=2,
        )
        
        store.add_service(service)
        retrieved = store.get_service("test-service")
        
        assert retrieved is not None
        assert retrieved.name == "test-service"
        assert retrieved.status == ServiceStatus.HEALTHY
    
    def test_list_services(self, store):
        """Test listing services."""
        store.add_service(Service(name="svc-1", namespace="ns1"))
        store.add_service(Service(name="svc-2", namespace="ns1"))
        store.add_service(Service(name="svc-3", namespace="ns2"))
        
        all_services = store.list_services()
        assert len(all_services) == 3
        
        ns1_services = store.list_services(namespace="ns1")
        assert len(ns1_services) == 2
    
    def test_update_service(self, store):
        """Test updating a service."""
        service = Service(name="update-test", status=ServiceStatus.HEALTHY)
        store.add_service(service)
        
        service.status = ServiceStatus.DEGRADED
        store.add_service(service)
        
        retrieved = store.get_service("update-test")
        assert retrieved.status == ServiceStatus.DEGRADED


class TestContextStoreOwnership:
    """Tests for ownership operations."""
    
    def test_set_and_get_ownership(self, store):
        """Test setting and retrieving ownership."""
        ownership = Ownership(
            service_name="owned-service",
            team="platform",
            tier=1,
        )
        
        store.set_ownership(ownership)
        retrieved = store.get_ownership("owned-service")
        
        assert retrieved is not None
        assert retrieved.team == "platform"
        assert retrieved.tier == 1
    
    def test_ownership_not_found(self, store):
        """Test getting ownership for non-existent service."""
        result = store.get_ownership("non-existent")
        assert result is None


class TestContextStoreChanges:
    """Tests for change operations."""
    
    def test_add_and_get_changes(self, store):
        """Test adding and retrieving changes."""
        change = ChangeEvent(
            id="change-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="test-service",
            description="Test deployment",
            author="tester@example.com",
            timestamp=utcnow(),
        )
        
        store.add_change(change)
        changes = store.get_recent_changes(service_name="test-service")
        
        assert len(changes) == 1
        assert changes[0].description == "Test deployment"
    
    def test_recent_changes_filter(self, store):
        """Test filtering changes by time."""
        # Add old change
        old_change = ChangeEvent(
            id="old-change",
            change_type=ChangeType.DEPLOYMENT,
            service_name="test-service",
            description="Old deployment",
            author="tester@example.com",
            timestamp=utcnow() - timedelta(days=2),
        )
        store.add_change(old_change)
        
        # Add recent change
        recent_change = ChangeEvent(
            id="recent-change",
            change_type=ChangeType.DEPLOYMENT,
            service_name="test-service",
            description="Recent deployment",
            author="tester@example.com",
            timestamp=utcnow(),
        )
        store.add_change(recent_change)
        
        # Get changes from last 24 hours
        changes = store.get_recent_changes(hours=24)
        
        assert len(changes) == 1
        assert changes[0].id == "recent-change"


class TestContextStoreAlerts:
    """Tests for alert operations."""
    
    def test_add_and_get_alerts(self, store):
        """Test adding and retrieving alerts."""
        alert = Alert(
            id="alert-1",
            name="TestAlert",
            severity=Severity.HIGH,
            service_name="test-service",
            summary="Test alert",
        )
        
        store.add_alert(alert)
        firing = store.get_firing_alerts()
        
        assert len(firing) == 1
        assert firing[0].name == "TestAlert"
    
    def test_resolved_alerts_not_firing(self, store):
        """Test that resolved alerts aren't returned as firing."""
        alert = Alert(
            id="resolved-alert",
            name="ResolvedAlert",
            summary="Was firing, now resolved",
            resolved_at=utcnow(),
        )
        
        store.add_alert(alert)
        firing = store.get_firing_alerts()
        
        assert len(firing) == 0


class TestContextStoreRunbooks:
    """Tests for runbook operations."""
    
    def test_add_and_find_runbook(self, store):
        """Test adding and finding runbooks."""
        runbook = Runbook(
            id="rb-1",
            title="Memory Troubleshooting",
            alert_names=["HighMemoryUsage", "OOMKilled"],
            services=["payment-service"],
            description="How to handle memory issues",
            steps=["Check metrics", "Scale up", "Investigate code"],
        )
        
        store.add_runbook(runbook)
        
        # Find by alert name
        found = store.find_runbook(alert_name="HighMemoryUsage")
        assert len(found) == 1
        assert found[0].title == "Memory Troubleshooting"
        
        # Find by service
        found = store.find_runbook(service_name="payment-service")
        assert len(found) == 1


class TestContextStoreIncidents:
    """Tests for incident operations."""
    
    def test_create_and_get_incident(self, store):
        """Test creating and retrieving incidents."""
        incident = Incident(
            id="inc-1",
            title="Test Incident",
            severity=Severity.HIGH,
            services=["test-service"],
        )
        
        store.create_incident(incident)
        retrieved = store.get_incident("inc-1")
        
        assert retrieved is not None
        assert retrieved.title == "Test Incident"
    
    def test_open_incidents(self, store):
        """Test getting open incidents."""
        # Create open incident
        open_inc = Incident(
            id="open-inc",
            title="Open Incident",
        )
        store.create_incident(open_inc)
        
        # Create resolved incident
        resolved_inc = Incident(
            id="resolved-inc",
            title="Resolved Incident",
            resolved_at=utcnow(),
        )
        store.create_incident(resolved_inc)
        
        open_incidents = store.get_open_incidents()
        
        assert len(open_incidents) == 1
        assert open_incidents[0].id == "open-inc"


class TestContextStoreSummary:
    """Tests for context summary."""
    
    def test_summary(self, store):
        """Test getting context summary."""
        # Add some data
        store.add_service(Service(name="svc-1"))
        store.add_service(Service(name="svc-2"))
        store.set_ownership(Ownership(service_name="svc-1", team="team1"))
        store.add_change(ChangeEvent(
            id="c1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc-1",
            description="Test",
            author="test",
        ))
        store.add_alert(Alert(id="a1", name="Alert1", summary="Test"))
        
        summary = store.get_context_summary()
        
        assert summary["services"] == 2
        assert summary["ownership_mappings"] == 1
        assert summary["changes_last_24h"] == 1
        assert summary["firing_alerts"] == 1
