"""
GitHub Connector - Pull deployment and change information from GitHub.

This connector provides:
- Recent deployments
- PR/commit history
- Release information
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from autosre.foundation.connectors.base import BaseConnector
from autosre.foundation.models import ChangeEvent, ChangeType


class GitHubConnector(BaseConnector):
    """
    GitHub connector for tracking deployments and changes.
    
    Uses GitHub REST API to fetch:
    - Deployment events
    - Recent commits
    - Pull requests
    - Releases
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = "https://api.github.com"
    
    @property
    def name(self) -> str:
        return "github"
    
    async def connect(self) -> bool:
        """Connect to GitHub API."""
        try:
            token = self.config.get("token")
            if not token:
                self._last_error = "GitHub token not configured"
                return False
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
            
            # Test connection
            response = await self._client.get(f"{self._base_url}/user")
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                self._last_error = f"GitHub returned status {response.status_code}"
                return False
                
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from GitHub."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
    
    async def health_check(self) -> bool:
        """Check if GitHub API is accessible."""
        if not self._connected or not self._client:
            return False
        
        try:
            response = await self._client.get(f"{self._base_url}/rate_limit")
            return response.status_code == 200
        except Exception:
            return False
    
    async def sync(self, context_store: Any) -> int:
        """Sync recent changes from configured repositories."""
        if not self._connected:
            raise RuntimeError("Not connected to GitHub")
        
        count = 0
        repos = self.config.get("repositories", [])
        
        for repo in repos:
            # Sync deployments
            deployments = await self.get_deployments(repo)
            for deploy in deployments:
                context_store.add_change(deploy)
                count += 1
            
            # Sync recent commits on main/master
            commits = await self.get_recent_commits(repo)
            for commit in commits:
                context_store.add_change(commit)
                count += 1
        
        return count
    
    async def get_deployments(
        self,
        repo: str,
        environment: Optional[str] = None,
        limit: int = 20
    ) -> list[ChangeEvent]:
        """
        Get recent deployments for a repository.
        
        Args:
            repo: Repository in "owner/repo" format
            environment: Filter by environment (e.g., "production")
            limit: Maximum deployments to fetch
        """
        if not self._client:
            return []
        
        changes = []
        try:
            url = f"{self._base_url}/repos/{repo}/deployments"
            params = {"per_page": limit}
            if environment:
                params["environment"] = environment
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                self._last_error = f"Failed to get deployments: {response.status_code}"
                return []
            
            for deploy in response.json():
                # Get deployment status
                status_url = deploy.get("statuses_url")
                status = "unknown"
                if status_url:
                    status_resp = await self._client.get(status_url)
                    if status_resp.status_code == 200:
                        statuses = status_resp.json()
                        if statuses:
                            status = statuses[0].get("state", "unknown")
                
                # Extract service name from repo
                service_name = repo.split("/")[-1]
                
                change = ChangeEvent(
                    id=f"gh-deploy-{deploy['id']}",
                    change_type=ChangeType.DEPLOYMENT,
                    service_name=service_name,
                    description=f"Deployment to {deploy.get('environment', 'unknown')}: {deploy.get('description', '')}",
                    author=deploy.get("creator", {}).get("login", "unknown"),
                    commit_sha=deploy.get("sha"),
                    new_version=deploy.get("ref"),
                    timestamp=datetime.fromisoformat(deploy["created_at"].replace("Z", "+00:00")),
                    successful=status == "success",
                )
                changes.append(change)
                
        except Exception as e:
            self._last_error = f"Error getting deployments: {e}"
        
        return changes
    
    async def get_recent_commits(
        self,
        repo: str,
        branch: str = "main",
        since_hours: int = 24
    ) -> list[ChangeEvent]:
        """
        Get recent commits for a repository.
        
        Args:
            repo: Repository in "owner/repo" format
            branch: Branch to fetch commits from
            since_hours: Only get commits from last N hours
        """
        if not self._client:
            return []
        
        changes = []
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat() + "Z"
        
        try:
            # Try main first, fall back to master
            for try_branch in [branch, "master"]:
                url = f"{self._base_url}/repos/{repo}/commits"
                params = {"sha": try_branch, "since": since, "per_page": 30}
                
                response = await self._client.get(url, params=params)
                if response.status_code == 200:
                    break
            else:
                return []
            
            service_name = repo.split("/")[-1]
            
            for commit in response.json():
                commit_data = commit.get("commit", {})
                author = commit_data.get("author", {})
                
                change = ChangeEvent(
                    id=f"gh-commit-{commit['sha'][:8]}",
                    change_type=ChangeType.DEPLOYMENT,
                    service_name=service_name,
                    description=commit_data.get("message", "").split("\n")[0][:100],
                    author=author.get("name", "unknown"),
                    commit_sha=commit["sha"],
                    timestamp=datetime.fromisoformat(author.get("date", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")),
                )
                changes.append(change)
                
        except Exception as e:
            self._last_error = f"Error getting commits: {e}"
        
        return changes
    
    async def get_pull_requests(
        self,
        repo: str,
        state: str = "closed",
        limit: int = 20
    ) -> list[ChangeEvent]:
        """
        Get recent pull requests.
        
        Args:
            repo: Repository in "owner/repo" format
            state: PR state (open, closed, all)
            limit: Maximum PRs to fetch
        """
        if not self._client:
            return []
        
        changes = []
        try:
            url = f"{self._base_url}/repos/{repo}/pulls"
            params = {"state": state, "per_page": limit, "sort": "updated", "direction": "desc"}
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                return []
            
            service_name = repo.split("/")[-1]
            
            for pr in response.json():
                if not pr.get("merged_at"):
                    continue  # Only include merged PRs
                
                change = ChangeEvent(
                    id=f"gh-pr-{pr['number']}",
                    change_type=ChangeType.DEPLOYMENT,
                    service_name=service_name,
                    description=pr.get("title", ""),
                    author=pr.get("user", {}).get("login", "unknown"),
                    pr_number=pr["number"],
                    pr_url=pr.get("html_url"),
                    commit_sha=pr.get("merge_commit_sha"),
                    timestamp=datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00")),
                )
                changes.append(change)
                
        except Exception as e:
            self._last_error = f"Error getting PRs: {e}"
        
        return changes
    
    async def get_releases(self, repo: str, limit: int = 10) -> list[ChangeEvent]:
        """Get recent releases."""
        if not self._client:
            return []
        
        changes = []
        try:
            url = f"{self._base_url}/repos/{repo}/releases"
            params = {"per_page": limit}
            
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                return []
            
            service_name = repo.split("/")[-1]
            
            for release in response.json():
                change = ChangeEvent(
                    id=f"gh-release-{release['id']}",
                    change_type=ChangeType.DEPLOYMENT,
                    service_name=service_name,
                    description=f"Release {release.get('tag_name', '')}: {release.get('name', '')}",
                    author=release.get("author", {}).get("login", "unknown"),
                    new_version=release.get("tag_name"),
                    timestamp=datetime.fromisoformat(release["created_at"].replace("Z", "+00:00")),
                )
                changes.append(change)
                
        except Exception as e:
            self._last_error = f"Error getting releases: {e}"
        
        return changes
