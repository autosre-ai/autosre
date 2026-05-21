# Iteration 1 Plan — AutoSRE to World-Class

**Goal:** Transform AutoSRE from placeholder code to a working SRE agent that can actually investigate incidents.

**Time Estimate:** 2-3 hours total

---

## Current State Assessment

### What's Working ✅
1. **Project structure** — Clean `autosre/` package
2. **Episodic memory** — SQLite + FTS5 search
3. **YAML topology** — Service dependency graph
4. **Orchestrator flow** — init → memory → planner → subagents → synthesizer → writeup
5. **Import chain** — Works with venv
6. **Example script** — Runs (but fails on LLM/missing skills)

### What's Broken/Placeholder ❌
1. **Subagents are stubs** — Just return `[Would execute...]` placeholders
2. **No ReAct loop** — Subagents don't actually call LLM or iterate
3. **No real tool execution** — kubectl/prometheus/etc are fake
4. **Skills directory mismatch** — `skills/` folder exists but isn't wired to subagents
5. **No CLI** — `autosre investigate` doesn't work

### OpenSRE Features to Copy
1. **Skill system** — `load_skill()` + `run_script()` tools (from `tools/skill_tools.py`)
2. **ReAct loop** — Tool calling with reflection checkpoints (from `nodes/subagent_executor.py`)
3. **Environment manifest** — Per-agent context formatting (metrics agent gets different context)
4. **First iteration dispatch all** — Send all agents on iteration 0 for broad coverage

---

## Phase 1: Core Fixes (30 min)

### Task 1.1: Fix LLM Client Error Handling (S) — 10 min
**Problem:** Demo crashes without API key
**Fix:** Add `--mock` flag for testing without LLM

**Files:**
- `autosre/llm/client.py` — Add `MockLLMClient` that returns canned responses
- `autosre/config.py` — Add `mock_llm: bool = False` setting

**Verify:**
```bash
AUTOSRE_MOCK_LLM=true python examples/investigate.py checkout_5xx
```

### Task 1.2: Wire Skills Directory to Subagents (S) — 15 min
**Problem:** `skills/` directory exists but subagents don't use it
**Fix:** Create skill loader that reads `skills/{domain}/skill.yaml`

**Files:**
- `autosre/skills/loader.py` — Load skill.yaml, list scripts
- `autosre/agents/subagents/base.py` — Add `load_skill()` and `run_script()` methods

**Verify:**
```python
from autosre.skills.loader import load_skill
skill = load_skill("kubernetes")
print(skill.scripts)  # ['get_pods.py', 'describe.py', ...]
```

### Task 1.3: Add Basic CLI (S) — 5 min
**Problem:** No `autosre investigate` command
**Fix:** Add Typer CLI with investigate subcommand

**Files:**
- `autosre/cli/__init__.py` — Typer app
- `autosre/cli/commands/investigate.py` — investigate command
- `pyproject.toml` — Add entry point

**Verify:**
```bash
autosre investigate "checkout 500 errors"
```

---

## Phase 2: Skills Implementation (1 hour)

### Task 2.1: Implement Kubernetes Skills (L) — 30 min
**Problem:** Kubernetes subagent returns placeholders
**Fix:** Add real kubectl execution scripts

**Files:**
- `skills/kubernetes/scripts/get_pods.py` — `kubectl get pods` wrapper
- `skills/kubernetes/scripts/describe.py` — `kubectl describe` wrapper
- `skills/kubernetes/scripts/get_events.py` — `kubectl get events` wrapper
- `skills/kubernetes/scripts/get_logs.py` — `kubectl logs` wrapper
- `autosre/agents/subagents/kubernetes.py` — Use real scripts

**Verify:**
```bash
# Should work against any K8s cluster
kubectl config current-context
python skills/kubernetes/scripts/get_pods.py -n default
```

### Task 2.2: Implement Prometheus Skills (M) — 15 min
**Problem:** Metrics subagent can't query Prometheus
**Fix:** Add PromQL execution scripts

**Files:**
- `skills/prometheus/scripts/query.py` — `promql_query()` function
- `skills/prometheus/scripts/query_range.py` — Range queries
- `skills/prometheus/skill.yaml` — Document available queries
- `autosre/agents/subagents/metrics.py` — Wire up prometheus scripts

**Verify:**
```bash
# With Prometheus running
python skills/prometheus/scripts/query.py "up{job='kubernetes'}"
```

### Task 2.3: Implement Log Skills (M) — 15 min
**Problem:** Logs subagent can't search logs
**Fix:** Add basic log search (file-based, journalctl)

**Files:**
- `skills/logs/scripts/grep_logs.py` — Grep pattern in log files
- `skills/logs/scripts/journalctl.py` — System journal search
- `skills/logs/scripts/tail.py` — Tail recent logs
- `autosre/agents/subagents/logs.py` — Wire up log scripts

**Verify:**
```bash
python skills/logs/scripts/grep_logs.py "ERROR" --path /var/log/
```

---

## Phase 3: ReAct Loop (45 min)

### Task 3.1: Copy OpenSRE ReAct Pattern (L) — 30 min
**Problem:** Subagents run once and exit, no tool-calling loop
**Fix:** Implement proper ReAct loop with tool calling

**Files:**
- `autosre/agents/subagents/base.py` — Add `run_react_loop()` method

**Key features from OpenSRE:**
1. Tool binding with LLM (`llm.bind_tools(tools)`)
2. Deduplication of tool calls (`seen_calls` set)
3. Reflection checkpoints every 5 tool calls
4. Forced summarization on max loops
5. Early exit when domain has no signals

**Verify:**
```python
# Subagent should make multiple tool calls
result = await kubernetes_agent.investigate(alert)
assert len(result.evidence) > 1  # Multiple evidence pieces
```

### Task 3.2: Add Reflection Checkpoints (S) — 15 min
**Problem:** LLMs can spin in circles
**Fix:** Inject reflection prompts every N tool calls

**Files:**
- `autosre/agents/subagents/base.py` — Add checkpoint logic

**From OpenSRE:**
```python
if tool_call_count > 0 and tool_call_count % 5 == 0:
    messages.append(HumanMessage(content=(
        "REFLECTION CHECKPOINT: Before making more tool calls, briefly assess:\n"
        "1. What have you learned so far?\n"
        "2. Which hypotheses can you confirm or eliminate?\n"
        "3. What is the single most valuable next action?\n"
        "4. Are you going in circles or making progress?"
    )))
```

---

## Phase 4: Demo That Works (30 min)

### Task 4.1: Create Mock Infrastructure (M) — 15 min
**Problem:** Demo requires real K8s cluster
**Fix:** Add mock data responses for offline demo

**Files:**
- `examples/mock_data/pods.json` — Sample pod listing
- `examples/mock_data/events.json` — Sample K8s events
- `examples/mock_data/logs.txt` — Sample error logs
- `skills/kubernetes/scripts/*.py` — Add `--mock` flag

**Verify:**
```bash
python skills/kubernetes/scripts/get_pods.py --mock
# Returns realistic looking pod data
```

### Task 4.2: End-to-End Demo Script (M) — 15 min
**Problem:** `examples/investigate.py` fails without API key
**Fix:** Add full demo that works with mock LLM

**Files:**
- `examples/demo.py` — Self-contained demo
- `examples/README.md` — How to run demo

**Verify:**
```bash
AUTOSRE_MOCK_LLM=true python examples/demo.py
# Shows full investigation flow with mock data
```

---

## Phase 5: Tests That Pass (15 min)

### Task 5.1: Fix Existing Test Failures (S) — 10 min
**Problem:** Some tests may be broken after changes
**Fix:** Update tests to match new code

**Files:**
- `tests/test_orchestrator.py` — Update for mock LLM
- `tests/test_subagents.py` — Test real tool execution

**Verify:**
```bash
pytest tests/ -v --tb=short
```

### Task 5.2: Add Integration Test (S) — 5 min
**Problem:** No end-to-end test
**Fix:** Add integration test with mock everything

**Files:**
- `tests/test_integration.py` — Full investigation flow test

**Verify:**
```bash
pytest tests/test_integration.py -v
```

---

## Success Criteria

After Iteration 1, these should all work:

1. **CLI works:**
   ```bash
   autosre investigate "checkout 500 errors" --mock
   ```

2. **Demo runs offline:**
   ```bash
   AUTOSRE_MOCK_LLM=true python examples/demo.py
   ```

3. **Subagents make real tool calls** (with mock data):
   ```python
   result = await kubernetes_agent.investigate(alert)
   assert result.evidence  # Has real evidence
   ```

4. **Tests pass:**
   ```bash
   pytest tests/ -v
   # 90%+ passing
   ```

5. **Full investigation produces report:**
   ```python
   report = await orchestrator.investigate("payment timeout")
   assert report.root_cause  # Has a root cause
   assert report.evidence  # Has gathered evidence
   ```

---

## Agent Assignment

| Task | Est Time | Agent |
|------|----------|-------|
| 1.1 Mock LLM | 10 min | Any |
| 1.2 Wire Skills | 15 min | Any |
| 1.3 Basic CLI | 5 min | Any |
| 2.1 K8s Skills | 30 min | Skills Agent |
| 2.2 Prometheus Skills | 15 min | Skills Agent |
| 2.3 Log Skills | 15 min | Skills Agent |
| 3.1 ReAct Loop | 30 min | Core Agent |
| 3.2 Reflection | 15 min | Core Agent |
| 4.1 Mock Infra | 15 min | Demo Agent |
| 4.2 Demo Script | 15 min | Demo Agent |
| 5.1 Fix Tests | 10 min | Test Agent |
| 5.2 Integration Test | 5 min | Test Agent |

**Parallel execution possible:**
- Phase 2 (Skills) can run in parallel with Phase 3 (ReAct)
- Phase 4 (Demo) depends on Phase 2+3
- Phase 5 (Tests) runs last

---

## Key Files to Copy from OpenSRE

1. **ReAct pattern:** `/tmp/OpenSRE-real/sre-agent/nodes/subagent_executor.py`
   - `make_subagent_executor()` — Full ReAct loop implementation
   - Reflection checkpoints
   - Deduplication
   - Forced summarization

2. **Skill tools:** `/tmp/OpenSRE-real/sre-agent/tools/skill_tools.py`
   - `load_skill()` — Load SKILL.md documentation
   - `run_script()` — Execute skill scripts

3. **Agent context formatting:** `/tmp/OpenSRE-real/sre-agent/nodes/subagent_executor.py`
   - `_format_kg_for_agent()` — Different context per agent type
   - `_format_env_for_agent()` — Environment manifest per agent

---

*Created: 2026-05-05*
*Status: Ready for execution*
