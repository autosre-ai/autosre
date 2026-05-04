# AutoSRE v2 Build Log

## Iteration 1: Project Restructure
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `graph.py`: Uses LangGraph StateGraph with Send() for parallel subagent dispatch
- Clear separation: nodes/ for graph nodes, memory/ for episode storage
- state.py for Pydantic models (GraphState, InvestigationPlan, SynthesisDecision)

### What I Implemented
- Created new `autosre/` package structure
- Config module with Pydantic settings
- Module stubs for memory, topology, agents, skills, llm

---

## Iteration 2: SQLite Episodic Memory
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `memory/integration.py`: HTTP-based PostgreSQL storage
- Episode schema with alert_type, service_name, root_cause, skills_used
- Search by alert_type and service_name with similarity scoring

### What I Implemented
- `memory/episodic.py`: SQLite-based Episode storage
- FTS5 full-text search for episode content
- Tiered search (exact match → alert type → service → full-text)
- Strategy table for caching generated strategies

---

## Iteration 3: Strategy Generation
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `memory/strategy_generator.py`: LLM-based strategy generation
- Prompt template with episode summaries

### What I Implemented
- `memory/strategy.py`: Strategy generation from past episodes
- `enhance_prompt_with_memory()` for prepending context to prompts
- Caching strategies in SQLite

---

## Iteration 4: YAML Topology
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- Uses Neo4j for knowledge graph (too complex)
- Formats KG context differently per agent type

### What I Implemented
- `topology/service.py`: YAML-based service graph
- Dependency and dependent queries
- Blast radius calculation
- Alert-to-service mapping

---

## Iteration 5: Investigation State
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `state.py`: GraphState TypedDict with merge functions
- Hypothesis, InvestigationPlan, SynthesisDecision models

### What I Implemented
- `agents/state.py`: Pydantic models for investigation flow
- InvestigationState, Evidence, Hypothesis, SubagentResult
- InvestigationReport for final output

---

## Iteration 6: LLM Client
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- Uses LangChain/LiteLLM wrappers
- Fallback handling between providers

### What I Implemented
- `llm/client.py`: Direct API client for Anthropic and OpenAI
- `FallbackLLMClient` for automatic provider fallback
- `complete_structured()` for JSON output parsing

---

## Iteration 7: Planner Agent
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `nodes/planner.py`: Hypothesis generation and agent selection
- System prompt with available agents
- Structured output with InvestigationPlan

### What I Implemented
- `agents/planner.py`: Hypothesis generation
- Selects subagents based on hypotheses
- First iteration dispatches all agents for broad coverage

---

## Iteration 8: Synthesizer Agent
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `nodes/synthesizer.py`: Evidence sufficiency check
- Decides loop back to planner or proceed to writeup

### What I Implemented
- `agents/synthesizer.py`: Evidence combination
- SynthesisDecision with confidence scoring
- Gap identification for next iteration

---

## Iterations 9-12: Subagents
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `nodes/subagent_executor.py`: ReAct loop with tool calls
- Skill loading from config
- Deduplication of tool calls

### What I Implemented
- `agents/subagents/base.py`: BaseSubagent with skill framework
- `kubernetes.py`: Pod logs, describe, events, top skills
- `metrics.py`: Prometheus queries, error rate, latency
- `logs.py`: Log search, grep, journalctl, Loki
- `run_subagents_parallel()` for concurrent execution

---

## Iterations 13-16: Orchestrator
**Completed:** 2025-05-05

### What I Studied from OpenSRE
- `graph.py`: LangGraph flow with conditional edges
- Send() for fan-out, merge_dicts for fan-in

### What I Implemented
- `orchestrator.py`: Main investigation flow
- Plain async Python (no LangGraph)
- Full flow: init → memory → planner → subagents → synthesizer → writeup → store

---

## Iterations 17-18: Skills & Example
**Completed:** 2025-05-05

### What I Implemented
- `skills/registry.py`: Skill loader from YAML + Python
- `examples/investigate.py`: Full investigation demo
- Updated `__init__.py` with public API

---

## Iteration 19: Tests
**Completed:** 2025-05-05

### What I Implemented
- `tests/test_episodic_memory.py`: Memory storage tests
- `tests/test_topology.py`: Topology loading tests
- `tests/test_orchestrator.py`: Orchestrator unit tests
- Fixed import issues

---

## Iteration 20: Documentation
**Completed:** 2025-05-05

### What I Implemented
- `README-v2.md`: Full documentation
- Quick start, configuration, API examples
- Architecture diagram

---

## Summary

**Total Iterations:** 20
**Status:** ✅ Complete

### Core Components Built:
1. ✅ Episodic Memory (SQLite + FTS5)
2. ✅ Strategy Generation
3. ✅ YAML Service Topology
4. ✅ Investigation State Models
5. ✅ LLM Client (Anthropic/OpenAI)
6. ✅ Planner Agent
7. ✅ Synthesizer Agent
8. ✅ Kubernetes Subagent
9. ✅ Metrics Subagent
10. ✅ Logs Subagent
11. ✅ Orchestrator
12. ✅ Skill Registry
13. ✅ Tests
14. ✅ Documentation

### Key Differences from OpenSRE:
- SQLite instead of PostgreSQL (simpler)
- YAML topology instead of Neo4j (no extra infra)
- Plain async Python instead of LangGraph (cleaner)
- Direct API clients instead of LangChain (fewer deps)
- Pydantic v2 everywhere (better typing)

### What's Left for Production:
- [ ] Full ReAct loop in subagents
- [ ] CLI with Typer
- [ ] Slack/PagerDuty integration
- [ ] Evaluation framework
- [ ] PyPI publish
