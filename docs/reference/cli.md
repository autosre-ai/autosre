# CLI Reference

AutoSRE provides a command-line interface for running investigations and managing the agent.

## Installation

```bash
pip install autosre
```

## Commands

### autosre init

Initialize AutoSRE configuration.

```bash
autosre init [OPTIONS]
```

**Options:**

- `--config-dir PATH` - Directory for configuration files (default: `.autosre`)
- `--force` - Overwrite existing configuration

### autosre investigate

Start an investigation.

```bash
autosre investigate [OPTIONS] ALERT
```

**Arguments:**

- `ALERT` - Alert description or title

**Options:**

- `--severity LEVEL` - Alert severity (critical, high, medium, low)
- `--service NAME` - Service name
- `--namespace NS` - Kubernetes namespace
- `--output FORMAT` - Output format (text, json, markdown)
- `--verbose / --no-verbose` - Enable verbose output

**Examples:**

```bash
# Simple investigation
autosre investigate "High CPU on api-server"

# With service context
autosre investigate "Database connection errors" --service payment --severity high

# JSON output for scripting
autosre investigate "Memory leak detected" --output json
```

### autosre server

Start the AutoSRE API server.

```bash
autosre server [OPTIONS]
```

**Options:**

- `--host HOST` - Bind host (default: 0.0.0.0)
- `--port PORT` - Bind port (default: 8000)
- `--workers N` - Number of workers
- `--reload` - Enable auto-reload for development

### autosre config

Manage configuration.

```bash
autosre config [COMMAND]
```

**Subcommands:**

- `show` - Display current configuration
- `validate` - Validate configuration file
- `set KEY VALUE` - Set a configuration value

## Environment Variables

CLI commands respect these environment variables:

- `AUTOSRE_CONFIG` - Path to configuration file
- `AUTOSRE_LOG_LEVEL` - Logging level (debug, info, warning, error)
- `AUTOSRE_API_KEY` - API key for remote operations
