"""
Shared pytest fixtures for AutoSRE tests.
"""

import os
import pytest
import tempfile
from datetime import datetime, timezone

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import (
    Service,
    ServiceStatus,
    Alert,
    Severity,
    ChangeEvent,
    ChangeType,
    Ownership,
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def context_store(temp_dir):
    """Create a temporary context store for testing."""
    db_path = os.path.join(temp_dir, "context.db")
    return ContextStore(db_path=db_path)


@pytest.fixture
def populated_context_store(context_store):
    """Create a context store with sample data."""
    # Add services
    services = [
        Service(
            name="api-gateway",
            namespace="production",
            status=ServiceStatus.HEALTHY,
            replicas=3,
            ready_replicas=3,
        ),
        Service(
            name="user-service",
            namespace="production",
            status=ServiceStatus.DEGRADED,
            replicas=2,
            ready_replicas=1,
        ),
        Service(
            name="database",
            namespace="production",
            status=ServiceStatus.HEALTHY,
            replicas=1,
            ready_replicas=1,
        ),
    ]
    for svc in services:
        context_store.add_service(svc)
    
    # Add ownership
    ownership = Ownership(
        service_name="api-gateway",
        team="platform",
        on_call_email="platform-oncall@example.com",
    )
    context_store.set_ownership(ownership)
    
    # Add an alert
    alert = Alert(
        id="alert-001",
        name="HighLatency",
        severity=Severity.HIGH,
        summary="High latency on api-gateway",
        service_name="api-gateway",
        fired_at=utcnow(),
    )
    context_store.add_alert(alert)
    
    # Add a change
    change = ChangeEvent(
        id="change-001",
        service_name="api-gateway",
        change_type=ChangeType.DEPLOYMENT,
        description="Deploy v2.0.0",
        author="deploy-bot",
        timestamp=utcnow(),
    )
    context_store.add_change(change)
    
    return context_store


@pytest.fixture
def sample_service():
    """Create a sample service."""
    return Service(
        name="test-service",
        namespace="default",
        status=ServiceStatus.HEALTHY,
        replicas=2,
        ready_replicas=2,
    )


@pytest.fixture
def sample_alert():
    """Create a sample alert."""
    return Alert(
        id="test-alert-001",
        name="TestAlert",
        severity=Severity.MEDIUM,
        summary="Test alert for unit testing",
        service_name="test-service",
        fired_at=utcnow(),
    )


@pytest.fixture
def sample_change():
    """Create a sample change event."""
    return ChangeEvent(
        id="test-change-001",
        service_name="test-service",
        change_type=ChangeType.CONFIG_CHANGE,
        description="Updated configuration",
        author="tester@example.com",
        timestamp=utcnow(),
    )


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    from click.testing import CliRunner
    return CliRunner()
