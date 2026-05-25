# Chaos Engineering Examples
# 
# This directory contains example chaos experiments for testing 
# system resilience using AutoSRE's chaos engineering module.

## Overview

AutoSRE's chaos engineering module is compatible with Chaos Mesh 
and LitmusChaos patterns, providing enterprise-grade chaos 
engineering capabilities.

## Examples

### Pod Chaos

| File | Description |
|------|-------------|
| pod_kill.yaml | Kill pods to test recovery and failover |

### Network Chaos

| File | Description |
|------|-------------|
| network_delay.yaml | Inject network latency to test timeouts |

### Stress Chaos

| File | Description |
|------|-------------|
| cpu_stress.yaml | CPU stress to test autoscaling and degradation |

## Running Experiments

### Using AutoSRE CLI

```bash
# Run an experiment
autosre chaos run examples/chaos/pod_kill.yaml

# Dry run (validate without executing)
autosre chaos run examples/chaos/pod_kill.yaml --dry-run

# Export to native Chaos Mesh format
autosre chaos export examples/chaos/pod_kill.yaml --format chaos-mesh

# Export to LitmusChaos format
autosre chaos export examples/chaos/pod_kill.yaml --format litmus
```

### Using Python SDK

```python
from autosre.chaos import (
    ChaosExperiment,
    ExperimentConfig,
    ExperimentType,
    TargetSelector,
    PodKillFault,
    SafetyChecker,
    SafetyPolicy,
    LocalExperimentRunner,
)

# Define target
target = TargetSelector(
    namespaces=["payments"],
    label_selectors={"app": "payment-service"},
    mode="one",
)

# Create experiment config
config = ExperimentConfig(
    experiment_type=ExperimentType.POD_CHAOS,
    target=target,
    fault_config=PodKillFault(grace_period=0).to_chaos_mesh_spec(),
)

# Create experiment
experiment = ChaosExperiment(
    name="pod-kill-test",
    description="Test pod recovery",
    hypothesis="System should recover within 30s",
    config=config,
)

# Validate with safety checker
checker = SafetyChecker(policy=SafetyPolicy())
is_valid, violations = await checker.validate(experiment)

if is_valid:
    # Run experiment
    runner = LocalExperimentRunner()
    result = await runner.run(experiment)
    print(f"Result: {result.state}")
```

## Safety Features

All experiments include:

- **Blast Radius Control**: Limits on affected pods/nodes/services
- **Time Restrictions**: Experiments only during business hours
- **Namespace Protection**: System namespaces blocked
- **Circuit Breaker**: Auto-stop after repeated failures
- **Rollback Triggers**: Automatic rollback on metric thresholds
- **Steady-State Validation**: Before/after checks

## Supported Fault Types

### Pod/Container Faults
- `pod_kill` - Kill pods
- `pod_failure` - Inject pod failure
- `container_kill` - Kill specific containers

### Network Faults
- `network_delay` - Add latency
- `network_partition` - Network isolation
- `network_loss` - Packet loss
- `network_duplicate` - Packet duplication
- `network_corrupt` - Packet corruption

### Stress Faults
- `cpu_stress` - CPU pressure
- `memory_stress` - Memory pressure
- `io_stress` - I/O pressure

### DNS Faults
- `dns_error` - DNS failures
- `dns_random` - Random DNS responses

### HTTP Faults
- `http_delay` - HTTP latency
- `http_abort` - HTTP failures
- `http_replace` - Replace responses
- `http_patch` - Modify responses

## Integration with Chaos Mesh

AutoSRE experiments can be exported to native Chaos Mesh CRDs:

```bash
autosre chaos export pod_kill.yaml --format chaos-mesh -o pod_kill_cm.yaml
kubectl apply -f pod_kill_cm.yaml
```

## Best Practices

1. **Start Small**: Begin with single pod, short duration
2. **Use Dry Run**: Validate before actual execution
3. **Define Steady State**: Clear success/failure criteria
4. **Set Rollback Triggers**: Auto-stop on adverse impact
5. **Monitor Closely**: Ensure observability during experiments
6. **Document Findings**: Update runbooks based on learnings
7. **Iterate**: Gradually increase blast radius as confidence grows
