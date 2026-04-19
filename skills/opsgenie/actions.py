"""
OpsGenie Skill for OpenSRE

Alert and incident management via OpsGenie API.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """OpsGenie alert."""
    id: str
    tiny_id: str
    message: str
    status: str
    priority: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    acknowledged: bool = False
    acknowledged_by: str | None = None
    owner: str | None = None


@dataclass
class OnCallParticipant:
    """On-call participant."""
    id: str
    name: str
    type: str


@dataclass
class OnCallSchedule:
    """On-call schedule."""
    id: str
    name: str
    participants: list[OnCallParticipant] = field(default_factory=list)


class OpsGenieSkill(Skill):
    """Skill for interacting with OpsGenie."""

    name = "opsgenie"
    version = "1.0.0"
    description = "OpsGenie alert and incident management"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.api_url = self.config.get("api_url", "https://api.opsgenie.com")
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("list_alerts", self.list_alerts, "List alerts")
        self.register_action("get_alert", self.get_alert, "Get alert details")
        self.register_action("acknowledge_alert", self.acknowledge_alert, "Acknowledge alert")
        self.register_action("close_alert", self.close_alert, "Close alert")
        self.register_action("create_alert", self.create_alert, "Create alert")
        self.register_action("get_oncall", self.get_oncall, "Get on-call schedule")

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={
                "Authorization": f"GenieKey {self.api_key}",
                "Content-Type": "application/json",
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
        """Check OpsGenie API connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/v2/heartbeats")
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy"})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    async def list_alerts(
        self,
        query: str | None = None,
        status: str | None = None,
    ) -> ActionResult[list[Alert]]:
        """List OpsGenie alerts."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {}
            if query:
                params["query"] = query
            elif status:
                params["query"] = f"status:{status}"

            response = await self._client.get("/v2/alerts", params=params)
            response.raise_for_status()
            data = response.json()

            alerts = []
            for a in data.get("data", []):
                alerts.append(Alert(
                    id=a["id"],
                    tiny_id=a.get("tinyId", ""),
                    message=a.get("message", ""),
                    status=a.get("status", ""),
                    priority=a.get("priority", "P3"),
                    tags=a.get("tags", []),
                    acknowledged=a.get("acknowledged", False),
                    owner=a.get("owner"),
                ))
            return ActionResult.ok(alerts)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing alerts")
            return ActionResult.fail(str(e))

    async def get_alert(self, alert_id: str) -> ActionResult[Alert]:
        """Get alert details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(f"/v2/alerts/{alert_id}")
            response.raise_for_status()
            data = response.json().get("data", {})

            return ActionResult.ok(Alert(
                id=data["id"],
                tiny_id=data.get("tinyId", ""),
                message=data.get("message", ""),
                status=data.get("status", ""),
                priority=data.get("priority", "P3"),
                tags=data.get("tags", []),
                acknowledged=data.get("acknowledged", False),
                owner=data.get("owner"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting alert")
            return ActionResult.fail(str(e))

    async def acknowledge_alert(
        self,
        alert_id: str,
        note: str | None = None,
    ) -> ActionResult[bool]:
        """Acknowledge an alert."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {}
            if note:
                body["note"] = note

            response = await self._client.post(
                f"/v2/alerts/{alert_id}/acknowledge",
                json=body,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error acknowledging alert")
            return ActionResult.fail(str(e))

    async def close_alert(
        self,
        alert_id: str,
        note: str | None = None,
    ) -> ActionResult[bool]:
        """Close an alert."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {}
            if note:
                body["note"] = note

            response = await self._client.post(
                f"/v2/alerts/{alert_id}/close",
                json=body,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error closing alert")
            return ActionResult.fail(str(e))

    async def create_alert(
        self,
        message: str,
        priority: str = "P3",
        tags: list[str] | None = None,
    ) -> ActionResult[Alert]:
        """Create a new alert."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {
                "message": message,
                "priority": priority,
            }
            if tags:
                body["tags"] = tags

            response = await self._client.post("/v2/alerts", json=body)
            response.raise_for_status()
            data = response.json()

            return ActionResult.ok(Alert(
                id=data.get("requestId", ""),
                tiny_id="",
                message=message,
                status="open",
                priority=priority,
                tags=tags or [],
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error creating alert")
            return ActionResult.fail(str(e))

    async def get_oncall(self, schedule_id: str) -> ActionResult[OnCallSchedule]:
        """Get on-call schedule."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(f"/v2/schedules/{schedule_id}/on-calls")
            response.raise_for_status()
            data = response.json().get("data", {})

            participants = []
            for p in data.get("onCallParticipants", []):
                participants.append(OnCallParticipant(
                    id=p.get("id", ""),
                    name=p.get("name", ""),
                    type=p.get("type", ""),
                ))

            return ActionResult.ok(OnCallSchedule(
                id=schedule_id,
                name=data.get("_parent", {}).get("name", ""),
                participants=participants,
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting on-call")
            return ActionResult.fail(str(e))
