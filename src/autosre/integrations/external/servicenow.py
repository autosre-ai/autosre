"""ServiceNow Integration for AutoSRE V2.

Provides ITSM integration with ServiceNow:
- Incident management
- Change requests
- Problem management
- CMDB queries
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.integrations.base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceNowState(str, Enum):
    """ServiceNow incident states."""
    
    NEW = "1"
    IN_PROGRESS = "2"
    ON_HOLD = "3"
    RESOLVED = "6"
    CLOSED = "7"
    CANCELED = "8"


class ServiceNowImpact(str, Enum):
    """ServiceNow impact levels."""
    
    HIGH = "1"
    MEDIUM = "2"
    LOW = "3"


class ServiceNowUrgency(str, Enum):
    """ServiceNow urgency levels."""
    
    HIGH = "1"
    MEDIUM = "2"
    LOW = "3"


class ServiceNowPriority(str, Enum):
    """ServiceNow priority (calculated from impact/urgency)."""
    
    CRITICAL = "1"
    HIGH = "2"
    MODERATE = "3"
    LOW = "4"
    PLANNING = "5"


@dataclass
class ServiceNowConfig:
    """Configuration for ServiceNow integration."""
    
    # Connection
    instance_url: str  # e.g., https://company.service-now.com
    username: str
    password: str
    
    # Optional OAuth
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    
    # Defaults
    default_assignment_group: Optional[str] = None
    default_category: Optional[str] = None
    
    # Timeouts
    timeout_seconds: float = 30.0


class ServiceNowUser(BaseModel):
    """ServiceNow user model."""
    
    sys_id: str
    user_name: str
    name: str
    email: Optional[str] = None


class ServiceNowIncident(BaseModel):
    """ServiceNow incident model."""
    
    # Identity
    sys_id: Optional[str] = None
    number: Optional[str] = None
    
    # Basic fields
    short_description: str
    description: Optional[str] = None
    
    # Classification
    impact: ServiceNowImpact = ServiceNowImpact.MEDIUM
    urgency: ServiceNowUrgency = ServiceNowUrgency.MEDIUM
    priority: Optional[ServiceNowPriority] = None
    
    # Category
    category: Optional[str] = None
    subcategory: Optional[str] = None
    
    # Assignment
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    
    # Status
    state: ServiceNowState = ServiceNowState.NEW
    
    # Caller/requestor
    caller_id: Optional[str] = None
    
    # Configuration item
    cmdb_ci: Optional[str] = None
    
    # Resolution
    close_code: Optional[str] = None
    close_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    
    # Timing
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Work notes
    work_notes: Optional[str] = None
    comments: Optional[str] = None
    
    # Custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    sys_created_on: Optional[datetime] = None
    sys_updated_on: Optional[datetime] = None
    
    def to_create_payload(self) -> Dict[str, Any]:
        """Convert to ServiceNow API create payload."""
        payload = {
            "short_description": self.short_description,
            "impact": self.impact.value,
            "urgency": self.urgency.value,
        }
        
        if self.description:
            payload["description"] = self.description
        
        if self.category:
            payload["category"] = self.category
        if self.subcategory:
            payload["subcategory"] = self.subcategory
        
        if self.assignment_group:
            payload["assignment_group"] = self.assignment_group
        if self.assigned_to:
            payload["assigned_to"] = self.assigned_to
        
        if self.caller_id:
            payload["caller_id"] = self.caller_id
        
        if self.cmdb_ci:
            payload["cmdb_ci"] = self.cmdb_ci
        
        if self.work_notes:
            payload["work_notes"] = self.work_notes
        
        # Add custom fields
        payload.update(self.custom_fields)
        
        return payload


class ServiceNowChangeRequest(BaseModel):
    """ServiceNow change request model."""
    
    # Identity
    sys_id: Optional[str] = None
    number: Optional[str] = None
    
    # Basic fields
    short_description: str
    description: Optional[str] = None
    
    # Classification
    type: str = "normal"  # emergency, normal, standard
    risk: str = "moderate"  # high, moderate, low
    impact: ServiceNowImpact = ServiceNowImpact.MEDIUM
    
    # Assignment
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    
    # Status
    state: Optional[str] = None
    
    # Planning
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Implementation
    implementation_plan: Optional[str] = None
    backout_plan: Optional[str] = None
    test_plan: Optional[str] = None
    
    # Related
    cmdb_ci: Optional[str] = None
    
    # Approvals
    approval: Optional[str] = None
    
    # Custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    def to_create_payload(self) -> Dict[str, Any]:
        """Convert to ServiceNow API create payload."""
        payload = {
            "short_description": self.short_description,
            "type": self.type,
            "risk": self.risk,
            "impact": self.impact.value,
        }
        
        if self.description:
            payload["description"] = self.description
        
        if self.assignment_group:
            payload["assignment_group"] = self.assignment_group
        if self.assigned_to:
            payload["assigned_to"] = self.assigned_to
        
        if self.start_date:
            payload["start_date"] = self.start_date.strftime("%Y-%m-%d %H:%M:%S")
        if self.end_date:
            payload["end_date"] = self.end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        if self.implementation_plan:
            payload["implementation_plan"] = self.implementation_plan
        if self.backout_plan:
            payload["backout_plan"] = self.backout_plan
        if self.test_plan:
            payload["test_plan"] = self.test_plan
        
        if self.cmdb_ci:
            payload["cmdb_ci"] = self.cmdb_ci
        
        payload.update(self.custom_fields)
        
        return payload


class ServiceNowQueryResult(BaseModel):
    """Result of a ServiceNow query."""
    
    records: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ServiceNowIntegration(AuthenticatedIntegration):
    """
    ServiceNow integration for ITSM.
    
    Provides comprehensive ServiceNow functionality:
    - Incident management
    - Change request management
    - Problem management
    - CMDB queries
    
    Example:
        config = ServiceNowConfig(
            instance_url="https://company.service-now.com",
            username="integration_user",
            password="password",
        )
        
        async with ServiceNowIntegration(config) as snow:
            # Create incident
            incident = await snow.create_incident(ServiceNowIncident(
                short_description="High CPU usage on prod-web-01",
                description="CPU utilization exceeded 90% for 15 minutes",
                impact=ServiceNowImpact.HIGH,
                urgency=ServiceNowUrgency.HIGH,
            ))
            
            # Update work notes
            await snow.add_work_note(incident.sys_id, "Investigating...")
            
            # Resolve
            await snow.resolve_incident(
                incident.sys_id,
                close_code="Resolved",
                close_notes="Scaled horizontally",
            )
    """
    
    def __init__(self, config: ServiceNowConfig):
        """Initialize ServiceNow integration.
        
        Args:
            config: ServiceNow configuration
        """
        self.snow_config = config
        
        # Create connection config
        conn_config = ConnectionConfig(
            base_url=config.instance_url,
            timeout=config.timeout_seconds,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        
        super().__init__(
            config=conn_config,
            username=config.username,
            password=config.password,
        )
    
    @property
    def name(self) -> str:
        return "servicenow"
    
    async def health_check(self) -> HealthCheckResult:
        """Check ServiceNow connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            # Query sys_user table with limit 1
            await self._request(
                "GET",
                "/api/now/table/sys_user",
                params={"sysparm_limit": 1},
            )
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Connected to ServiceNow",
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    # Incident Management
    
    async def create_incident(
        self,
        incident: ServiceNowIncident,
    ) -> ServiceNowIncident:
        """Create a ServiceNow incident.
        
        Args:
            incident: Incident to create
            
        Returns:
            Created incident with sys_id and number
        """
        # Apply defaults
        if not incident.assignment_group and self.snow_config.default_assignment_group:
            incident.assignment_group = self.snow_config.default_assignment_group
        if not incident.category and self.snow_config.default_category:
            incident.category = self.snow_config.default_category
        
        payload = incident.to_create_payload()
        
        data = await self._request(
            "POST",
            "/api/now/table/incident",
            json=payload,
        )
        
        result = data.get("result", {})
        incident.sys_id = result.get("sys_id")
        incident.number = result.get("number")
        
        logger.info(
            "Created ServiceNow incident",
            number=incident.number,
            sys_id=incident.sys_id,
        )
        
        return incident
    
    async def get_incident(self, sys_id: str) -> ServiceNowIncident:
        """Get an incident by sys_id.
        
        Args:
            sys_id: Incident sys_id
            
        Returns:
            ServiceNowIncident
        """
        data = await self._request(
            "GET",
            f"/api/now/table/incident/{sys_id}",
        )
        
        return self._parse_incident(data.get("result", {}))
    
    async def get_incident_by_number(self, number: str) -> Optional[ServiceNowIncident]:
        """Get an incident by number.
        
        Args:
            number: Incident number (e.g., "INC0012345")
            
        Returns:
            ServiceNowIncident or None
        """
        data = await self._request(
            "GET",
            "/api/now/table/incident",
            params={"sysparm_query": f"number={number}", "sysparm_limit": 1},
        )
        
        results = data.get("result", [])
        if not results:
            return None
        
        return self._parse_incident(results[0])
    
    async def update_incident(
        self,
        sys_id: str,
        updates: Dict[str, Any],
    ) -> ServiceNowIncident:
        """Update incident fields.
        
        Args:
            sys_id: Incident sys_id
            updates: Fields to update
            
        Returns:
            Updated incident
        """
        data = await self._request(
            "PATCH",
            f"/api/now/table/incident/{sys_id}",
            json=updates,
        )
        
        logger.info(
            "Updated ServiceNow incident",
            sys_id=sys_id,
            fields=list(updates.keys()),
        )
        
        return self._parse_incident(data.get("result", {}))
    
    async def add_work_note(
        self,
        sys_id: str,
        note: str,
    ) -> None:
        """Add a work note to an incident.
        
        Args:
            sys_id: Incident sys_id
            note: Work note content
        """
        await self._request(
            "PATCH",
            f"/api/now/table/incident/{sys_id}",
            json={"work_notes": note},
        )
        
        logger.info(
            "Added work note to incident",
            sys_id=sys_id,
        )
    
    async def add_comment(
        self,
        sys_id: str,
        comment: str,
    ) -> None:
        """Add a customer-visible comment to an incident.
        
        Args:
            sys_id: Incident sys_id
            comment: Comment content
        """
        await self._request(
            "PATCH",
            f"/api/now/table/incident/{sys_id}",
            json={"comments": comment},
        )
    
    async def assign_incident(
        self,
        sys_id: str,
        assignment_group: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> None:
        """Assign an incident.
        
        Args:
            sys_id: Incident sys_id
            assignment_group: Group sys_id
            assigned_to: User sys_id
        """
        updates = {}
        if assignment_group:
            updates["assignment_group"] = assignment_group
        if assigned_to:
            updates["assigned_to"] = assigned_to
        
        if updates:
            await self.update_incident(sys_id, updates)
    
    async def resolve_incident(
        self,
        sys_id: str,
        close_code: str,
        close_notes: str,
    ) -> ServiceNowIncident:
        """Resolve an incident.
        
        Args:
            sys_id: Incident sys_id
            close_code: Resolution code
            close_notes: Resolution notes
            
        Returns:
            Updated incident
        """
        updates = {
            "state": ServiceNowState.RESOLVED.value,
            "close_code": close_code,
            "close_notes": close_notes,
        }
        
        result = await self.update_incident(sys_id, updates)
        
        logger.info(
            "Resolved ServiceNow incident",
            sys_id=sys_id,
            close_code=close_code,
        )
        
        return result
    
    async def close_incident(
        self,
        sys_id: str,
        close_code: str,
        close_notes: str,
    ) -> ServiceNowIncident:
        """Close an incident.
        
        Args:
            sys_id: Incident sys_id
            close_code: Close code
            close_notes: Close notes
            
        Returns:
            Updated incident
        """
        updates = {
            "state": ServiceNowState.CLOSED.value,
            "close_code": close_code,
            "close_notes": close_notes,
        }
        
        return await self.update_incident(sys_id, updates)
    
    async def query_incidents(
        self,
        query: str,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "-sys_created_on",
    ) -> List[ServiceNowIncident]:
        """Query incidents.
        
        Args:
            query: ServiceNow query string
            limit: Maximum results
            offset: Pagination offset
            order_by: Sort order
            
        Returns:
            List of incidents
        """
        params = {
            "sysparm_query": query,
            "sysparm_limit": limit,
            "sysparm_offset": offset,
            "sysparm_orderby": order_by,
        }
        
        data = await self._request(
            "GET",
            "/api/now/table/incident",
            params=params,
        )
        
        return [self._parse_incident(r) for r in data.get("result", [])]
    
    # Change Request Management
    
    async def create_change_request(
        self,
        change: ServiceNowChangeRequest,
    ) -> ServiceNowChangeRequest:
        """Create a change request.
        
        Args:
            change: Change request to create
            
        Returns:
            Created change request
        """
        if not change.assignment_group and self.snow_config.default_assignment_group:
            change.assignment_group = self.snow_config.default_assignment_group
        
        payload = change.to_create_payload()
        
        data = await self._request(
            "POST",
            "/api/now/table/change_request",
            json=payload,
        )
        
        result = data.get("result", {})
        change.sys_id = result.get("sys_id")
        change.number = result.get("number")
        
        logger.info(
            "Created ServiceNow change request",
            number=change.number,
            type=change.type,
        )
        
        return change
    
    async def get_change_request(self, sys_id: str) -> ServiceNowChangeRequest:
        """Get a change request.
        
        Args:
            sys_id: Change request sys_id
            
        Returns:
            ServiceNowChangeRequest
        """
        data = await self._request(
            "GET",
            f"/api/now/table/change_request/{sys_id}",
        )
        
        result = data.get("result", {})
        
        return ServiceNowChangeRequest(
            sys_id=result.get("sys_id"),
            number=result.get("number"),
            short_description=result.get("short_description", ""),
            description=result.get("description"),
            type=result.get("type", "normal"),
            risk=result.get("risk", "moderate"),
            state=result.get("state"),
            assignment_group=result.get("assignment_group", {}).get("value") if isinstance(result.get("assignment_group"), dict) else result.get("assignment_group"),
        )
    
    async def update_change_request(
        self,
        sys_id: str,
        updates: Dict[str, Any],
    ) -> ServiceNowChangeRequest:
        """Update a change request.
        
        Args:
            sys_id: Change request sys_id
            updates: Fields to update
            
        Returns:
            Updated change request
        """
        data = await self._request(
            "PATCH",
            f"/api/now/table/change_request/{sys_id}",
            json=updates,
        )
        
        return await self.get_change_request(sys_id)
    
    # CMDB Queries
    
    async def get_ci(self, sys_id: str) -> Dict[str, Any]:
        """Get a configuration item.
        
        Args:
            sys_id: CI sys_id
            
        Returns:
            CI data
        """
        data = await self._request(
            "GET",
            f"/api/now/table/cmdb_ci/{sys_id}",
        )
        
        return data.get("result", {})
    
    async def query_cis(
        self,
        query: str,
        table: str = "cmdb_ci",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query configuration items.
        
        Args:
            query: ServiceNow query string
            table: CMDB table name
            limit: Maximum results
            
        Returns:
            List of CIs
        """
        data = await self._request(
            "GET",
            f"/api/now/table/{table}",
            params={"sysparm_query": query, "sysparm_limit": limit},
        )
        
        return data.get("result", [])
    
    # Generic Table Operations
    
    async def query_table(
        self,
        table: str,
        query: str = "",
        fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ServiceNowQueryResult:
        """Query any ServiceNow table.
        
        Args:
            table: Table name
            query: Query string
            fields: Fields to return
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Query result
        """
        params = {
            "sysparm_limit": limit,
            "sysparm_offset": offset,
        }
        
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        data = await self._request(
            "GET",
            f"/api/now/table/{table}",
            params=params,
        )
        
        return ServiceNowQueryResult(
            records=data.get("result", []),
            total=len(data.get("result", [])),
        )
    
    async def create_autosre_incident(
        self,
        title: str,
        description: str,
        severity: str,
        investigation_id: Optional[str] = None,
        affected_ci: Optional[str] = None,
    ) -> ServiceNowIncident:
        """Create an incident with AutoSRE context.
        
        Args:
            title: Incident title
            description: Description
            severity: Severity level
            investigation_id: AutoSRE investigation ID
            affected_ci: Affected CI sys_id
            
        Returns:
            Created incident
        """
        # Map severity
        impact_map = {
            "critical": ServiceNowImpact.HIGH,
            "high": ServiceNowImpact.HIGH,
            "medium": ServiceNowImpact.MEDIUM,
            "low": ServiceNowImpact.LOW,
        }
        urgency_map = {
            "critical": ServiceNowUrgency.HIGH,
            "high": ServiceNowUrgency.HIGH,
            "medium": ServiceNowUrgency.MEDIUM,
            "low": ServiceNowUrgency.LOW,
        }
        
        impact = impact_map.get(severity.lower(), ServiceNowImpact.MEDIUM)
        urgency = urgency_map.get(severity.lower(), ServiceNowUrgency.MEDIUM)
        
        # Build description
        full_description = description
        if investigation_id:
            full_description += f"\n\n[AutoSRE Investigation: {investigation_id}]"
        
        incident = ServiceNowIncident(
            short_description=title,
            description=full_description,
            impact=impact,
            urgency=urgency,
            cmdb_ci=affected_ci,
            custom_fields={
                "u_autosre_investigation_id": investigation_id,
            } if investigation_id else {},
        )
        
        return await self.create_incident(incident)
    
    def _parse_incident(self, data: Dict[str, Any]) -> ServiceNowIncident:
        """Parse incident data from API response."""
        return ServiceNowIncident(
            sys_id=data.get("sys_id"),
            number=data.get("number"),
            short_description=data.get("short_description", ""),
            description=data.get("description"),
            impact=ServiceNowImpact(data.get("impact", "2")),
            urgency=ServiceNowUrgency(data.get("urgency", "2")),
            priority=ServiceNowPriority(data["priority"]) if data.get("priority") else None,
            category=data.get("category"),
            subcategory=data.get("subcategory"),
            state=ServiceNowState(data.get("state", "1")),
            assignment_group=self._extract_value(data.get("assignment_group")),
            assigned_to=self._extract_value(data.get("assigned_to")),
            caller_id=self._extract_value(data.get("caller_id")),
            cmdb_ci=self._extract_value(data.get("cmdb_ci")),
            close_code=data.get("close_code"),
            close_notes=data.get("close_notes"),
        )
    
    def _extract_value(self, field: Any) -> Optional[str]:
        """Extract value from ServiceNow field (handles link objects)."""
        if field is None:
            return None
        if isinstance(field, dict):
            return field.get("value")
        return str(field)
