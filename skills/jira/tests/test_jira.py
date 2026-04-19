"""Tests for Jira skill."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from skills.jira import JiraSkill, JiraIssue, JiraSearchResult, JiraComment, JiraError


@pytest.fixture
def skill():
    """Create a JiraSkill with mocked config."""
    with patch.dict("os.environ", {
        "JIRA_URL": "https://test.atlassian.net",
        "JIRA_EMAIL": "test@example.com",
        "JIRA_API_TOKEN": "test-token",
    }):
        return JiraSkill()


def make_issue_response(key: str = "OPS-123", summary: str = "Test Issue") -> dict:
    """Create a mock issue response."""
    return {
        "id": "10001",
        "key": key,
        "fields": {
            "summary": summary,
            "description": {"type": "doc", "version": 1, "content": []},
            "status": {"id": "1", "name": "Open", "statusCategory": {"name": "To Do"}},
            "issuetype": {"id": "10001", "name": "Bug", "subtask": False},
            "project": {"id": "10000", "key": "OPS", "name": "Operations"},
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
            "labels": [],
        }
    }


@pytest.mark.asyncio
async def test_create_issue(skill):
    """Test creating an issue."""
    mock_create = {"id": "10001", "key": "OPS-123"}
    mock_get = make_issue_response()
    
    with patch.object(skill, "_request", AsyncMock(side_effect=[mock_create, mock_get])):
        result = await skill.create_issue(
            project="OPS",
            type="Bug",
            summary="Test Issue",
            description="Test description"
        )
    
    assert isinstance(result, JiraIssue)
    assert result.key == "OPS-123"


@pytest.mark.asyncio
async def test_update_issue(skill):
    """Test updating an issue."""
    mock_get = make_issue_response(summary="Updated Summary")
    
    with patch.object(skill, "_request", AsyncMock(side_effect=[{}, mock_get])):
        result = await skill.update_issue(
            issue_key="OPS-123",
            fields={"summary": "Updated Summary"}
        )
    
    assert result.summary == "Updated Summary"


@pytest.mark.asyncio
async def test_add_comment(skill):
    """Test adding a comment."""
    mock_response = {
        "id": "10001",
        "body": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Test comment"}]}
        ]},
        "author": {
            "accountId": "123",
            "displayName": "Test User",
        },
        "created": "2024-01-01T00:00:00.000+0000",
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.add_comment(
            issue_key="OPS-123",
            comment="Test comment"
        )
    
    assert isinstance(result, JiraComment)
    assert result.id == "10001"


@pytest.mark.asyncio
async def test_transition_issue(skill):
    """Test transitioning an issue."""
    mock_transitions = {
        "transitions": [
            {"id": "21", "name": "Done", "to": {"id": "3", "name": "Done"}},
            {"id": "11", "name": "In Progress", "to": {"id": "2", "name": "In Progress"}},
        ]
    }
    mock_get = make_issue_response()
    mock_get["fields"]["status"] = {"id": "3", "name": "Done", "statusCategory": {"name": "Done"}}
    
    with patch.object(skill, "_request", AsyncMock(side_effect=[mock_transitions, {}, mock_get])):
        result = await skill.transition_issue(
            issue_key="OPS-123",
            transition="Done"
        )
    
    assert result.status.name == "Done"


@pytest.mark.asyncio
async def test_transition_issue_not_found(skill):
    """Test error when transition not found."""
    mock_transitions = {
        "transitions": [
            {"id": "21", "name": "Done", "to": {"id": "3", "name": "Done"}},
        ]
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_transitions)):
        with pytest.raises(JiraError) as exc_info:
            await skill.transition_issue(
                issue_key="OPS-123",
                transition="Invalid"
            )
        assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_issues(skill):
    """Test searching issues."""
    mock_response = {
        "issues": [make_issue_response("OPS-1"), make_issue_response("OPS-2")],
        "total": 2,
        "startAt": 0,
        "maxResults": 50,
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.search_issues(jql="project = OPS")
    
    assert isinstance(result, JiraSearchResult)
    assert len(result.issues) == 2
    assert result.total == 2


@pytest.mark.asyncio
async def test_get_issue(skill):
    """Test getting issue details."""
    mock_response = make_issue_response()
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_issue("OPS-123")
    
    assert isinstance(result, JiraIssue)
    assert result.key == "OPS-123"
    assert result.project.key == "OPS"


def test_missing_url():
    """Test error when URL is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(JiraError) as exc_info:
            JiraSkill()
        assert exc_info.value.status == 400
