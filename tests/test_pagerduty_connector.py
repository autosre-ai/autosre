"""
Tests for PagerDuty connector.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.foundation.connectors.pagerduty import PagerDutyConnector


class TestPagerDutyConnectorInit:
    """Tests for PagerDutyConnector initialization."""
    
    def test_init_default(self):
        """Test default initialization."""
        connector = PagerDutyConnector()
        
        assert connector.name == "pagerduty"
        assert connector._connected is False
    
    def test_init_with_config(self):
        """Test initialization with config."""
        connector = PagerDutyConnector({
            "api_key": "pd_test_key",
            "service_ids": ["SERVICE1", "SERVICE2"],
        })
        
        assert connector.config["api_key"] == "pd_test_key"


class TestPagerDutyConnectorConnection:
    """Tests for connection methods."""
    
    @pytest.mark.asyncio
    async def test_connect_no_api_key(self):
        """Test connect fails without API key."""
        connector = PagerDutyConnector({})
        
        result = await connector.connect()
        
        assert result is False
        assert "api_key not configured" in connector._last_error.lower() or connector._last_error is not None
    
    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected."""
        connector = PagerDutyConnector()
        
        result = await connector.health_check()
        
        assert result is False


class TestPagerDutyConnectorSync:
    """Tests for sync functionality."""
    
    @pytest.mark.asyncio
    async def test_sync_not_connected(self):
        """Test sync fails when not connected."""
        connector = PagerDutyConnector()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.sync(MagicMock())
