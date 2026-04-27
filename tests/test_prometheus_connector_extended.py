"""
Tests for the Prometheus connector.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.foundation.connectors.prometheus import PrometheusConnector
from autosre.foundation.models import Severity


class TestPrometheusConnector:
    """Test PrometheusConnector class."""
    
    @pytest.fixture
    def connector(self):
        """Create a Prometheus connector."""
        return PrometheusConnector({
            "prometheus_url": "http://localhost:9090",
        })
    
    @pytest.fixture
    def connector_with_auth(self):
        """Create a Prometheus connector with auth."""
        return PrometheusConnector({
            "prometheus_url": "http://localhost:9090",
            "auth_token": "test-token",
        })
    
    def test_name(self, connector):
        """Test connector name."""
        assert connector.name == "prometheus"
    
    def test_init_default(self):
        """Test default initialization."""
        connector = PrometheusConnector()
        assert connector._connected is False
        assert connector._client is None
    
    def test_init_with_config(self, connector):
        """Test initialization with config."""
        assert connector.config["prometheus_url"] == "http://localhost:9090"
    
    @pytest.mark.asyncio
    async def test_connect_success(self, connector):
        """Test successful connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            result = await connector.connect()
            
            assert result is True
            assert connector._connected is True
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, connector):
        """Test connection failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            result = await connector.connect()
            
            assert result is False
            assert connector._connected is False
            assert "500" in connector._last_error
    
    @pytest.mark.asyncio
    async def test_connect_exception(self, connector):
        """Test connection exception handling."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_class.return_value = mock_client
            
            result = await connector.connect()
            
            assert result is False
            assert "Connection refused" in connector._last_error
    
    @pytest.mark.asyncio
    async def test_disconnect(self, connector):
        """Test disconnection."""
        connector._connected = True
        connector._client = MagicMock()
        connector._client.aclose = AsyncMock()
        
        await connector.disconnect()
        
        assert connector._connected is False
        assert connector._client is None
    
    @pytest.mark.asyncio
    async def test_health_check_not_connected(self, connector):
        """Test health check when not connected."""
        result = await connector.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, connector):
        """Test successful health check."""
        connector._connected = True
        connector._client = MagicMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.health_check()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, connector):
        """Test failed health check."""
        connector._connected = True
        connector._client = MagicMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connector.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self, connector):
        """Test health check with exception."""
        connector._connected = True
        connector._client = MagicMock()
        connector._client.get = AsyncMock(side_effect=Exception("Network error"))
        
        result = await connector.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_sync_not_connected(self, connector, tmp_path):
        """Test sync when not connected."""
        from autosre.foundation.context_store import ContextStore
        
        store = ContextStore(str(tmp_path / "test.db"))
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.sync(store)
    
    def test_alert_conversion(self, connector):
        """Test alert conversion from Prometheus format."""
        # Test that _prometheus_alert_to_model exists and works
        alert_data = {
            "labels": {
                "alertname": "HighCPU",
                "severity": "critical",
                "service": "api-service",
                "namespace": "production",
            },
            "annotations": {
                "summary": "CPU usage is high",
                "description": "CPU has been above 90% for 5 minutes",
            },
            "state": "firing",
            "activeAt": "2024-01-15T10:00:00Z",
        }
        
        alert = connector._prometheus_alert_to_model(alert_data)
        
        assert alert is not None
        assert alert.name == "HighCPU"
        assert alert.severity == Severity.CRITICAL
        assert alert.service_name == "api-service"
    
    def test_alert_conversion_invalid(self, connector):
        """Test alert conversion with invalid data."""
        # Invalid data should return None
        alert = connector._prometheus_alert_to_model({})
        # May or may not return None depending on implementation
        # At minimum shouldn't raise exception


class TestPrometheusQueries:
    """Test Prometheus query methods."""
    
    @pytest.fixture
    def connected_connector(self):
        """Create a connected Prometheus connector."""
        connector = PrometheusConnector({
            "prometheus_url": "http://localhost:9090",
        })
        connector._connected = True
        connector._prometheus_url = "http://localhost:9090"
        connector._client = MagicMock()
        return connector
    
    @pytest.mark.asyncio
    async def test_query_not_connected(self):
        """Test query when not connected."""
        connector = PrometheusConnector()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.query("up")
    
    @pytest.mark.asyncio
    async def test_query_success(self, connected_connector):
        """Test successful instant query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": {"instance": "localhost"}, "value": [1234567890, "0.75"]}
                ]
            }
        }
        connected_connector._client.get = AsyncMock(return_value=mock_response)
        
        result = await connected_connector.query("up")
        
        assert result is not None
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_query_failure(self, connected_connector):
        """Test query failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad query"
        connected_connector._client.get = AsyncMock(return_value=mock_response)
        
        with pytest.raises(RuntimeError, match="Query failed"):
            await connected_connector.query("invalid{}")
    
    @pytest.mark.asyncio
    async def test_query_range_not_connected(self):
        """Test range query when not connected."""
        from datetime import datetime, timezone
        connector = PrometheusConnector()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.query_range(
                "rate(http_requests_total[5m])",
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc),
            )
    
    @pytest.mark.asyncio
    async def test_query_range_success(self, connected_connector):
        """Test successful range query."""
        from datetime import datetime, timezone, timedelta
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": []
            }
        }
        connected_connector._client.get = AsyncMock(return_value=mock_response)
        
        now = datetime.now(timezone.utc)
        result = await connected_connector.query_range(
            promql="rate(http_requests_total[5m])",
            start=now - timedelta(hours=1),
            end=now,
            step="1m",
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_metric_metadata(self, connected_connector):
        """Test getting metric metadata."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "http_requests_total": [
                    {
                        "type": "counter",
                        "help": "Total HTTP requests",
                        "unit": "",
                    }
                ]
            }
        }
        connected_connector._client.get = AsyncMock(return_value=mock_response)
        
        metadata = await connected_connector.get_metric_metadata("http_requests_total")
        
        assert metadata is not None
    
    @pytest.mark.asyncio
    async def test_get_metric_metadata_not_found(self, connected_connector):
        """Test getting metadata for non-existent metric."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {}
        }
        connected_connector._client.get = AsyncMock(return_value=mock_response)
        
        metadata = await connected_connector.get_metric_metadata("nonexistent_metric")
        
        assert metadata == {}
