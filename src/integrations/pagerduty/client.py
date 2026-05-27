"""PagerDuty API client for AutoSRE.

Provides async methods for interacting with the PagerDuty REST API v2.
See: https://developer.pagerduty.com/api-reference/
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import (
    Alert,
    Escalation,
    Incident,
    IncidentStatus,
    LogEntry,
    Note,
    OnCall,
    Service,
    User,
)

logger = logging.getLogger(__name__)


class PagerDutyError(Exception):
    """Base exception for PagerDuty API errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PagerDutyAuthError(PagerDutyError):
    """Authentication/authorization error."""
    pass


class PagerDutyNotFoundError(PagerDutyError):
    """Resource not found error."""
    pass


class PagerDutyRateLimitError(PagerDutyError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class PagerDutyClient:
    """Async client for PagerDuty REST API v2.
    
    Usage:
        async with PagerDutyClient(api_key="your-api-key") as client:
            incidents = await client.list_incidents(status="triggered")
            for incident in incidents:
                print(f"{incident.incident_number}: {incident.title}")
    """
    
    DEFAULT_BASE_URL = "https://api.pagerduty.com"
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        requester_email: str | None = None,
    ):
        """Initialize PagerDuty client.
        
        Args:
            api_key: PagerDuty API key (REST API v2)
            base_url: API base URL (default: https://api.pagerduty.com)
            timeout: Request timeout in seconds
            requester_email: Email for From header (required for write operations)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.requester_email = requester_email
        self._client: httpx.AsyncClient | None = None
    
    @property
    def _headers(self) -> dict[str, str]:
        """Get default headers for API requests."""
        headers = {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }
        if self.requester_email:
            headers["From"] = self.requester_email
        return headers
    
    async def __aenter__(self) -> "PagerDutyClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self.timeout,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> dict[str, Any]:
        """Make an API request with error handling and retries.
        
        Args:
            method: HTTP method
            path: API path (e.g., /incidents)
            params: Query parameters
            json_data: JSON body data
            retry: Whether to retry on transient failures
            
        Returns:
            API response as dict
            
        Raises:
            PagerDutyError: On API errors
        """
        client = self._get_client()
        url = path if path.startswith("/") else f"/{path}"
        
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES if retry else 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.MAX_RETRIES - 1 and retry:
                        logger.warning(f"Rate limited, retrying in {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    raise PagerDutyRateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after,
                    )
                
                # Handle auth errors
                if response.status_code in (401, 403):
                    raise PagerDutyAuthError(
                        f"Authentication failed: {response.text}",
                        status_code=response.status_code,
                    )
                
                # Handle not found
                if response.status_code == 404:
                    raise PagerDutyNotFoundError(
                        f"Resource not found: {url}",
                        status_code=404,
                    )
                
                # Handle other errors
                if response.status_code >= 400:
                    error_body = response.json() if response.text else {}
                    raise PagerDutyError(
                        f"API error: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                        response=error_body,
                    )
                
                # Return successful response
                return response.json() if response.text else {}
                
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1 and retry:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise PagerDutyError(f"Request timeout: {e}")
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1 and retry:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise PagerDutyError(f"Request failed: {e}")
        
        raise PagerDutyError(f"Max retries exceeded: {last_error}")
    
    # -------------------------------------------------------------------------
    # Incidents API
    # -------------------------------------------------------------------------
    
    async def get_incident(self, incident_id: str, include: list[str] | None = None) -> Incident:
        """Get a single incident by ID.
        
        Args:
            incident_id: PagerDuty incident ID
            include: Additional data to include (e.g., ["acknowledgers", "assignees", "alerts"])
            
        Returns:
            Incident object
        """
        params = {}
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", f"/incidents/{incident_id}", params=params)
        return Incident.model_validate(data["incident"])
    
    async def list_incidents(
        self,
        status: str | list[str] | None = None,
        service_ids: list[str] | None = None,
        team_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        urgency: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        sort_by: str = "created_at",
        limit: int = 25,
        offset: int = 0,
        include: list[str] | None = None,
    ) -> list[Incident]:
        """List incidents with optional filters.
        
        Args:
            status: Filter by status(es) - triggered, acknowledged, resolved
            service_ids: Filter by service IDs
            team_ids: Filter by team IDs
            user_ids: Filter by assigned user IDs
            urgency: Filter by urgency - high, low
            since: Filter by created_at >= since
            until: Filter by created_at <= until
            sort_by: Sort field (created_at, resolved_at, incident_number)
            limit: Max results per page (max 100)
            offset: Pagination offset
            include: Additional data to include
            
        Returns:
            List of Incident objects
        """
        params: dict[str, Any] = {
            "sort_by": sort_by,
            "limit": min(limit, 100),
            "offset": offset,
        }
        
        if status:
            if isinstance(status, str):
                params["statuses[]"] = [status]
            else:
                params["statuses[]"] = status
        if service_ids:
            params["service_ids[]"] = service_ids
        if team_ids:
            params["team_ids[]"] = team_ids
        if user_ids:
            params["user_ids[]"] = user_ids
        if urgency:
            params["urgencies[]"] = [urgency]
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", "/incidents", params=params)
        return [Incident.model_validate(i) for i in data.get("incidents", [])]
    
    async def list_all_incidents(
        self,
        status: str | list[str] | None = None,
        service_ids: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        max_results: int = 1000,
        **kwargs,
    ) -> list[Incident]:
        """List all incidents with pagination.
        
        Automatically handles pagination to retrieve all matching incidents.
        
        Args:
            status: Filter by status(es)
            service_ids: Filter by service IDs
            since: Filter by created_at >= since
            until: Filter by created_at <= until
            max_results: Maximum total results to return
            **kwargs: Additional filters passed to list_incidents
            
        Returns:
            List of all matching Incident objects
        """
        all_incidents: list[Incident] = []
        offset = 0
        limit = 100
        
        while len(all_incidents) < max_results:
            incidents = await self.list_incidents(
                status=status,
                service_ids=service_ids,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
                **kwargs,
            )
            
            if not incidents:
                break
                
            all_incidents.extend(incidents)
            offset += len(incidents)
            
            if len(incidents) < limit:
                break
        
        return all_incidents[:max_results]
    
    async def add_note(self, incident_id: str, note: str) -> Note:
        """Add a note to an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            note: Note content
            
        Returns:
            Created Note object
            
        Note:
            Requires requester_email to be set for From header.
        """
        if not self.requester_email:
            raise PagerDutyError("requester_email required for write operations")
        
        data = await self._request(
            "POST",
            f"/incidents/{incident_id}/notes",
            json_data={"note": {"content": note}},
        )
        return Note.model_validate(data["note"])
    
    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str | None = None,
    ) -> Incident:
        """Resolve an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            resolution: Optional resolution note
            
        Returns:
            Updated Incident object
        """
        if not self.requester_email:
            raise PagerDutyError("requester_email required for write operations")
        
        incident_data: dict[str, Any] = {
            "id": incident_id,
            "type": "incident_reference",
            "status": "resolved",
        }
        
        if resolution:
            incident_data["resolution"] = resolution
        
        data = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            json_data={"incident": incident_data},
        )
        return Incident.model_validate(data["incident"])
    
    async def acknowledge_incident(self, incident_id: str) -> Incident:
        """Acknowledge an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            
        Returns:
            Updated Incident object
        """
        if not self.requester_email:
            raise PagerDutyError("requester_email required for write operations")
        
        data = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            json_data={
                "incident": {
                    "id": incident_id,
                    "type": "incident_reference",
                    "status": "acknowledged",
                }
            },
        )
        return Incident.model_validate(data["incident"])
    
    async def update_incident(
        self,
        incident_id: str,
        title: str | None = None,
        status: IncidentStatus | None = None,
        urgency: str | None = None,
        escalation_level: int | None = None,
        assignments: list[dict[str, str]] | None = None,
        resolution: str | None = None,
    ) -> Incident:
        """Update an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            title: New title
            status: New status
            urgency: New urgency (high/low)
            escalation_level: New escalation level
            assignments: New assignments [{"assignee": {"id": "user_id", "type": "user_reference"}}]
            resolution: Resolution note (for resolved status)
            
        Returns:
            Updated Incident object
        """
        if not self.requester_email:
            raise PagerDutyError("requester_email required for write operations")
        
        incident_data: dict[str, Any] = {
            "id": incident_id,
            "type": "incident_reference",
        }
        
        if title:
            incident_data["title"] = title
        if status:
            incident_data["status"] = status.value if isinstance(status, IncidentStatus) else status
        if urgency:
            incident_data["urgency"] = urgency
        if escalation_level:
            incident_data["escalation_level"] = escalation_level
        if assignments:
            incident_data["assignments"] = assignments
        if resolution:
            incident_data["resolution"] = resolution
        
        data = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            json_data={"incident": incident_data},
        )
        return Incident.model_validate(data["incident"])
    
    async def merge_incidents(
        self,
        target_incident_id: str,
        source_incident_ids: list[str],
    ) -> Incident:
        """Merge incidents into a target incident.
        
        Args:
            target_incident_id: Incident to merge others into
            source_incident_ids: Incidents to merge
            
        Returns:
            Merged Incident object
        """
        if not self.requester_email:
            raise PagerDutyError("requester_email required for write operations")
        
        source_incidents = [
            {"id": inc_id, "type": "incident_reference"}
            for inc_id in source_incident_ids
        ]
        
        data = await self._request(
            "PUT",
            f"/incidents/{target_incident_id}/merge",
            json_data={"source_incidents": source_incidents},
        )
        return Incident.model_validate(data["incident"])
    
    # -------------------------------------------------------------------------
    # Alerts API
    # -------------------------------------------------------------------------
    
    async def list_alerts(
        self,
        incident_id: str,
        status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Alert]:
        """List alerts for an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            status: Filter by status (triggered, resolved)
            limit: Max results per page
            offset: Pagination offset
            
        Returns:
            List of Alert objects
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
        }
        if status:
            params["statuses[]"] = [status]
        
        data = await self._request(
            "GET",
            f"/incidents/{incident_id}/alerts",
            params=params,
        )
        return [Alert.model_validate(a) for a in data.get("alerts", [])]
    
    async def get_alert(self, incident_id: str, alert_id: str) -> Alert:
        """Get a specific alert.
        
        Args:
            incident_id: PagerDuty incident ID
            alert_id: PagerDuty alert ID
            
        Returns:
            Alert object
        """
        data = await self._request(
            "GET",
            f"/incidents/{incident_id}/alerts/{alert_id}",
        )
        return Alert.model_validate(data["alert"])
    
    # -------------------------------------------------------------------------
    # Services API
    # -------------------------------------------------------------------------
    
    async def get_service(self, service_id: str, include: list[str] | None = None) -> Service:
        """Get a service by ID.
        
        Args:
            service_id: PagerDuty service ID
            include: Additional data to include (e.g., ["integrations", "escalation_policies"])
            
        Returns:
            Service object
        """
        params = {}
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", f"/services/{service_id}", params=params)
        return Service.model_validate(data["service"])
    
    async def list_services(
        self,
        team_ids: list[str] | None = None,
        query: str | None = None,
        limit: int = 25,
        offset: int = 0,
        include: list[str] | None = None,
    ) -> list[Service]:
        """List services.
        
        Args:
            team_ids: Filter by team IDs
            query: Search query
            limit: Max results per page
            offset: Pagination offset
            include: Additional data to include
            
        Returns:
            List of Service objects
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
        }
        if team_ids:
            params["team_ids[]"] = team_ids
        if query:
            params["query"] = query
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", "/services", params=params)
        return [Service.model_validate(s) for s in data.get("services", [])]
    
    # -------------------------------------------------------------------------
    # Escalation Policies API
    # -------------------------------------------------------------------------
    
    async def get_escalation_policy(
        self,
        policy_id: str,
        include: list[str] | None = None,
    ) -> Escalation:
        """Get an escalation policy by ID.
        
        Args:
            policy_id: PagerDuty escalation policy ID
            include: Additional data to include (e.g., ["services", "teams", "targets"])
            
        Returns:
            Escalation object
        """
        params = {}
        if include:
            params["include[]"] = include
        
        data = await self._request(
            "GET",
            f"/escalation_policies/{policy_id}",
            params=params,
        )
        return Escalation.model_validate(data["escalation_policy"])
    
    # -------------------------------------------------------------------------
    # Users API
    # -------------------------------------------------------------------------
    
    async def get_user(self, user_id: str, include: list[str] | None = None) -> User:
        """Get a user by ID.
        
        Args:
            user_id: PagerDuty user ID
            include: Additional data to include
            
        Returns:
            User object
        """
        params = {}
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", f"/users/{user_id}", params=params)
        return User.model_validate(data["user"])
    
    async def list_users(
        self,
        query: str | None = None,
        team_ids: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        include: list[str] | None = None,
    ) -> list[User]:
        """List users.
        
        Args:
            query: Search query
            team_ids: Filter by team IDs
            limit: Max results per page
            offset: Pagination offset
            include: Additional data to include
            
        Returns:
            List of User objects
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
        }
        if query:
            params["query"] = query
        if team_ids:
            params["team_ids[]"] = team_ids
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", "/users", params=params)
        return [User.model_validate(u) for u in data.get("users", [])]
    
    # -------------------------------------------------------------------------
    # On-Call API
    # -------------------------------------------------------------------------
    
    async def list_oncalls(
        self,
        schedule_ids: list[str] | None = None,
        escalation_policy_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        earliest: bool = False,
        limit: int = 25,
        offset: int = 0,
        include: list[str] | None = None,
    ) -> list[OnCall]:
        """List on-call entries.
        
        Args:
            schedule_ids: Filter by schedule IDs
            escalation_policy_ids: Filter by escalation policy IDs
            user_ids: Filter by user IDs
            since: Start of time range
            until: End of time range
            earliest: Only return earliest on-call per level
            limit: Max results per page
            offset: Pagination offset
            include: Additional data to include
            
        Returns:
            List of OnCall objects
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
            "earliest": earliest,
        }
        if schedule_ids:
            params["schedule_ids[]"] = schedule_ids
        if escalation_policy_ids:
            params["escalation_policy_ids[]"] = escalation_policy_ids
        if user_ids:
            params["user_ids[]"] = user_ids
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if include:
            params["include[]"] = include
        
        data = await self._request("GET", "/oncalls", params=params)
        return [OnCall.model_validate(o) for o in data.get("oncalls", [])]
    
    async def get_oncall_for_escalation_policy(
        self,
        escalation_policy_id: str,
        escalation_level: int = 1,
    ) -> list[OnCall]:
        """Get current on-call responders for an escalation policy.
        
        Args:
            escalation_policy_id: PagerDuty escalation policy ID
            escalation_level: Escalation level to query (default 1)
            
        Returns:
            List of OnCall objects for the specified level
        """
        now = datetime.now(timezone.utc)
        oncalls = await self.list_oncalls(
            escalation_policy_ids=[escalation_policy_id],
            since=now - timedelta(minutes=1),
            until=now + timedelta(minutes=1),
            earliest=True,
        )
        return [o for o in oncalls if o.escalation_level == escalation_level]
    
    # -------------------------------------------------------------------------
    # Log Entries API
    # -------------------------------------------------------------------------
    
    async def list_incident_log_entries(
        self,
        incident_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        is_overview: bool = False,
        limit: int = 25,
        offset: int = 0,
        include: list[str] | None = None,
    ) -> list[LogEntry]:
        """List log entries for an incident (timeline).
        
        Args:
            incident_id: PagerDuty incident ID
            since: Start of time range
            until: End of time range
            is_overview: Only return overview entries
            limit: Max results per page
            offset: Pagination offset
            include: Additional data to include
            
        Returns:
            List of LogEntry objects
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
            "is_overview": is_overview,
        }
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if include:
            params["include[]"] = include
        
        data = await self._request(
            "GET",
            f"/incidents/{incident_id}/log_entries",
            params=params,
        )
        return [LogEntry.model_validate(e) for e in data.get("log_entries", [])]
    
    async def get_incident_timeline(
        self,
        incident_id: str,
        max_entries: int = 100,
    ) -> list[LogEntry]:
        """Get full incident timeline.
        
        Args:
            incident_id: PagerDuty incident ID
            max_entries: Maximum entries to return
            
        Returns:
            List of LogEntry objects in chronological order
        """
        all_entries: list[LogEntry] = []
        offset = 0
        limit = 100
        
        while len(all_entries) < max_entries:
            entries = await self.list_incident_log_entries(
                incident_id=incident_id,
                limit=limit,
                offset=offset,
            )
            
            if not entries:
                break
            
            all_entries.extend(entries)
            offset += len(entries)
            
            if len(entries) < limit:
                break
        
        # Sort chronologically
        return sorted(all_entries[:max_entries], key=lambda e: e.created_at)
    
    # -------------------------------------------------------------------------
    # Notes API
    # -------------------------------------------------------------------------
    
    async def list_incident_notes(
        self,
        incident_id: str,
    ) -> list[Note]:
        """List notes for an incident.
        
        Args:
            incident_id: PagerDuty incident ID
            
        Returns:
            List of Note objects
        """
        data = await self._request("GET", f"/incidents/{incident_id}/notes")
        return [Note.model_validate(n) for n in data.get("notes", [])]
    
    # -------------------------------------------------------------------------
    # Related Incidents
    # -------------------------------------------------------------------------
    
    async def get_related_incidents(
        self,
        incident_id: str,
        service_id: str | None = None,
        lookback_hours: int = 24,
        max_results: int = 10,
    ) -> list[Incident]:
        """Get incidents related to a given incident.
        
        Finds incidents that:
        - Affect the same service
        - Occurred within the lookback window
        
        Args:
            incident_id: PagerDuty incident ID to find relations for
            service_id: Service ID (if not provided, fetched from incident)
            lookback_hours: Hours to look back
            max_results: Max related incidents to return
            
        Returns:
            List of related Incident objects (excluding the original)
        """
        # Get the original incident if service_id not provided
        if not service_id:
            original = await self.get_incident(incident_id)
            if original.service and isinstance(original.service, dict):
                service_id = original.service.get("id")
            elif original.service and hasattr(original.service, "id"):
                service_id = original.service.id
        
        if not service_id:
            return []
        
        # Get incidents for the same service
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        incidents = await self.list_incidents(
            service_ids=[service_id],
            since=since,
            limit=max_results + 1,  # +1 to account for excluding original
        )
        
        # Filter out the original incident
        return [i for i in incidents if i.id != incident_id][:max_results]
