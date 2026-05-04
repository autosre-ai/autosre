"""
PagerDuty Connector - Pull incident and on-call information.

This connector provides:
- On-call schedules
- Past incidents
- Escalation policies
- Service ownership
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from autosre.foundation.connectors.base import BaseConnector
from autosre.foundation.models import Ownership, Incident, Severity


class PagerDutyConnector(BaseConnector):
    """
    PagerDuty connector for incident and ownership data.
    
    Uses PagerDuty REST API to fetch:
    - Current on-call users
    - Past incidents
    - Service ownership
    - Escalation policies
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = "https://api.pagerduty.com"
    
    @property
    def name(self) -> str:
        return "pagerduty"
    
    async def connect(self) -> bool:
        """Connect to PagerDuty API."""
        try:
            token = self.config.get("token")
            if not token:
                self._last_error = "PagerDuty token not configured"
                return False
            
            headers = {
                "Authorization": f"Token token={token}",
                "Content-Type": "application/json",
            }
            
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
            
            # Test connection
            response = await self._client.get(f"{self._base_url}/abilities")
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                self._last_error = f"PagerDuty returned status {response.status_code}"
                return False
                
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from PagerDuty."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
    
    async def health_check(self) -> bool:
        """Check if PagerDuty API is accessible."""
        if not self._connected or not self._client:
            return False
        
        try:
            response = await self._client.get(f"{self._base_url}/abilities")
            return response.status_code == 200
        except Exception:
            return False
    
    async def sync(self, context_store: Any) -> int:
        """Sync PagerDuty data to context store."""
        if not self._connected:
            raise RuntimeError("Not connected to PagerDuty")
        
        count = 0
        
        # Sync service ownership
        services = await self.get_services()
        for service_id, ownership in services.items():
            context_store.set_ownership(ownership)
            count += 1
        
        # Sync recent incidents
        incidents = await self.get_recent_incidents()
        for incident in incidents:
            context_store.create_incident(incident)
            count += 1
        
        return count
    
    async def get_services(self) -> dict[str, Ownership]:
        """Get all PagerDuty services and their ownership."""
        if not self._client:
            return {}
        
        services = {}
        try:
            url = f"{self._base_url}/services"
            params = {"limit": 100}
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                self._last_error = f"Failed to get services: {response.status_code}"
                return {}
            
            for svc in response.json().get("services", []):
                # Get team info
                teams = svc.get("teams", [])
                team_name = teams[0].get("summary", "unknown") if teams else "unknown"
                
                ownership = Ownership(
                    service_name=svc.get("name", svc["id"]),
                    team=team_name,
                    pagerduty_service_id=svc["id"],
                )
                services[svc["id"]] = ownership
                
        except Exception as e:
            self._last_error = f"Error getting services: {e}"
        
        return services
    
    async def get_oncall(self, schedule_id: Optional[str] = None) -> list[dict]:
        """
        Get current on-call users.
        
        Args:
            schedule_id: Specific schedule to query, or all if None
        """
        if not self._client:
            return []
        
        oncall_users = []
        try:
            url = f"{self._base_url}/oncalls"
            params = {"limit": 100}
            if schedule_id:
                params["schedule_ids[]"] = schedule_id
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                return []
            
            for oncall in response.json().get("oncalls", []):
                user = oncall.get("user", {})
                schedule = oncall.get("schedule", {})
                escalation = oncall.get("escalation_policy", {})
                
                oncall_users.append({
                    "user_id": user.get("id"),
                    "user_name": user.get("summary"),
                    "user_email": user.get("email"),
                    "schedule_id": schedule.get("id"),
                    "schedule_name": schedule.get("summary"),
                    "escalation_policy": escalation.get("summary"),
                    "escalation_level": oncall.get("escalation_level"),
                    "start": oncall.get("start"),
                    "end": oncall.get("end"),
                })
                
        except Exception as e:
            self._last_error = f"Error getting on-call: {e}"
        
        return oncall_users
    
    async def get_recent_incidents(
        self,
        since_hours: int = 168,  # 7 days
        status: Optional[str] = None
    ) -> list[Incident]:
        """
        Get recent incidents.
        
        Args:
            since_hours: Get incidents from last N hours
            status: Filter by status (triggered, acknowledged, resolved)
        """
        if not self._client:
            return []
        
        incidents = []
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat() + "Z"
        
        try:
            url = f"{self._base_url}/incidents"
            params = {
                "since": since,
                "limit": 100,
                "sort_by": "created_at:desc",
            }
            if status:
                params["statuses[]"] = status
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                return []
            
            for inc in response.json().get("incidents", []):
                # Map PagerDuty urgency to severity
                urgency = inc.get("urgency", "low")
                severity_map = {
                    "high": Severity.HIGH,
                    "low": Severity.LOW,
                }
                severity = severity_map.get(urgency, Severity.MEDIUM)
                
                # Get service name
                service = inc.get("service", {})
                service_name = service.get("summary", "unknown")
                
                # Get assignee
                assignments = inc.get("assignments", [])
                assigned_to = assignments[0].get("assignee", {}).get("summary") if assignments else None
                
                # Get team
                teams = inc.get("teams", [])
                team = teams[0].get("summary") if teams else None
                
                incident = Incident(
                    id=f"pd-{inc['id']}",
                    title=inc.get("title", inc.get("summary", "")),
                    severity=severity,
                    services=[service_name] if service_name else [],
                    started_at=datetime.fromisoformat(inc["created_at"].replace("Z", "+00:00")),
                    acknowledged_at=datetime.fromisoformat(inc["last_status_change_at"].replace("Z", "+00:00")) if inc.get("status") in ["acknowledged", "resolved"] else None,
                    resolved_at=datetime.fromisoformat(inc["last_status_change_at"].replace("Z", "+00:00")) if inc.get("status") == "resolved" else None,
                    assigned_to=assigned_to,
                    team=team,
                )
                incidents.append(incident)
                
        except Exception as e:
            self._last_error = f"Error getting incidents: {e}"
        
        return incidents
    
    async def get_escalation_policy(self, policy_id: str) -> Optional[dict]:
        """Get details of an escalation policy."""
        if not self._client:
            return None
        
        try:
            url = f"{self._base_url}/escalation_policies/{policy_id}"
            response = await self._client.get(url)
            
            if response.status_code != 200:
                return None
            
            return response.json().get("escalation_policy")
            
        except Exception as e:
            self._last_error = f"Error getting escalation policy: {e}"
            return None
    
    async def trigger_incident(
        self,
        service_id: str,
        title: str,
        details: Optional[str] = None,
        urgency: str = "high"
    ) -> Optional[str]:
        """
        Trigger a new incident (for testing/escalation).
        
        Args:
            service_id: PagerDuty service ID
            title: Incident title
            details: Incident details
            urgency: high or low
            
        Returns:
            Incident ID if created, None otherwise
        """
        if not self._client:
            return None
        
        try:
            url = f"{self._base_url}/incidents"
            payload = {
                "incident": {
                    "type": "incident",
                    "title": title,
                    "service": {
                        "id": service_id,
                        "type": "service_reference"
                    },
                    "urgency": urgency,
                    "body": {
                        "type": "incident_body",
                        "details": details or title
                    }
                }
            }
            
            # Need From header for creating incidents
            from_email = self.config.get("from_email")
            if not from_email:
                self._last_error = "from_email required for creating incidents"
                return None
            
            response = await self._client.post(
                url,
                json=payload,
                headers={"From": from_email}
            )
            
            if response.status_code in [200, 201]:
                return response.json().get("incident", {}).get("id")
            else:
                self._last_error = f"Failed to create incident: {response.text}"
                return None
                
        except Exception as e:
            self._last_error = f"Error creating incident: {e}"
            return None
