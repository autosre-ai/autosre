"""
Jenkins Skill for OpenSRE

CI/CD integration with Jenkins.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Jenkins job."""
    name: str
    url: str
    color: str  # blue, red, yellow, disabled, etc.
    buildable: bool
    last_build_number: int | None = None
    last_successful_build: int | None = None
    last_failed_build: int | None = None


@dataclass
class Build:
    """Jenkins build."""
    number: int
    url: str
    result: str | None  # SUCCESS, FAILURE, UNSTABLE, ABORTED, None (in progress)
    building: bool
    duration: int  # milliseconds
    timestamp: int  # milliseconds since epoch
    display_name: str | None = None


class JenkinsSkill(Skill):
    """Skill for interacting with Jenkins."""

    name = "jenkins"
    version = "1.0.0"
    description = "Jenkins CI/CD integration"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "").rstrip("/")
        self.username = self.config.get("username", "")
        self.api_token = self.config.get("api_token", "")
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("get_jobs", self.get_jobs, "List Jenkins jobs")
        self.register_action("get_job", self.get_job, "Get job details")
        self.register_action("trigger_build", self.trigger_build, "Trigger build", requires_approval=True)
        self.register_action("get_build", self.get_build, "Get build details")
        self.register_action("get_build_log", self.get_build_log, "Get build log")
        self.register_action("stop_build", self.stop_build, "Stop build", requires_approval=True)

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.url,
            auth=(self.username, self.api_token),
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
        """Check Jenkins connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/api/json")
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy"})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    async def get_jobs(
        self,
        folder: str | None = None,
    ) -> ActionResult[list[Job]]:
        """List Jenkins jobs."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            path = f"/job/{folder}/api/json" if folder else "/api/json"
            response = await self._client.get(path)
            response.raise_for_status()
            data = response.json()

            jobs = []
            for j in data.get("jobs", []):
                jobs.append(Job(
                    name=j.get("name", ""),
                    url=j.get("url", ""),
                    color=j.get("color", ""),
                    buildable=j.get("buildable", True),
                ))
            return ActionResult.ok(jobs)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing jobs")
            return ActionResult.fail(str(e))

    async def get_job(self, name: str) -> ActionResult[Job]:
        """Get job details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(f"/job/{name}/api/json")
            response.raise_for_status()
            j = response.json()

            return ActionResult.ok(Job(
                name=j.get("name", ""),
                url=j.get("url", ""),
                color=j.get("color", ""),
                buildable=j.get("buildable", True),
                last_build_number=j.get("lastBuild", {}).get("number"),
                last_successful_build=j.get("lastSuccessfulBuild", {}).get("number"),
                last_failed_build=j.get("lastFailedBuild", {}).get("number"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting job")
            return ActionResult.fail(str(e))

    async def trigger_build(
        self,
        name: str,
        parameters: dict[str, Any] | None = None,
    ) -> ActionResult[Build]:
        """Trigger a job build."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            if parameters:
                response = await self._client.post(
                    f"/job/{name}/buildWithParameters",
                    data=parameters,
                )
            else:
                response = await self._client.post(f"/job/{name}/build")

            response.raise_for_status()

            # Get the queue location from header
            queue_url = response.headers.get("Location")

            return ActionResult.ok(Build(
                number=0,  # Will be assigned by Jenkins
                url=queue_url or "",
                result=None,
                building=True,
                duration=0,
                timestamp=0,
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error triggering build")
            return ActionResult.fail(str(e))

    async def get_build(
        self,
        job_name: str,
        build_number: int,
    ) -> ActionResult[Build]:
        """Get build details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/job/{job_name}/{build_number}/api/json"
            )
            response.raise_for_status()
            b = response.json()

            return ActionResult.ok(Build(
                number=b.get("number", 0),
                url=b.get("url", ""),
                result=b.get("result"),
                building=b.get("building", False),
                duration=b.get("duration", 0),
                timestamp=b.get("timestamp", 0),
                display_name=b.get("displayName"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting build")
            return ActionResult.fail(str(e))

    async def get_build_log(
        self,
        job_name: str,
        build_number: int,
    ) -> ActionResult[str]:
        """Get build console output."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/job/{job_name}/{build_number}/consoleText"
            )
            response.raise_for_status()
            return ActionResult.ok(response.text)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting build log")
            return ActionResult.fail(str(e))

    async def stop_build(
        self,
        job_name: str,
        build_number: int,
    ) -> ActionResult[bool]:
        """Stop a running build."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.post(
                f"/job/{job_name}/{build_number}/stop"
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error stopping build")
            return ActionResult.fail(str(e))
