# AutoSRE Examples

This directory contains examples, tutorials, and reference configurations for AutoSRE.

## Quick Start

```bash
# Run the simplest demo (mock mode, no external dependencies)
python examples/demo_simple.py --mock

# Run with your LLM configured
python examples/quickstart.py

# Test an investigation scenario
autosre investigate "high latency on api-gateway" --dry-run
```

## Directory Structure

```
examples/
├── README.md                    # This file
├── quickstart.py                # Minimal getting-started script
├── demo_simple.py               # Interactive demo with mock data
├── investigate.py               # Programmatic investigation example
├── topology.yaml                # Example service topology
│
├── configs/                     # Environment configurations
│   ├── local-ollama.env         # Local LLM with Ollama
│   ├── openai-cloud.env         # OpenAI API configuration
│   ├── azure-enterprise.env     # Azure OpenAI for enterprise
│   └── README.md
│
├── runbooks/                    # Automated runbook examples
│   ├── high-cpu.yaml            # CPU troubleshooting
│   ├── high-memory.yaml         # Memory/OOM resolution
│   ├── pod-crashloop.yaml       # CrashLoopBackOff handling
│   ├── high-latency.md          # Latency investigation guide
│   ├── redis-troubleshooting.md # Redis-specific runbook
│   └── README.md
│
├── scenarios/                   # Evaluation scenarios
│   ├── deployment-gone-wrong.yaml
│   └── README.md
│
├── kubernetes-remediation/      # K8s auto-remediation
│   ├── agent.yaml               # Agent config
│   ├── test-oom.yaml            # OOM test pod
│   └── README.md
│
├── prometheus-alerting/         # Prometheus/Alertmanager integration
│   ├── agent.yaml               # Agent config
│   └── README.md
│
├── multi-cloud-monitoring/      # AWS/GCP/Azure unified monitoring
│   ├── agent.yaml
│   └── README.md
│
├── demo-walkthrough/            # Demo recording resources
│   └── README.md
│
├── custom-skill/                # How to create custom skills
│   └── README.md
│
└── kubernetes manifests         # Test workloads
    ├── crashloop.yaml           # Pod that crash loops
    ├── oom-pod.yaml             # Pod that gets OOMKilled
    ├── memory-hog.yaml          # High memory consumer
    └── cpu-hog.yaml             # High CPU consumer
```

## Examples by Use Case

### Getting Started

| Example | Description | Requirements |
|---------|-------------|--------------|
| `quickstart.py` | Minimal investigation example | Python, LLM API key |
| `demo_simple.py` | Full interactive demo | Python only (mock mode) |
| `configs/*.env` | Configuration templates | Copy to `.env` |

### Kubernetes Operations

| Example | Description | Requirements |
|---------|-------------|--------------|
| `kubernetes-remediation/` | Auto-remediate K8s issues | K8s cluster, Prometheus |
| `runbooks/pod-crashloop.yaml` | CrashLoopBackOff runbook | K8s cluster |
| `runbooks/high-memory.yaml` | Memory troubleshooting | K8s cluster |
| `crashloop.yaml` | Test: crash looping pod | K8s cluster |
| `oom-pod.yaml` | Test: OOMKilled pod | K8s cluster |

### Observability Integration

| Example | Description | Requirements |
|---------|-------------|--------------|
| `prometheus-alerting/` | Prometheus + Alertmanager | Prometheus, Slack |
| `multi-cloud-monitoring/` | Multi-cloud health | AWS/GCP/Azure creds |
| `topology.yaml` | Service dependency map | None |

### Evaluation & Testing

| Example | Description | Requirements |
|---------|-------------|--------------|
| `scenarios/` | Synthetic incident scenarios | Python |
| `demo-walkthrough/` | Demo recording tools | asciinema |

### Extensibility

| Example | Description | Requirements |
|---------|-------------|--------------|
| `custom-skill/` | Create custom skills | Python |

## Running Examples

### 1. Demo Mode (No Dependencies)

Perfect for evaluation - no external services needed:

```bash
cd /path/to/autosre
python examples/demo_simple.py --mock
```

### 2. With Local LLM (Ollama)

```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull llama2

# Configure
cp examples/configs/local-ollama.env .env

# Run
python examples/quickstart.py
```

### 3. With Cloud LLM

```bash
# Configure (choose one)
cp examples/configs/openai-cloud.env .env
# or
cp examples/configs/azure-enterprise.env .env

# Edit with your API key
vim .env

# Run
python examples/quickstart.py
```

### 4. Full Kubernetes Setup

```bash
# Deploy test workload
kubectl apply -f examples/oom-pod.yaml

# Configure agent
cp examples/kubernetes-remediation/agent.yaml agents/

# Start AutoSRE
autosre start

# Watch for OOM events
kubectl get events -w
```

## Creating Test Incidents

Deploy test workloads to trigger alerts:

```bash
# Create a crash-looping pod
kubectl apply -f examples/crashloop.yaml

# Create OOM condition
kubectl apply -f examples/oom-pod.yaml

# Create CPU pressure
kubectl apply -f examples/cpu-hog.yaml

# Create memory pressure
kubectl apply -f examples/memory-hog.yaml
```

Clean up:

```bash
kubectl delete -f examples/crashloop.yaml
kubectl delete -f examples/oom-pod.yaml
kubectl delete -f examples/cpu-hog.yaml
kubectl delete -f examples/memory-hog.yaml
```

## Writing Your Own Scenarios

See `scenarios/README.md` for the full scenario format. Quick example:

```yaml
# examples/scenarios/my-scenario.yaml
name: my-custom-scenario
description: Test case for my specific issue
difficulty: medium

alert:
  name: HighErrorRate
  severity: critical
  service_name: my-service
  summary: "Error rate above threshold"

services:
  - name: my-service
    namespace: default
    status: degraded
    replicas: 3
    ready_replicas: 1

expected_root_cause: "Recent config change broke authentication"
expected_service: my-service
```

Run with:

```bash
autosre eval run --scenario my-custom-scenario
```

## Contributing Examples

We welcome new examples! Please:

1. Add a `README.md` explaining what the example demonstrates
2. Include all necessary configuration files
3. Test in both mock and real modes
4. Update this file with your example

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
