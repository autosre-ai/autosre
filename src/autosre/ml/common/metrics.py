"""Model evaluation metrics and tracking."""

from datetime import datetime
from typing import Any, Optional, Dict, List
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now


class ConfusionMatrix(BaseModel):
    """Confusion matrix for classification."""
    model_config = ConfigDict(validate_assignment=True)
    
    true_positives: int = Field(default=0, ge=0)
    true_negatives: int = Field(default=0, ge=0)
    false_positives: int = Field(default=0, ge=0)
    false_negatives: int = Field(default=0, ge=0)
    
    # Multi-class
    matrix: Optional[list[list[int]]] = None
    labels: list[str] = Field(default_factory=list)
    
    @classmethod
    def from_predictions(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        labels: Optional[list[str]] = None,
    ) -> "ConfusionMatrix":
        """Create confusion matrix from predictions.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            labels: Class labels
            
        Returns:
            Confusion matrix
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        
        unique_labels = sorted(set(y_true) | set(y_pred))
        
        if labels is None:
            labels = [str(l) for l in unique_labels]
        
        n_classes = len(unique_labels)
        
        if n_classes == 2:
            # Binary classification
            tp = np.sum((y_true == unique_labels[1]) & (y_pred == unique_labels[1]))
            tn = np.sum((y_true == unique_labels[0]) & (y_pred == unique_labels[0]))
            fp = np.sum((y_true == unique_labels[0]) & (y_pred == unique_labels[1]))
            fn = np.sum((y_true == unique_labels[1]) & (y_pred == unique_labels[0]))
            
            return cls(
                true_positives=int(tp),
                true_negatives=int(tn),
                false_positives=int(fp),
                false_negatives=int(fn),
                labels=labels,
            )
        else:
            # Multi-class
            matrix = np.zeros((n_classes, n_classes), dtype=int)
            label_to_idx = {l: i for i, l in enumerate(unique_labels)}
            
            for true, pred in zip(y_true, y_pred):
                i = label_to_idx[true]
                j = label_to_idx[pred]
                matrix[i, j] += 1
            
            return cls(
                matrix=matrix.tolist(),
                labels=labels,
            )
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy."""
        if self.matrix is not None:
            matrix = np.array(self.matrix)
            return float(np.trace(matrix) / np.sum(matrix))
        
        total = self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total
    
    @property
    def precision(self) -> float:
        """Calculate precision."""
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return 0.0
        return self.true_positives / denom
    
    @property
    def recall(self) -> float:
        """Calculate recall (sensitivity)."""
        denom = self.true_positives + self.false_negatives
        if denom == 0:
            return 0.0
        return self.true_positives / denom
    
    @property
    def f1_score(self) -> float:
        """Calculate F1 score."""
        p = self.precision
        r = self.recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)
    
    @property
    def specificity(self) -> float:
        """Calculate specificity."""
        denom = self.true_negatives + self.false_positives
        if denom == 0:
            return 0.0
        return self.true_negatives / denom


class RegressionMetrics(BaseModel):
    """Metrics for regression models."""
    model_config = ConfigDict(validate_assignment=True)
    
    mse: float = Field(default=0.0)
    rmse: float = Field(default=0.0)
    mae: float = Field(default=0.0)
    mape: Optional[float] = None
    smape: Optional[float] = None
    r2_score: float = Field(default=0.0)
    explained_variance: float = Field(default=0.0)
    max_error: float = Field(default=0.0)
    
    # Additional
    sample_size: int = Field(default=0, ge=0)
    computed_at: datetime = Field(default_factory=utc_now)
    
    @classmethod
    def compute(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> "RegressionMetrics":
        """Compute regression metrics.
        
        Args:
            y_true: True values
            y_pred: Predicted values
            
        Returns:
            Regression metrics
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        
        n = len(y_true)
        
        # Basic errors
        errors = y_true - y_pred
        abs_errors = np.abs(errors)
        sq_errors = errors ** 2
        
        mse = float(np.mean(sq_errors))
        rmse = float(np.sqrt(mse))
        mae = float(np.mean(abs_errors))
        max_error = float(np.max(abs_errors))
        
        # MAPE (avoid division by zero)
        mask = y_true != 0
        if np.any(mask):
            mape = float(np.mean(np.abs(errors[mask] / y_true[mask])) * 100)
        else:
            mape = None
        
        # SMAPE (symmetric MAPE)
        denom = np.abs(y_true) + np.abs(y_pred)
        mask = denom != 0
        if np.any(mask):
            smape = float(np.mean(2 * abs_errors[mask] / denom[mask]) * 100)
        else:
            smape = None
        
        # R² score
        ss_res = np.sum(sq_errors)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        
        # Explained variance
        var_res = np.var(errors)
        var_tot = np.var(y_true)
        explained_var = 1 - (var_res / var_tot) if var_tot != 0 else 0.0
        
        return cls(
            mse=mse,
            rmse=rmse,
            mae=mae,
            mape=mape,
            smape=smape,
            r2_score=float(r2),
            explained_variance=float(explained_var),
            max_error=max_error,
            sample_size=n,
        )


class ClassificationMetrics(BaseModel):
    """Metrics for classification models."""
    model_config = ConfigDict(validate_assignment=True)
    
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    f1_score: float = Field(default=0.0, ge=0.0, le=1.0)
    specificity: Optional[float] = None
    
    # Per-class metrics
    per_class_precision: dict[str, float] = Field(default_factory=dict)
    per_class_recall: dict[str, float] = Field(default_factory=dict)
    per_class_f1: dict[str, float] = Field(default_factory=dict)
    
    # AUC
    auc_roc: Optional[float] = None
    auc_pr: Optional[float] = None
    
    # Additional
    confusion_matrix: Optional[ConfusionMatrix] = None
    sample_size: int = Field(default=0, ge=0)
    computed_at: datetime = Field(default_factory=utc_now)
    
    @classmethod
    def compute(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: Optional[np.ndarray] = None,
        labels: Optional[list[str]] = None,
    ) -> "ClassificationMetrics":
        """Compute classification metrics.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_prob: Predicted probabilities (for AUC)
            labels: Class labels
            
        Returns:
            Classification metrics
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        
        n = len(y_true)
        unique_labels = sorted(set(y_true) | set(y_pred))
        
        if labels is None:
            labels = [str(l) for l in unique_labels]
        
        # Confusion matrix
        cm = ConfusionMatrix.from_predictions(y_true, y_pred, labels)
        
        # Overall metrics
        accuracy = float(np.mean(y_true == y_pred))
        
        # Per-class metrics
        per_class_precision = {}
        per_class_recall = {}
        per_class_f1 = {}
        
        for i, label in enumerate(unique_labels):
            tp = np.sum((y_true == label) & (y_pred == label))
            fp = np.sum((y_true != label) & (y_pred == label))
            fn = np.sum((y_true == label) & (y_pred != label))
            
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            
            per_class_precision[labels[i] if i < len(labels) else str(label)] = float(prec)
            per_class_recall[labels[i] if i < len(labels) else str(label)] = float(rec)
            per_class_f1[labels[i] if i < len(labels) else str(label)] = float(f1)
        
        # Macro-averaged metrics
        precision = float(np.mean(list(per_class_precision.values())))
        recall = float(np.mean(list(per_class_recall.values())))
        f1_score = float(np.mean(list(per_class_f1.values())))
        
        # AUC-ROC (binary only, or with probabilities)
        auc_roc = None
        if y_prob is not None and len(unique_labels) == 2:
            try:
                # Simple AUC calculation
                y_prob = np.asarray(y_prob).flatten()
                pos_label = unique_labels[1]
                pos_mask = y_true == pos_label
                
                # Sort by probability
                sorted_indices = np.argsort(y_prob)[::-1]
                sorted_labels = pos_mask[sorted_indices]
                
                # Calculate AUC using trapezoidal rule
                tpr = np.cumsum(sorted_labels) / np.sum(pos_mask)
                fpr = np.cumsum(~sorted_labels) / np.sum(~pos_mask)
                
                auc_roc = float(np.trapz(tpr, fpr))
            except Exception:
                pass
        
        return cls(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            specificity=cm.specificity if hasattr(cm, 'specificity') else None,
            per_class_precision=per_class_precision,
            per_class_recall=per_class_recall,
            per_class_f1=per_class_f1,
            auc_roc=auc_roc,
            confusion_matrix=cm,
            sample_size=n,
        )


class TimeSeriesMetrics(BaseModel):
    """Metrics for time series forecasting."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Standard regression metrics
    mse: float = Field(default=0.0)
    rmse: float = Field(default=0.0)
    mae: float = Field(default=0.0)
    mape: Optional[float] = None
    smape: Optional[float] = None
    
    # Time series specific
    mase: Optional[float] = None  # Mean Absolute Scaled Error
    wape: Optional[float] = None  # Weighted Absolute Percentage Error
    
    # Directional accuracy
    directional_accuracy: float = Field(default=0.0)
    
    # By horizon
    horizon_rmse: dict[int, float] = Field(default_factory=dict)
    horizon_mae: dict[int, float] = Field(default_factory=dict)
    
    # Additional
    forecast_horizon: int = Field(default=1, ge=1)
    sample_size: int = Field(default=0, ge=0)
    computed_at: datetime = Field(default_factory=utc_now)
    
    @classmethod
    def compute(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_naive: Optional[np.ndarray] = None,
        forecast_horizon: int = 1,
    ) -> "TimeSeriesMetrics":
        """Compute time series forecasting metrics.
        
        Args:
            y_true: True values
            y_pred: Predicted values
            y_naive: Naive forecast (for MASE)
            forecast_horizon: Forecast horizon
            
        Returns:
            Time series metrics
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        
        n = len(y_true)
        
        # Basic metrics
        errors = y_true - y_pred
        abs_errors = np.abs(errors)
        sq_errors = errors ** 2
        
        mse = float(np.mean(sq_errors))
        rmse = float(np.sqrt(mse))
        mae = float(np.mean(abs_errors))
        
        # MAPE
        mask = y_true != 0
        mape = float(np.mean(np.abs(errors[mask] / y_true[mask])) * 100) if np.any(mask) else None
        
        # SMAPE
        denom = np.abs(y_true) + np.abs(y_pred)
        mask = denom != 0
        smape = float(np.mean(2 * abs_errors[mask] / denom[mask]) * 100) if np.any(mask) else None
        
        # WAPE
        wape = float(np.sum(abs_errors) / np.sum(np.abs(y_true)) * 100) if np.sum(np.abs(y_true)) > 0 else None
        
        # MASE
        mase = None
        if y_naive is not None:
            y_naive = np.asarray(y_naive).flatten()
            naive_errors = np.abs(y_true - y_naive)
            naive_mae = np.mean(naive_errors)
            if naive_mae > 0:
                mase = float(mae / naive_mae)
        
        # Directional accuracy
        if n > 1:
            true_direction = np.diff(y_true) > 0
            pred_direction = np.diff(y_pred) > 0
            directional_accuracy = float(np.mean(true_direction == pred_direction))
        else:
            directional_accuracy = 0.0
        
        return cls(
            mse=mse,
            rmse=rmse,
            mae=mae,
            mape=mape,
            smape=smape,
            mase=mase,
            wape=wape,
            directional_accuracy=directional_accuracy,
            forecast_horizon=forecast_horizon,
            sample_size=n,
        )


class ModelMetrics(BaseModel):
    """Combined model metrics."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    model_id: str = Field(default="")
    model_version: str = Field(default="")
    
    # Different metric types
    regression: Optional[RegressionMetrics] = None
    classification: Optional[ClassificationMetrics] = None
    time_series: Optional[TimeSeriesMetrics] = None
    
    # Custom metrics
    custom: dict[str, float] = Field(default_factory=dict)
    
    # Evaluation context
    dataset_name: str = Field(default="")
    dataset_size: int = Field(default=0, ge=0)
    evaluation_time_ms: float = Field(default=0.0, ge=0.0)
    evaluated_at: datetime = Field(default_factory=utc_now)
    
    def to_dict(self) -> dict[str, float]:
        """Convert all metrics to a flat dictionary."""
        result = {}
        
        if self.regression:
            for field in self.regression.model_fields:
                value = getattr(self.regression, field)
                if isinstance(value, (int, float)) and value is not None:
                    result[f"regression_{field}"] = float(value)
        
        if self.classification:
            for field in self.classification.model_fields:
                value = getattr(self.classification, field)
                if isinstance(value, (int, float)) and value is not None:
                    result[f"classification_{field}"] = float(value)
        
        if self.time_series:
            for field in self.time_series.model_fields:
                value = getattr(self.time_series, field)
                if isinstance(value, (int, float)) and value is not None:
                    result[f"ts_{field}"] = float(value)
        
        result.update(self.custom)
        
        return result


class MetricsTracker:
    """Track metrics over time for experiments and A/B testing."""
    
    def __init__(self, experiment_name: str = "default"):
        """Initialize the tracker.
        
        Args:
            experiment_name: Name of the experiment
        """
        self.experiment_name = experiment_name
        self._history: list[ModelMetrics] = []
        self._best_metrics: dict[str, tuple[float, ModelMetrics]] = {}
    
    def log(self, metrics: ModelMetrics) -> None:
        """Log metrics.
        
        Args:
            metrics: Metrics to log
        """
        self._history.append(metrics)
        
        # Update best metrics
        flat_metrics = metrics.to_dict()
        for name, value in flat_metrics.items():
            if name not in self._best_metrics:
                self._best_metrics[name] = (value, metrics)
            else:
                # Assume higher is better (can be customized)
                if value > self._best_metrics[name][0]:
                    self._best_metrics[name] = (value, metrics)
    
    def get_history(self) -> list[ModelMetrics]:
        """Get metric history.
        
        Returns:
            List of logged metrics
        """
        return self._history
    
    def get_best(self, metric_name: str) -> Optional[ModelMetrics]:
        """Get best metrics for a given metric.
        
        Args:
            metric_name: Name of the metric to optimize
            
        Returns:
            Metrics with best value, or None
        """
        if metric_name in self._best_metrics:
            return self._best_metrics[metric_name][1]
        return None
    
    def compare(
        self,
        model_a_id: str,
        model_b_id: str,
    ) -> dict[str, Any]:
        """Compare two models based on logged metrics.
        
        Args:
            model_a_id: First model ID
            model_b_id: Second model ID
            
        Returns:
            Comparison results
        """
        metrics_a = [m for m in self._history if m.model_id == model_a_id]
        metrics_b = [m for m in self._history if m.model_id == model_b_id]
        
        if not metrics_a or not metrics_b:
            return {"error": "One or both models not found in history"}
        
        # Get latest metrics for each
        latest_a = metrics_a[-1]
        latest_b = metrics_b[-1]
        
        dict_a = latest_a.to_dict()
        dict_b = latest_b.to_dict()
        
        comparison = {}
        all_metrics = set(dict_a.keys()) | set(dict_b.keys())
        
        for metric in all_metrics:
            val_a = dict_a.get(metric)
            val_b = dict_b.get(metric)
            
            if val_a is not None and val_b is not None:
                diff = val_b - val_a
                pct_change = (diff / val_a * 100) if val_a != 0 else float("inf")
                comparison[metric] = {
                    "model_a": val_a,
                    "model_b": val_b,
                    "difference": diff,
                    "percent_change": pct_change,
                    "better": "a" if val_a > val_b else ("b" if val_b > val_a else "equal"),
                }
        
        return {
            "model_a_id": model_a_id,
            "model_b_id": model_b_id,
            "metrics": comparison,
        }
    
    def summary(self) -> dict[str, Any]:
        """Get summary statistics of tracked metrics.
        
        Returns:
            Summary statistics
        """
        if not self._history:
            return {"error": "No metrics logged"}
        
        all_dicts = [m.to_dict() for m in self._history]
        all_metrics = set()
        for d in all_dicts:
            all_metrics.update(d.keys())
        
        summary = {}
        for metric in all_metrics:
            values = [d.get(metric) for d in all_dicts if d.get(metric) is not None]
            if values:
                summary[metric] = {
                    "count": len(values),
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }
        
        return {
            "experiment_name": self.experiment_name,
            "total_entries": len(self._history),
            "metrics": summary,
        }
    
    def clear(self) -> None:
        """Clear all tracked metrics."""
        self._history.clear()
        self._best_metrics.clear()
