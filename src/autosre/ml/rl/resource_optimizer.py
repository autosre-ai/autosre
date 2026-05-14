"""Resource optimization using reinforcement learning."""

from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class ResourceType(str, Enum):
    """Type of resource."""
    CPU = "cpu"
    MEMORY = "memory"
    REPLICAS = "replicas"
    INSTANCES = "instances"


class ResourceAction(str, Enum):
    """Possible resource actions."""
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"
    LARGE_INCREASE = "large_increase"
    LARGE_DECREASE = "large_decrease"


class ResourceState(BaseModel):
    """State representation for resource optimization."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Current utilization
    cpu_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_utilization: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Current allocation
    current_replicas: int = Field(default=1, ge=0)
    current_cpu_limit: float = Field(default=1.0, ge=0.0)
    current_memory_limit: float = Field(default=1.0, ge=0.0)
    
    # Traffic
    request_rate: float = Field(default=0.0, ge=0.0)
    latency_p99: float = Field(default=0.0, ge=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Time features
    hour_of_day: int = Field(default=12, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    
    # Historical
    avg_utilization_1h: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_utilization_24h: float = Field(default=0.0, ge=0.0, le=100.0)
    
    def to_vector(self) -> np.ndarray:
        """Convert state to feature vector."""
        return np.array([
            self.cpu_utilization / 100.0,
            self.memory_utilization / 100.0,
            self.current_replicas / 10.0,  # Normalize
            self.current_cpu_limit,
            self.current_memory_limit,
            self.request_rate / 1000.0,  # Normalize
            self.latency_p99 / 1000.0,
            self.error_rate,
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
            self.avg_utilization_1h / 100.0,
            self.avg_utilization_24h / 100.0,
        ])


class ResourceDecision(BaseModel):
    """Resource optimization decision."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    decision_id: str = Field(default_factory=generate_id)
    
    # Action
    action: ResourceAction = Field(default=ResourceAction.MAINTAIN)
    resource_type: ResourceType = Field(default=ResourceType.REPLICAS)
    
    # Values
    current_value: float = Field(default=0.0)
    recommended_value: float = Field(default=0.0)
    change_amount: float = Field(default=0.0)
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_reward: float = Field(default=0.0)
    
    # State
    state: Optional[ResourceState] = None
    
    # Reasoning
    reason: str = Field(default="")
    
    # Metadata
    decided_at: datetime = Field(default_factory=utc_now)


class ResourceOptimizer:
    """Reinforcement learning agent for resource optimization.
    
    Learns optimal resource allocation policies:
    - When to scale up/down
    - Optimal resource limits
    - Cost-efficiency trade-offs
    
    Uses Q-learning with function approximation.
    """
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.1,
        min_exploration: float = 0.01,
        exploration_decay: float = 0.995,
    ):
        """Initialize the optimizer.
        
        Args:
            learning_rate: Learning rate (alpha)
            discount_factor: Discount factor (gamma)
            exploration_rate: Initial exploration rate (epsilon)
            min_exploration: Minimum exploration rate
            exploration_decay: Exploration decay rate
        """
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.min_exploration = min_exploration
        self.exploration_decay = exploration_decay
        
        # State dimension
        self._state_dim = 12
        
        # Actions
        self._actions = list(ResourceAction)
        self._n_actions = len(self._actions)
        
        # Q-function weights (linear approximation)
        self._weights = np.zeros((self._n_actions, self._state_dim))
        
        # Experience buffer
        self._experience: List[Tuple[np.ndarray, int, float, np.ndarray, bool]] = []
        self._max_experience = 10000
        
        # Statistics
        self._total_episodes = 0
        self._total_steps = 0
        self._total_reward = 0.0
    
    def _get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for all actions in a state.
        
        Args:
            state: State vector
            
        Returns:
            Q-values for each action
        """
        return np.dot(self._weights, state)
    
    def _select_action(self, state: np.ndarray, explore: bool = True) -> int:
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
        state: ResourceState,
        resource_type: ResourceType = ResourceType.REPLICAS,
        explore: bool = True,
    ) -> ResourceDecision:
        """Make resource optimization decision.
        
        Args:
            state: Current resource state
            resource_type: Type of resource to optimize
            explore: Whether to explore (for training)
            
        Returns:
            Resource decision
        """
        state_vector = state.to_vector()
        action_idx = self._select_action(state_vector, explore)
        action = self._actions[action_idx]
        
        # Get Q-values for confidence
        q_values = self._get_q_values(state_vector)
        expected_reward = float(q_values[action_idx])
        
        # Softmax for confidence
        exp_q = np.exp(q_values - np.max(q_values))
        probs = exp_q / np.sum(exp_q)
        confidence = float(probs[action_idx])
        
        # Determine change amount
        if resource_type == ResourceType.REPLICAS:
            current_value = state.current_replicas
            if action == ResourceAction.INCREASE:
                change_amount = 1
            elif action == ResourceAction.LARGE_INCREASE:
                change_amount = 2
            elif action == ResourceAction.DECREASE:
                change_amount = -1
            elif action == ResourceAction.LARGE_DECREASE:
                change_amount = -2
            else:
                change_amount = 0
        else:
            current_value = state.current_cpu_limit if resource_type == ResourceType.CPU else state.current_memory_limit
            if action in [ResourceAction.INCREASE, ResourceAction.LARGE_INCREASE]:
                change_amount = 0.25 if action == ResourceAction.INCREASE else 0.5
            elif action in [ResourceAction.DECREASE, ResourceAction.LARGE_DECREASE]:
                change_amount = -0.25 if action == ResourceAction.DECREASE else -0.5
            else:
                change_amount = 0
        
        recommended_value = max(0, current_value + change_amount)
        
        # Generate reason
        reason = self._generate_reason(state, action)
        
        return ResourceDecision(
            action=action,
            resource_type=resource_type,
            current_value=current_value,
            recommended_value=recommended_value,
            change_amount=change_amount,
            confidence=confidence,
            expected_reward=expected_reward,
            state=state,
            reason=reason,
        )
    
    def _generate_reason(
        self,
        state: ResourceState,
        action: ResourceAction,
    ) -> str:
        """Generate explanation for decision.
        
        Args:
            state: Current state
            action: Chosen action
            
        Returns:
            Explanation string
        """
        reasons = []
        
        if state.cpu_utilization > 80:
            reasons.append(f"High CPU utilization ({state.cpu_utilization:.1f}%)")
        elif state.cpu_utilization < 30:
            reasons.append(f"Low CPU utilization ({state.cpu_utilization:.1f}%)")
        
        if state.error_rate > 0.01:
            reasons.append(f"Elevated error rate ({state.error_rate:.2%})")
        
        if state.latency_p99 > 500:
            reasons.append(f"High latency ({state.latency_p99:.0f}ms)")
        
        if action in [ResourceAction.INCREASE, ResourceAction.LARGE_INCREASE]:
            return f"Scaling up due to: {', '.join(reasons)}" if reasons else "Proactive scaling for expected load"
        elif action in [ResourceAction.DECREASE, ResourceAction.LARGE_DECREASE]:
            return "Scaling down due to low utilization" if state.cpu_utilization < 30 else "Cost optimization"
        else:
            return "Maintaining current resources - optimal allocation"
    
    def update(
        self,
        state: ResourceState,
        action: ResourceAction,
        reward: float,
        next_state: ResourceState,
        done: bool = False,
    ) -> None:
        """Update Q-function with experience.
        
        Args:
            state: Starting state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
            done: Whether episode ended
        """
        state_vector = state.to_vector()
        next_state_vector = next_state.to_vector()
        action_idx = self._actions.index(action)
        
        # Store experience
        self._experience.append((
            state_vector, action_idx, reward, next_state_vector, done
        ))
        
        if len(self._experience) > self._max_experience:
            self._experience.pop(0)
        
        # Q-learning update
        current_q = self._get_q_values(state_vector)[action_idx]
        
        if done:
            target = reward
        else:
            next_q_values = self._get_q_values(next_state_vector)
            target = reward + self.discount_factor * np.max(next_q_values)
        
        # Update weights
        td_error = target - current_q
        self._weights[action_idx] += self.learning_rate * td_error * state_vector
        
        # Update statistics
        self._total_steps += 1
        self._total_reward += reward
        
        # Decay exploration
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay
        )
    
    def calculate_reward(
        self,
        state: ResourceState,
        action: ResourceAction,
        next_state: ResourceState,
    ) -> float:
        """Calculate reward for state transition.
        
        Args:
            state: Starting state
            action: Action taken
            next_state: Resulting state
            
        Returns:
            Reward value
        """
        reward = 0.0
        
        # Reward for maintaining good performance
        if next_state.error_rate < 0.01:
            reward += 1.0
        else:
            reward -= next_state.error_rate * 10
        
        # Reward for optimal utilization (50-80%)
        if 50 <= next_state.cpu_utilization <= 80:
            reward += 0.5
        elif next_state.cpu_utilization > 90:
            reward -= 1.0  # Penalty for overload
        elif next_state.cpu_utilization < 20:
            reward -= 0.3  # Penalty for waste
        
        # Reward for low latency
        if next_state.latency_p99 < 100:
            reward += 0.5
        elif next_state.latency_p99 > 500:
            reward -= 0.5
        
        # Cost penalty for scaling up
        if action in [ResourceAction.INCREASE, ResourceAction.LARGE_INCREASE]:
            reward -= 0.1  # Small cost for adding resources
        elif action in [ResourceAction.DECREASE, ResourceAction.LARGE_DECREASE]:
            reward += 0.05  # Small reward for reducing resources
        
        return reward
    
    def train_batch(self, batch_size: int = 32) -> float:
        """Train on a batch of experiences.
        
        Args:
            batch_size: Batch size
            
        Returns:
            Average loss
        """
        if len(self._experience) < batch_size:
            return 0.0
        
        # Sample batch
        indices = np.random.choice(len(self._experience), batch_size, replace=False)
        batch = [self._experience[i] for i in indices]
        
        total_loss = 0.0
        
        for state, action_idx, reward, next_state, done in batch:
            current_q = self._get_q_values(state)[action_idx]
            
            if done:
                target = reward
            else:
                next_q_values = self._get_q_values(next_state)
                target = reward + self.discount_factor * np.max(next_q_values)
            
            td_error = target - current_q
            total_loss += td_error ** 2
            
            # Update
            self._weights[action_idx] += self.learning_rate * td_error * state
        
        return total_loss / batch_size
    
    def get_policy(self) -> Dict[str, Any]:
        """Get the learned policy.
        
        Returns:
            Policy representation
        """
        return {
            "weights": self._weights.tolist(),
            "exploration_rate": self.exploration_rate,
            "total_episodes": self._total_episodes,
            "total_steps": self._total_steps,
            "total_reward": self._total_reward,
        }
    
    def load_policy(self, policy: Dict[str, Any]) -> None:
        """Load a saved policy.
        
        Args:
            policy: Policy dictionary
        """
        self._weights = np.array(policy["weights"])
        self.exploration_rate = policy.get("exploration_rate", self.min_exploration)
        self._total_episodes = policy.get("total_episodes", 0)
        self._total_steps = policy.get("total_steps", 0)
        self._total_reward = policy.get("total_reward", 0.0)
    
    def save(self, path: str) -> None:
        """Save the optimizer to disk.
        
        Args:
            path: Save path
        """
        import json
        
        policy = self.get_policy()
        with open(path, "w") as f:
            json.dump(policy, f)
    
    def load(self, path: str) -> None:
        """Load the optimizer from disk.
        
        Args:
            path: Load path
        """
        import json
        
        with open(path) as f:
            policy = json.load(f)
        
        self.load_policy(policy)
