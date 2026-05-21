# AutoSRE Agent

LangGraph-based AI SRE Investigation Agent that orchestrates multi-agent incident investigation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Investigation Flow                          │
└─────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │    START    │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │ init_context │
                              └──────┬──────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │           (parallel)            │
           ┌────────▼────────┐             ┌─────────▼─────────┐
           │ memory_lookup   │             │    kg_context     │
           └────────┬────────┘             └─────────┬─────────┘
                    └────────────────┬────────────────┘
                                     │
                              ┌──────▼──────┐
                              │   planner   │
                              └──────┬──────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │       Send() fan-out            │
           ┌────────▼────────┐    ┌────────▼────────┐
           │  subagent(k8s)  │    │ subagent(metrics)│ ...
           └────────┬────────┘    └────────┬────────┘
                    └────────────────┬────────────────┘
                                     │ (fan-in)
                              ┌──────▼──────┐
                              │ synthesizer │◄──────────┐
                              └──────┬──────┘           │
                                     │                  │
                           ┌─────────▼─────────┐        │
                           │ sufficient?       │────no──┘
                           └─────────┬─────────┘ (loop)
                                     │ yes
                              ┌──────▼──────┐
                              │   writeup   │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │ memory_store │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │     END     │
                              └─────────────┘
```

## Nodes

### init_context
Entry point. Validates alert payload, generates investigation ID, loads team configuration.

### memory_lookup
Searches for similar past investigations using episodic memory. Provides context about what worked before.

### kg_context
Fetches service topology from Neo4j knowledge graph. Understands service dependencies and blast radius.

### planner
LLM-driven hypothesis generation. Analyzes alert + context and selects which subagents to dispatch.

### subagent
Executes domain-specific investigation via ReAct loop. Types include:
- `kubernetes`: K8s resource status, pod health, events
- `metrics`: PromQL queries, anomaly detection
- `log_analysis`: Log search, error pattern analysis
- `traces`: Distributed tracing, latency analysis

### synthesizer
Combines subagent findings. Decides to loop (more investigation) or conclude (enough evidence).

### writeup
Generates structured investigation report with:
- Markdown narrative
- JSON structured report (title, severity, root cause, action items)

### memory_store
Persists completed investigation for future memory lookups.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Copy environment config
cp .env.example .env
# Edit .env with your API keys

# Run server
uvicorn agent.server:app --reload

# Or use LangGraph Studio
langgraph dev
```

## API Endpoints

### POST /investigate
Start an investigation with SSE streaming.

```bash
curl -X POST http://localhost:8000/investigate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "{\"name\": \"HighErrorRate\", \"service\": \"api-gateway\"}"}'
```

### GET /health
Health check.

### POST /interrupt
Interrupt a running investigation.

### GET /threads
List active investigation threads.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LITELLM_BASE_URL` | LiteLLM proxy URL | `http://localhost:4000/v1` |
| `LITELLM_API_KEY` | API key for LiteLLM | - |
| `DEFAULT_MODEL` | Default LLM model | `claude-sonnet-4-20250514` |
| `MAX_ITERATIONS` | Max planner iterations | `3` |
| `SUBAGENT_MAX_REACT_LOOPS` | Max tool calls per subagent | `25` |
| `MEMORY_SERVICE_URL` | Memory service endpoint | - |
| `NEO4J_URI` | Neo4j connection URI | - |
| `CONFIG_SERVICE_URL` | Team config service | - |

### Team Configuration

Team-specific configuration (agents, prompts, tools) can be loaded from a config service:

```json
{
  "agents": {
    "planner": {
      "model": {"name": "claude-sonnet-4-20250514"},
      "prompt": {"system": "Custom planner prompt..."}
    },
    "investigation": {
      "sub_agents": {
        "kubernetes": true,
        "metrics": true,
        "log_analysis": true,
        "traces": false
      }
    }
  }
}
```

## SSE Event Types

The investigation endpoint streams Server-Sent Events:

| Event | Description |
|-------|-------------|
| `thought` | Agent reasoning/thinking text |
| `tool_start` | Tool execution starting |
| `tool_end` | Tool execution completed |
| `result` | Final investigation result |
| `error` | Error occurred |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy .
```

## License

MIT
