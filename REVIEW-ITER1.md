# AutoSRE v2 — Code Review (Iteration 1)

**Date:** 2025-06-05  
**Reviewer:** Review Agent  
**Files Reviewed:** 22 Python files in `autosre/`

---

## Executive Summary

The codebase is **well-structured** with good separation of concerns (agents, memory, topology, skills). The code follows modern Python practices (async/await, Pydantic v2, type hints). However, there are **critical issues** that must be addressed before production use.

**Overall Grade: B-** (Solid foundation, needs polish)

---

## 🔴 CRITICAL ISSUES (Must Fix)

### 1. Missing LLM Dependencies in pyproject.toml
**Location:** `pyproject.toml` vs `requirements.txt`  
**Impact:** Package will fail to install via pip

The `pyproject.toml` does NOT list `anthropic` or `openai` as dependencies, but the code requires them:
```python
# llm/client.py uses:
import anthropic
import openai
```

`requirements.txt` has them, but `pyproject.toml` (the actual package spec) doesn't. Users installing via `pip install autosre` will get runtime ImportErrors.

**Fix:** Add to pyproject.toml dependencies:
```toml
"anthropic>=0.18.0",
"openai>=1.0.0",
```

### 2. Module-Level Import at Bottom of File
**Location:** `autosre/agents/subagents/base.py:240-241`  
**Ruff Error:** E402

```python
# Line 240-241 - imports at bottom of file
import asyncio
from ..state import InvestigationState, Hypothesis
```

This is a **circular import workaround** but violates Python style and may cause issues:
- Import order is unpredictable
- IDE analysis breaks
- Module may fail to load in some scenarios

**Fix:** Refactor to avoid circular dependency or use `TYPE_CHECKING` guard:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..state import InvestigationState, Hypothesis
```

### 3. Unused Imports
**Location:** Multiple files  
**Ruff Errors:** F401

| File | Unused Import |
|------|---------------|
| `agents/state.py:9` | `typing.Literal` |
| `agents/writeup.py:21` | `InvestigationStatus` |
| `orchestrator.py:18` | `SynthesisDecision` |

These bloat the module and confuse readers.

**Fix:** Remove all unused imports.

### 4. Abstract Methods Missing Implementation Marker
**Location:** `autosre/llm/client.py:50`, `agents/subagents/base.py:86, 95, 177`

Methods marked `@abstractmethod` have `pass` as body:
```python
@abstractmethod
async def complete(self, ...):
    pass  # Should use ... or raise NotImplementedError
```

While technically correct, using `pass` suggests incomplete code.

**Fix:** Change to `...` (ellipsis) for abstract methods:
```python
@abstractmethod
async def complete(self, ...):
    ...
```

---

## 🟠 WARNINGS (Should Fix)

### 5. F-strings Without Placeholders (Code Smell)
**Location:** 7 occurrences  
**Ruff Error:** F541

```python
# planner.py:108
f"## Service Topology"  # No placeholders, just use regular string

# synthesizer.py:99
f"\n## Subagent Findings\n"
```

This is sloppy and suggests copy-paste errors or incomplete interpolation.

**Fix:** Remove `f` prefix from strings without placeholders.

### 6. Massive Trailing Whitespace Problem
**Location:** ~500 lines across all files  
**Ruff Error:** W291, W293

Nearly every file has blank lines with trailing whitespace. This:
- Bloats diffs
- Triggers pre-commit hooks
- Looks unprofessional

**Fix:** Run `ruff format autosre/` or configure editor to strip trailing whitespace.

### 7. Unsorted Imports
**Location:** 6 files  
**Ruff Error:** I001

Import blocks are unsorted:
- `__init__.py`
- `agents/__init__.py`
- `agents/state.py`
- `agents/subagents/__init__.py`
- `agents/subagents/base.py` (2 locations)

**Fix:** Run `ruff check --fix autosre/` to auto-fix.

### 8. Subagents Are Placeholders Only
**Location:** `agents/subagents/kubernetes.py`, `metrics.py`, `logs.py`

All three subagents return placeholder strings:
```python
return f"[Would fetch logs for pod: {kwargs.get('pod', 'unknown')}]"
```

They do **zero actual investigation**. This is fine for v0.2.0-alpha but should be clearly documented.

**Fix:** Add prominent docstring/comment marking these as stubs:
```python
"""
⚠️ PLACEHOLDER IMPLEMENTATION
This subagent does not perform real Kubernetes operations.
TODO: Integrate with kubernetes-python client.
"""
```

### 9. No Input Validation on LLM Prompts
**Location:** `agents/planner.py`, `synthesizer.py`, `writeup.py`

User-controlled alert data is interpolated directly into prompts:
```python
prompt_parts.append(f"## Alert\n```json\n{json.dumps(state.alert, indent=2)}\n```")
```

While not a security vulnerability per se (no shell injection), malicious alert content could:
- Cause prompt injection attacks
- Exceed token limits
- Trigger unexpected LLM behavior

**Fix:** Truncate and sanitize alert content:
```python
alert_json = json.dumps(state.alert, indent=2)[:2000]  # Limit size
```

### 10. No Rate Limiting on LLM Calls
**Location:** `llm/client.py`

No backoff, retry, or rate limiting. A runaway investigation loop could:
- Burn through API credits
- Hit rate limits and crash

**Fix:** Add `tenacity` retry decorator or implement exponential backoff.

---

## 🟡 SUGGESTIONS (Nice to Have)

### 11. Inconsistent Docstring Style
Some files have excellent docstrings (`orchestrator.py`), others have minimal ones (`state.py`). 

**Suggestion:** Standardize on Google or NumPy docstring style project-wide.

### 12. No Logging Configuration
Code uses `logging.getLogger(__name__)` but there's no log configuration. Users won't see any debug output.

**Suggestion:** Add `logging.basicConfig()` in `__init__.py` or provide a `configure_logging()` function.

### 13. Magic Numbers in Code
```python
max_tokens: int = 4096  # Why 4096?
similarity_threshold: float = 0.7  # Why 0.7?
```

**Suggestion:** Document the reasoning or make configurable.

### 14. Missing `__repr__` Methods
Pydantic models benefit from custom `__repr__` for debugging:
```python
>>> state
InvestigationState(investigation_id='abc123', status=RUNNING, ...)
```

### 15. Test Coverage Unknown
No tests visible in the reviewed scope. Cannot assess test coverage.

**Suggestion:** Ensure `tests/` directory exists with pytest tests.

---

## 🔒 SECURITY CONCERNS

### ✅ No Hardcoded Secrets
API keys are loaded from environment variables, not hardcoded. Good.

### ✅ No Dangerous Functions
No use of `eval()`, `exec()`, `pickle`, `os.system()`, or `subprocess.shell=True`. Good.

### ⚠️ SQL Injection Potential (Low Risk)
SQLite queries in `memory/episodic.py` use parameterized queries. However, FTS5 MATCH clause deserves review:
```python
WHERE episodes_fts MATCH ?
```
FTS5 MATCH has its own query syntax. Malicious input could alter search behavior.

**Risk Level:** Low (limited impact)
**Mitigation:** Validate/sanitize FTS query input.

### ⚠️ Prompt Injection Risk (Medium)
Alert descriptions from external sources (Alertmanager, PagerDuty) are embedded directly in LLM prompts. A crafted alert could hijack the investigation.

**Risk Level:** Medium  
**Mitigation:** Sanitize external input, use structured prompts, consider guardrails.

### ⚠️ File System Access in Skills
`skills/registry.py` uses `importlib.util.spec_from_file_location()` to dynamically load Python files. If `skills_dir` is user-controlled, this is code execution.

**Risk Level:** Low (internal use)  
**Mitigation:** Validate `skills_dir` is within expected paths.

---

## 📊 Ruff Summary

```
Total Issues: 528
- W291/W293 (trailing whitespace): ~470
- I001 (import sorting): 6
- F401 (unused imports): 4
- F541 (f-string no placeholders): 7
- E402 (import not at top): 2
```

**Fix Command:**
```bash
cd ~/clawd/projects/autosre
source .venv/bin/activate
ruff check autosre/ --fix
ruff format autosre/
```

---

## 📝 Action Items by Priority

### P0 (Before Alpha Release)
1. [ ] Add `anthropic` and `openai` to pyproject.toml dependencies
2. [ ] Fix circular import in `agents/subagents/base.py`
3. [ ] Remove unused imports
4. [ ] Run `ruff check --fix && ruff format`

### P1 (Before Beta Release)
5. [ ] Add input validation/truncation for LLM prompts
6. [ ] Mark stub subagents clearly as placeholders
7. [ ] Add LLM retry/backoff logic
8. [ ] Add logging configuration

### P2 (Before Production)
9. [ ] Implement real Kubernetes/Metrics/Logs subagents
10. [ ] Add comprehensive test suite
11. [ ] Add prompt injection defenses
12. [ ] Document magic numbers

---

## Conclusion

**AutoSRE v2 has a solid architectural foundation.** The separation of concerns (orchestrator → planner → subagents → synthesizer → writeup) is clean. Pydantic models are well-designed. The episodic memory with FTS5 is clever.

**However, it's not production-ready.** The subagents are stubs, there's no real investigation capability, and there are basic code quality issues (500+ lines of trailing whitespace!). 

**Recommendation:** Fix P0 items immediately, then focus on implementing real subagent integrations. This could be world-class with another 2-3 iterations of polish.

---

*Generated by Review Agent — Iteration 1*
