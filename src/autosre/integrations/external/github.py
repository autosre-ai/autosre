"""GitHub Integration for AutoSRE V2.

Provides GitHub integration for:
- Pull request tracking
- Deployment tracking
- Commit information
- Repository events
"""

from __future__ import annotations

import asyncio
import base64
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


class DeploymentState(str, Enum):
    """GitHub deployment states."""
    
    ERROR = "error"
    FAILURE = "failure"
    INACTIVE = "inactive"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
    PENDING = "pending"
    SUCCESS = "success"


class PRState(str, Enum):
    """Pull request states."""
    
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class CheckStatus(str, Enum):
    """Check run status."""
    
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CheckConclusion(str, Enum):
    """Check run conclusion."""
    
    ACTION_REQUIRED = "action_required"
    CANCELLED = "cancelled"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    SUCCESS = "success"
    SKIPPED = "skipped"
    STALE = "stale"
    TIMED_OUT = "timed_out"


@dataclass
class GitHubConfig:
    """Configuration for GitHub integration."""
    
    # Authentication
    token: str  # Personal access token or app token
    
    # Base URL (for GitHub Enterprise)
    base_url: str = "https://api.github.com"
    
    # Default repository
    default_owner: Optional[str] = None
    default_repo: Optional[str] = None
    
    # Timeouts
    timeout_seconds: float = 30.0


class GitHubUser(BaseModel):
    """GitHub user model."""
    
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class GitHubCommit(BaseModel):
    """GitHub commit model."""
    
    sha: str
    message: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    authored_date: Optional[datetime] = None
    committer_name: Optional[str] = None
    committed_date: Optional[datetime] = None
    
    # PR info
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    
    # Stats
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None
    
    url: Optional[str] = None


class GitHubPullRequest(BaseModel):
    """GitHub pull request model."""
    
    # Identity
    number: int
    id: Optional[int] = None
    
    # Basic info
    title: str
    body: Optional[str] = None
    state: PRState = PRState.OPEN
    
    # Branches
    head_ref: str
    head_sha: str
    base_ref: str
    
    # Users
    author: Optional[GitHubUser] = None
    merged_by: Optional[GitHubUser] = None
    
    # Status
    draft: bool = False
    merged: bool = False
    mergeable: Optional[bool] = None
    
    # Labels
    labels: List[str] = Field(default_factory=list)
    
    # Timing
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Stats
    commits: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    
    # URLs
    html_url: Optional[str] = None
    diff_url: Optional[str] = None


class GitHubDeployment(BaseModel):
    """GitHub deployment model."""
    
    id: int
    sha: str
    ref: str
    task: str = "deploy"
    environment: str
    
    # Status
    state: DeploymentState = DeploymentState.PENDING
    
    # Payload
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Creator
    creator: Optional[GitHubUser] = None
    
    # URLs
    url: Optional[str] = None
    statuses_url: Optional[str] = None


class GitHubCheckRun(BaseModel):
    """GitHub check run model."""
    
    id: int
    name: str
    head_sha: str
    
    status: CheckStatus = CheckStatus.QUEUED
    conclusion: Optional[CheckConclusion] = None
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    output_title: Optional[str] = None
    output_summary: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository model."""
    
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    private: bool = False
    default_branch: str = "main"
    
    html_url: Optional[str] = None
    clone_url: Optional[str] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None


class GitHubIntegration(AuthenticatedIntegration):
    """
    GitHub integration for PR and deployment tracking.
    
    Provides comprehensive GitHub functionality:
    - Pull request management
    - Deployment tracking
    - Commit information
    - Check runs
    
    Example:
        config = GitHubConfig(
            token="ghp_xxxxxxxxxxxx",
            default_owner="myorg",
            default_repo="myapp",
        )
        
        async with GitHubIntegration(config) as github:
            # Get recent PRs
            prs = await github.list_pull_requests(state="merged")
            
            # Get deployments
            deploys = await github.list_deployments(environment="production")
            
            # Create deployment
            deploy = await github.create_deployment(
                ref="main",
                environment="production",
                description="Deploy v1.2.3",
            )
            
            # Update deployment status
            await github.create_deployment_status(
                deploy.id,
                state=DeploymentState.SUCCESS,
            )
    """
    
    def __init__(self, config: GitHubConfig):
        """Initialize GitHub integration.
        
        Args:
            config: GitHub configuration
        """
        self.github_config = config
        
        conn_config = ConnectionConfig(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        
        super().__init__(
            config=conn_config,
            auth_token=config.token,
        )
    
    @property
    def name(self) -> str:
        return "github"
    
    def _repo_path(
        self,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> str:
        """Get repository path."""
        owner = owner or self.github_config.default_owner
        repo = repo or self.github_config.default_repo
        
        if not owner or not repo:
            raise IntegrationError(
                "Owner and repo must be specified",
                integration=self.name,
            )
        
        return f"/repos/{owner}/{repo}"
    
    async def health_check(self) -> HealthCheckResult:
        """Check GitHub connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            data = await self._request("GET", "/user")
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Connected as {data.get('login')}",
                latency_ms=latency,
                details={"user": data.get("login")},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    async def get_authenticated_user(self) -> GitHubUser:
        """Get the authenticated user.
        
        Returns:
            GitHubUser
        """
        data = await self._request("GET", "/user")
        
        return GitHubUser(
            id=data["id"],
            login=data["login"],
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
        )
    
    # Pull Request Management
    
    async def list_pull_requests(
        self,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        state: str = "open",
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubPullRequest]:
        """List pull requests.
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state (open, closed, all)
            sort: Sort by (created, updated, popularity)
            direction: Sort direction
            per_page: Results per page
            page: Page number
            
        Returns:
            List of pull requests
        """
        path = f"{self._repo_path(owner, repo)}/pulls"
        
        data = await self._request(
            "GET",
            path,
            params={
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": per_page,
                "page": page,
            },
        )
        
        return [self._parse_pull_request(pr) for pr in data]
    
    async def get_pull_request(
        self,
        number: int,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> GitHubPullRequest:
        """Get a pull request.
        
        Args:
            number: PR number
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubPullRequest
        """
        path = f"{self._repo_path(owner, repo)}/pulls/{number}"
        data = await self._request("GET", path)
        
        return self._parse_pull_request(data)
    
    async def get_pull_request_commits(
        self,
        number: int,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> List[GitHubCommit]:
        """Get commits in a pull request.
        
        Args:
            number: PR number
            owner: Repository owner
            repo: Repository name
            
        Returns:
            List of commits
        """
        path = f"{self._repo_path(owner, repo)}/pulls/{number}/commits"
        data = await self._request("GET", path)
        
        commits = []
        for c in data:
            commit_data = c.get("commit", {})
            commits.append(GitHubCommit(
                sha=c["sha"],
                message=commit_data.get("message", ""),
                author_name=commit_data.get("author", {}).get("name"),
                author_email=commit_data.get("author", {}).get("email"),
                authored_date=datetime.fromisoformat(
                    commit_data.get("author", {}).get("date", "").replace("Z", "+00:00")
                ) if commit_data.get("author", {}).get("date") else None,
                pr_number=number,
            ))
        
        return commits
    
    async def create_pull_request(
        self,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        draft: bool = False,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> GitHubPullRequest:
        """Create a pull request.
        
        Args:
            title: PR title
            head: Head branch
            base: Base branch
            body: PR body
            draft: Create as draft
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Created pull request
        """
        path = f"{self._repo_path(owner, repo)}/pulls"
        
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "draft": draft,
        }
        
        if body:
            payload["body"] = body
        
        data = await self._request("POST", path, json=payload)
        
        logger.info(
            "Created GitHub pull request",
            number=data["number"],
            title=title,
        )
        
        return self._parse_pull_request(data)
    
    async def add_pr_comment(
        self,
        number: int,
        body: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a comment to a pull request.
        
        Args:
            number: PR number
            body: Comment body
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Created comment
        """
        path = f"{self._repo_path(owner, repo)}/issues/{number}/comments"
        
        data = await self._request(
            "POST",
            path,
            json={"body": body},
        )
        
        return data
    
    async def add_pr_labels(
        self,
        number: int,
        labels: List[str],
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        """Add labels to a pull request.
        
        Args:
            number: PR number
            labels: Labels to add
            owner: Repository owner
            repo: Repository name
        """
        path = f"{self._repo_path(owner, repo)}/issues/{number}/labels"
        
        await self._request(
            "POST",
            path,
            json={"labels": labels},
        )
    
    # Deployment Management
    
    async def list_deployments(
        self,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        sha: Optional[str] = None,
        ref: Optional[str] = None,
        task: Optional[str] = None,
        environment: Optional[str] = None,
        per_page: int = 30,
    ) -> List[GitHubDeployment]:
        """List deployments.
        
        Args:
            owner: Repository owner
            repo: Repository name
            sha: Filter by SHA
            ref: Filter by ref
            task: Filter by task
            environment: Filter by environment
            per_page: Results per page
            
        Returns:
            List of deployments
        """
        path = f"{self._repo_path(owner, repo)}/deployments"
        
        params: Dict[str, Any] = {"per_page": per_page}
        if sha:
            params["sha"] = sha
        if ref:
            params["ref"] = ref
        if task:
            params["task"] = task
        if environment:
            params["environment"] = environment
        
        data = await self._request("GET", path, params=params)
        
        return [self._parse_deployment(d) for d in data]
    
    async def get_deployment(
        self,
        deployment_id: int,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> GitHubDeployment:
        """Get a deployment.
        
        Args:
            deployment_id: Deployment ID
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubDeployment
        """
        path = f"{self._repo_path(owner, repo)}/deployments/{deployment_id}"
        data = await self._request("GET", path)
        
        return self._parse_deployment(data)
    
    async def create_deployment(
        self,
        ref: str,
        environment: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        task: str = "deploy",
        auto_merge: bool = False,
        required_contexts: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        transient_environment: bool = False,
        production_environment: bool = False,
    ) -> GitHubDeployment:
        """Create a deployment.
        
        Args:
            ref: Git ref to deploy
            environment: Environment name
            owner: Repository owner
            repo: Repository name
            task: Task type
            auto_merge: Auto-merge deployment
            required_contexts: Required status checks
            payload: Custom payload
            description: Deployment description
            transient_environment: Is transient
            production_environment: Is production
            
        Returns:
            Created deployment
        """
        path = f"{self._repo_path(owner, repo)}/deployments"
        
        body: Dict[str, Any] = {
            "ref": ref,
            "environment": environment,
            "task": task,
            "auto_merge": auto_merge,
            "transient_environment": transient_environment,
            "production_environment": production_environment,
        }
        
        if required_contexts is not None:
            body["required_contexts"] = required_contexts
        if payload:
            body["payload"] = payload
        if description:
            body["description"] = description
        
        data = await self._request("POST", path, json=body)
        
        logger.info(
            "Created GitHub deployment",
            id=data["id"],
            environment=environment,
            ref=ref,
        )
        
        return self._parse_deployment(data)
    
    async def create_deployment_status(
        self,
        deployment_id: int,
        state: DeploymentState,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        description: Optional[str] = None,
        log_url: Optional[str] = None,
        environment_url: Optional[str] = None,
        auto_inactive: bool = True,
    ) -> Dict[str, Any]:
        """Create a deployment status.
        
        Args:
            deployment_id: Deployment ID
            state: Deployment state
            owner: Repository owner
            repo: Repository name
            description: Status description
            log_url: URL to logs
            environment_url: URL to environment
            auto_inactive: Auto-mark old deployments inactive
            
        Returns:
            Created status
        """
        path = f"{self._repo_path(owner, repo)}/deployments/{deployment_id}/statuses"
        
        body: Dict[str, Any] = {
            "state": state.value,
            "auto_inactive": auto_inactive,
        }
        
        if description:
            body["description"] = description
        if log_url:
            body["log_url"] = log_url
        if environment_url:
            body["environment_url"] = environment_url
        
        data = await self._request("POST", path, json=body)
        
        logger.info(
            "Created deployment status",
            deployment_id=deployment_id,
            state=state.value,
        )
        
        return data
    
    # Commit Information
    
    async def get_commit(
        self,
        sha: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> GitHubCommit:
        """Get commit information.
        
        Args:
            sha: Commit SHA
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubCommit
        """
        path = f"{self._repo_path(owner, repo)}/commits/{sha}"
        data = await self._request("GET", path)
        
        commit_data = data.get("commit", {})
        stats = data.get("stats", {})
        
        return GitHubCommit(
            sha=data["sha"],
            message=commit_data.get("message", ""),
            author_name=commit_data.get("author", {}).get("name"),
            author_email=commit_data.get("author", {}).get("email"),
            authored_date=datetime.fromisoformat(
                commit_data.get("author", {}).get("date", "").replace("Z", "+00:00")
            ) if commit_data.get("author", {}).get("date") else None,
            committer_name=commit_data.get("committer", {}).get("name"),
            committed_date=datetime.fromisoformat(
                commit_data.get("committer", {}).get("date", "").replace("Z", "+00:00")
            ) if commit_data.get("committer", {}).get("date") else None,
            additions=stats.get("additions"),
            deletions=stats.get("deletions"),
            changed_files=len(data.get("files", [])),
            url=data.get("html_url"),
        )
    
    async def compare_commits(
        self,
        base: str,
        head: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare two commits.
        
        Args:
            base: Base commit SHA
            head: Head commit SHA
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Comparison data
        """
        path = f"{self._repo_path(owner, repo)}/compare/{base}...{head}"
        data = await self._request("GET", path)
        
        return {
            "status": data.get("status"),
            "ahead_by": data.get("ahead_by"),
            "behind_by": data.get("behind_by"),
            "total_commits": data.get("total_commits"),
            "commits": [
                GitHubCommit(
                    sha=c["sha"],
                    message=c.get("commit", {}).get("message", ""),
                )
                for c in data.get("commits", [])
            ],
            "files": data.get("files", []),
        }
    
    # Check Runs
    
    async def list_check_runs(
        self,
        ref: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> List[GitHubCheckRun]:
        """List check runs for a ref.
        
        Args:
            ref: Git ref (SHA, branch, or tag)
            owner: Repository owner
            repo: Repository name
            
        Returns:
            List of check runs
        """
        path = f"{self._repo_path(owner, repo)}/commits/{ref}/check-runs"
        data = await self._request("GET", path)
        
        runs = []
        for run in data.get("check_runs", []):
            runs.append(GitHubCheckRun(
                id=run["id"],
                name=run["name"],
                head_sha=run["head_sha"],
                status=CheckStatus(run.get("status", "queued")),
                conclusion=CheckConclusion(run["conclusion"]) if run.get("conclusion") else None,
                started_at=datetime.fromisoformat(run["started_at"].replace("Z", "+00:00")) if run.get("started_at") else None,
                completed_at=datetime.fromisoformat(run["completed_at"].replace("Z", "+00:00")) if run.get("completed_at") else None,
                output_title=run.get("output", {}).get("title"),
                output_summary=run.get("output", {}).get("summary"),
            ))
        
        return runs
    
    def _parse_pull_request(self, data: Dict[str, Any]) -> GitHubPullRequest:
        """Parse pull request data."""
        user = data.get("user", {})
        merged_by = data.get("merged_by", {})
        
        # Determine state
        if data.get("merged"):
            state = PRState.MERGED
        elif data.get("state") == "closed":
            state = PRState.CLOSED
        else:
            state = PRState.OPEN
        
        return GitHubPullRequest(
            number=data["number"],
            id=data.get("id"),
            title=data["title"],
            body=data.get("body"),
            state=state,
            head_ref=data.get("head", {}).get("ref", ""),
            head_sha=data.get("head", {}).get("sha", ""),
            base_ref=data.get("base", {}).get("ref", ""),
            author=GitHubUser(
                id=user.get("id", 0),
                login=user.get("login", ""),
                avatar_url=user.get("avatar_url"),
            ) if user else None,
            merged_by=GitHubUser(
                id=merged_by.get("id", 0),
                login=merged_by.get("login", ""),
            ) if merged_by else None,
            draft=data.get("draft", False),
            merged=data.get("merged", False),
            mergeable=data.get("mergeable"),
            labels=[l.get("name", "") for l in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
            merged_at=datetime.fromisoformat(data["merged_at"].replace("Z", "+00:00")) if data.get("merged_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"].replace("Z", "+00:00")) if data.get("closed_at") else None,
            commits=data.get("commits", 0),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            html_url=data.get("html_url"),
            diff_url=data.get("diff_url"),
        )
    
    def _parse_deployment(self, data: Dict[str, Any]) -> GitHubDeployment:
        """Parse deployment data."""
        creator = data.get("creator", {})
        
        return GitHubDeployment(
            id=data["id"],
            sha=data["sha"],
            ref=data["ref"],
            task=data.get("task", "deploy"),
            environment=data["environment"],
            payload=data.get("payload", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
            creator=GitHubUser(
                id=creator.get("id", 0),
                login=creator.get("login", ""),
            ) if creator else None,
            url=data.get("url"),
            statuses_url=data.get("statuses_url"),
        )
