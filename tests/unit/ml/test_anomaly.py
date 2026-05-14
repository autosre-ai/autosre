"""Unit tests for anomaly detection modules."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import numpy as np
import pytest

from autosre.ml.anomaly import (
    TimeSeriesAnomalyDetector,
    LogAnomalyDetector,
    BehaviorAnomalyDetector,
    MultiVariateDetector,
    AnomalyExplainer,
)


class TestTimeSeriesAnomalyDetector:
    """Tests for TimeSeriesAnomalyDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create a time series anomaly detector."""
        return TimeSeriesAnomalyDetector(
            name="test-ts-detector",
            sensitivity=0.95,
        )
    
    @pytest.fixture
    def normal_timeseries(self):
        """Generate normal time series data."""
        np.random.seed(42)
        n_points = 200
        
        # Seasonal pattern + noise
        t = np.linspace(0, 4 * np.pi, n_points)
        values = 100 + 20 * np.sin(t) + np.random.normal(0, 5, n_points)
        timestamps = [datetime.utcnow() - timedelta(minutes=n_points - i) for i in range(n_points)]
        
        return list(zip(timestamps, values))
    
    @pytest.fixture
    def anomalous_timeseries(self):
        """Generate time series with anomalies."""
        np.random.seed(42)
        n_points = 200
        
        t = np.linspace(0, 4 * np.pi, n_points)
        values = 100 + 20 * np.sin(t) + np.random.normal(0, 5, n_points)
        
        # Inject anomalies
        values[50] = 200   # Spike
        values[100] = 10   # Drop
        values[150:155] = 180  # Level shift
        
        timestamps = [datetime.utcnow() - timedelta(minutes=n_points - i) for i in range(n_points)]
        
        return list(zip(timestamps, values))
    
    def test_create_detector(self, detector):
        """Test creating detector."""
        assert detector.name == "test-ts-detector"
        assert not detector.is_fitted
    
    def test_fit_detector(self, detector, normal_timeseries):
        """Test fitting detector on normal data."""
        detector.fit(normal_timeseries)
        assert detector.is_fitted
    
    def test_detect_anomalies(self, detector, normal_timeseries, anomalous_timeseries):
        """Test detecting anomalies."""
        # Train on normal data
        detector.fit(normal_timeseries)
        
        # Detect on anomalous data
        anomalies = detector.detect(anomalous_timeseries)
        
        assert len(anomalies) > 0
        # Should detect at least some of the injected anomalies
    
    def test_no_false_positives_on_normal(self, detector, normal_timeseries):
        """Test that normal data doesn't trigger many false positives."""
        # Split data
        train_data = normal_timeseries[:150]
        test_data = normal_timeseries[150:]
        
        detector.fit(train_data)
        anomalies = detector.detect(test_data)
        
        # Very few or no anomalies in normal data
        assert len(anomalies) < len(test_data) * 0.1  # Less than 10%
    
    def test_anomaly_scores(self, detector, anomalous_timeseries):
        """Test anomaly scoring."""
        detector.fit(anomalous_timeseries[:100])
        
        scores = detector.score(anomalous_timeseries)
        
        assert len(scores) == len(anomalous_timeseries)
        # Anomaly points should have higher scores
        assert scores[50] > np.median(scores)  # The spike


class TestLogAnomalyDetector:
    """Tests for LogAnomalyDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create a log anomaly detector."""
        return LogAnomalyDetector(
            name="test-log-detector",
        )
    
    @pytest.fixture
    def normal_logs(self):
        """Generate normal log entries."""
        templates = [
            "Request processed successfully for user {}",
            "Connection established to database",
            "Cache hit for key {}",
            "Response sent in {} ms",
            "Health check passed",
        ]
        
        logs = []
        for i in range(100):
            template = np.random.choice(templates)
            if "{}" in template:
                log = template.format(np.random.randint(1000, 9999))
            else:
                log = template
            logs.append({
                "timestamp": datetime.utcnow() - timedelta(seconds=100 - i),
                "message": log,
                "level": "INFO",
            })
        
        return logs
    
    @pytest.fixture
    def anomalous_logs(self):
        """Generate logs with anomalies."""
        logs = []
        
        # Normal logs
        for i in range(80):
            logs.append({
                "timestamp": datetime.utcnow() - timedelta(seconds=100 - i),
                "message": "Request processed successfully",
                "level": "INFO",
            })
        
        # Anomalous logs
        anomalies = [
            "CRITICAL: Database connection pool exhausted",
            "ERROR: Out of memory exception in payment handler",
            "FATAL: Segmentation fault in core module",
            "ERROR: Unable to reach authentication service",
            "CRITICAL: Disk space below 5%",
        ]
        
        for i, msg in enumerate(anomalies):
            logs.append({
                "timestamp": datetime.utcnow() - timedelta(seconds=20 - i),
                "message": msg,
                "level": "ERROR" if "ERROR" in msg else "CRITICAL",
            })
        
        return logs
    
    def test_create_detector(self, detector):
        """Test creating log detector."""
        assert detector.name == "test-log-detector"
    
    def test_fit_detector(self, detector, normal_logs):
        """Test fitting on normal logs."""
        detector.fit(normal_logs)
        assert detector.is_fitted
    
    def test_detect_anomalous_logs(self, detector, normal_logs, anomalous_logs):
        """Test detecting anomalous log patterns."""
        detector.fit(normal_logs)
        anomalies = detector.detect(anomalous_logs)
        
        # Should detect the unusual log patterns
        assert len(anomalies) > 0
    
    def test_detect_log_template_changes(self, detector, normal_logs):
        """Test detecting new log templates."""
        detector.fit(normal_logs)
        
        new_logs = [
            {"timestamp": datetime.utcnow(), "message": "Unknown state transition detected", "level": "WARN"},
            {"timestamp": datetime.utcnow(), "message": "Unexpected null pointer in processOrder", "level": "ERROR"},
        ]
        
        anomalies = detector.detect(normal_logs + new_logs)
        
        # Should detect the new templates
        assert len(anomalies) >= 1


class TestBehaviorAnomalyDetector:
    """Tests for BehaviorAnomalyDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create a behavior anomaly detector."""
        return BehaviorAnomalyDetector(
            name="test-behavior-detector",
        )
    
    @pytest.fixture
    def normal_behavior(self):
        """Generate normal user/service behavior."""
        np.random.seed(42)
        n_sessions = 50
        
        behaviors = []
        for _ in range(n_sessions):
            behaviors.append({
                "requests_per_minute": np.random.normal(10, 2),
                "avg_session_duration": np.random.normal(300, 50),  # seconds
                "pages_visited": np.random.poisson(5),
                "api_calls": np.random.poisson(20),
                "error_rate": np.random.exponential(0.01),
                "unique_endpoints": np.random.poisson(8),
            })
        
        return behaviors
    
    @pytest.fixture
    def anomalous_behavior(self):
        """Generate anomalous behaviors."""
        return [
            {  # Bot-like behavior
                "requests_per_minute": 100,  # Very high
                "avg_session_duration": 1,   # Very short
                "pages_visited": 1,
                "api_calls": 500,            # Very high
                "error_rate": 0.0,
                "unique_endpoints": 1,       # Single endpoint hammering
            },
            {  # Data scraping
                "requests_per_minute": 50,
                "avg_session_duration": 3600,  # Very long
                "pages_visited": 500,          # Way too many
                "api_calls": 1000,
                "error_rate": 0.0,
                "unique_endpoints": 100,
            },
            {  # Attack pattern
                "requests_per_minute": 200,
                "avg_session_duration": 10,
                "pages_visited": 2,
                "api_calls": 5000,
                "error_rate": 0.8,           # High errors (probing)
                "unique_endpoints": 50,
            },
        ]
    
    def test_create_detector(self, detector):
        """Test creating behavior detector."""
        assert detector.name == "test-behavior-detector"
    
    def test_fit_detector(self, detector, normal_behavior):
        """Test fitting on normal behavior."""
        detector.fit(normal_behavior)
        assert detector.is_fitted
    
    def test_detect_anomalous_behavior(self, detector, normal_behavior, anomalous_behavior):
        """Test detecting anomalous behavior."""
        detector.fit(normal_behavior)
        
        anomalies = detector.detect(anomalous_behavior)
        
        # All should be detected as anomalous
        assert len(anomalies) == len(anomalous_behavior)
    
    def test_normal_not_flagged(self, detector, normal_behavior):
        """Test that normal behavior isn't flagged."""
        # Use first half for training
        detector.fit(normal_behavior[:25])
        
        # Test on second half
        anomalies = detector.detect(normal_behavior[25:])
        
        # Very few false positives
        assert len(anomalies) < len(normal_behavior[25:]) * 0.15


class TestMultiVariateDetector:
    """Tests for MultiVariateDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create a multivariate detector."""
        return MultiVariateDetector(
            name="test-multivariate-detector",
            features=["cpu", "memory", "latency", "error_rate"],
        )
    
    @pytest.fixture
    def normal_multivariate(self):
        """Generate normal multivariate data."""
        np.random.seed(42)
        n_samples = 100
        
        # Correlated features (when CPU goes up, latency goes up)
        cpu = np.random.normal(50, 10, n_samples)
        memory = np.random.normal(60, 8, n_samples)
        latency = cpu * 2 + np.random.normal(0, 10, n_samples)  # Correlated with CPU
        error_rate = np.random.exponential(0.01, n_samples)
        
        return np.column_stack([cpu, memory, latency, error_rate])
    
    @pytest.fixture
    def anomalous_multivariate(self):
        """Generate anomalous multivariate data."""
        return np.array([
            [80, 90, 50, 0.01],   # High resources, low latency (unusual)
            [30, 40, 200, 0.5],   # Low resources, high latency/errors
            [95, 95, 300, 0.8],   # Everything high
        ])
    
    def test_create_detector(self, detector):
        """Test creating multivariate detector."""
        assert detector.name == "test-multivariate-detector"
    
    def test_fit_detector(self, detector, normal_multivariate):
        """Test fitting multivariate detector."""
        detector.fit(normal_multivariate)
        assert detector.is_fitted
    
    def test_detect_multivariate_anomalies(self, detector, normal_multivariate, anomalous_multivariate):
        """Test detecting multivariate anomalies."""
        detector.fit(normal_multivariate)
        
        anomalies = detector.detect(anomalous_multivariate)
        
        # Should detect at least 2 of the 3
        assert len(anomalies) >= 2
    
    def test_correlation_based_detection(self, detector, normal_multivariate):
        """Test detecting correlation-based anomalies."""
        detector.fit(normal_multivariate)
        
        # This breaks the correlation: high CPU but low latency
        correlation_anomaly = np.array([[90, 50, 50, 0.01]])
        
        anomalies = detector.detect(correlation_anomaly)
        
        # Should be detected as anomalous
        assert len(anomalies) == 1


class TestAnomalyExplainer:
    """Tests for AnomalyExplainer."""
    
    @pytest.fixture
    def explainer(self):
        """Create an anomaly explainer."""
        return AnomalyExplainer()
    
    @pytest.fixture
    def sample_anomaly(self):
        """Create a sample anomaly for explanation."""
        return {
            "timestamp": datetime.utcnow(),
            "type": "multivariate",
            "features": {
                "cpu": 95,
                "memory": 88,
                "latency": 500,
                "error_rate": 0.15,
            },
            "normal_ranges": {
                "cpu": (40, 70),
                "memory": (50, 75),
                "latency": (50, 150),
                "error_rate": (0.0, 0.02),
            },
            "score": 0.95,
        }
    
    def test_create_explainer(self, explainer):
        """Test creating explainer."""
        assert explainer is not None
    
    def test_explain_anomaly(self, explainer, sample_anomaly):
        """Test explaining an anomaly."""
        explanation = explainer.explain(sample_anomaly)
        
        assert explanation is not None
        assert "summary" in explanation or hasattr(explanation, "summary")
    
    def test_identify_contributing_features(self, explainer, sample_anomaly):
        """Test identifying which features contributed to anomaly."""
        contributors = explainer.identify_contributors(sample_anomaly)
        
        assert len(contributors) > 0
        # All features are outside normal range, so all should contribute
    
    def test_generate_human_readable(self, explainer, sample_anomaly):
        """Test generating human-readable explanation."""
        text = explainer.to_human_readable(sample_anomaly)
        
        assert isinstance(text, str)
        assert len(text) > 0
        # Should mention the high values
        assert "cpu" in text.lower() or "latency" in text.lower()
    
    def test_severity_assessment(self, explainer, sample_anomaly):
        """Test assessing anomaly severity."""
        severity = explainer.assess_severity(sample_anomaly)
        
        assert severity in ["low", "medium", "high", "critical"]
        # With all features anomalous, should be high or critical
        assert severity in ["high", "critical"]
