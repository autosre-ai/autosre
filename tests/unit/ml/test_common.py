"""Unit tests for ML common modules."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from autosre.ml.common import (
    BaseMLModel,
    ModelMetadata,
    ModelVersion,
    ModelStatus,
    TrainingConfig,
    EvaluationMetrics,
    PredictionResult,
    BatchPredictionResult,
)


class TestModelMetadata:
    """Tests for ModelMetadata."""
    
    def test_create_metadata(self):
        """Test creating model metadata."""
        meta = ModelMetadata(
            name="test-model",
            model_type="capacity_predictor",
            description="Test model for capacity prediction",
        )
        
        assert meta.name == "test-model"
        assert meta.model_type == "capacity_predictor"
        assert meta.status == ModelStatus.DRAFT
        assert meta.model_id.startswith("model-")
        assert meta.current_version is None
        assert len(meta.versions) == 0
    
    def test_add_version(self):
        """Test adding a version to model."""
        meta = ModelMetadata(name="test", model_type="test")
        
        version = ModelVersion(
            version_number=1,
            description="First version",
            metrics={"accuracy": 0.95},
        )
        
        meta.add_version(version)
        
        assert len(meta.versions) == 1
        assert meta.current_version == version
        assert meta.current_version.version_number == 1
    
    def test_get_version(self):
        """Test getting a specific version."""
        meta = ModelMetadata(name="test", model_type="test")
        
        v1 = ModelVersion(version_number=1)
        v2 = ModelVersion(version_number=2)
        
        meta.add_version(v1)
        meta.add_version(v2)
        
        found = meta.get_version(v1.version_id)
        assert found == v1
        
        not_found = meta.get_version("nonexistent")
        assert not_found is None
    
    def test_metadata_with_tags_and_owner(self):
        """Test metadata with additional fields."""
        meta = ModelMetadata(
            name="production-model",
            model_type="failure_predictor",
            owner="sre-team",
            team="platform",
            tags=["production", "critical", "v2"],
        )
        
        assert meta.owner == "sre-team"
        assert meta.team == "platform"
        assert "production" in meta.tags


class TestModelVersion:
    """Tests for ModelVersion."""
    
    def test_create_version(self):
        """Test creating a model version."""
        version = ModelVersion(
            version_number=1,
            description="Initial release",
        )
        
        assert version.version_number == 1
        assert version.version_id.startswith("v-")
        assert version.description == "Initial release"
    
    def test_version_with_training_info(self):
        """Test version with training information."""
        now = datetime.utcnow()
        version = ModelVersion(
            version_number=2,
            training_started_at=now,
            training_completed_at=now + timedelta(hours=1),
            training_duration_seconds=3600.0,
            metrics={"rmse": 0.05, "mae": 0.03},
        )
        
        assert version.training_duration_seconds == 3600.0
        assert version.metrics["rmse"] == 0.05
    
    def test_version_with_artifact(self):
        """Test version with artifact information."""
        version = ModelVersion(
            version_number=3,
            artifact_path="/models/v3/model.pkl",
            artifact_size_bytes=1024 * 1024 * 50,
            git_commit="abc123",
            git_branch="main",
        )
        
        assert version.artifact_path == "/models/v3/model.pkl"
        assert version.artifact_size_bytes == 50 * 1024 * 1024
        assert version.git_commit == "abc123"


class TestTrainingConfig:
    """Tests for TrainingConfig."""
    
    def test_default_config(self):
        """Test default training configuration."""
        config = TrainingConfig()
        
        assert config.train_split == 0.8
        assert config.validation_split == 0.1
        assert config.test_split == 0.1
        assert config.epochs == 100
        assert config.batch_size == 32
        assert config.learning_rate == 0.001
    
    def test_custom_config(self):
        """Test custom training configuration."""
        config = TrainingConfig(
            train_split=0.7,
            validation_split=0.15,
            test_split=0.15,
            epochs=200,
            batch_size=64,
            learning_rate=0.0005,
            dropout_rate=0.2,
            use_gpu=False,
        )
        
        assert config.train_split == 0.7
        assert config.epochs == 200
        assert config.dropout_rate == 0.2
        assert config.use_gpu is False
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid train split
        with pytest.raises(ValueError):
            TrainingConfig(train_split=1.5)
        
        # Invalid batch size
        with pytest.raises(ValueError):
            TrainingConfig(batch_size=0)
        
        # Invalid learning rate
        with pytest.raises(ValueError):
            TrainingConfig(learning_rate=-0.001)


class TestEvaluationMetrics:
    """Tests for EvaluationMetrics."""
    
    def test_regression_metrics(self):
        """Test regression evaluation metrics."""
        metrics = EvaluationMetrics(
            mse=0.01,
            rmse=0.1,
            mae=0.08,
            mape=5.0,
            r2_score=0.95,
            dataset_size=1000,
        )
        
        assert metrics.mse == 0.01
        assert metrics.rmse == 0.1
        assert metrics.r2_score == 0.95
        assert metrics.dataset_size == 1000
    
    def test_classification_metrics(self):
        """Test classification evaluation metrics."""
        metrics = EvaluationMetrics(
            accuracy=0.92,
            precision=0.90,
            recall=0.88,
            f1_score=0.89,
            auc_roc=0.95,
        )
        
        assert metrics.accuracy == 0.92
        assert metrics.f1_score == 0.89
        assert metrics.auc_roc == 0.95
    
    def test_custom_metrics(self):
        """Test custom evaluation metrics."""
        metrics = EvaluationMetrics(
            custom_metrics={
                "specificity": 0.95,
                "balanced_accuracy": 0.90,
                "coverage": 0.85,
            }
        )
        
        assert metrics.custom_metrics["specificity"] == 0.95
        assert len(metrics.custom_metrics) == 3


class TestPredictionResult:
    """Tests for PredictionResult."""
    
    def test_basic_prediction(self):
        """Test basic prediction result."""
        result = PredictionResult(
            prediction=0.75,
            confidence=0.9,
            model_id="model-abc",
            model_version="v-123",
        )
        
        assert result.prediction == 0.75
        assert result.confidence == 0.9
        assert result.model_id == "model-abc"
    
    def test_prediction_with_bounds(self):
        """Test prediction with uncertainty bounds."""
        result = PredictionResult(
            prediction=100.0,
            confidence=0.85,
            lower_bound=90.0,
            upper_bound=110.0,
            std_dev=5.0,
        )
        
        assert result.lower_bound == 90.0
        assert result.upper_bound == 110.0
        assert result.std_dev == 5.0
    
    def test_prediction_with_explanation(self):
        """Test prediction with explanation."""
        result = PredictionResult(
            prediction="high_risk",
            confidence=0.95,
            feature_contributions={
                "cpu_usage": 0.3,
                "error_rate": 0.5,
                "memory_pressure": 0.2,
            },
            explanation="High risk due to elevated error rate",
        )
        
        assert result.prediction == "high_risk"
        assert result.feature_contributions["error_rate"] == 0.5
        assert "error rate" in result.explanation


class TestBatchPredictionResult:
    """Tests for BatchPredictionResult."""
    
    def test_batch_prediction(self):
        """Test batch prediction result."""
        predictions = [
            PredictionResult(prediction=0.5, confidence=0.8),
            PredictionResult(prediction=0.7, confidence=0.9),
            PredictionResult(prediction=0.3, confidence=0.7),
        ]
        
        result = BatchPredictionResult(
            predictions=predictions,
            batch_size=3,
            total_latency_ms=150.0,
            avg_latency_ms=50.0,
        )
        
        assert len(result.predictions) == 3
        assert result.batch_size == 3
        assert result.avg_latency_ms == 50.0
        assert result.success_rate() == 1.0
    
    def test_batch_with_failures(self):
        """Test batch with some failures."""
        predictions = [
            PredictionResult(prediction=0.5, confidence=0.8),
        ]
        
        result = BatchPredictionResult(
            predictions=predictions,
            batch_size=3,
            num_failures=2,
            failure_indices=[1, 2],
        )
        
        assert result.success_rate() == pytest.approx(0.333, rel=0.01)
        assert result.failure_indices == [1, 2]
    
    def test_empty_batch(self):
        """Test empty batch."""
        result = BatchPredictionResult(
            predictions=[],
            batch_size=0,
        )
        
        assert result.success_rate() == 0.0
