"""
ArgoCD Integration for AutoSRE

Provides comprehensive ArgoCD integration for GitOps-driven incident response:
- Application management and monitoring
- Sync operations and rollback capabilities
- Health status tracking and alerting
- ApplicationSet and Rollout support
- Webhook event handling for incident triggers
"""

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

import httpx
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """ArgoCD application health status."""
    
    HEALTHY = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED = "Degraded"
    SUSPENDED = "Suspended"
    MISSING = "Missing"
    UNKNOWN = "Unknown"


class SyncStatus(str, Enum):
    """ArgoCD application sync status."""
    
    SYNCED = "Synced"
    OUT_OF_SYNC = "OutOfSync"
    UNKNOWN = "Unknown"


class SyncStrategy(str, Enum):
    """Sync strategy for ArgoCD applications."""
    
    APPLY = "apply"
    HOOK = "hook"
    FORCE = "force"


class ArgoCDEventType(str, Enum):
    """ArgoCD webhook event types."""
    
    APP_CREATED = "app.created"
    APP_UPDATED = "app.updated"
    APP_DELETED = "app.deleted"
    APP_SYNCED = "app.synced"
    APP_SYNC_FAILED = "app.sync.failed"
    APP_HEALTH_DEGRADED = "app.health.degraded"
    APP_HEALTH_HEALTHY = "app.health.healthy"
    APP_OUT_OF_SYNC = "app.out_of_sync"
    RESOURCE_CREATED = "resource.created"
    RESOURCE_UPDATED = "resource.updated"
    RESOURCE_DELETED = "resource.deleted"


class ArgoCDConfig(BaseModel):
    """Configuration for ArgoCD client."""
    
    server_url: str = Field(..., description="ArgoCD server URL")
    auth_token: Optional[str] = Field(None, description="ArgoCD API token")
    username: Optional[str] = Field(None, description="ArgoCD username")
    password: Optional[str] = Field(None, description="ArgoCD password")
    insecure: bool = Field(False, description="Skip TLS verification")
    timeout: int = Field(30, description="Request timeout in seconds")
    grpc_web: bool = Field(True, description="Use gRPC-Web for API calls")


class ApplicationSource(BaseModel):
    """ArgoCD application source configuration."""
    
    repo_url: str = Field(..., description="Git repository URL")
    path: str = Field(default=".", description="Path within repository")
    target_revision: str = Field(default="HEAD", description="Git revision (branch, tag, commit)")
    
    # Helm configuration
    helm: Optional[dict[str, Any]] = Field(None, description="Helm parameters")
    
    # Kustomize configuration
    kustomize: Optional[dict[str, Any]] = Field(None, description="Kustomize parameters")
    
    # Directory configuration
    directory: Optional[dict[str, Any]] = Field(None, description="Directory parameters")
    
    # Plugin configuration
    plugin: Optional[dict[str, Any]] = Field(None, description="Plugin configuration")


class ApplicationDestination(BaseModel):
    """ArgoCD application destination configuration."""
    
    server: str = Field(default="https://kubernetes.default.svc", description="Kubernetes API server")
    namespace: str = Field(..., description="Target namespace")
    name: Optional[str] = Field(None, description="Cluster name (alternative to server)")


class SyncPolicy(BaseModel):
    """ArgoCD sync policy configuration."""
    
    automated: Optional[dict[str, bool]] = Field(
        None, description="Automated sync settings (prune, selfHeal, allowEmpty)"
    )
    sync_options: list[str] = Field(
        default_factory=list, description="Sync options (CreateNamespace, PruneLast, etc.)"
    )
    retry: Optional[dict[str, Any]] = Field(None, description="Retry configuration")
    
    @classmethod
    def auto_sync(
        cls,
        prune: bool = True,
        self_heal: bool = True,
        allow_empty: bool = False,
    ) -> "SyncPolicy":
        """Create an auto-sync policy."""
        return cls(
            automated={
                "prune": prune,
                "selfHeal": self_heal,
                "allowEmpty": allow_empty,
            },
            sync_options=["CreateNamespace=true"],
        )


class ResourceHealth(BaseModel):
    """Health status of a Kubernetes resource."""
    
    status: HealthStatus = HealthStatus.UNKNOWN
    message: Optional[str] = None


class ResourceStatus(BaseModel):
    """Status of a managed resource in ArgoCD."""
    
    group: str = ""
    version: str = "v1"
    kind: str
    namespace: str
    name: str
    status: SyncStatus = SyncStatus.UNKNOWN
    health: Optional[ResourceHealth] = None
    requires_pruning: bool = False
    hook: bool = False


class ApplicationStatus(BaseModel):
    """ArgoCD application status."""
    
    health: HealthStatus = HealthStatus.UNKNOWN
    sync: SyncStatus = SyncStatus.UNKNOWN
    
    # Detailed status
    health_message: Optional[str] = None
    sync_revision: Optional[str] = None
    sync_compared_to_revision: Optional[str] = None
    
    # Operation status
    operation_state: Optional[dict[str, Any]] = None
    
    # Resource statuses
    resources: list[ResourceStatus] = Field(default_factory=list)
    
    # Conditions
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    
    # Timestamps
    reconciledAt: Optional[datetime] = None
    observedAt: Optional[datetime] = None
    
    def is_healthy(self) -> bool:
        """Check if application is healthy."""
        return self.health == HealthStatus.HEALTHY
    
    def is_synced(self) -> bool:
        """Check if application is synced."""
        return self.sync == SyncStatus.SYNCED
    
    def is_ready(self) -> bool:
        """Check if application is both healthy and synced."""
        return self.is_healthy() and self.is_synced()
    
    def get_unhealthy_resources(self) -> list[ResourceStatus]:
        """Get list of unhealthy resources."""
        return [
            r for r in self.resources
            if r.health and r.health.status not in [HealthStatus.HEALTHY, HealthStatus.PROGRESSING]
        ]
    
    def get_out_of_sync_resources(self) -> list[ResourceStatus]:
        """Get list of out-of-sync resources."""
        return [r for r in self.resources if r.status == SyncStatus.OUT_OF_SYNC]


class Application(BaseModel):
    """ArgoCD Application resource."""
    
    name: str = Field(..., description="Application name")
    namespace: str = Field(default="argocd", description="ArgoCD namespace")
    project: str = Field(default="default", description="ArgoCD project")
    
    source: ApplicationSource
    destination: ApplicationDestination
    
    sync_policy: Optional[SyncPolicy] = None
    
    # Status (populated from cluster)
    status: Optional[ApplicationStatus] = None
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    finalizers: list[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_manifest(self) -> dict[str, Any]:
        """Convert to Kubernetes Application manifest."""
        manifest: dict[str, Any] = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": {
                "project": self.project,
                "source": {
                    "repoURL": self.source.repo_url,
                    "path": self.source.path,
                    "targetRevision": self.source.target_revision,
                },
                "destination": {
                    "namespace": self.destination.namespace,
                },
            },
        }
        
        # Add server or name to destination
        if self.destination.name:
            manifest["spec"]["destination"]["name"] = self.destination.name
        else:
            manifest["spec"]["destination"]["server"] = self.destination.server
        
        # Add source-specific config
        if self.source.helm:
            manifest["spec"]["source"]["helm"] = self.source.helm
        if self.source.kustomize:
            manifest["spec"]["source"]["kustomize"] = self.source.kustomize
        if self.source.directory:
            manifest["spec"]["source"]["directory"] = self.source.directory
        
        # Add sync policy
        if self.sync_policy:
            manifest["spec"]["syncPolicy"] = {}
            if self.sync_policy.automated:
                manifest["spec"]["syncPolicy"]["automated"] = self.sync_policy.automated
            if self.sync_policy.sync_options:
                manifest["spec"]["syncPolicy"]["syncOptions"] = self.sync_policy.sync_options
            if self.sync_policy.retry:
                manifest["spec"]["syncPolicy"]["retry"] = self.sync_policy.retry
        
        return manifest


@dataclass
class SyncOperationResult:
    """Result of a sync operation."""
    
    success: bool
    message: str
    revision: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    resources_synced: list[str] = field(default_factory=list)
    resources_failed: list[str] = field(default_factory=list)
    sync_result: Optional[dict[str, Any]] = None


class SyncOperation(BaseModel):
    """ArgoCD sync operation configuration."""
    
    revision: Optional[str] = Field(None, description="Target revision to sync")
    prune: bool = Field(False, description="Prune resources not in Git")
    dry_run: bool = Field(False, description="Dry run mode")
    strategy: SyncStrategy = Field(SyncStrategy.APPLY, description="Sync strategy")
    resources: Optional[list[dict[str, str]]] = Field(
        None, description="Specific resources to sync"
    )
    retry: bool = Field(True, description="Retry on failure")
    force: bool = Field(False, description="Force sync (delete and recreate)")
    
    def to_api_payload(self) -> dict[str, Any]:
        """Convert to ArgoCD API payload."""
        payload: dict[str, Any] = {
            "prune": self.prune,
            "dryRun": self.dry_run,
            "strategy": {
                "apply": {"force": self.force},
            },
        }
        
        if self.revision:
            payload["revision"] = self.revision
        
        if self.resources:
            payload["resources"] = self.resources
        
        if self.strategy == SyncStrategy.HOOK:
            payload["strategy"] = {"hook": {}}
        
        return payload


class ApplicationSetGenerator(BaseModel):
    """ApplicationSet generator configuration."""
    
    generator_type: str = Field(..., description="Generator type (list, cluster, git, etc.)")
    config: dict[str, Any] = Field(default_factory=dict, description="Generator configuration")


class ApplicationSet(BaseModel):
    """ArgoCD ApplicationSet resource."""
    
    name: str = Field(..., description="ApplicationSet name")
    namespace: str = Field(default="argocd", description="ArgoCD namespace")
    
    generators: list[ApplicationSetGenerator] = Field(
        default_factory=list, description="ApplicationSet generators"
    )
    template: dict[str, Any] = Field(..., description="Application template")
    
    sync_policy: Optional[dict[str, Any]] = None
    
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    
    def to_manifest(self) -> dict[str, Any]:
        """Convert to Kubernetes ApplicationSet manifest."""
        generators = []
        for gen in self.generators:
            generators.append({gen.generator_type: gen.config})
        
        return {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "ApplicationSet",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": {
                "generators": generators,
                "template": self.template,
                "syncPolicy": self.sync_policy or {},
            },
        }


class RolloutStrategy(str, Enum):
    """Argo Rollouts deployment strategy."""
    
    CANARY = "canary"
    BLUE_GREEN = "blueGreen"


class Rollout(BaseModel):
    """Argo Rollouts resource for progressive delivery."""
    
    name: str
    namespace: str
    
    strategy: RolloutStrategy
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    
    replicas: int = 1
    selector: dict[str, str] = Field(default_factory=dict)
    template: dict[str, Any] = Field(default_factory=dict)
    
    # Status
    current_step: Optional[int] = None
    current_step_index: Optional[int] = None
    phase: Optional[str] = None
    
    def to_manifest(self) -> dict[str, Any]:
        """Convert to Kubernetes Rollout manifest."""
        return {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Rollout",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
            },
            "spec": {
                "replicas": self.replicas,
                "selector": {"matchLabels": self.selector},
                "template": self.template,
                "strategy": {
                    self.strategy.value: self.strategy_config,
                },
            },
        }


@dataclass
class ArgoCDWebhook:
    """ArgoCD webhook event data."""
    
    event_type: ArgoCDEventType
    application_name: str
    application_namespace: str = "argocd"
    project: str = "default"
    
    # Event details
    health_status: Optional[HealthStatus] = None
    sync_status: Optional[SyncStatus] = None
    revision: Optional[str] = None
    
    # Resource info (for resource events)
    resource_kind: Optional[str] = None
    resource_name: Optional[str] = None
    resource_namespace: Optional[str] = None
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Raw event data
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_incident_context(self) -> dict[str, Any]:
        """Convert to incident context for AutoSRE integration."""
        return {
            "source": "argocd",
            "event_type": self.event_type.value,
            "application": self.application_name,
            "namespace": self.application_namespace,
            "project": self.project,
            "health_status": self.health_status.value if self.health_status else None,
            "sync_status": self.sync_status.value if self.sync_status else None,
            "revision": self.revision,
            "timestamp": self.timestamp.isoformat(),
        }


class ArgoCDClient:
    """ArgoCD API client for GitOps operations.
    
    Provides comprehensive ArgoCD integration for:
    - Application CRUD operations
    - Sync and rollback operations
    - Health and sync status monitoring
    - ApplicationSet management
    - Webhook event processing
    """
    
    def __init__(self, config: ArgoCDConfig):
        """Initialize ArgoCD client.
        
        Args:
            config: ArgoCD connection configuration
        """
        self.config = config
        self._token: Optional[str] = config.auth_token
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.server_url,
                verify=not self.config.insecure,
                timeout=self.config.timeout,
            )
        return self._client
    
    async def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self.config.username and self.config.password:
            # Authenticate and get token
            self._token = await self._authenticate()
            headers["Authorization"] = f"Bearer {self._token}"
        
        return headers
    
    async def _authenticate(self) -> str:
        """Authenticate with ArgoCD and get session token."""
        client = await self._get_client()
        response = await client.post(
            "/api/v1/session",
            json={
                "username": self.config.username,
                "password": self.config.password,
            },
        )
        response.raise_for_status()
        return response.json()["token"]
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # Application Operations
    
    async def list_applications(
        self,
        project: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> list[Application]:
        """List ArgoCD applications.
        
        Args:
            project: Filter by project name
            selector: Label selector
            
        Returns:
            List of applications
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        params = {}
        if project:
            params["project"] = project
        if selector:
            params["selector"] = selector
        
        response = await client.get(
            "/api/v1/applications",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        
        applications = []
        for item in response.json().get("items", []):
            app = self._parse_application(item)
            applications.append(app)
        
        return applications
    
    async def get_application(self, name: str, namespace: str = "argocd") -> Application:
        """Get a specific ArgoCD application.
        
        Args:
            name: Application name
            namespace: ArgoCD namespace
            
        Returns:
            Application details
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.get(
            f"/api/v1/applications/{name}",
            headers=headers,
            params={"appNamespace": namespace},
        )
        response.raise_for_status()
        
        return self._parse_application(response.json())
    
    async def create_application(self, app: Application) -> Application:
        """Create a new ArgoCD application.
        
        Args:
            app: Application to create
            
        Returns:
            Created application
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.post(
            "/api/v1/applications",
            headers=headers,
            json=app.to_manifest(),
        )
        response.raise_for_status()
        
        return self._parse_application(response.json())
    
    async def update_application(self, app: Application) -> Application:
        """Update an existing ArgoCD application.
        
        Args:
            app: Application with updates
            
        Returns:
            Updated application
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.put(
            f"/api/v1/applications/{app.name}",
            headers=headers,
            json=app.to_manifest(),
        )
        response.raise_for_status()
        
        return self._parse_application(response.json())
    
    async def delete_application(
        self,
        name: str,
        cascade: bool = True,
        propagation_policy: str = "foreground",
    ) -> bool:
        """Delete an ArgoCD application.
        
        Args:
            name: Application name
            cascade: Delete resources managed by the application
            propagation_policy: Kubernetes deletion propagation policy
            
        Returns:
            True if deleted successfully
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.delete(
            f"/api/v1/applications/{name}",
            headers=headers,
            params={
                "cascade": cascade,
                "propagationPolicy": propagation_policy,
            },
        )
        response.raise_for_status()
        return True
    
    # Sync Operations
    
    async def sync_application(
        self,
        name: str,
        operation: Optional[SyncOperation] = None,
    ) -> SyncOperationResult:
        """Sync an ArgoCD application.
        
        Args:
            name: Application name
            operation: Sync operation configuration
            
        Returns:
            Sync operation result
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        payload = operation.to_api_payload() if operation else {}
        
        response = await client.post(
            f"/api/v1/applications/{name}/sync",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        
        data = response.json()
        return SyncOperationResult(
            success=True,
            message="Sync initiated",
            revision=data.get("spec", {}).get("source", {}).get("targetRevision"),
            started_at=datetime.utcnow(),
        )
    
    async def rollback_application(
        self,
        name: str,
        revision_id: int,
        prune: bool = True,
    ) -> SyncOperationResult:
        """Rollback an application to a previous revision.
        
        Args:
            name: Application name
            revision_id: History revision ID to rollback to
            prune: Prune resources not in the target revision
            
        Returns:
            Rollback operation result
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.post(
            f"/api/v1/applications/{name}/rollback",
            headers=headers,
            json={
                "id": revision_id,
                "prune": prune,
            },
        )
        response.raise_for_status()
        
        return SyncOperationResult(
            success=True,
            message=f"Rollback to revision {revision_id} initiated",
            started_at=datetime.utcnow(),
        )
    
    async def terminate_operation(self, name: str) -> bool:
        """Terminate a running sync operation.
        
        Args:
            name: Application name
            
        Returns:
            True if terminated successfully
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.delete(
            f"/api/v1/applications/{name}/operation",
            headers=headers,
        )
        response.raise_for_status()
        return True
    
    async def refresh_application(
        self,
        name: str,
        hard: bool = False,
    ) -> Application:
        """Refresh application state from Git.
        
        Args:
            name: Application name
            hard: Perform hard refresh (invalidate cache)
            
        Returns:
            Refreshed application
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        refresh_type = "hard" if hard else "normal"
        
        response = await client.get(
            f"/api/v1/applications/{name}",
            headers=headers,
            params={"refresh": refresh_type},
        )
        response.raise_for_status()
        
        return self._parse_application(response.json())
    
    # History Operations
    
    async def get_application_history(
        self,
        name: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get application deployment history.
        
        Args:
            name: Application name
            limit: Maximum history entries to return
            
        Returns:
            List of history entries
        """
        app = await self.get_application(name)
        # History is part of the application status
        history = app.status.operation_state if app.status else {}
        return history.get("history", [])[:limit] if history else []
    
    # Health Monitoring
    
    async def get_health_status(self, name: str) -> ApplicationStatus:
        """Get application health status.
        
        Args:
            name: Application name
            
        Returns:
            Application status with health info
        """
        app = await self.get_application(name)
        return app.status or ApplicationStatus()
    
    async def wait_for_health(
        self,
        name: str,
        target_health: HealthStatus = HealthStatus.HEALTHY,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> ApplicationStatus:
        """Wait for application to reach target health status.
        
        Args:
            name: Application name
            target_health: Target health status to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Final application status
            
        Raises:
            TimeoutError: If target health not reached within timeout
        """
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            status = await self.get_health_status(name)
            
            if status.health == target_health:
                return status
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(
            f"Application {name} did not reach {target_health.value} within {timeout}s"
        )
    
    async def wait_for_sync(
        self,
        name: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> ApplicationStatus:
        """Wait for application to be synced.
        
        Args:
            name: Application name
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Final application status
        """
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            status = await self.get_health_status(name)
            
            if status.is_synced():
                return status
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(
            f"Application {name} did not sync within {timeout}s"
        )
    
    # Resource Operations
    
    async def get_resource_tree(self, name: str) -> dict[str, Any]:
        """Get application resource tree.
        
        Args:
            name: Application name
            
        Returns:
            Resource tree structure
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.get(
            f"/api/v1/applications/{name}/resource-tree",
            headers=headers,
        )
        response.raise_for_status()
        
        return response.json()
    
    async def get_managed_resources(self, name: str) -> list[ResourceStatus]:
        """Get list of resources managed by application.
        
        Args:
            name: Application name
            
        Returns:
            List of managed resources with status
        """
        client = await self._get_client()
        headers = await self._get_headers()
        
        response = await client.get(
            f"/api/v1/applications/{name}/managed-resources",
            headers=headers,
        )
        response.raise_for_status()
        
        resources = []
        for item in response.json().get("items", []):
            resources.append(ResourceStatus(
                group=item.get("group", ""),
                version=item.get("version", "v1"),
                kind=item.get("kind", ""),
                namespace=item.get("namespace", ""),
                name=item.get("name", ""),
                status=SyncStatus(item.get("status", "Unknown")),
            ))
        
        return resources
    
    # Helpers
    
    def _parse_application(self, data: dict[str, Any]) -> Application:
        """Parse application from API response."""
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status_data = data.get("status", {})
        
        source = spec.get("source", {})
        destination = spec.get("destination", {})
        
        # Parse status
        status = ApplicationStatus(
            health=HealthStatus(status_data.get("health", {}).get("status", "Unknown")),
            sync=SyncStatus(status_data.get("sync", {}).get("status", "Unknown")),
            health_message=status_data.get("health", {}).get("message"),
            sync_revision=status_data.get("sync", {}).get("revision"),
            operation_state=status_data.get("operationState"),
            conditions=status_data.get("conditions", []),
        )
        
        # Parse resources
        for res in status_data.get("resources", []):
            health = None
            if "health" in res:
                health = ResourceHealth(
                    status=HealthStatus(res["health"].get("status", "Unknown")),
                    message=res["health"].get("message"),
                )
            
            status.resources.append(ResourceStatus(
                group=res.get("group", ""),
                version=res.get("version", "v1"),
                kind=res.get("kind", ""),
                namespace=res.get("namespace", ""),
                name=res.get("name", ""),
                status=SyncStatus(res.get("status", "Unknown")),
                health=health,
            ))
        
        return Application(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "argocd"),
            project=spec.get("project", "default"),
            source=ApplicationSource(
                repo_url=source.get("repoURL", ""),
                path=source.get("path", "."),
                target_revision=source.get("targetRevision", "HEAD"),
                helm=source.get("helm"),
                kustomize=source.get("kustomize"),
                directory=source.get("directory"),
            ),
            destination=ApplicationDestination(
                server=destination.get("server", "https://kubernetes.default.svc"),
                namespace=destination.get("namespace", "default"),
                name=destination.get("name"),
            ),
            status=status,
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
        )
    
    # Incident Response Integration
    
    async def handle_degraded_application(
        self,
        name: str,
        auto_rollback: bool = False,
        rollback_to_healthy: bool = True,
    ) -> dict[str, Any]:
        """Handle a degraded application for incident response.
        
        Args:
            name: Application name
            auto_rollback: Automatically rollback if unhealthy
            rollback_to_healthy: Find last healthy revision to rollback to
            
        Returns:
            Incident response context
        """
        app = await self.get_application(name)
        status = app.status or ApplicationStatus()
        
        response: dict[str, Any] = {
            "application": name,
            "health_status": status.health.value,
            "sync_status": status.sync.value,
            "unhealthy_resources": [
                {"kind": r.kind, "name": r.name, "namespace": r.namespace}
                for r in status.get_unhealthy_resources()
            ],
            "out_of_sync_resources": [
                {"kind": r.kind, "name": r.name, "namespace": r.namespace}
                for r in status.get_out_of_sync_resources()
            ],
            "action_taken": None,
        }
        
        if auto_rollback and status.health == HealthStatus.DEGRADED:
            # Get history and find last healthy revision
            history = await self.get_application_history(name)
            
            if history and rollback_to_healthy:
                # Find last successful deployment
                for entry in history:
                    if entry.get("deployedAt"):
                        rollback_result = await self.rollback_application(
                            name, entry.get("id", 0)
                        )
                        response["action_taken"] = {
                            "type": "rollback",
                            "revision_id": entry.get("id"),
                            "result": rollback_result.success,
                        }
                        break
        
        return response
    
    def parse_webhook_event(self, payload: dict[str, Any]) -> ArgoCDWebhook:
        """Parse incoming ArgoCD webhook event.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Parsed webhook event
        """
        event_type_str = payload.get("type", "app.updated")
        
        try:
            event_type = ArgoCDEventType(event_type_str)
        except ValueError:
            event_type = ArgoCDEventType.APP_UPDATED
        
        app_data = payload.get("application", {})
        metadata = app_data.get("metadata", {})
        status = app_data.get("status", {})
        
        health_status = None
        if "health" in status:
            try:
                health_status = HealthStatus(status["health"].get("status", "Unknown"))
            except ValueError:
                health_status = HealthStatus.UNKNOWN
        
        sync_status = None
        if "sync" in status:
            try:
                sync_status = SyncStatus(status["sync"].get("status", "Unknown"))
            except ValueError:
                sync_status = SyncStatus.UNKNOWN
        
        return ArgoCDWebhook(
            event_type=event_type,
            application_name=metadata.get("name", ""),
            application_namespace=metadata.get("namespace", "argocd"),
            project=app_data.get("spec", {}).get("project", "default"),
            health_status=health_status,
            sync_status=sync_status,
            revision=status.get("sync", {}).get("revision"),
            raw_data=payload,
        )
