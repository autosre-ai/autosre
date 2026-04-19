"""Pydantic models for GitHub skill."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class GitHubError(Exception):
    """GitHub API error."""
    
    def __init__(self, status: int, message: str, documentation_url: Optional[str] = None):
        self.status = status
        self.message = message
        self.documentation_url = documentation_url
        super().__init__(f"[{status}] {message}")


class GitHubUser(BaseModel):
    """GitHub user info."""
    
    id: int
    login: str
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None


class GitHubLabel(BaseModel):
    """GitHub issue label."""
    
    id: int
    name: str
    color: str
    description: Optional[str] = None


class GitHubIssue(BaseModel):
    """GitHub issue."""
    
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str = Field(description="open or closed")
    user: GitHubUser
    labels: list[GitHubLabel] = Field(default_factory=list)
    assignees: list[GitHubUser] = Field(default_factory=list)
    html_url: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    
    @property
    def is_open(self) -> bool:
        return self.state == "open"


class GitHubComment(BaseModel):
    """GitHub comment."""
    
    id: int
    body: str
    user: GitHubUser
    html_url: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class GitHubCommitAuthor(BaseModel):
    """Commit author info."""
    
    name: str
    email: str
    date: datetime


class GitHubCommit(BaseModel):
    """GitHub commit."""
    
    sha: str
    message: str
    author: GitHubCommitAuthor
    committer: GitHubCommitAuthor
    html_url: str
    stats: Optional[dict[str, int]] = None
    files: Optional[list[dict[str, Any]]] = None
    
    @property
    def short_sha(self) -> str:
        return self.sha[:7]


class GitHubWorkflowRun(BaseModel):
    """GitHub Actions workflow run."""
    
    id: int
    name: str
    head_branch: str
    head_sha: str
    status: str = Field(description="queued, in_progress, completed")
    conclusion: Optional[str] = Field(None, description="success, failure, cancelled, etc.")
    html_url: str
    created_at: datetime
    updated_at: datetime
    run_attempt: int = 1
    
    @property
    def is_completed(self) -> bool:
        return self.status == "completed"
    
    @property
    def is_successful(self) -> bool:
        return self.conclusion == "success"


class GitHubWorkflowRunList(BaseModel):
    """List of workflow runs."""
    
    total_count: int
    workflow_runs: list[GitHubWorkflowRun]
