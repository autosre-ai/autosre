"""Terraform Integration for AutoSRE V2.

Provides Terraform Cloud/Enterprise integration:
- Workspace management
- Run tracking
- State access
- Plan/apply operations
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.integrations.base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class RunStatus(str, Enum):
    """Terraform run statuses."""
    
    PENDING = "pending"
    PLAN_QUEUED = "plan_queued"
    PLANNING = "planning"
    PLANNED = "planned"
    COST_ESTIMATING = "cost_estimating"
    COST_ESTIMATED = "cost_estimated"
    POLICY_CHECKING = "policy_checking"
    POLICY_OVERRIDE = "policy_override"
    POLICY_CHECKED = "policy_checked"
    CONFIRMED = "confirmed"
    APPLY_QUEUED = "apply_queued"
    APPLYING = "applying"
    APPLIED = "applied"
    DISCARDED = "discarded"
    ERRORED = "errored"
    CANCELED = "canceled"
    FORCE_CANCELED = "force_canceled"


class PlanAction(str, Enum):
    """Terraform plan actions."""
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_OP = "no-op"
    READ = "read"


class WorkspaceExecutionMode(str, Enum):
    """Workspace execution modes."""
    
    REMOTE = "remote"
    LOCAL = "local"
    AGENT = "agent"


@dataclass
class TerraformConfig:
    """Configuration for Terraform Cloud/Enterprise."""
    
    # API token
    token: str
    
    # Base URL
    base_url: str = "https://app.terraform.io"
    
    # Organization
    organization: str = ""
    
    # Timeouts
    timeout_seconds: float = 60.0


class TerraformOrganization(BaseModel):
    """Terraform organization model."""
    
    id: str
    name: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None


class TerraformWorkspace(BaseModel):
    """Terraform workspace model."""
    
    id: str
    name: str
    description: Optional[str] = None
    
    # Configuration
    auto_apply: bool = False
    execution_mode: WorkspaceExecutionMode = WorkspaceExecutionMode.REMOTE
    terraform_version: Optional[str] = None
    working_directory: Optional[str] = None
    
    # VCS
    vcs_repo: Optional[str] = None
    vcs_branch: Optional[str] = None
    
    # Status
    locked: bool = False
    locked_by: Optional[str] = None
    
    # Timing
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Stats
    resource_count: int = 0


class TerraformResource(BaseModel):
    """Resource in Terraform state."""
    
    type: str
    name: str
    module: Optional[str] = None
    provider: str
    
    # Current state
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Plan changes
    action: Optional[PlanAction] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    
    # Sensitivity
    sensitive: bool = False


class TerraformPlan(BaseModel):
    """Terraform plan model."""
    
    # Changes
    resource_additions: int = 0
    resource_changes: int = 0
    resource_destructions: int = 0
    
    # Resources
    resources: List[TerraformResource] = Field(default_factory=list)
    
    # Outputs
    output_changes: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    has_changes: bool = False


class TerraformRun(BaseModel):
    """Terraform run model."""
    
    id: str
    status: RunStatus = RunStatus.PENDING
    
    # Context
    workspace_id: str
    workspace_name: Optional[str] = None
    
    # Source
    source: str = "api"  # api, ui, vcs, etc.
    trigger_reason: Optional[str] = None
    
    # Configuration
    is_destroy: bool = False
    auto_apply: bool = False
    
    # Plan
    plan: Optional[TerraformPlan] = None
    
    # Timing
    created_at: Optional[datetime] = None
    status_timestamps: Dict[str, datetime] = Field(default_factory=dict)
    
    # Messages
    message: Optional[str] = None
    
    # URLs
    url: Optional[str] = None


class TerraformState(BaseModel):
    """Terraform state model."""
    
    version: int
    terraform_version: str
    serial: int
    
    # Resources
    resources: List[TerraformResource] = Field(default_factory=list)
    
    # Outputs
    outputs: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    created_at: Optional[datetime] = None


class TerraformIntegration(AuthenticatedIntegration):
    """
    Terraform Cloud/Enterprise integration.
    
    Provides comprehensive Terraform functionality:
    - Workspace management
    - Run tracking and triggering
    - State inspection
    - Plan/apply operations
    
    Example:
        config = TerraformConfig(
            token="your-api-token",
            organization="my-org",
        )
        
        async with TerraformIntegration(config) as tf:
            # List workspaces
            workspaces = await tf.list_workspaces()
            
            # Trigger a run
            run = await tf.create_run(
                workspace_name="production",
                message="Deploy new configuration",
            )
            
            # Wait for completion
            run = await tf.wait_for_run(run.id)
            
            # Get state
            state = await tf.get_state("production")
    """
    
    def __init__(self, config: TerraformConfig):
        """Initialize Terraform integration.
        
        Args:
            config: Terraform configuration
        """
        self.tf_config = config
        
        conn_config = ConnectionConfig(
            base_url=f"{config.base_url}/api/v2",
            timeout=config.timeout_seconds,
            headers={
                "Content-Type": "application/vnd.api+json",
            },
        )
        
        super().__init__(
            config=conn_config,
            auth_token=config.token,
        )
    
    @property
    def name(self) -> str:
        return "terraform"
    
    async def health_check(self) -> HealthCheckResult:
        """Check Terraform Cloud connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            await self._request("GET", "/account/details")
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Connected to Terraform Cloud",
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    # Organization Management
    
    async def get_organization(
        self,
        name: Optional[str] = None,
    ) -> TerraformOrganization:
        """Get organization details.
        
        Args:
            name: Organization name (defaults to configured)
            
        Returns:
            TerraformOrganization
        """
        org_name = name or self.tf_config.organization
        
        data = await self._request(
            "GET",
            f"/organizations/{org_name}",
        )
        
        attrs = data.get("data", {}).get("attributes", {})
        
        return TerraformOrganization(
            id=data.get("data", {}).get("id", ""),
            name=org_name,
            email=attrs.get("email"),
            created_at=datetime.fromisoformat(
                attrs["created-at"].replace("Z", "+00:00")
            ) if attrs.get("created-at") else None,
        )
    
    # Workspace Management
    
    async def list_workspaces(
        self,
        organization: Optional[str] = None,
        search: Optional[str] = None,
        page_size: int = 20,
        page_number: int = 1,
    ) -> List[TerraformWorkspace]:
        """List workspaces.
        
        Args:
            organization: Organization name
            search: Search filter
            page_size: Results per page
            page_number: Page number
            
        Returns:
            List of workspaces
        """
        org = organization or self.tf_config.organization
        
        params: Dict[str, Any] = {
            "page[size]": page_size,
            "page[number]": page_number,
        }
        
        if search:
            params["search[name]"] = search
        
        data = await self._request(
            "GET",
            f"/organizations/{org}/workspaces",
            params=params,
        )
        
        workspaces = []
        for ws in data.get("data", []):
            workspaces.append(self._parse_workspace(ws))
        
        return workspaces
    
    async def get_workspace(
        self,
        name: str,
        organization: Optional[str] = None,
    ) -> TerraformWorkspace:
        """Get workspace by name.
        
        Args:
            name: Workspace name
            organization: Organization name
            
        Returns:
            TerraformWorkspace
        """
        org = organization or self.tf_config.organization
        
        data = await self._request(
            "GET",
            f"/organizations/{org}/workspaces/{name}",
        )
        
        return self._parse_workspace(data.get("data", {}))
    
    async def get_workspace_by_id(self, workspace_id: str) -> TerraformWorkspace:
        """Get workspace by ID.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            TerraformWorkspace
        """
        data = await self._request(
            "GET",
            f"/workspaces/{workspace_id}",
        )
        
        return self._parse_workspace(data.get("data", {}))
    
    async def lock_workspace(
        self,
        workspace_id: str,
        reason: str = "Locked by AutoSRE",
    ) -> TerraformWorkspace:
        """Lock a workspace.
        
        Args:
            workspace_id: Workspace ID
            reason: Lock reason
            
        Returns:
            Updated workspace
        """
        data = await self._request(
            "POST",
            f"/workspaces/{workspace_id}/actions/lock",
            json={"reason": reason},
        )
        
        logger.info(
            "Locked Terraform workspace",
            workspace_id=workspace_id,
            reason=reason,
        )
        
        return self._parse_workspace(data.get("data", {}))
    
    async def unlock_workspace(
        self,
        workspace_id: str,
    ) -> TerraformWorkspace:
        """Unlock a workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Updated workspace
        """
        data = await self._request(
            "POST",
            f"/workspaces/{workspace_id}/actions/unlock",
        )
        
        logger.info(
            "Unlocked Terraform workspace",
            workspace_id=workspace_id,
        )
        
        return self._parse_workspace(data.get("data", {}))
    
    # Run Management
    
    async def list_runs(
        self,
        workspace_id: str,
        page_size: int = 20,
        page_number: int = 1,
    ) -> List[TerraformRun]:
        """List runs for a workspace.
        
        Args:
            workspace_id: Workspace ID
            page_size: Results per page
            page_number: Page number
            
        Returns:
            List of runs
        """
        data = await self._request(
            "GET",
            f"/workspaces/{workspace_id}/runs",
            params={
                "page[size]": page_size,
                "page[number]": page_number,
            },
        )
        
        runs = []
        for run in data.get("data", []):
            runs.append(self._parse_run(run))
        
        return runs
    
    async def get_run(self, run_id: str) -> TerraformRun:
        """Get run by ID.
        
        Args:
            run_id: Run ID
            
        Returns:
            TerraformRun
        """
        data = await self._request(
            "GET",
            f"/runs/{run_id}",
        )
        
        return self._parse_run(data.get("data", {}))
    
    async def create_run(
        self,
        workspace_name: str,
        organization: Optional[str] = None,
        message: Optional[str] = None,
        is_destroy: bool = False,
        auto_apply: bool = False,
        target_addrs: Optional[List[str]] = None,
        replace_addrs: Optional[List[str]] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> TerraformRun:
        """Create a new run.
        
        Args:
            workspace_name: Workspace name
            organization: Organization name
            message: Run message
            is_destroy: Is destroy run
            auto_apply: Auto-apply after plan
            target_addrs: Target resource addresses
            replace_addrs: Replace resource addresses
            variables: Terraform variables
            
        Returns:
            Created run
        """
        org = organization or self.tf_config.organization
        
        # Get workspace ID
        workspace = await self.get_workspace(workspace_name, org)
        
        payload = {
            "data": {
                "type": "runs",
                "attributes": {
                    "is-destroy": is_destroy,
                    "auto-apply": auto_apply,
                },
                "relationships": {
                    "workspace": {
                        "data": {
                            "type": "workspaces",
                            "id": workspace.id,
                        }
                    }
                }
            }
        }
        
        if message:
            payload["data"]["attributes"]["message"] = message
        if target_addrs:
            payload["data"]["attributes"]["target-addrs"] = target_addrs
        if replace_addrs:
            payload["data"]["attributes"]["replace-addrs"] = replace_addrs
        
        data = await self._request(
            "POST",
            "/runs",
            json=payload,
        )
        
        run = self._parse_run(data.get("data", {}))
        
        logger.info(
            "Created Terraform run",
            run_id=run.id,
            workspace=workspace_name,
            is_destroy=is_destroy,
        )
        
        return run
    
    async def apply_run(self, run_id: str, comment: Optional[str] = None) -> None:
        """Apply a planned run.
        
        Args:
            run_id: Run ID
            comment: Apply comment
        """
        payload = {}
        if comment:
            payload["comment"] = comment
        
        await self._request(
            "POST",
            f"/runs/{run_id}/actions/apply",
            json=payload if payload else None,
        )
        
        logger.info(
            "Applied Terraform run",
            run_id=run_id,
        )
    
    async def discard_run(self, run_id: str, comment: Optional[str] = None) -> None:
        """Discard a planned run.
        
        Args:
            run_id: Run ID
            comment: Discard comment
        """
        payload = {}
        if comment:
            payload["comment"] = comment
        
        await self._request(
            "POST",
            f"/runs/{run_id}/actions/discard",
            json=payload if payload else None,
        )
        
        logger.info(
            "Discarded Terraform run",
            run_id=run_id,
        )
    
    async def cancel_run(self, run_id: str, comment: Optional[str] = None) -> None:
        """Cancel a run.
        
        Args:
            run_id: Run ID
            comment: Cancel comment
        """
        payload = {}
        if comment:
            payload["comment"] = comment
        
        await self._request(
            "POST",
            f"/runs/{run_id}/actions/cancel",
            json=payload if payload else None,
        )
        
        logger.info(
            "Canceled Terraform run",
            run_id=run_id,
        )
    
    async def wait_for_run(
        self,
        run_id: str,
        target_statuses: Optional[List[RunStatus]] = None,
        timeout_seconds: float = 600.0,
        poll_interval: float = 10.0,
    ) -> TerraformRun:
        """Wait for a run to reach a status.
        
        Args:
            run_id: Run ID
            target_statuses: Statuses to wait for
            timeout_seconds: Maximum wait time
            poll_interval: Poll interval
            
        Returns:
            Run in target status
        """
        if target_statuses is None:
            target_statuses = [
                RunStatus.PLANNED,
                RunStatus.APPLIED,
                RunStatus.ERRORED,
                RunStatus.DISCARDED,
                RunStatus.CANCELED,
            ]
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            run = await self.get_run(run_id)
            
            if run.status in target_statuses:
                return run
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout_seconds:
                raise IntegrationError(
                    f"Run {run_id} did not reach target status within {timeout_seconds}s",
                    integration=self.name,
                )
            
            await asyncio.sleep(poll_interval)
    
    # State Management
    
    async def get_state(
        self,
        workspace_name: str,
        organization: Optional[str] = None,
    ) -> TerraformState:
        """Get current state for a workspace.
        
        Args:
            workspace_name: Workspace name
            organization: Organization name
            
        Returns:
            TerraformState
        """
        org = organization or self.tf_config.organization
        workspace = await self.get_workspace(workspace_name, org)
        
        data = await self._request(
            "GET",
            f"/workspaces/{workspace.id}/current-state-version",
        )
        
        state_data = data.get("data", {})
        attrs = state_data.get("attributes", {})
        
        # Get the actual state JSON
        state_url = attrs.get("hosted-state-download-url")
        
        state = TerraformState(
            version=4,  # Terraform state version
            terraform_version=attrs.get("terraform-version", ""),
            serial=attrs.get("serial", 0),
            created_at=datetime.fromisoformat(
                attrs["created-at"].replace("Z", "+00:00")
            ) if attrs.get("created-at") else None,
        )
        
        # Optionally fetch full state
        if state_url:
            try:
                client = await self._get_client()
                response = await client.get(state_url)
                state_json = response.json()
                
                # Parse resources
                for resource in state_json.get("resources", []):
                    for instance in resource.get("instances", []):
                        state.resources.append(TerraformResource(
                            type=resource.get("type", ""),
                            name=resource.get("name", ""),
                            module=resource.get("module"),
                            provider=resource.get("provider", ""),
                            attributes=instance.get("attributes", {}),
                        ))
                
                state.outputs = state_json.get("outputs", {})
            except Exception as e:
                logger.warning(
                    "Failed to fetch full state",
                    error=str(e),
                )
        
        return state
    
    async def get_resources(
        self,
        workspace_name: str,
        organization: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> List[TerraformResource]:
        """Get resources from state.
        
        Args:
            workspace_name: Workspace name
            organization: Organization name
            resource_type: Filter by resource type
            
        Returns:
            List of resources
        """
        state = await self.get_state(workspace_name, organization)
        
        resources = state.resources
        
        if resource_type:
            resources = [r for r in resources if r.type == resource_type]
        
        return resources
    
    def _parse_workspace(self, data: Dict[str, Any]) -> TerraformWorkspace:
        """Parse workspace data."""
        attrs = data.get("attributes", {})
        
        return TerraformWorkspace(
            id=data.get("id", ""),
            name=attrs.get("name", ""),
            description=attrs.get("description"),
            auto_apply=attrs.get("auto-apply", False),
            execution_mode=WorkspaceExecutionMode(attrs.get("execution-mode", "remote")),
            terraform_version=attrs.get("terraform-version"),
            working_directory=attrs.get("working-directory"),
            locked=attrs.get("locked", False),
            resource_count=attrs.get("resource-count", 0),
            created_at=datetime.fromisoformat(
                attrs["created-at"].replace("Z", "+00:00")
            ) if attrs.get("created-at") else None,
            updated_at=datetime.fromisoformat(
                attrs["updated-at"].replace("Z", "+00:00")
            ) if attrs.get("updated-at") else None,
        )
    
    def _parse_run(self, data: Dict[str, Any]) -> TerraformRun:
        """Parse run data."""
        attrs = data.get("attributes", {})
        
        return TerraformRun(
            id=data.get("id", ""),
            status=RunStatus(attrs.get("status", "pending")),
            workspace_id=data.get("relationships", {}).get("workspace", {}).get("data", {}).get("id", ""),
            source=attrs.get("source", "api"),
            trigger_reason=attrs.get("trigger-reason"),
            is_destroy=attrs.get("is-destroy", False),
            auto_apply=attrs.get("auto-apply", False),
            message=attrs.get("message"),
            created_at=datetime.fromisoformat(
                attrs["created-at"].replace("Z", "+00:00")
            ) if attrs.get("created-at") else None,
        )
