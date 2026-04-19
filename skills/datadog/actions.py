"""
Datadog Skill for OpenSRE

Query metrics, monitors, events, and manage incidents.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class MetricSeries:
    """Datadog metric time series."""
    metric: str
    scope: str
    points: list[tuple[float, float]]  # (timestamp, value)
    unit: str | None = None


@dataclass
class Monitor:
    """Datadog monitor."""
    id: int
    name: str
    type: str
    query: str
    message: str
    overall_state: str
    tags: list[str] = field(default_factory=list)
    priority: int | None = None
    created: datetime | None = None
    modified: datetime | None = None


@dataclass
class Event:
    """Datadog event."""
    id: int
    title: str
    text: str
    date_happened: datetime
    tags: list[str] = field(default_factory=list)
    priority: str | None = None
    alert_type: str | None = None


@dataclass
class Incident:
    """Datadog incident."""
    id: str
    title: str
    status: str
    severity: str
    customer_impact_scope: str | None = None
    created: datetime | None = None
    resolved: datetime | None = None


class DatadogSkill(Skill):
    """Skill for interacting with Datadog."""

    name = "datadog"
    version = "1.0.0"
    description = "Query Datadog metrics, monitors, events, and incidents"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.app_key = self.config.get("app_key", "")
        self.site = self.config.get("site", "datadoghq.com")
        self.timeout = self.config.get("timeout", 30)
        self.base_url = f"https://api.{self.site}"
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("query_metrics", self.query_metrics, "Query Datadog metrics")
        self.register_action("get_monitors", self.get_monitors, "List monitors")
        self.register_action("mute_monitor", self.mute_monitor, "Mute a monitor", requires_approval=True)
        self.register_action("get_events", self.get_events, "Query events")
        self.register_action("get_incidents", self.get_incidents, "List incidents")
        self.register_action("create_incident", self.create_incident, "Create incident")

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
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
        """Check Datadog API connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/api/v1/validate")
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy", "valid": True})
            return ActionResult.fail(f"Validation failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    async def query_metrics(
        self,
        query: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> ActionResult[list[MetricSeries]]:
        """Query Datadog metrics.

        Args:
            query: Datadog metrics query (e.g., "avg:system.cpu.user{*}")
            from_ts: Start timestamp (defaults to 1 hour ago)
            to_ts: End timestamp (defaults to now)
        """
        if not self._client:
            return ActionResult.fail("Client not initialized")

        now = int(time.time())
        from_ts = from_ts or (now - 3600)
        to_ts = to_ts or now

        try:
            response = await self._client.get(
                "/api/v1/query",
                params={"query": query, "from": from_ts, "to": to_ts},
            )
            response.raise_for_status()
            data = response.json()

            series = []
            for s in data.get("series", []):
                series.append(MetricSeries(
                    metric=s.get("metric", ""),
                    scope=s.get("scope", ""),
                    points=[(p[0], p[1]) for p in s.get("pointlist", [])],
                    unit=s.get("unit", [{}])[0].get("name") if s.get("unit") else None,
                ))
            return ActionResult.ok(series)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error querying metrics")
            return ActionResult.fail(str(e))

    async def get_monitors(
        self,
        tags: list[str] | None = None,
        monitor_states: list[str] | None = None,
    ) -> ActionResult[list[Monitor]]:
        """List Datadog monitors."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {}
            if tags:
                params["tags"] = ",".join(tags)
            if monitor_states:
                params["monitor_states"] = ",".join(monitor_states)

            response = await self._client.get("/api/v1/monitor", params=params)
            response.raise_for_status()
            data = response.json()

            monitors = []
            for m in data:
                monitors.append(Monitor(
                    id=m["id"],
                    name=m.get("name", ""),
                    type=m.get("type", ""),
                    query=m.get("query", ""),
                    message=m.get("message", ""),
                    overall_state=m.get("overall_state", "Unknown"),
                    tags=m.get("tags", []),
                    priority=m.get("priority"),
                ))
            return ActionResult.ok(monitors)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing monitors")
            return ActionResult.fail(str(e))

    async def mute_monitor(
        self,
        monitor_id: int,
        end: int | None = None,
        scope: str | None = None,
    ) -> ActionResult[bool]:
        """Mute a Datadog monitor."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {}
            if end:
                body["end"] = end
            if scope:
                body["scope"] = scope

            response = await self._client.post(
                f"/api/v1/monitor/{monitor_id}/mute",
                json=body,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error muting monitor")
            return ActionResult.fail(str(e))

    async def get_events(
        self,
        start: int,
        end: int,
        tags: str | None = None,
    ) -> ActionResult[list[Event]]:
        """Query Datadog events."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {"start": start, "end": end}
            if tags:
                params["tags"] = tags

            response = await self._client.get("/api/v1/events", params=params)
            response.raise_for_status()
            data = response.json()

            events = []
            for e in data.get("events", []):
                events.append(Event(
                    id=e["id"],
                    title=e.get("title", ""),
                    text=e.get("text", ""),
                    date_happened=datetime.fromtimestamp(e.get("date_happened", 0)),
                    tags=e.get("tags", []),
                    priority=e.get("priority"),
                    alert_type=e.get("alert_type"),
                ))
            return ActionResult.ok(events)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error querying events")
            return ActionResult.fail(str(e))

    async def get_incidents(
        self,
        status: str | None = None,
    ) -> ActionResult[list[Incident]]:
        """List Datadog incidents."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {}
            if status:
                params["status"] = status

            # Use v2 API for incidents
            response = await self._client.get("/api/v2/incidents", params=params)
            response.raise_for_status()
            data = response.json()

            incidents = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                incidents.append(Incident(
                    id=item["id"],
                    title=attrs.get("title", ""),
                    status=attrs.get("status", ""),
                    severity=attrs.get("severity", ""),
                    customer_impact_scope=attrs.get("customer_impact_scope"),
                    created=datetime.fromisoformat(attrs["created"].replace("Z", "+00:00")) if attrs.get("created") else None,
                    resolved=datetime.fromisoformat(attrs["resolved"].replace("Z", "+00:00")) if attrs.get("resolved") else None,
                ))
            return ActionResult.ok(incidents)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing incidents")
            return ActionResult.fail(str(e))

    async def create_incident(
        self,
        title: str,
        severity: str,
        customer_impact_scope: str | None = None,
    ) -> ActionResult[Incident]:
        """Create a Datadog incident."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body = {
                "data": {
                    "type": "incidents",
                    "attributes": {
                        "title": title,
                        "severity": severity,
                    }
                }
            }
            if customer_impact_scope:
                body["data"]["attributes"]["customer_impact_scope"] = customer_impact_scope

            response = await self._client.post("/api/v2/incidents", json=body)
            response.raise_for_status()
            data = response.json()

            item = data.get("data", {})
            attrs = item.get("attributes", {})
            return ActionResult.ok(Incident(
                id=item["id"],
                title=attrs.get("title", ""),
                status=attrs.get("status", ""),
                severity=attrs.get("severity", ""),
                customer_impact_scope=attrs.get("customer_impact_scope"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error creating incident")
            return ActionResult.fail(str(e))
