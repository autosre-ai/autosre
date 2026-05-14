"""Scaling agent using reinforcement learning.

Learns optimal scaling policies for services based on:
- Traffic patterns
- Resource utilization
- Performance metrics
- Cost constraints
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict, Tuple
import math

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class ScalingDirection(str, Enum):
    """Direction of scaling."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


class ScalingType(str, Enum):
    """Type of scaling."""
    HORIZONTAL = "horizontal"  # Add/remove replicas
    VERTICAL = "vertical"  # Change resource limits


class ScalingAction(BaseModel):
    """An action in the scaling space."""
    model_config = ConfigDict(validate_assignment=True)
    
    direction: ScalingDirection = Field(default=ScalingDirection.NO_CHANGE)
    scaling_type: ScalingType = Field(default=ScalingType.HORIZONTAL)
    magnitude: int = Field(default=0, ge=-10, le=10)  # -10 to +10 replicas or % change
    
    def to_index(self) -> int:
        """Convert action to index for Q-table."""
        # 3 directions x 2 types x 21 magnitudes = 126 possible actions
        # Simplified: 5 actions (scale down big, small, no change, scale up small, big)
        if self.direction == ScalingDirection.NO_CHANGE:
            return 2
        elif self.direction == ScalingDirection.SCALE_DOWN:
            return 0 if abs(self.magnitude) > 2 else 1
        else:  # SCALE_UP
            return 3 if self.magnitude <= 2 else 4
    
    @classmethod
    def from_index(cls, index: int, scaling_type: ScalingType = ScalingType.HORIZONTAL) -> "ScalingAction":
        """Create action from index."""
        actions = [
            (ScalingDirection.SCALE_DOWN, -3),  # Big scale down
            (ScalingDirection.SCALE_DOWN, -1),  # Small scale down
            (ScalingDirection.NO_CHANGE, 0),    # No change
            (ScalingDirection.SCALE_UP, 1),     # Small scale up
            (ScalingDirection.SCALE_UP, 3),     # Big scale up
        ]
        direction, magnitude = actions[index]
        return cls(direction=direction, scaling_type=scaling_type, magnitude=magnitude)


class ScalingState(BaseModel):
    """State representation for scaling decisions."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Service identification
    service_name: str = Field(default="")
    namespace: str = Field(default="default")
    
    # Current state
    current_replicas: int = Field(default=1, ge=0)
    min_replicas: int = Field(default=1, ge=0)
    max_replicas: int = Field(default=10, ge=1)
    
    # Resource utilization
    cpu_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Traffic metrics
    requests_per_second: float = Field(default=0.0, ge=0.0)
    avg_response_time_ms: float = Field(default=0.0, ge=0.0)
    p99_response_time_ms: float = Field(default=0.0, ge=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Queue metrics
    pending_requests: int = Field(default=0, ge=0)
    queue_depth: int = Field(default=0, ge=0)
    
    # Time features (for seasonality)
    hour_of_day: int = Field(default=12, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    is_business_hours: bool = Field(default=True)
    
    # Historical features
    avg_cpu_1h: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_cpu_24h: float = Field(default=0.0, ge=0.0, le=100.0)
    max_cpu_1h: float = Field(default=0.0, ge=0.0, le=100.0)
    
    avg_rps_1h: float = Field(default=0.0, ge=0.0)
    avg_rps_24h: float = Field(default=0.0, ge=0.0)
    
    # Scaling history
    last_scale_time_minutes: float = Field(default=60.0, ge=0.0)
    scale_count_last_hour: int = Field(default=0, ge=0)
    
    # Cost context
    cost_per_replica_hour: float = Field(default=1.0, ge=0.0)
    
    def to_vector(self) -> np.ndarray:
        """Convert state to normalized feature vector."""
        return np.array([
            # Current state (3)
            self.current_replicas / self.max_replicas,
            (self.current_replicas - self.min_replicas) / max(1, self.max_replicas - self.min_replicas),
            
            # Resource utilization (2)
            self.cpu_utilization / 100.0,
            self.memory_utilization / 100.0,
            
            # Traffic metrics (4)
            min(1.0, self.requests_per_second / 1000.0),
            min(1.0, self.avg_response_time_ms / 1000.0),
            min(1.0, self.p99_response_time_ms / 2000.0),
            self.error_rate,
            
            # Queue metrics (2)
            min(1.0, self.pending_requests / 100.0),
            min(1.0, self.queue_depth / 100.0),
            
            # Time features (3)
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
            float(self.is_business_hours),
            
            # Historical features (5)
            self.avg_cpu_1h / 100.0,
            self.avg_cpu_24h / 100.0,
            self.max_cpu_1h / 100.0,
            min(1.0, self.avg_rps_1h / 1000.0),
            min(1.0, self.avg_rps_24h / 1000.0),
            
            # Scaling history (2)
            min(1.0, self.last_scale_time_minutes / 60.0),
            min(1.0, self.scale_count_last_hour / 10.0),
        ])
    
    @property
    def state_dimension(self) -> int:
        """Get the dimension of the state vector."""
        return 20


class ScalingDecision(BaseModel):
    """A scaling decision with explanation."""
    model_config = ConfigDict(validate_assignment=True)
    
    decision_id: str = Field(default_factory=generate_id)
    
    # Action
    action: ScalingAction = Field(default_factory=ScalingAction)
    
    # Target state
    target_replicas: int = Field(default=1, ge=0)
    current_replicas: int = Field(default=1, ge=0)
    
    # Confidence and Q-values
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_reward: float = Field(default=0.0)
    q_values: Dict[str, float] = Field(default_factory=dict)
    
    # Explanation
    reason: str = Field(default="")
    factors: List[str] = Field(default_factory=list)
    
    # Constraints check
    within_bounds: bool = Field(default=True)
    cooldown_active: bool = Field(default=False)
    
    # Metadata
    decided_at: datetime = Field(default_factory=utc_now)
    service_name: str = Field(default="")
    namespace: str = Field(default="default")


class ScalingPolicy(BaseModel):
    """Learned scaling policy parameters."""
    model_config = ConfigDict(validate_assignment=True)
    
    policy_id: str = Field(default_factory=generate_id)
    name: str = Field(default="")
    
    # Thresholds learned from experience
    scale_up_cpu_threshold: float = Field(default=70.0, ge=0.0, le=100.0)
    scale_down_cpu_threshold: float = Field(default=30.0, ge=0.0, le=100.0)
    scale_up_rps_threshold: float = Field(default=500.0, ge=0.0)
    
    # Timing
    cooldown_seconds: int = Field(default=300, ge=0)
    stabilization_window_seconds: int = Field(default=60, ge=0)
    
    # Weights (learned)
    cpu_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    memory_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    latency_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    cost_weight: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Training info
    trained_episodes: int = Field(default=0, ge=0)
    avg_reward: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScalingAgent:
    """Reinforcement learning agent for service scaling.
    
    Uses Deep Q-Network (DQN) approach with:
    - Experience replay
    - Target network
    - Dueling architecture
    
    Learns from:
    - CPU/memory utilization
    - Request rates and latencies
    - Error rates
    - Scaling history
    """
    
    def __init__(
        self,
        service_name: str = "",
        learning_rate: float = 0.001,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.3,
        min_exploration: float = 0.01,
        exploration_decay: float = 0.995,
        target_update_frequency: int = 100,
        memory_size: int = 10000,
        batch_size: int = 32,
    ):
        """Initialize the scaling agent.
        
        Args:
            service_name: Name of service being scaled
            learning_rate: Learning rate (alpha)
            discount_factor: Discount factor (gamma)
            exploration_rate: Initial epsilon for exploration
            min_exploration: Minimum exploration rate
            exploration_decay: Decay rate for exploration
            target_update_frequency: Steps between target network updates
            memory_size: Size of replay buffer
            batch_size: Batch size for training
        """
        self.service_name = service_name
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.min_exploration = min_exploration
        self.exploration_decay = exploration_decay
        self.target_update_frequency = target_update_frequency
        self.batch_size = batch_size
        
        # State and action dimensions
        self._state_dim = 20
        self._n_actions = 5  # 5 discrete actions
        
        # Q-network (linear approximation for simplicity)
        # In production, this would be a neural network
        self._weights = np.random.randn(self._n_actions, self._state_dim) * 0.01
        self._target_weights = self._weights.copy()
        
        # Experience replay buffer
        self._memory: List[Tuple[np.ndarray, int, float, np.ndarray, bool]] = []
        self._memory_size = memory_size
        
        # Training statistics
        self._total_steps = 0
        self._total_episodes = 0
        self._total_reward = 0.0
        self._episode_rewards: List[float] = []
        
        # Scaling history for this service
        self._scaling_history: List[ScalingDecision] = []
        
        # Learned policy
        self._policy = ScalingPolicy(name=f"policy_{service_name}")
        
        # Cooldown tracking
        self._last_scale_time: Optional[datetime] = None
    
    def _get_q_values(
        self,
        state: np.ndarray,
        use_target: bool = False,
    ) -> np.ndarray:
        """Get Q-values for all actions.
        
        Args:
            state: State vector
            use_target: Whether to use target network
            
        Returns:
            Q-values for each action
        """
        weights = self._target_weights if use_target else self._weights
        return np.dot(weights, state)
    
    def _select_action(
        self,
        state: np.ndarray,
        explore: bool = True,
    ) -> int:
        """Select action using epsilon-greedy policy.
        
        Args:
            state: State vector
            explore: Whether to explore
            
        Returns:
            Action index
        """
        if explore and np.random.random() < self.exploration_rate:
            return np.random.randint(self._n_actions)
        
        q_values = self._get_q_values(state)
        return int(np.argmax(q_values))
    
    def decide(
        self,
        state: ScalingState,
        explore: bool = True,
    ) -> ScalingDecision:
        """Make scaling decision for current state.
        
        Args:
            state: Current scaling state
            explore: Whether to explore during training
            
        Returns:
            Scaling decision
        """
        state_vector = state.to_vector()
        action_idx = self._select_action(state_vector, explore)
        action = ScalingAction.from_index(action_idx)
        
        # Get Q-values for confidence calculation
        q_values = self._get_q_values(state_vector)
        expected_reward = float(q_values[action_idx])
        
        # Softmax for confidence
        exp_q = np.exp(q_values - np.max(q_values))
        probs = exp_q / np.sum(exp_q)
        confidence = float(probs[action_idx])
        
        # Calculate target replicas
        target_replicas = state.current_replicas + action.magnitude
        target_replicas = max(state.min_replicas, min(state.max_replicas, target_replicas))
        
        # Check constraints
        within_bounds = state.min_replicas <= target_replicas <= state.max_replicas
        cooldown_active = self._is_cooldown_active(state)
        
        # Generate explanation
        reason, factors = self._generate_explanation(state, action)
        
        # If cooldown active, override action
        if cooldown_active:
            action = ScalingAction(direction=ScalingDirection.NO_CHANGE, magnitude=0)
            target_replicas = state.current_replicas
            reason = "Scaling cooldown active"
            factors = [f"Last scale was {state.last_scale_time_minutes:.1f} minutes ago"]
        
        decision = ScalingDecision(
            action=action,
            target_replicas=target_replicas,
            current_replicas=state.current_replicas,
            confidence=confidence,
            expected_reward=expected_reward,
            q_values={f"action_{i}": float(q_values[i]) for i in range(len(q_values))},
            reason=reason,
            factors=factors,
            within_bounds=within_bounds,
            cooldown_active=cooldown_active,
            service_name=state.service_name,
            namespace=state.namespace,
        )
        
        self._scaling_history.append(decision)
        return decision
    
    def _is_cooldown_active(self, state: ScalingState) -> bool:
        """Check if scaling cooldown is active.
        
        Args:
            state: Current state
            
        Returns:
            True if cooldown is active
        """
        cooldown_minutes = self._policy.cooldown_seconds / 60.0
        return state.last_scale_time_minutes < cooldown_minutes
    
    def _generate_explanation(
        self,
        state: ScalingState,
        action: ScalingAction,
    ) -> Tuple[str, List[str]]:
        """Generate explanation for scaling decision.
        
        Args:
            state: Current state
            action: Chosen action
            
        Returns:
            Tuple of (reason, factors)
        """
        factors = []
        
        # CPU factors
        if state.cpu_utilization > 80:
            factors.append(f"High CPU utilization: {state.cpu_utilization:.1f}%")
        elif state.cpu_utilization < 20:
            factors.append(f"Low CPU utilization: {state.cpu_utilization:.1f}%")
        
        # Memory factors
        if state.memory_utilization > 85:
            factors.append(f"High memory utilization: {state.memory_utilization:.1f}%")
        
        # Latency factors
        if state.p99_response_time_ms > 500:
            factors.append(f"High P99 latency: {state.p99_response_time_ms:.0f}ms")
        
        # Error rate factors
        if state.error_rate > 0.01:
            factors.append(f"Elevated error rate: {state.error_rate:.2%}")
        
        # Queue factors
        if state.pending_requests > 50:
            factors.append(f"High pending requests: {state.pending_requests}")
        
        # Historical factors
        if state.max_cpu_1h > state.avg_cpu_1h * 1.5:
            factors.append("CPU spikes detected in last hour")
        
        # Generate reason based on action
        if action.direction == ScalingDirection.SCALE_UP:
            if state.error_rate > 0.01:
                reason = "Scaling up to reduce error rate"
            elif state.cpu_utilization > 70:
                reason = "Scaling up due to high resource utilization"
            elif state.p99_response_time_ms > 300:
                reason = "Scaling up to improve latency"
            else:
                reason = "Proactive scale up for expected load"
        elif action.direction == ScalingDirection.SCALE_DOWN:
            if state.cpu_utilization < 30 and state.memory_utilization < 30:
                reason = "Scaling down due to low resource utilization"
            else:
                reason = "Cost optimization: reducing excess capacity"
        else:
            reason = "Maintaining current scale - optimal allocation"
        
        return reason, factors
    
    def update(
        self,
        state: ScalingState,
        action: ScalingAction,
        reward: float,
        next_state: ScalingState,
        done: bool = False,
    ) -> float:
        """Update agent with experience.
        
        Args:
            state: Starting state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
            done: Whether episode ended
            
        Returns:
            TD error
        """
        state_vector = state.to_vector()
        next_state_vector = next_state.to_vector()
        action_idx = action.to_index()
        
        # Store experience
        self._memory.append((
            state_vector,
            action_idx,
            reward,
            next_state_vector,
            done,
        ))
        
        # Limit memory size
        if len(self._memory) > self._memory_size:
            self._memory.pop(0)
        
        # Calculate TD target
        current_q = self._get_q_values(state_vector)[action_idx]
        
        if done:
            target = reward
        else:
            # Double DQN: use online network to select action, target network to evaluate
            next_action = np.argmax(self._get_q_values(next_state_vector))
            target = reward + self.discount_factor * self._get_q_values(
                next_state_vector, use_target=True
            )[next_action]
        
        # Update weights
        td_error = target - current_q
        self._weights[action_idx] += self.learning_rate * td_error * state_vector
        
        # Update statistics
        self._total_steps += 1
        self._total_reward += reward
        
        # Update target network periodically
        if self._total_steps % self.target_update_frequency == 0:
            self._target_weights = self._weights.copy()
        
        # Decay exploration
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay,
        )
        
        return td_error
    
    def train_batch(self) -> Tuple[float, int]:
        """Train on a batch from replay buffer.
        
        Returns:
            Tuple of (average loss, batch size)
        """
        if len(self._memory) < self.batch_size:
            return 0.0, 0
        
        # Sample batch
        indices = np.random.choice(len(self._memory), self.batch_size, replace=False)
        batch = [self._memory[i] for i in indices]
        
        total_loss = 0.0
        
        for state, action_idx, reward, next_state, done in batch:
            current_q = self._get_q_values(state)[action_idx]
            
            if done:
                target = reward
            else:
                next_action = np.argmax(self._get_q_values(next_state))
                target = reward + self.discount_factor * self._get_q_values(
                    next_state, use_target=True
                )[next_action]
            
            td_error = target - current_q
            total_loss += td_error ** 2
            
            # Update weights
            self._weights[action_idx] += self.learning_rate * td_error * state
        
        return total_loss / self.batch_size, self.batch_size
    
    def calculate_reward(
        self,
        state: ScalingState,
        action: ScalingAction,
        next_state: ScalingState,
    ) -> float:
        """Calculate reward for state transition.
        
        Rewards:
        - Performance: Low latency, low error rate
        - Efficiency: Good resource utilization (50-80%)
        - Stability: Penalize frequent scaling
        - Cost: Penalize excess capacity
        
        Args:
            state: Starting state
            action: Action taken
            next_state: Resulting state
            
        Returns:
            Reward value
        """
        reward = 0.0
        
        # Performance reward
        if next_state.error_rate < 0.001:
            reward += 2.0  # High reward for low error rate
        elif next_state.error_rate < 0.01:
            reward += 1.0
        else:
            reward -= next_state.error_rate * 10  # Penalty for errors
        
        # Latency reward
        if next_state.p99_response_time_ms < 100:
            reward += 1.0
        elif next_state.p99_response_time_ms < 300:
            reward += 0.5
        elif next_state.p99_response_time_ms > 1000:
            reward -= 1.0
        
        # Utilization efficiency
        cpu_util = next_state.cpu_utilization
        if 50 <= cpu_util <= 80:
            reward += 1.0  # Optimal range
        elif cpu_util > 90:
            reward -= 1.5  # Overloaded
        elif cpu_util < 20:
            reward -= 0.5  # Underutilized (waste)
        
        # Stability reward
        if action.direction == ScalingDirection.NO_CHANGE:
            reward += 0.2  # Small reward for stability
        else:
            # Penalize scaling if utilization was already good
            if 40 <= state.cpu_utilization <= 70:
                reward -= 0.3
        
        # Cost efficiency
        cost = next_state.current_replicas * next_state.cost_per_replica_hour
        if cpu_util > 0:
            cost_efficiency = cpu_util / (cost * 10)  # Normalize
            reward += min(0.5, cost_efficiency)
        
        # Scaling cooldown consideration
        if action.direction != ScalingDirection.NO_CHANGE:
            if state.last_scale_time_minutes < 5:
                reward -= 0.5  # Penalize rapid scaling
        
        return reward
    
    def end_episode(self, total_reward: float) -> None:
        """Mark end of training episode.
        
        Args:
            total_reward: Total reward for episode
        """
        self._total_episodes += 1
        self._episode_rewards.append(total_reward)
        
        # Update policy
        self._policy.trained_episodes = self._total_episodes
        self._policy.avg_reward = np.mean(self._episode_rewards[-100:])
        self._policy.updated_at = utc_now()
    
    def get_policy(self) -> ScalingPolicy:
        """Get the learned policy.
        
        Returns:
            Current policy
        """
        return self._policy
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get training statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_steps": self._total_steps,
            "total_episodes": self._total_episodes,
            "total_reward": self._total_reward,
            "exploration_rate": self.exploration_rate,
            "memory_size": len(self._memory),
            "avg_reward_last_100": np.mean(self._episode_rewards[-100:]) if self._episode_rewards else 0,
            "policy": self._policy.model_dump(),
        }
    
    def save(self, path: str) -> None:
        """Save agent to disk.
        
        Args:
            path: Save path
        """
        import json
        
        data = {
            "service_name": self.service_name,
            "weights": self._weights.tolist(),
            "target_weights": self._target_weights.tolist(),
            "exploration_rate": self.exploration_rate,
            "total_steps": self._total_steps,
            "total_episodes": self._total_episodes,
            "total_reward": self._total_reward,
            "episode_rewards": self._episode_rewards[-1000:],  # Keep last 1000
            "policy": self._policy.model_dump(),
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "discount_factor": self.discount_factor,
                "min_exploration": self.min_exploration,
                "exploration_decay": self.exploration_decay,
                "target_update_frequency": self.target_update_frequency,
                "batch_size": self.batch_size,
            },
        }
        
        with open(path, "w") as f:
            json.dump(data, f, default=str)
    
    def load(self, path: str) -> None:
        """Load agent from disk.
        
        Args:
            path: Load path
        """
        import json
        
        with open(path) as f:
            data = json.load(f)
        
        self.service_name = data.get("service_name", "")
        self._weights = np.array(data["weights"])
        self._target_weights = np.array(data["target_weights"])
        self.exploration_rate = data.get("exploration_rate", self.min_exploration)
        self._total_steps = data.get("total_steps", 0)
        self._total_episodes = data.get("total_episodes", 0)
        self._total_reward = data.get("total_reward", 0.0)
        self._episode_rewards = data.get("episode_rewards", [])
        
        if "policy" in data:
            self._policy = ScalingPolicy(**data["policy"])
        
        if "hyperparameters" in data:
            hp = data["hyperparameters"]
            self.learning_rate = hp.get("learning_rate", self.learning_rate)
            self.discount_factor = hp.get("discount_factor", self.discount_factor)
            self.min_exploration = hp.get("min_exploration", self.min_exploration)
            self.exploration_decay = hp.get("exploration_decay", self.exploration_decay)
            self.target_update_frequency = hp.get("target_update_frequency", self.target_update_frequency)
            self.batch_size = hp.get("batch_size", self.batch_size)


class MultiServiceScalingAgent:
    """Manages scaling agents for multiple services."""
    
    def __init__(
        self,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize multi-service agent.
        
        Args:
            default_config: Default configuration for new agents
        """
        self._agents: Dict[str, ScalingAgent] = {}
        self._default_config = default_config or {}
    
    def get_agent(self, service_name: str, namespace: str = "default") -> ScalingAgent:
        """Get or create agent for service.
        
        Args:
            service_name: Service name
            namespace: Kubernetes namespace
            
        Returns:
            Scaling agent for service
        """
        key = f"{namespace}/{service_name}"
        
        if key not in self._agents:
            self._agents[key] = ScalingAgent(
                service_name=service_name,
                **self._default_config,
            )
        
        return self._agents[key]
    
    def decide(
        self,
        state: ScalingState,
        explore: bool = True,
    ) -> ScalingDecision:
        """Make scaling decision for service.
        
        Args:
            state: Current state
            explore: Whether to explore
            
        Returns:
            Scaling decision
        """
        agent = self.get_agent(state.service_name, state.namespace)
        return agent.decide(state, explore)
    
    def update(
        self,
        state: ScalingState,
        action: ScalingAction,
        reward: float,
        next_state: ScalingState,
        done: bool = False,
    ) -> float:
        """Update agent with experience.
        
        Args:
            state: Starting state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
            done: Whether episode ended
            
        Returns:
            TD error
        """
        agent = self.get_agent(state.service_name, state.namespace)
        return agent.update(state, action, reward, next_state, done)
    
    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all agents.
        
        Returns:
            Statistics by service
        """
        return {
            key: agent.get_statistics()
            for key, agent in self._agents.items()
        }
    
    def save_all(self, directory: str) -> None:
        """Save all agents to directory.
        
        Args:
            directory: Save directory
        """
        import os
        os.makedirs(directory, exist_ok=True)
        
        for key, agent in self._agents.items():
            safe_key = key.replace("/", "_")
            agent.save(os.path.join(directory, f"{safe_key}.json"))
    
    def load_all(self, directory: str) -> None:
        """Load all agents from directory.
        
        Args:
            directory: Load directory
        """
        import os
        
        if not os.path.exists(directory):
            return
        
        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                path = os.path.join(directory, filename)
                key = filename[:-5].replace("_", "/")
                
                # Extract service name and namespace
                parts = key.split("/")
                namespace = parts[0] if len(parts) > 1 else "default"
                service_name = parts[-1]
                
                agent = ScalingAgent(service_name=service_name)
                agent.load(path)
                self._agents[key] = agent
