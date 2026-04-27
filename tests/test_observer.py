"""
Tests for the agent/observer module.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.agent.observer import (
    AlertWatcher,
    MetricAnalyzer,
    LogCorrelator,
    ChangeDetector,
)
from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Alert, ChangeEvent, ChangeType, Severity


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TestAlertWatcher:
    """Test AlertWatcher class."""
    
    @pytest.fixture
    def context_store(self, tmp_path):
        """Create a context store with temp database."""
        db_path = str(tmp_path / "test.db")
        return ContextStore(db_path=db_path)
    
    @pytest.fixture
    def watcher(self, context_store):
        """Create an alert watcher."""
        return AlertWatcher(context_store, poll_interval=1)
    
    def test_init(self, context_store):
        """Test alert watcher initialization."""
        watcher = AlertWatcher(context_store, poll_interval=60)
        assert watcher.context_store is context_store
        assert watcher.poll_interval == 60
        assert watcher._running is False
        assert len(watcher._callbacks) == 0
    
    def test_on_alert_registers_callback(self, watcher):
        """Test registering a callback."""
        callback = MagicMock()
        watcher.on_alert(callback)
        assert callback in watcher._callbacks
    
    def test_on_alert_multiple_callbacks(self, watcher):
        """Test registering multiple callbacks."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        watcher.on_alert(cb1)
        watcher.on_alert(cb2)
        assert len(watcher._callbacks) == 2
    
    def test_stop(self, watcher):
        """Test stopping the watcher."""
        watcher._running = True
        watcher.stop()
        assert watcher._running is False
    
    @pytest.mark.asyncio
    async def test_check_alerts_empty(self, watcher):
        """Test checking alerts when none exist."""
        callback = MagicMock()
        watcher.on_alert(callback)
        
        await watcher._check_alerts()
        
        callback.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_alerts_triggers_callback(self, context_store, watcher):
        """Test that new alerts trigger callbacks."""
        # Add an alert
        context_store.add_alert(Alert(
            id="alert-001",
            name="HighCPU",
            summary="CPU is high",
            severity=Severity.HIGH,
            source="prometheus",
        ))
        
        callback = MagicMock()
        watcher.on_alert(callback)
        
        await watcher._check_alerts()
        
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0].id == "alert-001"
    
    @pytest.mark.asyncio
    async def test_check_alerts_no_duplicate_triggers(self, context_store, watcher):
        """Test that seen alerts don't trigger again."""
        context_store.add_alert(Alert(
            id="alert-001",
            name="HighCPU",
            summary="CPU is high",
            severity=Severity.HIGH,
            source="prometheus",
        ))
        
        callback = MagicMock()
        watcher.on_alert(callback)
        
        await watcher._check_alerts()
        await watcher._check_alerts()
        
        # Only called once despite two checks
        assert callback.call_count == 1
    
    @pytest.mark.asyncio
    async def test_check_alerts_async_callback(self, context_store, watcher):
        """Test async callback is awaited."""
        context_store.add_alert(Alert(
            id="alert-002",
            name="HighMemory",
            summary="Memory is high",
            severity=Severity.MEDIUM,
            source="prometheus",
        ))
        
        callback = AsyncMock()
        watcher.on_alert(callback)
        
        await watcher._check_alerts()
        
        callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_alerts_callback_error_handled(self, context_store, watcher):
        """Test that callback errors don't break the watcher."""
        context_store.add_alert(Alert(
            id="alert-003",
            name="Test",
            summary="Test",
            severity=Severity.LOW,
            source="test",
        ))
        
        bad_callback = MagicMock(side_effect=Exception("Callback error"))
        good_callback = MagicMock()
        
        watcher.on_alert(bad_callback)
        watcher.on_alert(good_callback)
        
        await watcher._check_alerts()
        
        # Both called, error from first doesn't prevent second
        bad_callback.assert_called_once()
        good_callback.assert_called_once()
    
    def test_get_alert_history(self, context_store, watcher):
        """Test getting alert history."""
        context_store.add_alert(Alert(
            id="alert-001",
            name="Test",
            summary="Test",
            severity=Severity.LOW,
            source="test",
        ))
        
        history = watcher.get_alert_history()
        assert len(history) == 1


class TestMetricAnalyzer:
    """Test MetricAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a metric analyzer."""
        return MetricAnalyzer(prometheus_url="http://localhost:9090")
    
    def test_init_default_url(self):
        """Test default Prometheus URL."""
        analyzer = MetricAnalyzer()
        assert analyzer.prometheus_url == "http://localhost:9090"
    
    def test_init_custom_url(self):
        """Test custom Prometheus URL."""
        analyzer = MetricAnalyzer(prometheus_url="http://prom.example.com:9090")
        assert analyzer.prometheus_url == "http://prom.example.com:9090"
    
    @pytest.mark.asyncio
    async def test_analyze_service_structure(self, analyzer):
        """Test analyze_service returns correct structure."""
        with patch.object(analyzer, '_query_prometheus', return_value=None):
            result = await analyzer.analyze_service("api-service")
            
            assert "service" in result
            assert result["service"] == "api-service"
            assert "timestamp" in result
            assert "anomalies" in result
            assert "metrics" in result
    
    @pytest.mark.asyncio
    async def test_check_cpu_anomaly_detected(self, analyzer):
        """Test CPU anomaly detection."""
        with patch.object(analyzer, '_query_prometheus', return_value=0.95):
            anomaly = await analyzer._check_cpu("api-service")
            
            assert anomaly is not None
            assert anomaly["type"] == "high_cpu"
            assert anomaly["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_check_cpu_no_anomaly(self, analyzer):
        """Test no CPU anomaly when under threshold."""
        with patch.object(analyzer, '_query_prometheus', return_value=0.5):
            anomaly = await analyzer._check_cpu("api-service")
            assert anomaly is None
    
    @pytest.mark.asyncio
    async def test_check_memory_anomaly_detected(self, analyzer):
        """Test memory anomaly detection."""
        with patch.object(analyzer, '_query_prometheus', return_value=0.90):
            anomaly = await analyzer._check_memory("api-service")
            
            assert anomaly is not None
            assert anomaly["type"] == "high_memory"
    
    @pytest.mark.asyncio
    async def test_check_error_rate_anomaly_detected(self, analyzer):
        """Test error rate anomaly detection."""
        with patch.object(analyzer, '_query_prometheus', return_value=0.03):
            anomaly = await analyzer._check_error_rate("api-service")
            
            assert anomaly is not None
            assert anomaly["type"] == "high_error_rate"
            assert anomaly["severity"] == "warning"
    
    @pytest.mark.asyncio
    async def test_check_error_rate_critical(self, analyzer):
        """Test critical error rate detection."""
        with patch.object(analyzer, '_query_prometheus', return_value=0.10):
            anomaly = await analyzer._check_error_rate("api-service")
            
            assert anomaly["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_check_latency_anomaly_detected(self, analyzer):
        """Test latency anomaly detection."""
        with patch.object(analyzer, '_query_prometheus', return_value=1.5):
            anomaly = await analyzer._check_latency("api-service")
            
            assert anomaly is not None
            assert anomaly["type"] == "high_latency"
    
    @pytest.mark.asyncio
    async def test_query_prometheus_success(self, analyzer):
        """Test successful Prometheus query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [{"value": [1234567890, "0.75"]}]
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            result = await analyzer._query_prometheus("up")
            assert result == 0.75
    
    @pytest.mark.asyncio
    async def test_query_prometheus_error(self, analyzer):
        """Test Prometheus query error handling."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_class.return_value = mock_client
            
            result = await analyzer._query_prometheus("up")
            assert result is None


class TestLogCorrelator:
    """Test LogCorrelator class."""
    
    @pytest.fixture
    def correlator(self):
        """Create a log correlator."""
        return LogCorrelator()
    
    def test_init(self, correlator):
        """Test log correlator initialization."""
        assert len(correlator._error_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_find_related_logs_empty(self, correlator):
        """Test finding related logs returns empty (placeholder)."""
        result = await correlator.find_related_logs(
            service_name="api-service",
            alert_time=utcnow(),
        )
        assert result == []
    
    def test_extract_error_context_empty(self, correlator):
        """Test extracting context from empty logs."""
        result = correlator.extract_error_context([])
        assert result["error_count"] == 0
        assert result["errors"] == []
    
    def test_extract_error_context_with_errors(self, correlator):
        """Test extracting context from logs with errors."""
        logs = [
            {"message": "INFO: Request received", "timestamp": "2024-01-01T10:00:00"},
            {"message": "ERROR: Failed to connect to database", "timestamp": "2024-01-01T10:00:01"},
            {"message": "Exception: Connection refused", "timestamp": "2024-01-01T10:00:02"},
            {"message": "INFO: Retrying...", "timestamp": "2024-01-01T10:00:03"},
        ]
        
        result = correlator.extract_error_context(logs)
        
        assert result["error_count"] == 2
        assert len(result["errors"]) == 2
    
    def test_extract_error_context_case_insensitive(self, correlator):
        """Test error pattern matching is case insensitive."""
        logs = [
            {"message": "error occurred", "timestamp": "2024-01-01T10:00:00"},
            {"message": "ERROR OCCURRED", "timestamp": "2024-01-01T10:00:01"},
            {"message": "Error Occurred", "timestamp": "2024-01-01T10:00:02"},
        ]
        
        result = correlator.extract_error_context(logs)
        assert result["error_count"] == 3


class TestChangeDetector:
    """Test ChangeDetector class."""
    
    @pytest.fixture
    def context_store(self, tmp_path):
        """Create a context store with temp database."""
        db_path = str(tmp_path / "test.db")
        return ContextStore(db_path=db_path)
    
    @pytest.fixture
    def detector(self, context_store):
        """Create a change detector."""
        return ChangeDetector(context_store)
    
    def test_init(self, context_store):
        """Test change detector initialization."""
        detector = ChangeDetector(context_store)
        assert detector.context_store is context_store
    
    def test_find_relevant_changes_empty(self, detector):
        """Test finding changes when none exist."""
        changes = detector.find_relevant_changes(
            service_name="api-service",
            alert_time=utcnow(),
        )
        assert changes == []
    
    def test_find_relevant_changes_scores(self, context_store, detector):
        """Test change scoring."""
        now = utcnow()
        
        # Add a recent deployment for the affected service
        context_store.add_change(ChangeEvent(
            id="change-001",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Deploy v2.0",
            author="ci-bot",
            timestamp=now - timedelta(minutes=15),
        ))
        
        # Add an old change for different service
        context_store.add_change(ChangeEvent(
            id="change-002",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="other-service",
            description="Update config",
            author="admin",
            timestamp=now - timedelta(hours=12),
        ))
        
        changes = detector.find_relevant_changes(
            service_name="api-service",
            alert_time=now,
        )
        
        assert len(changes) == 2
        # Direct service match + recent deployment should score highest
        assert changes[0]["change"].id == "change-001"
        assert changes[0]["score"] > changes[1]["score"]
    
    def test_find_relevant_changes_filters_future(self, context_store, detector):
        """Test that changes after alert are filtered."""
        now = utcnow()
        
        context_store.add_change(ChangeEvent(
            id="change-001",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Future deploy",
            author="ci-bot",
            timestamp=now + timedelta(hours=1),  # After alert
        ))
        
        changes = detector.find_relevant_changes(
            service_name="api-service",
            alert_time=now,
        )
        
        assert len(changes) == 0
    
    def test_score_relevance_direct_match(self, detector):
        """Test scoring for direct service match."""
        now = utcnow()
        change = ChangeEvent(
            id="test",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Test",
            author="test",
            timestamp=now - timedelta(minutes=10),
        )
        
        score = detector._score_relevance(change, "api-service", now)
        
        # Should have high score: service match + recent + deployment
        assert score >= 10.0
    
    def test_score_relevance_failed_change(self, detector):
        """Test scoring for failed changes."""
        now = utcnow()
        change = ChangeEvent(
            id="test",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Failed deploy",
            author="test",
            timestamp=now - timedelta(minutes=10),
            successful=False,
        )
        
        score = detector._score_relevance(change, "api-service", now)
        
        # Failed + service match should be very high
        assert score >= 13.0
    
    def test_get_change_summary_empty(self, detector):
        """Test summary when no changes."""
        summary = detector.get_change_summary()
        
        assert summary["total_changes"] == 0
        assert summary["by_type"] == {}
        assert summary["failed_changes"] == 0
    
    def test_get_change_summary(self, context_store, detector):
        """Test change summary."""
        now = utcnow()
        
        context_store.add_change(ChangeEvent(
            id="change-001",
            change_type=ChangeType.DEPLOYMENT,
            service_name="api-service",
            description="Deploy",
            author="ci-bot",
            timestamp=now - timedelta(hours=1),
        ))
        
        context_store.add_change(ChangeEvent(
            id="change-002",
            change_type=ChangeType.DEPLOYMENT,
            service_name="web-service",
            description="Deploy",
            author="ci-bot",
            timestamp=now - timedelta(hours=2),
        ))
        
        context_store.add_change(ChangeEvent(
            id="change-003",
            change_type=ChangeType.CONFIG_CHANGE,
            service_name="api-service",
            description="Config",
            author="admin",
            timestamp=now - timedelta(hours=3),
            successful=False,
        ))
        
        summary = detector.get_change_summary()
        
        assert summary["total_changes"] == 3
        assert summary["by_type"]["deployment"] == 2
        assert summary["by_type"]["config_change"] == 1
        assert summary["by_service"]["api-service"] == 2
        assert summary["failed_changes"] == 1
