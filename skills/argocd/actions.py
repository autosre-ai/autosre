"""ArgoCD skill actions."""

import asyncio
import os
import ssl
from datetime import datetime
from typing import Any, Optional

import aiohttp

from .models import (
    Application,
    ApplicationList,
    ApplicationHealth,
    ApplicationSource,
    ApplicationDestination,
    ResourceHealth,
    SyncResult,
    ArgoCDError,
)


class RateLimiter:
    """Rate limiter for ArgoCD API."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()


class ArgoCDSkill:
    """ArgoCD integration skill."""
    
    def __init__(
        self,
        server: Optional[str] = None,
        token: Optional[str] = None,
        insecure: Optional[bool] = None,
    ):
        self.server = (server or os.environ.get("ARGOCD_SERVER", "")).rstrip("/")
        self.token = token or os.environ.get("ARGOCD_TOKEN")
        self.insecure = insecure if insecure is not None else os.environ.get("ARGOCD_INSECURE", "").lower() == "true"
        
        if not self.server:
            raise ArgoCDError(400, "ARGOCD_SERVER not configured")
        if not self.token:
            raise ArgoCDError(401, "ARGOCD_TOKEN not configured")
        
        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            ssl_context = False if self.insecure else None
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                connector=connector,
            )
        return self._session
    
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make rate-limited API request."""
        await self.rate_limiter.acquire()
        
        session = await self._get_session()
        url = f"{self.server}/api/v1{path}"
        
        async with session.request(method, url, json=data, params=params) as resp:
            body = await resp.json() if resp.content_length else {}
            
            if not resp.ok:
                raise ArgoCDError(
                    code=resp.status,
                    message=body.get("message", resp.reason or "Unknown error"),
                )
            
            return body
    
    def _parse_application(self, data: dict[str, Any]) -> Application:
        """Parse application from API response."""
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})
        source = spec.get("source", {})
        destination = spec.get("destination", {})
        health = status.get("health", {})
        sync = status.get("sync", {})
        
        created_str = metadata.get("creationTimestamp")
        created_at = None
        if created_str:
            try:
                created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return Application(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "argocd"),
            project=spec.get("project", "default"),
            source=ApplicationSource(
                repo_url=source.get("repoURL", ""),
                path=source.get("path"),
                target_revision=source.get("targetRevision", "HEAD"),
                chart=source.get("chart"),
                helm=source.get("helm"),
            ),
            destination=ApplicationDestination(
                server=destination.get("server", ""),
                namespace=destination.get("namespace", ""),
            ),
            health_status=health.get("status", "Unknown"),
            sync_status=sync.get("status", "Unknown"),
            revision=sync.get("revision"),
            created_at=created_at,
        )
    
    async def list_applications(
        self,
        project: Optional[str] = None,
    ) -> ApplicationList:
        """List all applications.
        
        Args:
            project: Filter by project name
            
        Returns:
            List of applications
        """
        params = {}
        if project:
            params["project"] = project
        
        data = await self._request("GET", "/applications", params=params)
        
        items = [self._parse_application(app) for app in data.get("items", [])]
        
        return ApplicationList(items=items)
    
    async def get_application(self, name: str) -> Application:
        """Get application details.
        
        Args:
            name: Application name
            
        Returns:
            Application details
        """
        data = await self._request("GET", f"/applications/{name}")
        return self._parse_application(data)
    
    async def sync_application(
        self,
        name: str,
        revision: Optional[str] = None,
        prune: bool = False,
        dry_run: bool = False,
    ) -> SyncResult:
        """Trigger application sync.
        
        Args:
            name: Application name
            revision: Target revision (defaults to app's target)
            prune: Delete resources not in Git
            dry_run: Simulate sync without applying
            
        Returns:
            Sync result
        """
        payload: dict[str, Any] = {
            "prune": prune,
            "dryRun": dry_run,
        }
        
        if revision:
            payload["revision"] = revision
        
        data = await self._request(
            "POST",
            f"/applications/{name}/sync",
            data=payload,
        )
        
        status = data.get("status", {})
        operation_state = status.get("operationState", {})
        sync_result = operation_state.get("syncResult", {})
        
        started_str = operation_state.get("startedAt")
        finished_str = operation_state.get("finishedAt")
        
        return SyncResult(
            revision=sync_result.get("revision", revision or "HEAD"),
            phase=operation_state.get("phase", "Running"),
            message=operation_state.get("message"),
            resources=sync_result.get("resources", []),
            started_at=datetime.fromisoformat(started_str.replace("Z", "+00:00")) if started_str else None,
            finished_at=datetime.fromisoformat(finished_str.replace("Z", "+00:00")) if finished_str else None,
        )
    
    async def rollback_application(
        self,
        name: str,
        revision: int,
    ) -> SyncResult:
        """Rollback application to a specific revision.
        
        Args:
            name: Application name
            revision: Deployment revision number
            
        Returns:
            Sync result
        """
        data = await self._request(
            "POST",
            f"/applications/{name}/rollback",
            data={"id": revision},
        )
        
        status = data.get("status", {})
        operation_state = status.get("operationState", {})
        sync_result = operation_state.get("syncResult", {})
        
        return SyncResult(
            revision=sync_result.get("revision", str(revision)),
            phase=operation_state.get("phase", "Running"),
            message=operation_state.get("message"),
            resources=sync_result.get("resources", []),
        )
    
    async def get_application_health(self, name: str) -> ApplicationHealth:
        """Get application health status.
        
        Args:
            name: Application name
            
        Returns:
            Health status with resource details
        """
        data = await self._request("GET", f"/applications/{name}")
        
        status = data.get("status", {})
        health = status.get("health", {})
        resources = status.get("resources", [])
        
        resource_health = []
        for res in resources:
            res_health = res.get("health", {})
            if res_health:
                resource_health.append(ResourceHealth(
                    kind=res.get("kind", ""),
                    name=res.get("name", ""),
                    namespace=res.get("namespace"),
                    status=res_health.get("status", "Unknown"),
                    message=res_health.get("message"),
                ))
        
        return ApplicationHealth(
            status=health.get("status", "Unknown"),
            message=health.get("message"),
            resources=resource_health,
        )
    
    async def refresh_application(self, name: str) -> Application:
        """Refresh application state from cluster.
        
        Args:
            name: Application name
            
        Returns:
            Updated application
        """
        data = await self._request(
            "GET",
            f"/applications/{name}",
            params={"refresh": "normal"},
        )
        return self._parse_application(data)
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
