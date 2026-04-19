"""Pydantic models for Jira skill."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JiraError(Exception):
    """Jira API error."""

    def __init__(self, status: int, message: str, errors: Optional[dict[str, Any]] = None):
        self.status = status
        self.message = message
        self.errors = errors or {}
        super().__init__(f"[{status}] {message}")


class JiraUser(BaseModel):
    """Jira user info."""

    account_id: str
    display_name: str
    email_address: Optional[str] = None
    avatar_url: Optional[str] = None
    active: bool = True


class JiraStatus(BaseModel):
    """Issue status."""

    id: str
    name: str
    category: Optional[str] = None


class JiraIssueType(BaseModel):
    """Issue type."""

    id: str
    name: str
    subtask: bool = False
    icon_url: Optional[str] = None


class JiraProject(BaseModel):
    """Jira project."""

    id: str
    key: str
    name: str


class JiraIssue(BaseModel):
    """Jira issue."""

    id: str
    key: str
    summary: str
    description: Optional[str] = None
    status: JiraStatus
    issue_type: JiraIssueType
    project: JiraProject
    assignee: Optional[JiraUser] = None
    reporter: Optional[JiraUser] = None
    priority: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    created: datetime
    updated: datetime
    resolved: Optional[datetime] = None

    @property
    def url(self) -> str:
        """Generate issue URL (requires base URL)."""
        return f"/browse/{self.key}"


class JiraComment(BaseModel):
    """Issue comment."""

    id: str
    body: str
    author: JiraUser
    created: datetime
    updated: Optional[datetime] = None


class JiraTransition(BaseModel):
    """Issue transition."""

    id: str
    name: str
    to_status: JiraStatus


class JiraSearchResult(BaseModel):
    """JQL search result."""

    issues: list[JiraIssue]
    total: int
    start_at: int = 0
    max_results: int = 50

    @property
    def has_more(self) -> bool:
        return self.start_at + len(self.issues) < self.total
