# AutoSRE CLI Reference

Complete reference for all AutoSRE command-line commands.

## Global Options

```bash
autosre [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `-q, --quiet` | Suppress non-essential output |
| `--debug` | Enable debug logging |
| `--help` | Show help message |

---

## Commands Overview

| Command | Description |
|---------|-------------|
| `init` | Initialize AutoSRE in current directory |
| `status` | Show overall status and health |
| `context` | Manage context store |
| `eval` | Run evaluation scenarios |
| `sandbox` | Manage sandbox environments |
| `agent` | Run the AI SRE agent |
| `feedback` | Manage learning and feedback |

---

## `autosre init`

Initialize AutoSRE in a directory.

```bash
autosre init [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-d, --dir` | `.` | Directory to initialize |

**Example:**

```bash
autosre init
autosre init --dir ./my-project
```

**Creates:**
- `.autosre/` - Data directory
- `runbooks/` - Runbook files
- `.env.example` - Configuration template

---

## `autosre status`

Show AutoSRE status and health.

```bash
autosre status
```

**Output includes:**
- Configuration file status
- Context store summary
- LLM provider connectivity
- Integration status (Kubernetes, Prometheus, etc.)

---

## `autosre context`

Manage the context store (services, ownership, changes, runbooks).

### `autosre context show`

Display context store contents.

```bash
autosre context show [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --services` | Show services |
| `-c, --changes` | Show recent changes |
| `-a, --alerts` | Show firing alerts |
| `-r, --runbooks` | Show runbooks |
| `--json` | Output as JSON |

**Examples:**

```bash
autosre context show                    # Summary
autosre context show --services         # List services
autosre context show -sc                # Services and changes
autosre context show --services --json  # JSON output
```

### `autosre context sync`

Sync context from external sources.

```bash
autosre context sync [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-k, --kubernetes` | Sync from Kubernetes |
| `-p, --prometheus` | Sync from Prometheus |
| `-g, --github` | Sync from GitHub |
| `-a, --all` | Sync from all sources |
| `--dry-run` | Preview without syncing |

**Examples:**

```bash
autosre context sync --all
autosre context sync --kubernetes --prometheus
autosre context sync --dry-run --all
```

### `autosre context add`

Add items to the context store.

#### `autosre context add service`

```bash
autosre context add service [OPTIONS]
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `-n, --name` | Yes | Service name |
| `--namespace` | No | Kubernetes namespace (default: `default`) |
| `--cluster` | No | Cluster name (default: `default`) |
| `-t, --team` | No | Owning team |
| `-d, --dependencies` | No | Dependencies (repeatable) |

**Example:**

```bash
autosre context add service \
  --name frontend \
  --namespace production \
  --team platform \
  -d api \
  -d redis
```

#### `autosre context add runbook`

```bash
autosre context add runbook --file <path>
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `-f, --file` | Yes | Runbook YAML file path |

### `autosre context list`

List items from the context store.

```bash
autosre context list <type> [OPTIONS]
```

**Types:** `services`, `changes`, `alerts`, `runbooks`, `incidents`

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-l, --limit` | 20 | Maximum items |
| `--json` | - | Output as JSON |

---

## `autosre eval`

Run evaluation scenarios and track results.

### `autosre eval list`

List available scenarios.

```bash
autosre eval list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `-v, --verbose` | Show additional details |

### `autosre eval run`

Run an evaluation scenario.

```bash
autosre eval run [OPTIONS]
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `-s, --scenario` | Yes | Scenario name |
| `-v, --verbose` | No | Detailed output |
| `-t, --timeout` | No | Timeout in seconds (default: 300) |
| `-m, --model` | No | Override LLM model |
| `--json` | No | Output as JSON |

**Examples:**

```bash
autosre eval run --scenario high_cpu
autosre eval run -s cascading_failure --verbose
autosre eval run -s memory_leak --model gpt-4
```

### `autosre eval create`

Create a new scenario.

```bash
autosre eval create [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-f, --file` | Output file path |
| `-t, --template` | Interactive wizard |
| `-n, --name` | Scenario name |
| `-d, --description` | Description |

**Examples:**

```bash
autosre eval create --template
autosre eval create -f scenarios/custom.yaml -n my-scenario
```

### `autosre eval report`

Show evaluation results.

```bash
autosre eval report [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-s, --scenario` | - | Filter by scenario |
| `-l, --limit` | 20 | Number of results |
| `-f, --format` | `table` | Output format (`table`, `json`, `summary`) |

---

## `autosre sandbox`

Manage sandbox Kubernetes environments.

### `autosre sandbox start`

Create and start a sandbox cluster.

```bash
autosre sandbox start [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --name` | `autosre-sandbox` | Cluster name |
| `--nodes` | 1 | Worker nodes (1-3) |
| `--k8s-version` | `v1.29.0` | Kubernetes version |
| `--skip-observability` | - | Skip Prometheus/Grafana |
| `--skip-sample-apps` | - | Skip sample apps |

**Examples:**

```bash
autosre sandbox start
autosre sandbox start --nodes 2 --name my-test
```

### `autosre sandbox stop`

Destroy a sandbox cluster.

```bash
autosre sandbox stop [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --name` | `autosre-sandbox` | Cluster name |
| `-f, --force` | - | Skip confirmation |

### `autosre sandbox status`

Show sandbox status.

```bash
autosre sandbox status [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --name` | `autosre-sandbox` | Cluster name |
| `--json` | - | Output as JSON |

### `autosre sandbox inject`

Inject chaos for testing.

```bash
autosre sandbox inject <chaos_type> [OPTIONS]
```

**Chaos Types:**

| Type | Description |
|------|-------------|
| `cpu-hog` | Consume CPU |
| `memory-hog` | Consume memory |
| `io-stress` | Stress disk I/O |
| `network-latency` | Add network delay |
| `pod-kill` | Kill a pod |
| `pod-failure` | Fail health checks |
| `disk-fill` | Fill disk space |

**Options:**

| Option | Description |
|--------|-------------|
| `-t, --target` | Target service/pod |
| `-n, --namespace` | Target namespace (default: `default`) |
| `-d, --duration` | Duration (default: `60s`) |
| `--dry-run` | Preview only |

**Examples:**

```bash
autosre sandbox inject cpu-hog
autosre sandbox inject pod-kill --target frontend
autosre sandbox inject network-latency --duration 120s
```

### `autosre sandbox list`

List all sandbox clusters.

```bash
autosre sandbox list [OPTIONS]
```

---

## `autosre agent`

Run and manage the AI SRE agent.

### `autosre agent run`

Start the agent in watch mode.

```bash
autosre agent run [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-i, --interval` | 30 | Poll interval (seconds) |
| `--once` | - | Run once and exit |
| `--dry-run` | - | Don't execute remediation |
| `-m, --model` | - | Override LLM model |
| `-v, --verbose` | - | Verbose output |

**Examples:**

```bash
autosre agent run
autosre agent run --interval 60 --dry-run
autosre agent run --once
```

### `autosre agent analyze`

Analyze an alert.

```bash
autosre agent analyze [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-a, --alert` | Alert JSON file path |
| `--alert-name` | Alert name from context store |
| `-s, --service` | Service to analyze |
| `-v, --verbose` | Detailed output |
| `--json` | Output as JSON |
| `-m, --model` | Override LLM model |

**Examples:**

```bash
autosre agent analyze --alert alert.json
autosre agent analyze --alert-name HighCPUUsage
autosre agent analyze --service frontend --verbose
```

### `autosre agent config`

View agent configuration.

```bash
autosre agent config [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--set KEY VALUE` | Set config value (repeatable) |

### `autosre agent history`

Show analysis history.

```bash
autosre agent history [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-l, --limit` | 20 | Number of entries |
| `-s, --service` | - | Filter by service |
| `--json` | - | Output as JSON |

---

## `autosre feedback`

Manage learning and feedback.

### `autosre feedback submit`

Submit feedback on an analysis.

```bash
autosre feedback submit [OPTIONS]
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `-i, --incident` | Yes | Incident ID |
| `--correct` | - | Mark as correct |
| `--incorrect` | - | Mark as incorrect |
| `--partial` | - | Mark as partially correct |
| `--actual-cause` | - | Actual root cause |
| `-n, --notes` | - | Additional notes |

**Examples:**

```bash
autosre feedback submit -i INC-123 --correct
autosre feedback submit -i INC-123 --incorrect --actual-cause "DNS timeout"
autosre feedback submit -i INC-456 --partial --notes "Right service, wrong cause"
```

### `autosre feedback report`

Show feedback statistics.

```bash
autosre feedback report [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-d, --days` | 30 | Days to include |
| `--json` | - | Output as JSON |

### `autosre feedback list`

List feedback entries.

```bash
autosre feedback list [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-l, --limit` | 20 | Number of entries |
| `-r, --rating` | - | Filter by rating |
| `--json` | - | Output as JSON |

### `autosre feedback export`

Export feedback data.

```bash
autosre feedback export [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `feedback-export.json` | Output file |
| `-f, --format` | `json` | Format (`json`, `csv`) |

---

## Environment Variables

All configuration can be set via environment variables:

| Variable | Description |
|----------|-------------|
| `OPENSRE_LLM_PROVIDER` | LLM provider (ollama, openai, anthropic, azure) |
| `OPENSRE_OLLAMA_HOST` | Ollama server URL |
| `OPENSRE_OLLAMA_MODEL` | Ollama model name |
| `OPENSRE_OPENAI_API_KEY` | OpenAI API key |
| `OPENSRE_OPENAI_MODEL` | OpenAI model name |
| `OPENSRE_ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL |
| `OPENSRE_K8S_NAMESPACES` | Kubernetes namespaces (comma-separated) |
| `OPENSRE_REQUIRE_APPROVAL` | Require approval for actions |
| `OPENSRE_CONFIDENCE_THRESHOLD` | Minimum confidence for actions |

See [Configuration Guide](CONFIGURATION.md) for complete list.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Command-line usage error |
| 130 | Interrupted (Ctrl+C) |
