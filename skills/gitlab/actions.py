"""
GitLab Skill for OpenSRE

Pipeline, issue, and merge request management.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Pipeline:
    """GitLab pipeline."""
    id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    duration: int | None = None  # seconds


@dataclass
class Job:
    """GitLab CI job."""
    id: int
    name: str
    status: str
    stage: str
    web_url: str
    duration: float | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class MergeRequest:
    """GitLab merge request."""
    id: int
    iid: int
    title: str
    state: str
    source_branch: str
    target_branch: str
    web_url: str
    author: str | None = None
    created_at: datetime | None = None


class GitLabSkill(Skill):
    """Skill for interacting with GitLab."""

    name = "gitlab"
    version = "1.0.0"
    description = "GitLab pipeline and merge request management"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "https://gitlab.com").rstrip("/")
        self.token = self.config.get("token", "")
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("get_pipelines", self.get_pipelines, "List pipelines")
        self.register_action("get_pipeline", self.get_pipeline, "Get pipeline")
        self.register_action("trigger_pipeline", self.trigger_pipeline, "Trigger pipeline", requires_approval=True)
        self.register_action("cancel_pipeline", self.cancel_pipeline, "Cancel pipeline", requires_approval=True)
        self.register_action("retry_pipeline", self.retry_pipeline, "Retry pipeline", requires_approval=True)
        self.register_action("get_merge_requests", self.get_merge_requests, "List MRs")
        self.register_action("get_jobs", self.get_jobs, "List pipeline jobs")

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=f"{self.url}/api/v4",
            headers={
                "PRIVATE-TOKEN": self.token,
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
        """Check GitLab connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/user")
            if response.status_code == 200:
                data = response.json()
                return ActionResult.ok({"status": "healthy", "user": data.get("username")})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    def _encode_project(self, project_id: str) -> str:
        """URL-encode project ID for path."""
        if "/" in project_id:
            return quote_plus(project_id)
        return project_id

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except:
            return None

    async def get_pipelines(
        self,
        project_id: str,
        status: str | None = None,
    ) -> ActionResult[list[Pipeline]]:
        """List project pipelines."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {"per_page": 20}
            if status:
                params["status"] = status

            response = await self._client.get(
                f"/projects/{self._encode_project(project_id)}/pipelines",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            pipelines = []
            for p in data:
                pipelines.append(Pipeline(
                    id=p["id"],
                    status=p.get("status", ""),
                    ref=p.get("ref", ""),
                    sha=p.get("sha", ""),
                    web_url=p.get("web_url", ""),
                    created_at=self._parse_datetime(p.get("created_at")),
                    updated_at=self._parse_datetime(p.get("updated_at")),
                ))
            return ActionResult.ok(pipelines)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing pipelines")
            return ActionResult.fail(str(e))

    async def get_pipeline(
        self,
        project_id: str,
        pipeline_id: int,
    ) -> ActionResult[Pipeline]:
        """Get pipeline details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/projects/{self._encode_project(project_id)}/pipelines/{pipeline_id}"
            )
            response.raise_for_status()
            p = response.json()

            return ActionResult.ok(Pipeline(
                id=p["id"],
                status=p.get("status", ""),
                ref=p.get("ref", ""),
                sha=p.get("sha", ""),
                web_url=p.get("web_url", ""),
                created_at=self._parse_datetime(p.get("created_at")),
                updated_at=self._parse_datetime(p.get("updated_at")),
                duration=p.get("duration"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting pipeline")
            return ActionResult.fail(str(e))

    async def trigger_pipeline(
        self,
        project_id: str,
        ref: str,
        variables: dict[str, str] | None = None,
    ) -> ActionResult[Pipeline]:
        """Trigger a new pipeline."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {"ref": ref}
            if variables:
                body["variables"] = [
                    {"key": k, "value": v} for k, v in variables.items()
                ]

            response = await self._client.post(
                f"/projects/{self._encode_project(project_id)}/pipeline",
                json=body,
            )
            response.raise_for_status()
            p = response.json()

            return ActionResult.ok(Pipeline(
                id=p["id"],
                status=p.get("status", ""),
                ref=p.get("ref", ""),
                sha=p.get("sha", ""),
                web_url=p.get("web_url", ""),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error triggering pipeline")
            return ActionResult.fail(str(e))

    async def cancel_pipeline(
        self,
        project_id: str,
        pipeline_id: int,
    ) -> ActionResult[bool]:
        """Cancel a running pipeline."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.post(
                f"/projects/{self._encode_project(project_id)}/pipelines/{pipeline_id}/cancel"
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error canceling pipeline")
            return ActionResult.fail(str(e))

    async def retry_pipeline(
        self,
        project_id: str,
        pipeline_id: int,
    ) -> ActionResult[Pipeline]:
        """Retry a failed pipeline."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.post(
                f"/projects/{self._encode_project(project_id)}/pipelines/{pipeline_id}/retry"
            )
            response.raise_for_status()
            p = response.json()

            return ActionResult.ok(Pipeline(
                id=p["id"],
                status=p.get("status", ""),
                ref=p.get("ref", ""),
                sha=p.get("sha", ""),
                web_url=p.get("web_url", ""),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error retrying pipeline")
            return ActionResult.fail(str(e))

    async def get_merge_requests(
        self,
        project_id: str,
        state: str = "opened",
    ) -> ActionResult[list[MergeRequest]]:
        """List merge requests."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/projects/{self._encode_project(project_id)}/merge_requests",
                params={"state": state, "per_page": 20},
            )
            response.raise_for_status()
            data = response.json()

            mrs = []
            for m in data:
                mrs.append(MergeRequest(
                    id=m["id"],
                    iid=m["iid"],
                    title=m.get("title", ""),
                    state=m.get("state", ""),
                    source_branch=m.get("source_branch", ""),
                    target_branch=m.get("target_branch", ""),
                    web_url=m.get("web_url", ""),
                    author=m.get("author", {}).get("username"),
                    created_at=self._parse_datetime(m.get("created_at")),
                ))
            return ActionResult.ok(mrs)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing merge requests")
            return ActionResult.fail(str(e))

    async def get_jobs(
        self,
        project_id: str,
        pipeline_id: int,
    ) -> ActionResult[list[Job]]:
        """List pipeline jobs."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/projects/{self._encode_project(project_id)}/pipelines/{pipeline_id}/jobs"
            )
            response.raise_for_status()
            data = response.json()

            jobs = []
            for j in data:
                jobs.append(Job(
                    id=j["id"],
                    name=j.get("name", ""),
                    status=j.get("status", ""),
                    stage=j.get("stage", ""),
                    web_url=j.get("web_url", ""),
                    duration=j.get("duration"),
                    created_at=self._parse_datetime(j.get("created_at")),
                    finished_at=self._parse_datetime(j.get("finished_at")),
                ))
            return ActionResult.ok(jobs)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing jobs")
            return ActionResult.fail(str(e))
