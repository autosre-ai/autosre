"""
ServiceNow Skill for OpenSRE

Incident and change management via ServiceNow API.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Incident:
    """ServiceNow incident."""
    sys_id: str
    number: str
    short_description: str
    description: str
    state: str
    urgency: int
    impact: int
    priority: int
    assignment_group: str | None = None
    assigned_to: str | None = None
    opened_at: datetime | None = None
    resolved_at: datetime | None = None
    caller_id: str | None = None


@dataclass
class ChangeRequest:
    """ServiceNow change request."""
    sys_id: str
    number: str
    short_description: str
    state: str
    type: str
    risk: str
    impact: int
    start_date: datetime | None = None
    end_date: datetime | None = None


class ServiceNowSkill(Skill):
    """Skill for interacting with ServiceNow."""

    name = "servicenow"
    version = "1.0.0"
    description = "ServiceNow incident and change management"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.instance = self.config.get("instance", "")
        self.username = self.config.get("username", "")
        self.password = self.config.get("password", "")
        self.timeout = self.config.get("timeout", 30)
        self.base_url = f"https://{self.instance}/api/now"
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("get_incidents", self.get_incidents, "Query incidents")
        self.register_action("get_incident", self.get_incident, "Get incident details")
        self.register_action("create_incident", self.create_incident, "Create incident")
        self.register_action("update_incident", self.update_incident, "Update incident")
        self.register_action("add_work_note", self.add_work_note, "Add work note")
        self.register_action("get_change_requests", self.get_change_requests, "Query change requests")

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.password),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )
        self._initialized = True

    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check ServiceNow connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/table/sys_user?sysparm_limit=1")
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy"})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    def _parse_incident(self, data: dict) -> Incident:
        """Parse incident from API response."""
        return Incident(
            sys_id=data.get("sys_id", ""),
            number=data.get("number", ""),
            short_description=data.get("short_description", ""),
            description=data.get("description", ""),
            state=data.get("state", ""),
            urgency=int(data.get("urgency", 3)),
            impact=int(data.get("impact", 3)),
            priority=int(data.get("priority", 5)),
            assignment_group=data.get("assignment_group", {}).get("display_value"),
            assigned_to=data.get("assigned_to", {}).get("display_value"),
            caller_id=data.get("caller_id", {}).get("display_value"),
        )

    async def get_incidents(
        self,
        query: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ) -> ActionResult[list[Incident]]:
        """Query ServiceNow incidents."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {"sysparm_limit": limit}

            queries = []
            if query:
                queries.append(query)
            if state:
                state_map = {
                    "new": 1, "in_progress": 2, "on_hold": 3,
                    "resolved": 6, "closed": 7
                }
                if state in state_map:
                    queries.append(f"state={state_map[state]}")

            if queries:
                params["sysparm_query"] = "^".join(queries)

            response = await self._client.get("/table/incident", params=params)
            response.raise_for_status()
            data = response.json()

            incidents = [self._parse_incident(i) for i in data.get("result", [])]
            return ActionResult.ok(incidents)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error querying incidents")
            return ActionResult.fail(str(e))

    async def get_incident(self, sys_id: str) -> ActionResult[Incident]:
        """Get incident details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(f"/table/incident/{sys_id}")
            response.raise_for_status()
            data = response.json().get("result", {})
            return ActionResult.ok(self._parse_incident(data))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting incident")
            return ActionResult.fail(str(e))

    async def create_incident(
        self,
        short_description: str,
        description: str | None = None,
        urgency: int = 3,
        impact: int = 3,
        assignment_group: str | None = None,
    ) -> ActionResult[Incident]:
        """Create a new incident."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {
                "short_description": short_description,
                "urgency": urgency,
                "impact": impact,
            }
            if description:
                body["description"] = description
            if assignment_group:
                body["assignment_group"] = assignment_group

            response = await self._client.post("/table/incident", json=body)
            response.raise_for_status()
            data = response.json().get("result", {})
            return ActionResult.ok(self._parse_incident(data))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error creating incident")
            return ActionResult.fail(str(e))

    async def update_incident(
        self,
        sys_id: str,
        fields: dict[str, Any],
    ) -> ActionResult[Incident]:
        """Update an incident."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.patch(f"/table/incident/{sys_id}", json=fields)
            response.raise_for_status()
            data = response.json().get("result", {})
            return ActionResult.ok(self._parse_incident(data))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error updating incident")
            return ActionResult.fail(str(e))

    async def add_work_note(
        self,
        sys_id: str,
        note: str,
    ) -> ActionResult[bool]:
        """Add work note to incident."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.patch(
                f"/table/incident/{sys_id}",
                json={"work_notes": note},
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error adding work note")
            return ActionResult.fail(str(e))

    async def get_change_requests(
        self,
        query: str | None = None,
        state: str | None = None,
    ) -> ActionResult[list[ChangeRequest]]:
        """Query change requests."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {"sysparm_limit": 100}

            queries = []
            if query:
                queries.append(query)
            if state:
                queries.append(f"state={state}")

            if queries:
                params["sysparm_query"] = "^".join(queries)

            response = await self._client.get("/table/change_request", params=params)
            response.raise_for_status()
            data = response.json()

            changes = []
            for c in data.get("result", []):
                changes.append(ChangeRequest(
                    sys_id=c.get("sys_id", ""),
                    number=c.get("number", ""),
                    short_description=c.get("short_description", ""),
                    state=c.get("state", ""),
                    type=c.get("type", ""),
                    risk=c.get("risk", ""),
                    impact=int(c.get("impact", 3)),
                ))
            return ActionResult.ok(changes)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error querying change requests")
            return ActionResult.fail(str(e))
