"""Jira Integration for AutoSRE V2.

Provides comprehensive Jira integration:
- Issue creation and management
- Transitions and workflows
- Comments and attachments
- Search and querying
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


class JiraPriority(str, Enum):
    """Jira issue priorities."""
    
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class JiraIssueType(str, Enum):
    """Jira issue types."""
    
    BUG = "Bug"
    TASK = "Task"
    STORY = "Story"
    EPIC = "Epic"
    INCIDENT = "Incident"
    SERVICE_REQUEST = "Service Request"
    PROBLEM = "Problem"
    CHANGE = "Change"


@dataclass
class JiraConfig:
    """Configuration for Jira integration."""
    
    # Connection
    base_url: str  # e.g., https://company.atlassian.net
    email: str
    api_token: str
    
    # Defaults
    default_project: Optional[str] = None
    default_issue_type: JiraIssueType = JiraIssueType.TASK
    
    # Timeouts
    timeout_seconds: float = 30.0
    
    # Features
    create_links: bool = True
    sync_comments: bool = True


class JiraUser(BaseModel):
    """Jira user model."""
    
    account_id: str
    display_name: str
    email_address: Optional[str] = None
    active: bool = True


class JiraComment(BaseModel):
    """Jira comment model."""
    
    id: Optional[str] = None
    body: str
    author: Optional[JiraUser] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None


class JiraTransition(BaseModel):
    """Jira workflow transition."""
    
    id: str
    name: str
    to_status: str
    has_screen: bool = False


class JiraIssue(BaseModel):
    """Jira issue model."""
    
    # Identity
    key: Optional[str] = None
    id: Optional[str] = None
    
    # Basic fields
    summary: str
    description: Optional[str] = None
    project: str
    issue_type: str = "Task"
    
    # Assignment
    assignee: Optional[JiraUser] = None
    reporter: Optional[JiraUser] = None
    
    # Classification
    priority: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    
    # Status
    status: Optional[str] = None
    resolution: Optional[str] = None
    
    # Timing
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    resolved: Optional[datetime] = None
    due_date: Optional[datetime] = None
    
    # Links
    parent_key: Optional[str] = None
    epic_key: Optional[str] = None
    linked_issues: List[str] = Field(default_factory=list)
    
    # Comments
    comments: List[JiraComment] = Field(default_factory=list)
    
    # Custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    self_url: Optional[str] = None
    browse_url: Optional[str] = None
    
    def to_create_payload(self) -> Dict[str, Any]:
        """Convert to Jira API create payload."""
        fields = {
            "project": {"key": self.project},
            "summary": self.summary,
            "issuetype": {"name": self.issue_type},
        }
        
        if self.description:
            # Use Atlassian Document Format for Cloud
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": self.description}],
                    }
                ],
            }
        
        if self.priority:
            fields["priority"] = {"name": self.priority}
        
        if self.labels:
            fields["labels"] = self.labels
        
        if self.components:
            fields["components"] = [{"name": c} for c in self.components]
        
        if self.due_date:
            fields["duedate"] = self.due_date.strftime("%Y-%m-%d")
        
        if self.assignee:
            fields["assignee"] = {"accountId": self.assignee.account_id}
        
        if self.epic_key:
            fields["parent"] = {"key": self.epic_key}
        
        # Add custom fields
        for field_id, value in self.custom_fields.items():
            fields[field_id] = value
        
        return {"fields": fields}


class JiraSearchResult(BaseModel):
    """Result of a Jira search."""
    
    issues: List[JiraIssue] = Field(default_factory=list)
    total: int = 0
    start_at: int = 0
    max_results: int = 50


class JiraCreateResult(BaseModel):
    """Result of creating a Jira issue."""
    
    id: str
    key: str
    self_url: str


class JiraIntegration(AuthenticatedIntegration):
    """
    Jira integration for issue tracking.
    
    Provides comprehensive Jira functionality:
    - Create, read, update issues
    - Workflow transitions
    - Comments and attachments
    - Search with JQL
    
    Example:
        config = JiraConfig(
            base_url="https://company.atlassian.net",
            email="user@company.com",
            api_token="your-api-token",
        )
        
        async with JiraIntegration(config) as jira:
            # Create issue
            issue = await jira.create_issue(JiraIssue(
                project="SRE",
                summary="Investigate high latency",
                description="P99 latency exceeded threshold",
                issue_type="Incident",
                priority="High",
            ))
            
            # Add comment
            await jira.add_comment(issue.key, "Starting investigation...")
            
            # Transition
            await jira.transition_issue(issue.key, "In Progress")
    """
    
    def __init__(self, config: JiraConfig):
        """Initialize Jira integration.
        
        Args:
            config: Jira configuration
        """
        self.jira_config = config
        
        # Create connection config
        conn_config = ConnectionConfig(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        
        # Initialize with basic auth
        super().__init__(
            config=conn_config,
            username=config.email,
            password=config.api_token,
        )
        
        self._current_user: Optional[JiraUser] = None
    
    @property
    def name(self) -> str:
        return "jira"
    
    async def health_check(self) -> HealthCheckResult:
        """Check Jira connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            user = await self.get_current_user()
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Connected as {user.display_name}",
                latency_ms=latency,
                details={"user": user.display_name},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    async def get_current_user(self) -> JiraUser:
        """Get current authenticated user.
        
        Returns:
            JiraUser
        """
        if self._current_user:
            return self._current_user
        
        data = await self._request("GET", "/rest/api/3/myself")
        
        self._current_user = JiraUser(
            account_id=data["accountId"],
            display_name=data["displayName"],
            email_address=data.get("emailAddress"),
            active=data.get("active", True),
        )
        
        return self._current_user
    
    async def create_issue(self, issue: JiraIssue) -> JiraCreateResult:
        """Create a Jira issue.
        
        Args:
            issue: Issue to create
            
        Returns:
            JiraCreateResult with key and ID
        """
        # Use default project if not specified
        if not issue.project and self.jira_config.default_project:
            issue.project = self.jira_config.default_project
        
        payload = issue.to_create_payload()
        
        data = await self._request(
            "POST",
            "/rest/api/3/issue",
            json=payload,
        )
        
        result = JiraCreateResult(
            id=data["id"],
            key=data["key"],
            self_url=data["self"],
        )
        
        logger.info(
            "Created Jira issue",
            key=result.key,
            project=issue.project,
            summary=issue.summary[:50],
        )
        
        return result
    
    async def get_issue(
        self,
        issue_key: str,
        fields: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> JiraIssue:
        """Get a Jira issue.
        
        Args:
            issue_key: Issue key (e.g., "SRE-123")
            fields: Specific fields to return
            expand: Fields to expand
            
        Returns:
            JiraIssue
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = ",".join(expand)
        
        data = await self._request(
            "GET",
            f"/rest/api/3/issue/{issue_key}",
            params=params if params else None,
        )
        
        return self._parse_issue(data)
    
    async def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any],
    ) -> None:
        """Update issue fields.
        
        Args:
            issue_key: Issue key
            fields: Fields to update
        """
        payload = {"fields": fields}
        
        await self._request(
            "PUT",
            f"/rest/api/3/issue/{issue_key}",
            json=payload,
        )
        
        logger.info(
            "Updated Jira issue",
            key=issue_key,
            fields=list(fields.keys()),
        )
    
    async def delete_issue(self, issue_key: str) -> None:
        """Delete a Jira issue.
        
        Args:
            issue_key: Issue key
        """
        await self._request(
            "DELETE",
            f"/rest/api/3/issue/{issue_key}",
        )
        
        logger.info("Deleted Jira issue", key=issue_key)
    
    async def search_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: int = 50,
        start_at: int = 0,
    ) -> JiraSearchResult:
        """Search issues using JQL.
        
        Args:
            jql: JQL query string
            fields: Fields to return
            max_results: Maximum results
            start_at: Pagination start
            
        Returns:
            JiraSearchResult
        """
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
        }
        
        if fields:
            payload["fields"] = fields
        
        data = await self._request(
            "POST",
            "/rest/api/3/search",
            json=payload,
        )
        
        issues = [self._parse_issue(i) for i in data.get("issues", [])]
        
        return JiraSearchResult(
            issues=issues,
            total=data.get("total", len(issues)),
            start_at=data.get("startAt", start_at),
            max_results=data.get("maxResults", max_results),
        )
    
    async def get_transitions(self, issue_key: str) -> List[JiraTransition]:
        """Get available transitions for an issue.
        
        Args:
            issue_key: Issue key
            
        Returns:
            List of available transitions
        """
        data = await self._request(
            "GET",
            f"/rest/api/3/issue/{issue_key}/transitions",
        )
        
        transitions = []
        for t in data.get("transitions", []):
            transitions.append(JiraTransition(
                id=t["id"],
                name=t["name"],
                to_status=t.get("to", {}).get("name", "Unknown"),
                has_screen=t.get("hasScreen", False),
            ))
        
        return transitions
    
    async def transition_issue(
        self,
        issue_key: str,
        transition_name: str,
        comment: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> None:
        """Transition an issue to a new status.
        
        Args:
            issue_key: Issue key
            transition_name: Name of transition (e.g., "In Progress")
            comment: Optional comment to add
            resolution: Optional resolution name
        """
        # Get available transitions
        transitions = await self.get_transitions(issue_key)
        
        # Find matching transition
        transition = None
        for t in transitions:
            if t.name.lower() == transition_name.lower():
                transition = t
                break
        
        if not transition:
            available = [t.name for t in transitions]
            raise IntegrationError(
                f"Transition '{transition_name}' not found. Available: {available}",
                integration=self.name,
            )
        
        payload: Dict[str, Any] = {
            "transition": {"id": transition.id},
        }
        
        if resolution:
            payload["fields"] = {"resolution": {"name": resolution}}
        
        if comment:
            payload["update"] = {
                "comment": [
                    {
                        "add": {
                            "body": {
                                "type": "doc",
                                "version": 1,
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": comment}],
                                    }
                                ],
                            }
                        }
                    }
                ]
            }
        
        await self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/transitions",
            json=payload,
        )
        
        logger.info(
            "Transitioned Jira issue",
            key=issue_key,
            transition=transition_name,
            to_status=transition.to_status,
        )
    
    async def add_comment(
        self,
        issue_key: str,
        body: str,
    ) -> JiraComment:
        """Add a comment to an issue.
        
        Args:
            issue_key: Issue key
            body: Comment body
            
        Returns:
            Created comment
        """
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        
        data = await self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/comment",
            json=payload,
        )
        
        comment = JiraComment(
            id=data["id"],
            body=body,
            created=datetime.now(timezone.utc),
        )
        
        logger.info(
            "Added comment to Jira issue",
            key=issue_key,
            comment_id=comment.id,
        )
        
        return comment
    
    async def get_comments(
        self,
        issue_key: str,
        max_results: int = 50,
    ) -> List[JiraComment]:
        """Get comments on an issue.
        
        Args:
            issue_key: Issue key
            max_results: Maximum comments
            
        Returns:
            List of comments
        """
        data = await self._request(
            "GET",
            f"/rest/api/3/issue/{issue_key}/comment",
            params={"maxResults": max_results},
        )
        
        comments = []
        for c in data.get("comments", []):
            body = c.get("body", {})
            # Extract text from ADF
            body_text = self._extract_adf_text(body) if isinstance(body, dict) else str(body)
            
            comments.append(JiraComment(
                id=c["id"],
                body=body_text,
                author=JiraUser(
                    account_id=c.get("author", {}).get("accountId", ""),
                    display_name=c.get("author", {}).get("displayName", "Unknown"),
                ) if c.get("author") else None,
                created=datetime.fromisoformat(c["created"].replace("Z", "+00:00")) if c.get("created") else None,
                updated=datetime.fromisoformat(c["updated"].replace("Z", "+00:00")) if c.get("updated") else None,
            ))
        
        return comments
    
    async def assign_issue(
        self,
        issue_key: str,
        account_id: Optional[str] = None,
    ) -> None:
        """Assign an issue to a user.
        
        Args:
            issue_key: Issue key
            account_id: User account ID (None to unassign)
        """
        payload = {"accountId": account_id}
        
        await self._request(
            "PUT",
            f"/rest/api/3/issue/{issue_key}/assignee",
            json=payload,
        )
        
        logger.info(
            "Assigned Jira issue",
            key=issue_key,
            assignee=account_id,
        )
    
    async def link_issues(
        self,
        from_key: str,
        to_key: str,
        link_type: str = "relates to",
    ) -> None:
        """Create a link between issues.
        
        Args:
            from_key: Source issue key
            to_key: Target issue key
            link_type: Type of link
        """
        payload = {
            "type": {"name": link_type},
            "inwardIssue": {"key": from_key},
            "outwardIssue": {"key": to_key},
        }
        
        await self._request(
            "POST",
            "/rest/api/3/issueLink",
            json=payload,
        )
        
        logger.info(
            "Linked Jira issues",
            from_key=from_key,
            to_key=to_key,
            link_type=link_type,
        )
    
    async def create_incident_issue(
        self,
        title: str,
        description: str,
        severity: str,
        investigation_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> JiraCreateResult:
        """Create an incident issue with AutoSRE context.
        
        Args:
            title: Incident title
            description: Incident description
            severity: Severity level
            investigation_id: AutoSRE investigation ID
            labels: Additional labels
            
        Returns:
            JiraCreateResult
        """
        # Map severity to priority
        priority_map = {
            "critical": JiraPriority.HIGHEST,
            "high": JiraPriority.HIGH,
            "medium": JiraPriority.MEDIUM,
            "low": JiraPriority.LOW,
        }
        priority = priority_map.get(severity.lower(), JiraPriority.MEDIUM)
        
        # Build labels
        issue_labels = labels or []
        issue_labels.extend(["autosre", f"severity:{severity}"])
        if investigation_id:
            issue_labels.append(f"investigation:{investigation_id}")
        
        # Build description
        full_description = f"{description}\n\n---\n*Created by AutoSRE*"
        if investigation_id:
            full_description += f"\nInvestigation ID: {investigation_id}"
        
        issue = JiraIssue(
            project=self.jira_config.default_project or "SRE",
            summary=title,
            description=full_description,
            issue_type=JiraIssueType.INCIDENT.value,
            priority=priority.value,
            labels=issue_labels,
        )
        
        return await self.create_issue(issue)
    
    def _parse_issue(self, data: Dict[str, Any]) -> JiraIssue:
        """Parse Jira API issue response."""
        fields = data.get("fields", {})
        
        # Extract description text
        description = fields.get("description")
        if isinstance(description, dict):
            description = self._extract_adf_text(description)
        
        # Parse assignee
        assignee = None
        if fields.get("assignee"):
            assignee = JiraUser(
                account_id=fields["assignee"].get("accountId", ""),
                display_name=fields["assignee"].get("displayName", ""),
                email_address=fields["assignee"].get("emailAddress"),
            )
        
        # Parse reporter
        reporter = None
        if fields.get("reporter"):
            reporter = JiraUser(
                account_id=fields["reporter"].get("accountId", ""),
                display_name=fields["reporter"].get("displayName", ""),
            )
        
        return JiraIssue(
            key=data.get("key"),
            id=data.get("id"),
            summary=fields.get("summary", ""),
            description=description,
            project=fields.get("project", {}).get("key", ""),
            issue_type=fields.get("issuetype", {}).get("name", "Task"),
            assignee=assignee,
            reporter=reporter,
            priority=fields.get("priority", {}).get("name"),
            labels=fields.get("labels", []),
            components=[c.get("name", "") for c in fields.get("components", [])],
            status=fields.get("status", {}).get("name"),
            resolution=fields.get("resolution", {}).get("name") if fields.get("resolution") else None,
            created=datetime.fromisoformat(fields["created"].replace("Z", "+00:00")) if fields.get("created") else None,
            updated=datetime.fromisoformat(fields["updated"].replace("Z", "+00:00")) if fields.get("updated") else None,
            self_url=data.get("self"),
            browse_url=f"{self.jira_config.base_url}/browse/{data.get('key')}",
        )
    
    def _extract_adf_text(self, adf: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format."""
        if not adf:
            return ""
        
        content = adf.get("content", [])
        texts = []
        
        for block in content:
            if block.get("type") == "paragraph":
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                texts.append("\n")
            elif block.get("type") == "codeBlock":
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                texts.append("\n")
        
        return "".join(texts).strip()
