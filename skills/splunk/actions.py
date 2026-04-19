"""
Splunk Skill for OpenSRE

Query logs and metrics from Splunk.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Splunk search result."""
    raw: str
    time: datetime | None = None
    host: str | None = None
    source: str | None = None
    sourcetype: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class SavedSearch:
    """Splunk saved search."""
    name: str
    search: str
    description: str | None = None
    is_scheduled: bool = False
    cron_schedule: str | None = None


@dataclass
class Alert:
    """Splunk triggered alert."""
    name: str
    severity: str
    trigger_time: datetime | None = None
    results_count: int = 0


class SplunkSkill(Skill):
    """Skill for interacting with Splunk."""

    name = "splunk"
    version = "1.0.0"
    description = "Query Splunk for logs and metrics"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", 8089)
        self.username = self.config.get("username", "")
        self.password = self.config.get("password", "")
        self.verify_ssl = self.config.get("verify_ssl", True)
        self.timeout = self.config.get("timeout", 60)
        self.base_url = f"https://{self.host}:{self.port}"
        self._client: httpx.AsyncClient | None = None
        self._session_key: str | None = None

        # Register actions
        self.register_action("search", self.search, "Execute Splunk search")
        self.register_action("get_saved_searches", self.get_saved_searches, "List saved searches")
        self.register_action("run_saved_search", self.run_saved_search, "Run saved search")
        self.register_action("get_alerts", self.get_alerts, "Get triggered alerts")

    async def initialize(self) -> None:
        """Initialize HTTP client and authenticate."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify_ssl,
            timeout=self.timeout,
        )

        # Authenticate to get session key
        try:
            response = await self._client.post(
                "/services/auth/login",
                data={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
            # Parse session key from XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            session_key = root.find(".//sessionKey")
            if session_key is not None:
                self._session_key = session_key.text
                self._client.headers["Authorization"] = f"Splunk {self._session_key}"
        except Exception as e:
            logger.error(f"Failed to authenticate with Splunk: {e}")

        self._initialized = True

    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Splunk connectivity."""
        if not self._client or not self._session_key:
            return ActionResult.fail("Client not authenticated")
        try:
            response = await self._client.get(
                "/services/server/info",
                params={"output_mode": "json"},
            )
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy"})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    async def search(
        self,
        query: str,
        earliest_time: str = "-1h",
        latest_time: str = "now",
        max_results: int = 100,
    ) -> ActionResult[list[SearchResult]]:
        """Execute a Splunk search."""
        if not self._client or not self._session_key:
            return ActionResult.fail("Client not authenticated")

        try:
            # Create search job
            response = await self._client.post(
                "/services/search/jobs",
                data={
                    "search": f"search {query}" if not query.startswith("search") else query,
                    "earliest_time": earliest_time,
                    "latest_time": latest_time,
                    "output_mode": "json",
                },
            )
            response.raise_for_status()
            job_data = response.json()
            job_id = job_data.get("sid")

            if not job_id:
                return ActionResult.fail("Failed to create search job")

            # Poll for job completion
            for _ in range(60):  # Max 60 seconds
                status_response = await self._client.get(
                    f"/services/search/jobs/{job_id}",
                    params={"output_mode": "json"},
                )
                status_data = status_response.json()
                entry = status_data.get("entry", [{}])[0]
                content = entry.get("content", {})

                if content.get("isDone"):
                    break
                await asyncio.sleep(1)
            else:
                return ActionResult.fail("Search job timed out")

            # Get results
            results_response = await self._client.get(
                f"/services/search/jobs/{job_id}/results",
                params={"output_mode": "json", "count": max_results},
            )
            results_data = results_response.json()

            results = []
            for r in results_data.get("results", []):
                results.append(SearchResult(
                    raw=r.get("_raw", ""),
                    host=r.get("host"),
                    source=r.get("source"),
                    sourcetype=r.get("sourcetype"),
                    fields={k: v for k, v in r.items() if not k.startswith("_")},
                ))
            return ActionResult.ok(results)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error executing search")
            return ActionResult.fail(str(e))

    async def get_saved_searches(self) -> ActionResult[list[SavedSearch]]:
        """List saved searches."""
        if not self._client or not self._session_key:
            return ActionResult.fail("Client not authenticated")

        try:
            response = await self._client.get(
                "/services/saved/searches",
                params={"output_mode": "json", "count": 0},
            )
            response.raise_for_status()
            data = response.json()

            searches = []
            for entry in data.get("entry", []):
                content = entry.get("content", {})
                searches.append(SavedSearch(
                    name=entry.get("name", ""),
                    search=content.get("search", ""),
                    description=content.get("description"),
                    is_scheduled=content.get("is_scheduled", False),
                    cron_schedule=content.get("cron_schedule"),
                ))
            return ActionResult.ok(searches)
        except Exception as e:
            logger.exception("Error listing saved searches")
            return ActionResult.fail(str(e))

    async def run_saved_search(self, name: str) -> ActionResult[list[SearchResult]]:
        """Run a saved search."""
        if not self._client or not self._session_key:
            return ActionResult.fail("Client not authenticated")

        try:
            # Get the saved search
            response = await self._client.get(
                f"/services/saved/searches/{name}",
                params={"output_mode": "json"},
            )
            response.raise_for_status()
            data = response.json()
            entry = data.get("entry", [{}])[0]
            search_query = entry.get("content", {}).get("search", "")

            if not search_query:
                return ActionResult.fail(f"Saved search '{name}' not found")

            return await self.search(search_query)
        except Exception as e:
            logger.exception("Error running saved search")
            return ActionResult.fail(str(e))

    async def get_alerts(
        self,
        severity: str | None = None,
    ) -> ActionResult[list[Alert]]:
        """Get triggered alerts."""
        if not self._client or not self._session_key:
            return ActionResult.fail("Client not authenticated")

        try:
            response = await self._client.get(
                "/services/alerts/fired_alerts",
                params={"output_mode": "json", "count": 0},
            )
            response.raise_for_status()
            data = response.json()

            alerts = []
            for entry in data.get("entry", []):
                content = entry.get("content", {})
                alert_severity = content.get("severity", "unknown")

                if severity and alert_severity != severity:
                    continue

                alerts.append(Alert(
                    name=entry.get("name", ""),
                    severity=alert_severity,
                    results_count=content.get("triggered_alert_count", 0),
                ))
            return ActionResult.ok(alerts)
        except Exception as e:
            logger.exception("Error getting alerts")
            return ActionResult.fail(str(e))
