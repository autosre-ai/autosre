"""
Change History Tracker - What changed, when, and who did it.

Changes are the #1 cause of incidents. This module tracks:
- Deployments
- Config changes
- Scale events
- Rollbacks
"""

from datetime import datetime, timedelta
from typing import Optional

from autosre.foundation.models import ChangeEvent, ChangeType
from autosre.foundation.context_store import ContextStore


class ChangeTracker:
    """
    Change history tracker.
    
    Maintains a history of all changes for:
    - Root cause analysis
    - Correlation with incidents
    - Rollback decisions
    """
    
    def __init__(self, context_store: ContextStore):
        """
        Initialize with a context store.
        
        Args:
            context_store: The ContextStore to read/write changes
        """
        self.context_store = context_store
    
    def record_change(self, change: ChangeEvent) -> None:
        """
        Record a new change event.
        
        Args:
            change: The change event to record
        """
        self.context_store.add_change(change)
    
    def get_recent_changes(
        self,
        service_name: Optional[str] = None,
        hours: int = 24,
        limit: int = 50
    ) -> list[ChangeEvent]:
        """
        Get recent changes.
        
        Args:
            service_name: Filter by service, or all if None
            hours: Look back this many hours
            limit: Maximum changes to return
            
        Returns:
            List of changes, most recent first
        """
        return self.context_store.get_recent_changes(
            service_name=service_name,
            hours=hours,
            limit=limit
        )
    
    def get_changes_around_time(
        self,
        timestamp: datetime,
        window_minutes: int = 30,
        service_name: Optional[str] = None
    ) -> list[ChangeEvent]:
        """
        Get changes around a specific time.
        
        Useful for correlating incidents with recent changes.
        
        Args:
            timestamp: Center of the time window
            window_minutes: Minutes before and after to include
            service_name: Filter by service
            
        Returns:
            List of changes within the window
        """
        # Get changes from last 48 hours and filter
        all_changes = self.context_store.get_recent_changes(
            service_name=service_name,
            hours=48,
            limit=200
        )
        
        window_start = timestamp - timedelta(minutes=window_minutes)
        window_end = timestamp + timedelta(minutes=window_minutes)
        
        return [
            c for c in all_changes
            if window_start <= c.timestamp <= window_end
        ]
    
    def correlate_with_alert(
        self,
        alert_time: datetime,
        service_name: str,
        lookback_minutes: int = 60
    ) -> list[dict]:
        """
        Find changes that may have caused an alert.
        
        Returns changes with correlation scores.
        
        Args:
            alert_time: When the alert fired
            service_name: Service that alerted
            lookback_minutes: How far back to look
            
        Returns:
            List of changes with correlation metadata
        """
        # Get changes for this service and its dependencies
        # (For now, just this service - topology integration later)
        changes = self.get_changes_around_time(
            timestamp=alert_time,
            window_minutes=lookback_minutes,
            service_name=None  # Get all, filter later
        )
        
        correlations = []
        
        for change in changes:
            # Skip changes after the alert
            if change.timestamp > alert_time:
                continue
            
            # Calculate correlation score
            minutes_before = (alert_time - change.timestamp).total_seconds() / 60
            
            # Base score: closer changes are more likely causes
            time_score = max(0, 1 - (minutes_before / lookback_minutes))
            
            # Service match bonus
            service_score = 1.0 if change.service_name == service_name else 0.5
            
            # Change type scoring
            type_scores = {
                ChangeType.DEPLOYMENT: 1.0,
                ChangeType.CONFIG_CHANGE: 0.9,
                ChangeType.ROLLBACK: 0.8,
                ChangeType.SCALE_UP: 0.6,
                ChangeType.SCALE_DOWN: 0.7,
                ChangeType.FEATURE_FLAG: 0.8,
                ChangeType.INFRASTRUCTURE: 0.9,
            }
            type_score = type_scores.get(change.change_type, 0.5)
            
            # Combined score
            total_score = (time_score * 0.4) + (service_score * 0.4) + (type_score * 0.2)
            
            correlations.append({
                "change": change,
                "score": total_score,
                "minutes_before_alert": minutes_before,
                "service_match": change.service_name == service_name,
            })
        
        # Sort by score
        correlations.sort(key=lambda x: -x["score"])
        
        return correlations
    
    def get_rollback_candidates(self, service_name: str) -> list[ChangeEvent]:
        """
        Get recent deployments that could be rolled back.
        
        Args:
            service_name: Service to check
            
        Returns:
            List of deployments, most recent first
        """
        changes = self.get_recent_changes(
            service_name=service_name,
            hours=168,  # 7 days
            limit=20
        )
        
        return [
            c for c in changes
            if c.change_type == ChangeType.DEPLOYMENT
            and c.successful
            and not c.rolled_back
        ]
    
    def mark_rolled_back(self, change_id: str) -> bool:
        """
        Mark a change as rolled back.
        
        Args:
            change_id: ID of the change to mark
            
        Returns:
            True if updated, False if not found
        """
        # This would need to update the database directly
        # For now, we'd need to add a method to context_store
        # TODO: Add update_change method to ContextStore
        return False
    
    def get_change_velocity(
        self,
        service_name: Optional[str] = None,
        hours: int = 24
    ) -> dict:
        """
        Calculate change velocity metrics.
        
        Args:
            service_name: Filter by service
            hours: Time window
            
        Returns:
            Dict with velocity metrics
        """
        changes = self.get_recent_changes(
            service_name=service_name,
            hours=hours,
            limit=1000
        )
        
        # Count by type
        by_type = {}
        for change in changes:
            type_name = change.change_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        # Count by service
        by_service = {}
        for change in changes:
            by_service[change.service_name] = by_service.get(change.service_name, 0) + 1
        
        # Count by hour
        by_hour = {}
        for change in changes:
            hour = change.timestamp.hour
            by_hour[hour] = by_hour.get(hour, 0) + 1
        
        # Success rate
        successful = sum(1 for c in changes if c.successful)
        rollbacks = sum(1 for c in changes if c.rolled_back)
        
        return {
            "total_changes": len(changes),
            "time_window_hours": hours,
            "changes_per_hour": len(changes) / hours if hours > 0 else 0,
            "by_type": by_type,
            "by_service": dict(sorted(by_service.items(), key=lambda x: -x[1])[:10]),
            "by_hour": by_hour,
            "success_rate": successful / len(changes) if changes else 1.0,
            "rollback_rate": rollbacks / len(changes) if changes else 0.0,
        }
