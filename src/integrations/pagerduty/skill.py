"""PagerDuty skill for AutoSRE.

Provides actions for querying PagerDuty incidents, alerts, services,
and on-call information during investigations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from autosre.skills import ActionResult, Skill, action

from .client import (
    PagerDutyClient,
    PagerDutyError,
    PagerDutyNotFoundError,
)
from .models import (
    Alert,
    Escalation,
    Incident,
    LogEntry,
    Note,
    OnCall,
    Service,
    User,
)

logger = logging.getLogger(__name__)


class PagerDutySkill(Skill):
    """Skill for interacting with PagerDuty.
    
    Provides actions for:
    - Getting incident details and timeline
    - Finding related incidents
    - Getting on-call responders
    - Adding notes and updating incidents
    
    Configuration:
        api_key: PagerDuty REST API key
        requester_email: Email for write operations (From header)
    """
    
    name = "pagerduty"
    version = "1.0.0"
    description = "Query and manage PagerDuty incidents, alerts, and on-call schedules"
    
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize PagerDuty skill.
        
        Args:
            config: Configuration dict with:
                - api_key: PagerDuty API key (required)
                - requester_email: Email for write operations
                - base_url: API base URL (optional)
        """
        super().__init__(config)
        self._client: PagerDutyClient | None = None
    
    async def initialize(self) -> None:
        """Initialize the PagerDuty client."""
        api_key = self.config.get("api_key")
        if not api_key:
            logger.warning("PagerDuty API key not configured")
            self._initialized = False
            return
        
        self._client = PagerDutyClient(
            api_key=api_key,
            requester_email=self.config.get("requester_email"),
            base_url=self.config.get("base_url", PagerDutyClient.DEFAULT_BASE_URL),
        )
        
        # Register actions
        self._register_actions()
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Close the PagerDuty client."""
        if self._client:
            await self._client.close()
            self._client = None
        self._initialized = False
    
    def _register_actions(self) -> None:
        """Register all skill actions."""
        self.register_action(
            name="get_incident",
            handler=self.get_incident,
            description="Get details of a specific PagerDuty incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
                {"name": "include_alerts", "type": "bool", "required": False, "description": "Include alerts"},
            ],
            returns="Incident details",
        )
        
        self.register_action(
            name="get_incident_timeline",
            handler=self.get_incident_timeline,
            description="Get the full timeline of events for an incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
                {"name": "max_entries", "type": "int", "required": False, "description": "Max log entries"},
            ],
            returns="List of log entries",
        )
        
        self.register_action(
            name="get_related_incidents",
            handler=self.get_related_incidents,
            description="Find incidents related to the current one",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
                {"name": "lookback_hours", "type": "int", "required": False, "description": "Hours to look back"},
                {"name": "max_results", "type": "int", "required": False, "description": "Max incidents"},
            ],
            returns="List of related incidents",
        )
        
        self.register_action(
            name="get_oncall_responders",
            handler=self.get_oncall_responders,
            description="Get current on-call responders for a service or escalation policy",
            params=[
                {"name": "service_id", "type": "str", "required": False, "description": "Service ID"},
                {"name": "escalation_policy_id", "type": "str", "required": False, "description": "Escalation policy ID"},
                {"name": "incident_id", "type": "str", "required": False, "description": "Get from incident"},
            ],
            returns="List of on-call users",
        )
        
        self.register_action(
            name="list_incidents",
            handler=self.list_incidents,
            description="List incidents with optional filters",
            params=[
                {"name": "status", "type": "str", "required": False, "description": "Filter by status"},
                {"name": "service_ids", "type": "list[str]", "required": False, "description": "Filter by services"},
                {"name": "since_hours", "type": "int", "required": False, "description": "Incidents from last N hours"},
                {"name": "limit", "type": "int", "required": False, "description": "Max results"},
            ],
            returns="List of incidents",
        )
        
        self.register_action(
            name="list_alerts",
            handler=self.list_alerts,
            description="List alerts for an incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
            ],
            returns="List of alerts",
        )
        
        self.register_action(
            name="get_service",
            handler=self.get_service,
            description="Get details of a PagerDuty service",
            params=[
                {"name": "service_id", "type": "str", "required": True, "description": "Service ID"},
            ],
            returns="Service details",
        )
        
        self.register_action(
            name="add_note",
            handler=self.add_note,
            description="Add a note to an incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
                {"name": "note", "type": "str", "required": True, "description": "Note content"},
            ],
            returns="Created note",
            requires_approval=False,  # Notes are generally safe
        )
        
        self.register_action(
            name="acknowledge_incident",
            handler=self.acknowledge_incident,
            description="Acknowledge an incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
            ],
            returns="Updated incident",
            requires_approval=True,  # State changes need approval
        )
        
        self.register_action(
            name="resolve_incident",
            handler=self.resolve_incident,
            description="Resolve an incident",
            params=[
                {"name": "incident_id", "type": "str", "required": True, "description": "PagerDuty incident ID"},
                {"name": "resolution", "type": "str", "required": False, "description": "Resolution note"},
            ],
            returns="Updated incident",
            requires_approval=True,  # State changes need approval
        )
    
    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check if PagerDuty API is accessible."""
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            # Try to list users as a health check
            users = await self._client.list_users(limit=1)
            return ActionResult.ok({
                "healthy": True,
                "api_accessible": True,
                "users_count": len(users),
            })
        except PagerDutyError as e:
            return ActionResult.fail(f"PagerDuty API error: {e}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")
    
    # -------------------------------------------------------------------------
    # Read Actions
    # -------------------------------------------------------------------------
    
    @action(description="Get details of a specific PagerDuty incident")
    async def get_incident(
        self,
        incident_id: str,
        include_alerts: bool = False,
    ) -> ActionResult[dict[str, Any]]:
        """Get incident details.
        
        Args:
            incident_id: PagerDuty incident ID
            include_alerts: Whether to include alerts
            
        Returns:
            ActionResult with incident data
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            include = ["acknowledgers", "assignees", "services"]
            if include_alerts:
                include.append("alerts")
            
            incident = await self._client.get_incident(incident_id, include=include)
            
            return ActionResult.ok(
                self._serialize_incident(incident),
                source="pagerduty",
                incident_number=incident.incident_number,
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to get incident: {e}")
    
    @action(description="Get the full timeline of events for an incident")
    async def get_incident_timeline(
        self,
        incident_id: str,
        max_entries: int = 100,
    ) -> ActionResult[list[dict[str, Any]]]:
        """Get incident timeline (log entries).
        
        Args:
            incident_id: PagerDuty incident ID
            max_entries: Maximum entries to return
            
        Returns:
            ActionResult with list of timeline entries
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            entries = await self._client.get_incident_timeline(
                incident_id=incident_id,
                max_entries=max_entries,
            )
            
            timeline = [self._serialize_log_entry(e) for e in entries]
            
            return ActionResult.ok(
                timeline,
                source="pagerduty",
                entry_count=len(timeline),
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to get timeline: {e}")
    
    @action(description="Find incidents related to the current one")
    async def get_related_incidents(
        self,
        incident_id: str,
        lookback_hours: int = 24,
        max_results: int = 10,
    ) -> ActionResult[list[dict[str, Any]]]:
        """Get related incidents.
        
        Finds incidents that:
        - Affect the same service
        - Occurred within the lookback window
        
        Args:
            incident_id: PagerDuty incident ID
            lookback_hours: Hours to look back
            max_results: Max incidents to return
            
        Returns:
            ActionResult with list of related incidents
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            related = await self._client.get_related_incidents(
                incident_id=incident_id,
                lookback_hours=lookback_hours,
                max_results=max_results,
            )
            
            incidents = [self._serialize_incident(i) for i in related]
            
            return ActionResult.ok(
                incidents,
                source="pagerduty",
                incident_count=len(incidents),
                lookback_hours=lookback_hours,
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to get related incidents: {e}")
    
    @action(description="Get current on-call responders")
    async def get_oncall_responders(
        self,
        service_id: str | None = None,
        escalation_policy_id: str | None = None,
        incident_id: str | None = None,
    ) -> ActionResult[list[dict[str, Any]]]:
        """Get on-call responders.
        
        At least one of service_id, escalation_policy_id, or incident_id must be provided.
        
        Args:
            service_id: Service ID to get on-call for
            escalation_policy_id: Escalation policy ID
            incident_id: Get on-call for this incident's service
            
        Returns:
            ActionResult with list of on-call users
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            # Get escalation policy from incident or service if needed
            if incident_id and not escalation_policy_id:
                incident = await self._client.get_incident(incident_id)
                if incident.escalation_policy:
                    if isinstance(incident.escalation_policy, dict):
                        escalation_policy_id = incident.escalation_policy.get("id")
                    else:
                        escalation_policy_id = incident.escalation_policy.id
            
            if service_id and not escalation_policy_id:
                service = await self._client.get_service(service_id, include=["escalation_policies"])
                if service.escalation_policy:
                    if isinstance(service.escalation_policy, dict):
                        escalation_policy_id = service.escalation_policy.get("id")
            
            if not escalation_policy_id:
                return ActionResult.fail("Could not determine escalation policy")
            
            # Get on-call for all levels
            oncalls = await self._client.list_oncalls(
                escalation_policy_ids=[escalation_policy_id],
                earliest=True,
            )
            
            responders = []
            for oncall in oncalls:
                responders.append({
                    "user": {
                        "id": oncall.user.id,
                        "name": oncall.user.name,
                        "email": oncall.user.email,
                    },
                    "escalation_level": oncall.escalation_level,
                    "start": oncall.start.isoformat() if oncall.start else None,
                    "end": oncall.end.isoformat() if oncall.end else None,
                })
            
            # Sort by escalation level
            responders.sort(key=lambda x: x["escalation_level"])
            
            return ActionResult.ok(
                responders,
                source="pagerduty",
                escalation_policy_id=escalation_policy_id,
                responder_count=len(responders),
            )
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to get on-call responders: {e}")
    
    @action(description="List incidents with optional filters")
    async def list_incidents(
        self,
        status: str | None = None,
        service_ids: list[str] | None = None,
        since_hours: int | None = None,
        limit: int = 25,
    ) -> ActionResult[list[dict[str, Any]]]:
        """List incidents.
        
        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            service_ids: Filter by service IDs
            since_hours: Only include incidents from last N hours
            limit: Maximum results
            
        Returns:
            ActionResult with list of incidents
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            since = None
            if since_hours:
                since = datetime.utcnow() - timedelta(hours=since_hours)
            
            incidents = await self._client.list_incidents(
                status=status,
                service_ids=service_ids,
                since=since,
                limit=limit,
            )
            
            result = [self._serialize_incident(i) for i in incidents]
            
            return ActionResult.ok(
                result,
                source="pagerduty",
                incident_count=len(result),
                filters={"status": status, "service_ids": service_ids, "since_hours": since_hours},
            )
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to list incidents: {e}")
    
    @action(description="List alerts for an incident")
    async def list_alerts(
        self,
        incident_id: str,
    ) -> ActionResult[list[dict[str, Any]]]:
        """List alerts for an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            
        Returns:
            ActionResult with list of alerts
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            alerts = await self._client.list_alerts(incident_id=incident_id)
            result = [self._serialize_alert(a) for a in alerts]
            
            return ActionResult.ok(
                result,
                source="pagerduty",
                alert_count=len(result),
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to list alerts: {e}")
    
    @action(description="Get details of a PagerDuty service")
    async def get_service(
        self,
        service_id: str,
    ) -> ActionResult[dict[str, Any]]:
        """Get service details.
        
        Args:
            service_id: PagerDuty service ID
            
        Returns:
            ActionResult with service data
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            service = await self._client.get_service(
                service_id=service_id,
                include=["integrations", "escalation_policies", "teams"],
            )
            
            return ActionResult.ok(
                self._serialize_service(service),
                source="pagerduty",
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Service not found: {service_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to get service: {e}")
    
    # -------------------------------------------------------------------------
    # Write Actions
    # -------------------------------------------------------------------------
    
    @action(description="Add a note to an incident")
    async def add_note(
        self,
        incident_id: str,
        note: str,
    ) -> ActionResult[dict[str, Any]]:
        """Add a note to an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            note: Note content
            
        Returns:
            ActionResult with created note
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            created_note = await self._client.add_note(
                incident_id=incident_id,
                note=note,
            )
            
            return ActionResult.ok(
                {
                    "id": created_note.id,
                    "content": created_note.content,
                    "created_at": created_note.created_at.isoformat(),
                },
                source="pagerduty",
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to add note: {e}")
    
    @action(description="Acknowledge an incident", requires_approval=True)
    async def acknowledge_incident(
        self,
        incident_id: str,
    ) -> ActionResult[dict[str, Any]]:
        """Acknowledge an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            
        Returns:
            ActionResult with updated incident
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            incident = await self._client.acknowledge_incident(incident_id)
            
            return ActionResult.ok(
                self._serialize_incident(incident),
                source="pagerduty",
                action="acknowledged",
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to acknowledge incident: {e}")
    
    @action(description="Resolve an incident", requires_approval=True)
    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str | None = None,
    ) -> ActionResult[dict[str, Any]]:
        """Resolve an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            resolution: Resolution note
            
        Returns:
            ActionResult with updated incident
        """
        if not self._client:
            return ActionResult.fail("PagerDuty client not initialized")
        
        try:
            incident = await self._client.resolve_incident(
                incident_id=incident_id,
                resolution=resolution,
            )
            
            return ActionResult.ok(
                self._serialize_incident(incident),
                source="pagerduty",
                action="resolved",
            )
        except PagerDutyNotFoundError:
            return ActionResult.fail(f"Incident not found: {incident_id}")
        except PagerDutyError as e:
            return ActionResult.fail(f"Failed to resolve incident: {e}")
    
    # -------------------------------------------------------------------------
    # Serialization Helpers
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _serialize_incident(incident: Incident) -> dict[str, Any]:
        """Serialize incident for action result."""
        service_info = None
        if incident.service:
            if isinstance(incident.service, dict):
                service_info = {
                    "id": incident.service.get("id"),
                    "name": incident.service.get("name"),
                }
            else:
                service_info = {
                    "id": incident.service.id,
                    "name": incident.service.name,
                }
        
        return {
            "id": incident.id,
            "incident_number": incident.incident_number,
            "title": incident.title,
            "description": incident.description,
            "status": incident.status.value if incident.status else None,
            "urgency": incident.urgency.value if incident.urgency else None,
            "html_url": incident.html_url,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "service": service_info,
            "is_open": incident.is_open,
            "assigned_users": incident.assigned_users,
            "priority": incident.priority.name if incident.priority else None,
        }
    
    @staticmethod
    def _serialize_alert(alert: Alert) -> dict[str, Any]:
        """Serialize alert for action result."""
        return {
            "id": alert.id,
            "status": alert.status,
            "alert_key": alert.alert_key,
            "severity": alert.severity.value if alert.severity else None,
            "summary": alert.summary,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "suppressed": alert.suppressed,
            "details": alert.body.details if alert.body else {},
        }
    
    @staticmethod
    def _serialize_service(service: Service) -> dict[str, Any]:
        """Serialize service for action result."""
        return {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "status": service.status,
            "html_url": service.html_url,
            "created_at": service.created_at.isoformat() if service.created_at else None,
            "teams": service.teams,
        }
    
    @staticmethod
    def _serialize_log_entry(entry: LogEntry) -> dict[str, Any]:
        """Serialize log entry for action result."""
        return {
            "id": entry.id,
            "type": entry.type,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "note": entry.note,
            "agent": entry.agent,
            "channel": entry.channel,
            "contexts": entry.contexts,
        }
