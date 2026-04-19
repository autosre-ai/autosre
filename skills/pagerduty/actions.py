"""PagerDuty skill actions."""

import asyncio
import os
from datetime import datetime
from typing import Any, Optional

import aiohttp

from .models import (
    Incident,
    IncidentList,
    IncidentNote,
    OnCall,
    OnCallUser,
    PagerDutyError,
    Service,
)


class RateLimiter:
    """Rate limiter for PagerDuty API (960 req/min)."""

    def __init__(self, calls_per_minute: int = 960):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()


class PagerDutySkill:
    """PagerDuty integration skill."""

    BASE_URL = "https://api.pagerduty.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("PAGERDUTY_API_KEY")
        self.from_email = from_email or os.environ.get("PAGERDUTY_FROM_EMAIL")

        if not self.api_key:
            raise PagerDutyError(401, "PAGERDUTY_API_KEY not configured")
        if not self.from_email:
            raise PagerDutyError(400, "PAGERDUTY_FROM_EMAIL not configured")

        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "From": self.from_email,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make rate-limited API request."""
        await self.rate_limiter.acquire()

        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"

        async with session.request(method, url, json=data, params=params) as resp:
            body = await resp.json() if resp.content_length else {}

            if not resp.ok:
                error = body.get("error", {})
                raise PagerDutyError(
                    code=resp.status,
                    message=error.get("message", resp.reason or "Unknown error"),
                    errors=error.get("errors", []),
                )

            return body

    def _parse_incident(self, data: dict[str, Any]) -> Incident:
        """Parse incident from API response."""
        service_data = data.get("service", {})
        return Incident(
            id=data["id"],
            incident_number=data["incident_number"],
            title=data["title"],
            status=data["status"],
            urgency=data["urgency"],
            service=Service(
                id=service_data.get("id", ""),
                name=service_data.get("summary", ""),
                description=service_data.get("description"),
            ),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"].replace("Z", "+00:00")) if data.get("resolved_at") else None,
            html_url=data["html_url"],
            description=data.get("description"),
            assignments=data.get("assignments", []),
            acknowledgements=data.get("acknowledgements", []),
        )

    async def list_incidents(
        self,
        status: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> IncidentList:
        """Get incidents by status.

        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            limit: Max results (1-100)
            offset: Pagination offset

        Returns:
            IncidentList with incidents
        """
        params = {"limit": min(limit, 100), "offset": offset}
        if status:
            params["statuses[]"] = status

        data = await self._request("GET", "/incidents", params=params)

        incidents = [self._parse_incident(inc) for inc in data.get("incidents", [])]

        return IncidentList(
            incidents=incidents,
            total=data.get("total", len(incidents)),
            offset=offset,
            limit=limit,
            more=data.get("more", False),
        )

    async def get_incident(self, incident_id: str) -> Incident:
        """Get incident details.

        Args:
            incident_id: PagerDuty incident ID

        Returns:
            Incident details
        """
        data = await self._request("GET", f"/incidents/{incident_id}")
        return self._parse_incident(data["incident"])

    async def acknowledge_incident(self, incident_id: str) -> Incident:
        """Acknowledge an incident.

        Args:
            incident_id: PagerDuty incident ID

        Returns:
            Updated incident
        """
        data = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            data={
                "incident": {
                    "type": "incident_reference",
                    "status": "acknowledged",
                }
            },
        )
        return self._parse_incident(data["incident"])

    async def resolve_incident(self, incident_id: str) -> Incident:
        """Resolve an incident.

        Args:
            incident_id: PagerDuty incident ID

        Returns:
            Updated incident
        """
        data = await self._request(
            "PUT",
            f"/incidents/{incident_id}",
            data={
                "incident": {
                    "type": "incident_reference",
                    "status": "resolved",
                }
            },
        )
        return self._parse_incident(data["incident"])

    async def add_note(self, incident_id: str, note: str) -> IncidentNote:
        """Add note to incident.

        Args:
            incident_id: PagerDuty incident ID
            note: Note content

        Returns:
            Created note
        """
        data = await self._request(
            "POST",
            f"/incidents/{incident_id}/notes",
            data={"note": {"content": note}},
        )

        note_data = data["note"]
        user_data = note_data.get("user", {})

        return IncidentNote(
            id=note_data["id"],
            content=note_data["content"],
            created_at=datetime.fromisoformat(note_data["created_at"].replace("Z", "+00:00")),
            user=OnCallUser(
                id=user_data.get("id", ""),
                name=user_data.get("summary", ""),
                email=user_data.get("email", ""),
            ) if user_data else None,
        )

    async def get_oncall(
        self,
        schedule_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[OnCall]:
        """Get current on-call responders for a schedule.

        Args:
            schedule_id: PagerDuty schedule ID
            since: Start time (defaults to now)
            until: End time (defaults to now)

        Returns:
            List of on-call entries
        """
        params = {"schedule_ids[]": schedule_id}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        data = await self._request("GET", "/oncalls", params=params)

        oncalls = []
        for entry in data.get("oncalls", []):
            user_data = entry.get("user", {})
            schedule_data = entry.get("schedule", {})

            oncalls.append(OnCall(
                user=OnCallUser(
                    id=user_data.get("id", ""),
                    name=user_data.get("summary", ""),
                    email=user_data.get("email", ""),
                    avatar_url=user_data.get("avatar_url"),
                ),
                schedule_id=schedule_data.get("id", schedule_id),
                schedule_name=schedule_data.get("summary"),
                escalation_level=entry.get("escalation_level", 1),
                start=datetime.fromisoformat(entry["start"].replace("Z", "+00:00")) if entry.get("start") else None,
                end=datetime.fromisoformat(entry["end"].replace("Z", "+00:00")) if entry.get("end") else None,
            ))

        return oncalls

    async def create_incident(
        self,
        service_id: str,
        title: str,
        body: Optional[str] = None,
        urgency: str = "high",
    ) -> Incident:
        """Trigger a new incident.

        Args:
            service_id: Service ID to trigger on
            title: Incident title
            body: Incident description
            urgency: high or low

        Returns:
            Created incident
        """
        incident_data = {
            "type": "incident",
            "title": title,
            "urgency": urgency,
            "service": {
                "id": service_id,
                "type": "service_reference",
            },
        }

        if body:
            incident_data["body"] = {"type": "incident_body", "details": body}

        data = await self._request(
            "POST",
            "/incidents",
            data={"incident": incident_data},
        )

        return self._parse_incident(data["incident"])

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
