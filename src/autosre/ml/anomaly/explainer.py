"""Anomaly explanation module."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class ExplanationType(str, Enum):
    """Type of anomaly explanation."""
    STATISTICAL = "statistical"
    COMPARATIVE = "comparative"
    COUNTERFACTUAL = "counterfactual"
    FEATURE_CONTRIBUTION = "feature_contribution"


class AnomalyExplanation(BaseModel):
    """Explanation for an anomaly."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    explanation_id: str = Field(default_factory=generate_id)
    anomaly_id: str = Field(default="")
    
    # Type
    explanation_type: ExplanationType = Field(default=ExplanationType.STATISTICAL)
    
    # Summary
    summary: str = Field(default="")
    detailed_explanation: str = Field(default="")
    
    # Statistical info
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    deviation: Optional[float] = None
    z_score: Optional[float] = None
    percentile: Optional[float] = None
    
    # Feature contributions
    feature_contributions: dict[str, float] = Field(default_factory=dict)
    top_features: list[str] = Field(default_factory=list)
    
    # Comparison
    similar_normal_examples: list[dict[str, Any]] = Field(default_factory=list)
    nearest_normal_distance: float = Field(default=0.0)
    
    # Counterfactual
    counterfactual: dict[str, float] = Field(default_factory=dict)
    changes_needed: dict[str, float] = Field(default_factory=dict)
    
    # Context
    historical_context: str = Field(default="")
    baseline_period: str = Field(default="")
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Metadata
    generated_at: datetime = Field(default_factory=utc_now)


class AnomalyExplainer:
    """Generate explanations for detected anomalies.
    
    Provides multiple explanation types:
    - Statistical: z-scores, percentiles, deviation from mean
    - Comparative: comparison with similar normal examples
    - Counterfactual: what would need to change to be normal
    - Feature contribution: which features contribute most
    """
    
    def __init__(
        self,
        include_counterfactual: bool = True,
        include_similar_examples: bool = True,
        n_similar_examples: int = 3,
    ):
        """Initialize the explainer.
        
        Args:
            include_counterfactual: Generate counterfactual explanations
            include_similar_examples: Include similar normal examples
            n_similar_examples: Number of similar examples to show
        """
        self.include_counterfactual = include_counterfactual
        self.include_similar_examples = include_similar_examples
        self.n_similar_examples = n_similar_examples
        
        # Reference data
        self._reference_data: Optional[np.ndarray] = None
        self._reference_mean: Optional[np.ndarray] = None
        self._reference_std: Optional[np.ndarray] = None
        self._feature_names: List[str] = []
    
    def set_reference_data(
        self,
        data: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> None:
        """Set reference data for comparisons.
        
        Args:
            data: Normal reference data
            feature_names: Names of features
        """
        self._reference_data = np.asarray(data)
        if self._reference_data.ndim == 1:
            self._reference_data = self._reference_data.reshape(-1, 1)
        
        self._reference_mean = np.mean(self._reference_data, axis=0)
        self._reference_std = np.std(self._reference_data, axis=0)
        self._reference_std[self._reference_std == 0] = 1.0
        
        if feature_names:
            self._feature_names = feature_names
        else:
            self._feature_names = [f"feature_{i}" for i in range(self._reference_data.shape[1])]
    
    def explain(
        self,
        anomaly_values: np.ndarray,
        anomaly_id: str = "",
        anomaly_score: float = 0.0,
        metric_name: str = "",
        timestamp: Optional[datetime] = None,
    ) -> AnomalyExplanation:
        """Generate explanation for an anomaly.
        
        Args:
            anomaly_values: Values of the anomalous point
            anomaly_id: ID of the anomaly
            anomaly_score: Anomaly score
            metric_name: Name of metric (for univariate)
            timestamp: Timestamp of anomaly
            
        Returns:
            Anomaly explanation
        """
        anomaly_values = np.asarray(anomaly_values).flatten()
        
        # Statistical explanation
        statistical = self._generate_statistical_explanation(anomaly_values, metric_name)
        
        # Feature contributions
        contributions = self._calculate_feature_contributions(anomaly_values)
        
        # Similar examples
        similar_examples = []
        nearest_distance = 0.0
        if self.include_similar_examples and self._reference_data is not None:
            similar_examples, nearest_distance = self._find_similar_examples(anomaly_values)
        
        # Counterfactual
        counterfactual = {}
        changes_needed = {}
        if self.include_counterfactual and self._reference_mean is not None:
            counterfactual, changes_needed = self._generate_counterfactual(anomaly_values)
        
        # Generate summary
        summary = self._generate_summary(
            anomaly_values, statistical, contributions, metric_name
        )
        
        # Detailed explanation
        detailed = self._generate_detailed_explanation(
            anomaly_values, statistical, contributions, similar_examples
        )
        
        return AnomalyExplanation(
            anomaly_id=anomaly_id,
            explanation_type=ExplanationType.FEATURE_CONTRIBUTION,
            summary=summary,
            detailed_explanation=detailed,
            observed_value=float(anomaly_values[0]) if len(anomaly_values) == 1 else None,
            expected_value=float(self._reference_mean[0]) if self._reference_mean is not None and len(self._reference_mean) > 0 else None,
            deviation=statistical.get("deviation"),
            z_score=statistical.get("z_score"),
            percentile=statistical.get("percentile"),
            feature_contributions=contributions,
            top_features=list(sorted(contributions.keys(), key=lambda k: abs(contributions.get(k, 0)), reverse=True))[:5],
            similar_normal_examples=similar_examples,
            nearest_normal_distance=nearest_distance,
            counterfactual=counterfactual,
            changes_needed=changes_needed,
            confidence=min(anomaly_score, 1.0) if anomaly_score > 0 else 0.8,
        )
    
    def _generate_statistical_explanation(
        self,
        values: np.ndarray,
        metric_name: str,
    ) -> Dict[str, Any]:
        """Generate statistical explanation.
        
        Args:
            values: Anomaly values
            metric_name: Metric name
            
        Returns:
            Statistical info dictionary
        """
        if self._reference_mean is None:
            return {}
        
        result = {}
        
        # Overall z-score
        z_scores = (values - self._reference_mean[:len(values)]) / self._reference_std[:len(values)]
        
        if len(values) == 1:
            result["z_score"] = float(z_scores[0])
            result["deviation"] = float(values[0] - self._reference_mean[0])
            
            # Calculate percentile
            if self._reference_data is not None:
                percentile = np.mean(self._reference_data[:, 0] <= values[0]) * 100
                result["percentile"] = float(percentile)
        else:
            result["mean_z_score"] = float(np.mean(np.abs(z_scores)))
            result["max_z_score"] = float(np.max(np.abs(z_scores)))
        
        return result
    
    def _calculate_feature_contributions(
        self,
        values: np.ndarray,
    ) -> Dict[str, float]:
        """Calculate feature contributions to anomaly.
        
        Args:
            values: Anomaly values
            
        Returns:
            Feature contribution dictionary
        """
        if self._reference_mean is None or self._reference_std is None:
            return {}
        
        contributions = {}
        
        for i, name in enumerate(self._feature_names[:len(values)]):
            if i < len(values) and i < len(self._reference_mean):
                z = (values[i] - self._reference_mean[i]) / self._reference_std[i]
                contributions[name] = float(z)
        
        return contributions
    
    def _find_similar_examples(
        self,
        values: np.ndarray,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Find similar normal examples.
        
        Args:
            values: Anomaly values
            
        Returns:
            Tuple of (similar examples, nearest distance)
        """
        if self._reference_data is None:
            return [], 0.0
        
        # Calculate distances to all reference points
        # Normalize for comparison
        values_norm = (values - self._reference_mean[:len(values)]) / self._reference_std[:len(values)]
        ref_norm = (self._reference_data[:, :len(values)] - self._reference_mean[:len(values)]) / self._reference_std[:len(values)]
        
        distances = np.sqrt(np.sum((ref_norm - values_norm) ** 2, axis=1))
        
        # Get nearest neighbors
        nearest_indices = np.argsort(distances)[:self.n_similar_examples]
        
        similar_examples = []
        for idx in nearest_indices:
            example = {
                "values": {
                    name: float(self._reference_data[idx, i])
                    for i, name in enumerate(self._feature_names[:len(values)])
                },
                "distance": float(distances[idx]),
            }
            similar_examples.append(example)
        
        nearest_distance = float(distances[nearest_indices[0]]) if len(nearest_indices) > 0 else 0.0
        
        return similar_examples, nearest_distance
    
    def _generate_counterfactual(
        self,
        values: np.ndarray,
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Generate counterfactual explanation.
        
        What would need to change for this to be normal?
        
        Args:
            values: Anomaly values
            
        Returns:
            Tuple of (counterfactual values, changes needed)
        """
        if self._reference_mean is None:
            return {}, {}
        
        counterfactual = {}
        changes = {}
        
        for i, name in enumerate(self._feature_names[:len(values)]):
            if i < len(values) and i < len(self._reference_mean):
                # The counterfactual is simply the mean (most "normal" value)
                counterfactual[name] = float(self._reference_mean[i])
                changes[name] = float(self._reference_mean[i] - values[i])
        
        return counterfactual, changes
    
    def _generate_summary(
        self,
        values: np.ndarray,
        statistical: Dict[str, Any],
        contributions: Dict[str, float],
        metric_name: str,
    ) -> str:
        """Generate human-readable summary.
        
        Args:
            values: Anomaly values
            statistical: Statistical info
            contributions: Feature contributions
            metric_name: Metric name
            
        Returns:
            Summary string
        """
        parts = []
        
        if len(values) == 1:
            z = statistical.get("z_score", 0)
            if abs(z) > 3:
                direction = "above" if z > 0 else "below"
                parts.append(f"Value is significantly {direction} normal ({abs(z):.1f} standard deviations)")
        else:
            # Multi-feature
            top_contributors = sorted(
                contributions.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:3]
            
            if top_contributors:
                feature_str = ", ".join([f"{name}" for name, _ in top_contributors])
                parts.append(f"Main anomalous features: {feature_str}")
        
        percentile = statistical.get("percentile")
        if percentile is not None:
            if percentile > 99:
                parts.append(f"This value is higher than 99% of normal observations")
            elif percentile < 1:
                parts.append(f"This value is lower than 99% of normal observations")
        
        return ". ".join(parts) if parts else "Anomaly detected"
    
    def _generate_detailed_explanation(
        self,
        values: np.ndarray,
        statistical: Dict[str, Any],
        contributions: Dict[str, float],
        similar_examples: List[Dict[str, Any]],
    ) -> str:
        """Generate detailed explanation.
        
        Args:
            values: Anomaly values
            statistical: Statistical info
            contributions: Feature contributions
            similar_examples: Similar normal examples
            
        Returns:
            Detailed explanation string
        """
        parts = []
        
        # Statistical summary
        if statistical:
            z = statistical.get("z_score") or statistical.get("mean_z_score", 0)
            parts.append(f"Statistical deviation: z-score = {z:.2f}")
        
        # Feature breakdown
        if contributions:
            parts.append("\nFeature contributions to anomaly:")
            sorted_contribs = sorted(
                contributions.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )
            for name, z in sorted_contribs[:5]:
                direction = "↑" if z > 0 else "↓"
                parts.append(f"  • {name}: {direction} {abs(z):.2f} std devs")
        
        # Similar examples
        if similar_examples:
            parts.append(f"\nNearest normal example is at distance {similar_examples[0]['distance']:.2f}")
        
        return "\n".join(parts)
    
    def explain_batch(
        self,
        anomalies: List[Dict[str, Any]],
    ) -> List[AnomalyExplanation]:
        """Explain multiple anomalies.
        
        Args:
            anomalies: List of anomaly dictionaries
            
        Returns:
            List of explanations
        """
        explanations = []
        
        for anomaly in anomalies:
            values = np.asarray(anomaly.get("values", [0]))
            explanation = self.explain(
                values,
                anomaly_id=anomaly.get("id", ""),
                anomaly_score=anomaly.get("score", 0),
            )
            explanations.append(explanation)
        
        return explanations


# Import Tuple for type hints
from typing import Tuple
