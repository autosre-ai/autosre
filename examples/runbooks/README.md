# Example Runbooks

This directory contains example runbooks for common incident types.

## What is a Runbook?

A runbook is a YAML file that describes:
1. **What alerts it handles** - Alert names it applies to
2. **What services it covers** - Services this runbook is for
3. **Steps to follow** - Commands and checks to perform
4. **Whether it's automated** - Can the agent run it automatically?

## Using Runbooks

```bash
# Add a runbook to the context store
autosre context add runbook --file examples/runbooks/high-cpu.yaml

# View loaded runbooks
autosre context show --runbooks
```

## Creating Your Own

Copy one of these examples and modify:

```yaml
id: my-runbook
title: My Custom Runbook
description: Steps to resolve X issue

alerts:
  - MyAlertName

services:
  - my-service

steps:
  - name: First step
    command: kubectl get pods -n {{ namespace }}
    
  - name: Second step
    command: kubectl logs {{ pod }} --tail=100

automated: false
requires_approval: true
```

## Available Examples

| File | Description |
|------|-------------|
| `high-cpu.yaml` | CPU troubleshooting |
| `high-memory.yaml` | Memory/OOM troubleshooting |
| `pod-crashloop.yaml` | CrashLoopBackOff resolution |
| `deployment-failed.yaml` | Failed deployment rollback |
| `database-connection.yaml` | DB connection issues |
