# Getting Started with AutoSRE

This guide will get you from zero to running AutoSRE in 5 minutes.

## Prerequisites

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker** (optional) - For sandbox environments
- **kubectl** (optional) - For Kubernetes integration
- **kind** (optional) - For local test clusters

## Installation

### Quick Install

```bash
pip install autosre
```

### Full Installation (with all features)

```bash
pip install autosre[all]
```

This includes:
- `llm` - OpenAI, Anthropic, Ollama support
- `sandbox` - Docker/Kind cluster management

### Development Install

```bash
git clone https://github.com/opensre/autosre.git
cd autosre
pip install -e ".[all,dev]"
```

## First Steps

### 1. Initialize Your Project

```bash
cd your-project
autosre init
```

This creates:
```
your-project/
├── .autosre/           # AutoSRE data directory
│   ├── context.db      # Context store (SQLite)
│   ├── evals.db        # Evaluation results
│   └── scenarios/      # Custom evaluation scenarios
├── runbooks/           # Your runbook YAML files
│   └── high-cpu.yaml   # Sample runbook
└── .env.example        # Configuration template
```

### 2. Configure AutoSRE

Copy and edit the configuration:

```bash
cp .env.example .env
```

**Minimal configuration (local Ollama):**

```bash
# .env
OPENSRE_LLM_PROVIDER=ollama
OPENSRE_OLLAMA_HOST=http://localhost:11434
OPENSRE_OLLAMA_MODEL=llama3.1:8b
```

**Using OpenAI:**

```bash
OPENSRE_LLM_PROVIDER=openai
OPENSRE_OPENAI_API_KEY=sk-your-key-here
OPENSRE_OPENAI_MODEL=gpt-4o-mini
```

### 3. Check Status

```bash
autosre status
```

You should see:
```
📊 AutoSRE Status

Configuration
  ✓ .env file found
  ✓ .autosre directory exists

Context Store
  Services: 0
  Ownership Mappings: 0
  Changes (24h): 0
  ...

LLM Provider
  Provider: ollama
  Host: http://localhost:11434
  Model: llama3.1:8b
  Status: ✓ Connected, model available
```

### 4. (Optional) Create a Sandbox

If you have Docker and kind installed:

```bash
autosre sandbox start
```

This creates a local Kubernetes cluster with:
- Prometheus for metrics
- Grafana for dashboards
- Sample applications

### 5. Sync Context

Connect to your Kubernetes cluster:

```bash
# If using sandbox
export KUBECONFIG=~/.autosre/kubeconfig-autosre-sandbox

# Sync context
autosre context sync --kubernetes
```

View what was synced:

```bash
autosre context show --services
```

### 6. Run Your First Evaluation

```bash
# List available scenarios
autosre eval list

# Run a simple scenario
autosre eval run --scenario high_cpu --verbose
```

### 7. Start the Agent

```bash
# Watch mode (continuous monitoring)
autosre agent run

# Or analyze a specific alert
autosre agent analyze --alert-name HighCPUUsage
```

## Next Steps

- **[CLI Reference](cli-reference.md)** - All commands explained
- **[Configuration Guide](CONFIGURATION.md)** - All configuration options
- **[Architecture](ARCHITECTURE.md)** - How AutoSRE works
- **[Writing Runbooks](RUNBOOKS.md)** - Create your own runbooks
- **[Custom Scenarios](examples/custom-scenario.md)** - Create test scenarios

## Common Tasks

### Add a Service Manually

```bash
autosre context add service \
  --name my-api \
  --namespace production \
  --team platform
```

### Add a Runbook

Create `runbooks/my-runbook.yaml`:

```yaml
id: my-runbook
title: My Custom Runbook
description: Steps to resolve X issue

alerts:
  - MyCustomAlert

steps:
  - name: Check the thing
    command: kubectl get pods -n {{ namespace }}
    
  - name: Fix the thing
    command: kubectl rollout restart deployment/{{ service }}

automated: false
```

Then add it:

```bash
autosre context add runbook --file runbooks/my-runbook.yaml
```

### Test with Chaos

```bash
# Inject CPU stress
autosre sandbox inject cpu-hog --target my-service

# Watch the agent analyze
autosre agent run --once
```

### View Feedback Stats

```bash
autosre feedback report
```

## Troubleshooting

### "Ollama not reachable"

Make sure Ollama is running:
```bash
ollama serve
ollama pull llama3.1:8b
```

### "Failed to connect to Kubernetes"

Check your kubeconfig:
```bash
kubectl cluster-info
```

### "No scenarios found"

Run `autosre init` to create sample scenarios, or check that `~/.autosre/scenarios/` exists.

## Getting Help

- **GitHub Issues**: [Report a bug](https://github.com/opensre/autosre/issues)
- **Discussions**: [Ask questions](https://github.com/opensre/autosre/discussions)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)
