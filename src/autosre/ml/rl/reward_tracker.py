"""Reward tracking for reinforcement learning.

Tracks rewards and outcomes across:
- Resource optimization
- Scaling decisions
- Alert tuning
- Remediation actions

Provides analytics and learning signals.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, List, Dict, Tuple
import statistics

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class RewardType(str, Enum):
    """Type of reward."""
    RESOURCE_OPTIMIZATION = "resource_optimization"
    SCALING = "scaling"
    ALERT_TUNING = "alert_tuning"
    REMEDIATION = "remediation"
    INVESTIGATION = "investigation"
    CUSTOM = "custom"


class RewardSignal(str, Enum):
    """Signal that triggered reward."""
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    COST_REDUCTION = "cost_reduction"
    INCIDENT_PREVENTED = "incident_prevented"
    INCIDENT_RESOLVED = "incident_resolved"
    FALSE_POSITIVE_AVOIDED = "false_positive_avoided"
    SLO_MAINTAINED = "slo_maintained"
    USER_FEEDBACK = "user_feedback"
    AUTOMATED = "automated"


class Reward(BaseModel):
    """A single reward observation."""
    model_config = ConfigDict(validate_assignment=True)
    
    reward_id: str = Field(default_factory=generate_id)
    
    # Context
    reward_type: RewardType = Field(default=RewardType.CUSTOM)
    signal: RewardSignal = Field(default=RewardSignal.AUTOMATED)
    
    # Value
    value: float = Field(default=0.0)
    raw_value: float = Field(default=0.0)  # Before normalization
    
    # Components
    components: Dict[str, float] = Field(default_factory=dict)
    
    # Context
    episode_id: str = Field(default="")
    step: int = Field(default=0, ge=0)
    
    # Association
    service: str = Field(default="")
    action_taken: str = Field(default="")
    state_hash: str = Field(default="")
    
    # Timing
    observed_at: datetime = Field(default_factory=utc_now)
    delay_seconds: float = Field(default=0.0)  # Delay between action and reward
    
    # Confidence
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Episode(BaseModel):
    """A learning episode (sequence of steps)."""
    model_config = ConfigDict(validate_assignment=True)
    
    episode_id: str = Field(default_factory=generate_id)
    
    # Context
    episode_type: RewardType = Field(default=RewardType.CUSTOM)
    service: str = Field(default="")
    
    # Status
    status: str = Field(default="active")  # active, completed, failed
    
    # Timing
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Steps
    steps: int = Field(default=0, ge=0)
    
    # Rewards
    total_reward: float = Field(default=0.0)
    avg_reward: float = Field(default=0.0)
    max_reward: float = Field(default=float("-inf"))
    min_reward: float = Field(default=float("inf"))
    
    # Final outcome
    outcome: str = Field(default="")  # success, failure, timeout
    outcome_details: Dict[str, Any] = Field(default_factory=dict)
    
    # Discounted return
    discounted_return: float = Field(default=0.0)
    
    def add_reward(self, reward: Reward, discount: float = 0.95) -> None:
        """Add reward to episode.
        
        Args:
            reward: Reward to add
            discount: Discount factor
        """
        self.steps += 1
        self.total_reward += reward.value
        self.avg_reward = self.total_reward / self.steps
        self.max_reward = max(self.max_reward, reward.value)
        self.min_reward = min(self.min_reward, reward.value)
        
        # Update discounted return
        self.discounted_return = reward.value + discount * self.discounted_return
    
    def complete(self, outcome: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark episode as completed.
        
        Args:
            outcome: Episode outcome
            details: Outcome details
        """
        self.status = "completed"
        self.completed_at = utc_now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.outcome = outcome
        if details:
            self.outcome_details = details


class RewardStats(BaseModel):
    """Statistics for rewards."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Count
    count: int = Field(default=0, ge=0)
    
    # Value statistics
    mean: float = Field(default=0.0)
    std: float = Field(default=0.0)
    min_value: float = Field(default=0.0)
    max_value: float = Field(default=0.0)
    median: float = Field(default=0.0)
    
    # Percentiles
    p25: float = Field(default=0.0)
    p75: float = Field(default=0.0)
    p90: float = Field(default=0.0)
    p99: float = Field(default=0.0)
    
    # Trend
    trend: str = Field(default="stable")  # improving, declining, stable
    recent_mean: float = Field(default=0.0)  # Last 100 rewards
    
    @classmethod
    def from_values(cls, values: List[float]) -> "RewardStats":
        """Create stats from values.
        
        Args:
            values: List of reward values
            
        Returns:
            RewardStats instance
        """
        if not values:
            return cls()
        
        sorted_values = sorted(values)
        n = len(values)
        
        return cls(
            count=n,
            mean=statistics.mean(values),
            std=statistics.stdev(values) if n > 1 else 0.0,
            min_value=min(values),
            max_value=max(values),
            median=statistics.median(values),
            p25=sorted_values[int(n * 0.25)],
            p75=sorted_values[int(n * 0.75)],
            p90=sorted_values[int(n * 0.90)],
            p99=sorted_values[min(int(n * 0.99), n - 1)],
            recent_mean=statistics.mean(values[-100:]) if values else 0.0,
        )


class RewardTracker:
    """Tracks rewards and outcomes for RL agents.
    
    Provides:
    - Reward normalization
    - Episode tracking
    - Analytics and trends
    - Reward shaping
    """
    
    def __init__(
        self,
        max_history: int = 100000,
        normalization_window: int = 1000,
        discount_factor: float = 0.95,
    ):
        """Initialize reward tracker.
        
        Args:
            max_history: Maximum rewards to keep
            normalization_window: Window for normalization statistics
            discount_factor: Discount factor for returns
        """
        self.max_history = max_history
        self.normalization_window = normalization_window
        self.discount_factor = discount_factor
        
        # Reward storage
        self._rewards: List[Reward] = []
        self._rewards_by_type: Dict[RewardType, List[Reward]] = {
            t: [] for t in RewardType
        }
        
        # Episode storage
        self._episodes: List[Episode] = []
        self._active_episodes: Dict[str, Episode] = {}
        
        # Running statistics for normalization
        self._running_mean: float = 0.0
        self._running_var: float = 1.0
        self._count: int = 0
        
        # Statistics per type
        self._type_stats: Dict[RewardType, Dict[str, float]] = {}
        
        # Service-level statistics
        self._service_stats: Dict[str, Dict[str, float]] = {}
    
    def record(
        self,
        value: float,
        reward_type: RewardType,
        signal: RewardSignal = RewardSignal.AUTOMATED,
        episode_id: str = "",
        step: int = 0,
        service: str = "",
        action: str = "",
        components: Optional[Dict[str, float]] = None,
        normalize: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Reward:
        """Record a reward.
        
        Args:
            value: Raw reward value
            reward_type: Type of reward
            signal: Signal that triggered reward
            episode_id: Associated episode ID
            step: Step in episode
            service: Service name
            action: Action taken
            components: Reward components
            normalize: Whether to normalize reward
            metadata: Additional metadata
            
        Returns:
            Recorded reward
        """
        # Normalize if requested
        normalized_value = self._normalize(value) if normalize else value
        
        reward = Reward(
            reward_type=reward_type,
            signal=signal,
            value=normalized_value,
            raw_value=value,
            components=components or {},
            episode_id=episode_id,
            step=step,
            service=service,
            action_taken=action,
            metadata=metadata or {},
        )
        
        # Store
        self._rewards.append(reward)
        self._rewards_by_type[reward_type].append(reward)
        
        # Limit history
        if len(self._rewards) > self.max_history:
            removed = self._rewards.pop(0)
            self._rewards_by_type[removed.reward_type].pop(0)
        
        # Update running stats
        self._update_running_stats(value)
        
        # Update type stats
        self._update_type_stats(reward_type, value)
        
        # Update service stats
        if service:
            self._update_service_stats(service, value)
        
        # Add to episode if active
        if episode_id and episode_id in self._active_episodes:
            self._active_episodes[episode_id].add_reward(reward, self.discount_factor)
        
        return reward
    
    def _normalize(self, value: float) -> float:
        """Normalize reward value.
        
        Uses running mean and standard deviation.
        
        Args:
            value: Raw value
            
        Returns:
            Normalized value
        """
        if self._count < 10:
            return value
        
        std = np.sqrt(self._running_var)
        if std < 1e-8:
            return value - self._running_mean
        
        return (value - self._running_mean) / std
    
    def _update_running_stats(self, value: float) -> None:
        """Update running statistics.
        
        Uses Welford's online algorithm.
        
        Args:
            value: New value
        """
        self._count += 1
        delta = value - self._running_mean
        self._running_mean += delta / self._count
        delta2 = value - self._running_mean
        self._running_var += (delta * delta2 - self._running_var) / self._count
    
    def _update_type_stats(self, reward_type: RewardType, value: float) -> None:
        """Update per-type statistics.
        
        Args:
            reward_type: Reward type
            value: Reward value
        """
        if reward_type not in self._type_stats:
            self._type_stats[reward_type] = {
                "count": 0,
                "sum": 0.0,
                "sum_sq": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }
        
        stats = self._type_stats[reward_type]
        stats["count"] += 1
        stats["sum"] += value
        stats["sum_sq"] += value ** 2
        stats["min"] = min(stats["min"], value)
        stats["max"] = max(stats["max"], value)
    
    def _update_service_stats(self, service: str, value: float) -> None:
        """Update per-service statistics.
        
        Args:
            service: Service name
            value: Reward value
        """
        if service not in self._service_stats:
            self._service_stats[service] = {
                "count": 0,
                "sum": 0.0,
                "sum_sq": 0.0,
            }
        
        stats = self._service_stats[service]
        stats["count"] += 1
        stats["sum"] += value
        stats["sum_sq"] += value ** 2
    
    def start_episode(
        self,
        episode_type: RewardType,
        service: str = "",
    ) -> Episode:
        """Start a new episode.
        
        Args:
            episode_type: Type of episode
            service: Service name
            
        Returns:
            New episode
        """
        episode = Episode(
            episode_type=episode_type,
            service=service,
        )
        
        self._active_episodes[episode.episode_id] = episode
        return episode
    
    def end_episode(
        self,
        episode_id: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Episode]:
        """End an episode.
        
        Args:
            episode_id: Episode ID
            outcome: Episode outcome
            details: Outcome details
            
        Returns:
            Completed episode or None
        """
        if episode_id not in self._active_episodes:
            return None
        
        episode = self._active_episodes.pop(episode_id)
        episode.complete(outcome, details)
        
        self._episodes.append(episode)
        
        # Limit episode history
        if len(self._episodes) > 10000:
            self._episodes.pop(0)
        
        return episode
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID.
        
        Args:
            episode_id: Episode ID
            
        Returns:
            Episode or None
        """
        # Check active
        if episode_id in self._active_episodes:
            return self._active_episodes[episode_id]
        
        # Check completed
        for ep in reversed(self._episodes):
            if ep.episode_id == episode_id:
                return ep
        
        return None
    
    def shape_reward(
        self,
        reward: float,
        reward_type: RewardType,
        potential_before: float,
        potential_after: float,
    ) -> float:
        """Shape reward using potential-based shaping.
        
        F(s, s') = γ * Φ(s') - Φ(s)
        
        This is guaranteed to not change the optimal policy.
        
        Args:
            reward: Original reward
            reward_type: Type of reward
            potential_before: Potential of state before action
            potential_after: Potential of state after action
            
        Returns:
            Shaped reward
        """
        shaping = self.discount_factor * potential_after - potential_before
        return reward + shaping
    
    def compute_return(
        self,
        rewards: List[float],
        start_index: int = 0,
    ) -> float:
        """Compute discounted return.
        
        Args:
            rewards: List of rewards
            start_index: Starting index
            
        Returns:
            Discounted return
        """
        total = 0.0
        discount = 1.0
        
        for r in rewards[start_index:]:
            total += discount * r
            discount *= self.discount_factor
        
        return total
    
    def compute_advantages(
        self,
        rewards: List[float],
        values: List[float],
        lambda_gae: float = 0.95,
    ) -> List[float]:
        """Compute Generalized Advantage Estimation (GAE).
        
        Args:
            rewards: List of rewards
            values: List of value estimates
            lambda_gae: GAE lambda parameter
            
        Returns:
            List of advantages
        """
        if len(rewards) != len(values):
            raise ValueError("rewards and values must have same length")
        
        n = len(rewards)
        advantages = [0.0] * n
        gae = 0.0
        
        for t in reversed(range(n - 1)):
            delta = rewards[t] + self.discount_factor * values[t + 1] - values[t]
            gae = delta + self.discount_factor * lambda_gae * gae
            advantages[t] = gae
        
        return advantages
    
    def get_statistics(
        self,
        reward_type: Optional[RewardType] = None,
        service: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> RewardStats:
        """Get reward statistics.
        
        Args:
            reward_type: Filter by type
            service: Filter by service
            time_window: Time window to consider
            
        Returns:
            Reward statistics
        """
        rewards = self._rewards
        
        # Filter by type
        if reward_type:
            rewards = self._rewards_by_type.get(reward_type, [])
        
        # Filter by service
        if service:
            rewards = [r for r in rewards if r.service == service]
        
        # Filter by time
        if time_window:
            cutoff = utc_now() - time_window
            rewards = [r for r in rewards if r.observed_at >= cutoff]
        
        values = [r.raw_value for r in rewards]
        stats = RewardStats.from_values(values)
        
        # Determine trend
        if len(values) >= 200:
            old_mean = statistics.mean(values[:100])
            new_mean = statistics.mean(values[-100:])
            if new_mean > old_mean * 1.1:
                stats.trend = "improving"
            elif new_mean < old_mean * 0.9:
                stats.trend = "declining"
            else:
                stats.trend = "stable"
        
        return stats
    
    def get_episode_statistics(
        self,
        episode_type: Optional[RewardType] = None,
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get episode statistics.
        
        Args:
            episode_type: Filter by type
            service: Filter by service
            
        Returns:
            Episode statistics
        """
        episodes = self._episodes
        
        if episode_type:
            episodes = [e for e in episodes if e.episode_type == episode_type]
        
        if service:
            episodes = [e for e in episodes if e.service == service]
        
        if not episodes:
            return {
                "count": 0,
                "avg_return": 0.0,
                "avg_steps": 0.0,
                "success_rate": 0.0,
            }
        
        returns = [e.total_reward for e in episodes]
        steps = [e.steps for e in episodes]
        successes = sum(1 for e in episodes if e.outcome == "success")
        
        return {
            "count": len(episodes),
            "avg_return": statistics.mean(returns),
            "std_return": statistics.stdev(returns) if len(returns) > 1 else 0.0,
            "avg_steps": statistics.mean(steps),
            "max_steps": max(steps),
            "success_rate": successes / len(episodes),
            "avg_duration": statistics.mean([
                e.duration_seconds for e in episodes if e.duration_seconds
            ]) if any(e.duration_seconds for e in episodes) else 0.0,
        }
    
    def get_reward_breakdown(
        self,
        time_window: Optional[timedelta] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get reward breakdown by type.
        
        Args:
            time_window: Time window to consider
            
        Returns:
            Breakdown by type
        """
        breakdown = {}
        
        for reward_type in RewardType:
            stats = self.get_statistics(reward_type=reward_type, time_window=time_window)
            if stats.count > 0:
                breakdown[reward_type.value] = {
                    "count": stats.count,
                    "mean": stats.mean,
                    "std": stats.std,
                    "trend": stats.trend,
                }
        
        return breakdown
    
    def get_service_comparison(self) -> Dict[str, Dict[str, float]]:
        """Get reward comparison across services.
        
        Returns:
            Comparison by service
        """
        comparison = {}
        
        for service, stats in self._service_stats.items():
            count = stats["count"]
            if count > 0:
                mean = stats["sum"] / count
                variance = (stats["sum_sq"] / count) - (mean ** 2)
                std = np.sqrt(max(0, variance))
                
                comparison[service] = {
                    "count": count,
                    "mean": mean,
                    "std": std,
                }
        
        return comparison
    
    def get_recent_rewards(
        self,
        n: int = 100,
        reward_type: Optional[RewardType] = None,
    ) -> List[Reward]:
        """Get recent rewards.
        
        Args:
            n: Number of rewards
            reward_type: Filter by type
            
        Returns:
            Recent rewards
        """
        if reward_type:
            rewards = self._rewards_by_type.get(reward_type, [])
        else:
            rewards = self._rewards
        
        return rewards[-n:]
    
    def export_for_training(
        self,
        episode_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Export rewards for training.
        
        Args:
            episode_ids: Specific episodes to export
            
        Returns:
            List of reward dictionaries
        """
        rewards = self._rewards
        
        if episode_ids:
            rewards = [r for r in rewards if r.episode_id in episode_ids]
        
        return [
            {
                "reward_type": r.reward_type.value,
                "value": r.value,
                "raw_value": r.raw_value,
                "episode_id": r.episode_id,
                "step": r.step,
                "service": r.service,
                "action": r.action_taken,
                "components": r.components,
            }
            for r in rewards
        ]
    
    def reset_running_stats(self) -> None:
        """Reset running normalization statistics."""
        self._running_mean = 0.0
        self._running_var = 1.0
        self._count = 0
    
    def save(self, path: str) -> None:
        """Save tracker to disk.
        
        Args:
            path: Save path
        """
        import json
        
        data = {
            "running_mean": self._running_mean,
            "running_var": self._running_var,
            "count": self._count,
            "type_stats": {k.value: v for k, v in self._type_stats.items()},
            "service_stats": self._service_stats,
            "recent_rewards": [r.model_dump() for r in self._rewards[-1000:]],
            "recent_episodes": [e.model_dump() for e in self._episodes[-100:]],
            "config": {
                "max_history": self.max_history,
                "normalization_window": self.normalization_window,
                "discount_factor": self.discount_factor,
            },
        }
        
        with open(path, "w") as f:
            json.dump(data, f, default=str)
    
    def load(self, path: str) -> None:
        """Load tracker from disk.
        
        Args:
            path: Load path
        """
        import json
        
        with open(path) as f:
            data = json.load(f)
        
        self._running_mean = data.get("running_mean", 0.0)
        self._running_var = data.get("running_var", 1.0)
        self._count = data.get("count", 0)
        
        self._type_stats = {
            RewardType(k): v for k, v in data.get("type_stats", {}).items()
        }
        self._service_stats = data.get("service_stats", {})
        
        # Reload recent rewards
        for reward_data in data.get("recent_rewards", []):
            if "reward_type" in reward_data:
                reward_data["reward_type"] = RewardType(reward_data["reward_type"])
            if "signal" in reward_data:
                reward_data["signal"] = RewardSignal(reward_data["signal"])
            if "observed_at" in reward_data and isinstance(reward_data["observed_at"], str):
                reward_data["observed_at"] = datetime.fromisoformat(reward_data["observed_at"].replace("Z", "+00:00"))
            
            reward = Reward(**reward_data)
            self._rewards.append(reward)
            self._rewards_by_type[reward.reward_type].append(reward)
        
        # Reload recent episodes
        for episode_data in data.get("recent_episodes", []):
            if "episode_type" in episode_data:
                episode_data["episode_type"] = RewardType(episode_data["episode_type"])
            if "started_at" in episode_data and isinstance(episode_data["started_at"], str):
                episode_data["started_at"] = datetime.fromisoformat(episode_data["started_at"].replace("Z", "+00:00"))
            if "completed_at" in episode_data and episode_data["completed_at"] and isinstance(episode_data["completed_at"], str):
                episode_data["completed_at"] = datetime.fromisoformat(episode_data["completed_at"].replace("Z", "+00:00"))
            
            episode = Episode(**episode_data)
            self._episodes.append(episode)
        
        if "config" in data:
            self.max_history = data["config"].get("max_history", self.max_history)
            self.normalization_window = data["config"].get("normalization_window", self.normalization_window)
            self.discount_factor = data["config"].get("discount_factor", self.discount_factor)
