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
- Create `src/autosre/` package structure
- Move existing code to new locations
- Update imports
**Verify:** `autosre --help` works

- [ ] Complete

### 1.2 SQLite Memory Schema (S)
**What:** Create episodic memory database
**Files:**
- `src/autosre/memory/episodic.py`
- `src/autosre/memory/models.py`
**Verify:** Can store and retrieve episodes

- [ ] Complete

### 1.3 Memory Search (M)
**What:** Implement similar episode search
**Files:**
- `src/autosre/memory/episodic.py` - search_similar()
**Verify:** Returns relevant past investigations

- [ ] Complete

### 1.4 YAML Topology Loader (S)
**What:** Load service topology from YAML
**Files:**
- `src/autosre/topology/service.py`
- `examples/topology.yaml`
**Verify:** Can query dependencies and blast radius

- [ ] Complete

### 1.5 Config System (S)
**What:** Pydantic settings with YAML support
**Files:**
- `src/autosre/config.py`
- `examples/config.yaml`
**Verify:** Config loads from file and env vars

- [ ] Complete

### 1.6 CLI Foundation (M)
**What:** Typer CLI with main commands
**Files:**
- `src/autosre/cli.py`
**Commands:**
- `autosre investigate <alert>`
- `autosre history`
- `autosre memory stats`
- `autosre topology show`
**Verify:** All commands respond (even if stub)

- [ ] Complete

---

## Phase 2: Multi-Agent Investigation

### 2.1 Investigation State (S)
**What:** Define state schema for investigation flow
**Files:**
- `src/autosre/agents/state.py`
**Verify:** Pydantic models validate correctly

- [ ] Complete

### 2.2 LLM Router (M)
**What:** Multi-provider LLM with fallback
**Files:**
- `src/autosre/llm/router.py`
**Verify:** Can call Claude, fallback to OpenAI, fallback to Ollama

- [ ] Complete

### 2.3 Planner Agent (L)
**What:** Generate hypotheses and select subagents
**Files:**
- `src/autosre/agents/planner.py`
**Verify:** Given alert, returns hypotheses + agent selection

- [ ] Complete

### 2.4 Subagent Base (M)
**What:** Base class for investigation subagents
**Files:**
- `src/autosre/agents/subagents/base.py`
**Verify:** Subagents can register skills and execute

- [ ] Complete

### 2.5 Kubernetes Subagent (L)
**What:** K8s investigation agent
**Files:**
- `src/autosre/agents/subagents/kubernetes.py`
**Skills:** pod_logs, describe, events, exec
**Verify:** Can investigate K8s issues

- [ ] Complete

### 2.6 Metrics Subagent (M)
**What:** Prometheus/metrics investigation
**Files:**
- `src/autosre/agents/subagents/metrics.py`
**Skills:** query_prometheus, anomaly_detect
**Verify:** Can query Prometheus and detect anomalies

- [ ] Complete

### 2.7 Logs Subagent (M)
**What:** Log investigation agent
**Files:**
- `src/autosre/agents/subagents/logs.py`
**Skills:** search_logs, tail_logs
**Verify:** Can search logs for patterns

- [ ] Complete

### 2.8 Synthesizer Agent (L)
**What:** Combine evidence from subagents
**Files:**
- `src/autosre/agents/synthesizer.py`
**Verify:** Determines if evidence is sufficient, generates feedback

- [ ] Complete

### 2.9 Writeup Agent (M)
**What:** Generate final investigation report
**Files:**
- `src/autosre/agents/writeup.py`
**Verify:** Produces structured report with root cause

- [ ] Complete

### 2.10 Orchestrator (L)
**What:** Main investigation flow coordinator
**Files:**
- `src/autosre/orchestrator.py`
**Flow:** init → memory → planner → subagents → synthesizer → writeup → store
**Verify:** Full investigation runs end-to-end

- [ ] Complete

---

## Phase 3: Skills System

### 3.1 Skill Loader (M)
**What:** Load skills from YAML definitions
**Files:**
- `src/autosre/skills/loader.py`
- `src/autosre/skills/registry.py`
**Verify:** Skills auto-discovered and registered

- [ ] Complete

### 3.2 Kubernetes Skills (L)
**What:** Full K8s skill implementations
**Files:**
- `skills/kubernetes/skill.yaml`
- `skills/kubernetes/pod_logs.py`
- `skills/kubernetes/describe.py`
- `skills/kubernetes/events.py`
**Verify:** Each skill executes correctly

- [ ] Complete

### 3.3 Metrics Skills (M)
**What:** Prometheus query skills
**Files:**
- `skills/metrics/skill.yaml`
- `skills/metrics/query.py`
- `skills/metrics/anomaly.py`
**Verify:** Can query and detect anomalies

- [ ] Complete

### 3.4 Logs Skills (M)
**What:** Log search skills
**Files:**
- `skills/logs/skill.yaml`
- `skills/logs/search.py`
**Verify:** Can search logs

- [ ] Complete

### 3.5 Changes Skills (M)
**What:** Recent changes detection
**Files:**
- `skills/changes/skill.yaml`
- `skills/changes/git_history.py`
- `skills/changes/deploys.py`
**Verify:** Can find recent deployments

- [ ] Complete

---

## Phase 4: Memory & Strategy

### 4.1 Memory Store (M)
**What:** Store completed investigations
**Files:**
- `src/autosre/memory/episodic.py` - store_episode()
**Verify:** Episodes persisted with metadata

- [ ] Complete

### 4.2 Strategy Generation (L)
**What:** Generate strategies from past episodes
**Files:**
- `src/autosre/memory/strategy.py`
**Verify:** Given 2+ similar episodes, generates reusable strategy

- [ ] Complete

### 4.3 Memory CLI (S)
**What:** CLI commands for memory management
**Files:**
- `src/autosre/cli.py` - memory subcommand
**Commands:** stats, search, clear
**Verify:** Can view and manage memory

- [ ] Complete

---

## Phase 5: Polish & Ship

### 5.1 Evaluation Framework (L)
**What:** Test against synthetic scenarios
**Files:**
- `tests/scenarios/` - scenario definitions
- `src/autosre/eval/runner.py`
**Verify:** Can measure accuracy on test cases

- [ ] Complete

### 5.2 Terminal Reporter (M)
**What:** Rich terminal output for reports
**Files:**
- `src/autosre/reporters/terminal.py`
**Verify:** Beautiful, readable output

- [ ] Complete

### 5.3 Documentation (M)
**What:** README, quickstart, architecture docs
**Files:**
- `README.md`
- `docs/quickstart.md`
- `docs/architecture.md`
- `docs/skills.md`
**Verify:** New user can get started in 5 min

- [ ] Complete

### 5.4 CI/CD (M)
**What:** GitHub Actions for test/lint/publish
**Files:**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
**Verify:** PR checks run, releases publish to PyPI

- [ ] Complete

### 5.5 PyPI Publish (S)
**What:** Publish to PyPI
**Verify:** `pip install autosre` works

- [ ] Complete

---

## Progress Summary

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| Core | 6 | 0 | ⬜ |
| Multi-Agent | 10 | 0 | ⬜ |
| Skills | 5 | 0 | ⬜ |
| Memory | 3 | 0 | ⬜ |
| Polish | 5 | 0 | ⬜ |

**Total:** 0/29 tasks (0%)

---

## Quick Start Today

Priority order for first session:
1. **1.1** Project Restructure
2. **1.2** SQLite Memory Schema  
3. **1.4** YAML Topology Loader
4. **1.6** CLI Foundation
5. **2.1** Investigation State

This gives us a working skeleton to build on.

---

*Last Updated: 2026-05-03*
