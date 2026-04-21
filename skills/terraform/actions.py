"""
Terraform Skill for OpenSRE

Terraform Cloud/Enterprise workspace and run management.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """Terraform workspace."""
    id: str
    name: str
    locked: bool
    auto_apply: bool
    terraform_version: str
    resource_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    current_run_id: str | None = None


@dataclass
class Run:
    """Terraform run."""
    id: str
    status: str
    message: str
    is_destroy: bool
    has_changes: bool
    created_at: datetime | None = None
    plan_only: bool = False
    auto_apply: bool = False


class TerraformSkill(Skill):
    """Skill for interacting with Terraform Cloud/Enterprise."""

    name = "terraform"
    version = "1.0.0"
    description = "Terraform Cloud/Enterprise workspace management"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "https://app.terraform.io").rstrip("/")
        self.token = self.config.get("token", "")
        self.organization = self.config.get("organization", "")
        self.timeout = self.config.get("timeout", 60)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("list_workspaces", self.list_workspaces, "List workspaces")
        self.register_action("get_workspace", self.get_workspace, "Get workspace")
        self.register_action("get_runs", self.get_runs, "List runs")
        self.register_action("get_run", self.get_run, "Get run")
        self.register_action("apply_run", self.apply_run, "Apply run", requires_approval=True)
        self.register_action("cancel_run", self.cancel_run, "Cancel run", requires_approval=True)
        self.register_action("lock_workspace", self.lock_workspace, "Lock workspace", requires_approval=True)
        self.register_action("unlock_workspace", self.unlock_workspace, "Unlock workspace", requires_approval=True)

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=f"{self.url}/api/v2",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/vnd.api+json",
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
        """Check Terraform Cloud connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/account/details")
            if response.status_code == 200:
                return ActionResult.ok({"status": "healthy"})
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    async def list_workspaces(
        self,
        search: str | None = None,
    ) -> ActionResult[list[Workspace]]:
        """List workspaces."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {"page[size]": 20}
            if search:
                params["search[name]"] = search

            response = await self._client.get(
                f"/organizations/{self.organization}/workspaces",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            workspaces = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                workspaces.append(Workspace(
                    id=item["id"],
                    name=attrs.get("name", ""),
                    locked=attrs.get("locked", False),
                    auto_apply=attrs.get("auto-apply", False),
                    terraform_version=attrs.get("terraform-version", ""),
                    resource_count=attrs.get("resource-count", 0),
                    created_at=self._parse_datetime(attrs.get("created-at")),
                    updated_at=self._parse_datetime(attrs.get("updated-at")),
                ))
            return ActionResult.ok(workspaces)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing workspaces")
            return ActionResult.fail(str(e))

    async def get_workspace(self, name: str) -> ActionResult[Workspace]:
        """Get workspace details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/organizations/{self.organization}/workspaces/{name}"
            )
            response.raise_for_status()
            item = response.json().get("data", {})
            attrs = item.get("attributes", {})

            return ActionResult.ok(Workspace(
                id=item["id"],
                name=attrs.get("name", ""),
                locked=attrs.get("locked", False),
                auto_apply=attrs.get("auto-apply", False),
                terraform_version=attrs.get("terraform-version", ""),
                resource_count=attrs.get("resource-count", 0),
                created_at=self._parse_datetime(attrs.get("created-at")),
                current_run_id=item.get("relationships", {}).get("current-run", {}).get("data", {}).get("id"),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting workspace")
            return ActionResult.fail(str(e))

    async def get_runs(
        self,
        workspace_name: str,
        status: str | None = None,
    ) -> ActionResult[list[Run]]:
        """List runs for a workspace."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            # First get workspace ID
            ws_result = await self.get_workspace(workspace_name)
            if not ws_result.success:
                return ActionResult.fail(ws_result.error or "Workspace not found")

            params: dict[str, Any] = {"page[size]": 20}
            if status:
                params["filter[status]"] = status

            response = await self._client.get(
                f"/workspaces/{ws_result.data.id}/runs",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            runs = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                runs.append(Run(
                    id=item["id"],
                    status=attrs.get("status", ""),
                    message=attrs.get("message", ""),
                    is_destroy=attrs.get("is-destroy", False),
                    has_changes=attrs.get("has-changes", False),
                    created_at=self._parse_datetime(attrs.get("created-at")),
                    plan_only=attrs.get("plan-only", False),
                    auto_apply=attrs.get("auto-apply", False),
                ))
            return ActionResult.ok(runs)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing runs")
            return ActionResult.fail(str(e))

    async def get_run(self, run_id: str) -> ActionResult[Run]:
        """Get run details."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(f"/runs/{run_id}")
            response.raise_for_status()
            item = response.json().get("data", {})
            attrs = item.get("attributes", {})

            return ActionResult.ok(Run(
                id=item["id"],
                status=attrs.get("status", ""),
                message=attrs.get("message", ""),
                is_destroy=attrs.get("is-destroy", False),
                has_changes=attrs.get("has-changes", False),
                created_at=self._parse_datetime(attrs.get("created-at")),
                plan_only=attrs.get("plan-only", False),
                auto_apply=attrs.get("auto-apply", False),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting run")
            return ActionResult.fail(str(e))

    async def apply_run(
        self,
        run_id: str,
        comment: str | None = None,
    ) -> ActionResult[bool]:
        """Apply a confirmed run."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {}
            if comment:
                body["comment"] = comment

            response = await self._client.post(
                f"/runs/{run_id}/actions/apply",
                json=body if body else None,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error applying run")
            return ActionResult.fail(str(e))

    async def cancel_run(
        self,
        run_id: str,
        comment: str | None = None,
    ) -> ActionResult[bool]:
        """Cancel a pending run."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {}
            if comment:
                body["comment"] = comment

            response = await self._client.post(
                f"/runs/{run_id}/actions/cancel",
                json=body if body else None,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error canceling run")
            return ActionResult.fail(str(e))

    async def lock_workspace(
        self,
        workspace_name: str,
        reason: str | None = None,
    ) -> ActionResult[bool]:
        """Lock a workspace."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            ws_result = await self.get_workspace(workspace_name)
            if not ws_result.success:
                return ActionResult.fail(ws_result.error or "Workspace not found")

            body: dict[str, Any] = {}
            if reason:
                body["reason"] = reason

            response = await self._client.post(
                f"/workspaces/{ws_result.data.id}/actions/lock",
                json=body if body else None,
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error locking workspace")
            return ActionResult.fail(str(e))

    async def unlock_workspace(
        self,
        workspace_name: str,
    ) -> ActionResult[bool]:
        """Unlock a workspace."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            ws_result = await self.get_workspace(workspace_name)
            if not ws_result.success:
                return ActionResult.fail(ws_result.error or "Workspace not found")

            response = await self._client.post(
                f"/workspaces/{ws_result.data.id}/actions/unlock"
            )
            response.raise_for_status()
            return ActionResult.ok(True)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error unlocking workspace")
            return ActionResult.fail(str(e))
