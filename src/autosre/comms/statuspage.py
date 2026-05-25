"""
Statuspage.io Integration

Provides automated status page management for incident communication.
Supports Statuspage.io API and compatible status page providers.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field
import httpx


class ComponentStatus(str, Enum):
    """Status levels for status page components."""
    
    OPERATIONAL = "operational"
    DEGRADED_PERFORMANCE = "degraded_performance"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    UNDER_MAINTENANCE = "under_maintenance"


class IncidentStatus(str, Enum):
    """Status levels for status page incidents."""
    
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETED = "completed"


class IncidentImpact(str, Enum):
    """Impact levels for status page incidents."""
    
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    MAINTENANCE = "maintenance"


class StatusPageConfig(BaseModel):
    """Configuration for status page integration."""
    
    api_key: str = Field(..., description="Statuspage.io API key")
    page_id: str = Field(..., description="Status page ID")
    base_url: str = Field(
        default="https://api.statuspage.io/v1",
        description="API base URL"
    )
    timeout: int = Field(default=30, description="API request timeout in seconds")
    auto_create_incidents: bool = Field(
        default=True,
        description="Automatically create incidents for alerts"
    )
    auto_resolve: bool = Field(
        default=True,
        description="Automatically resolve incidents when issues are fixed"
    )
    default_impact: IncidentImpact = Field(
        default=IncidentImpact.MINOR,
        description="Default incident impact level"
    )
    component_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map service names to component IDs"
    )


class Component(BaseModel):
    """A status page component (service/system)."""
    
    id: str = Field(..., description="Component ID")
    name: str = Field(..., description="Component name")
    description: Optional[str] = Field(None, description="Component description")
    status: ComponentStatus = Field(
        default=ComponentStatus.OPERATIONAL,
        description="Current status"
    )
    position: int = Field(default=0, description="Display position")
    group_id: Optional[str] = Field(None, description="Component group ID")
    only_show_if_degraded: bool = Field(
        default=False,
        description="Only show when degraded"
    )
    showcase: bool = Field(default=True, description="Show in status page")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class ComponentGroup(BaseModel):
    """A group of related components."""
    
    id: str = Field(..., description="Group ID")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    position: int = Field(default=0, description="Display position")
    components: list[Component] = Field(
        default_factory=list,
        description="Components in this group"
    )


class Subscriber(BaseModel):
    """A status page subscriber."""
    
    id: str = Field(..., description="Subscriber ID")
    email: Optional[str] = Field(None, description="Email address")
    phone_number: Optional[str] = Field(None, description="Phone number for SMS")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    mode: str = Field(default="email", description="Notification mode")
    skip_confirmation: bool = Field(
        default=False,
        description="Skip confirmation for notifications"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class StatusPageUpdate(BaseModel):
    """An update to a status page incident."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Update ID")
    incident_id: str = Field(..., description="Parent incident ID")
    status: IncidentStatus = Field(..., description="Status at time of update")
    body: str = Field(..., description="Update message")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Update timestamp"
    )
    wants_twitter_update: bool = Field(
        default=False,
        description="Post update to Twitter"
    )
    deliver_notifications: bool = Field(
        default=True,
        description="Send subscriber notifications"
    )
    affected_components: list[tuple[str, ComponentStatus]] = Field(
        default_factory=list,
        description="Component status updates"
    )


class StatusPageIncident(BaseModel):
    """A status page incident."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Incident ID")
    name: str = Field(..., description="Incident name/title")
    status: IncidentStatus = Field(
        default=IncidentStatus.INVESTIGATING,
        description="Current incident status"
    )
    impact: IncidentImpact = Field(
        default=IncidentImpact.MINOR,
        description="Incident impact level"
    )
    body: Optional[str] = Field(None, description="Initial incident description")
    component_ids: list[str] = Field(
        default_factory=list,
        description="Affected component IDs"
    )
    scheduled_for: Optional[datetime] = Field(
        None,
        description="Scheduled maintenance start time"
    )
    scheduled_until: Optional[datetime] = Field(
        None,
        description="Scheduled maintenance end time"
    )
    scheduled_remind_prior: bool = Field(
        default=True,
        description="Send reminder before scheduled maintenance"
    )
    scheduled_auto_in_progress: bool = Field(
        default=True,
        description="Auto-transition to in_progress at scheduled time"
    )
    scheduled_auto_completed: bool = Field(
        default=True,
        description="Auto-complete at scheduled end time"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata"
    )
    updates: list[StatusPageUpdate] = Field(
        default_factory=list,
        description="Incident updates"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp"
    )
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    shortlink: Optional[str] = Field(None, description="Short URL for incident")
    
    # AutoSRE correlation
    alert_id: Optional[str] = Field(
        None,
        description="Correlated AutoSRE alert ID"
    )
    investigation_id: Optional[str] = Field(
        None,
        description="Correlated AutoSRE investigation ID"
    )


class StatusPageClient:
    """Client for Statuspage.io API integration.
    
    Provides automated status page management including:
    - Creating and updating incidents
    - Managing component status
    - Subscriber management
    - Scheduled maintenance
    
    Example:
        config = StatusPageConfig(
            api_key="your-api-key",
            page_id="your-page-id",
            component_mapping={
                "payment-service": "component-123",
                "api-gateway": "component-456",
            }
        )
        client = StatusPageClient(config)
        
        # Create incident
        incident = await client.create_incident(
            name="Payment Processing Delayed",
            status=IncidentStatus.INVESTIGATING,
            impact=IncidentImpact.MINOR,
            body="We are investigating reports of delayed payments.",
            component_ids=["component-123"],
        )
        
        # Post update
        await client.post_update(
            incident_id=incident.id,
            status=IncidentStatus.IDENTIFIED,
            body="We have identified the root cause.",
        )
        
        # Resolve incident
        await client.resolve_incident(
            incident_id=incident.id,
            body="The issue has been resolved.",
        )
    """
    
    def __init__(self, config: StatusPageConfig) -> None:
        """Initialize the status page client.
        
        Args:
            config: Status page configuration
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._incidents: dict[str, StatusPageIncident] = {}
        self._components: dict[str, Component] = {}
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"OAuth {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_components(self) -> list[Component]:
        """Get all components for the status page.
        
        Returns:
            List of components
        """
        response = await self.client.get(
            f"/pages/{self.config.page_id}/components"
        )
        response.raise_for_status()
        
        components = [Component(**c) for c in response.json()]
        self._components = {c.id: c for c in components}
        return components
    
    async def update_component_status(
        self,
        component_id: str,
        status: ComponentStatus,
    ) -> Component:
        """Update a component's status.
        
        Args:
            component_id: Component ID to update
            status: New component status
            
        Returns:
            Updated component
        """
        response = await self.client.patch(
            f"/pages/{self.config.page_id}/components/{component_id}",
            json={"component": {"status": status.value}},
        )
        response.raise_for_status()
        
        component = Component(**response.json())
        self._components[component.id] = component
        return component
    
    async def create_incident(
        self,
        name: str,
        status: IncidentStatus = IncidentStatus.INVESTIGATING,
        impact: Optional[IncidentImpact] = None,
        body: Optional[str] = None,
        component_ids: Optional[list[str]] = None,
        component_status: Optional[ComponentStatus] = None,
        deliver_notifications: bool = True,
        alert_id: Optional[str] = None,
        investigation_id: Optional[str] = None,
    ) -> StatusPageIncident:
        """Create a new incident.
        
        Args:
            name: Incident name/title
            status: Initial incident status
            impact: Incident impact level
            body: Initial incident description
            component_ids: Affected component IDs
            component_status: Status for affected components
            deliver_notifications: Whether to notify subscribers
            alert_id: Correlated AutoSRE alert ID
            investigation_id: Correlated AutoSRE investigation ID
            
        Returns:
            Created incident
        """
        if impact is None:
            impact = self.config.default_impact
        
        payload: dict[str, Any] = {
            "incident": {
                "name": name,
                "status": status.value,
                "impact_override": impact.value,
                "deliver_notifications": deliver_notifications,
            }
        }
        
        if body:
            payload["incident"]["body"] = body
        
        if component_ids:
            component_ids_dict = {}
            for cid in component_ids:
                cs = component_status or ComponentStatus.DEGRADED_PERFORMANCE
                component_ids_dict[cid] = cs.value
            payload["incident"]["component_ids"] = component_ids_dict
        
        response = await self.client.post(
            f"/pages/{self.config.page_id}/incidents",
            json=payload,
        )
        response.raise_for_status()
        
        data = response.json()
        incident = StatusPageIncident(
            id=data["id"],
            name=data["name"],
            status=IncidentStatus(data["status"]),
            impact=IncidentImpact(data.get("impact", "minor")),
            body=body,
            component_ids=component_ids or [],
            shortlink=data.get("shortlink"),
            alert_id=alert_id,
            investigation_id=investigation_id,
        )
        
        self._incidents[incident.id] = incident
        return incident
    
    async def post_update(
        self,
        incident_id: str,
        status: IncidentStatus,
        body: str,
        component_updates: Optional[dict[str, ComponentStatus]] = None,
        deliver_notifications: bool = True,
    ) -> StatusPageUpdate:
        """Post an update to an existing incident.
        
        Args:
            incident_id: Incident ID to update
            status: New incident status
            body: Update message
            component_updates: Map of component ID to new status
            deliver_notifications: Whether to notify subscribers
            
        Returns:
            Created update
        """
        payload: dict[str, Any] = {
            "incident": {
                "status": status.value,
                "body": body,
                "deliver_notifications": deliver_notifications,
            }
        }
        
        if component_updates:
            payload["incident"]["component_ids"] = {
                cid: cs.value for cid, cs in component_updates.items()
            }
        
        response = await self.client.patch(
            f"/pages/{self.config.page_id}/incidents/{incident_id}",
            json=payload,
        )
        response.raise_for_status()
        
        update = StatusPageUpdate(
            incident_id=incident_id,
            status=status,
            body=body,
            affected_components=[
                (cid, cs) for cid, cs in (component_updates or {}).items()
            ],
            deliver_notifications=deliver_notifications,
        )
        
        # Update local cache
        if incident_id in self._incidents:
            self._incidents[incident_id].status = status
            self._incidents[incident_id].updates.append(update)
            self._incidents[incident_id].updated_at = datetime.now(timezone.utc)
        
        return update
    
    async def resolve_incident(
        self,
        incident_id: str,
        body: str = "This incident has been resolved.",
        deliver_notifications: bool = True,
    ) -> StatusPageUpdate:
        """Resolve an incident.
        
        Args:
            incident_id: Incident ID to resolve
            body: Resolution message
            deliver_notifications: Whether to notify subscribers
            
        Returns:
            Resolution update
        """
        # Set all affected components back to operational
        if incident_id in self._incidents:
            incident = self._incidents[incident_id]
            component_updates = {
                cid: ComponentStatus.OPERATIONAL
                for cid in incident.component_ids
            }
        else:
            component_updates = None
        
        update = await self.post_update(
            incident_id=incident_id,
            status=IncidentStatus.RESOLVED,
            body=body,
            component_updates=component_updates,
            deliver_notifications=deliver_notifications,
        )
        
        # Update local cache
        if incident_id in self._incidents:
            self._incidents[incident_id].resolved_at = datetime.now(timezone.utc)
        
        return update
    
    async def get_incident(self, incident_id: str) -> StatusPageIncident:
        """Get an incident by ID.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            Incident details
        """
        response = await self.client.get(
            f"/pages/{self.config.page_id}/incidents/{incident_id}"
        )
        response.raise_for_status()
        
        data = response.json()
        incident = StatusPageIncident(
            id=data["id"],
            name=data["name"],
            status=IncidentStatus(data["status"]),
            impact=IncidentImpact(data.get("impact", "minor")),
            shortlink=data.get("shortlink"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
        )
        
        self._incidents[incident.id] = incident
        return incident
    
    async def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        limit: int = 100,
    ) -> list[StatusPageIncident]:
        """List incidents.
        
        Args:
            status: Filter by status
            limit: Maximum number of incidents
            
        Returns:
            List of incidents
        """
        params = {"limit": limit}
        if status:
            params["status"] = status.value
        
        response = await self.client.get(
            f"/pages/{self.config.page_id}/incidents",
            params=params,
        )
        response.raise_for_status()
        
        incidents = []
        for data in response.json():
            incident = StatusPageIncident(
                id=data["id"],
                name=data["name"],
                status=IncidentStatus(data["status"]),
                impact=IncidentImpact(data.get("impact", "minor")),
                shortlink=data.get("shortlink"),
            )
            incidents.append(incident)
            self._incidents[incident.id] = incident
        
        return incidents
    
    async def create_scheduled_maintenance(
        self,
        name: str,
        scheduled_for: datetime,
        scheduled_until: datetime,
        body: Optional[str] = None,
        component_ids: Optional[list[str]] = None,
        auto_transition: bool = True,
        remind_prior: bool = True,
    ) -> StatusPageIncident:
        """Create a scheduled maintenance window.
        
        Args:
            name: Maintenance name/title
            scheduled_for: Start time
            scheduled_until: End time
            body: Maintenance description
            component_ids: Affected component IDs
            auto_transition: Automatically transition status at times
            remind_prior: Send reminder before maintenance
            
        Returns:
            Created scheduled maintenance
        """
        payload: dict[str, Any] = {
            "incident": {
                "name": name,
                "status": "scheduled",
                "scheduled_for": scheduled_for.isoformat(),
                "scheduled_until": scheduled_until.isoformat(),
                "scheduled_remind_prior": remind_prior,
                "scheduled_auto_in_progress": auto_transition,
                "scheduled_auto_completed": auto_transition,
            }
        }
        
        if body:
            payload["incident"]["body"] = body
        
        if component_ids:
            payload["incident"]["component_ids"] = {
                cid: ComponentStatus.UNDER_MAINTENANCE.value
                for cid in component_ids
            }
        
        response = await self.client.post(
            f"/pages/{self.config.page_id}/incidents",
            json=payload,
        )
        response.raise_for_status()
        
        data = response.json()
        incident = StatusPageIncident(
            id=data["id"],
            name=data["name"],
            status=IncidentStatus.SCHEDULED,
            impact=IncidentImpact.MAINTENANCE,
            body=body,
            component_ids=component_ids or [],
            scheduled_for=scheduled_for,
            scheduled_until=scheduled_until,
            scheduled_remind_prior=remind_prior,
            scheduled_auto_in_progress=auto_transition,
            scheduled_auto_completed=auto_transition,
            shortlink=data.get("shortlink"),
        )
        
        self._incidents[incident.id] = incident
        return incident
    
    def get_component_id_for_service(self, service_name: str) -> Optional[str]:
        """Get component ID for a service name using configured mapping.
        
        Args:
            service_name: Service name to look up
            
        Returns:
            Component ID if found, None otherwise
        """
        return self.config.component_mapping.get(service_name)
    
    async def auto_incident_from_alert(
        self,
        alert_name: str,
        alert_id: str,
        affected_services: list[str],
        severity: str,
        investigation_id: Optional[str] = None,
    ) -> Optional[StatusPageIncident]:
        """Automatically create an incident from an alert.
        
        Uses configured component mapping to determine affected components.
        
        Args:
            alert_name: Name of the alert
            alert_id: Alert ID for correlation
            affected_services: List of affected service names
            severity: Alert severity (critical, warning, etc.)
            investigation_id: Correlated investigation ID
            
        Returns:
            Created incident if auto-creation enabled, None otherwise
        """
        if not self.config.auto_create_incidents:
            return None
        
        # Map services to component IDs
        component_ids = []
        for service in affected_services:
            cid = self.get_component_id_for_service(service)
            if cid:
                component_ids.append(cid)
        
        # Determine impact based on severity
        impact_mapping = {
            "critical": IncidentImpact.CRITICAL,
            "high": IncidentImpact.MAJOR,
            "warning": IncidentImpact.MINOR,
            "low": IncidentImpact.MINOR,
        }
        impact = impact_mapping.get(severity.lower(), self.config.default_impact)
        
        # Determine component status based on impact
        component_status_mapping = {
            IncidentImpact.CRITICAL: ComponentStatus.MAJOR_OUTAGE,
            IncidentImpact.MAJOR: ComponentStatus.PARTIAL_OUTAGE,
            IncidentImpact.MINOR: ComponentStatus.DEGRADED_PERFORMANCE,
        }
        component_status = component_status_mapping.get(
            impact, ComponentStatus.DEGRADED_PERFORMANCE
        )
        
        incident = await self.create_incident(
            name=alert_name,
            status=IncidentStatus.INVESTIGATING,
            impact=impact,
            body=f"We are investigating an issue affecting {', '.join(affected_services)}.",
            component_ids=component_ids if component_ids else None,
            component_status=component_status,
            alert_id=alert_id,
            investigation_id=investigation_id,
        )
        
        return incident
