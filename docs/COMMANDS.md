# AutoSRE CLI Command Reference

Complete reference for all AutoSRE command-line interface commands.

## Installation

```bash
pip install autosre-ai
```

## Global Options

All commands support these global options:

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Show version and exit |
| `--install-completion` | Install shell completion |
| `--show-completion` | Show completion script |
| `--help` | Show help message |

---

## Quick Commands

### `autosre run`

Quick start an investigation (alias for `investigate run`).

```bash
autosre run ALERT [OPTIONS]
```

**Arguments:**
- `ALERT` (required): Alert or incident description

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--service`, `-s` | Service name | None |
| `--severity` | Severity level: low\|medium\|high\|critical | `high` |
| `--output`, `-o` | Output format: text\|json\|markdown\|html | `text` |
| `--demo`, `-d` | Run with simulated data (no infrastructure required) | False |
| `--watch`, `-w` | Continuously monitor (re-run every 60s, show diff) | False |

**Examples:**
```bash
autosre run "High error rate on checkout"
autosre run "API latency spike" --service api-gateway
autosre run "Database timeout errors" -s payment --severity critical
autosre run "Memory leak" --demo        # Run without infrastructure
autosre run "High error rate" --watch   # Continuous monitoring
```

---

### `autosre status`

Show comprehensive AutoSRE status and configuration.

```bash
autosre status [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--quiet`, `-q` | Minimal output, just show readiness |
| `--verbose`, `-v` | Show additional details |

**Examples:**
```bash
autosre status           # Full status display
autosre status -q        # Quick readiness check
autosre status -v        # Verbose with extra details
```

---

### `autosre completion`

Generate shell completion scripts for bash, zsh, or fish.

```bash
autosre completion [SHELL] [OPTIONS]
```

**Arguments:**
- `SHELL`: Shell type (bash, zsh, fish). Auto-detected if not specified.

**Options:**
| Option | Description |
|--------|-------------|
| `--install`, `-i` | Install completion to shell config |

**Examples:**
```bash
autosre completion bash              # Output bash completion script
autosre completion zsh --install     # Install zsh completion
autosre completion fish > ~/.config/fish/completions/autosre.fish
```

---

## Investigation Commands

### `autosre investigate run`

Start an AI-powered investigation using real infrastructure.

```bash
autosre investigate run ALERT [OPTIONS]
```

**Arguments:**
- `ALERT` (required): Alert or incident description

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--service`, `-s` | Service name | None |
| `--severity` | Severity: low\|medium\|high\|critical | `high` |
| `--output`, `--format`, `-o`, `-f` | Output format: text\|json\|markdown\|html | `text` |
| `--stream` / `--no-stream` | Stream output in real-time | `--stream` |
| `--save PATH` | Save report to file | None |
| `--demo`, `-d` | Run with simulated data (no infrastructure required) | False |
| `--watch`, `-w` | Continuously monitor (re-run every interval) | False |
| `--watch-interval` | Interval between watch runs (seconds) | `60` |

**Examples:**
```bash
# Basic investigation
autosre investigate run "High error rate on checkout"

# With service context
autosre investigate run "API latency spike" --service api-gateway

# Save HTML report
autosre investigate run "Redis connection errors" --format html --save report.html

# Demo mode (no infrastructure)
autosre investigate run "Memory leak detected" --demo

# Continuous monitoring
autosre investigate run "High error rate" --watch --watch-interval 120
```

---

### `autosre investigate history`

Show recent investigations from memory.

```bash
autosre investigate history [OPTIONS]
```

---

### `autosre investigate replay`

Replay a past investigation with visualization.

```bash
autosre investigate replay INVESTIGATION_ID [OPTIONS]
```

---

## Memory Commands

### `autosre memory list`

List past investigation episodes.

```bash
autosre memory list [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--limit`, `-n` | Number of episodes to show | `20` |
| `--service`, `-s` | Filter by service | None |
| `--type`, `-t` | Filter by alert type | None |
| `--resolved` | Show only resolved episodes | False |
| `--json` | Output as JSON | False |

**Examples:**
```bash
autosre memory list
autosre memory list --service checkout --limit 5
autosre memory list --type error_rate --resolved
```

---

### `autosre memory search`

Search episodes by text query.

```bash
autosre memory search QUERY [OPTIONS]
```

**Examples:**
```bash
autosre memory search "database timeout"
autosre memory search "connection pool" --limit 10
```

---

### `autosre memory stats`

Show memory statistics and insights.

```bash
autosre memory stats [OPTIONS]
```

---

### `autosre memory show`

Show detailed information about a specific episode.

```bash
autosre memory show EPISODE_ID [OPTIONS]
```

---

### `autosre memory clear`

Clear all memory data.

```bash
autosre memory clear [OPTIONS]
```

---

### `autosre memory export`

Export memory to a file.

```bash
autosre memory export OUTPUT_PATH [OPTIONS]
```

---

### `autosre memory import`

Import memory from a file.

```bash
autosre memory import INPUT_PATH [OPTIONS]
```

---

## Configuration Commands

### `autosre config show`

Show current configuration.

```bash
autosre config show [OPTIONS]
```

---

### `autosre config set`

Set a configuration value.

```bash
autosre config set KEY VALUE [OPTIONS]
```

**Examples:**
```bash
autosre config set llm.provider openai
autosre config set prometheus.url http://prometheus:9090
```

---

### `autosre config unset`

Remove a configuration value.

```bash
autosre config unset KEY [OPTIONS]
```

---

### `autosre config validate`

Validate configuration and check connections.

```bash
autosre config validate [OPTIONS]
```

---

### `autosre config init`

Initialize configuration with defaults.

```bash
autosre config init [OPTIONS]
```

---

### `autosre config edit`

Open configuration file in editor.

```bash
autosre config edit [OPTIONS]
```

---

### `autosre config env`

Show environment variables for configuration.

```bash
autosre config env [OPTIONS]
```

---

## Model Commands

### `autosre model list`

Show available models for each provider.

```bash
autosre model list [OPTIONS]
```

---

### `autosre model use`

Set the active AI model.

```bash
autosre model use PROVIDER MODEL [OPTIONS]
```

**Arguments:**
- `PROVIDER` (required): Provider name (ollama, openai, anthropic, azure)
- `MODEL` (required): Model name to use

**Examples:**
```bash
autosre model use ollama llama3.1:8b
autosre model use openai gpt-4o
autosre model use anthropic claude-3-5-sonnet-20241022
autosre model use azure gpt-4
```

---

### `autosre model test`

Test the current model connection.

```bash
autosre model test [OPTIONS]
```

---

### `autosre model info`

Show current model configuration.

```bash
autosre model info [OPTIONS]
```

---

## Server Commands

### `autosre serve start`

Start the webhook server for alert-driven investigations.

```bash
autosre serve start [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--host`, `-h` | Host to bind to | `0.0.0.0` |
| `--port`, `-p` | Port to listen on | `8080` |
| `--auto-investigate` / `--no-auto-investigate` | Auto-start investigations for alerts | `--auto-investigate` |
| `--notification-webhook` | Webhook URL for notifications (e.g., Slack) | None |
| `--workers`, `-w` | Number of worker processes | `1` |
| `--reload` | Enable auto-reload for development | False |
| `--log-level` | Log level | `info` |

**Alertmanager Configuration:**
```yaml
receivers:
  - name: autosre
    webhook_configs:
      - url: http://autosre-server:8080/webhook/alertmanager
        send_resolved: true
```

**Examples:**
```bash
autosre serve start
autosre serve start --port 9090
autosre serve start --no-auto-investigate
autosre serve start --notification-webhook https://hooks.slack.com/...
```

---

### `autosre serve status`

Check if the webhook server is running.

```bash
autosre serve status [OPTIONS]
```

---

### `autosre serve test-webhook`

Send a test webhook to the server.

```bash
autosre serve test-webhook [OPTIONS]
```

---

## Demo Commands

### `autosre demo run`

Run a demo investigation with simulated data.

```bash
autosre demo run [SCENARIO_ID] [OPTIONS]
```

> ⚠️ **WARNING:** Uses fake/mock data for demonstration only. Does NOT query real infrastructure.

**Arguments:**
- `SCENARIO_ID`: Scenario to run (e.g., redis-connection, memory-leak)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--scenario`, `-s` | Scenario ID (alternative to positional) | None |
| `--list`, `-l` | List available scenarios | False |
| `--random`, `-r` | Run a random scenario | False |
| `--yes`, `-y` | Skip confirmations (non-interactive) | False |
| `--interactive`, `-i` / `--batch` | Interactive mode with prompts | `--batch` |
| `--quiet`, `-q` | Minimal output | False |

**Examples:**
```bash
autosre demo run                           # Run default scenario
autosre demo run redis-connection          # Run specific scenario
autosre demo run --list                    # List available scenarios
autosre demo run --random                  # Run random scenario
autosre demo run -s memory-leak --quiet    # Quiet mode
```

---

### `autosre demo seed`

Seed episodic memory with simulated demo data.

```bash
autosre demo seed [OPTIONS]
```

---

### `autosre demo scenarios`

List all available demo scenarios.

```bash
autosre demo scenarios [OPTIONS]
```

---

### `autosre demo benchmark`

Benchmark investigation performance with simulated data.

```bash
autosre demo benchmark [OPTIONS]
```

---

### `autosre demo topology`

Show demo service topology.

```bash
autosre demo topology [OPTIONS]
```

---

## Chat Commands

### `autosre chat`

Interactive AI chat assistant for SRE questions.

```bash
autosre chat [MESSAGE] [OPTIONS]
```

**Arguments:**
- `MESSAGE`: Initial message (optional, starts interactive mode if omitted)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--context`, `-c` | Additional context file or incident ID | None |
| `--model`, `-m` | LLM model to use | From config |
| `--temperature`, `-t` | Response temperature (0.0-1.0) | `0.7` |
| `--mock` / `--live` | Use mock or live LLM responses | `--live` |

**Examples:**
```bash
autosre chat "What causes high p99 latency?"
autosre chat --context incident-123
autosre chat start  # Start interactive session
```

---

### `autosre chat start`

Start an interactive chat session with the SRE assistant.

```bash
autosre chat start [OPTIONS]
```

---

## Doctor Commands

### `autosre doctor`

Health check and diagnostics.

```bash
autosre doctor [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Show detailed output |
| `--json` | Output as JSON |

---

## Runbook Commands

### `autosre runbook list`

List all available runbooks.

```bash
autosre runbook list [OPTIONS]
```

---

### `autosre runbook show`

Show details of a specific runbook.

```bash
autosre runbook show RUNBOOK_ID [OPTIONS]
```

---

### `autosre runbook suggest`

AI suggests relevant runbooks based on alert or symptoms.

```bash
autosre runbook suggest DESCRIPTION [OPTIONS]
```

---

### `autosre runbook execute`

Execute a runbook step by step interactively.

```bash
autosre runbook execute RUNBOOK_ID [OPTIONS]
```

---

### `autosre runbook create`

Create a new runbook interactively.

```bash
autosre runbook create [OPTIONS]
```

---

### `autosre runbook search`

Search runbooks by keyword.

```bash
autosre runbook search QUERY [OPTIONS]
```

---

## Tutorial Commands

### `autosre tutorial`

Interactive onboarding tutorial.

```bash
autosre tutorial [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--interactive`, `-i` / `--no-interactive`, `-n` | Interactive mode with prompts | `--interactive` |
| `--section`, `-s` | Jump to section: welcome, commands, investigation, configuration, resources | None |
| `--quick`, `-q` | Quick mode - show all without pausing | False |

---

### `autosre tutorial sections`

List all available tutorial sections.

```bash
autosre tutorial sections [OPTIONS]
```

---

### `autosre tutorial reset`

Reset tutorial progress.

```bash
autosre tutorial reset [OPTIONS]
```

---

## Benchmark Commands

### `autosre benchmark`

Performance benchmarking.

```bash
autosre benchmark [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--iterations`, `-n` | Number of iterations per benchmark | `10` |
| `--warmup`, `-w` | Number of warmup iterations | `2` |
| `--json` | Output results as JSON | False |
| `--llm` / `--no-llm` | Include LLM latency benchmark | `--llm` |

---

### `autosre benchmark memory`

Benchmark memory system only.

```bash
autosre benchmark memory [OPTIONS]
```

---

### `autosre benchmark llm`

Benchmark LLM response latency.

```bash
autosre benchmark llm [OPTIONS]
```

---

## Plugin Commands

### `autosre plugin list`

Show installed plugins.

```bash
autosre plugin list [OPTIONS]
```

---

### `autosre plugin info`

Show detailed plugin information.

```bash
autosre plugin info PLUGIN_NAME [OPTIONS]
```

---

### `autosre plugin enable`

Enable a plugin.

```bash
autosre plugin enable PLUGIN_NAME [OPTIONS]
```

---

### `autosre plugin disable`

Disable a plugin.

```bash
autosre plugin disable PLUGIN_NAME [OPTIONS]
```

---

### `autosre plugin install`

Install a plugin from a source.

```bash
autosre plugin install SOURCE [OPTIONS]
```

---

### `autosre plugin uninstall`

Uninstall a plugin.

```bash
autosre plugin uninstall PLUGIN_NAME [OPTIONS]
```

---

### `autosre plugin create`

Create a new plugin from template.

```bash
autosre plugin create [OPTIONS]
```

---

## Team Commands

### `autosre team share`

Share an investigation with the team.

```bash
autosre team share INVESTIGATION_ID [OPTIONS]
```

---

### `autosre team comment`

Add a comment to an investigation.

```bash
autosre team comment INVESTIGATION_ID MESSAGE [OPTIONS]
```

---

### `autosre team assign`

Assign an investigation to a team member.

```bash
autosre team assign INVESTIGATION_ID ASSIGNEE [OPTIONS]
```

---

### `autosre team list`

Show team investigations.

```bash
autosre team list [OPTIONS]
```

---

### `autosre team comments`

Show comments on an investigation.

```bash
autosre team comments INVESTIGATION_ID [OPTIONS]
```

---

## Template Commands

### `autosre template list`

List all available investigation templates.

```bash
autosre template list [OPTIONS]
```

---

### `autosre template show`

Show details of a specific investigation template.

```bash
autosre template show TEMPLATE_ID [OPTIONS]
```

---

### `autosre template use`

Start an investigation using a template.

```bash
autosre template use TEMPLATE_ID [OPTIONS]
```

---

### `autosre template create`

Create a new investigation template interactively.

```bash
autosre template create [OPTIONS]
```

---

## Agent Commands

### `autosre agent run`

Run the agent in watch mode, continuously monitoring for alerts.

```bash
autosre agent run [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--config`, `-c` | Agent configuration file | None |
| `--dry-run` | Run without taking actions | False |

---

### `autosre agent analyze`

Analyze an alert and suggest remediation.

```bash
autosre agent analyze ALERT [OPTIONS]
```

---

## History Commands

### `autosre history list`

List recent incident investigations.

```bash
autosre history list [OPTIONS]
```

---

### `autosre history show`

View detailed information about a specific investigation.

```bash
autosre history show INVESTIGATION_ID [OPTIONS]
```

---

### `autosre history search`

Search past investigations by text query.

```bash
autosre history search QUERY [OPTIONS]
```

---

### `autosre history export`

Export a specific investigation to a file.

```bash
autosre history export INVESTIGATION_ID OUTPUT_PATH [OPTIONS]
```

---

### `autosre history stats`

Show statistics about past investigations.

```bash
autosre history stats [OPTIONS]
```

---

### `autosre history diff`

Compare two investigations side-by-side.

```bash
autosre history diff INVESTIGATION_ID1 INVESTIGATION_ID2 [OPTIONS]
```

---

### `autosre diff`

Quick alias for `history diff` — compare two investigations side-by-side.

```bash
autosre diff INVESTIGATION_ID1 INVESTIGATION_ID2 [OPTIONS]
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Configuration error |
| `3` | Connection error |

---

## See Also

- [Configuration Reference](CONFIGURATION.md)
- [Development Guide](DEVELOPMENT.md)
- [Main README](../README.md)
