"""Tests for GitHub skill."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from skills.github import GitHubSkill, GitHubIssue, GitHubComment, GitHubCommit, GitHubWorkflowRun, GitHubError


@pytest.fixture
def skill():
    """Create a GitHubSkill with mocked config."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
        return GitHubSkill()


def make_user(login: str = "testuser") -> dict:
    """Create a mock user response."""
    return {
        "id": 12345,
        "login": login,
        "avatar_url": f"https://github.com/{login}.png",
        "html_url": f"https://github.com/{login}",
    }


def make_issue(number: int = 1, title: str = "Test Issue") -> dict:
    """Create a mock issue response."""
    return {
        "id": 100000 + number,
        "number": number,
        "title": title,
        "body": "Test body",
        "state": "open",
        "user": make_user(),
        "labels": [{"id": 1, "name": "bug", "color": "d73a4a"}],
        "assignees": [],
        "html_url": f"https://github.com/org/repo/issues/{number}",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
    }


@pytest.mark.asyncio
async def test_create_issue(skill):
    """Test creating an issue."""
    mock_response = make_issue(number=42, title="New Issue")
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.create_issue(
            repo="org/repo",
            title="New Issue",
            body="Issue description",
            labels=["bug"]
        )
    
    assert isinstance(result, GitHubIssue)
    assert result.number == 42
    assert result.title == "New Issue"
    assert result.is_open


@pytest.mark.asyncio
async def test_close_issue(skill):
    """Test closing an issue."""
    mock_response = make_issue(number=42)
    mock_response["state"] = "closed"
    mock_response["closed_at"] = "2024-01-02T00:00:00Z"
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.close_issue(repo="org/repo", issue_number=42)
    
    assert not result.is_open
    assert result.closed_at is not None


@pytest.mark.asyncio
async def test_create_pr_comment(skill):
    """Test commenting on a PR."""
    mock_response = {
        "id": 123456,
        "body": "LGTM!",
        "user": make_user(),
        "html_url": "https://github.com/org/repo/issues/42#comment-123456",
        "created_at": "2024-01-01T00:00:00Z",
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.create_pr_comment(
            repo="org/repo",
            pr_number=42,
            body="LGTM!"
        )
    
    assert isinstance(result, GitHubComment)
    assert result.body == "LGTM!"


@pytest.mark.asyncio
async def test_get_workflow_runs(skill):
    """Test listing workflow runs."""
    mock_response = {
        "total_count": 2,
        "workflow_runs": [
            {
                "id": 1001,
                "name": "CI",
                "head_branch": "main",
                "head_sha": "abc123",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/org/repo/actions/runs/1001",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:30:00Z",
                "run_attempt": 1,
            },
            {
                "id": 1002,
                "name": "CI",
                "head_branch": "feature",
                "head_sha": "def456",
                "status": "in_progress",
                "conclusion": None,
                "html_url": "https://github.com/org/repo/actions/runs/1002",
                "created_at": "2024-01-01T01:00:00Z",
                "updated_at": "2024-01-01T01:00:00Z",
            },
        ]
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_workflow_runs(repo="org/repo", workflow="ci.yml")
    
    assert result.total_count == 2
    assert len(result.workflow_runs) == 2
    assert result.workflow_runs[0].is_successful


@pytest.mark.asyncio
async def test_trigger_workflow(skill):
    """Test dispatching a workflow."""
    with patch.object(skill, "_request", AsyncMock(return_value={})) as mock_req:
        result = await skill.trigger_workflow(
            repo="org/repo",
            workflow="deploy.yml",
            ref="main",
            inputs={"environment": "staging"}
        )
        
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert "deploy.yml" in call_args[0][1]
    
    assert result is True


@pytest.mark.asyncio
async def test_get_commit(skill):
    """Test getting commit details."""
    mock_response = {
        "sha": "abc123def456",
        "commit": {
            "message": "Fix bug",
            "author": {
                "name": "Test User",
                "email": "test@example.com",
                "date": "2024-01-01T00:00:00Z",
            },
            "committer": {
                "name": "Test User",
                "email": "test@example.com",
                "date": "2024-01-01T00:00:00Z",
            },
        },
        "html_url": "https://github.com/org/repo/commit/abc123",
        "stats": {"additions": 10, "deletions": 5, "total": 15},
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_commit(repo="org/repo", sha="abc123")
    
    assert isinstance(result, GitHubCommit)
    assert result.short_sha == "abc123d"
    assert result.message == "Fix bug"


def test_missing_token():
    """Test error when token is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(GitHubError) as exc_info:
            GitHubSkill()
        assert exc_info.value.status == 401
