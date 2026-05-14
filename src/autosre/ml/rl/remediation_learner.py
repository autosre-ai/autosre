"""Remediation learning using reinforcement learning.

Learns from successful and failed remediations to:
- Suggest effective remediation actions
- Learn optimal action sequences
- Adapt to service-specific patterns
- Improve over time from feedback
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, List, Dict, Tuple, Set
import hashlib

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class RemediationOutcome(str, Enum):
    """Outcome of a remediation action."""
    SUCCESS = "success"  # Fixed the issue
    PARTIAL = "partial"  # Helped but didn't fully fix
    FAILED = "failed"  # Didn't help
    MADE_WORSE = "made_worse"  # Made things worse
    TIMEOUT = "timeout"  # Took too long to determine
    SKIPPED = "skipped"  # Was skipped


class RemediationType(str, Enum):
    """Type of remediation action."""
    RESTART = "restart"  # Restart pods/services
    SCALE = "scale"  # Scale up/down
    ROLLBACK = "rollback"  # Rollback deployment
    DRAIN = "drain"  # Drain node
    FAILOVER = "failover"  # Failover to backup
    CONFIG_CHANGE = "config_change"  # Change configuration
    RATE_LIMIT = "rate_limit"  # Enable/adjust rate limiting
    CIRCUIT_BREAKER = "circuit_breaker"  # Open circuit breaker
    CACHE_CLEAR = "cache_clear"  # Clear caches
    CONNECTION_RESET = "connection_reset"  # Reset connections
    MANUAL = "manual"  # Manual intervention required
    CUSTOM = "custom"  # Custom action


class IncidentCategory(str, Enum):
    """Category of incident."""
    PERFORMANCE = "performance"  # Latency, throughput
    AVAILABILITY = "availability"  # Down, unreachable
    ERROR_RATE = "error_rate"  # High errors
    RESOURCE = "resource"  # CPU, memory, disk
    NETWORK = "network"  # Network issues
    DATABASE = "database"  # DB issues
    DEPENDENCY = "dependency"  # Upstream/downstream issues
    SECURITY = "security"  # Security incidents
    UNKNOWN = "unknown"


class Remediation(BaseModel):
    """A remediation action."""
    model_config = ConfigDict(validate_assignment=True)
    
    remediation_id: str = Field(default_factory=generate_id)
    
    # Action details
    action_type: RemediationType = Field(default=RemediationType.CUSTOM)
    action_name: str = Field(default="")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Target
    service: str = Field(default="")
    namespace: str = Field(default="default")
    component: str = Field(default="")  # Specific component (pod, node, etc.)
    
    # Context
    incident_id: str = Field(default="")
    incident_category: IncidentCategory = Field(default=IncidentCategory.UNKNOWN)
    
    # Execution
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Outcome
    outcome: RemediationOutcome = Field(default=RemediationOutcome.TIMEOUT)
    outcome_details: str = Field(default="")
    
    # Metrics before/after
    metrics_before: Dict[str, float] = Field(default_factory=dict)
    metrics_after: Dict[str, float] = Field(default_factory=dict)
    
    # Confidence at time of suggestion
    suggested_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    was_suggested: bool = Field(default=False)
    was_executed: bool = Field(default=False)
    
    def get_improvement(self, metric: str) -> Optional[float]:
        """Calculate improvement for a metric.
        
        Args:
            metric: Metric name
            
        Returns:
            Improvement percentage (positive is better) or None
        """
        if metric not in self.metrics_before or metric not in self.metrics_after:
            return None
        
        before = self.metrics_before[metric]
        after = self.metrics_after[metric]
        
        if before == 0:
            return None
        
        # For metrics where lower is better (latency, error_rate)
        if metric in ["latency", "error_rate", "response_time", "p99_latency"]:
            return (before - after) / before * 100
        # For metrics where higher is better (throughput, availability)
        else:
            return (after - before) / before * 100


class IncidentContext(BaseModel):
    """Context of an incident for remediation."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Identification
    incident_id: str = Field(default="")
    service: str = Field(default="")
    namespace: str = Field(default="default")
    
    # Incident details
    category: IncidentCategory = Field(default=IncidentCategory.UNKNOWN)
    severity: str = Field(default="warning")
    alert_name: str = Field(default="")
    description: str = Field(default="")
    
    # Symptoms
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_p99_ms: float = Field(default=0.0, ge=0.0)
    cpu_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    request_rate: float = Field(default=0.0, ge=0.0)
    pod_restart_count: int = Field(default=0, ge=0)
    
    # History
    similar_incidents_7d: int = Field(default=0, ge=0)
    last_remediation_hours: float = Field(default=24.0, ge=0.0)
    last_remediation_type: Optional[RemediationType] = None
    last_remediation_outcome: Optional[RemediationOutcome] = None
    
    # Time
    started_at: datetime = Field(default_factory=utc_now)
    duration_minutes: float = Field(default=0.0, ge=0.0)
    hour_of_day: int = Field(default=12, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    
    # Actions taken
    attempted_actions: List[RemediationType] = Field(default_factory=list)
    
    def to_vector(self) -> np.ndarray:
        """Convert to feature vector."""
        # Category one-hot (9 categories)
        category_vec = np.zeros(len(IncidentCategory))
        category_vec[list(IncidentCategory).index(self.category)] = 1.0
        
        # Last remediation type one-hot (12 types)
        last_rem_vec = np.zeros(len(RemediationType))
        if self.last_remediation_type:
            last_rem_vec[list(RemediationType).index(self.last_remediation_type)] = 1.0
        
        # Last outcome one-hot (6 outcomes)
        last_outcome_vec = np.zeros(len(RemediationOutcome))
        if self.last_remediation_outcome:
            last_outcome_vec[list(RemediationOutcome).index(self.last_remediation_outcome)] = 1.0
        
        # Symptom features
        symptom_vec = np.array([
            self.error_rate,
            min(1.0, self.latency_p99_ms / 2000.0),
            self.cpu_utilization / 100.0,
            self.memory_utilization / 100.0,
            min(1.0, self.request_rate / 1000.0),
            min(1.0, self.pod_restart_count / 10.0),
        ])
        
        # Context features
        context_vec = np.array([
            min(1.0, self.similar_incidents_7d / 10.0),
            min(1.0, self.last_remediation_hours / 168.0),  # Normalize to week
            min(1.0, self.duration_minutes / 60.0),
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
        ])
        
        return np.concatenate([
            category_vec,
            last_rem_vec,
            last_outcome_vec,
            symptom_vec,
            context_vec,
        ])
    
    @property
    def state_dimension(self) -> int:
        """Get state dimension."""
        return len(IncidentCategory) + len(RemediationType) + len(RemediationOutcome) + 11


class RemediationSuggestion(BaseModel):
    """A suggested remediation action."""
    model_config = ConfigDict(validate_assignment=True)
    
    suggestion_id: str = Field(default_factory=generate_id)
    
    # Action
    action_type: RemediationType = Field(default=RemediationType.MANUAL)
    action_name: str = Field(default="")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Ranking
    rank: int = Field(default=1, ge=1)
    q_value: float = Field(default=0.0)
    
    # Explanation
    reason: str = Field(default="")
    supporting_evidence: List[str] = Field(default_factory=list)
    
    # Similar past cases
    similar_cases: int = Field(default=0, ge=0)
    success_rate_similar: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Risks
    risk_level: str = Field(default="low")
    potential_side_effects: List[str] = Field(default_factory=list)
    
    # Metadata
    suggested_at: datetime = Field(default_factory=utc_now)


class RemediationLearner:
    """Learns effective remediation strategies.
    
    Uses:
    - Contextual bandits for action selection
    - Experience replay for batch learning
    - Similar incident matching for cold start
    
    Learns:
    - Which actions work for which incident types
    - Optimal action sequences
    - Service-specific patterns
    """
    
    def __init__(
        self,
        learning_rate: float = 0.01,
        discount_factor: float = 0.9,
        exploration_rate: float = 0.3,
        min_exploration: float = 0.05,
        exploration_decay: float = 0.995,
        similarity_threshold: float = 0.7,
    ):
        """Initialize the remediation learner.
        
        Args:
            learning_rate: Learning rate
            discount_factor: Discount for future rewards
            exploration_rate: Initial exploration rate
            min_exploration: Minimum exploration rate
            exploration_decay: Decay rate for exploration
            similarity_threshold: Threshold for similar incident matching
        """
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.min_exploration = min_exploration
        self.exploration_decay = exploration_decay
        self.similarity_threshold = similarity_threshold
        
        # State and action dimensions
        self._state_dim = 38  # From IncidentContext.state_dimension
        self._n_actions = len(RemediationType)
        
        # Q-network (linear for interpretability)
        self._weights = np.zeros((self._n_actions, self._state_dim))
        
        # Action value estimates (for UCB)
        self._action_counts = np.ones(self._n_actions)
        self._action_values = np.zeros(self._n_actions)
        
        # Experience storage
        self._remediations: List[Remediation] = []
        self._max_history = 10000
        
        # Per-service learning
        self._service_weights: Dict[str, np.ndarray] = {}
        
        # Per-category learning
        self._category_weights: Dict[IncidentCategory, np.ndarray] = {}
        
        # Success rates per action-category pair
        self._success_counts: Dict[Tuple[RemediationType, IncidentCategory], int] = {}
        self._attempt_counts: Dict[Tuple[RemediationType, IncidentCategory], int] = {}
        
        # Statistics
        self._total_suggestions = 0
        self._total_feedback = 0
    
    def _get_q_values(
        self,
        state: np.ndarray,
        service: str = "",
        category: Optional[IncidentCategory] = None,
    ) -> np.ndarray:
        """Get Q-values for state.
        
        Combines global, service-specific, and category-specific weights.
        
        Args:
            state: State vector
            service: Service name
            category: Incident category
            
        Returns:
            Q-values for each action
        """
        # Global Q-values
        q_values = np.dot(self._weights, state)
        
        # Add service-specific if available
        if service and service in self._service_weights:
            q_values += 0.3 * np.dot(self._service_weights[service], state)
        
        # Add category-specific if available
        if category and category in self._category_weights:
            q_values += 0.3 * np.dot(self._category_weights[category], state)
        
        return q_values
    
    def _select_action(
        self,
        state: np.ndarray,
        context: IncidentContext,
        explore: bool = True,
        excluded_actions: Optional[Set[RemediationType]] = None,
    ) -> int:
        """Select remediation action.
        
        Uses UCB (Upper Confidence Bound) for exploration.
        
        Args:
            state: State vector
            context: Incident context
            explore: Whether to explore
            excluded_actions: Actions to exclude
            
        Returns:
            Action index
        """
        q_values = self._get_q_values(state, context.service, context.category)
        
        # Apply exclusions
        if excluded_actions:
            for action in excluded_actions:
                q_values[list(RemediationType).index(action)] = -np.inf
        
        if explore and np.random.random() < self.exploration_rate:
            # UCB exploration
            total_counts = np.sum(self._action_counts)
            ucb_values = q_values + np.sqrt(2 * np.log(total_counts + 1) / self._action_counts)
            
            # Mask excluded actions
            if excluded_actions:
                for action in excluded_actions:
                    ucb_values[list(RemediationType).index(action)] = -np.inf
            
            return int(np.argmax(ucb_values))
        
        return int(np.argmax(q_values))
    
    def suggest(
        self,
        context: IncidentContext,
        top_k: int = 3,
        explore: bool = True,
        exclude_attempted: bool = True,
    ) -> List[RemediationSuggestion]:
        """Suggest remediation actions.
        
        Args:
            context: Incident context
            top_k: Number of suggestions
            explore: Whether to explore
            exclude_attempted: Exclude already attempted actions
            
        Returns:
            List of suggestions ranked by expected effectiveness
        """
        state = context.to_vector()
        
        # Exclude already attempted actions
        excluded = set(context.attempted_actions) if exclude_attempted else set()
        
        # Get Q-values
        q_values = self._get_q_values(state, context.service, context.category)
        
        suggestions = []
        used_actions = set()
        
        for rank in range(1, top_k + 1):
            # Select best remaining action
            best_idx = self._select_action(
                state, context, explore and rank == 1,
                excluded.union(used_actions)
            )
            
            if q_values[best_idx] == -np.inf:
                break  # No more valid actions
            
            action_type = list(RemediationType)[best_idx]
            used_actions.add(action_type)
            
            # Calculate confidence using softmax
            valid_q = np.array([
                q if i not in [list(RemediationType).index(a) for a in excluded.union(used_actions) - {action_type}]
                else -np.inf
                for i, q in enumerate(q_values)
            ])
            exp_q = np.exp(valid_q - np.max(valid_q[valid_q > -np.inf]))
            exp_q[valid_q == -np.inf] = 0
            probs = exp_q / np.sum(exp_q)
            confidence = float(probs[best_idx])
            
            # Get success rate for this action-category pair
            key = (action_type, context.category)
            attempts = self._attempt_counts.get(key, 0)
            successes = self._success_counts.get(key, 0)
            success_rate = successes / attempts if attempts > 0 else 0.5
            
            # Generate suggestion
            reason, evidence = self._generate_explanation(context, action_type)
            parameters = self._get_action_parameters(context, action_type)
            
            suggestion = RemediationSuggestion(
                action_type=action_type,
                action_name=self._get_action_name(action_type, context),
                parameters=parameters,
                confidence=confidence,
                expected_success_rate=success_rate,
                rank=rank,
                q_value=float(q_values[best_idx]),
                reason=reason,
                supporting_evidence=evidence,
                similar_cases=attempts,
                success_rate_similar=success_rate,
                risk_level=self._assess_risk(action_type, context),
                potential_side_effects=self._get_side_effects(action_type),
            )
            
            suggestions.append(suggestion)
        
        self._total_suggestions += 1
        return suggestions
    
    def _generate_explanation(
        self,
        context: IncidentContext,
        action_type: RemediationType,
    ) -> Tuple[str, List[str]]:
        """Generate explanation for suggestion.
        
        Args:
            context: Incident context
            action_type: Suggested action
            
        Returns:
            Tuple of (reason, evidence list)
        """
        evidence = []
        
        # Category-based reasoning
        category_actions = {
            IncidentCategory.PERFORMANCE: {
                RemediationType.SCALE: "Scaling helps with performance under load",
                RemediationType.RESTART: "Restart can clear stuck processes",
            },
            IncidentCategory.RESOURCE: {
                RemediationType.SCALE: "Adding resources for resource exhaustion",
                RemediationType.RESTART: "Restart to clear memory leaks",
            },
            IncidentCategory.AVAILABILITY: {
                RemediationType.RESTART: "Restart unresponsive components",
                RemediationType.FAILOVER: "Failover to healthy instances",
            },
            IncidentCategory.ERROR_RATE: {
                RemediationType.ROLLBACK: "Rollback if recent deployment caused errors",
                RemediationType.CIRCUIT_BREAKER: "Circuit breaker to prevent cascade",
            },
        }
        
        # Add category-based evidence
        if context.category in category_actions:
            if action_type in category_actions[context.category]:
                evidence.append(category_actions[context.category][action_type])
        
        # Add symptom-based evidence
        if context.error_rate > 0.05:
            evidence.append(f"High error rate: {context.error_rate:.1%}")
        if context.latency_p99_ms > 500:
            evidence.append(f"High latency: {context.latency_p99_ms:.0f}ms")
        if context.cpu_utilization > 80:
            evidence.append(f"High CPU: {context.cpu_utilization:.0f}%")
        if context.memory_utilization > 85:
            evidence.append(f"High memory: {context.memory_utilization:.0f}%")
        if context.pod_restart_count > 3:
            evidence.append(f"Multiple restarts: {context.pod_restart_count}")
        
        # Generate reason
        key = (action_type, context.category)
        attempts = self._attempt_counts.get(key, 0)
        successes = self._success_counts.get(key, 0)
        
        if attempts >= 5:
            rate = successes / attempts
            reason = f"Based on {attempts} similar cases with {rate:.0%} success rate"
        elif context.last_remediation_type == action_type and context.last_remediation_outcome == RemediationOutcome.SUCCESS:
            reason = "Previously successful for this service"
        else:
            reason = f"Recommended for {context.category.value} incidents"
        
        return reason, evidence
    
    def _get_action_name(
        self,
        action_type: RemediationType,
        context: IncidentContext,
    ) -> str:
        """Get human-readable action name.
        
        Args:
            action_type: Action type
            context: Incident context
            
        Returns:
            Action name
        """
        names = {
            RemediationType.RESTART: f"Restart {context.service} pods",
            RemediationType.SCALE: f"Scale {context.service} horizontally",
            RemediationType.ROLLBACK: f"Rollback {context.service} deployment",
            RemediationType.DRAIN: "Drain affected node",
            RemediationType.FAILOVER: f"Failover {context.service}",
            RemediationType.CONFIG_CHANGE: f"Adjust {context.service} configuration",
            RemediationType.RATE_LIMIT: "Enable/adjust rate limiting",
            RemediationType.CIRCUIT_BREAKER: "Open circuit breaker",
            RemediationType.CACHE_CLEAR: "Clear service caches",
            RemediationType.CONNECTION_RESET: "Reset connection pools",
            RemediationType.MANUAL: "Manual intervention required",
            RemediationType.CUSTOM: "Custom remediation action",
        }
        return names.get(action_type, action_type.value)
    
    def _get_action_parameters(
        self,
        context: IncidentContext,
        action_type: RemediationType,
    ) -> Dict[str, Any]:
        """Get suggested parameters for action.
        
        Args:
            context: Incident context
            action_type: Action type
            
        Returns:
            Parameter dictionary
        """
        params: Dict[str, Any] = {
            "service": context.service,
            "namespace": context.namespace,
        }
        
        if action_type == RemediationType.RESTART:
            params["strategy"] = "rolling"
            params["max_unavailable"] = "25%"
        elif action_type == RemediationType.SCALE:
            # Suggest scaling based on load
            if context.cpu_utilization > 80:
                params["scale_factor"] = 1.5
            else:
                params["scale_factor"] = 1.2
            params["min_replicas"] = 2
        elif action_type == RemediationType.ROLLBACK:
            params["revisions_back"] = 1
        elif action_type == RemediationType.RATE_LIMIT:
            params["rate"] = 100  # requests per second
            params["burst"] = 50
        elif action_type == RemediationType.CIRCUIT_BREAKER:
            params["threshold"] = 50  # % failures
            params["timeout_seconds"] = 30
        
        return params
    
    def _assess_risk(
        self,
        action_type: RemediationType,
        context: IncidentContext,
    ) -> str:
        """Assess risk level of action.
        
        Args:
            action_type: Action type
            context: Incident context
            
        Returns:
            Risk level (low, medium, high)
        """
        high_risk = {RemediationType.DRAIN, RemediationType.FAILOVER}
        medium_risk = {RemediationType.ROLLBACK, RemediationType.RESTART}
        
        if action_type in high_risk:
            return "high"
        elif action_type in medium_risk:
            return "medium"
        else:
            return "low"
    
    def _get_side_effects(self, action_type: RemediationType) -> List[str]:
        """Get potential side effects of action.
        
        Args:
            action_type: Action type
            
        Returns:
            List of side effects
        """
        effects: Dict[RemediationType, List[str]] = {
            RemediationType.RESTART: [
                "Brief service interruption",
                "Loss of in-flight requests",
            ],
            RemediationType.SCALE: [
                "Increased resource costs",
                "Potential cold start latency",
            ],
            RemediationType.ROLLBACK: [
                "Loss of new features",
                "Potential data compatibility issues",
            ],
            RemediationType.DRAIN: [
                "Reduced cluster capacity",
                "Pod rescheduling latency",
            ],
            RemediationType.FAILOVER: [
                "Potential data sync issues",
                "Connection reset for clients",
            ],
            RemediationType.RATE_LIMIT: [
                "Rejected requests for some users",
                "Potential 429 errors",
            ],
            RemediationType.CIRCUIT_BREAKER: [
                "Failed requests during open state",
                "Dependent service degradation",
            ],
            RemediationType.CACHE_CLEAR: [
                "Increased backend load",
                "Temporary performance degradation",
            ],
        }
        return effects.get(action_type, [])
    
    def record_outcome(
        self,
        remediation: Remediation,
    ) -> float:
        """Record outcome of remediation.
        
        Args:
            remediation: Completed remediation
            
        Returns:
            Reward value
        """
        # Store remediation
        self._remediations.append(remediation)
        if len(self._remediations) > self._max_history:
            self._remediations.pop(0)
        
        # Calculate reward
        reward = self._calculate_reward(remediation)
        
        # Update action statistics
        action_idx = list(RemediationType).index(remediation.action_type)
        self._action_counts[action_idx] += 1
        
        # Running average for action values
        n = self._action_counts[action_idx]
        self._action_values[action_idx] += (reward - self._action_values[action_idx]) / n
        
        # Update success counts
        key = (remediation.action_type, remediation.incident_category)
        self._attempt_counts[key] = self._attempt_counts.get(key, 0) + 1
        if remediation.outcome == RemediationOutcome.SUCCESS:
            self._success_counts[key] = self._success_counts.get(key, 0) + 1
        
        # Create context from remediation for learning
        context = self._remediation_to_context(remediation)
        state = context.to_vector()
        
        # Update weights
        current_q = self._get_q_values(state, remediation.service, remediation.incident_category)[action_idx]
        td_error = reward - current_q
        
        # Global update
        self._weights[action_idx] += self.learning_rate * td_error * state
        
        # Service-specific update
        if remediation.service:
            if remediation.service not in self._service_weights:
                self._service_weights[remediation.service] = np.zeros((self._n_actions, self._state_dim))
            self._service_weights[remediation.service][action_idx] += (
                self.learning_rate * 0.5 * td_error * state
            )
        
        # Category-specific update
        if remediation.incident_category not in self._category_weights:
            self._category_weights[remediation.incident_category] = np.zeros((self._n_actions, self._state_dim))
        self._category_weights[remediation.incident_category][action_idx] += (
            self.learning_rate * 0.5 * td_error * state
        )
        
        # Decay exploration
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay,
        )
        
        self._total_feedback += 1
        return reward
    
    def _calculate_reward(self, remediation: Remediation) -> float:
        """Calculate reward for remediation outcome.
        
        Args:
            remediation: Remediation with outcome
            
        Returns:
            Reward value
        """
        base_rewards = {
            RemediationOutcome.SUCCESS: 2.0,
            RemediationOutcome.PARTIAL: 0.5,
            RemediationOutcome.FAILED: -0.5,
            RemediationOutcome.MADE_WORSE: -2.0,
            RemediationOutcome.TIMEOUT: -0.2,
            RemediationOutcome.SKIPPED: 0.0,
        }
        
        reward = base_rewards[remediation.outcome]
        
        # Bonus for fast resolution
        if remediation.duration_seconds and remediation.duration_seconds < 300:
            reward += 0.3
        
        # Bonus for metric improvements
        for metric in ["error_rate", "latency_p99", "p99_latency"]:
            improvement = remediation.get_improvement(metric)
            if improvement is not None and improvement > 0:
                reward += min(0.5, improvement / 100)
        
        return reward
    
    def _remediation_to_context(self, remediation: Remediation) -> IncidentContext:
        """Convert remediation to context for learning.
        
        Args:
            remediation: Remediation record
            
        Returns:
            Incident context
        """
        return IncidentContext(
            incident_id=remediation.incident_id,
            service=remediation.service,
            namespace=remediation.namespace,
            category=remediation.incident_category,
            error_rate=remediation.metrics_before.get("error_rate", 0),
            latency_p99_ms=remediation.metrics_before.get("latency_p99", 0),
            cpu_utilization=remediation.metrics_before.get("cpu_utilization", 0),
            memory_utilization=remediation.metrics_before.get("memory_utilization", 0),
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics.
        
        Returns:
            Statistics dictionary
        """
        # Calculate success rates per action
        action_stats = {}
        for action in RemediationType:
            total = sum(
                self._attempt_counts.get((action, cat), 0)
                for cat in IncidentCategory
            )
            success = sum(
                self._success_counts.get((action, cat), 0)
                for cat in IncidentCategory
            )
            if total > 0:
                action_stats[action.value] = {
                    "attempts": total,
                    "successes": success,
                    "success_rate": success / total,
                }
        
        # Calculate success rates per category
        category_stats = {}
        for category in IncidentCategory:
            total = sum(
                self._attempt_counts.get((action, category), 0)
                for action in RemediationType
            )
            success = sum(
                self._success_counts.get((action, category), 0)
                for action in RemediationType
            )
            if total > 0:
                category_stats[category.value] = {
                    "attempts": total,
                    "successes": success,
                    "success_rate": success / total,
                }
        
        return {
            "total_suggestions": self._total_suggestions,
            "total_feedback": self._total_feedback,
            "total_remediations": len(self._remediations),
            "exploration_rate": self.exploration_rate,
            "action_statistics": action_stats,
            "category_statistics": category_stats,
            "services_tracked": len(self._service_weights),
        }
    
    def find_similar_remediations(
        self,
        context: IncidentContext,
        top_k: int = 5,
    ) -> List[Remediation]:
        """Find similar past remediations.
        
        Args:
            context: Current incident context
            top_k: Number to return
            
        Returns:
            Similar remediations sorted by similarity
        """
        if not self._remediations:
            return []
        
        current_state = context.to_vector()
        
        # Calculate similarities
        similarities = []
        for rem in self._remediations:
            rem_context = self._remediation_to_context(rem)
            rem_state = rem_context.to_vector()
            
            # Cosine similarity
            dot = np.dot(current_state, rem_state)
            norm = np.linalg.norm(current_state) * np.linalg.norm(rem_state)
            similarity = dot / norm if norm > 0 else 0
            
            # Boost for same service/category
            if rem.service == context.service:
                similarity *= 1.2
            if rem.incident_category == context.category:
                similarity *= 1.1
            
            if similarity >= self.similarity_threshold:
                similarities.append((similarity, rem))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        return [rem for _, rem in similarities[:top_k]]
    
    def save(self, path: str) -> None:
        """Save learner to disk.
        
        Args:
            path: Save path
        """
        import json
        
        data = {
            "weights": self._weights.tolist(),
            "action_counts": self._action_counts.tolist(),
            "action_values": self._action_values.tolist(),
            "exploration_rate": self.exploration_rate,
            "total_suggestions": self._total_suggestions,
            "total_feedback": self._total_feedback,
            "service_weights": {
                k: v.tolist() for k, v in self._service_weights.items()
            },
            "category_weights": {
                k.value: v.tolist() for k, v in self._category_weights.items()
            },
            "success_counts": {
                f"{action.value}:{category.value}": count
                for (action, category), count in self._success_counts.items()
            },
            "attempt_counts": {
                f"{action.value}:{category.value}": count
                for (action, category), count in self._attempt_counts.items()
            },
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "discount_factor": self.discount_factor,
                "min_exploration": self.min_exploration,
                "exploration_decay": self.exploration_decay,
                "similarity_threshold": self.similarity_threshold,
            },
        }
        
        with open(path, "w") as f:
            json.dump(data, f, default=str)
    
    def load(self, path: str) -> None:
        """Load learner from disk.
        
        Args:
            path: Load path
        """
        import json
        
        with open(path) as f:
            data = json.load(f)
        
        self._weights = np.array(data["weights"])
        self._action_counts = np.array(data["action_counts"])
        self._action_values = np.array(data["action_values"])
        self.exploration_rate = data.get("exploration_rate", self.min_exploration)
        self._total_suggestions = data.get("total_suggestions", 0)
        self._total_feedback = data.get("total_feedback", 0)
        
        # Load service weights
        self._service_weights = {
            k: np.array(v) for k, v in data.get("service_weights", {}).items()
        }
        
        # Load category weights
        self._category_weights = {
            IncidentCategory(k): np.array(v)
            for k, v in data.get("category_weights", {}).items()
        }
        
        # Load success/attempt counts
        for key, count in data.get("success_counts", {}).items():
            action_str, category_str = key.split(":")
            self._success_counts[(RemediationType(action_str), IncidentCategory(category_str))] = count
        
        for key, count in data.get("attempt_counts", {}).items():
            action_str, category_str = key.split(":")
            self._attempt_counts[(RemediationType(action_str), IncidentCategory(category_str))] = count
        
        # Load hyperparameters
        if "hyperparameters" in data:
            hp = data["hyperparameters"]
            self.learning_rate = hp.get("learning_rate", self.learning_rate)
            self.discount_factor = hp.get("discount_factor", self.discount_factor)
            self.min_exploration = hp.get("min_exploration", self.min_exploration)
            self.exploration_decay = hp.get("exploration_decay", self.exploration_decay)
            self.similarity_threshold = hp.get("similarity_threshold", self.similarity_threshold)
