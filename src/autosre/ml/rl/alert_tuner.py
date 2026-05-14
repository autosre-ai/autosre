"""Alert threshold tuning using reinforcement learning.

Learns optimal alert thresholds to:
- Minimize false positives
- Avoid missing true incidents
- Adapt to service behavior
- Account for seasonality
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, List, Dict, Tuple
import math

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class AlertOutcome(str, Enum):
    """Outcome of an alert."""
    TRUE_POSITIVE = "true_positive"  # Real incident
    FALSE_POSITIVE = "false_positive"  # No real incident
    TRUE_NEGATIVE = "true_negative"  # Correctly no alert
    FALSE_NEGATIVE = "false_negative"  # Missed incident


class ThresholdAction(str, Enum):
    """Actions for threshold adjustment."""
    INCREASE_LARGE = "increase_large"
    INCREASE_SMALL = "increase_small"
    NO_CHANGE = "no_change"
    DECREASE_SMALL = "decrease_small"
    DECREASE_LARGE = "decrease_large"


class AlertType(str, Enum):
    """Type of alert being tuned."""
    CPU_HIGH = "cpu_high"
    MEMORY_HIGH = "memory_high"
    LATENCY_HIGH = "latency_high"
    ERROR_RATE_HIGH = "error_rate_high"
    REQUEST_RATE_HIGH = "request_rate_high"
    DISK_HIGH = "disk_high"
    CUSTOM = "custom"


class AlertState(BaseModel):
    """State for alert threshold tuning."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Alert identification
    alert_name: str = Field(default="")
    alert_type: AlertType = Field(default=AlertType.CUSTOM)
    service_name: str = Field(default="")
    
    # Current threshold
    current_threshold: float = Field(default=0.0)
    threshold_min: float = Field(default=0.0)
    threshold_max: float = Field(default=100.0)
    
    # Alert history
    alerts_last_24h: int = Field(default=0, ge=0)
    alerts_last_7d: int = Field(default=0, ge=0)
    true_positives_last_7d: int = Field(default=0, ge=0)
    false_positives_last_7d: int = Field(default=0, ge=0)
    
    # Current metric value
    current_metric_value: float = Field(default=0.0)
    
    # Metric statistics
    avg_metric_24h: float = Field(default=0.0)
    std_metric_24h: float = Field(default=0.0)
    max_metric_24h: float = Field(default=0.0)
    p99_metric_24h: float = Field(default=0.0)
    
    # Time features
    hour_of_day: int = Field(default=12, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    is_business_hours: bool = Field(default=True)
    
    # Incident correlation
    incidents_last_7d: int = Field(default=0, ge=0)
    incident_correlation: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Team feedback
    silenced_count_7d: int = Field(default=0, ge=0)
    acknowledged_within_5min_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    def to_vector(self) -> np.ndarray:
        """Convert state to feature vector."""
        # Normalize threshold position
        threshold_range = self.threshold_max - self.threshold_min
        normalized_threshold = (
            (self.current_threshold - self.threshold_min) / threshold_range
            if threshold_range > 0 else 0.5
        )
        
        # Calculate precision and recall estimates
        total_alerts = self.true_positives_last_7d + self.false_positives_last_7d
        precision = (
            self.true_positives_last_7d / total_alerts
            if total_alerts > 0 else 0.5
        )
        
        # Metric relative to threshold
        metric_to_threshold = (
            self.current_metric_value / self.current_threshold
            if self.current_threshold > 0 else 0
        )
        
        return np.array([
            # Threshold position (1)
            normalized_threshold,
            
            # Alert statistics (4)
            min(1.0, self.alerts_last_24h / 50.0),
            min(1.0, self.alerts_last_7d / 200.0),
            precision,
            min(1.0, self.false_positives_last_7d / 50.0),
            
            # Metric values (5)
            min(1.0, self.current_metric_value / 100.0),
            min(1.0, self.avg_metric_24h / 100.0),
            min(1.0, self.std_metric_24h / 50.0),
            min(1.0, self.max_metric_24h / 100.0),
            min(1.0, metric_to_threshold),
            
            # Time features (3)
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
            float(self.is_business_hours),
            
            # Incident correlation (2)
            min(1.0, self.incidents_last_7d / 20.0),
            self.incident_correlation,
            
            # Team feedback (2)
            min(1.0, self.silenced_count_7d / 20.0),
            self.acknowledged_within_5min_rate,
        ])
    
    @property
    def state_dimension(self) -> int:
        """Get state dimension."""
        return 17


class AlertTuning(BaseModel):
    """Result of alert tuning decision."""
    model_config = ConfigDict(validate_assignment=True)
    
    tuning_id: str = Field(default_factory=generate_id)
    
    # Alert info
    alert_name: str = Field(default="")
    alert_type: AlertType = Field(default=AlertType.CUSTOM)
    
    # Action
    action: ThresholdAction = Field(default=ThresholdAction.NO_CHANGE)
    
    # Threshold changes
    current_threshold: float = Field(default=0.0)
    recommended_threshold: float = Field(default=0.0)
    change_amount: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_improvement: float = Field(default=0.0)
    
    # Explanation
    reason: str = Field(default="")
    factors: List[str] = Field(default_factory=list)
    
    # Predicted impact
    predicted_alert_reduction: float = Field(default=0.0)
    predicted_miss_rate_change: float = Field(default=0.0)
    
    # Metadata
    decided_at: datetime = Field(default_factory=utc_now)


class AlertThresholdPolicy(BaseModel):
    """Learned policy for an alert type."""
    model_config = ConfigDict(validate_assignment=True)
    
    policy_id: str = Field(default_factory=generate_id)
    alert_type: AlertType = Field(default=AlertType.CUSTOM)
    
    # Learned thresholds by time
    default_threshold: float = Field(default=80.0)
    business_hours_threshold: float = Field(default=75.0)
    off_hours_threshold: float = Field(default=85.0)
    
    # Adjustment factors
    high_traffic_multiplier: float = Field(default=1.1)
    low_traffic_multiplier: float = Field(default=0.9)
    
    # Constraints
    min_threshold: float = Field(default=50.0)
    max_threshold: float = Field(default=95.0)
    max_change_per_update: float = Field(default=5.0)
    
    # Performance metrics
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    f1_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Training info
    total_updates: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=utc_now)


class AlertTuner:
    """Reinforcement learning agent for alert threshold tuning.
    
    Goals:
    - Maximize precision (minimize false positives)
    - Maintain recall (don't miss real incidents)
    - Adapt to service patterns
    - Learn from team feedback
    
    Uses contextual bandits with Thompson sampling.
    """
    
    def __init__(
        self,
        learning_rate: float = 0.01,
        exploration_rate: float = 0.2,
        min_exploration: float = 0.05,
        exploration_decay: float = 0.998,
        false_positive_weight: float = 1.0,
        false_negative_weight: float = 5.0,  # Missing incidents is worse
    ):
        """Initialize the alert tuner.
        
        Args:
            learning_rate: Learning rate for updates
            exploration_rate: Initial exploration rate
            min_exploration: Minimum exploration rate
            exploration_decay: Decay rate for exploration
            false_positive_weight: Weight for false positive penalty
            false_negative_weight: Weight for false negative penalty
        """
        self.learning_rate = learning_rate
        self.exploration_rate = exploration_rate
        self.min_exploration = min_exploration
        self.exploration_decay = exploration_decay
        self.false_positive_weight = false_positive_weight
        self.false_negative_weight = false_negative_weight
        
        # State and action dimensions
        self._state_dim = 17
        self._n_actions = 5  # 5 threshold actions
        
        # Q-network weights
        self._weights = np.zeros((self._n_actions, self._state_dim))
        
        # Action history for bandits
        self._action_counts = np.ones(self._n_actions)  # Start at 1 to avoid div by 0
        self._action_rewards = np.zeros(self._n_actions)
        
        # Experience buffer per alert type
        self._experiences: Dict[AlertType, List[Tuple]] = {t: [] for t in AlertType}
        self._max_experience_per_type = 1000
        
        # Policies per alert type
        self._policies: Dict[AlertType, AlertThresholdPolicy] = {}
        
        # Statistics
        self._total_tunings = 0
        self._outcomes: List[Tuple[AlertType, AlertOutcome]] = []
    
    def _get_action_change(
        self,
        action: ThresholdAction,
        current_threshold: float,
    ) -> float:
        """Get threshold change for action.
        
        Args:
            action: Threshold action
            current_threshold: Current threshold value
            
        Returns:
            Change amount
        """
        # Base changes (percentage of current)
        changes = {
            ThresholdAction.INCREASE_LARGE: 0.10,
            ThresholdAction.INCREASE_SMALL: 0.03,
            ThresholdAction.NO_CHANGE: 0.0,
            ThresholdAction.DECREASE_SMALL: -0.03,
            ThresholdAction.DECREASE_LARGE: -0.10,
        }
        
        return current_threshold * changes[action]
    
    def _action_to_index(self, action: ThresholdAction) -> int:
        """Convert action to index."""
        return list(ThresholdAction).index(action)
    
    def _index_to_action(self, index: int) -> ThresholdAction:
        """Convert index to action."""
        return list(ThresholdAction)[index]
    
    def _get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for state.
        
        Args:
            state: State vector
            
        Returns:
            Q-values
        """
        return np.dot(self._weights, state)
    
    def _thompson_sample(self) -> int:
        """Select action using Thompson sampling.
        
        Returns:
            Action index
        """
        # Calculate posterior parameters
        means = self._action_rewards / self._action_counts
        stds = 1.0 / np.sqrt(self._action_counts)
        
        # Sample from posteriors
        samples = np.random.normal(means, stds)
        
        return int(np.argmax(samples))
    
    def _select_action(
        self,
        state: np.ndarray,
        explore: bool = True,
    ) -> int:
        """Select action.
        
        Args:
            state: State vector
            explore: Whether to explore
            
        Returns:
            Action index
        """
        if explore and np.random.random() < self.exploration_rate:
            # Use Thompson sampling for exploration
            return self._thompson_sample()
        
        # Exploit: use Q-values
        q_values = self._get_q_values(state)
        return int(np.argmax(q_values))
    
    def tune(
        self,
        state: AlertState,
        explore: bool = True,
    ) -> AlertTuning:
        """Make threshold tuning decision.
        
        Args:
            state: Current alert state
            explore: Whether to explore
            
        Returns:
            Tuning decision
        """
        state_vector = state.to_vector()
        action_idx = self._select_action(state_vector, explore)
        action = self._index_to_action(action_idx)
        
        # Calculate threshold change
        change_amount = self._get_action_change(action, state.current_threshold)
        
        # Apply constraints
        recommended_threshold = state.current_threshold + change_amount
        recommended_threshold = max(state.threshold_min, min(state.threshold_max, recommended_threshold))
        
        # Recalculate actual change
        actual_change = recommended_threshold - state.current_threshold
        change_percent = (
            actual_change / state.current_threshold * 100
            if state.current_threshold > 0 else 0
        )
        
        # Get confidence
        q_values = self._get_q_values(state_vector)
        exp_q = np.exp(q_values - np.max(q_values))
        probs = exp_q / np.sum(exp_q)
        confidence = float(probs[action_idx])
        
        # Generate explanation
        reason, factors = self._generate_explanation(state, action)
        
        # Predict impact
        predicted_reduction, miss_rate_change = self._predict_impact(
            state, recommended_threshold
        )
        
        self._total_tunings += 1
        
        return AlertTuning(
            alert_name=state.alert_name,
            alert_type=state.alert_type,
            action=action,
            current_threshold=state.current_threshold,
            recommended_threshold=recommended_threshold,
            change_amount=actual_change,
            change_percent=change_percent,
            confidence=confidence,
            expected_improvement=float(q_values[action_idx]),
            reason=reason,
            factors=factors,
            predicted_alert_reduction=predicted_reduction,
            predicted_miss_rate_change=miss_rate_change,
        )
    
    def _generate_explanation(
        self,
        state: AlertState,
        action: ThresholdAction,
    ) -> Tuple[str, List[str]]:
        """Generate explanation for tuning decision.
        
        Args:
            state: Current state
            action: Chosen action
            
        Returns:
            Tuple of (reason, factors)
        """
        factors = []
        
        # Calculate precision
        total_alerts = state.true_positives_last_7d + state.false_positives_last_7d
        if total_alerts > 0:
            precision = state.true_positives_last_7d / total_alerts
            if precision < 0.5:
                factors.append(f"Low precision: {precision:.1%}")
            elif precision > 0.9:
                factors.append(f"High precision: {precision:.1%}")
        
        # Alert volume
        if state.alerts_last_24h > 20:
            factors.append(f"High alert volume: {state.alerts_last_24h} in 24h")
        elif state.alerts_last_24h == 0:
            factors.append("No alerts in 24h")
        
        # Silenced alerts
        if state.silenced_count_7d > 5:
            factors.append(f"Frequently silenced: {state.silenced_count_7d} times")
        
        # Metric proximity to threshold
        if state.current_threshold > 0:
            proximity = state.current_metric_value / state.current_threshold
            if proximity > 0.95:
                factors.append("Metric near threshold")
            elif proximity < 0.5:
                factors.append("Metric well below threshold")
        
        # False positive rate
        if state.false_positives_last_7d > 10:
            factors.append(f"High false positives: {state.false_positives_last_7d}")
        
        # Generate reason
        if action in [ThresholdAction.INCREASE_LARGE, ThresholdAction.INCREASE_SMALL]:
            if state.false_positives_last_7d > state.true_positives_last_7d:
                reason = "Increasing threshold to reduce false positive alerts"
            else:
                reason = "Increasing threshold based on metric distribution"
        elif action in [ThresholdAction.DECREASE_LARGE, ThresholdAction.DECREASE_SMALL]:
            if state.incident_correlation < 0.3:
                reason = "Decreasing threshold to improve incident detection"
            else:
                reason = "Decreasing threshold to catch issues earlier"
        else:
            reason = "Maintaining current threshold - optimal balance"
        
        return reason, factors
    
    def _predict_impact(
        self,
        state: AlertState,
        new_threshold: float,
    ) -> Tuple[float, float]:
        """Predict impact of threshold change.
        
        Args:
            state: Current state
            new_threshold: New threshold value
            
        Returns:
            Tuple of (predicted alert reduction %, predicted miss rate change %)
        """
        if state.current_threshold == 0:
            return 0.0, 0.0
        
        threshold_change_pct = (new_threshold - state.current_threshold) / state.current_threshold
        
        # Simple model: increasing threshold reduces alerts
        # but may increase missed incidents
        if threshold_change_pct > 0:
            # Increasing threshold
            alert_reduction = min(0.5, threshold_change_pct * 2)  # Up to 50% reduction
            miss_rate_change = threshold_change_pct * 0.5  # Some increase in misses
        elif threshold_change_pct < 0:
            # Decreasing threshold
            alert_reduction = threshold_change_pct * 2  # Negative = more alerts
            miss_rate_change = threshold_change_pct * 0.3  # Less misses
        else:
            alert_reduction = 0.0
            miss_rate_change = 0.0
        
        return alert_reduction, miss_rate_change
    
    def record_outcome(
        self,
        state: AlertState,
        action: ThresholdAction,
        outcome: AlertOutcome,
    ) -> None:
        """Record outcome of alert with current threshold.
        
        Args:
            state: State when decision was made
            action: Action taken
            outcome: Outcome of alert
        """
        # Calculate reward
        reward = self._calculate_reward(outcome)
        
        # Update action statistics (for Thompson sampling)
        action_idx = self._action_to_index(action)
        self._action_counts[action_idx] += 1
        self._action_rewards[action_idx] += reward
        
        # Store experience
        state_vector = state.to_vector()
        self._experiences[state.alert_type].append((
            state_vector,
            action_idx,
            reward,
        ))
        
        # Limit experience buffer
        if len(self._experiences[state.alert_type]) > self._max_experience_per_type:
            self._experiences[state.alert_type].pop(0)
        
        # Record outcome
        self._outcomes.append((state.alert_type, outcome))
        
        # Update Q-values
        current_q = self._get_q_values(state_vector)[action_idx]
        td_error = reward - current_q
        self._weights[action_idx] += self.learning_rate * td_error * state_vector
        
        # Decay exploration
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay,
        )
        
        # Update policy metrics
        self._update_policy_metrics(state.alert_type)
    
    def _calculate_reward(self, outcome: AlertOutcome) -> float:
        """Calculate reward for outcome.
        
        Args:
            outcome: Alert outcome
            
        Returns:
            Reward value
        """
        rewards = {
            AlertOutcome.TRUE_POSITIVE: 2.0,  # Good: caught real issue
            AlertOutcome.TRUE_NEGATIVE: 1.0,  # Good: no noise
            AlertOutcome.FALSE_POSITIVE: -self.false_positive_weight,
            AlertOutcome.FALSE_NEGATIVE: -self.false_negative_weight,
        }
        return rewards[outcome]
    
    def _update_policy_metrics(self, alert_type: AlertType) -> None:
        """Update policy metrics.
        
        Args:
            alert_type: Alert type to update
        """
        # Get recent outcomes for this alert type
        recent = [o for t, o in self._outcomes[-1000:] if t == alert_type]
        
        if not recent:
            return
        
        # Calculate metrics
        tp = sum(1 for o in recent if o == AlertOutcome.TRUE_POSITIVE)
        fp = sum(1 for o in recent if o == AlertOutcome.FALSE_POSITIVE)
        fn = sum(1 for o in recent if o == AlertOutcome.FALSE_NEGATIVE)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Update or create policy
        if alert_type not in self._policies:
            self._policies[alert_type] = AlertThresholdPolicy(alert_type=alert_type)
        
        policy = self._policies[alert_type]
        policy.precision = precision
        policy.recall = recall
        policy.f1_score = f1
        policy.total_updates += 1
        policy.last_updated = utc_now()
    
    def get_policy(self, alert_type: AlertType) -> AlertThresholdPolicy:
        """Get policy for alert type.
        
        Args:
            alert_type: Alert type
            
        Returns:
            Policy for alert type
        """
        if alert_type not in self._policies:
            self._policies[alert_type] = AlertThresholdPolicy(alert_type=alert_type)
        return self._policies[alert_type]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tuning statistics.
        
        Returns:
            Statistics dictionary
        """
        # Overall stats
        total_outcomes = len(self._outcomes)
        if total_outcomes > 0:
            tp = sum(1 for _, o in self._outcomes if o == AlertOutcome.TRUE_POSITIVE)
            fp = sum(1 for _, o in self._outcomes if o == AlertOutcome.FALSE_POSITIVE)
            tn = sum(1 for _, o in self._outcomes if o == AlertOutcome.TRUE_NEGATIVE)
            fn = sum(1 for _, o in self._outcomes if o == AlertOutcome.FALSE_NEGATIVE)
        else:
            tp = fp = tn = fn = 0
        
        return {
            "total_tunings": self._total_tunings,
            "total_outcomes": total_outcomes,
            "exploration_rate": self.exploration_rate,
            "outcomes": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
            },
            "precision": tp / (tp + fp) if (tp + fp) > 0 else 0,
            "recall": tp / (tp + fn) if (tp + fn) > 0 else 0,
            "action_distribution": {
                a.value: int(self._action_counts[i])
                for i, a in enumerate(ThresholdAction)
            },
            "policies": {
                t.value: p.model_dump()
                for t, p in self._policies.items()
            },
        }
    
    def save(self, path: str) -> None:
        """Save tuner to disk.
        
        Args:
            path: Save path
        """
        import json
        
        data = {
            "weights": self._weights.tolist(),
            "action_counts": self._action_counts.tolist(),
            "action_rewards": self._action_rewards.tolist(),
            "exploration_rate": self.exploration_rate,
            "total_tunings": self._total_tunings,
            "policies": {
                t.value: p.model_dump()
                for t, p in self._policies.items()
            },
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "min_exploration": self.min_exploration,
                "exploration_decay": self.exploration_decay,
                "false_positive_weight": self.false_positive_weight,
                "false_negative_weight": self.false_negative_weight,
            },
        }
        
        with open(path, "w") as f:
            json.dump(data, f, default=str)
    
    def load(self, path: str) -> None:
        """Load tuner from disk.
        
        Args:
            path: Load path
        """
        import json
        
        with open(path) as f:
            data = json.load(f)
        
        self._weights = np.array(data["weights"])
        self._action_counts = np.array(data["action_counts"])
        self._action_rewards = np.array(data["action_rewards"])
        self.exploration_rate = data.get("exploration_rate", self.min_exploration)
        self._total_tunings = data.get("total_tunings", 0)
        
        if "policies" in data:
            for type_str, policy_data in data["policies"].items():
                alert_type = AlertType(type_str)
                self._policies[alert_type] = AlertThresholdPolicy(**policy_data)
        
        if "hyperparameters" in data:
            hp = data["hyperparameters"]
            self.learning_rate = hp.get("learning_rate", self.learning_rate)
            self.min_exploration = hp.get("min_exploration", self.min_exploration)
            self.exploration_decay = hp.get("exploration_decay", self.exploration_decay)
            self.false_positive_weight = hp.get("false_positive_weight", self.false_positive_weight)
            self.false_negative_weight = hp.get("false_negative_weight", self.false_negative_weight)


class MultiAlertTuner:
    """Manages tuning for multiple alert rules."""
    
    def __init__(
        self,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize multi-alert tuner.
        
        Args:
            default_config: Default configuration for tuner
        """
        self._tuner = AlertTuner(**(default_config or {}))
        self._alert_history: Dict[str, List[AlertTuning]] = {}
    
    def tune(
        self,
        state: AlertState,
        explore: bool = True,
    ) -> AlertTuning:
        """Tune alert threshold.
        
        Args:
            state: Alert state
            explore: Whether to explore
            
        Returns:
            Tuning decision
        """
        tuning = self._tuner.tune(state, explore)
        
        # Track history
        if state.alert_name not in self._alert_history:
            self._alert_history[state.alert_name] = []
        self._alert_history[state.alert_name].append(tuning)
        
        # Limit history
        if len(self._alert_history[state.alert_name]) > 100:
            self._alert_history[state.alert_name].pop(0)
        
        return tuning
    
    def record_outcome(
        self,
        state: AlertState,
        action: ThresholdAction,
        outcome: AlertOutcome,
    ) -> None:
        """Record alert outcome.
        
        Args:
            state: Alert state
            action: Action taken
            outcome: Alert outcome
        """
        self._tuner.record_outcome(state, action, outcome)
    
    def get_alert_history(self, alert_name: str) -> List[AlertTuning]:
        """Get tuning history for alert.
        
        Args:
            alert_name: Alert name
            
        Returns:
            List of tuning decisions
        """
        return self._alert_history.get(alert_name, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self._tuner.get_statistics()
        stats["tracked_alerts"] = len(self._alert_history)
        stats["total_history_entries"] = sum(
            len(h) for h in self._alert_history.values()
        )
        return stats
    
    def save(self, path: str) -> None:
        """Save to disk.
        
        Args:
            path: Save path
        """
        self._tuner.save(path)
    
    def load(self, path: str) -> None:
        """Load from disk.
        
        Args:
            path: Load path
        """
        self._tuner.load(path)
