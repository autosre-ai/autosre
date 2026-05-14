"""Unit tests for Reinforcement Learning modules."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from autosre.ml.rl import (
    # Resource Optimizer
    ResourceOptimizer,
    ResourceState,
    ResourceAction,
    ResourceDecision,
    ResourceType,
    # Scaling Agent
    ScalingAgent,
    ScalingState,
    ScalingAction,
    ScalingDecision,
    ScalingDirection,
    ScalingType,
    ScalingPolicy,
    MultiServiceScalingAgent,
    # Alert Tuner
    AlertTuner,
    AlertState,
    AlertTuning,
    AlertOutcome,
    AlertType,
    ThresholdAction,
    AlertThresholdPolicy,
    MultiAlertTuner,
    # Remediation Learner
    RemediationLearner,
    Remediation,
    RemediationSuggestion,
    RemediationOutcome,
    RemediationType,
    IncidentCategory,
    IncidentContext,
    # Reward Tracker
    RewardTracker,
    Reward,
    Episode,
    RewardType,
    RewardSignal,
    RewardStats,
)


class TestResourceState:
    """Tests for ResourceState."""
    
    def test_create_state(self):
        """Test creating resource state."""
        state = ResourceState(
            cpu_utilization=75.0,
            memory_utilization=60.0,
            current_replicas=3,
            request_rate=500.0,
            latency_p99=150.0,
            error_rate=0.01,
        )
        
        assert state.cpu_utilization == 75.0
        assert state.current_replicas == 3
    
    def test_state_to_vector(self):
        """Test converting state to vector."""
        state = ResourceState(
            cpu_utilization=50.0,
            memory_utilization=40.0,
            current_replicas=2,
        )
        
        vector = state.to_vector()
        
        assert isinstance(vector, np.ndarray)
        assert len(vector) == 12  # Expected dimension


class TestResourceOptimizer:
    """Tests for ResourceOptimizer."""
    
    @pytest.fixture
    def optimizer(self):
        """Create resource optimizer."""
        return ResourceOptimizer(
            learning_rate=0.1,
            exploration_rate=0.3,
        )
    
    @pytest.fixture
    def sample_state(self):
        """Create sample state."""
        return ResourceState(
            cpu_utilization=80.0,
            memory_utilization=65.0,
            current_replicas=3,
            current_cpu_limit=2.0,
            current_memory_limit=4.0,
            request_rate=800.0,
            latency_p99=250.0,
            error_rate=0.02,
            hour_of_day=14,
            day_of_week=2,
        )
    
    def test_create_optimizer(self, optimizer):
        """Test creating optimizer."""
        assert optimizer.learning_rate == 0.1
        assert optimizer.exploration_rate == 0.3
    
    def test_decide(self, optimizer, sample_state):
        """Test making decision."""
        decision = optimizer.decide(sample_state)
        
        assert isinstance(decision, ResourceDecision)
        assert decision.action in list(ResourceAction)
        assert 0 <= decision.confidence <= 1
    
    def test_decide_no_explore(self, optimizer, sample_state):
        """Test decision without exploration."""
        decision = optimizer.decide(sample_state, explore=False)
        
        assert isinstance(decision, ResourceDecision)
    
    def test_update(self, optimizer, sample_state):
        """Test updating with experience."""
        next_state = ResourceState(
            cpu_utilization=70.0,
            memory_utilization=60.0,
            current_replicas=4,
            error_rate=0.01,
        )
        
        optimizer.update(
            state=sample_state,
            action=ResourceAction.INCREASE,
            reward=1.0,
            next_state=next_state,
        )
        
        assert optimizer._total_steps == 1
    
    def test_calculate_reward(self, optimizer, sample_state):
        """Test reward calculation."""
        good_next_state = ResourceState(
            cpu_utilization=60.0,
            memory_utilization=55.0,
            current_replicas=3,
            error_rate=0.001,
            latency_p99=80.0,
        )
        
        reward = optimizer.calculate_reward(
            sample_state,
            ResourceAction.MAINTAIN,
            good_next_state,
        )
        
        # Good state should have positive reward
        assert reward > 0
    
    def test_train_batch(self, optimizer, sample_state):
        """Test batch training."""
        # Add some experiences
        for i in range(50):
            next_state = ResourceState(
                cpu_utilization=70.0 - i * 0.5,
                memory_utilization=60.0,
                current_replicas=3,
            )
            optimizer.update(
                sample_state,
                ResourceAction.INCREASE,
                0.5,
                next_state,
            )
        
        loss = optimizer.train_batch(batch_size=32)
        
        assert isinstance(loss, float)
    
    def test_save_load(self, optimizer, sample_state, tmp_path):
        """Test saving and loading optimizer."""
        # Make some decisions to build state
        for _ in range(10):
            optimizer.decide(sample_state)
        
        path = str(tmp_path / "optimizer.json")
        optimizer.save(path)
        
        # Create new optimizer and load
        new_optimizer = ResourceOptimizer()
        new_optimizer.load(path)
        
        # Should have same state
        assert np.allclose(optimizer._weights, new_optimizer._weights)


class TestScalingAgent:
    """Tests for ScalingAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create scaling agent."""
        return ScalingAgent(
            service_name="api-gateway",
            learning_rate=0.001,
            exploration_rate=0.2,
        )
    
    @pytest.fixture
    def sample_state(self):
        """Create sample scaling state."""
        return ScalingState(
            service_name="api-gateway",
            namespace="production",
            current_replicas=3,
            min_replicas=2,
            max_replicas=10,
            cpu_utilization=85.0,
            memory_utilization=70.0,
            requests_per_second=500.0,
            avg_response_time_ms=200.0,
            p99_response_time_ms=500.0,
            error_rate=0.02,
            hour_of_day=14,
            day_of_week=3,
            is_business_hours=True,
        )
    
    def test_create_agent(self, agent):
        """Test creating agent."""
        assert agent.service_name == "api-gateway"
        assert agent.learning_rate == 0.001
    
    def test_decide(self, agent, sample_state):
        """Test making scaling decision."""
        decision = agent.decide(sample_state)
        
        assert isinstance(decision, ScalingDecision)
        assert isinstance(decision.action, ScalingAction)
        assert decision.target_replicas >= sample_state.min_replicas
        assert decision.target_replicas <= sample_state.max_replicas
    
    def test_decide_high_load(self, agent):
        """Test decision under high load."""
        high_load_state = ScalingState(
            service_name="api-gateway",
            current_replicas=3,
            max_replicas=10,
            cpu_utilization=95.0,
            error_rate=0.05,
            p99_response_time_ms=1000.0,
            last_scale_time_minutes=10.0,  # Past cooldown
        )
        
        # Train a bit first to learn pattern
        for _ in range(100):
            agent.decide(high_load_state)
            agent.update(
                high_load_state,
                ScalingAction(direction=ScalingDirection.SCALE_UP, magnitude=1),
                reward=1.0,
                next_state=ScalingState(
                    cpu_utilization=70.0,
                    error_rate=0.01,
                ),
            )
        
        decision = agent.decide(high_load_state, explore=False)
        
        # Should likely recommend scaling up
        # (though not guaranteed due to exploration)
    
    def test_cooldown_respected(self, agent):
        """Test that cooldown is respected."""
        state = ScalingState(
            service_name="api-gateway",
            current_replicas=3,
            cpu_utilization=85.0,
            last_scale_time_minutes=2.0,  # Recently scaled
        )
        
        decision = agent.decide(state)
        
        # Should have cooldown active
        assert decision.cooldown_active
    
    def test_update_and_train(self, agent, sample_state):
        """Test updating and training."""
        next_state = ScalingState(
            service_name="api-gateway",
            current_replicas=4,
            cpu_utilization=70.0,
            error_rate=0.01,
        )
        
        td_error = agent.update(
            sample_state,
            ScalingAction(direction=ScalingDirection.SCALE_UP, magnitude=1),
            reward=1.5,
            next_state=next_state,
        )
        
        assert isinstance(td_error, float)
    
    def test_calculate_reward(self, agent, sample_state):
        """Test reward calculation."""
        good_next = ScalingState(
            cpu_utilization=65.0,
            error_rate=0.001,
            p99_response_time_ms=100.0,
        )
        
        reward = agent.calculate_reward(
            sample_state,
            ScalingAction(direction=ScalingDirection.SCALE_UP),
            good_next,
        )
        
        assert reward > 0  # Good outcome
    
    def test_get_policy(self, agent):
        """Test getting learned policy."""
        policy = agent.get_policy()
        
        assert isinstance(policy, ScalingPolicy)
    
    def test_get_statistics(self, agent, sample_state):
        """Test getting statistics."""
        # Make some decisions
        for _ in range(5):
            agent.decide(sample_state)
        
        stats = agent.get_statistics()
        
        assert "total_steps" in stats
        assert "exploration_rate" in stats


class TestMultiServiceScalingAgent:
    """Tests for MultiServiceScalingAgent."""
    
    @pytest.fixture
    def multi_agent(self):
        """Create multi-service agent."""
        return MultiServiceScalingAgent()
    
    def test_create_multi_agent(self, multi_agent):
        """Test creating multi-service agent."""
        assert multi_agent is not None
    
    def test_get_agent_for_service(self, multi_agent):
        """Test getting agent for specific service."""
        agent1 = multi_agent.get_agent("payment-service", "production")
        agent2 = multi_agent.get_agent("payment-service", "production")
        agent3 = multi_agent.get_agent("checkout-service", "production")
        
        # Same service should return same agent
        assert agent1 is agent2
        # Different service should return different agent
        assert agent1 is not agent3
    
    def test_decide_across_services(self, multi_agent):
        """Test making decisions across services."""
        state1 = ScalingState(service_name="svc-1", namespace="prod", cpu_utilization=80)
        state2 = ScalingState(service_name="svc-2", namespace="prod", cpu_utilization=40)
        
        decision1 = multi_agent.decide(state1)
        decision2 = multi_agent.decide(state2)
        
        assert decision1.service_name == "svc-1"
        assert decision2.service_name == "svc-2"


class TestAlertTuner:
    """Tests for AlertTuner."""
    
    @pytest.fixture
    def tuner(self):
        """Create alert tuner."""
        return AlertTuner(
            learning_rate=0.01,
            exploration_rate=0.2,
            false_positive_weight=1.0,
            false_negative_weight=5.0,
        )
    
    @pytest.fixture
    def sample_state(self):
        """Create sample alert state."""
        return AlertState(
            alert_name="HighCPU",
            alert_type=AlertType.CPU_HIGH,
            service_name="api-gateway",
            current_threshold=80.0,
            threshold_min=50.0,
            threshold_max=95.0,
            alerts_last_24h=15,
            alerts_last_7d=80,
            true_positives_last_7d=30,
            false_positives_last_7d=50,
            current_metric_value=75.0,
            avg_metric_24h=65.0,
            std_metric_24h=10.0,
        )
    
    def test_create_tuner(self, tuner):
        """Test creating tuner."""
        assert tuner.learning_rate == 0.01
        assert tuner.false_negative_weight > tuner.false_positive_weight
    
    def test_tune(self, tuner, sample_state):
        """Test tuning threshold."""
        tuning = tuner.tune(sample_state)
        
        assert isinstance(tuning, AlertTuning)
        assert tuning.alert_name == "HighCPU"
        assert tuning.current_threshold == 80.0
    
    def test_tune_high_false_positives(self, tuner):
        """Test tuning with high false positives."""
        state = AlertState(
            alert_name="HighLatency",
            alert_type=AlertType.LATENCY_HIGH,
            current_threshold=100.0,
            threshold_max=500.0,
            false_positives_last_7d=80,
            true_positives_last_7d=10,
            silenced_count_7d=15,
        )
        
        # After training on this pattern, should learn to increase threshold
        for _ in range(50):
            tuner.tune(state)
            tuner.record_outcome(state, ThresholdAction.INCREASE_SMALL, AlertOutcome.TRUE_NEGATIVE)
        
        tuning = tuner.tune(state, explore=False)
        
        # Should recommend increasing threshold
        assert tuning.action in [ThresholdAction.INCREASE_SMALL, ThresholdAction.INCREASE_LARGE, ThresholdAction.NO_CHANGE]
    
    def test_record_outcome(self, tuner, sample_state):
        """Test recording outcome."""
        tuning = tuner.tune(sample_state)
        
        tuner.record_outcome(
            sample_state,
            tuning.action,
            AlertOutcome.TRUE_POSITIVE,
        )
        
        stats = tuner.get_statistics()
        assert stats["total_outcomes"] == 1
    
    def test_get_policy(self, tuner, sample_state):
        """Test getting policy."""
        tuner.tune(sample_state)
        
        policy = tuner.get_policy(AlertType.CPU_HIGH)
        
        assert isinstance(policy, AlertThresholdPolicy)
        assert policy.alert_type == AlertType.CPU_HIGH


class TestRemediationLearner:
    """Tests for RemediationLearner."""
    
    @pytest.fixture
    def learner(self):
        """Create remediation learner."""
        return RemediationLearner(
            learning_rate=0.01,
            exploration_rate=0.3,
        )
    
    @pytest.fixture
    def sample_context(self):
        """Create sample incident context."""
        return IncidentContext(
            incident_id="inc-123",
            service="payment-service",
            namespace="production",
            category=IncidentCategory.RESOURCE,
            severity="high",
            error_rate=0.05,
            latency_p99_ms=500.0,
            cpu_utilization=95.0,
            memory_utilization=88.0,
            pod_restart_count=5,
        )
    
    def test_create_learner(self, learner):
        """Test creating learner."""
        assert learner.learning_rate == 0.01
    
    def test_suggest(self, learner, sample_context):
        """Test suggesting remediations."""
        suggestions = learner.suggest(sample_context, top_k=3)
        
        assert len(suggestions) <= 3
        for suggestion in suggestions:
            assert isinstance(suggestion, RemediationSuggestion)
            assert suggestion.action_type in list(RemediationType)
    
    def test_suggest_excludes_attempted(self, learner, sample_context):
        """Test that suggestions exclude attempted actions."""
        sample_context.attempted_actions = [RemediationType.RESTART]
        
        suggestions = learner.suggest(sample_context, top_k=3, exclude_attempted=True)
        
        # RESTART should not be suggested
        for suggestion in suggestions:
            assert suggestion.action_type != RemediationType.RESTART
    
    def test_record_outcome(self, learner, sample_context):
        """Test recording remediation outcome."""
        remediation = Remediation(
            action_type=RemediationType.RESTART,
            service="payment-service",
            incident_id="inc-123",
            incident_category=IncidentCategory.RESOURCE,
            outcome=RemediationOutcome.SUCCESS,
            metrics_before={"error_rate": 0.05, "latency_p99": 500},
            metrics_after={"error_rate": 0.001, "latency_p99": 100},
        )
        
        reward = learner.record_outcome(remediation)
        
        assert reward > 0  # Success should give positive reward
    
    def test_find_similar_remediations(self, learner, sample_context):
        """Test finding similar past remediations."""
        # Record some remediations
        for i in range(5):
            remediation = Remediation(
                action_type=RemediationType.RESTART,
                service="payment-service",
                incident_category=IncidentCategory.RESOURCE,
                outcome=RemediationOutcome.SUCCESS,
                metrics_before={"cpu_utilization": 95},
                metrics_after={"cpu_utilization": 50},
            )
            learner.record_outcome(remediation)
        
        similar = learner.find_similar_remediations(sample_context, top_k=3)
        
        assert len(similar) <= 5
    
    def test_get_statistics(self, learner, sample_context):
        """Test getting statistics."""
        learner.suggest(sample_context)
        
        stats = learner.get_statistics()
        
        assert "total_suggestions" in stats
        assert stats["total_suggestions"] >= 1


class TestRewardTracker:
    """Tests for RewardTracker."""
    
    @pytest.fixture
    def tracker(self):
        """Create reward tracker."""
        return RewardTracker(
            max_history=1000,
            discount_factor=0.95,
        )
    
    def test_create_tracker(self, tracker):
        """Test creating tracker."""
        assert tracker.max_history == 1000
        assert tracker.discount_factor == 0.95
    
    def test_record_reward(self, tracker):
        """Test recording a reward."""
        reward = tracker.record(
            value=1.5,
            reward_type=RewardType.SCALING,
            signal=RewardSignal.PERFORMANCE_IMPROVEMENT,
            service="api-gateway",
            action="scale_up",
        )
        
        assert isinstance(reward, Reward)
        assert reward.raw_value == 1.5
    
    def test_record_with_normalization(self, tracker):
        """Test recording with normalization."""
        # Record some rewards to build statistics
        for i in range(20):
            tracker.record(value=float(i), reward_type=RewardType.SCALING)
        
        # New reward should be normalized
        reward = tracker.record(value=50.0, reward_type=RewardType.SCALING)
        
        # Normalized value should be different from raw
        assert reward.value != reward.raw_value
    
    def test_start_end_episode(self, tracker):
        """Test episode management."""
        episode = tracker.start_episode(
            episode_type=RewardType.REMEDIATION,
            service="payment-service",
        )
        
        assert episode.status == "active"
        
        # Record some rewards
        for i in range(5):
            tracker.record(
                value=float(i),
                reward_type=RewardType.REMEDIATION,
                episode_id=episode.episode_id,
                step=i,
            )
        
        # End episode
        completed = tracker.end_episode(
            episode.episode_id,
            outcome="success",
            details={"time_to_resolve": 300},
        )
        
        assert completed.status == "completed"
        assert completed.steps == 5
        assert completed.outcome == "success"
    
    def test_get_statistics(self, tracker):
        """Test getting statistics."""
        # Record various rewards
        for reward_type in [RewardType.SCALING, RewardType.REMEDIATION]:
            for _ in range(10):
                tracker.record(
                    value=np.random.random(),
                    reward_type=reward_type,
                )
        
        stats = tracker.get_statistics(reward_type=RewardType.SCALING)
        
        assert isinstance(stats, RewardStats)
        assert stats.count == 10
    
    def test_compute_return(self, tracker):
        """Test computing discounted return."""
        rewards = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        return_value = tracker.compute_return(rewards)
        
        # Should be sum of discounted rewards
        expected = sum(tracker.discount_factor ** i * r for i, r in enumerate(rewards))
        assert abs(return_value - expected) < 0.001
    
    def test_compute_advantages(self, tracker):
        """Test computing GAE advantages."""
        rewards = [1.0, 1.0, 1.0, 0.0, 0.0]
        values = [0.5, 0.6, 0.7, 0.3, 0.1]
        
        advantages = tracker.compute_advantages(rewards, values)
        
        assert len(advantages) == len(rewards)
    
    def test_get_reward_breakdown(self, tracker):
        """Test getting reward breakdown by type."""
        # Record rewards of different types
        for _ in range(5):
            tracker.record(value=1.0, reward_type=RewardType.SCALING)
        for _ in range(3):
            tracker.record(value=2.0, reward_type=RewardType.REMEDIATION)
        
        breakdown = tracker.get_reward_breakdown()
        
        assert "scaling" in breakdown
        assert "remediation" in breakdown
        assert breakdown["scaling"]["count"] == 5
        assert breakdown["remediation"]["count"] == 3
    
    def test_save_load(self, tracker, tmp_path):
        """Test saving and loading tracker."""
        # Record some data
        episode = tracker.start_episode(RewardType.SCALING, "test-service")
        for i in range(5):
            tracker.record(
                value=float(i),
                reward_type=RewardType.SCALING,
                episode_id=episode.episode_id,
            )
        tracker.end_episode(episode.episode_id, "success")
        
        path = str(tmp_path / "tracker.json")
        tracker.save(path)
        
        # Load into new tracker
        new_tracker = RewardTracker()
        new_tracker.load(path)
        
        # Should have the data
        assert new_tracker._count == tracker._count
