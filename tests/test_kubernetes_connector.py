"""
Tests for Kubernetes connector.
"""

import pytest
from unittest.mock import MagicMock, patch

from autosre.foundation.connectors.kubernetes import KubernetesConnector


class TestKubernetesConnectorBasics:
    """Test KubernetesConnector basic functionality."""
    
    def test_create_connector(self):
        """Test creating Kubernetes connector."""
        connector = KubernetesConnector()
        assert connector.name == "kubernetes"
        assert connector._connected is False
    
    def test_create_with_config(self):
        """Test creating with custom config."""
        config = {
            "kubeconfig": "~/.kube/config",
            "namespaces": ["default", "production"],
        }
        connector = KubernetesConnector(config=config)
        assert connector.config["kubeconfig"] == "~/.kube/config"
    
    def test_default_namespaces(self):
        """Test default namespace handling."""
        connector = KubernetesConnector()
        assert "namespaces" not in connector.config or connector.config.get("namespaces") is None


class TestKubernetesConnection:
    """Test Kubernetes connection handling."""
    
    @pytest.mark.asyncio
    async def test_connect_no_config(self):
        """Test connection attempt without k8s config."""
        connector = KubernetesConnector()
        
        # Should fail gracefully without k8s access
        result = await connector.connect()
        
        # Result depends on whether k8s is available
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect."""
        connector = KubernetesConnector()
        connector._connected = True
        
        await connector.disconnect()
        
        assert connector._connected is False


class TestKubernetesHealthCheck:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected."""
        connector = KubernetesConnector()
        connector._connected = False
        
        result = await connector.health_check()
        
        assert result is False


class TestKubernetesSync:
    """Test sync functionality."""
    
    @pytest.mark.asyncio
    async def test_sync_not_connected_raises(self):
        """Test sync raises when not connected."""
        connector = KubernetesConnector()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.sync(MagicMock())


class TestKubernetesStatus:
    """Test connector status."""
    
    def test_get_status(self):
        """Test getting connector status."""
        connector = KubernetesConnector({"enabled": True})
        connector._connected = True
        connector._items_synced = 10
        
        status = connector.get_status()
        
        assert status.name == "kubernetes"
        assert status.connected is True
        assert status.items_synced == 10
    
    def test_status_disabled(self):
        """Test status when disabled."""
        connector = KubernetesConnector({"enabled": False})
        
        status = connector.get_status()
        
        assert status.enabled is False
