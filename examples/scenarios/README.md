# Example Scenarios

This directory contains custom evaluation scenarios.

## What is a Scenario?

A scenario defines a synthetic incident for testing AutoSRE's diagnostic capabilities:

1. **Alert** - The triggering alert
2. **Services** - State of services in the scenario
3. **Changes** - Recent changes to correlate
4. **Expected outcomes** - What the agent should identify

## Using Scenarios

```bash
# List available scenarios
autosre eval list

# Run a scenario
autosre eval run --scenario my-custom-scenario

# Create a new scenario interactively
autosre eval create --template
```

## Scenario Format

```yaml
name: my-scenario
description: What this scenario tests
difficulty: easy|medium|hard

alert:
  name: AlertName
  severity: critical|high|medium|low
  service_name: affected-service
  summary: Alert summary text

services:
  - name: service-name
    namespace: default
    status: healthy|degraded|down
    replicas: 3
    ready_replicas: 2

changes:
  - type: deployment|config_change|scale
    service_name: service-name
    description: What changed
    author: who@example.com
    timestamp: "2024-01-15T10:00:00Z"

expected_root_cause: "The actual root cause"
expected_service: affected-service
expected_runbook: runbook-id
expected_action: "What remediation should be suggested"

max_time_seconds: 180
```

## Available Examples

| File | Difficulty | Description |
|------|------------|-------------|
| `deployment-gone-wrong.yaml` | Medium | Failed deployment with rollback |
| `cascading-outage.yaml` | Hard | Multi-service cascading failure |
| `config-drift.yaml` | Easy | Configuration mismatch |
