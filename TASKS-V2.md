# AutoSRE v2 - Task Breakdown

## Legend
- **S** = Small (< 30 min)
- **M** = Medium (30 min - 2 hours)
- **L** = Large (2+ hours)

---

## Phase 1: Core Architecture

### 1.1 Project Restructure (M)
**What:** Reorganize project to new structure
**Files:**
- Create `autosre/` package structure
- Module stubs for all components
**Verify:** All imports work

- [x] Complete ✅

### 1.2 SQLite Memory Schema (S)
**What:** Create episodic memory database
**Files:**
- `autosre/memory/episodic.py`
**Verify:** Can store and retrieve episodes

- [x] Complete ✅

### 1.3 Memory Search + Strategy (M)
**What:** Implement similar episode search and strategy generation
**Files:**
- `autosre/memory/episodic.py` - search_similar()
- `autosre/memory/strategy.py` - generate_strategy()
**Verify:** Returns relevant past investigations

- [x] Complete ✅

### 1.4 YAML Topology Loader (S)
**What:** Load service topology from YAML
**Files:**
- `autosre/topology/service.py`
- `examples/topology.yaml`
**Verify:** Can query dependencies and blast radius

- [x] Complete ✅

### 1.5 Config System (S)
**What:** Pydantic settings with env var support
**Files:**
- `autosre/config.py`
- `examples/config.yaml`
**Verify:** Config loads from file and env vars

- [x] Complete ✅

---

## Phase 2: Multi-Agent Investigation

### 2.1 Investigation State (S)
**What:** Define state schema for investigation flow
**Files:**
- `autosre/agents/state.py`
**Verify:** Pydantic models validate correctly

- [x] Complete ✅

### 2.2 LLM Client (M)
**What:** Multi-provider LLM with fallback
**Files:**
- `autosre/llm/client.py`
**Verify:** Can call Anthropic, fallback to OpenAI

- [x] Complete ✅

### 2.3 Planner Agent (L)
**What:** Generate hypotheses and select subagents
**Files:**
- `autosre/agents/planner.py`
**Verify:** Given alert, returns hypotheses + agent selection

- [x] Complete ✅

### 2.4 Subagent Base (M)
**What:** Base class for investigation subagents
**Files:**
- `autosre/agents/subagents/base.py`
**Verify:** Subagents can register skills and execute

- [x] Complete ✅

### 2.5 Kubernetes Subagent (L)
**What:** K8s investigation agent
**Files:**
- `autosre/agents/subagents/kubernetes.py`
**Skills:** pod_logs, describe, events, get_pods, top_pods
**Verify:** Can investigate K8s issues

- [x] Complete ✅

### 2.6 Metrics Subagent (M)
**What:** Prometheus/metrics investigation
**Files:**
- `autosre/agents/subagents/metrics.py`
**Skills:** query_prometheus, query_range, error_rate, latency
**Verify:** Can query Prometheus

- [x] Complete ✅

### 2.7 Logs Subagent (M)
**What:** Log investigation agent
**Files:**
- `autosre/agents/subagents/logs.py`
**Skills:** search_logs, tail_logs, grep_errors, journalctl, loki_search
**Verify:** Can search logs for patterns

- [x] Complete ✅

### 2.8 Synthesizer Agent (L)
**What:** Combine evidence from subagents
**Files:**
- `autosre/agents/synthesizer.py`
**Verify:** Determines if evidence is sufficient, generates feedback

- [x] Complete ✅

### 2.9 Writeup Agent (M)
**What:** Generate final investigation report
**Files:**
- `autosre/agents/writeup.py`
**Verify:** Produces structured report with root cause

- [x] Complete ✅

### 2.10 Orchestrator (L)
**What:** Main investigation flow coordinator
**Files:**
- `autosre/orchestrator.py`
**Flow:** init → memory → planner → subagents → synthesizer → writeup → store
**Verify:** Full investigation runs end-to-end

- [x] Complete ✅

---

## Phase 3: Skills System

### 3.1 Skill Registry (M)
**What:** Load skills from YAML definitions
**Files:**
- `autosre/skills/registry.py`
**Verify:** Skills can be loaded and registered

- [x] Complete ✅

### 3.2-3.4 Built-in Skills (M)
**What:** Skills are built into subagents for v2
**Verify:** Each subagent has working skills

- [x] Complete ✅ (embedded in subagents)

---

## Phase 4: Polish

### 4.1 Tests (M)
**What:** Unit tests for core components
**Files:**
- `tests/test_episodic_memory.py`
- `tests/test_topology.py`
- `tests/test_orchestrator.py`
**Verify:** Tests pass

- [x] Complete ✅

### 4.2 Documentation (M)
**What:** README and examples
**Files:**
- `README-v2.md`
- `examples/investigate.py`
**Verify:** New user can get started

- [x] Complete ✅

### 4.3 Example Script (S)
**What:** Working investigation example
**Files:**
- `examples/investigate.py`
**Verify:** Runs end-to-end with API key

- [x] Complete ✅

---

## Progress Summary

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| Core | 5 | 5 | ✅ |
| Multi-Agent | 10 | 10 | ✅ |
| Skills | 2 | 2 | ✅ |
| Polish | 3 | 3 | ✅ |

**Total:** 20/20 tasks (100%)

---

## What Was Built

### Core Components:
1. ✅ **Episodic Memory** - SQLite + FTS5 full-text search
2. ✅ **Strategy Generation** - LLM-based from past episodes
3. ✅ **Service Topology** - YAML with blast radius
4. ✅ **Config System** - Pydantic settings
5. ✅ **LLM Client** - Anthropic + OpenAI with fallback
6. ✅ **Planner Agent** - Hypothesis generation
7. ✅ **Synthesizer Agent** - Evidence combination
8. ✅ **Writeup Agent** - Report generation
9. ✅ **Kubernetes Subagent** - 5 skills
10. ✅ **Metrics Subagent** - 4 skills  
11. ✅ **Logs Subagent** - 5 skills
12. ✅ **Orchestrator** - Full investigation flow
13. ✅ **Skill Registry** - YAML + Python loader
14. ✅ **Tests** - Memory, topology, orchestrator
15. ✅ **Documentation** - README, examples

### Key Design Decisions:
- **SQLite** instead of PostgreSQL (simpler, local-first)
- **YAML topology** instead of Neo4j (no extra infra)
- **Plain async Python** instead of LangGraph (cleaner code)
- **Direct API clients** instead of LangChain (fewer deps)
- **Pydantic v2** for all models (better typing)

---

## Future Work (Not in v2 Scope)

- [ ] CLI with Typer
- [ ] Full ReAct loop in subagents
- [ ] Slack/PagerDuty integration
- [ ] Evaluation framework with scenarios
- [ ] Traces subagent (Jaeger/Tempo)
- [ ] Changes subagent (Git/ArgoCD)
- [ ] PyPI publish

---

*Last Updated: 2025-05-05*
*v2 Overnight Build Complete*
