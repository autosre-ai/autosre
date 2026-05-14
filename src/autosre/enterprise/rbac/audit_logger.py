"""Audit Logger for AutoSRE V2 RBAC.

Provides comprehensive audit logging:
- Event capture and storage
- Query and search capabilities
- Compliance reporting
- Event forwarding
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    
    # Authentication events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"
    PASSWORD_CHANGED = "password_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    POLICY_EVALUATED = "policy_evaluated"
    
    # Resource events
    RESOURCE_CREATED = "resource_created"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_DELETED = "resource_deleted"
    RESOURCE_ACCESSED = "resource_accessed"
    RESOURCE_EXPORTED = "resource_exported"
    
    # Investigation events
    INVESTIGATION_STARTED = "investigation_started"
    INVESTIGATION_COMPLETED = "investigation_completed"
    ACTION_PROPOSED = "action_proposed"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    ACTION_EXECUTED = "action_executed"
    
    # Configuration events
    SETTING_CHANGED = "setting_changed"
    INTEGRATION_ADDED = "integration_added"
    INTEGRATION_REMOVED = "integration_removed"
    WEBHOOK_CREATED = "webhook_created"
    
    # Administrative events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_SUSPENDED = "user_suspended"
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    TENANT_SUSPENDED = "tenant_suspended"
    
    # Security events
    SECURITY_ALERT = "security_alert"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    IP_BLOCKED = "ip_blocked"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    BACKUP_CREATED = "backup_created"
    MAINTENANCE_STARTED = "maintenance_started"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """An audit event record."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Event classification
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Actor (who performed the action)
    actor_id: Optional[str] = None
    actor_type: str = "user"  # user, system, api_key, service
    actor_ip: Optional[str] = None
    actor_user_agent: Optional[str] = None
    
    # Context
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    
    # Target (what was affected)
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    
    # Event details
    action: str  # Human-readable action description
    description: Optional[str] = None
    
    # Before/after state (for changes)
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Result
    success: bool = True
    error_message: Optional[str] = None
    
    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: Optional[float] = None
    
    # Compliance
    retention_days: Optional[int] = None  # Override default retention
    is_sensitive: bool = False  # Contains sensitive data
    
    # Integrity
    checksum: Optional[str] = None
    
    def compute_checksum(self) -> str:
        """Compute integrity checksum for this event."""
        data = {
            "id": self.id,
            "event_type": self.event_type.value,
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "event_id": self.id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditQuery(BaseModel):
    """Query parameters for searching audit events."""
    
    # Filters
    event_types: Optional[List[AuditEventType]] = None
    severities: Optional[List[AuditSeverity]] = None
    actor_ids: Optional[List[str]] = None
    tenant_ids: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None
    resource_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    
    # Text search
    search_text: Optional[str] = None
    
    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Result filters
    success_only: Optional[bool] = None
    
    # Pagination
    offset: int = 0
    limit: int = 100
    
    # Sorting
    sort_by: str = "timestamp"
    sort_desc: bool = True


class AuditStats(BaseModel):
    """Statistics for audit events."""
    
    total_events: int = 0
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    events_by_day: Dict[str, int] = Field(default_factory=dict)
    
    top_actors: List[Dict[str, Any]] = Field(default_factory=list)
    top_resources: List[Dict[str, Any]] = Field(default_factory=list)
    
    success_rate: float = 0.0
    avg_events_per_day: float = 0.0
    
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class AuditExport(BaseModel):
    """Audit export configuration."""
    
    format: str = "json"  # json, csv, ndjson
    include_sensitive: bool = False
    include_checksums: bool = True
    compress: bool = False
    
    # Filter
    query: Optional[AuditQuery] = None
    
    # Output
    filename: Optional[str] = None


# Type for audit event handlers
AuditHandler = Callable[[AuditEvent], Awaitable[None]]


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    Provides:
    - Event capture and storage
    - Query and search
    - Statistics and reporting
    - Event forwarding to external systems
    - Compliance features
    
    Example:
        audit = AuditLogger()
        
        # Log an event
        await audit.log(
            event_type=AuditEventType.RESOURCE_ACCESSED,
            actor_id="user-123",
            tenant_id="tenant-456",
            resource_type="alert",
            resource_id="alert-789",
            action="Viewed alert details",
        )
        
        # Query events
        results = await audit.query(AuditQuery(
            actor_ids=["user-123"],
            start_time=datetime.now() - timedelta(days=7),
        ))
        
        # Get statistics
        stats = await audit.get_stats(tenant_id="tenant-456")
    """
    
    def __init__(
        self,
        retention_days: int = 90,
        max_events: int = 1000000,
        handlers: Optional[List[AuditHandler]] = None,
    ):
        """Initialize AuditLogger.
        
        Args:
            retention_days: Default retention period
            max_events: Maximum events to store
            handlers: External handlers for event forwarding
        """
        self.retention_days = retention_days
        self.max_events = max_events
        self.handlers = handlers or []
        
        self._events: List[AuditEvent] = []
        self._lock = asyncio.Lock()
        
        # Indexes for efficient queries
        self._by_actor: Dict[str, List[str]] = {}
        self._by_tenant: Dict[str, List[str]] = {}
        self._by_resource: Dict[str, List[str]] = {}
        self._by_type: Dict[AuditEventType, List[str]] = {}
    
    async def log(
        self,
        event_type: AuditEventType,
        action: str,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        description: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        actor_ip: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> AuditEvent:
        """Log an audit event.
        
        Args:
            event_type: Type of event
            action: Human-readable action description
            actor_id: ID of the actor
            tenant_id: Tenant ID
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            resource_name: Name of resource
            severity: Event severity
            description: Detailed description
            old_value: Value before change
            new_value: Value after change
            metadata: Additional metadata
            tags: Tags for categorization
            success: Whether action succeeded
            error_message: Error message if failed
            actor_ip: Actor's IP address
            session_id: Session ID
            request_id: Request ID
            is_sensitive: Contains sensitive data
            
        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            actor_ip=actor_ip,
            tenant_id=tenant_id,
            session_id=session_id,
            request_id=request_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            action=action,
            description=description,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata or {},
            tags=tags or [],
            success=success,
            error_message=error_message,
            is_sensitive=is_sensitive,
        )
        
        # Compute checksum
        event.checksum = event.compute_checksum()
        
        async with self._lock:
            # Store event
            self._events.append(event)
            
            # Update indexes
            if actor_id:
                if actor_id not in self._by_actor:
                    self._by_actor[actor_id] = []
                self._by_actor[actor_id].append(event.id)
            
            if tenant_id:
                if tenant_id not in self._by_tenant:
                    self._by_tenant[tenant_id] = []
                self._by_tenant[tenant_id].append(event.id)
            
            if resource_id:
                if resource_id not in self._by_resource:
                    self._by_resource[resource_id] = []
                self._by_resource[resource_id].append(event.id)
            
            if event_type not in self._by_type:
                self._by_type[event_type] = []
            self._by_type[event_type].append(event.id)
            
            # Enforce max events
            if len(self._events) > self.max_events:
                await self._cleanup_old_events()
        
        # Log to standard logger
        log_method = logger.info if success else logger.warning
        log_method(
            f"Audit: {action}",
            **event.to_log_dict(),
        )
        
        # Forward to handlers
        for handler in self.handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "Audit handler failed",
                    handler=handler.__name__,
                    error=str(e),
                )
        
        return event
    
    async def query(
        self,
        query: AuditQuery,
    ) -> tuple[List[AuditEvent], int]:
        """Query audit events.
        
        Args:
            query: Query parameters
            
        Returns:
            Tuple of (events, total_count)
        """
        events = self._events.copy()
        
        # Apply filters
        if query.event_types:
            events = [e for e in events if e.event_type in query.event_types]
        
        if query.severities:
            events = [e for e in events if e.severity in query.severities]
        
        if query.actor_ids:
            events = [e for e in events if e.actor_id in query.actor_ids]
        
        if query.tenant_ids:
            events = [e for e in events if e.tenant_id in query.tenant_ids]
        
        if query.resource_types:
            events = [e for e in events if e.resource_type in query.resource_types]
        
        if query.resource_ids:
            events = [e for e in events if e.resource_id in query.resource_ids]
        
        if query.tags:
            events = [
                e for e in events
                if any(tag in e.tags for tag in query.tags)
            ]
        
        if query.start_time:
            events = [e for e in events if e.timestamp >= query.start_time]
        
        if query.end_time:
            events = [e for e in events if e.timestamp <= query.end_time]
        
        if query.success_only is not None:
            events = [e for e in events if e.success == query.success_only]
        
        if query.search_text:
            search = query.search_text.lower()
            events = [
                e for e in events
                if search in e.action.lower()
                or (e.description and search in e.description.lower())
                or (e.resource_name and search in e.resource_name.lower())
            ]
        
        total_count = len(events)
        
        # Sort
        reverse = query.sort_desc
        if query.sort_by == "timestamp":
            events.sort(key=lambda e: e.timestamp, reverse=reverse)
        elif query.sort_by == "severity":
            severity_order = {s: i for i, s in enumerate(AuditSeverity)}
            events.sort(key=lambda e: severity_order.get(e.severity, 0), reverse=reverse)
        elif query.sort_by == "event_type":
            events.sort(key=lambda e: e.event_type.value, reverse=reverse)
        
        # Paginate
        events = events[query.offset:query.offset + query.limit]
        
        return events, total_count
    
    async def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a single event by ID."""
        for event in self._events:
            if event.id == event_id:
                return event
        return None
    
    async def get_events_for_resource(
        self,
        resource_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get all events for a resource.
        
        Args:
            resource_id: Resource ID
            limit: Maximum events
            
        Returns:
            List of events
        """
        event_ids = self._by_resource.get(resource_id, [])
        events = [e for e in self._events if e.id in event_ids]
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    async def get_events_for_actor(
        self,
        actor_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get all events for an actor.
        
        Args:
            actor_id: Actor ID
            limit: Maximum events
            
        Returns:
            List of events
        """
        event_ids = self._by_actor.get(actor_id, [])
        events = [e for e in self._events if e.id in event_ids]
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    async def get_stats(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> AuditStats:
        """Get audit statistics.
        
        Args:
            tenant_id: Filter by tenant
            start_time: Period start
            end_time: Period end
            
        Returns:
            AuditStats
        """
        # Set default time range
        if not end_time:
            end_time = datetime.now(timezone.utc)
        if not start_time:
            start_time = end_time - timedelta(days=30)
        
        # Filter events
        events = self._events.copy()
        
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        
        events = [
            e for e in events
            if start_time <= e.timestamp <= end_time
        ]
        
        if not events:
            return AuditStats(period_start=start_time, period_end=end_time)
        
        # Calculate stats
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_day: Dict[str, int] = {}
        actor_counts: Dict[str, int] = {}
        resource_counts: Dict[str, int] = {}
        success_count = 0
        
        for event in events:
            # By type
            type_key = event.event_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            
            # By severity
            sev_key = event.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
            
            # By day
            day_key = event.timestamp.strftime("%Y-%m-%d")
            by_day[day_key] = by_day.get(day_key, 0) + 1
            
            # Actor counts
            if event.actor_id:
                actor_counts[event.actor_id] = actor_counts.get(event.actor_id, 0) + 1
            
            # Resource counts
            if event.resource_id:
                resource_counts[event.resource_id] = resource_counts.get(event.resource_id, 0) + 1
            
            # Success count
            if event.success:
                success_count += 1
        
        # Top actors
        top_actors = sorted(
            [{"actor_id": k, "count": v} for k, v in actor_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]
        
        # Top resources
        top_resources = sorted(
            [{"resource_id": k, "count": v} for k, v in resource_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]
        
        # Calculate averages
        days_in_period = max(1, (end_time - start_time).days)
        
        return AuditStats(
            total_events=len(events),
            events_by_type=by_type,
            events_by_severity=by_severity,
            events_by_day=by_day,
            top_actors=top_actors,
            top_resources=top_resources,
            success_rate=success_count / len(events) if events else 0,
            avg_events_per_day=len(events) / days_in_period,
            period_start=start_time,
            period_end=end_time,
        )
    
    async def export(
        self,
        config: AuditExport,
    ) -> str:
        """Export audit events.
        
        Args:
            config: Export configuration
            
        Returns:
            Exported data as string
        """
        # Query events
        query = config.query or AuditQuery(limit=100000)
        events, _ = await self.query(query)
        
        # Filter sensitive if needed
        if not config.include_sensitive:
            events = [e for e in events if not e.is_sensitive]
        
        # Format output
        if config.format == "json":
            data = [e.model_dump() for e in events]
            for item in data:
                item["timestamp"] = item["timestamp"].isoformat()
                if not config.include_checksums:
                    del item["checksum"]
            return json.dumps(data, indent=2)
        
        elif config.format == "ndjson":
            lines = []
            for event in events:
                data = event.model_dump()
                data["timestamp"] = data["timestamp"].isoformat()
                if not config.include_checksums:
                    del data["checksum"]
                lines.append(json.dumps(data))
            return "\n".join(lines)
        
        elif config.format == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            fieldnames = [
                "id", "event_type", "severity", "actor_id", "tenant_id",
                "resource_type", "resource_id", "action", "success",
                "timestamp",
            ]
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for event in events:
                writer.writerow({
                    "id": event.id,
                    "event_type": event.event_type.value,
                    "severity": event.severity.value,
                    "actor_id": event.actor_id,
                    "tenant_id": event.tenant_id,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "action": event.action,
                    "success": event.success,
                    "timestamp": event.timestamp.isoformat(),
                })
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported format: {config.format}")
    
    async def verify_integrity(
        self,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify integrity of audit events.
        
        Args:
            event_id: Specific event to verify (or all if None)
            
        Returns:
            Verification results
        """
        results = {
            "verified": 0,
            "failed": 0,
            "failures": [],
        }
        
        events = self._events
        if event_id:
            events = [e for e in events if e.id == event_id]
        
        for event in events:
            expected_checksum = event.compute_checksum()
            
            if event.checksum == expected_checksum:
                results["verified"] += 1
            else:
                results["failed"] += 1
                results["failures"].append({
                    "event_id": event.id,
                    "expected": expected_checksum,
                    "actual": event.checksum,
                })
        
        return results
    
    async def cleanup_old_events(self) -> int:
        """Clean up events past retention period.
        
        Returns:
            Number of events removed
        """
        async with self._lock:
            return await self._cleanup_old_events()
    
    async def _cleanup_old_events(self) -> int:
        """Internal cleanup (must hold lock)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        
        initial_count = len(self._events)
        
        # Remove old events
        self._events = [
            e for e in self._events
            if e.timestamp >= cutoff
        ]
        
        removed = initial_count - len(self._events)
        
        if removed > 0:
            # Rebuild indexes
            self._rebuild_indexes()
            
            logger.info(
                "Cleaned up old audit events",
                removed=removed,
                remaining=len(self._events),
            )
        
        return removed
    
    def _rebuild_indexes(self) -> None:
        """Rebuild all indexes."""
        self._by_actor.clear()
        self._by_tenant.clear()
        self._by_resource.clear()
        self._by_type.clear()
        
        for event in self._events:
            if event.actor_id:
                if event.actor_id not in self._by_actor:
                    self._by_actor[event.actor_id] = []
                self._by_actor[event.actor_id].append(event.id)
            
            if event.tenant_id:
                if event.tenant_id not in self._by_tenant:
                    self._by_tenant[event.tenant_id] = []
                self._by_tenant[event.tenant_id].append(event.id)
            
            if event.resource_id:
                if event.resource_id not in self._by_resource:
                    self._by_resource[event.resource_id] = []
                self._by_resource[event.resource_id].append(event.id)
            
            if event.event_type not in self._by_type:
                self._by_type[event.event_type] = []
            self._by_type[event.event_type].append(event.id)
    
    def add_handler(self, handler: AuditHandler) -> None:
        """Add an event handler.
        
        Args:
            handler: Handler function
        """
        self.handlers.append(handler)
    
    def remove_handler(self, handler: AuditHandler) -> None:
        """Remove an event handler.
        
        Args:
            handler: Handler function
        """
        if handler in self.handlers:
            self.handlers.remove(handler)


# Helper functions for common audit patterns
async def audit_resource_change(
    audit_logger: AuditLogger,
    event_type: AuditEventType,
    actor_id: str,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> AuditEvent:
    """Helper to audit resource changes."""
    action_map = {
        AuditEventType.RESOURCE_CREATED: f"Created {resource_type}",
        AuditEventType.RESOURCE_UPDATED: f"Updated {resource_type}",
        AuditEventType.RESOURCE_DELETED: f"Deleted {resource_type}",
        AuditEventType.RESOURCE_ACCESSED: f"Accessed {resource_type}",
    }
    
    return await audit_logger.log(
        event_type=event_type,
        action=f"{action_map.get(event_type, 'Modified')} '{resource_name}'",
        actor_id=actor_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        old_value=old_value,
        new_value=new_value,
        **kwargs,
    )


async def audit_auth_event(
    audit_logger: AuditLogger,
    event_type: AuditEventType,
    actor_id: str,
    success: bool,
    actor_ip: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs,
) -> AuditEvent:
    """Helper to audit authentication events."""
    action_map = {
        AuditEventType.LOGIN: "User logged in",
        AuditEventType.LOGOUT: "User logged out",
        AuditEventType.LOGIN_FAILED: "Login attempt failed",
        AuditEventType.TOKEN_ISSUED: "API token issued",
        AuditEventType.TOKEN_REVOKED: "API token revoked",
        AuditEventType.PASSWORD_CHANGED: "Password changed",
    }
    
    severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
    
    return await audit_logger.log(
        event_type=event_type,
        action=action_map.get(event_type, "Authentication event"),
        actor_id=actor_id,
        actor_ip=actor_ip,
        success=success,
        error_message=error_message,
        severity=severity,
        **kwargs,
    )
