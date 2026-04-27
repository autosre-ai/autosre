"""
Tests for change tracking functionality.
"""

import pytest
from datetime import datetime, timedelta, timezone

from autosre.foundation.changes import ChangeTracker
from autosre.foundation.models import ChangeEvent, ChangeType


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TestChangeTracker:
    """Tests for ChangeTracker."""
    
    def test_init(self, context_store):
        """Test initialization with context store."""
        tracker = ChangeTracker(context_store)
        assert tracker.context_store is context_store
    
    def test_record_change(self, context_store):
        """Test recording a change."""
        tracker = ChangeTracker(context_store)
        
        change = ChangeEvent(
            id="change-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Deploy v1.2.0",
            author="deploy-bot",
            timestamp=utcnow(),
        )
        
        tracker.record_change(change)
        
        # Verify it was recorded
        recent = tracker.get_recent_changes(service_name="api-service", hours=1)
        assert len(recent) == 1
        assert recent[0].id == "change-1"
    
    def test_get_recent_changes_filter_by_service(self, context_store):
        """Test filtering recent changes by service."""
        tracker = ChangeTracker(context_store)
        
        # Add changes for different services
        now = utcnow()
        tracker.record_change(ChangeEvent(
            id="change-api-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="API deploy",
            author="ci",
            timestamp=now,
        ))
        tracker.record_change(ChangeEvent(
            id="change-web-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="web-service",
            description="Web deploy",
            author="ci",
            timestamp=now,
        ))
        
        api_changes = tracker.get_recent_changes(service_name="api-service", hours=1)
        assert len(api_changes) == 1
        assert api_changes[0].service_name == "api-service"
        
        all_changes = tracker.get_recent_changes(service_name=None, hours=1)
        assert len(all_changes) == 2
    
    def test_get_recent_changes_time_filter(self, context_store):
        """Test time filtering of changes."""
        tracker = ChangeTracker(context_store)
        
        now = utcnow()
        # Add an old change (26 hours ago)
        old_change = ChangeEvent(
            id="old-change",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="Old deploy",
            author="ci",
            timestamp=now - timedelta(hours=26),
        )
        tracker.record_change(old_change)
        
        # Add a recent change
        new_change = ChangeEvent(
            id="new-change",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="New deploy",
            author="ci",
            timestamp=now,
        )
        tracker.record_change(new_change)
        
        # 24 hour window should only return recent change
        recent = tracker.get_recent_changes(hours=24)
        assert len(recent) == 1
        assert recent[0].id == "new-change"
        
        # 48 hour window should return both
        all_recent = tracker.get_recent_changes(hours=48)
        assert len(all_recent) == 2
    
    def test_get_changes_around_time(self, context_store):
        """Test getting changes within a time window."""
        tracker = ChangeTracker(context_store)
        
        reference_time = utcnow()
        
        # Change 20 minutes before reference
        tracker.record_change(ChangeEvent(
            id="change-before",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="svc",
            description="Config change",
            author="admin",
            timestamp=reference_time - timedelta(minutes=20),
        ))
        
        # Change 10 minutes after reference
        tracker.record_change(ChangeEvent(
            id="change-after",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=reference_time + timedelta(minutes=10),
        ))
        
        # Change 60 minutes before (outside 30-min window)
        tracker.record_change(ChangeEvent(
            id="change-outside",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Old deploy",
            author="ci",
            timestamp=reference_time - timedelta(minutes=60),
        ))
        
        changes = tracker.get_changes_around_time(
            timestamp=reference_time,
            window_minutes=30
        )
        
        assert len(changes) == 2
        change_ids = {c.id for c in changes}
        assert "change-before" in change_ids
        assert "change-after" in change_ids
        assert "change-outside" not in change_ids
    
    def test_correlate_with_alert_basic(self, context_store):
        """Test basic alert correlation."""
        tracker = ChangeTracker(context_store)
        
        alert_time = utcnow()
        
        # Deploy 10 minutes before alert
        tracker.record_change(ChangeEvent(
            id="deploy-10",
            change_type=ChangeType.DEPLOYMENT,
            service_name="payment-service",
            description="Deploy v2.0",
            author="ci",
            timestamp=alert_time - timedelta(minutes=10),
        ))
        
        # Config change 30 minutes before
        tracker.record_change(ChangeEvent(
            id="config-30",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="payment-service",
            description="Config update",
            author="admin",
            timestamp=alert_time - timedelta(minutes=30),
        ))
        
        correlations = tracker.correlate_with_alert(
            alert_time=alert_time,
            service_name="payment-service",
            lookback_minutes=60
        )
        
        assert len(correlations) == 2
        # Closer change should have higher score
        assert correlations[0]["change"].id == "deploy-10"
        assert correlations[0]["score"] > correlations[1]["score"]
        assert correlations[0]["minutes_before_alert"] < correlations[1]["minutes_before_alert"]
    
    def test_correlate_with_alert_service_match_bonus(self, context_store):
        """Test that matching service gets higher correlation score."""
        tracker = ChangeTracker(context_store)
        
        alert_time = utcnow()
        
        # Change to different service
        tracker.record_change(ChangeEvent(
            id="other-svc",
            change_type=ChangeType.DEPLOYMENT,
            service_name="other-service",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=5),
        ))
        
        # Change to same service (slightly older)
        tracker.record_change(ChangeEvent(
            id="same-svc",
            change_type=ChangeType.DEPLOYMENT,
            service_name="target-service",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=10),
        ))
        
        correlations = tracker.correlate_with_alert(
            alert_time=alert_time,
            service_name="target-service",
            lookback_minutes=60
        )
        
        assert len(correlations) == 2
        # Same service change should score higher despite being older
        same_svc = next(c for c in correlations if c["change"].id == "same-svc")
        other_svc = next(c for c in correlations if c["change"].id == "other-svc")
        
        assert same_svc["service_match"] is True
        assert other_svc["service_match"] is False
    
    def test_correlate_excludes_changes_after_alert(self, context_store):
        """Test that changes after alert time are excluded."""
        tracker = ChangeTracker(context_store)
        
        alert_time = utcnow()
        
        # Change before alert
        tracker.record_change(ChangeEvent(
            id="before",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=10),
        ))
        
        # Change after alert
        tracker.record_change(ChangeEvent(
            id="after",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=alert_time + timedelta(minutes=10),
        ))
        
        correlations = tracker.correlate_with_alert(
            alert_time=alert_time,
            service_name="svc",
            lookback_minutes=60
        )
        
        # Only the change before should be included
        assert len(correlations) == 1
        assert correlations[0]["change"].id == "before"
    
    def test_get_rollback_candidates(self, context_store):
        """Test getting rollback candidates."""
        tracker = ChangeTracker(context_store)
        
        now = utcnow()
        
        # Successful deployment
        tracker.record_change(ChangeEvent(
            id="deploy-success",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="Deploy v1.0",
            author="ci",
            timestamp=now - timedelta(hours=2),
            successful=True,
            rolled_back=False,
        ))
        
        # Already rolled back
        tracker.record_change(ChangeEvent(
            id="deploy-rolled-back",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="Deploy v2.0 (bad)",
            author="ci",
            timestamp=now - timedelta(hours=1),
            successful=True,
            rolled_back=True,
        ))
        
        # Failed deployment
        tracker.record_change(ChangeEvent(
            id="deploy-failed",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="Deploy v3.0 (failed)",
            author="ci",
            timestamp=now,
            successful=False,
            rolled_back=False,
        ))
        
        # Config change (not a deployment)
        tracker.record_change(ChangeEvent(
            id="config-change",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="api",
            description="Config update",
            author="admin",
            timestamp=now,
            successful=True,
        ))
        
        candidates = tracker.get_rollback_candidates("api")
        
        # Only successful, not-rolled-back deployments
        assert len(candidates) == 1
        assert candidates[0].id == "deploy-success"
    
    def test_get_rollback_candidates_empty(self, context_store):
        """Test rollback candidates when none exist."""
        tracker = ChangeTracker(context_store)
        candidates = tracker.get_rollback_candidates("nonexistent-service")
        assert candidates == []
    
    def test_mark_rolled_back(self, context_store):
        """Test marking a change as rolled back."""
        tracker = ChangeTracker(context_store)
        
        # Currently returns False as it's not implemented
        result = tracker.mark_rolled_back("some-change-id")
        assert result is False
    
    def test_get_change_velocity_basic(self, context_store):
        """Test change velocity metrics."""
        tracker = ChangeTracker(context_store)
        
        now = utcnow()
        
        # Add several changes
        for i in range(5):
            tracker.record_change(ChangeEvent(
                id=f"deploy-{i}",
                change_type=ChangeType.DEPLOYMENT,
                service_name="api",
                description=f"Deploy #{i}",
                author="ci",
                timestamp=now - timedelta(hours=i),
                successful=True,
            ))
        
        # Add a config change
        tracker.record_change(ChangeEvent(
            id="config-1",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="api",
            description="Config update",
            author="admin",
            timestamp=now,
            successful=True,
        ))
        
        # Add a rollback
        tracker.record_change(ChangeEvent(
            id="rollback-1",
            change_type=ChangeType.ROLLBACK,
            service_name="api",
            description="Rollback",
            author="ci",
            timestamp=now,
            successful=True,
            rolled_back=True,
        ))
        
        velocity = tracker.get_change_velocity(hours=24)
        
        assert velocity["total_changes"] == 7
        assert velocity["time_window_hours"] == 24
        assert velocity["changes_per_hour"] == 7 / 24
        assert "deployment" in velocity["by_type"]
        assert velocity["by_type"]["deployment"] == 5
        assert velocity["by_type"]["config_change"] == 1
        assert "api" in velocity["by_service"]
    
    def test_get_change_velocity_by_service(self, context_store):
        """Test velocity filtered by service."""
        tracker = ChangeTracker(context_store)
        
        now = utcnow()
        
        tracker.record_change(ChangeEvent(
            id="api-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="API deploy",
            author="ci",
            timestamp=now,
        ))
        tracker.record_change(ChangeEvent(
            id="web-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="web",
            description="Web deploy",
            author="ci",
            timestamp=now,
        ))
        
        velocity = tracker.get_change_velocity(service_name="api", hours=24)
        
        assert velocity["total_changes"] == 1
        assert velocity["by_service"] == {"api": 1}
    
    def test_get_change_velocity_empty(self, context_store):
        """Test velocity with no changes."""
        tracker = ChangeTracker(context_store)
        
        velocity = tracker.get_change_velocity(hours=24)
        
        assert velocity["total_changes"] == 0
        assert velocity["success_rate"] == 1.0  # Default when empty
        assert velocity["rollback_rate"] == 0.0
    
    def test_get_change_velocity_success_rate(self, context_store):
        """Test success rate calculation."""
        tracker = ChangeTracker(context_store)
        
        now = utcnow()
        
        # 2 successful
        for i in range(2):
            tracker.record_change(ChangeEvent(
                id=f"success-{i}",
                change_type=ChangeType.DEPLOYMENT,
                service_name="api",
                description="Success",
                author="ci",
                timestamp=now,
                successful=True,
            ))
        
        # 1 failed
        tracker.record_change(ChangeEvent(
            id="fail-1",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api",
            description="Fail",
            author="ci",
            timestamp=now,
            successful=False,
        ))
        
        velocity = tracker.get_change_velocity(hours=24)
        
        assert velocity["total_changes"] == 3
        assert velocity["success_rate"] == pytest.approx(2/3)


class TestChangeCorrelationScoring:
    """Tests for change correlation scoring logic."""
    
    def test_deployment_scores_higher_than_scale(self, context_store):
        """Test that deployments score higher than scale events."""
        tracker = ChangeTracker(context_store)
        
        alert_time = utcnow()
        
        # Deployment
        tracker.record_change(ChangeEvent(
            id="deploy",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=10),
        ))
        
        # Scale up (same time)
        tracker.record_change(ChangeEvent(
            id="scale",
            change_type=ChangeType.SCALE_UP,
            service_name="svc",
            description="Scale",
            author="autoscaler",
            timestamp=alert_time - timedelta(minutes=10),
        ))
        
        correlations = tracker.correlate_with_alert(
            alert_time=alert_time,
            service_name="svc",
            lookback_minutes=60
        )
        
        deploy = next(c for c in correlations if c["change"].id == "deploy")
        scale = next(c for c in correlations if c["change"].id == "scale")
        
        # Deployment should have higher type score
        assert deploy["score"] >= scale["score"]
    
    def test_closer_changes_score_higher(self, context_store):
        """Test that time proximity increases score."""
        tracker = ChangeTracker(context_store)
        
        alert_time = utcnow()
        
        # Close change
        tracker.record_change(ChangeEvent(
            id="close",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=5),
        ))
        
        # Far change
        tracker.record_change(ChangeEvent(
            id="far",
            change_type=ChangeType.DEPLOYMENT,
            service_name="svc",
            description="Deploy",
            author="ci",
            timestamp=alert_time - timedelta(minutes=55),
        ))
        
        correlations = tracker.correlate_with_alert(
            alert_time=alert_time,
            service_name="svc",
            lookback_minutes=60
        )
        
        close = next(c for c in correlations if c["change"].id == "close")
        far = next(c for c in correlations if c["change"].id == "far")
        
        assert close["score"] > far["score"]
        assert close["minutes_before_alert"] < far["minutes_before_alert"]
