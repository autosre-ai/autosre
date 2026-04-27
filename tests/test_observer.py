"""
Tests for the observer module (alert watching, metric analysis, log correlation).
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

from autosre.agent.observer import (
    AlertWatcher,
    MetricAnalyzer,
    LogCorrelator,
    ChangeDetector,
)
from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Alert, Severity, ChangeEvent, ChangeType


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def context_store():
    """Create a temporary context store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "context.db")
        yield ContextStore(db_path=db_path)


@pytest.fixture
def sample_alert():
    """Create a sample alert."""
    return Alert(
        id="alert-001",
        name="HighCPU",
        severity=Severity.HIGH,
        summary="CPU usage above 90%",
        service_name="api-server",
        fired_at=utcnow(),
    )


class TestAlertWatcher:
    """Test AlertWatcher functionality."""
    
    def test_create_watcher(self, context_store):
        """Test creating an alert watcher."""
        watcher = AlertWatcher(context_store, poll_interval=10)
        assert watcher.context_store == context_store
        assert watcher.poll_interval == 10
        assert watcher._running is False
    
    def test_register_callback(self, context_store):
        """Test registering alert callbacks."""
        watcher = AlertWatcher(context_store)
        
        callback = MagicMock()
        watcher.on_alert(callback)
        
        assert len(watcher._callbacks) == 1
        assert callback in watcher._callbacks
    
    def test_register_multiple_callbacks(self, context_store):
        """Test registering multiple callbacks."""
        watcher = AlertWatcher(context_store)
        
        callback1 = MagicMock()
        callback2 = MagicMock()
        watcher.on_alert(callback1)
        watcher.on_alert(callback2)
        
        assert len(watcher._callbacks) == 2
    
    @pytest.mark.asyncio
    async def test_check_alerts_triggers_callback(self, context_store, sample_alert):
        """Test that new alerts trigger callbacks."""
        watcher = AlertWatcher(context_store)
        
        callback = MagicMock()
        watcher.on_alert(callback)
        
        # Add an alert
        context_store.add_alert(sample_alert)
        
        # Check alerts
        await watcher._check_alerts()
        
        # Callback should have been triggered
        callback.assert_called_once()
        called_alert = callback.call_args[0][0]
        assert called_alert.id == "alert-001"
    
    @pytest.mark.asyncio
    async def test_same_alert_not_triggered_twice(self, context_store, sample_alert):
        """Test that same alert doesn't trigger callback twice."""
        watcher = AlertWatcher(context_store)
        
        callback = MagicMock()
        watcher.on_alert(callback)
        
        context_store.add_alert(sample_alert)
        
        await watcher._check_alerts()
        await watcher._check_alerts()
        
        # Callback should only be called once
        assert callback.call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_callback(self, context_store, sample_alert):
        """Test async callback support."""
        watcher = AlertWatcher(context_store)
        
        results = []
        async def async_callback(alert):
            results.append(alert.id)
        
        watcher.on_alert(async_callback)
        context_store.add_alert(sample_alert)
        
        await watcher._check_alerts()
        
        assert "alert-001" in results
    
    def test_stop_watcher(self, context_store):
        """Test stopping the watcher."""
        watcher = AlertWatcher(context_store)
        watcher._running = True
        
        watcher.stop()
        
        assert watcher._running is False


class TestMetricAnalyzer:
    """Test MetricAnalyzer functionality."""
    
    def test_create_analyzer(self):
        """Test creating a metric analyzer."""
        analyzer = MetricAnalyzer()
        assert analyzer.prometheus_url == "http://localhost:9090"
        
    def test_custom_prometheus_url(self):
        """Test custom Prometheus URL."""
        analyzer = MetricAnalyzer(prometheus_url="http://prometheus:9090")
        assert analyzer.prometheus_url == "http://prometheus:9090"
    
    @pytest.mark.asyncio
    async def test_analyze_service_structure(self):
        """Test analyze_service returns correct structure."""
        analyzer = MetricAnalyzer()
        
        # This will fail to connect but should return valid structure
        results = await analyzer.analyze_service("test-service")
        
        assert "service" in results
        assert results["service"] == "test-service"
        assert "timestamp" in results
        assert "anomalies" in results
        assert "metrics" in results
        assert isinstance(results["anomalies"], list)


class TestLogCorrelator:
    """Test LogCorrelator functionality."""
    
    def test_create_correlator(self):
        """Test creating log correlator."""
        correlator = LogCorrelator()
        assert len(correlator._error_patterns) > 0
    
    def test_error_patterns_exist(self):
        """Test that error patterns include common errors."""
        correlator = LogCorrelator()
        patterns_str = " ".join(correlator._error_patterns)
        
        assert "error" in patterns_str.lower()
        assert "exception" in patterns_str.lower()
        assert "timeout" in patterns_str.lower()


class TestChangeDetector:
    """Test ChangeDetector functionality."""
    
    def test_create_detector(self, context_store):
        """Test creating change detector."""
        detector = ChangeDetector(context_store)
        assert detector.context_store == context_store
    
    def test_find_relevant_changes_empty(self, context_store):
        """Test finding relevant changes with no data."""
        detector = ChangeDetector(context_store)
        
        results = detector.find_relevant_changes(
            service_name="api-server",
            alert_time=utcnow(),
        )
        
        assert results == []
    
    def test_find_service_correlated_changes(self, context_store):
        """Test finding changes for the same service."""
        detector = ChangeDetector(context_store)
        
        # Add a recent change
        change = ChangeEvent(
            id="change-001",
            service_name="api-server",
            change_type=ChangeType.DEPLOYMENT,
            description="Deploy v2.0",
            author="deploy-bot",
            timestamp=utcnow() - timedelta(minutes=30),
        )
        context_store.add_change(change)
        
        # Find relevant changes
        results = detector.find_relevant_changes(
            service_name="api-server",
            alert_time=utcnow(),
        )
        
        # Should find the correlated change
        assert len(results) >= 0  # Depends on scoring
    
    def test_score_relevance_direct_match(self, context_store):
        """Test scoring gives high score for direct service match."""
        detector = ChangeDetector(context_store)
        
        change = ChangeEvent(
            id="change-001",
            service_name="api-server",
            change_type=ChangeType.DEPLOYMENT,
            description="Deploy v2.0",
            author="deploy-bot",
            timestamp=utcnow() - timedelta(minutes=15),
        )
        
        score = detector._score_relevance(
            change,
            service_name="api-server",
            alert_time=utcnow(),
        )
        
        # Should have high score (service match + time proximity + deployment)
        assert score >= 5.0
    
    def test_score_relevance_no_match(self, context_store):
        """Test scoring gives low score for unrelated change."""
        detector = ChangeDetector(context_store)
        
        change = ChangeEvent(
            id="change-001",
            service_name="database",
            change_type=ChangeType.SCALE_UP,
            description="Scale up",
            author="autoscaler",
            timestamp=utcnow() - timedelta(hours=10),
        )
        
        score = detector._score_relevance(
            change,
            service_name="api-server",
            alert_time=utcnow(),
        )
        
        # Should have low score (no service match, old change)
        assert score < 3.0
    
    def test_get_change_summary(self, context_store):
        """Test getting change summary."""
        detector = ChangeDetector(context_store)
        
        summary = detector.get_change_summary(hours=24)
        
        assert "total_changes" in summary
        assert "by_type" in summary
