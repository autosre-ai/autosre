"""Tests for watch mode functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from opensre_core.watch import (
    Issue,
    WatchConfig,
    Watcher,
    WatchState,
)


class TestWatchConfig:
    """Test WatchConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = WatchConfig()

        assert config.namespace == "default"
        assert config.interval_seconds == 60
        assert config.auto_investigate is True
        assert config.alert_threshold == 3
        assert config.notify_slack is False
        assert config.max_investigations_per_hour == 5
        assert config.cooldown_seconds == 300

    def test_custom_values(self):
        """Test custom configuration values."""
        config = WatchConfig(
            namespace="production",
            interval_seconds=30,
            auto_investigate=False,
            alert_threshold=1,
            notify_slack=True,
            max_investigations_per_hour=10,
            cooldown_seconds=60,
        )

        assert config.namespace == "production"
        assert config.interval_seconds == 30
        assert config.auto_investigate is False
        assert config.alert_threshold == 1
        assert config.notify_slack is True
        assert config.max_investigations_per_hour == 10
        assert config.cooldown_seconds == 60


class TestIssue:
    """Test Issue dataclass."""

    def test_creation(self):
        """Test Issue creation."""
        issue = Issue(
            type="pod_unhealthy",
            severity="warning",
            message="Pod xyz is not ready",
            source="xyz",
        )

        assert issue.type == "pod_unhealthy"
        assert issue.severity == "warning"
        assert issue.message == "Pod xyz is not ready"
        assert issue.source == "xyz"
        assert isinstance(issue.detected_at, datetime)

    def test_equality_for_deduplication(self):
        """Test Issue equality based on type and message."""
        issue1 = Issue(type="alert", severity="critical", message="High CPU")
        issue2 = Issue(type="alert", severity="warning", message="High CPU")
        issue3 = Issue(type="alert", severity="critical", message="Different")

        # Same type and message = equal (for deduplication)
        assert issue1 == issue2
        # Different message = not equal
        assert issue1 != issue3

    def test_hashable(self):
        """Test Issue is hashable for set operations."""
        issue1 = Issue(type="alert", severity="critical", message="Test")
        issue2 = Issue(type="alert", severity="warning", message="Test")

        # Should deduplicate in a set
        issues_set = {issue1, issue2}
        assert len(issues_set) == 1


class TestWatchState:
    """Test WatchState dataclass."""

    def test_defaults(self):
        """Test default state values."""
        state = WatchState()

        assert state.last_check is None
        assert state.issues_detected == []
        assert state.active_investigation is None
        assert state.investigations_today == 0
        assert state.investigations_this_hour == 0

    def test_reset_hourly_count(self):
        """Test hourly count reset logic."""
        state = WatchState()
        state.investigations_this_hour = 5
        state.last_investigation_at = datetime.now() - timedelta(hours=2)

        state.reset_hourly_count()

        # Count should reset since hour changed
        assert state.investigations_this_hour == 0


class TestWatcher:
    """Test Watcher class."""

    @pytest.fixture
    def watcher(self):
        """Create a watcher instance for testing."""
        config = WatchConfig(
            namespace="test",
            interval_seconds=10,
            auto_investigate=True,
            alert_threshold=2,
        )
        return Watcher(config)

    def test_instantiation(self, watcher):
        """Test Watcher instantiation."""
        assert watcher.config.namespace == "test"
        assert watcher.state is not None
        assert watcher._stop_event is not None

    def test_should_investigate_disabled(self, watcher):
        """Test _should_investigate when disabled."""
        watcher.config.auto_investigate = False
        issues = [Issue(type="test", severity="critical", message="Test")]

        assert watcher._should_investigate(issues) is False

    def test_should_investigate_below_threshold(self, watcher):
        """Test _should_investigate below threshold."""
        watcher.config.alert_threshold = 3
        issues = [
            Issue(type="test1", severity="warning", message="Test 1"),
            Issue(type="test2", severity="warning", message="Test 2"),
        ]

        assert watcher._should_investigate(issues) is False

    def test_should_investigate_at_threshold(self, watcher):
        """Test _should_investigate at threshold."""
        watcher.config.alert_threshold = 2
        issues = [
            Issue(type="test1", severity="warning", message="Test 1"),
            Issue(type="test2", severity="warning", message="Test 2"),
        ]

        assert watcher._should_investigate(issues) is True

    def test_should_investigate_critical_bypasses_threshold(self, watcher):
        """Test that critical issues bypass threshold."""
        watcher.config.alert_threshold = 3
        issues = [Issue(type="oom", severity="critical", message="OOMKilled")]

        # Only 1 issue but critical
        assert watcher._should_investigate(issues) is True

    def test_should_investigate_rate_limited(self, watcher):
        """Test rate limiting prevents investigation."""
        watcher.config.max_investigations_per_hour = 2
        watcher.state.investigations_this_hour = 2
        issues = [Issue(type="test", severity="critical", message="Test")]

        assert watcher._should_investigate(issues) is False

    def test_should_investigate_cooldown(self, watcher):
        """Test cooldown prevents investigation."""
        watcher.config.cooldown_seconds = 300
        watcher.state.last_investigation_at = datetime.now() - timedelta(seconds=60)
        issues = [Issue(type="test", severity="critical", message="Test")]

        # Within cooldown
        assert watcher._should_investigate(issues) is False

    def test_should_investigate_after_cooldown(self, watcher):
        """Test investigation allowed after cooldown."""
        watcher.config.cooldown_seconds = 300
        watcher.state.last_investigation_at = datetime.now() - timedelta(seconds=400)
        issues = [Issue(type="test", severity="critical", message="Test")]

        assert watcher._should_investigate(issues) is True

    def test_render_status_no_issues(self, watcher):
        """Test _render_status with no issues."""
        panel = watcher._render_status()
        assert panel is not None

    def test_render_status_with_issues(self, watcher):
        """Test _render_status with issues."""
        watcher.state.issues_detected = [
            Issue(type="test1", severity="critical", message="Critical issue"),
            Issue(type="test2", severity="warning", message="Warning issue"),
        ]
        watcher.state.last_check = datetime.now()

        panel = watcher._render_status()
        assert panel is not None

    def test_stop(self, watcher):
        """Test stop sets the stop event."""
        assert not watcher._stop_event.is_set()
        watcher.stop()
        assert watcher._stop_event.is_set()

    def test_map_alert_severity_critical(self, watcher):
        """Test alert severity mapping for critical."""
        mock_alert = MagicMock()
        mock_alert.labels = {"severity": "critical"}

        assert watcher._map_alert_severity(mock_alert) == "critical"

        mock_alert.labels = {"severity": "page"}
        assert watcher._map_alert_severity(mock_alert) == "critical"

    def test_map_alert_severity_warning(self, watcher):
        """Test alert severity mapping for warning."""
        mock_alert = MagicMock()
        mock_alert.labels = {"severity": "warning"}

        assert watcher._map_alert_severity(mock_alert) == "warning"

    def test_map_alert_severity_info(self, watcher):
        """Test alert severity mapping for info."""
        mock_alert = MagicMock()
        mock_alert.labels = {"severity": "info"}

        assert watcher._map_alert_severity(mock_alert) == "info"


class TestWatcherAsync:
    """Test async methods of Watcher."""

    @pytest.fixture
    def watcher(self):
        """Create a watcher instance for testing."""
        config = WatchConfig(
            namespace="test",
            interval_seconds=10,
        )
        return Watcher(config)

    @pytest.mark.asyncio
    async def test_check_once(self, watcher):
        """Test check_once method."""
        # Mock adapters
        watcher.prometheus.get_alerts = AsyncMock(return_value=[])
        watcher.kubernetes.get_pods = AsyncMock(return_value=[])
        watcher.kubernetes.get_events = AsyncMock(return_value=[])

        issues = await watcher.check_once()

        assert isinstance(issues, list)
        watcher.prometheus.get_alerts.assert_called_once()
        watcher.kubernetes.get_pods.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_once_finds_unhealthy_pod(self, watcher):
        """Test check_once detects unhealthy pods."""
        mock_pod = MagicMock()
        mock_pod.name = "test-pod"
        mock_pod.ready = False
        mock_pod.status = "CrashLoopBackOff"
        mock_pod.restarts = 10

        watcher.prometheus.get_alerts = AsyncMock(return_value=[])
        watcher.kubernetes.get_pods = AsyncMock(return_value=[mock_pod])
        watcher.kubernetes.get_events = AsyncMock(return_value=[])

        issues = await watcher.check_once()

        # Should detect both unhealthy and high restarts
        assert len(issues) >= 2
        assert any(i.type == "pod_unhealthy" for i in issues)
        assert any(i.type == "high_restarts" for i in issues)
