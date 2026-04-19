"""
Dynatrace Skill Actions

Query Dynatrace for problems, metrics, and monitored entities.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill, action

logger = logging.getLogger(__name__)


@dataclass
class Problem:
    """Dynatrace problem."""
    problem_id: str
    display_id: str
    title: str
    status: str  # OPEN, CLOSED
    severity_level: str
    impact_level: str
    affected_entities: list[dict[str, str]]
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass
class ProblemDetails:
    """Detailed Dynatrace problem."""
    problem: Problem
    root_cause_entity: dict[str, str] | None = None
    impacted_entities: list[dict[str, str]] = field(default_factory=list)
    evidence_details: list[dict[str, Any]] = field(default_factory=list)
    recent_comments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MetricDataPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float | None


@dataclass
class MetricSeries:
    """Metric time series."""
    metric_id: str
    dimensions: dict[str, str]
    data_points: list[MetricDataPoint]


@dataclass
class MetricData:
    """Metric query result."""
    metric_key: str
    unit: str
    series: list[MetricSeries]


@dataclass
class Entity:
    """Dynatrace monitored entity."""
    entity_id: str
    display_name: str
    entity_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    management_zones: list[str] = field(default_factory=list)


class DynatraceSkill(Skill):
    """Skill for querying Dynatrace."""

    name = "dynatrace"
    version = "1.0.0"
    description = "Query Dynatrace for problems, metrics, and entities"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "").rstrip("/")
        self.api_token = self.config.get("api_token", "")
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("get_problems", self.get_problems, "Get active problems")
        self.register_action("get_problem_details", self.get_problem_details, "Get problem details")
        self.register_action("get_metrics", self.get_metrics, "Query metrics")
        self.register_action("get_entities", self.get_entities, "List entities")

    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Api-Token {self.api_token}",
            "Accept": "application/json",
        }

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._get_headers(),
        )
        await super().initialize()

    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().shutdown()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._get_headers(),
            )
        return self._client

    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Dynatrace API connection."""
        if not self.url:
            return ActionResult.fail("Dynatrace URL not configured")
        if not self.api_token:
            return ActionResult.fail("Dynatrace API token not configured")

        try:
            response = await self.client.get(
                f"{self.url}/api/v1/time",
            )
            response.raise_for_status()
            return ActionResult.ok({
                "status": "healthy",
                "url": self.url,
            })
        except Exception as e:
            return ActionResult.fail(f"Connection failed: {e}")

    @action(description="Get active problems")
    async def get_problems(
        self,
        status: str = "OPEN",
        impact_level: str | None = None,
        severity_level: str | None = None,
    ) -> ActionResult[list[Problem]]:
        """Get problems from Dynatrace.

        Args:
            status: Problem status (OPEN or CLOSED)
            impact_level: Filter by impact level
            severity_level: Filter by severity level

        Returns:
            List of problems
        """
        try:
            params: dict[str, str] = {"problemSelector": f"status(\"{status}\")"}

            if impact_level:
                params["problemSelector"] += f",impactLevel(\"{impact_level}\")"
            if severity_level:
                params["problemSelector"] += f",severityLevel(\"{severity_level}\")"

            response = await self.client.get(
                f"{self.url}/api/v2/problems",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            problems = []
            for p in data.get("problems", []):
                problems.append(Problem(
                    problem_id=p.get("problemId", ""),
                    display_id=p.get("displayId", ""),
                    title=p.get("title", ""),
                    status=p.get("status", "UNKNOWN"),
                    severity_level=p.get("severityLevel", "UNKNOWN"),
                    impact_level=p.get("impactLevel", "UNKNOWN"),
                    affected_entities=[
                        {"id": e.get("entityId", {}).get("id", ""), "name": e.get("name", "")}
                        for e in p.get("affectedEntities", [])
                    ],
                    start_time=self._parse_timestamp(p.get("startTime")),
                    end_time=self._parse_timestamp(p.get("endTime")),
                ))

            return ActionResult.ok(problems, total=len(problems))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return ActionResult.fail("Authentication failed - check API token")
            return ActionResult.fail(f"API error: {e.response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get problems: {e}")

    @action(description="Get problem details")
    async def get_problem_details(self, problem_id: str) -> ActionResult[ProblemDetails]:
        """Get detailed problem information.

        Args:
            problem_id: Problem ID

        Returns:
            Detailed problem info
        """
        try:
            response = await self.client.get(
                f"{self.url}/api/v2/problems/{problem_id}",
            )
            response.raise_for_status()
            data = response.json()

            # Parse basic problem info
            problem = Problem(
                problem_id=data.get("problemId", ""),
                display_id=data.get("displayId", ""),
                title=data.get("title", ""),
                status=data.get("status", "UNKNOWN"),
                severity_level=data.get("severityLevel", "UNKNOWN"),
                impact_level=data.get("impactLevel", "UNKNOWN"),
                affected_entities=[
                    {"id": e.get("entityId", {}).get("id", ""), "name": e.get("name", "")}
                    for e in data.get("affectedEntities", [])
                ],
                start_time=self._parse_timestamp(data.get("startTime")),
                end_time=self._parse_timestamp(data.get("endTime")),
            )

            # Parse root cause
            root_cause = None
            rc = data.get("rootCauseEntity")
            if rc:
                root_cause = {
                    "id": rc.get("entityId", {}).get("id", ""),
                    "name": rc.get("name", ""),
                    "type": rc.get("entityId", {}).get("type", ""),
                }

            # Parse impacted entities
            impacted = [
                {"id": e.get("entityId", {}).get("id", ""), "name": e.get("name", "")}
                for e in data.get("impactedEntities", [])
            ]

            # Parse evidence
            evidence = []
            for ev in data.get("evidenceDetails", {}).get("details", []):
                evidence.append({
                    "type": ev.get("evidenceType", ""),
                    "entity": ev.get("entity", {}).get("name", ""),
                    "data": ev.get("data", {}),
                })

            return ActionResult.ok(ProblemDetails(
                problem=problem,
                root_cause_entity=root_cause,
                impacted_entities=impacted,
                evidence_details=evidence,
            ))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ActionResult.fail(f"Problem not found: {problem_id}")
            return ActionResult.fail(f"API error: {e.response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get problem details: {e}")

    @action(description="Query metrics")
    async def get_metrics(
        self,
        metric_key: str,
        entity: str | None = None,
        time_range: str = "now-1h",
        resolution: str | None = None,
    ) -> ActionResult[MetricData]:
        """Query metrics from Dynatrace.

        Args:
            metric_key: Metric key (e.g., builtin:host.cpu.usage)
            entity: Entity selector (optional)
            time_range: Time range (e.g., now-1h, now-24h)
            resolution: Resolution (e.g., 1m, 5m)

        Returns:
            Metric data
        """
        try:
            params = {
                "metricSelector": metric_key,
                "from": time_range,
            }

            if entity:
                params["entitySelector"] = entity
            if resolution:
                params["resolution"] = resolution

            response = await self.client.get(
                f"{self.url}/api/v2/metrics/query",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            # Parse metric results
            series_list = []
            for result in data.get("result", []):
                metric_id = result.get("metricId", metric_key)

                for series_data in result.get("data", []):
                    dimensions = series_data.get("dimensions", [])
                    dimension_map = {}
                    for i, dim in enumerate(result.get("dimensionMap", {}).values()):
                        if i < len(dimensions):
                            dimension_map[dim] = dimensions[i]

                    timestamps = series_data.get("timestamps", [])
                    values = series_data.get("values", [])

                    data_points = []
                    for ts, val in zip(timestamps, values, strict=False):
                        data_points.append(MetricDataPoint(
                            timestamp=self._parse_timestamp(ts),
                            value=val,
                        ))

                    series_list.append(MetricSeries(
                        metric_id=metric_id,
                        dimensions=dimension_map,
                        data_points=data_points,
                    ))

            # Get unit from first result
            unit = ""
            if data.get("result"):
                unit = data["result"][0].get("unit", "")

            return ActionResult.ok(MetricData(
                metric_key=metric_key,
                unit=unit,
                series=series_list,
            ))

        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"API error: {e.response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Failed to query metrics: {e}")

    @action(description="List entities")
    async def get_entities(
        self,
        type: str,
        filter: str | None = None,
        limit: int = 100,
    ) -> ActionResult[list[Entity]]:
        """List monitored entities.

        Args:
            type: Entity type (HOST, SERVICE, PROCESS_GROUP, APPLICATION)
            filter: Entity selector filter
            limit: Maximum entities to return

        Returns:
            List of entities
        """
        try:
            entity_selector = f"type(\"{type}\")"
            if filter:
                entity_selector += f",{filter}"

            params = {
                "entitySelector": entity_selector,
                "pageSize": min(limit, 500),
                "fields": "+properties,+tags,+managementZones",
            }

            response = await self.client.get(
                f"{self.url}/api/v2/entities",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            entities = []
            for e in data.get("entities", [])[:limit]:
                entities.append(Entity(
                    entity_id=e.get("entityId", ""),
                    display_name=e.get("displayName", ""),
                    entity_type=e.get("type", type),
                    properties=e.get("properties", {}),
                    tags=[t.get("key", "") for t in e.get("tags", [])],
                    management_zones=[mz.get("name", "") for mz in e.get("managementZones", [])],
                ))

            return ActionResult.ok(entities, total=len(entities))

        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"API error: {e.response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get entities: {e}")

    def _parse_timestamp(self, ts: int | None) -> datetime | None:
        """Parse Dynatrace timestamp (milliseconds)."""
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(ts / 1000)
        except (ValueError, TypeError):
            return None
