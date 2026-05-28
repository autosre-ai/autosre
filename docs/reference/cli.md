# CLI Reference

AutoSRE provides a powerful command-line interface for incident investigation and SRE operations.

## Installation

```bash
pip install autosre-ai
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `autosre run` | Quick start an investigation |
| `autosre status` | Show system status |
| `autosre chat` | Interactive AI assistant |
| `autosre doctor` | Health check and diagnostics |
| `autosre investigate` | Investigation commands |
| `autosre memory` | Episodic memory management |
| `autosre history` | Browse past investigations |
| `autosre config` | Configuration management |
| `autosre model` | AI model settings |
| `autosre serve` | Webhook server |
| `autosre demo` | Demo and testing |
| `autosre runbook` | Runbook management |
| `autosre tutorial` | Interactive onboarding |
| `autosre template` | Investigation templates |
| `autosre plugin` | Plugin management |
| `autosre team` | Team collaboration |
| `autosre agent` | Autonomous monitoring |
| `autosre benchmark` | Performance testing |

## Core Commands

### autosre run

Quick start an investigation (alias for `investigate run`).

```bash
autosre run ALERT [OPTIONS]
```

**Arguments:**

- `ALERT` - Alert or incident description (required)

**Options:**

- `--service, -s TEXT` - Service name
- `--severity TEXT` - Severity level (default: high)
- `--output, -o TEXT` - Output format: text|json|markdown|html (default: text)
- `--demo, -d` - Run with simulated data (no infrastructure required)
- `--watch, -w` - Continuously monitor (re-run every 60s, show diff)

**Examples:**

```bash
# Simple investigation
autosre run "High CPU on api-server"

# With service context
autosre run "Database connection errors" --service payment --severity critical

# Demo mode (no infrastructure required)
autosre run "Memory leak detected" --demo

# Continuous monitoring
autosre run "High error rate" --watch
```

### autosre status

Show comprehensive AutoSRE status and configuration.

```bash
autosre status [OPTIONS]
```

**Options:**

- `--quiet, -q` - Minimal output, just show readiness
- `--verbose, -v` - Show additional details

### autosre doctor

Health check and diagnostics.

```bash
autosre doctor [OPTIONS]
```

**Options:**

- `--verbose, -v` - Show detailed output
- `--json` - Output as JSON

## Investigation Commands

### autosre investigate run

Start an AI-powered investigation.

```bash
autosre investigate run ALERT [OPTIONS]
```

**Options:**

- `--service, -s TEXT` - Service name
- `--severity TEXT` - Severity level (default: high)
- `--output, --format, -o, -f TEXT` - Output format: text|json|markdown|html
- `--stream / --no-stream` - Stream output in real-time (default: --stream)
- `--save PATH` - Save report to file
- `--demo, -d` - Run with simulated data
- `--watch, -w` - Continuously monitor
- `--watch-interval INT` - Interval between watch runs in seconds (default: 60)

### autosre investigate history

Show recent investigations from memory.

```bash
autosre investigate history [OPTIONS]
```

### autosre investigate replay

Replay a past investigation with visualization.

```bash
autosre investigate replay INVESTIGATION_ID [OPTIONS]
```

## Memory Commands

### autosre memory list

List past investigation episodes.

```bash
autosre memory list [OPTIONS]
```

**Options:**

- `--limit, -n INT` - Number of episodes to show (default: 20)
- `--service, -s TEXT` - Filter by service
- `--type, -t TEXT` - Filter by alert type
- `--resolved` - Show only resolved episodes
- `--json` - Output as JSON

### autosre memory search

Search episodes by text query.

```bash
autosre memory search QUERY [OPTIONS]
```

### autosre memory stats

Show memory statistics and insights.

```bash
autosre memory stats [OPTIONS]
```

### autosre memory show

Show detailed information about a specific episode.

```bash
autosre memory show EPISODE_ID [OPTIONS]
```

### autosre memory clear

Clear all memory data.

```bash
autosre memory clear [OPTIONS]
```

### autosre memory export / import

Export or import memory data.

```bash
autosre memory export OUTPUT_PATH
autosre memory import INPUT_PATH
```

## Configuration Commands

### autosre config init

Initialize configuration with defaults.

```bash
autosre config init [OPTIONS]
```

### autosre config show

Show current configuration.

```bash
autosre config show [OPTIONS]
```

### autosre config set

Set a configuration value.

```bash
autosre config set KEY VALUE
```

**Examples:**

```bash
autosre config set llm.provider openai
autosre config set prometheus.url http://prometheus:9090
```

### autosre config validate

Validate configuration and check connections.

```bash
autosre config validate [OPTIONS]
```

## Model Commands

### autosre model list

Show available models for each provider.

```bash
autosre model list [OPTIONS]
```

### autosre model use

Set the active AI model.

```bash
autosre model use PROVIDER MODEL
```

**Examples:**

```bash
autosre model use ollama llama3.1:8b
autosre model use openai gpt-4o
autosre model use anthropic claude-3-5-sonnet-20241022
```

### autosre model test

Test the current model connection.

```bash
autosre model test [OPTIONS]
```

### autosre model info

Show current model configuration.

```bash
autosre model info [OPTIONS]
```

## Server Commands

### autosre serve start

Start the webhook server for alert-driven investigations.

```bash
autosre serve start [OPTIONS]
```

**Options:**

- `--host, -h TEXT` - Host to bind to (default: 0.0.0.0)
- `--port, -p INT` - Port to listen on (default: 8080)
- `--auto-investigate / --no-auto-investigate` - Auto-start investigations (default: on)
- `--notification-webhook TEXT` - Webhook URL for notifications (e.g., Slack)
- `--workers, -w INT` - Number of worker processes (default: 1)
- `--reload` - Enable auto-reload for development
- `--log-level TEXT` - Log level (default: info)

### autosre serve status

Check if the webhook server is running.

```bash
autosre serve status [OPTIONS]
```

### autosre serve test-webhook

Send a test webhook to the server.

```bash
autosre serve test-webhook [OPTIONS]
```

## Environment Variables

CLI commands respect these environment variables:

| Variable | Description |
|----------|-------------|
| `OPENSRE_LLM_PROVIDER` | LLM provider (ollama, openai, anthropic, azure) |
| `OPENSRE_OPENAI_API_KEY` | OpenAI API key |
| `OPENSRE_ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENSRE_PROMETHEUS_URL` | Prometheus server URL |
| `OPENSRE_K8S_NAMESPACES` | Kubernetes namespaces to monitor |
| `OPENSRE_LOG_LEVEL` | Logging level (debug, info, warning, error) |

See [Environment Variables Reference](environment-variables.md) for the complete list.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Configuration error |
| `3` | Connection error |

## See Also

- [Full CLI Command Reference](../COMMANDS.md) - Complete documentation for all commands
- [Configuration Reference](configuration.md) - Configuration options
- [Environment Variables](environment-variables.md) - All environment variables
