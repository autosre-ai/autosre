"""Jira skill actions."""

import asyncio
import base64
import os
from datetime import datetime
from typing import Any, Optional

import aiohttp

from .models import (
    JiraIssue,
    JiraComment,
    JiraTransition,
    JiraSearchResult,
    JiraStatus,
    JiraIssueType,
    JiraProject,
    JiraUser,
    JiraError,
)


class RateLimiter:
    """Rate limiter for Jira API."""
    
    def __init__(self, calls_per_minute: int = 100):
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


class JiraSkill:
    """Jira integration skill."""
    
    def __init__(
        self,
        url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.url = (url or os.environ.get("JIRA_URL", "")).rstrip("/")
        self.email = email or os.environ.get("JIRA_EMAIL")
        self.api_token = api_token or os.environ.get("JIRA_API_TOKEN")
        
        if not self.url:
            raise JiraError(400, "JIRA_URL not configured")
        if not self.email:
            raise JiraError(400, "JIRA_EMAIL not configured")
        if not self.api_token:
            raise JiraError(401, "JIRA_API_TOKEN not configured")
        
        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def _headers(self) -> dict[str, str]:
        auth = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
        url = f"{self.url}/rest/api/3{path}"
        
        async with session.request(method, url, json=data, params=params) as resp:
            body = await resp.json() if resp.content_length else {}
            
            if not resp.ok:
                raise JiraError(
                    status=resp.status,
                    message=body.get("errorMessages", [resp.reason])[0] if body.get("errorMessages") else str(body),
                    errors=body.get("errors", {}),
                )
            
            return body
    
    def _parse_user(self, data: Optional[dict[str, Any]]) -> Optional[JiraUser]:
        """Parse user from API response."""
        if not data:
            return None
        return JiraUser(
            account_id=data.get("accountId", ""),
            display_name=data.get("displayName", ""),
            email_address=data.get("emailAddress"),
            avatar_url=data.get("avatarUrls", {}).get("48x48"),
            active=data.get("active", True),
        )
    
    def _parse_issue(self, data: dict[str, Any]) -> JiraIssue:
        """Parse issue from API response."""
        fields = data.get("fields", {})
        status = fields.get("status", {})
        issue_type = fields.get("issuetype", {})
        project = fields.get("project", {})
        
        return JiraIssue(
            id=data["id"],
            key=data["key"],
            summary=fields.get("summary", ""),
            description=self._parse_description(fields.get("description")),
            status=JiraStatus(
                id=status.get("id", ""),
                name=status.get("name", ""),
                category=status.get("statusCategory", {}).get("name"),
            ),
            issue_type=JiraIssueType(
                id=issue_type.get("id", ""),
                name=issue_type.get("name", ""),
                subtask=issue_type.get("subtask", False),
            ),
            project=JiraProject(
                id=project.get("id", ""),
                key=project.get("key", ""),
                name=project.get("name", ""),
            ),
            assignee=self._parse_user(fields.get("assignee")),
            reporter=self._parse_user(fields.get("reporter")),
            priority=fields.get("priority", {}).get("name"),
            labels=fields.get("labels", []),
            created=datetime.fromisoformat(fields["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(fields["updated"].replace("Z", "+00:00")),
            resolved=datetime.fromisoformat(fields["resolutiondate"].replace("Z", "+00:00")) if fields.get("resolutiondate") else None,
        )
    
    def _parse_description(self, desc: Any) -> Optional[str]:
        """Parse ADF description to plain text."""
        if desc is None:
            return None
        if isinstance(desc, str):
            return desc
        # Handle Atlassian Document Format
        if isinstance(desc, dict) and desc.get("type") == "doc":
            return self._adf_to_text(desc)
        return str(desc)
    
    def _adf_to_text(self, node: dict[str, Any]) -> str:
        """Convert ADF node to plain text."""
        if node.get("type") == "text":
            return node.get("text", "")
        
        content = node.get("content", [])
        parts = [self._adf_to_text(child) for child in content]
        
        if node.get("type") == "paragraph":
            return "".join(parts) + "\n"
        
        return "".join(parts)
    
    def _text_to_adf(self, text: str) -> dict[str, Any]:
        """Convert plain text to ADF."""
        paragraphs = text.split("\n\n")
        content = []
        
        for para in paragraphs:
            if para.strip():
                content.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": para}]
                })
        
        return {"type": "doc", "version": 1, "content": content}
    
    async def create_issue(
        self,
        project: str,
        type: str,
        summary: str,
        description: Optional[str] = None,
        labels: Optional[list[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> JiraIssue:
        """Create a new issue.
        
        Args:
            project: Project key (e.g., "OPS")
            type: Issue type (e.g., "Bug", "Task")
            summary: Issue title
            description: Issue description
            labels: Issue labels
            priority: Priority name
            assignee: Assignee account ID
            
        Returns:
            Created issue
        """
        fields: dict[str, Any] = {
            "project": {"key": project},
            "issuetype": {"name": type},
            "summary": summary,
        }
        
        if description:
            fields["description"] = self._text_to_adf(description)
        if labels:
            fields["labels"] = labels
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"accountId": assignee}
        
        data = await self._request("POST", "/issue", data={"fields": fields})
        
        # Fetch full issue details
        return await self.get_issue(data["key"])
    
    async def update_issue(
        self,
        issue_key: str,
        fields: dict[str, Any],
    ) -> JiraIssue:
        """Update issue fields.
        
        Args:
            issue_key: Issue key (e.g., "OPS-123")
            fields: Fields to update
            
        Returns:
            Updated issue
        """
        # Convert description to ADF if present
        if "description" in fields and isinstance(fields["description"], str):
            fields["description"] = self._text_to_adf(fields["description"])
        
        await self._request("PUT", f"/issue/{issue_key}", data={"fields": fields})
        
        return await self.get_issue(issue_key)
    
    async def add_comment(
        self,
        issue_key: str,
        comment: str,
    ) -> JiraComment:
        """Add comment to an issue.
        
        Args:
            issue_key: Issue key (e.g., "OPS-123")
            comment: Comment text
            
        Returns:
            Created comment
        """
        data = await self._request(
            "POST",
            f"/issue/{issue_key}/comment",
            data={"body": self._text_to_adf(comment)},
        )
        
        return JiraComment(
            id=data["id"],
            body=self._parse_description(data.get("body")) or comment,
            author=self._parse_user(data.get("author")) or JiraUser(account_id="", display_name="Unknown"),
            created=datetime.fromisoformat(data["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(data["updated"].replace("Z", "+00:00")) if data.get("updated") else None,
        )
    
    async def transition_issue(
        self,
        issue_key: str,
        transition: str,
    ) -> JiraIssue:
        """Change issue status.
        
        Args:
            issue_key: Issue key (e.g., "OPS-123")
            transition: Transition name (e.g., "Done", "In Progress")
            
        Returns:
            Updated issue
        """
        # Get available transitions
        trans_data = await self._request("GET", f"/issue/{issue_key}/transitions")
        transitions = trans_data.get("transitions", [])
        
        # Find matching transition
        target = None
        for t in transitions:
            if t["name"].lower() == transition.lower():
                target = t
                break
        
        if not target:
            available = [t["name"] for t in transitions]
            raise JiraError(400, f"Transition '{transition}' not found. Available: {available}")
        
        await self._request(
            "POST",
            f"/issue/{issue_key}/transitions",
            data={"transition": {"id": target["id"]}},
        )
        
        return await self.get_issue(issue_key)
    
    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        start_at: int = 0,
        fields: Optional[list[str]] = None,
    ) -> JiraSearchResult:
        """Search issues with JQL.
        
        Args:
            jql: JQL query string
            max_results: Maximum results (1-100)
            start_at: Pagination offset
            fields: Fields to return (default: all)
            
        Returns:
            Search results
        """
        data = await self._request(
            "POST",
            "/search",
            data={
                "jql": jql,
                "maxResults": min(max_results, 100),
                "startAt": start_at,
                "fields": fields or ["*all"],
            },
        )
        
        issues = [self._parse_issue(issue) for issue in data.get("issues", [])]
        
        return JiraSearchResult(
            issues=issues,
            total=data.get("total", len(issues)),
            start_at=data.get("startAt", start_at),
            max_results=data.get("maxResults", max_results),
        )
    
    async def get_issue(self, issue_key: str) -> JiraIssue:
        """Get issue details.
        
        Args:
            issue_key: Issue key (e.g., "OPS-123")
            
        Returns:
            Issue details
        """
        data = await self._request("GET", f"/issue/{issue_key}")
        return self._parse_issue(data)
    
    async def get_transitions(self, issue_key: str) -> list[JiraTransition]:
        """Get available transitions for an issue.
        
        Args:
            issue_key: Issue key
            
        Returns:
            List of available transitions
        """
        data = await self._request("GET", f"/issue/{issue_key}/transitions")
        
        transitions = []
        for t in data.get("transitions", []):
            to_status = t.get("to", {})
            transitions.append(JiraTransition(
                id=t["id"],
                name=t["name"],
                to_status=JiraStatus(
                    id=to_status.get("id", ""),
                    name=to_status.get("name", ""),
                    category=to_status.get("statusCategory", {}).get("name"),
                ),
            ))
        
        return transitions
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
