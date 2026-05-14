"""
PagerDuty integration for AutoSRE V2.

Provides async PagerDuty client with support for:
- Incident management (list, get, acknowledge, resolve)
- Incident creation and notes
- User and service management
- Webhook parsing and signature validation
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, field_validator

from autosre.core.alert import Alert, AlertSeverity, AlertStatus
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================


class IncidentStatus(str, Enum):
    """PagerDuty incident status."""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentUrgency(str, Enum):
    """PagerDuty incident urgency."""

    HIGH = "high"
    LOW = "low"


class IncidentPriority(BaseModel):
    """Incident priority from PagerDuty."""

    id: str
    name: str
    description: str | None = None
    order: int | None = None
    color: str | None = None


class User(BaseModel):
    """PagerDuty user."""

    id: str
    type: str = "user_reference"
    summary: str | None = None
    name: str | None = None
    email: str | None = None
    html_url: str | None = None

    @property
    def display_name(self) -> str:
        """Get display name."""
        return self.name or self.summary or self.email or self.id


class Service(BaseModel):
    """PagerDuty service."""

    id: str
    type: str = "service_reference"
    summary: str | None = None
    name: str | None = None
    description: str | None = None
    html_url: str | None = None
    status: str | None = None

    @property
    def display_name(self) -> str:
        """Get display name."""
        return self.name or self.summary or self.id


class EscalationPolicy(BaseModel):
    """PagerDuty escalation policy."""

    id: str
    type: str = "escalation_policy_reference"
    summary: str | None = None
    name: str | None = None
    html_url: str | None = None


class Assignment(BaseModel):
    """Incident assignment."""

    at: datetime
    assignee: User

    @field_validator("at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)


class Acknowledgement(BaseModel):
    """Incident acknowledgement."""

    at: datetime
    acknowledger: User

    @field_validator("at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)


class Note(BaseModel):
    """Incident note/comment."""

    id: str
    user: User
    content: str
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)


class Incident(BaseModel):
    """PagerDuty incident."""

    id: str
    type: str = "incident"
    summary: str | None = None
    incident_number: int | None = None
    title: str
    description: str | None = None
    status: IncidentStatus = IncidentStatus.TRIGGERED
    urgency: IncidentUrgency = IncidentUrgency.HIGH
    priority: IncidentPriority | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime | None = None
    last_status_change_at: datetime | None = None

    # References
    service: Service | None = None
    escalation_policy: EscalationPolicy | None = None
    assignments: list[Assignment] = Field(default_factory=list)
    acknowledgements: list[Acknowledgement] = Field(default_factory=list)

    # URLs
    html_url: str | None = None
    self_url: str | None = Field(None, alias="self")

    # Additional data
    incident_key: str | None = None
    resolve_reason: str | None = None

    @field_validator("created_at", "updated_at", "last_status_change_at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return None

    @property
    def duration_seconds(self) -> float | None:
        """Get incident duration in seconds."""
        if self.last_status_change_at and self.status == IncidentStatus.RESOLVED:
            return (self.last_status_change_at - self.created_at).total_seconds()
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    @property
    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status in (IncidentStatus.TRIGGERED, IncidentStatus.ACKNOWLEDGED)

    @property
    def current_assignees(self) -> list[User]:
        """Get current assignees."""
        return [a.assignee for a in self.assignments]

    def to_alert(self) -> Alert:
        """Convert to AutoSRE Alert format."""
        from autosre.core.alert import AlertSource

        severity_map = {
            IncidentUrgency.HIGH: AlertSeverity.HIGH,
            IncidentUrgency.LOW: AlertSeverity.LOW,
        }

        status_map = {
            IncidentStatus.TRIGGERED: AlertStatus.FIRING,
            IncidentStatus.ACKNOWLEDGED: AlertStatus.ACKNOWLEDGED,
            IncidentStatus.RESOLVED: AlertStatus.RESOLVED,
        }

        return Alert(
            id=self.id,
            name=self.title,
            description=self.description or "",
            severity=severity_map.get(self.urgency, AlertSeverity.MEDIUM),
            status=status_map.get(self.status, AlertStatus.FIRING),
            source=AlertSource.PAGERDUTY,
            service=self.service.display_name if self.service else None,
            started_at=self.created_at,
            ended_at=self.last_status_change_at if self.status == IncidentStatus.RESOLVED else None,
            labels={
                "incident_number": str(self.incident_number) if self.incident_number else "",
                "urgency": self.urgency.value,
            },
            raw_data=self.model_dump(mode="json"),
        )


class PagerDutyEvent(BaseModel):
    """Parsed PagerDuty webhook event."""

    event_type: str
    resource_type: str
    incident: Incident | None = None
    log_entries: list[dict[str, Any]] = Field(default_factory=list)
    webhook_id: str | None = None
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_incident_event(self) -> bool:
        """Check if this is an incident-related event."""
        return self.resource_type == "incident"

    @property
    def action(self) -> str:
        """Get the action from the event type."""
        # e.g., "incident.triggered" -> "triggered"
        parts = self.event_type.split(".")
        return parts[-1] if len(parts) > 1 else self.event_type


# ============================================================================
# Rate Limiter
# ============================================================================


class RateLimiter:
    """Token bucket rate limiter for PagerDuty API."""

    def __init__(
        self,
        requests_per_minute: int = 900,  # PagerDuty limit is 900/min
        burst_size: int = 30,
    ):
        self.rate = requests_per_minute / 60.0
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request can be made."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug("PagerDuty rate limited", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


# ============================================================================
# PagerDuty Client
# ============================================================================


class PagerDutyError(Exception):
    """Base PagerDuty API error."""

    def __init__(self, message: str, status_code: int | None = None, error_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class PagerDutyRateLimitError(PagerDutyError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(f"Rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class PagerDutyNotFoundError(PagerDutyError):
    """Resource not found."""

    pass


class PagerDutyClient:
    """
    Async PagerDuty client for incident management.

    Provides methods for managing incidents, notes, and integrating
    with PagerDuty webhooks.
    """

    API_BASE = "https://api.pagerduty.com"

    def __init__(
        self,
        api_key: str,
        webhook_secret: str | None = None,
        default_from_email: str | None = None,
        requests_per_minute: int = 900,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize PagerDuty client.

        Args:
            api_key: PagerDuty API key (REST API key)
            webhook_secret: Webhook signing secret for validation
            default_from_email: Default email for API calls requiring From header
            requests_per_minute: Rate limit for API calls
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.default_from_email = default_from_email
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)

    async def __aenter__(self) -> PagerDutyClient:
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE,
                headers={
                    "Authorization": f"Token token={self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.pagerduty+json;version=2",
                },
                timeout=30.0,
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
        endpoint: str,
        from_email: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an API request with retries and rate limiting.

        Args:
            method: HTTP method
            endpoint: API endpoint
            from_email: Email for From header (required for some endpoints)
            **kwargs: Additional request arguments

        Returns:
            API response data

        Raises:
            PagerDutyError: If the request fails after retries
        """
        client = await self._ensure_client()
        last_error: Exception | None = None

        # Add From header if provided
        headers = kwargs.pop("headers", {})
        if from_email or self.default_from_email:
            headers["From"] = from_email or self.default_from_email

        for attempt in range(self.max_retries):
            await self._rate_limiter.acquire()

            try:
                response = await client.request(
                    method,
                    endpoint,
                    headers=headers if headers else None,
                    **kwargs,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 30))
                    logger.warning(
                        "PagerDuty rate limit hit",
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                # Handle not found
                if response.status_code == 404:
                    raise PagerDutyNotFoundError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                    )

                response.raise_for_status()

                # Handle empty responses (e.g., 204 No Content)
                if response.status_code == 204:
                    return {}

                return response.json()

            except PagerDutyNotFoundError:
                raise
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "PagerDuty request failed",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )

                # Try to parse error details
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                    error_code = error_data.get("error", {}).get("code")
                    raise PagerDutyError(error_msg, e.response.status_code, error_code)
                except (ValueError, KeyError):
                    pass

            except PagerDutyError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "PagerDuty request error",
                    error=str(e),
                    attempt=attempt + 1,
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2**attempt)
                await asyncio.sleep(delay)

        raise PagerDutyError(f"Request failed after {self.max_retries} attempts: {last_error}")

    # ========================================================================
    # Incident Management
    # ========================================================================

    async def list_incidents(
        self,
        status: str | list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        service_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        urgencies: list[str] | None = None,
        time_zone: str = "UTC",
        sort_by: str = "created_at:desc",
        limit: int = 25,
        offset: int = 0,
    ) -> list[Incident]:
        """
        List incidents with filtering options.

        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            since: Return incidents created after this time
            until: Return incidents created before this time
            service_ids: Filter by service IDs
            user_ids: Filter by assigned user IDs
            urgencies: Filter by urgencies (high, low)
            time_zone: Time zone for date parameters
            sort_by: Sort field and direction
            limit: Maximum results per request
            offset: Pagination offset

        Returns:
            List of incidents
        """
        params: dict[str, Any] = {
            "time_zone": time_zone,
            "sort_by": sort_by,
            "limit": limit,
            "offset": offset,
        }

        if status:
            if isinstance(status, list):
                params["statuses[]"] = status
            else:
                params["statuses[]"] = [status]

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if service_ids:
            params["service_ids[]"] = service_ids
        if user_ids:
            params["user_ids[]"] = user_ids
        if urgencies:
            params["urgencies[]"] = urgencies

        response = await self._request("GET", "/incidents", params=params)

        incidents = []
        for inc_data in response.get("incidents", []):
            try:
                incidents.append(Incident(**inc_data))
            except Exception as e:
                logger.warning("Failed to parse incident", error=str(e))

        logger.debug("Listed incidents", count=len(incidents))
        return incidents

    async def get_incident(self, incident_id: str) -> Incident:
        """
        Get a single incident by ID.

        Args:
            incident_id: Incident ID

        Returns:
            Incident details
        """
        response = await self._request("GET", f"/incidents/{incident_id}")
        return Incident(**response["incident"])

    async def create_incident(
        self,
        title: str,
        service_id: str,
        body: str | None = None,
        urgency: IncidentUrgency = IncidentUrgency.HIGH,
        incident_key: str | None = None,
        escalation_policy_id: str | None = None,
        priority_id: str | None = None,
        from_email: str | None = None,
    ) -> Incident:
        """
        Create a new incident.

        Args:
            title: Incident title
            service_id: Service ID to create incident on
            body: Incident body/details
            urgency: Incident urgency
            incident_key: Deduplication key
            escalation_policy_id: Override escalation policy
            priority_id: Incident priority ID
            from_email: Email of user creating incident

        Returns:
            Created incident
        """
        incident_data: dict[str, Any] = {
            "type": "incident",
            "title": title,
            "service": {
                "id": service_id,
                "type": "service_reference",
            },
            "urgency": urgency.value,
        }

        if body:
            incident_data["body"] = {"type": "incident_body", "details": body}
        if incident_key:
            incident_data["incident_key"] = incident_key
        if escalation_policy_id:
            incident_data["escalation_policy"] = {
                "id": escalation_policy_id,
                "type": "escalation_policy_reference",
            }
        if priority_id:
            incident_data["priority"] = {
                "id": priority_id,
                "type": "priority_reference",
            }

        response = await self._request(
            "POST",
            "/incidents",
            json={"incident": incident_data},
            from_email=from_email,
        )

        incident = Incident(**response["incident"])
        logger.info("Created incident", incident_id=incident.id, title=title)
        return incident

    async def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus | None = None,
        title: str | None = None,
        urgency: IncidentUrgency | None = None,
        escalation_level: int | None = None,
        escalation_policy_id: str | None = None,
        priority_id: str | None = None,
        resolution: str | None = None,
        from_email: str | None = None,
    ) -> Incident:
        """
        Update an incident.

        Args:
            incident_id: Incident ID to update
            status: New status
            title: New title
            urgency: New urgency
            escalation_level: Escalation level
            escalation_policy_id: New escalation policy
            priority_id: New priority
            resolution: Resolution notes (when resolving)
            from_email: Email of user making changes

        Returns:
            Updated incident
        """
        incident_data: dict[str, Any] = {
            "id": incident_id,
            "type": "incident",
        }

        if status:
            incident_data["status"] = status.value
        if title:
            incident_data["title"] = title
        if urgency:
            incident_data["urgency"] = urgency.value
        if escalation_level is not None:
            incident_data["escalation_level"] = escalation_level
        if escalation_policy_id:
            incident_data["escalation_policy"] = {
                "id": escalation_policy_id,
                "type": "escalation_policy_reference",
            }
        if priority_id:
            incident_data["priority"] = {
                "id": priority_id,
                "type": "priority_reference",
            }
        if resolution:
            incident_data["resolution"] = resolution

        response = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            json={"incident": incident_data},
            from_email=from_email,
        )

        incident = Incident(**response["incident"])
        logger.info("Updated incident", incident_id=incident_id)
        return incident

    async def acknowledge_incident(
        self,
        incident_id: str,
        from_email: str | None = None,
    ) -> Incident:
        """
        Acknowledge an incident.

        Args:
            incident_id: Incident ID
            from_email: Email of acknowledging user

        Returns:
            Updated incident
        """
        return await self.update_incident(
            incident_id,
            status=IncidentStatus.ACKNOWLEDGED,
            from_email=from_email,
        )

    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str | None = None,
        from_email: str | None = None,
    ) -> Incident:
        """
        Resolve an incident.

        Args:
            incident_id: Incident ID
            resolution: Resolution notes
            from_email: Email of resolving user

        Returns:
            Updated incident
        """
        return await self.update_incident(
            incident_id,
            status=IncidentStatus.RESOLVED,
            resolution=resolution,
            from_email=from_email,
        )

    async def reassign_incident(
        self,
        incident_id: str,
        user_ids: list[str],
        from_email: str | None = None,
    ) -> Incident:
        """
        Reassign an incident to different users.

        Args:
            incident_id: Incident ID
            user_ids: List of user IDs to assign
            from_email: Email of user making reassignment

        Returns:
            Updated incident
        """
        assignments = [
            {"assignee": {"id": uid, "type": "user_reference"}} for uid in user_ids
        ]

        response = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            json={
                "incident": {
                    "id": incident_id,
                    "type": "incident",
                    "assignments": assignments,
                }
            },
            from_email=from_email,
        )

        incident = Incident(**response["incident"])
        logger.info("Reassigned incident", incident_id=incident_id, users=user_ids)
        return incident

    async def merge_incidents(
        self,
        source_incident_ids: list[str],
        target_incident_id: str,
        from_email: str | None = None,
    ) -> Incident:
        """
        Merge multiple incidents into one.

        Args:
            source_incident_ids: Incidents to merge
            target_incident_id: Incident to merge into
            from_email: Email of user performing merge

        Returns:
            Target incident after merge
        """
        source_incidents = [
            {"id": sid, "type": "incident_reference"} for sid in source_incident_ids
        ]

        response = await self._request(
            "PUT",
            f"/incidents/{target_incident_id}/merge",
            json={"source_incidents": source_incidents},
            from_email=from_email,
        )

        incident = Incident(**response["incident"])
        logger.info(
            "Merged incidents",
            target=target_incident_id,
            sources=source_incident_ids,
        )
        return incident

    # ========================================================================
    # Incident Notes
    # ========================================================================

    async def add_note(
        self,
        incident_id: str,
        note: str,
        from_email: str | None = None,
    ) -> Note:
        """
        Add a note to an incident.

        Args:
            incident_id: Incident ID
            note: Note content
            from_email: Email of user adding note

        Returns:
            Created note
        """
        response = await self._request(
            "POST",
            f"/incidents/{incident_id}/notes",
            json={"note": {"content": note}},
            from_email=from_email,
        )

        note_data = response["note"]
        created_note = Note(
            id=note_data["id"],
            user=User(**note_data.get("user", {"id": "unknown", "type": "user_reference"})),
            content=note_data["content"],
            created_at=note_data.get("created_at", datetime.now(timezone.utc)),
        )

        logger.info("Added note", incident_id=incident_id)
        return created_note

    async def list_notes(self, incident_id: str) -> list[Note]:
        """
        List notes on an incident.

        Args:
            incident_id: Incident ID

        Returns:
            List of notes
        """
        response = await self._request("GET", f"/incidents/{incident_id}/notes")

        notes = []
        for note_data in response.get("notes", []):
            try:
                notes.append(
                    Note(
                        id=note_data["id"],
                        user=User(**note_data.get("user", {"id": "unknown", "type": "user_reference"})),
                        content=note_data["content"],
                        created_at=note_data.get("created_at", datetime.now(timezone.utc)),
                    )
                )
            except Exception as e:
                logger.warning("Failed to parse note", error=str(e))

        return notes

    # ========================================================================
    # Services
    # ========================================================================

    async def list_services(
        self,
        query: str | None = None,
        include: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Service]:
        """
        List services.

        Args:
            query: Search query
            include: Additional fields to include
            limit: Max results
            offset: Pagination offset

        Returns:
            List of services
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if include:
            params["include[]"] = include

        response = await self._request("GET", "/services", params=params)

        services = []
        for svc_data in response.get("services", []):
            try:
                services.append(Service(**svc_data))
            except Exception as e:
                logger.warning("Failed to parse service", error=str(e))

        return services

    async def get_service(self, service_id: str) -> Service:
        """Get a service by ID."""
        response = await self._request("GET", f"/services/{service_id}")
        return Service(**response["service"])

    # ========================================================================
    # Users
    # ========================================================================

    async def list_users(
        self,
        query: str | None = None,
        include: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[User]:
        """
        List users.

        Args:
            query: Search query
            include: Additional fields to include
            limit: Max results
            offset: Pagination offset

        Returns:
            List of users
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if include:
            params["include[]"] = include

        response = await self._request("GET", "/users", params=params)

        users = []
        for user_data in response.get("users", []):
            try:
                users.append(User(**user_data))
            except Exception as e:
                logger.warning("Failed to parse user", error=str(e))

        return users

    async def get_user(self, user_id: str) -> User:
        """Get a user by ID."""
        response = await self._request("GET", f"/users/{user_id}")
        return User(**response["user"])

    async def get_current_user(self) -> User:
        """Get the current authenticated user."""
        response = await self._request("GET", "/users/me")
        return User(**response["user"])

    # ========================================================================
    # Escalation Policies
    # ========================================================================

    async def list_escalation_policies(
        self,
        query: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[EscalationPolicy]:
        """List escalation policies."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query

        response = await self._request("GET", "/escalation_policies", params=params)

        policies = []
        for policy_data in response.get("escalation_policies", []):
            try:
                policies.append(EscalationPolicy(**policy_data))
            except Exception as e:
                logger.warning("Failed to parse escalation policy", error=str(e))

        return policies

    # ========================================================================
    # Priorities
    # ========================================================================

    async def list_priorities(self) -> list[IncidentPriority]:
        """List available priorities."""
        response = await self._request("GET", "/priorities")

        priorities = []
        for priority_data in response.get("priorities", []):
            try:
                priorities.append(IncidentPriority(**priority_data))
            except Exception as e:
                logger.warning("Failed to parse priority", error=str(e))

        return priorities

    # ========================================================================
    # Webhook Handling
    # ========================================================================

    def verify_webhook_signature(
        self,
        body: bytes,
        signatures: list[str],
    ) -> bool:
        """
        Verify PagerDuty webhook signature (v3 webhooks).

        Args:
            body: Raw request body
            signatures: X-PagerDuty-Signature header values

        Returns:
            True if any signature is valid
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True

        for signature in signatures:
            # Parse signature header (format: "v1=<signature>")
            parts = signature.split("=", 1)
            if len(parts) != 2:
                continue

            version, sig = parts
            if version != "v1":
                continue

            # Compute expected signature
            expected_sig = hmac.new(
                self.webhook_secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(expected_sig, sig):
                return True

        logger.warning("Webhook signature verification failed")
        return False

    def parse_webhook(self, payload: dict[str, Any]) -> PagerDutyEvent:
        """
        Parse a PagerDuty webhook payload (v3 format).

        Args:
            payload: Raw webhook JSON payload

        Returns:
            Parsed event
        """
        event = payload.get("event", {})
        event_type = event.get("event_type", "unknown")
        resource_type = event.get("resource_type", "unknown")

        # Parse incident if present
        incident_data = event.get("data")
        incident = None
        if incident_data and resource_type == "incident":
            try:
                incident = Incident(**incident_data)
            except Exception as e:
                logger.warning("Failed to parse webhook incident", error=str(e))

        occurred_at = None
        if "occurred_at" in event:
            try:
                occurred_at = datetime.fromisoformat(
                    event["occurred_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return PagerDutyEvent(
            event_type=event_type,
            resource_type=resource_type,
            incident=incident,
            webhook_id=payload.get("id"),
            occurred_at=occurred_at,
            raw_payload=payload,
        )

    # ========================================================================
    # Utilities
    # ========================================================================

    async def check_connection(self) -> bool:
        """Check if PagerDuty connection is working."""
        try:
            await self.get_current_user()
            return True
        except Exception as e:
            logger.warning("PagerDuty connection check failed", error=str(e))
            return False

    async def send_event(
        self,
        routing_key: str,
        event_action: Literal["trigger", "acknowledge", "resolve"],
        dedup_key: str | None = None,
        summary: str | None = None,
        source: str | None = None,
        severity: Literal["critical", "error", "warning", "info"] = "error",
        custom_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send an event to PagerDuty Events API v2.

        This is for sending events directly (not managing incidents via REST API).

        Args:
            routing_key: Integration key (Events API v2)
            event_action: Event action
            dedup_key: Deduplication key
            summary: Event summary (required for trigger)
            source: Event source
            severity: Event severity
            custom_details: Additional event details

        Returns:
            API response
        """
        payload: dict[str, Any] = {
            "routing_key": routing_key,
            "event_action": event_action,
        }

        if dedup_key:
            payload["dedup_key"] = dedup_key

        if event_action == "trigger":
            if not summary:
                raise ValueError("Summary required for trigger events")
            payload["payload"] = {
                "summary": summary,
                "source": source or "autosre",
                "severity": severity,
            }
            if custom_details:
                payload["payload"]["custom_details"] = custom_details

        # Events API has a different base URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
