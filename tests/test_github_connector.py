"""
Tests for GitHub connector.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from autosre.foundation.connectors.github import GitHubConnector
from autosre.foundation.models import ChangeType


class TestGitHubConnectorInit:
    """Tests for GitHubConnector initialization."""
    
    def test_init_default(self):
        """Test default initialization."""
        connector = GitHubConnector()
        
        assert connector.name == "github"
        assert connector._base_url == "https://api.github.com"
        assert connector._connected is False
    
    def test_init_with_config(self):
        """Test initialization with config."""
        connector = GitHubConnector({
            "token": "ghp_test123",
            "repositories": ["org/repo1", "org/repo2"],
        })
        
        assert connector.config["token"] == "ghp_test123"
        assert len(connector.config["repositories"]) == 2


class TestGitHubConnectorConnection:
    """Tests for connection methods."""
    
    @pytest.mark.asyncio
    async def test_connect_no_token(self):
        """Test connect fails without token."""
        connector = GitHubConnector({})
        
        result = await connector.connect()
        
        assert result is False
        assert "token not configured" in connector._last_error
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        connector = GitHubConnector({"token": "ghp_test123"})
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await connector.connect()
        
        assert result is True
        assert connector._connected is True
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        connector = GitHubConnector({"token": "ghp_test123"})
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await connector.connect()
        
        assert result is False
        assert "401" in connector._last_error
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        connector = GitHubConnector({"token": "ghp_test123"})
        connector._connected = True
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        connector._client = mock_client
        
        await connector.disconnect()
        
        assert connector._connected is False
        assert connector._client is None
        mock_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected."""
        connector = GitHubConnector()
        
        result = await connector.health_check()
        
        assert result is False


class TestGitHubConnectorDeployments:
    """Tests for deployment fetching."""
    
    @pytest.fixture
    def connector(self):
        """Create a connected connector."""
        conn = GitHubConnector({"token": "ghp_test123"})
        conn._connected = True
        conn._client = MagicMock()
        return conn
    
    @pytest.mark.asyncio
    async def test_get_deployments_not_connected(self):
        """Test getting deployments when not connected."""
        connector = GitHubConnector()
        
        result = await connector.get_deployments("org/repo")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_deployments_success(self, connector):
        """Test successful deployment fetch."""
        deployment_data = [
            {
                "id": 12345,
                "environment": "production",
                "description": "Deploy v1.0.0",
                "sha": "abc123",
                "ref": "v1.0.0",
                "created_at": "2024-01-15T10:00:00Z",
                "creator": {"login": "deploy-bot"},
                "statuses_url": "https://api.github.com/repos/org/repo/deployments/12345/statuses",
            }
        ]
        
        status_data = [{"state": "success"}]
        
        async def mock_get(url, **kwargs):
            response = MagicMock()
            if "statuses" in url:
                response.status_code = 200
                response.json.return_value = status_data
            else:
                response.status_code = 200
                response.json.return_value = deployment_data
            return response
        
        connector._client.get = mock_get
        
        result = await connector.get_deployments("org/repo")
        
        assert len(result) == 1
        assert result[0].id == "gh-deploy-12345"
        assert result[0].change_type == ChangeType.DEPLOYMENT
        assert result[0].service_name == "repo"
        assert result[0].successful is True
    
    @pytest.mark.asyncio
    async def test_get_deployments_api_error(self, connector):
        """Test handling API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.get_deployments("org/repo")
        
        assert result == []
        assert "500" in connector._last_error


class TestGitHubConnectorCommits:
    """Tests for commit fetching."""
    
    @pytest.fixture
    def connector(self):
        """Create a connected connector."""
        conn = GitHubConnector({"token": "ghp_test123"})
        conn._connected = True
        conn._client = MagicMock()
        return conn
    
    @pytest.mark.asyncio
    async def test_get_recent_commits_success(self, connector):
        """Test successful commit fetch."""
        commit_data = [
            {
                "sha": "abc123def456",
                "commit": {
                    "message": "feat: add new feature\n\nDetailed description",
                    "author": {
                        "name": "John Doe",
                        "date": "2024-01-15T09:00:00Z",
                    },
                },
            }
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = commit_data
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.get_recent_commits("org/repo")
        
        assert len(result) == 1
        assert result[0].id == "gh-commit-abc123de"
        assert result[0].author == "John Doe"
        assert "add new feature" in result[0].description
    
    @pytest.mark.asyncio
    async def test_get_recent_commits_fallback_to_master(self, connector):
        """Test fallback to master branch."""
        call_count = [0]
        
        async def mock_get(url, **kwargs):
            call_count[0] += 1
            response = MagicMock()
            if call_count[0] == 1:
                # First call (main) fails
                response.status_code = 404
            else:
                # Second call (master) succeeds
                response.status_code = 200
                response.json.return_value = []
            return response
        
        connector._client.get = mock_get
        
        result = await connector.get_recent_commits("org/repo")
        
        assert call_count[0] == 2  # Both branches tried


class TestGitHubConnectorPullRequests:
    """Tests for PR fetching."""
    
    @pytest.fixture
    def connector(self):
        """Create a connected connector."""
        conn = GitHubConnector({"token": "ghp_test123"})
        conn._connected = True
        conn._client = MagicMock()
        return conn
    
    @pytest.mark.asyncio
    async def test_get_pull_requests_success(self, connector):
        """Test successful PR fetch."""
        pr_data = [
            {
                "number": 42,
                "title": "Add feature X",
                "html_url": "https://github.com/org/repo/pull/42",
                "user": {"login": "contributor"},
                "merge_commit_sha": "def456",
                "merged_at": "2024-01-15T10:30:00Z",
            }
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = pr_data
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.get_pull_requests("org/repo")
        
        assert len(result) == 1
        assert result[0].id == "gh-pr-42"
        assert result[0].pr_number == 42
        assert result[0].description == "Add feature X"
    
    @pytest.mark.asyncio
    async def test_get_pull_requests_skips_unmerged(self, connector):
        """Test that unmerged PRs are skipped."""
        pr_data = [
            {"number": 1, "title": "Open PR", "merged_at": None},
            {"number": 2, "title": "Merged PR", "merged_at": "2024-01-15T10:00:00Z",
             "user": {"login": "user"}, "html_url": "https://github.com/org/repo/pull/2"},
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = pr_data
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.get_pull_requests("org/repo")
        
        assert len(result) == 1
        assert result[0].pr_number == 2


class TestGitHubConnectorReleases:
    """Tests for release fetching."""
    
    @pytest.fixture
    def connector(self):
        """Create a connected connector."""
        conn = GitHubConnector({"token": "ghp_test123"})
        conn._connected = True
        conn._client = MagicMock()
        return conn
    
    @pytest.mark.asyncio
    async def test_get_releases_success(self, connector):
        """Test successful release fetch."""
        release_data = [
            {
                "id": 100,
                "tag_name": "v2.0.0",
                "name": "Version 2.0.0",
                "author": {"login": "releaser"},
                "created_at": "2024-01-15T12:00:00Z",
            }
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = release_data
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.get_releases("org/repo")
        
        assert len(result) == 1
        assert result[0].id == "gh-release-100"
        assert result[0].new_version == "v2.0.0"


class TestGitHubConnectorSync:
    """Tests for sync functionality."""
    
    @pytest.mark.asyncio
    async def test_sync_not_connected(self):
        """Test sync fails when not connected."""
        connector = GitHubConnector()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.sync(MagicMock())
    
    @pytest.mark.asyncio
    async def test_sync_success(self):
        """Test successful sync."""
        connector = GitHubConnector({
            "token": "ghp_test123",
            "repositories": ["org/repo1"],
        })
        connector._connected = True
        
        # Mock the individual methods
        with patch.object(connector, "get_deployments", new_callable=AsyncMock) as mock_deploy:
            with patch.object(connector, "get_recent_commits", new_callable=AsyncMock) as mock_commits:
                mock_deploy.return_value = []
                mock_commits.return_value = []
                
                mock_store = MagicMock()
                result = await connector.sync(mock_store)
                
                assert result == 0
                mock_deploy.assert_called_once_with("org/repo1")
                mock_commits.assert_called_once_with("org/repo1")
