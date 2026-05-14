# AutoSRE ML Intelligence Layer

The ML Intelligence Layer provides machine learning capabilities for automated SRE operations.

## Components

### 1. Reinforcement Learning (`ml/rl/`)

#### ScalingAgent (`scaling_agent.py`)
Learns optimal scaling policies for services using Deep Q-Learning.

**Features:**
- Horizontal scaling decisions (add/remove replicas)
- Cooldown period handling
- Service-specific learning
- Multi-service management via `MultiServiceScalingAgent`

**Example:**
```python
from autosre.ml.rl import ScalingAgent, ScalingState

agent = ScalingAgent(service_name="api-gateway", learning_rate=0.001)

state = ScalingState(
    service_name="api-gateway",
    current_replicas=3,
    cpu_utilization=85.0,
    error_rate=0.02,
)

decision = agent.decide(state)
print(f"Recommendation: {decision.action} to {decision.target_replicas} replicas")
print(f"Reason: {decision.reason}")
```

#### AlertTuner (`alert_tuner.py`)
Learns optimal alert thresholds to minimize false positives while maintaining recall.

**Features:**
- Thompson sampling for exploration
- Per-alert-type policies
- Outcome tracking (TP, FP, TN, FN)
- Automatic threshold adjustment

**Example:**
```python
from autosre.ml.rl import AlertTuner, AlertState, AlertOutcome

tuner = AlertTuner(false_negative_weight=5.0)

state = AlertState(
    alert_name="HighCPU",
    alert_type=AlertType.CPU_HIGH,
    current_threshold=80.0,
    false_positives_last_7d=50,
)

tuning = tuner.tune(state)
print(f"Recommended threshold: {tuning.recommended_threshold}")

# After observing outcome:
tuner.record_outcome(state, tuning.action, AlertOutcome.TRUE_POSITIVE)
```

#### RemediationLearner (`remediation_learner.py`)
Learns which remediation actions work for different incident types.

**Features:**
- Contextual bandits with UCB exploration
- Service-specific and category-specific learning
- Similar incident matching
- Ranked suggestions with explanations

**Example:**
```python
from autosre.ml.rl import RemediationLearner, IncidentContext, IncidentCategory

learner = RemediationLearner()

context = IncidentContext(
    service="payment-service",
    category=IncidentCategory.RESOURCE,
    cpu_utilization=95.0,
    error_rate=0.05,
)

suggestions = learner.suggest(context, top_k=3)
for suggestion in suggestions:
    print(f"{suggestion.rank}. {suggestion.action_type}: {suggestion.reason}")
```

#### RewardTracker (`reward_tracker.py`)
Tracks and analyzes rewards across all RL components.

**Features:**
- Reward normalization
- Episode management
- GAE advantage computation
- Statistics and analytics

**Example:**
```python
from autosre.ml.rl import RewardTracker, RewardType

tracker = RewardTracker(discount_factor=0.95)

episode = tracker.start_episode(RewardType.SCALING, "api-gateway")

for step in range(10):
    tracker.record(
        value=reward_value,
        reward_type=RewardType.SCALING,
        episode_id=episode.episode_id,
        step=step,
    )

tracker.end_episode(episode.episode_id, "success")
```

### 2. Predictive Analytics (`ml/prediction/`)

- **CapacityPredictor**: Forecast resource needs
- **FailurePredictor**: Predict potential failures
- **TrafficPredictor**: Forecast traffic patterns
- **CostPredictor**: Predict infrastructure costs

### 3. Root Cause Analysis (`ml/rca/`)

- **CausalGraph**: Build causal dependency graphs
- **RCAEngine**: Automated root cause analysis
- **SymptomCorrelator**: Correlate symptoms to causes
- **HypothesisRanker**: Rank likely root causes
- **EvidenceCollector**: Gather supporting evidence

### 4. Anomaly Detection (`ml/anomaly/`)

- **TimeSeriesAnomalyDetector**: LSTM/Transformer based detection
- **LogAnomalyDetector**: Detect unusual log patterns
- **BehaviorAnomalyDetector**: User/service behavior anomalies
- **MultiVariateDetector**: Correlated anomalies
- **AnomalyExplainer**: Explain why something is anomalous

### 5. NLP for Operations (`ml/nlp/`)

- **IncidentClassifier**: Classify incident types
- **SeverityEstimator**: Estimate incident severity
- **SimilarityFinder**: Find similar past incidents
- **SummaryGenerator**: Generate incident summaries
- **CommandParser**: Parse natural language to actions

## Model Persistence

All RL components support saving and loading:

```python
# Save
agent.save("/models/scaling_agent.json")

# Load
new_agent = ScalingAgent()
new_agent.load("/models/scaling_agent.json")
```

## Integration

Import from the main ML module:

```python
from autosre.ml import (
    # RL
    ScalingAgent,
    AlertTuner,
    RemediationLearner,
    RewardTracker,
    # Prediction
    CapacityPredictor,
    FailurePredictor,
    # RCA
    RCAEngine,
    CausalGraph,
    # Anomaly
    TimeSeriesAnomalyDetector,
    # NLP
    IncidentClassifier,
)
```

## Testing

Run ML tests:
```bash
pytest tests/unit/ml/ -v
```

## Code Statistics

- **Total ML Layer**: ~19,000 lines
- **RL Module**: ~4,000 lines
- **ML Tests**: ~2,500 lines
