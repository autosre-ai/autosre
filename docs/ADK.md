# ADK Integration - Multi-Agent SRE Team

OpenSRE integrates Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) for sophisticated multi-agent incident investigation workflows.

## Overview

The ADK integration provides a multi-agent system where specialized AI agents collaborate to investigate incidents:

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Observer   │───▶│  Analyzer   │───▶│ Diagnostician │───▶│ Remediator  │
│             │    │             │    │              │    │             │
│ Gathers     │    │ Correlates  │    │ Determines   │    │ Suggests    │
│ metrics,    │    │ data, finds │    │ root cause   │    │ and executes│
│ logs, events│    │ patterns    │    │ with         │    │ fixes       │
│             │    │             │    │ confidence   │    │             │
└─────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
```

## Installation

ADK is installed automatically with OpenSRE's dependencies:

```bash
pip install google-adk
# or with opensre
pip install opensre[adk]
```

## Usage

### CLI

Use the `investigate-adk` command for multi-agent investigation:

```bash
# Basic investigation
opensre investigate-adk "high CPU on payment-service"

# In a specific namespace
opensre investigate-adk "pod crashlooping" -n production

# With auto-remediation (agents can execute safe fixes)
opensre investigate-adk "checkout errors" --auto-remediate

# Verbose output (shows full agent responses)
opensre investigate-adk "memory leak" -v
```

### Python API

```python
import asyncio
from opensre_core.adk_agents.sre_team import investigate_with_adk

result = asyncio.run(investigate_with_adk(
    issue="High latency on checkout-service",
    namespace="production",
    auto_remediate=False,  # Just recommend, don't execute
))

print(f"Root Cause: {result.root_cause}")
print(f"Confidence: {result.confidence:.0%}")
print(f"Actions: {result.recommended_actions}")
```

## Agent Roles

### 1. Observer Agent

**Purpose**: Gather all relevant observability data

**Tools Available**:
- `query_prometheus(query)` - Execute PromQL queries
- `get_firing_alerts()` - Get active alerts
- `get_service_metrics(service, namespace)` - Get CPU, memory, errors, latency
- `get_pods(namespace)` - List pod status
- `get_pod_logs(pod_name, namespace)` - Get container logs
- `get_events(namespace)` - Get Kubernetes events
- `describe_pod(pod_name, namespace)` - Detailed pod info
- `get_deployment(name, namespace)` - Deployment status

**Output**: Structured observations including alerts, pod status, events, metrics, and log summaries.

### 2. Analyzer Agent

**Purpose**: Correlate data and identify patterns

**Responsibilities**:
- Reconstruct timeline of events
- Find correlations between observations
- Identify anomalies
- Map affected services and dependencies
- Determine blast radius

**Output**: Timeline, correlations, anomalies, and affected components.

### 3. Diagnostician Agent

**Purpose**: Determine root cause with scientific rigor

**Responsibilities**:
- Generate hypotheses
- Evaluate evidence for/against each hypothesis
- Assign confidence scores
- Identify the most likely root cause
- Note contributing factors and uncertainties

**Output**: Root cause determination with confidence score and reasoning.

### 4. Remediator Agent

**Purpose**: Suggest and execute fixes

**Tools Available**:
- `restart_pod(pod_name, namespace)` - Delete a pod (controller recreates it)
- `scale_deployment(name, replicas, namespace)` - Scale replicas up/down
- `rollout_restart(deployment, namespace)` - Rolling restart without downtime

**Responsibilities**:
- Suggest immediate mitigation actions
- Propose permanent fixes
- Assess risk of each action
- Prioritize by impact and safety

**Output**: Prioritized action recommendations with risk levels.

## When to Use ADK vs Standard Investigation

| Use ADK Investigation | Use Standard Investigation |
|-----------------------|---------------------------|
| Complex, multi-service incidents | Simple, single-service issues |
| Need thorough root cause analysis | Quick triage |
| Want confidence scoring | Time-critical response |
| Learning from the investigation process | Automated remediation |
| Post-incident review material | Real-time alerting |

## Model Configuration

The ADK agents use LiteLLM for model flexibility. Configure via environment variables:

```bash
# Use Gemini (recommended for ADK)
export GEMINI_API_KEY=your-key
# or
export GOOGLE_API_KEY=your-key

# Use Claude
export ANTHROPIC_API_KEY=your-key

# Use OpenAI
export OPENAI_API_KEY=your-key

# Use local Ollama (default if no API keys)
# No configuration needed, uses ollama/llama3.2
```

## Customizing Agents

### Custom Agent Instructions

Create your own specialized agents:

```python
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from opensre_core.adk_agents.tools import create_kubernetes_tools

# Create a specialized agent
security_agent = Agent(
    name="SecurityAnalyzer",
    model=LiteLlm(model="gemini/gemini-2.0-flash"),
    instruction="""You are a Security-focused SRE agent. 
    Analyze incidents for potential security implications:
    - Check for unusual network patterns
    - Look for privilege escalation attempts
    - Identify potential data exfiltration
    ...""",
    tools=create_kubernetes_tools(),
)
```

### Custom Tool Creation

Add your own tools for ADK agents:

```python
from google.adk.tools import FunctionTool

def check_database_connections(database: str) -> str:
    """Check active connections to a database.
    
    Args:
        database: Database name (e.g., 'postgres-primary')
    
    Returns:
        Connection count and status
    """
    # Your implementation
    return f"Database {database}: 45 active connections (normal)"

# Add to agent
my_tools = [FunctionTool(check_database_connections)]
```

### Custom Team Composition

Build your own multi-agent team:

```python
from google.adk.agents import SequentialAgent, ParallelAgent
from opensre_core.adk_agents.sre_team import (
    create_observer_agent,
    create_diagnostician_agent,
)

# Parallel observation from multiple sources
parallel_observers = ParallelAgent(
    name="ParallelObservers",
    sub_agents=[
        create_observer_agent(),  # K8s + Prometheus
        my_database_observer,     # Your custom DB observer
        my_network_observer,      # Your custom network observer
    ],
)

# Sequential investigation
custom_team = SequentialAgent(
    name="CustomSRETeam",
    sub_agents=[
        parallel_observers,
        create_diagnostician_agent(),
        my_custom_remediator,
    ],
)
```

## Safety & Guardrails

The ADK integration includes several safety measures:

1. **Dry-run by default**: Actions are recommended but not executed unless `--auto-remediate` is specified

2. **Risk classification**: Actions are tagged as LOW, MEDIUM, or HIGH risk

3. **Tool restrictions**: Remediation tools require explicit opt-in

4. **Audit logging**: All agent actions are logged

5. **Rollback support**: Where possible, rollback commands are generated

## Output Format

The ADK investigation returns an `ADKInvestigationResult`:

```python
@dataclass
class ADKInvestigationResult:
    observations: str          # Raw observations from Observer
    analysis: str              # Correlation analysis from Analyzer
    diagnosis: str             # Full diagnosis from Diagnostician
    root_cause: str            # Extracted root cause statement
    confidence: float          # Confidence score (0.0-1.0)
    recommended_actions: list  # Prioritized action list
    remediation_output: str    # Full remediation recommendations
    agent_outputs: dict        # Raw outputs from each agent
```

## Troubleshooting

### "ADK import error"

Make sure google-adk is installed:
```bash
pip install google-adk
```

### "No model configured"

Set an API key for your preferred provider:
```bash
export GEMINI_API_KEY=your-key
# or run local Ollama
ollama serve
```

### Slow investigations

- ADK investigations are thorough and may take 30-60 seconds
- Use standard `investigate` command for faster triage
- Consider using faster models for non-critical investigations

### Agent not using tools

- Check that tools are properly registered
- Ensure the agent instruction mentions the tools
- Verify adapter connections (Prometheus, Kubernetes) are working

## Architecture

```
opensre_core/
├── adk_agents/
│   ├── __init__.py        # Module exports
│   ├── tools.py           # ADK tool wrappers
│   └── sre_team.py        # Multi-agent team definition
├── adapters/
│   ├── prometheus.py      # Underlying Prometheus adapter
│   └── kubernetes.py      # Underlying K8s adapter
└── cli.py                 # CLI with investigate-adk command
```

## Further Reading

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [OpenSRE Architecture](./ARCHITECTURE.md)
- [Tool Development Guide](./TOOLS.md)
