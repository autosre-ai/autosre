"""
Change Tracker.

Tracks all changes in the system.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Change,
    ChangeType,
    ChangeStatus,
    ChangeRisk,
    ChangeImpact,
)

logger = get_logger(__name__)


# Type for change event handlers
ChangeEventHandler = Callable[[Change, str], Awaitable[None]]


class ChangeTracker:
    """
    Tracks all changes in the system.
    
    Features:
    - Record changes from various sources
    - Query change history
    - Event notifications
    - Change state management
    
    Example:
        tracker = ChangeTracker()
        
        change = await tracker.record_change(
            change_type=ChangeType.DEPLOYMENT,
            resource_type="deployment",
            resource_name="api-server",
            namespace="production",
            changed_by="ci-system",
        )
        
        # Later
        recent = await tracker.get_recent_changes(
            namespace="production",
            minutes=60,
        )
    """
    
    def __init__(self):
        # Change storage
        self._changes: dict[UUID, Change] = {}
        
        # Indexes
        self._by_namespace: dict[str, list[UUID]] = {}
        self._by_resource: dict[str, list[UUID]] = {}
        self._by_type: dict[ChangeType, list[UUID]] = {}
        
        # Event handlers
        self._handlers: list[ChangeEventHandler] = []
        
        self._lock = asyncio.Lock()
    
    async def record_change(
        self,
        change_type: ChangeType,
        resource_type: str,
        resource_name: str,
        namespace: str | None = None,
        cluster: str = "default",
        title: str = "",
        description: str = "",
        reason: str = "",
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        source: str = "unknown",
        source_id: str | None = None,
        source_url: str | None = None,
        changed_by: str = "unknown",
        approved_by: str | None = None,
        risk: ChangeRisk = ChangeRisk.MEDIUM,
        impact: ChangeImpact | None = None,
        labels: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> Change:
        """
        Record a new change.
        
        Args:
            change_type: Type of change
            resource_type: Kubernetes resource type
            resource_name: Resource name
            namespace: Kubernetes namespace
            cluster: Cluster name
            title: Change title
            description: Change description
            reason: Reason for change
            before_state: State before change
            after_state: State after change
            source: Change source (ci/cd, manual, etc.)
            source_id: Source identifier
            source_url: URL to source
            changed_by: Who made the change
            approved_by: Who approved the change
            risk: Risk level
            impact: Impact assessment
            labels: Labels
            tags: Tags
            
        Returns:
            Recorded change
        """
        change = Change(
            change_type=change_type,
            resource_type=resource_type,
            resource_name=resource_name,
            namespace=namespace,
            cluster=cluster,
            title=title or f"{change_type.value}: {resource_name}",
            description=description,
            reason=reason,
            before_state=before_state or {},
            after_state=after_state or {},
            source=source,
            source_id=source_id,
            source_url=source_url,
            changed_by=changed_by,
            approved_by=approved_by,
            risk=risk,
            impact=impact,
            labels=labels or {},
            tags=tags or [],
            status=ChangeStatus.PENDING,
        )
        
        async with self._lock:
            self._changes[change.id] = change
            self._index_change(change)
        
        logger.info(
            f"Recorded change: {change.id} - {change_type.value} "
            f"{resource_type}/{namespace}/{resource_name}"
        )
        
        # Notify handlers
        await self._notify_handlers(change, "created")
        
        return change
    
    async def start_change(self, change_id: UUID) -> bool:
        """
        Mark a change as started.
        
        Args:
            change_id: Change ID
            
        Returns:
            True if updated
        """
        change = self._changes.get(change_id)
        if not change:
            return False
        
        change.status = ChangeStatus.IN_PROGRESS
        change.started_at = datetime.utcnow()
        
        await self._notify_handlers(change, "started")
        
        return True
    
    async def complete_change(
        self,
        change_id: UUID,
        success: bool = True,
        after_state: dict[str, Any] | None = None,
    ) -> bool:
        """
        Mark a change as completed.
        
        Args:
            change_id: Change ID
            success: Whether change was successful
            after_state: Final state after change
            
        Returns:
            True if updated
        """
        change = self._changes.get(change_id)
        if not change:
            return False
        
        change.status = ChangeStatus.COMPLETED if success else ChangeStatus.FAILED
        change.completed_at = datetime.utcnow()
        
        if after_state:
            change.after_state = after_state
        
        await self._notify_handlers(change, "completed" if success else "failed")
        
        return True
    
    async def rollback_change(
        self,
        change_id: UUID,
        rollback_id: UUID | None = None,
    ) -> bool:
        """
        Mark a change as rolled back.
        
        Args:
            change_id: Change ID
            rollback_id: ID of rollback change
            
        Returns:
            True if updated
        """
        change = self._changes.get(change_id)
        if not change:
            return False
        
        change.status = ChangeStatus.ROLLED_BACK
        change.rolled_back_at = datetime.utcnow()
        change.rollback_id = rollback_id
        
        await self._notify_handlers(change, "rolled_back")
        
        return True
    
    async def link_incident(
        self,
        change_id: UUID,
        incident_id: str,
    ) -> bool:
        """
        Link a change to an incident.
        
        Args:
            change_id: Change ID
            incident_id: Incident ID
            
        Returns:
            True if linked
        """
        change = self._changes.get(change_id)
        if not change:
            return False
        
        if incident_id not in change.incident_ids:
            change.incident_ids.append(incident_id)
        
        return True
    
    async def get_change(self, change_id: UUID) -> Change | None:
        """Get a change by ID."""
        return self._changes.get(change_id)
    
    async def get_recent_changes(
        self,
        namespace: str | None = None,
        cluster: str | None = None,
        change_type: ChangeType | None = None,
        minutes: int = 60,
        status: ChangeStatus | None = None,
    ) -> list[Change]:
        """
        Get recent changes.
        
        Args:
            namespace: Filter by namespace
            cluster: Filter by cluster
            change_type: Filter by type
            minutes: Lookback window
            status: Filter by status
            
        Returns:
            List of changes
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        results = []
        
        for change in self._changes.values():
            # Time filter
            change_time = change.started_at or change.created_at
            if change_time < cutoff:
                continue
            
            # Namespace filter
            if namespace and change.namespace != namespace:
                continue
            
            # Cluster filter
            if cluster and change.cluster != cluster:
                continue
            
            # Type filter
            if change_type and change.change_type != change_type:
                continue
            
            # Status filter
            if status and change.status != status:
                continue
            
            results.append(change)
        
        # Sort by time (most recent first)
        results.sort(
            key=lambda c: c.started_at or c.created_at,
            reverse=True,
        )
        
        return results
    
    async def get_changes_for_resource(
        self,
        resource_type: str,
        resource_name: str,
        namespace: str | None = None,
        limit: int = 50,
    ) -> list[Change]:
        """
        Get changes for a specific resource.
        
        Args:
            resource_type: Resource type
            resource_name: Resource name
            namespace: Namespace
            limit: Maximum results
            
        Returns:
            List of changes
        """
        key = f"{resource_type}/{namespace}/{resource_name}"
        change_ids = self._by_resource.get(key, [])
        
        results = [
            self._changes[cid]
            for cid in change_ids[-limit:]
            if cid in self._changes
        ]
        
        results.sort(
            key=lambda c: c.started_at or c.created_at,
            reverse=True,
        )
        
        return results
    
    async def get_changes_in_window(
        self,
        start_time: datetime,
        end_time: datetime,
        namespace: str | None = None,
    ) -> list[Change]:
        """
        Get changes within a time window.
        
        Args:
            start_time: Window start
            end_time: Window end
            namespace: Filter by namespace
            
        Returns:
            List of changes
        """
        results = []
        
        for change in self._changes.values():
            change_time = change.started_at or change.created_at
            
            if not (start_time <= change_time <= end_time):
                continue
            
            if namespace and change.namespace != namespace:
                continue
            
            results.append(change)
        
        results.sort(key=lambda c: c.started_at or c.created_at)
        
        return results
    
    async def get_active_changes(self) -> list[Change]:
        """Get all currently active changes."""
        return [c for c in self._changes.values() if c.is_active]
    
    async def get_failed_changes(
        self,
        hours: int = 24,
    ) -> list[Change]:
        """Get recently failed changes."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            c for c in self._changes.values()
            if c.status == ChangeStatus.FAILED
            and (c.completed_at or c.created_at) > cutoff
        ]
    
    def on_change(self, handler: ChangeEventHandler) -> None:
        """
        Register a change event handler.
        
        Args:
            handler: Async function called with (change, event_type)
        """
        self._handlers.append(handler)
    
    async def _notify_handlers(
        self,
        change: Change,
        event_type: str,
    ) -> None:
        """Notify all registered handlers."""
        for handler in self._handlers:
            try:
                await handler(change, event_type)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    def _index_change(self, change: Change) -> None:
        """Add change to indexes."""
        # By namespace
        if change.namespace:
            if change.namespace not in self._by_namespace:
                self._by_namespace[change.namespace] = []
            self._by_namespace[change.namespace].append(change.id)
        
        # By resource
        key = f"{change.resource_type}/{change.namespace}/{change.resource_name}"
        if key not in self._by_resource:
            self._by_resource[key] = []
        self._by_resource[key].append(change.id)
        
        # By type
        if change.change_type not in self._by_type:
            self._by_type[change.change_type] = []
        self._by_type[change.change_type].append(change.id)
    
    def get_stats(self) -> dict[str, Any]:
        """Get tracker statistics."""
        total = len(self._changes)
        
        by_status = {}
        for change in self._changes.values():
            status = change.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        by_type = {}
        for change in self._changes.values():
            ctype = change.change_type.value
            by_type[ctype] = by_type.get(ctype, 0) + 1
        
        return {
            "total_changes": total,
            "by_status": by_status,
            "by_type": by_type,
            "namespaces_tracked": len(self._by_namespace),
            "resources_tracked": len(self._by_resource),
        }
