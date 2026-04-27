"""
Tests for the connector base class and connector infrastructure.
"""

import pytest
from datetime import datetime, timezone
from typing import Any

from autosre.foundation.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class MockConnector(BaseConnector):
    """Mock connector for testing."""
    
    def __init__(self, config=None, should_fail=False, sync_count=5):
        super().__init__(config)
        self.should_fail = should_fail
        self.sync_count = sync_count
    
    @property
    def name(self) -> str:
        return "mock"
    
    async def connect(self) -> bool:
        if self.should_fail:
            self._last_error = "Connection failed"
            return False
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        self._connected = False
    
    async def sync(self, context_store: Any) -> int:
        if self.should_fail:
            raise Exception("Sync failed")
        return self.sync_count
    
    async def health_check(self) -> bool:
        return not self.should_fail


class TestConnectorConfig:
    """Test ConnectorConfig model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ConnectorConfig()
        assert config.enabled is True
        assert config.sync_interval_seconds == 300
        assert config.last_sync is None
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ConnectorConfig(
            enabled=False,
            sync_interval_seconds=60,
            last_sync=utcnow(),
        )
        assert config.enabled is False
        assert config.sync_interval_seconds == 60
        assert config.last_sync is not None


class TestConnectorStatus:
    """Test ConnectorStatus model."""
    
    def test_status_creation(self):
        """Test status model creation."""
        status = ConnectorStatus(
            name="test",
            enabled=True,
            connected=True,
            last_sync=utcnow(),
            items_synced=10,
        )
        assert status.name == "test"
        assert status.connected is True
        assert status.items_synced == 10
        assert status.error is None
    
    def test_status_with_error(self):
        """Test status with error."""
        status = ConnectorStatus(
            name="test",
            enabled=True,
            connected=False,
            last_sync=None,
            error="Connection refused",
        )
        assert status.connected is False
        assert status.error == "Connection refused"


class TestBaseConnector:
    """Test BaseConnector functionality via MockConnector."""
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        connector = MockConnector()
        result = await connector.connect()
        assert result is True
        assert connector._connected is True
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test failed connection."""
        connector = MockConnector(should_fail=True)
        result = await connector.connect()
        assert result is False
        assert connector._connected is False
        assert connector._last_error == "Connection failed"
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect."""
        connector = MockConnector()
        await connector.connect()
        assert connector._connected is True
        await connector.disconnect()
        assert connector._connected is False
    
    @pytest.mark.asyncio
    async def test_sync_success(self):
        """Test successful sync."""
        connector = MockConnector(sync_count=10)
        count = await connector.sync(None)
        assert count == 10
    
    @pytest.mark.asyncio
    async def test_safe_sync_success(self):
        """Test safe_sync with successful sync."""
        connector = MockConnector(sync_count=5)
        count = await connector.safe_sync(None)
        assert count == 5
        assert connector._items_synced == 5
        assert connector._last_error is None
    
    @pytest.mark.asyncio
    async def test_safe_sync_error_handling(self):
        """Test safe_sync handles errors gracefully."""
        connector = MockConnector(should_fail=True)
        count = await connector.safe_sync(None)
        assert count == 0
        assert connector._last_error == "Sync failed"
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        healthy = MockConnector(should_fail=False)
        unhealthy = MockConnector(should_fail=True)
        
        assert await healthy.health_check() is True
        assert await unhealthy.health_check() is False
    
    def test_get_status(self):
        """Test get_status returns correct status."""
        connector = MockConnector(config={"enabled": True})
        connector._connected = True
        connector._items_synced = 15
        
        status = connector.get_status()
        assert status.name == "mock"
        assert status.enabled is True
        assert status.connected is True
        assert status.items_synced == 15
    
    def test_config_access(self):
        """Test config is accessible."""
        connector = MockConnector(config={"api_key": "secret123"})
        assert connector.config["api_key"] == "secret123"
    
    def test_name_property(self):
        """Test name property."""
        connector = MockConnector()
        assert connector.name == "mock"
