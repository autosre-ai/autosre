# Chaos Engineering Guide

This guide covers AutoSRE's chaos engineering capabilities for testing system resilience through controlled fault injection.

## Overview

AutoSRE's chaos engineering module provides:

- **Chaos Experiments**: Define and run fault injection tests
- **Fault Library**: Pre-built faults (pod kill, network delay, CPU stress, etc.)
- **GameDay Automation**: Structured chaos engineering events
- **Safety Controls**: Blast radius limits and automatic rollback
- **Reports & Analytics**: Resilience scoring and trend analysis

Compatible with [Chaos Mesh](https://chaos-mesh.org/) and [LitmusChaos](https://litmuschaos.io/) patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Chaos Engineering Module                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Experiments │  │   Faults    │  │  GameDays   │  │  Reports   │ │
│  │  Runner     │  │  Injector   │  │  Scheduler  │  │ Generator  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │                │        │
│  ┌──────┴────────────────┴────────────────┴────────────────┴──────┐ │
│  │                      Safety Checker                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐│ │
│  │  │ Blast Radius │  │   Circuit    │  │   Rollback Triggers    ││ │
│  │  │   Control    │  │   Breaker    │  │                        ││ │
│  │  └──────────────┘  └──────────────┘  └────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│              Chaos Mesh / LitmusChaos / Local Backend               │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Define a Chaos Experiment

```python
from autosre.chaos import (
    ChaosExperiment,
    ExperimentConfig,
    ExperimentType,
    TargetSelector,
    ExperimentSchedule,
)

# Define target
target = TargetSelector(
    namespaces=["default"],
    label_selectors={"app": "payment-service"},
    mode="one",  # Target one random pod
)

# Create experiment
experiment = ChaosExperiment(
    name="payment-pod-failure",
    description="Test payment service resilience to pod failures",
    hypothesis="Payment service should handle single pod failure without user-visible errors",
    config=ExperimentConfig(
        experiment_type=ExperimentType.POD_CHAOS,
        target=target,
        schedule=ExperimentSchedule(duration="30s"),
        fault_config={
            "action": "pod-kill",
            "gracePeriod": 0,
        },
    ),
)
```

### 2. Run the Experiment

```python
from autosre.chaos import LocalExperimentRunner, KubernetesExperimentRunner

# For local testing
runner = LocalExperimentRunner()

# For Kubernetes (using Chaos Mesh)
# runner = KubernetesExperimentRunner(backend="chaos-mesh")

# Run experiment
result = await runner.run(experiment)

print(f"Experiment completed: {result.state}")
print(f"Affected pods: {result.affected_pods}")
print(f"Steady state maintained: {result.steady_state_maintained}")
```

### 3. Add Safety Checks

```python
from autosre.chaos import SafetyChecker, default_safety_policy

# Create safety checker
checker = SafetyChecker(policy=default_safety_policy())

# Validate experiment before running
is_valid, violations = await checker.validate(experiment)

if not is_valid:
    for violation in violations:
        print(f"[{violation.severity}] {violation.rule_name}: {violation.message}")
else:
    result = await runner.run(experiment)
```

## Fault Types

### Pod Faults

```python
from autosre.chaos import PodKillFault, pod_kill

# Using the convenience function
fault = pod_kill(
    namespace="production",
    labels={"app": "api-gateway"},
    duration="30s",
    grace_period=0,
)

# Or using the class directly
fault = PodKillFault(
    name="api-gateway-pod-kill",
    target_namespace="production",
    target_labels={"app": "api-gateway"},
    duration="30s",
    grace_period=0,
)
```

### Network Faults

```python
from autosre.chaos import NetworkDelayFault, network_delay

# Add 200ms latency with 50ms jitter
fault = network_delay(
    namespace="production",
    labels={"app": "checkout"},
    latency="200ms",
    jitter="50ms",
    duration="5m",
    direction="to",
)

# Network partition
from autosre.chaos import NetworkPartitionFault

fault = NetworkPartitionFault(
    name="partition-database",
    target_namespace="production",
    target_labels={"app": "checkout"},
    external_targets=["10.0.0.0/8"],  # Block database access
    direction="both",
    duration="2m",
)

# Packet loss
from autosre.chaos import NetworkLossFault

fault = NetworkLossFault(
    name="packet-loss-test",
    target_namespace="production",
    target_labels={"app": "streaming"},
    loss="25",  # 25% packet loss
    duration="2m",
)
```

### Stress Faults

```python
from autosre.chaos import CPUStressFault, MemoryStressFault, cpu_stress, memory_stress

# CPU stress
fault = cpu_stress(
    namespace="production",
    labels={"app": "compute-service"},
    workers=2,
    load=80,  # 80% CPU load
    duration="5m",
)

# Memory stress
fault = memory_stress(
    namespace="production",
    labels={"app": "cache-service"},
    workers=1,
    size="512Mi",
    duration="5m",
)

# I/O stress
from autosre.chaos import IOStressFault

fault = IOStressFault(
    name="io-stress-test",
    target_namespace="production",
    target_labels={"app": "storage"},
    workers=4,
    duration="5m",
)
```

### DNS and HTTP Faults

```python
from autosre.chaos import DNSFault, HTTPFault

# DNS errors
fault = DNSFault(
    name="dns-failure",
    action="error",
    domain_patterns=["*.external-api.com"],
    duration="2m",
)

# HTTP delay
fault = HTTPFault(
    name="http-delay",
    action="delay",
    delay="500ms",
    port=8080,
    path="/api/*",
    duration="3m",
)

# HTTP abort (500 errors)
fault = HTTPFault(
    name="http-abort",
    action="abort",
    abort_code=500,
    port=8080,
    method="POST",
    duration="2m",
)
```

## Fault Injector

The `FaultInjector` manages fault injection across backends:

```python
from autosre.chaos import FaultInjector

# Create injector
injector = FaultInjector(
    backend="chaos-mesh",  # or "litmus", "local"
    namespace="chaos-testing",
    dry_run=False,
)

# Inject fault
result = await injector.inject(fault)
print(f"Injected: {result.success}, {result.message}")

# List active faults
active = await injector.list_active()

# Rollback specific fault
await injector.rollback(fault.id)

# Rollback all faults (emergency)
rolled_back = await injector.rollback_all()
```

## GameDay Automation

GameDays are structured chaos engineering events with multiple scenarios:

### Create a GameDay

```python
from autosre.chaos import (
    GameDay,
    GameDayScenario,
    Participant,
    ParticipantRole,
    create_service_resilience_gameday,
)

# Quick start with template
gameday = create_service_resilience_gameday(
    service_name="payment-service",
    namespace="production",
    labels={"app": "payment-service"},
)

# Or build custom GameDay
gameday = GameDay(
    name="Q4 Resilience GameDay",
    description="Quarterly resilience validation for checkout flow",
    objectives=[
        "Validate checkout flow resilience",
        "Test payment service failover",
        "Verify monitoring and alerting",
    ],
    scope="checkout-service, payment-service, inventory-service",
    out_of_scope="Database and third-party payment gateways",
)

# Add participants
gameday.add_participant(Participant(
    name="Jane Doe",
    email="jane@example.com",
    role=ParticipantRole.FACILITATOR,
    team="SRE",
))

gameday.add_participant(Participant(
    name="John Smith",
    email="john@example.com",
    role=ParticipantRole.RESPONDER,
    team="Platform",
))

# Add scenarios
scenario = GameDayScenario(
    name="Checkout Pod Failure",
    hypothesis="Checkout maintains 99.9% availability during pod failures",
    success_criteria=[
        "No user-visible errors",
        "Recovery within 30 seconds",
        "Alerts fire within 60 seconds",
    ],
    experiments=[pod_failure_experiment],
    estimated_duration_minutes=20,
)
gameday.add_scenario(scenario)
```

### Schedule and Run GameDay

```python
from autosre.chaos import GameDayScheduler, GameDayRunner
from datetime import datetime, timedelta

# Schedule
scheduler = GameDayScheduler()
scheduler.schedule(
    gameday,
    start_time=datetime.utcnow() + timedelta(days=7),
)

# Check upcoming GameDays
upcoming = scheduler.get_upcoming(within_hours=168)  # Next week

# Run GameDay
runner = GameDayRunner(
    experiment_runner=KubernetesExperimentRunner(),
    notify_callback=lambda channel, msg: send_slack(channel, msg),
)

# Verify readiness
is_ready, issues = gameday.is_ready()
if not is_ready:
    print(f"GameDay not ready: {issues}")
else:
    result = await runner.run(gameday)
    print(f"GameDay completed with score: {result.resilience_score:.1f}")

# Control during execution
await runner.pause()  # Pause if issues arise
await runner.resume()  # Resume after investigation
await runner.abort("Critical production issue")  # Emergency stop
```

## Safety Controls

### Blast Radius Configuration

```python
from autosre.chaos import BlastRadiusConfig, SafetyPolicy, SafetyLevel

config = BlastRadiusConfig(
    # Pod limits
    max_pods_affected=10,
    max_pods_percentage=50,
    
    # Node limits
    max_nodes_affected=3,
    max_nodes_percentage=30,
    
    # Namespace restrictions
    allowed_namespaces=["staging", "production-non-critical"],
    blocked_namespaces=["kube-system", "monitoring", "istio-system"],
    
    # Protected resources
    protected_labels={
        "tier": ["critical", "database"],
        "app.kubernetes.io/part-of": ["infrastructure"],
    },
    
    # Time restrictions
    allowed_hours=(9, 17),  # 9 AM to 5 PM
    blocked_days=[5, 6],    # Saturday, Sunday
    
    # Duration limits
    max_experiment_duration_minutes=60,
)

policy = SafetyPolicy(
    name="production",
    level=SafetyLevel.STRICT,
    blast_radius=config,
)
```

### Pre-built Safety Policies

```python
from autosre.chaos import (
    default_safety_policy,
    production_safety_policy,
    development_safety_policy,
)

# Standard policy for most environments
checker = SafetyChecker(policy=default_safety_policy())

# Strict policy for production
checker = SafetyChecker(policy=production_safety_policy())

# Permissive policy for development
checker = SafetyChecker(policy=development_safety_policy())
```

### Circuit Breaker

```python
from autosre.chaos import CircuitBreaker

circuit_breaker = CircuitBreaker(
    threshold=3,           # Open after 3 failures
    timeout_minutes=30,    # Reset after 30 minutes
)

# After each experiment
if result.is_successful():
    circuit_breaker.record_success()
else:
    if circuit_breaker.record_failure():
        print("Circuit breaker opened - pausing chaos experiments")

# Check status
status = circuit_breaker.get_status()
if status["is_open"]:
    print(f"Circuit open, resets in {status['remaining_minutes']:.1f} minutes")
```

### Rollback Triggers

```python
from autosre.chaos import RollbackTrigger, SafetyChecker

# Define automatic rollback triggers
trigger = RollbackTrigger(
    name="high-error-rate",
    description="Rollback if error rate exceeds 10%",
    metric_query="sum(rate(http_requests_total{status=~'5..'}[1m])) / sum(rate(http_requests_total[1m]))",
    threshold=0.10,
    comparison=">",
    duration_seconds=60,
    rollback_type="immediate",
)

checker = SafetyChecker(policy=production_safety_policy())
checker.add_rollback_trigger(trigger)

# During experiment, check triggers
triggered = await checker.check_rollback_triggers(current_metrics)
if triggered:
    print(f"Rollback triggered: {triggered.name}")
    await injector.rollback_all()
```

## Reports and Analytics

### Generate Chaos Report

```python
from autosre.chaos import (
    ReportGenerator,
    ExperimentMetrics,
    ReportFormat,
)
from datetime import datetime, timedelta

# Collect metrics from experiments
metrics = [
    ExperimentMetrics(
        experiment_id=exp.id,
        experiment_name=exp.name,
        start_time=result.start_time,
        end_time=result.end_time,
        duration_seconds=result.duration_seconds,
        availability_during=99.5,
        recovery_time_seconds=15.0,
        latency_p99_before=50.0,
        latency_p99_during=150.0,
        latency_p99_after=52.0,
    )
    for exp, result in experiment_results
]

# Generate report
generator = ReportGenerator()
report = generator.generate(
    experiments=experiments,
    metrics=metrics,
    period_start=datetime.utcnow() - timedelta(days=30),
    period_end=datetime.utcnow(),
    title="Monthly Chaos Engineering Report",
)

print(f"Resilience Score: {report.resilience_score:.1f} (Grade: {report.resilience_grade})")
print(f"Key Findings: {report.key_findings}")
```

### Export Reports

```python
# Export as Markdown
markdown = generator.export(report, format=ReportFormat.MARKDOWN)

# Export as HTML
html = generator.export(report, format=ReportFormat.HTML, output_path="report.html")

# Export for Slack
slack_msg = generator.export(report, format=ReportFormat.SLACK)

# Export as JSON
json_data = generator.export(report, format=ReportFormat.JSON)
```

### Resilience Scoring

```python
from autosre.chaos import ResilienceScore

score = ResilienceScore()
overall = score.calculate(metrics)

print(f"Overall Score: {overall:.1f}/100")
print(f"Availability Score: {score.availability_score:.1f}")
print(f"Recovery Score: {score.recovery_score:.1f}")
print(f"Degradation Score: {score.degradation_score:.1f}")
print(f"Trend: {score.trend}")
```

### Trend Analysis

```python
from autosre.chaos import TrendAnalysis

analysis = TrendAnalysis(
    start_date=datetime.utcnow() - timedelta(days=90),
    end_date=datetime.utcnow(),
)
analysis.analyze(all_metrics)

print(f"Total Experiments: {analysis.total_experiments}")
print(f"Availability Trend: {analysis.availability_trend}")
print(f"Recovery Time Trend: {analysis.recovery_time_trend}")
print(f"Improvements: {analysis.improvements}")
print(f"Regressions: {analysis.regressions}")
```

## Chaos Mesh Integration

AutoSRE experiments can be exported as Chaos Mesh CRDs:

```python
# Generate Chaos Mesh manifest
manifest = experiment.to_chaos_mesh_manifest()

# Apply using kubectl
import yaml
print(yaml.dump(manifest))

# Or apply programmatically
# kubectl_client.create(manifest)
```

Example output:

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: payment-pod-failure
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: payment-service
  duration: 30s
```

## LitmusChaos Integration

AutoSRE also supports LitmusChaos:

```python
# Generate LitmusChaos manifest
manifest = experiment.to_litmus_manifest()

print(yaml.dump(manifest))
```

Example output:

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: payment-pod-failure
  namespace: default
spec:
  engineState: active
  appinfo:
    appns: default
    applabel: app=payment-service
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "30"
            - name: FORCE
              value: "true"
```

## Best Practices

### 1. Start Small

```python
# Begin with non-critical services
target = TargetSelector(
    namespaces=["staging"],
    label_selectors={"tier": "non-critical"},
    mode="one",  # Single pod first
)
```

### 2. Define Clear Hypotheses

```python
experiment = ChaosExperiment(
    name="api-gateway-latency",
    hypothesis=(
        "API Gateway should handle 100ms network latency "
        "without exceeding P99 latency SLO of 500ms"
    ),
    # ...
)
```

### 3. Always Use Safety Checks

```python
checker = SafetyChecker(policy=production_safety_policy())
is_valid, violations = await checker.validate(experiment)

if not is_valid:
    # Never run without addressing violations
    raise ValueError(f"Safety violations: {violations}")
```

### 4. Monitor During Experiments

```python
scenario = GameDayScenario(
    name="Database Failover",
    dashboards=[
        "https://grafana.example.com/d/db-metrics",
        "https://grafana.example.com/d/app-health",
    ],
    alerts_to_watch=[
        "HighErrorRate",
        "DatabaseConnectionFailure",
    ],
    metrics_to_track=[
        "sum(rate(http_requests_total[1m]))",
        "histogram_quantile(0.99, http_request_duration_seconds_bucket)",
    ],
    # ...
)
```

### 5. Document and Share Findings

```python
# Generate and distribute reports
report = generator.generate(experiments, metrics, start, end)

# Send to Slack
slack_msg = generator.export(report, format=ReportFormat.SLACK)
send_to_slack("#sre-team", slack_msg)

# Archive HTML report
generator.export(report, format=ReportFormat.HTML, 
                 output_path=f"reports/chaos-{date}.html")
```

## CLI Commands (Coming Soon)

```bash
# Run a quick chaos experiment
autosre chaos run pod-kill --namespace=staging --selector="app=test-service"

# Schedule a GameDay
autosre chaos gameday schedule --config=gameday.yaml --date=2024-02-15

# Generate a report
autosre chaos report --period=30d --format=markdown --output=report.md

# Check safety status
autosre chaos safety status

# List active experiments
autosre chaos list --active
```

## Related Guides

- [Incident Investigation](./investigations.md) - Use chaos findings to improve incident response
- [SLO Management](./slo.md) - Validate SLOs with chaos experiments
- [On-Call](./oncall.md) - Train on-call engineers with GameDays
