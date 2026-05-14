"""Unit tests for prediction models."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from autosre.ml.prediction import (
    CapacityPredictor,
    FailurePredictor,
    TrafficPredictor,
    CostPredictor,
)


class TestCapacityPredictor:
    """Tests for CapacityPredictor."""
    
    @pytest.fixture
    def predictor(self):
        """Create a capacity predictor."""
        return CapacityPredictor(
            name="test-capacity-predictor",
            resource_types=["cpu", "memory", "disk"],
        )
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample training data."""
        n_samples = 100
        np.random.seed(42)
        
        # Features: hour, day_of_week, request_rate, current_usage
        X = np.random.rand(n_samples, 4)
        X[:, 0] = np.random.randint(0, 24, n_samples) / 24  # hour
        X[:, 1] = np.random.randint(0, 7, n_samples) / 7    # day of week
        X[:, 2] = np.random.rand(n_samples)                  # request rate
        X[:, 3] = np.random.rand(n_samples) * 0.8 + 0.1     # current usage
        
        # Target: predicted usage (with some pattern)
        y = X[:, 3] + 0.1 * X[:, 2] + np.random.normal(0, 0.05, n_samples)
        y = np.clip(y, 0, 1)
        
        return X, y
    
    def test_create_predictor(self, predictor):
        """Test creating a capacity predictor."""
        assert predictor.name == "test-capacity-predictor"
        assert not predictor.is_fitted
    
    def test_fit_predictor(self, predictor, sample_data):
        """Test fitting the predictor."""
        X, y = sample_data
        predictor.fit(X, y)
        
        assert predictor.is_fitted
    
    def test_predict_single(self, predictor, sample_data):
        """Test predicting a single sample."""
        X, y = sample_data
        predictor.fit(X, y)
        
        result = predictor.predict(X[0:1])
        
        assert result.prediction is not None
        assert 0 <= result.confidence <= 1
    
    def test_predict_batch(self, predictor, sample_data):
        """Test batch prediction."""
        X, y = sample_data
        predictor.fit(X, y)
        
        result = predictor.predict_batch([X[i:i+1] for i in range(10)])
        
        assert len(result.predictions) == 10
        assert result.batch_size == 10
    
    def test_evaluate(self, predictor, sample_data):
        """Test evaluating the predictor."""
        X, y = sample_data
        n_train = 80
        
        predictor.fit(X[:n_train], y[:n_train])
        metrics = predictor.evaluate(X[n_train:], y[n_train:])
        
        assert metrics.mse is not None or metrics.rmse is not None
        assert metrics.dataset_size == len(y) - n_train


class TestFailurePredictor:
    """Tests for FailurePredictor."""
    
    @pytest.fixture
    def predictor(self):
        """Create a failure predictor."""
        return FailurePredictor(
            name="test-failure-predictor",
            failure_types=["oom", "crash", "timeout", "network"],
        )
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample training data with failure labels."""
        n_samples = 200
        np.random.seed(42)
        
        # Features: cpu_util, mem_util, error_rate, restart_count, latency
        X = np.random.rand(n_samples, 5)
        X[:, 0] = np.random.rand(n_samples) * 0.9 + 0.1   # cpu
        X[:, 1] = np.random.rand(n_samples) * 0.9 + 0.1   # memory
        X[:, 2] = np.random.exponential(0.01, n_samples)   # error rate
        X[:, 3] = np.random.poisson(0.5, n_samples)        # restarts
        X[:, 4] = np.random.exponential(100, n_samples)    # latency
        
        # Binary label: will fail in next hour
        # High probability if high resource usage or high error rate
        failure_prob = 0.1 + 0.3 * (X[:, 0] > 0.8) + 0.3 * (X[:, 1] > 0.85) + 0.2 * (X[:, 2] > 0.05)
        y = (np.random.rand(n_samples) < failure_prob).astype(int)
        
        return X, y
    
    def test_create_predictor(self, predictor):
        """Test creating a failure predictor."""
        assert predictor.name == "test-failure-predictor"
        assert not predictor.is_fitted
    
    def test_fit_predictor(self, predictor, sample_data):
        """Test fitting the predictor."""
        X, y = sample_data
        predictor.fit(X, y)
        
        assert predictor.is_fitted
    
    def test_predict_failure_probability(self, predictor, sample_data):
        """Test predicting failure probability."""
        X, y = sample_data
        predictor.fit(X, y)
        
        result = predictor.predict(X[0:1])
        
        # Should return a probability
        assert 0 <= result.prediction <= 1
        assert result.confidence > 0
    
    def test_evaluate_classification(self, predictor, sample_data):
        """Test evaluating classification metrics."""
        X, y = sample_data
        n_train = 160
        
        predictor.fit(X[:n_train], y[:n_train])
        metrics = predictor.evaluate(X[n_train:], y[n_train:])
        
        # Should have classification metrics
        assert metrics.accuracy is not None or metrics.f1_score is not None


class TestTrafficPredictor:
    """Tests for TrafficPredictor."""
    
    @pytest.fixture
    def predictor(self):
        """Create a traffic predictor."""
        return TrafficPredictor(
            name="test-traffic-predictor",
            forecast_horizons=[1, 6, 24],  # 1h, 6h, 24h
        )
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample time series data."""
        n_samples = 168  # 1 week of hourly data
        np.random.seed(42)
        
        hours = np.arange(n_samples)
        
        # Simulate daily pattern
        daily_pattern = np.sin(2 * np.pi * hours / 24) * 0.3
        # Weekly pattern
        weekly_pattern = np.sin(2 * np.pi * hours / 168) * 0.1
        # Base traffic
        base = 1000
        # Noise
        noise = np.random.normal(0, 50, n_samples)
        
        traffic = base + base * daily_pattern + base * weekly_pattern + noise
        traffic = np.maximum(traffic, 0)
        
        # Create features and targets
        X = np.column_stack([
            hours % 24,           # hour of day
            hours // 24 % 7,      # day of week
            traffic[:-1] if len(traffic) > 1 else [0],  # lag 1
        ])[:-1]
        y = traffic[1:]
        
        return X, y
    
    def test_create_predictor(self, predictor):
        """Test creating a traffic predictor."""
        assert predictor.name == "test-traffic-predictor"
        assert not predictor.is_fitted
    
    def test_fit_predictor(self, predictor, sample_data):
        """Test fitting the predictor."""
        X, y = sample_data
        predictor.fit(X, y)
        
        assert predictor.is_fitted
    
    def test_predict_traffic(self, predictor, sample_data):
        """Test predicting traffic."""
        X, y = sample_data
        predictor.fit(X, y)
        
        result = predictor.predict(X[-1:])
        
        assert result.prediction is not None
        assert result.prediction > 0  # Traffic should be positive


class TestCostPredictor:
    """Tests for CostPredictor."""
    
    @pytest.fixture
    def predictor(self):
        """Create a cost predictor."""
        return CostPredictor(
            name="test-cost-predictor",
            cost_components=["compute", "storage", "network", "other"],
        )
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample cost data."""
        n_samples = 100
        np.random.seed(42)
        
        # Features: instances, storage_gb, network_gb, region_id
        X = np.random.rand(n_samples, 4)
        X[:, 0] = np.random.randint(1, 50, n_samples)     # instances
        X[:, 1] = np.random.randint(100, 10000, n_samples)  # storage GB
        X[:, 2] = np.random.randint(10, 5000, n_samples)    # network GB
        X[:, 3] = np.random.randint(0, 5, n_samples)        # region
        
        # Cost calculation
        y = (
            X[:, 0] * 50 +      # $50 per instance
            X[:, 1] * 0.1 +     # $0.1 per GB storage
            X[:, 2] * 0.05 +    # $0.05 per GB network
            np.random.normal(0, 100, n_samples)  # noise
        )
        y = np.maximum(y, 0)
        
        return X, y
    
    def test_create_predictor(self, predictor):
        """Test creating a cost predictor."""
        assert predictor.name == "test-cost-predictor"
        assert not predictor.is_fitted
    
    def test_fit_predictor(self, predictor, sample_data):
        """Test fitting the predictor."""
        X, y = sample_data
        predictor.fit(X, y)
        
        assert predictor.is_fitted
    
    def test_predict_cost(self, predictor, sample_data):
        """Test predicting cost."""
        X, y = sample_data
        predictor.fit(X, y)
        
        # Predict for specific configuration
        config = np.array([[10, 500, 100, 0]])  # 10 instances, 500GB storage, 100GB network
        result = predictor.predict(config)
        
        assert result.prediction is not None
        assert result.prediction > 0  # Cost should be positive
    
    def test_evaluate_cost_prediction(self, predictor, sample_data):
        """Test evaluating cost prediction."""
        X, y = sample_data
        n_train = 80
        
        predictor.fit(X[:n_train], y[:n_train])
        metrics = predictor.evaluate(X[n_train:], y[n_train:])
        
        assert metrics.mse is not None or metrics.mae is not None
