"""
Unit tests for change management.

Tests for:
- ChangeTracker
- ImpactAnalyzer
- CorrelationEngine
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from autosre.changes import (
    ChangeTracker,
    CorrelationEngine,
    ImpactAnalyzer,
)
from autosre.changes.models import (
    Change,
    ChangeType,
    ChangeStatus,
    ChangeRisk,
    ChangeImpact,
    ChangeWindow,
    ChangeWindowType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tracker() -> ChangeTracker:
    """Create a change tracker."""
    return ChangeTracker()


@pytest.fixture
def sample_change() -> Change:
    """Create a sample change."""
    return Change(
        change_type=ChangeType.DEPLOYMENT,
        resource_type="deployment",
        resource_name="api-server",
        namespace="production",
        cluster="prod-us-west-2",
        title="Deploy api-server v1.2.3",
        description="Deploy new version with bug fixes",
        before_state={"image": "api:v1.2.2", "replicas": 3},
        after_state={"image": "api:v1.2.3", "replicas": 3},
        source="ci-cd",
        changed_by="deploy-bot",
        risk=ChangeRisk.MEDIUM,
    )


# ============================================================================
# ChangeTracker Tests
# ============================================================================

class TestChangeTracker:
    """Tests for ChangeTracker."""
    
    @pytest.mark.asyncio
    async def test_record_change(
        self,
        tracker: ChangeTracker,
    ):
        """Test recording a change."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            title="Deploy api-server v1.2.3",
            changed_by="deploy-bot",
        )
        
        assert change is not None
        assert change.change_type == ChangeType.DEPLOYMENT
        assert change.status == ChangeStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_start_change(
        self,
        tracker: ChangeTracker,
    ):
        """Test starting a change."""
        change = await tracker.record_change(
            change_type=ChangeType.CONFIG_MAP,
            resource_type="configmap",
            resource_name="api-config",
            namespace="production",
            changed_by="admin",
        )
        
        started = await tracker.start_change(change.id)
        
        assert started
        assert change.status == ChangeStatus.IN_PROGRESS
        assert change.started_at is not None
    
    @pytest.mark.asyncio
    async def test_complete_change_success(
        self,
        tracker: ChangeTracker,
    ):
        """Test completing a change successfully."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        await tracker.start_change(change.id)
        completed = await tracker.complete_change(change.id, success=True)
        
        assert completed
        assert change.status == ChangeStatus.COMPLETED
        assert change.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_complete_change_failure(
        self,
        tracker: ChangeTracker,
    ):
        """Test completing a change with failure."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        await tracker.start_change(change.id)
        completed = await tracker.complete_change(change.id, success=False)
        
        assert completed
        assert change.status == ChangeStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_rollback_change(
        self,
        tracker: ChangeTracker,
    ):
        """Test rolling back a change."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        await tracker.start_change(change.id)
        await tracker.complete_change(change.id, success=True)
        
        rolled_back = await tracker.rollback_change(change.id)
        
        assert rolled_back
        assert change.status == ChangeStatus.ROLLED_BACK
    
    @pytest.mark.asyncio
    async def test_link_incident(
        self,
        tracker: ChangeTracker,
    ):
        """Test linking change to incident."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        linked = await tracker.link_incident(change.id, "INC-123")
        
        assert linked
        assert "INC-123" in change.incident_ids
    
    @pytest.mark.asyncio
    async def test_get_recent_changes(
        self,
        tracker: ChangeTracker,
    ):
        """Test getting recent changes."""
        # Record some changes
        for i in range(5):
            await tracker.record_change(
                change_type=ChangeType.DEPLOYMENT,
                resource_type="deployment",
                resource_name=f"service-{i}",
                namespace="production",
                changed_by="deploy-bot",
            )
        
        recent = await tracker.get_recent_changes(
            namespace="production",
            minutes=60,
        )
        
        assert len(recent) == 5
    
    @pytest.mark.asyncio
    async def test_get_changes_for_resource(
        self,
        tracker: ChangeTracker,
    ):
        """Test getting changes for specific resource."""
        # Record changes for same resource
        for i in range(3):
            change = await tracker.record_change(
                change_type=ChangeType.DEPLOYMENT,
                resource_type="deployment",
                resource_name="api-server",
                namespace="production",
                changed_by="deploy-bot",
                title=f"Deploy {i}",
            )
            await asyncio.sleep(0.01)  # Small delay for ordering
        
        changes = await tracker.get_changes_for_resource(
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
        )
        
        assert len(changes) == 3
    
    @pytest.mark.asyncio
    async def test_get_active_changes(
        self,
        tracker: ChangeTracker,
    ):
        """Test getting active changes."""
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        await tracker.start_change(change.id)
        
        active = await tracker.get_active_changes()
        
        assert len(active) == 1
        assert active[0].id == change.id
    
    @pytest.mark.asyncio
    async def test_change_event_handler(
        self,
        tracker: ChangeTracker,
    ):
        """Test change event handler."""
        events_received = []
        
        async def handler(change, event_type):
            events_received.append((change.id, event_type))
        
        tracker.on_change(handler)
        
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="deploy-bot",
        )
        
        assert len(events_received) == 1
        assert events_received[0][1] == "created"
    
    def test_get_stats(
        self,
        tracker: ChangeTracker,
    ):
        """Test getting tracker stats."""
        stats = tracker.get_stats()
        
        assert "total_changes" in stats
        assert "by_status" in stats
        assert "by_type" in stats


# ============================================================================
# Model Tests
# ============================================================================

class TestChangeModels:
    """Tests for change management models."""
    
    def test_change_creation(self, sample_change: Change):
        """Test change model creation."""
        assert sample_change.change_type == ChangeType.DEPLOYMENT
        assert sample_change.resource_name == "api-server"
        assert sample_change.status == ChangeStatus.PENDING
    
    def test_change_is_active(self, sample_change: Change):
        """Test change active status."""
        # PENDING is considered active (waiting to start)
        assert sample_change.is_active
        
        sample_change.status = ChangeStatus.IN_PROGRESS
        assert sample_change.is_active
        
        sample_change.status = ChangeStatus.COMPLETED
        assert not sample_change.is_active
    
    def test_change_duration(self, sample_change: Change):
        """Test change duration calculation."""
        sample_change.started_at = datetime.utcnow() - timedelta(minutes=5)
        sample_change.completed_at = datetime.utcnow()
        
        assert sample_change.duration_seconds is not None
        assert 290 <= sample_change.duration_seconds <= 310
    
    def test_change_window_creation(self):
        """Test change window creation."""
        now = datetime.utcnow()
        window = ChangeWindow(
            name="Maintenance Window",
            window_type=ChangeWindowType.MAINTENANCE,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        
        assert window.name == "Maintenance Window"
        assert window.window_type == ChangeWindowType.MAINTENANCE
        assert window.active is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestChangeManagementIntegration:
    """Integration tests for change management."""
    
    @pytest.mark.asyncio
    async def test_full_change_lifecycle(self):
        """Test full change lifecycle."""
        tracker = ChangeTracker()
        
        # Record change
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            title="Deploy api-server v1.2.3",
            changed_by="deploy-bot",
        )
        
        # Start change
        await tracker.start_change(change.id)
        assert change.status == ChangeStatus.IN_PROGRESS
        
        # Complete change
        await tracker.complete_change(change.id, success=True)
        assert change.status == ChangeStatus.COMPLETED
        
        # Link to incident
        await tracker.link_incident(change.id, "INC-123")
        assert "INC-123" in change.incident_ids
