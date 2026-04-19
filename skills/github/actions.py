"""GitHub skill actions."""

import asyncio
import os
from datetime import datetime
from typing import Any, Optional

import aiohttp

from .models import (
    GitHubIssue,
    GitHubComment,
    GitHubCommit,
    GitHubCommitAuthor,
    GitHubWorkflowRun,
    GitHubWorkflowRunList,
    GitHubUser,
    GitHubLabel,
    GitHubError,
)


class RateLimiter:
    """Rate limiter for GitHub API (5000 req/hour)."""
    
    def __init__(self, calls_per_hour: int = 5000):
        self.calls_per_hour = calls_per_hour
        self.interval = 3600.0 / calls_per_hour
        self.last_call = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()


class GitHubSkill:
    """GitHub integration skill."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(
        self,
        token: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.api_url = (api_url or os.environ.get("GITHUB_API_URL", self.BASE_URL)).rstrip("/")
        
        if not self.token:
            raise GitHubError(401, "GITHUB_TOKEN not configured")
        
        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
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
        url = f"{self.api_url}{path}"
        
        async with session.request(method, url, json=data, params=params) as resp:
            # Handle rate limiting
            if resp.status == 403:
                remaining = resp.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = int(resp.headers.get("X-RateLimit-Reset", "0"))
                    wait = max(0, reset_time - int(datetime.now().timestamp()))
                    raise GitHubError(429, f"Rate limited. Reset in {wait}s")
            
            body = await resp.json() if resp.content_length else {}
            
            if not resp.ok:
                raise GitHubError(
                    status=resp.status,
                    message=body.get("message", resp.reason or "Unknown error"),
                    documentation_url=body.get("documentation_url"),
                )
            
            return body
    
    def _parse_user(self, data: dict[str, Any]) -> GitHubUser:
        """Parse user from API response."""
        return GitHubUser(
            id=data["id"],
            login=data["login"],
            avatar_url=data.get("avatar_url"),
            html_url=data.get("html_url"),
        )
    
    def _parse_issue(self, data: dict[str, Any]) -> GitHubIssue:
        """Parse issue from API response."""
        return GitHubIssue(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            user=self._parse_user(data["user"]),
            labels=[
                GitHubLabel(
                    id=label["id"],
                    name=label["name"],
                    color=label["color"],
                    description=label.get("description"),
                )
                for label in data.get("labels", [])
            ],
            assignees=[self._parse_user(u) for u in data.get("assignees", [])],
            html_url=data["html_url"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            closed_at=datetime.fromisoformat(data["closed_at"].replace("Z", "+00:00")) if data.get("closed_at") else None,
        )
    
    async def create_issue(
        self,
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[list[str]] = None,
        assignees: Optional[list[str]] = None,
    ) -> GitHubIssue:
        """Create a new issue.
        
        Args:
            repo: Repository in owner/repo format
            title: Issue title
            body: Issue body (markdown)
            labels: List of label names
            assignees: List of usernames
            
        Returns:
            Created issue
        """
        payload: dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        
        data = await self._request("POST", f"/repos/{repo}/issues", data=payload)
        return self._parse_issue(data)
    
    async def close_issue(
        self,
        repo: str,
        issue_number: int,
        reason: str = "completed",
    ) -> GitHubIssue:
        """Close an issue.
        
        Args:
            repo: Repository in owner/repo format
            issue_number: Issue number
            reason: Close reason (completed, not_planned)
            
        Returns:
            Updated issue
        """
        data = await self._request(
            "PATCH",
            f"/repos/{repo}/issues/{issue_number}",
            data={"state": "closed", "state_reason": reason},
        )
        return self._parse_issue(data)
    
    async def create_pr_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
    ) -> GitHubComment:
        """Comment on a pull request.
        
        Args:
            repo: Repository in owner/repo format
            pr_number: PR number
            body: Comment body (markdown)
            
        Returns:
            Created comment
        """
        data = await self._request(
            "POST",
            f"/repos/{repo}/issues/{pr_number}/comments",
            data={"body": body},
        )
        
        return GitHubComment(
            id=data["id"],
            body=data["body"],
            user=self._parse_user(data["user"]),
            html_url=data["html_url"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )
    
    async def get_workflow_runs(
        self,
        repo: str,
        workflow: str,
        branch: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 30,
    ) -> GitHubWorkflowRunList:
        """List workflow runs.
        
        Args:
            repo: Repository in owner/repo format
            workflow: Workflow filename (e.g., "ci.yml") or ID
            branch: Filter by branch
            status: Filter by status (queued, in_progress, completed)
            per_page: Results per page (max 100)
            
        Returns:
            List of workflow runs
        """
        params: dict[str, Any] = {"per_page": min(per_page, 100)}
        if branch:
            params["branch"] = branch
        if status:
            params["status"] = status
        
        data = await self._request(
            "GET",
            f"/repos/{repo}/actions/workflows/{workflow}/runs",
            params=params,
        )
        
        runs = [
            GitHubWorkflowRun(
                id=run["id"],
                name=run["name"],
                head_branch=run["head_branch"],
                head_sha=run["head_sha"],
                status=run["status"],
                conclusion=run.get("conclusion"),
                html_url=run["html_url"],
                created_at=datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00")),
                run_attempt=run.get("run_attempt", 1),
            )
            for run in data.get("workflow_runs", [])
        ]
        
        return GitHubWorkflowRunList(
            total_count=data.get("total_count", len(runs)),
            workflow_runs=runs,
        )
    
    async def trigger_workflow(
        self,
        repo: str,
        workflow: str,
        ref: str = "main",
        inputs: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Dispatch a workflow.
        
        Args:
            repo: Repository in owner/repo format
            workflow: Workflow filename (e.g., "deploy.yml") or ID
            ref: Git ref (branch, tag, SHA)
            inputs: Workflow inputs
            
        Returns:
            True if dispatched successfully
        """
        payload: dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        
        await self._request(
            "POST",
            f"/repos/{repo}/actions/workflows/{workflow}/dispatches",
            data=payload,
        )
        
        return True
    
    async def get_commit(
        self,
        repo: str,
        sha: str,
    ) -> GitHubCommit:
        """Get commit details.
        
        Args:
            repo: Repository in owner/repo format
            sha: Commit SHA
            
        Returns:
            Commit details
        """
        data = await self._request("GET", f"/repos/{repo}/commits/{sha}")
        
        commit_data = data["commit"]
        author = commit_data["author"]
        committer = commit_data["committer"]
        
        return GitHubCommit(
            sha=data["sha"],
            message=commit_data["message"],
            author=GitHubCommitAuthor(
                name=author["name"],
                email=author["email"],
                date=datetime.fromisoformat(author["date"].replace("Z", "+00:00")),
            ),
            committer=GitHubCommitAuthor(
                name=committer["name"],
                email=committer["email"],
                date=datetime.fromisoformat(committer["date"].replace("Z", "+00:00")),
            ),
            html_url=data["html_url"],
            stats=data.get("stats"),
            files=data.get("files"),
        )
    
    async def get_issue(self, repo: str, issue_number: int) -> GitHubIssue:
        """Get issue details.
        
        Args:
            repo: Repository in owner/repo format
            issue_number: Issue number
            
        Returns:
            Issue details
        """
        data = await self._request("GET", f"/repos/{repo}/issues/{issue_number}")
        return self._parse_issue(data)
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
