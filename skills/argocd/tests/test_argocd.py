"""Tests for ArgoCD skill."""

import pytest
from unittest.mock import AsyncMock, patch

from skills.argocd import ArgoCDSkill, Application, ApplicationList, ApplicationHealth, SyncResult, ArgoCDError


@pytest.fixture
def skill():
    """Create an ArgoCDSkill with mocked config."""
    with patch.dict("os.environ", {
        "ARGOCD_SERVER": "https://argocd.example.com",
        "ARGOCD_TOKEN": "test-token",
    }):
        return ArgoCDSkill()


def make_application(name: str = "my-app") -> dict:
    """Create a mock application response."""
    return {
        "metadata": {
            "name": name,
            "namespace": "argocd",
            "creationTimestamp": "2024-01-01T00:00:00Z",
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": "https://github.com/org/repo",
                "path": "manifests",
                "targetRevision": "main",
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "production",
            },
        },
        "status": {
            "health": {"status": "Healthy"},
            "sync": {"status": "Synced", "revision": "abc123"},
            "resources": [
                {
                    "kind": "Deployment",
                    "name": "my-app",
                    "namespace": "production",
                    "health": {"status": "Healthy"},
                },
                {
                    "kind": "Service",
                    "name": "my-app",
                    "namespace": "production",
                    "health": {"status": "Healthy"},
                },
            ],
        },
    }


@pytest.mark.asyncio
async def test_list_applications(skill):
    """Test listing applications."""
    mock_response = {
        "items": [make_application("app1"), make_application("app2")]
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.list_applications()
    
    assert isinstance(result, ApplicationList)
    assert result.count == 2
    assert result.items[0].name == "app1"


@pytest.mark.asyncio
async def test_get_application(skill):
    """Test getting application details."""
    mock_response = make_application("my-app")
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_application("my-app")
    
    assert isinstance(result, Application)
    assert result.name == "my-app"
    assert result.is_healthy
    assert result.is_synced


@pytest.mark.asyncio
async def test_sync_application(skill):
    """Test triggering sync."""
    mock_response = {
        "status": {
            "operationState": {
                "phase": "Running",
                "startedAt": "2024-01-01T00:00:00Z",
                "syncResult": {
                    "revision": "abc123",
                    "resources": [],
                },
            },
        },
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await skill.sync_application("my-app")
        
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert "sync" in call_args[0][1]
    
    assert isinstance(result, SyncResult)
    assert result.is_running


@pytest.mark.asyncio
async def test_rollback_application(skill):
    """Test rollback."""
    mock_response = {
        "status": {
            "operationState": {
                "phase": "Succeeded",
                "syncResult": {
                    "revision": "5",
                    "resources": [],
                },
            },
        },
    }
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await skill.rollback_application("my-app", revision=5)
        
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert "rollback" in call_args[0][1]
    
    assert result.is_successful


@pytest.mark.asyncio
async def test_get_application_health(skill):
    """Test getting health status."""
    mock_response = make_application()
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_application_health("my-app")
    
    assert isinstance(result, ApplicationHealth)
    assert result.is_healthy
    assert len(result.resources) == 2
    assert result.resources[0].kind == "Deployment"


@pytest.mark.asyncio
async def test_application_degraded(skill):
    """Test degraded application."""
    mock_response = make_application()
    mock_response["status"]["health"]["status"] = "Degraded"
    mock_response["status"]["health"]["message"] = "Pod crash looping"
    mock_response["status"]["resources"][0]["health"]["status"] = "Degraded"
    mock_response["status"]["resources"][0]["health"]["message"] = "CrashLoopBackOff"
    
    with patch.object(skill, "_request", AsyncMock(return_value=mock_response)):
        result = await skill.get_application_health("my-app")
    
    assert result.is_degraded
    assert result.message == "Pod crash looping"


def test_missing_server():
    """Test error when server is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ArgoCDError) as exc_info:
            ArgoCDSkill()
        assert exc_info.value.code == 400


def test_missing_token():
    """Test error when token is missing."""
    with patch.dict("os.environ", {"ARGOCD_SERVER": "https://argocd.example.com"}, clear=True):
        with pytest.raises(ArgoCDError) as exc_info:
            ArgoCDSkill()
        assert exc_info.value.code == 401
