# AutoSRE V2 - Intelligent Remediation Engine

## Overview

The AutoSRE V2 Intelligent Remediation Engine provides automated incident remediation capabilities with safety mechanisms, human-in-the-loop approval workflows, and comprehensive rollback support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Remediation Engine                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Action    │  │   Safety    │  │     Approval           │  │
│  │  Registry   │  │   Checker   │  │     Workflow           │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│         └────────────────┼──────────────────────┘                │
│                          │                                       │
│                  ┌───────┴───────┐                               │
│                  │   Rollback    │                               │
│                  │   Manager     │                               │
│                  └───────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Kubernetes Operators                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    Pod      │  │   Scale     │  │     Resource           │  │
│  │  Restarter  │  │   Manager   │  │     Tuner              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │   Drain     │  │ Deployment  │                               │
│  │   Manager   │  │  Rollback   │                               │
│  └─────────────┘  └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Remediation Framework

#### RemediationEngine
The central orchestrator for remediation workflows.

```python
from autosre.remediation import RemediationEngine, EngineConfig

# Create engine with configuration
config = EngineConfig(
    enable_safety_checks=True,
    enable_approvals=True,
    enable_auto_rollback=True,
)
engine = RemediationEngine(config=config)

# Create and execute an action
action = engine.create_action(
    definition_name="restart_pod",
    target_type="pod",
    target_name="api-server-xyz",
    target_namespace="production",
    parameters={"grace_period": 30},
)

result = await engine.execute(action)
```

#### ActionRegistry
Manages action definitions and handlers.

```python
from autosre.remediation import ActionRegistry, ActionType, RiskLevel

registry = ActionRegistry()

@registry.register(
    name="restart_pod",
    display_name="Restart Pod",
    description="Gracefully restart a Kubernetes pod",
    action_type=ActionType.RESTART,
    risk_level=RiskLevel.LOW,
    target_types=["pod"],
)
async def restart_pod(namespace: str, pod_name: str, grace_period: int = 30):
    # Implementation
    return {"restarted": True}
```

#### SafetyChecker
Pre-flight safety validation.

```python
from autosre.remediation import SafetyChecker, SafetyPolicy

policy = SafetyPolicy(
    name="production",
    max_risk_level=RiskLevel.HIGH,
    protected_namespaces=["kube-system", "production"],
    require_approval_for_namespaces=["production"],
)

checker = SafetyChecker(policy=policy)
results = await checker.check_action(action)

if not checker.is_safe(results):
    violations = checker.get_violations(results)
    # Handle violations
```

#### RollbackManager
Handles state capture and rollback.

```python
from autosre.remediation import RollbackManager

manager = RollbackManager()

# Capture state before changes
snapshot = await manager.capture_state(
    action_id=action.id,
    resource_type="deployment",
    resource_name="api-server",
    state_data={"replicas": 3, "image": "api:v1.0"},
)

# Create checkpoint
checkpoint = await manager.create_checkpoint(
    action_id=action.id,
    name="pre-scale",
)

# Rollback if needed
result = await manager.execute_rollback(action)
```

#### ApprovalWorkflow
Human-in-the-loop approvals.

```python
from autosre.remediation import ApprovalWorkflow, ApprovalPolicy

workflow = ApprovalWorkflow()

request = await workflow.request_approval(
    action=action,
    reason="High-risk scaling operation",
    blast_radius=blast_radius,
)

# Wait for decision
status = await workflow.wait_for_decision(request.id, timeout_seconds=300)

# Or register callback
workflow.on_decision(request.id, async def callback(req, status, reason):
    if status == ApprovalStatus.APPROVED:
        await engine.execute(action)
)
```

### 2. Kubernetes Operators

#### PodRestarter
Smart pod restart with health verification.

```python
from autosre.operators import PodRestarter, RestartStrategy

restarter = PodRestarter(k8s_client)

# Restart single pod
result = await restarter.restart_pod(
    namespace="production",
    pod_name="api-server-xyz",
    strategy=RestartStrategy.GRACEFUL,
)

# Rolling restart of deployment
results = await restarter.restart_deployment(
    namespace="production",
    deployment_name="api-server",
)
```

#### ScaleManager
HPA override and manual scaling.

```python
from autosre.operators import ScaleManager, ScaleMode

scaler = ScaleManager(k8s_client)

# Scale deployment
result = await scaler.scale_deployment(
    namespace="production",
    deployment_name="api-server",
    replicas=10,
)

# Override HPA temporarily
result = await scaler.override_hpa(
    namespace="production",
    hpa_name="api-hpa",
    min_replicas=5,
    max_replicas=10,
    duration_minutes=30,
)
```

#### ResourceTuner
CPU/memory limit adjustments.

```python
from autosre.operators import ResourceTuner

tuner = ResourceTuner(k8s_client)

result = await tuner.update_resources(
    namespace="production",
    deployment_name="api-server",
    container_name="api",
    cpu_request="200m",
    cpu_limit="500m",
    memory_request="256Mi",
    memory_limit="512Mi",
)
```

#### DrainManager
Safe node draining.

```python
from autosre.operators import DrainManager, DrainConfig

config = DrainConfig(
    grace_period_seconds=30,
    ignore_daemonsets=True,
    delete_emptydir_data=False,
)

drain_manager = DrainManager(k8s_client, config)

result = await drain_manager.drain_node(
    node_name="worker-1",
)
```

#### DeploymentRollback
Automated rollback to last good version.

```python
from autosre.operators import DeploymentRollback

rollbacker = DeploymentRollback(k8s_client)

# Rollback to specific revision
result = await rollbacker.rollback(
    namespace="production",
    deployment_name="api-server",
    revision=5,
)

# Rollback to previous version
result = await rollbacker.rollback_to_previous(
    namespace="production",
    deployment_name="api-server",
)
```

### 3. Runbook Automation

#### RunbookParser
Parse runbooks from YAML/Markdown.

```python
from autosre.runbooks import RunbookParser

parser = RunbookParser()

# Parse YAML
runbook = parser.parse_yaml(yaml_content)

# Parse Markdown
runbook = parser.parse_markdown(markdown_content)

# Parse from file
runbook = await parser.parse_file("runbooks/restart-api.yaml")

# Validate
errors = parser.validate_runbook(runbook)
```

#### RunbookExecutor
Execute runbook steps.

```python
from autosre.runbooks import RunbookExecutor

executor = RunbookExecutor()

execution = await executor.execute(
    runbook=runbook,
    context={"namespace": "production", "service": "api-server"},
    dry_run=False,
)

print(execution.to_summary())
```

### 4. Chaos Engineering

#### ExperimentRunner
Run chaos experiments.

```python
from autosre.chaos import ExperimentRunner
from autosre.chaos.models import Experiment, Fault, FaultType, Target, TargetType

runner = ExperimentRunner(k8s_client)

experiment = Experiment(
    name="API Resilience Test",
    faults=[
        Fault(
            type=FaultType.POD_FAILURE,
            target=Target(
                type=TargetType.DEPLOYMENT,
                name="api-server",
                namespace="production",
            ),
            parameters={"count": 1},
        )
    ],
    steady_state=[
        SteadyStateHypothesis(
            name="API Health Check",
            probe_type="http",
            endpoint="http://api-server/health",
            expected_status=200,
        )
    ],
    duration_seconds=300,
)

result = await runner.run(experiment)
```

#### FaultInjector
Inject specific faults.

```python
from autosre.chaos.faults import FaultInjector

injector = FaultInjector(k8s_client)

# Inject network latency
result = await injector.inject(
    fault=Fault(
        type=FaultType.NETWORK_LATENCY,
        target=target,
        parameters={"latency_ms": 200},
    ),
    duration=60,
)
```

### 5. Change Management

#### ChangeTracker
Track all system changes.

```python
from autosre.changes import ChangeTracker
from autosre.changes.models import ChangeType

tracker = ChangeTracker()

change = await tracker.record_change(
    change_type=ChangeType.DEPLOYMENT,
    resource_type="deployment",
    resource_name="api-server",
    namespace="production",
    title="Deploy api-server v1.2.3",
    changed_by="ci-system",
)

# Link to incident
await tracker.link_incident(change.id, "INC-123")
```

#### CorrelationEngine
Link incidents to changes.

```python
from autosre.changes.correlation import CorrelationEngine

engine = CorrelationEngine(tracker)

correlations = await engine.correlate_incident({
    "id": "INC-123",
    "service": "api-server",
    "started_at": datetime.utcnow(),
})
```

## API Endpoints

### Remediation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/remediation/actions` | Create an action |
| POST | `/api/v1/remediation/execute` | Create and execute an action |
| GET | `/api/v1/remediation/registry/actions` | List registered actions |
| GET | `/api/v1/remediation/approvals` | List pending approvals |
| POST | `/api/v1/remediation/approvals/{id}/decide` | Approve/reject |

### Chaos API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chaos/experiments` | Create experiment |
| POST | `/api/v1/chaos/experiments/{id}/run` | Run experiment |
| POST | `/api/v1/chaos/faults/inject` | Inject fault |
| GET | `/api/v1/chaos/resilience/{service}` | Get resilience score |

### Runbooks API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/runbooks/` | Create runbook |
| POST | `/api/v1/runbooks/{id}/execute` | Execute runbook |
| GET | `/api/v1/runbooks/executions` | List executions |

### Changes API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/changes/` | Record a change |
| GET | `/api/v1/changes/` | List recent changes |
| POST | `/api/v1/changes/correlate` | Correlate to incident |

## Safety Features

1. **Pre-flight Checks**: Validate actions before execution
2. **Blast Radius Assessment**: Estimate impact before changes
3. **Protected Resources**: Block changes to critical namespaces
4. **Rate Limiting**: Prevent action floods
5. **Human Approval**: Require approval for high-risk actions
6. **Auto-rollback**: Automatically revert failed changes
7. **Dry-run Mode**: Simulate actions without effects
8. **Change Windows**: Enforce change freeze periods

## Configuration

```yaml
remediation:
  enable_safety_checks: true
  enable_approvals: true
  enable_auto_rollback: true
  
  safety_policy:
    max_risk_level: high
    protected_namespaces:
      - kube-system
      - production
    max_blast_radius_pods: 50
    
  approval_policy:
    require_approval_above_risk: high
    require_approval_namespaces:
      - production
    escalation_timeout_minutes: 15
```

## Best Practices

1. **Always use dry-run first** for new actions
2. **Define clear safety policies** for your environment
3. **Create runbooks** for common remediation tasks
4. **Track all changes** for correlation
5. **Run chaos experiments** regularly
6. **Monitor resilience scores** over time
