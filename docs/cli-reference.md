# CLI Reference

Complete command-line interface documentation for OpenSRE.

## Overview

The `opensre` CLI provides commands for managing skills, agents, and investigations.

```bash
opensre [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help and exit |
| `--config PATH` | Path to config file |
| `--debug` | Enable debug logging |
| `--quiet` | Suppress non-essential output |

---

## Core Commands

### `opensre status`

Show system status and connection health.

```bash
opensre status [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--verbose` | Show detailed status |

**Example:**

```bash
$ opensre status

OpenSRE v0.1.0

✓ Prometheus    http://prometheus:9090    Connected
✓ Kubernetes    ~/.kube/config            Connected (3 nodes)
✓ LLM           ollama/llama3.1:8b        Ready
✓ Slack         #incidents                Connected

Agents: 3 active | Investigations: 0 running
```

### `opensre start`

Start the OpenSRE daemon.

```bash
opensre start [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--foreground` | Run in foreground (don't daemonize) |
| `--host HOST` | API server host (default: 0.0.0.0) |
| `--port PORT` | API server port (default: 8000) |
| `--workers N` | Number of worker processes |
| `--reload` | Auto-reload on file changes (dev mode) |

**Example:**

```bash
# Start as daemon
opensre start

# Start in foreground with auto-reload
opensre start --foreground --reload

# Start on specific port
opensre start --port 9000
```

### `opensre stop`

Stop the OpenSRE daemon.

```bash
opensre stop [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--force` | Force immediate stop |

### `opensre investigate`

Manually trigger an investigation.

```bash
opensre investigate [OPTIONS] DESCRIPTION
```

**Options:**

| Option | Description |
|--------|-------------|
| `--namespace NS` | Target Kubernetes namespace |
| `--service SVC` | Target service name |
| `--json` | Output as JSON |
| `--watch` | Watch investigation progress |
| `--timeout SECONDS` | Investigation timeout |

**Example:**

```bash
# Simple investigation
opensre investigate "high error rate on checkout service"

# With context
opensre investigate "pods crashing" --namespace production --service payment

# Watch progress
opensre investigate "memory leak" --watch
```

---

## Skill Commands

### `opensre skill list`

List all available skills.

```bash
opensre skill list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--installed` | Show only installed skills |
| `--available` | Show only available (not installed) |
| `--json` | Output as JSON |

**Example:**

```bash
$ opensre skill list

Installed Skills:
┌─────────────┬─────────┬─────────────────────────────────────────┐
│ Name        │ Version │ Description                             │
├─────────────┼─────────┼─────────────────────────────────────────┤
│ prometheus  │ 1.0.0   │ Query metrics and manage alerts         │
│ kubernetes  │ 1.0.0   │ Kubernetes cluster management           │
│ slack       │ 1.0.0   │ Send notifications to Slack             │
└─────────────┴─────────┴─────────────────────────────────────────┘

Available Skills:
┌─────────────┬─────────┬─────────────────────────────────────────┐
│ aws         │ 1.0.0   │ AWS cloud operations                    │
│ datadog     │ 1.0.0   │ Datadog metrics and monitors            │
│ pagerduty   │ 1.0.0   │ PagerDuty incident management           │
└─────────────┴─────────┴─────────────────────────────────────────┘
```

### `opensre skill install`

Install a skill.

```bash
opensre skill install [OPTIONS] SKILL_NAME...
```

**Options:**

| Option | Description |
|--------|-------------|
| `--version VERSION` | Install specific version |
| `--upgrade` | Upgrade if already installed |

**Example:**

```bash
# Install single skill
opensre skill install aws

# Install multiple skills
opensre skill install aws gcp pagerduty

# Install specific version
opensre skill install prometheus --version 1.2.0
```

### `opensre skill uninstall`

Uninstall a skill.

```bash
opensre skill uninstall [OPTIONS] SKILL_NAME
```

**Options:**

| Option | Description |
|--------|-------------|
| `--force` | Skip confirmation |

### `opensre skill info`

Show detailed skill information.

```bash
opensre skill info SKILL_NAME
```

**Example:**

```bash
$ opensre skill info prometheus

Skill: prometheus
Version: 1.0.0
Description: Query Prometheus metrics and manage alerts

Actions:
┌───────────────┬────────────────────────────────────────────────┐
│ Action        │ Description                                    │
├───────────────┼────────────────────────────────────────────────┤
│ query         │ Execute instant PromQL query                   │
│ query_range   │ Execute range PromQL query                     │
│ alerts        │ Get active alerts                              │
│ silence       │ Create or update silence                       │
│ targets       │ List scrape targets                            │
└───────────────┴────────────────────────────────────────────────┘

Configuration:
  url: Prometheus server URL (required)
  auth: Authentication type (none, basic, bearer)

Dependencies:
  - prometheus-client>=0.19.0
```

### `opensre skill test`

Test skill connectivity and configuration.

```bash
opensre skill test SKILL_NAME
```

**Example:**

```bash
$ opensre skill test prometheus

Testing prometheus skill...
✓ Connection to http://prometheus:9090
✓ Query execution
✓ Alerts endpoint
✓ Targets endpoint

All tests passed!
```

---

## Agent Commands

### `opensre agent list`

List all agents.

```bash
opensre agent list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--running` | Show only running agents |
| `--json` | Output as JSON |

**Example:**

```bash
$ opensre agent list

┌──────────────────────┬─────────┬─────────────────────────────┬─────────┐
│ Name                 │ Status  │ Triggers                    │ Last Run│
├──────────────────────┼─────────┼─────────────────────────────┼─────────┤
│ incident-responder   │ running │ webhook: pagerduty          │ 5m ago  │
│ pod-crash-handler    │ running │ webhook: kubernetes         │ 1h ago  │
│ cert-checker         │ idle    │ schedule: 0 8 * * *         │ 23h ago │
└──────────────────────┴─────────┴─────────────────────────────┴─────────┘
```

### `opensre agent run`

Run an agent manually.

```bash
opensre agent run [OPTIONS] AGENT_NAME
```

**Options:**

| Option | Description |
|--------|-------------|
| `--params JSON` | Input parameters as JSON |
| `--dry-run` | Execute in dry-run mode |
| `--watch` | Watch execution progress |
| `--timeout SECONDS` | Execution timeout |

**Example:**

```bash
# Run agent with default params
opensre agent run incident-responder

# Run with parameters
opensre agent run pod-crash-handler --params '{"namespace": "production"}'

# Dry-run mode
opensre agent run deploy-validator --dry-run
```

### `opensre agent deploy`

Deploy an agent from a template.

```bash
opensre agent deploy [OPTIONS] AGENT_PATH
```

**Options:**

| Option | Description |
|--------|-------------|
| `--all` | Deploy all agents from catalog |
| `--set KEY=VALUE` | Override configuration |

**Example:**

```bash
# Deploy single agent
opensre agent deploy incident-responder/

# Deploy all agents
opensre agent deploy --all

# Deploy with config overrides
opensre agent deploy cert-checker/ --set pagerduty_on_critical=true
```

### `opensre agent config`

Configure an agent.

```bash
opensre agent config AGENT_NAME [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--set KEY=VALUE` | Set configuration value |
| `--unset KEY` | Remove configuration value |
| `--show` | Show current configuration |

**Example:**

```bash
# Show config
opensre agent config incident-responder --show

# Set config
opensre agent config incident-responder --set slack_channel="#sre-alerts"

# Multiple settings
opensre agent config deploy-validator \
  --set auto_rollback=false \
  --set error_threshold=2.0
```

### `opensre agent logs`

View agent execution logs.

```bash
opensre agent logs [OPTIONS] AGENT_NAME
```

**Options:**

| Option | Description |
|--------|-------------|
| `--follow` | Follow log output |
| `--tail N` | Show last N lines |
| `--since DURATION` | Show logs since duration (e.g., 1h, 30m) |

**Example:**

```bash
# View recent logs
opensre agent logs incident-responder

# Follow logs
opensre agent logs incident-responder --follow

# Last 50 lines from past hour
opensre agent logs incident-responder --tail 50 --since 1h
```

### `opensre agent status`

Show agent status.

```bash
opensre agent status AGENT_NAME
```

**Example:**

```bash
$ opensre agent status incident-responder

Agent: incident-responder
Status: running
Uptime: 4h 32m
Last Execution: 5m ago (success)

Triggers:
  - webhook: pagerduty (active)
  - prometheus_alert: severity=critical (active)

Recent Executions:
┌─────────────────────┬─────────┬──────────┬────────────┐
│ Timestamp           │ Trigger │ Duration │ Result     │
├─────────────────────┼─────────┼──────────┼────────────┤
│ 2024-03-15 14:32:05 │ webhook │ 45s      │ ✓ success  │
│ 2024-03-15 12:15:22 │ alert   │ 1m 12s   │ ✓ success  │
│ 2024-03-15 08:45:10 │ webhook │ 32s      │ ✗ timeout  │
└─────────────────────┴─────────┴──────────┴────────────┘
```

---

## Configuration Commands

### `opensre config show`

Show resolved configuration.

```bash
opensre config show [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--secrets` | Show secret values |
| `--json` | Output as JSON |

### `opensre config validate`

Validate configuration.

```bash
opensre config validate [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--strict` | Fail on warnings |

**Example:**

```bash
$ opensre config validate

Validating configuration...

✓ Core configuration
✓ LLM provider (ollama)
✓ Prometheus connection
✓ Kubernetes access
⚠ Slack not configured (notifications disabled)

Configuration valid with 1 warning.
```

### `opensre config init`

Initialize configuration interactively.

```bash
opensre config init [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing config |
| `--minimal` | Create minimal config |

---

## Testing Commands

### `opensre test`

Run connectivity tests.

```bash
opensre test [OPTIONS] [COMPONENT...]
```

**Components:** `all`, `prometheus`, `kubernetes`, `llm`, `slack`

**Example:**

```bash
# Test all components
opensre test all

# Test specific components
opensre test prometheus kubernetes

# Test LLM
opensre test llm
```

---

## Utility Commands

### `opensre init`

Initialize a new OpenSRE project.

```bash
opensre init [OPTIONS] [NAME]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--template TEMPLATE` | Project template |
| `--minimal` | Minimal project structure |

**Example:**

```bash
opensre init my-sre-project
cd my-sre-project
```

### `opensre version`

Show version information.

```bash
opensre version
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Connection error |
| 4 | Authentication error |
| 5 | Timeout |

---

## Environment Variables

All CLI options can be set via environment variables:

| Variable | CLI Option |
|----------|------------|
| `OPENSRE_CONFIG` | `--config` |
| `OPENSRE_DEBUG` | `--debug` |
| `OPENSRE_QUIET` | `--quiet` |

---

## Shell Completion

Enable shell completion:

```bash
# Bash
opensre --install-completion bash

# Zsh
opensre --install-completion zsh

# Fish
opensre --install-completion fish
```

---

## Next Steps

- **[Getting Started](getting-started.md)** — First investigation
- **[Skills Overview](skills/overview.md)** — Available skills
- **[Agent Catalog](../agents/CATALOG.md)** — Pre-built agents
