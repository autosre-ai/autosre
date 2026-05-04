# AutoSRE v2 Build Log

## Build Started: 2025-05-03

## Iteration 1: Project Structure ✅
- Created `autosre/` package directory
- Set up target directory structure
- Created basic `__init__.py` with version

## Iteration 2: State Models ✅
- OpenSRE file studied: `sre-agent/state.py`
- Copied and adapted Pydantic models
- Created: `autosre/agents/state.py`
- Models: InvestigationState, Hypothesis, Evidence, InvestigationPlan, etc.

## Iteration 3: Configuration ✅
- OpenSRE file studied: `sre-agent/config.py`
- Created Pydantic Settings with nested config
- Created: `autosre/config.py`
- Supports env vars, YAML, and defaults

## Iteration 4: LLM Client ✅
- Created unified LLM interface for Anthropic/OpenAI
- No LangChain dependency - direct API calls
- Created: `autosre/llm/client.py`
- Features: structured output, automatic fallback

## Iteration 5: Episodic Memory ✅
- OpenSRE file studied: `sre-agent/memory/integration.py`
- Replaced PostgreSQL with SQLite
- Created: `autosre/memory/episodic.py`
- Features: FTS5 full-text search, tiered search priority

## Iteration 6: Strategy Generator ✅
- OpenSRE file studied: `sre-agent/memory/strategy_generator.py`
- Copied key prompts for strategy generation
- Created: `autosre/memory/strategy.py`
- Features: async generation, memory enhancement

## Iteration 7: Memory Tests ✅
- Created comprehensive tests for episodic memory
- Created: `tests/test_episodic_memory.py`
- Tests: store/retrieve, search, FTS, stats

## Iteration 8: Service Topology ✅
- Created YAML-based topology loader
- Simpler than Neo4j knowledge graph
- Created: `autosre/topology/service.py`
- Features: blast radius, dependencies, tier SLAs

## Iteration 9: Planner Agent ✅
- OpenSRE file studied: `sre-agent/nodes/planner.py`
- Preserved key prompts
- Created: `autosre/agents/planner.py`
- Features: hypothesis generation, agent selection

## Iteration 10: Synthesizer Agent ✅
- OpenSRE file studied: `sre-agent/nodes/synthesizer.py`
- Preserved key prompts
- Created: `autosre/agents/synthesizer.py`
- Features: evidence synthesis, loop/conclude decision

## Iteration 11: Writeup Agent ✅
- OpenSRE file studied: `sre-agent/nodes/writeup.py`
- Full report generation with normalization
- Created: `autosre/agents/writeup.py`
- Features: markdown + JSON output, enrichment from narrative

## Iteration 12: Subagent Base ✅
- OpenSRE file studied: `sre-agent/nodes/subagent_executor.py`
- Created abstract base class
- Created: `autosre/agents/subagents/base.py`
- Features: ReAct loop structure, evidence collection

## Iteration 13: Kubernetes Subagent ✅
- Created Kubernetes investigation subagent
- Created: `autosre/agents/subagents/kubernetes.py`
- Capabilities: pod logs, describe, events

## Iteration 14: Metrics Subagent ✅
- Created metrics/observability subagent
- Created: `autosre/agents/subagents/metrics.py`
- Capabilities: PromQL queries, error rates, latency

## Iteration 15: Logs Subagent ✅
- Created log analysis subagent
- Created: `autosre/agents/subagents/logs.py`
- Capabilities: log search, error patterns, trace correlation

## Iteration 16: Skills Registry ✅
- Created pluggable skill system
- Created: `autosre/skills/registry.py`
- Features: YAML frontmatter parsing, catalog generation

## Iteration 17: Orchestrator ✅
- OpenSRE file studied: `sre-agent/graph.py`
- Replaced LangGraph with plain async Python
- Created: `autosre/orchestrator.py`
- Flow: init → memory → topology → planner → subagents → synthesizer → writeup

## Iteration 18: Example Script ✅
- Created demo/investigation script
- Created: `examples/investigate.py`
- Features: interactive mode, example alerts

## Iteration 19: Agent Tests ✅
- Created tests for agents and orchestrator
- Created: `tests/test_agents.py`, `tests/test_orchestrator.py`
- Tests: state management, planner fallback, integration

## Iteration 20: Documentation ✅
- Created comprehensive README
- Created: `README-v2.md`
- Includes: quick start, architecture, comparison to OpenSRE

---

## Files Created/Modified

### New Files
- `autosre/__init__.py` - Package init with exports
- `autosre/config.py` - Pydantic settings
- `autosre/orchestrator.py` - Main flow controller
- `autosre/llm/__init__.py`
- `autosre/llm/client.py` - Anthropic/OpenAI client
- `autosre/memory/__init__.py`
- `autosre/memory/episodic.py` - SQLite memory
- `autosre/memory/strategy.py` - Strategy generation
- `autosre/topology/__init__.py`
- `autosre/topology/service.py` - YAML topology
- `autosre/agents/__init__.py`
- `autosre/agents/state.py` - State models
- `autosre/agents/planner.py` - Planner agent
- `autosre/agents/synthesizer.py` - Synthesizer agent
- `autosre/agents/writeup.py` - Writeup agent
- `autosre/agents/subagents/__init__.py`
- `autosre/agents/subagents/base.py` - Base subagent
- `autosre/agents/subagents/kubernetes.py`
- `autosre/agents/subagents/metrics.py`
- `autosre/agents/subagents/logs.py`
- `autosre/skills/__init__.py`
- `autosre/skills/registry.py` - Skill discovery
- `tests/test_agents.py`
- `tests/test_orchestrator.py`
- `tests/test_episodic_memory.py`
- `tests/test_topology.py`
- `examples/investigate.py`
- `examples/topology.yaml`
- `README-v2.md`

## Key Prompts Preserved

### Planner System Prompt
```
You are the Planner agent for an AI SRE investigation system.
Your role is to:
1. Analyze the alert and available context (memory, topology)
2. Generate hypotheses about potential root causes
3. Select which investigation subagents to dispatch
```

### Synthesizer System Prompt
```
You are the Synthesizer agent for an AI SRE investigation system.
Your role is to combine findings from multiple investigation subagents and decide:
1. Is there enough evidence to determine the root cause?
2. Or should we investigate further?
```

### Strategy Generation Prompt
```
Generate a markdown strategy with these sections:
1. **Common Root Causes** - patterns seen across episodes
2. **Recommended Investigation Steps** - ordered by effectiveness
3. **Key Skills/Commands** - tools that worked well
4. **Anti-patterns** - approaches that didn't help
```

## Simplifications Made

1. ✅ PostgreSQL → SQLite (episodic memory)
2. ✅ Neo4j → YAML (service topology)
3. ✅ LangGraph → Plain async Python (orchestration)
4. ✅ HTTP config service → Local YAML/env (configuration)
5. ✅ LiteLLM proxy → Direct Anthropic/OpenAI (LLM calls)

## Status: COMPLETE ✅

All 20 iterations completed. AutoSRE v2 is ready for testing.

Run tests:
```bash
cd ~/clawd/projects/autosre
pytest tests/test_episodic_memory.py tests/test_topology.py tests/test_agents.py -v
```

Run example:
```bash
export ANTHROPIC_API_KEY=your-key
python examples/investigate.py
```
