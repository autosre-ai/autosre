# Iteration 2 - Testing & Coverage

**Date:** 2026-05-02
**Duration:** ~45 minutes
**Focus:** Increase test coverage, add web route tests

## What Was Done

### 1. Web Route Tests
- Created `tests/test_web_routes.py` with 31 tests
- Tests all major pages: dashboard, evals, context, agent, feedback
- Tests HTMX partials and API endpoints
- Tests error handling and static files

### 2. Bug Fixes
- Fixed `TemplateResponse` calls in `autosre/web/routes/evals.py`
- Fixed `TemplateResponse` calls in `autosre/web/routes/feedback.py`
- Both had old-style dict args instead of keyword arguments

### 3. Coverage Analysis
- Ran full coverage report
- Identified modules with 0% coverage:
  - `autosre/watch.py` (depends on missing `opensre_core`)
  - `autosre/mcp_client.py`
  - `autosre/mcp_server.py`
  - `autosre/remediation/manager.py`
  - `autosre/runbooks/manager.py`
  - `autosre/api.py`
  - `autosre/cli.py` (old CLI)

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| Web Routes | ✅ Working | All 7 routes tested |
| HTMX Partials | ✅ Working | Scenario list, results, services |
| API Endpoints | ✅ Working | /api/scenarios, /api/results |
| Feedback Form | ✅ Working | Submit endpoint fixed |
| Test Suite | ✅ Working | 873 tests passing |

## What's Broken/Missing

| Issue | Severity | Notes |
|-------|----------|-------|
| `watch.py` dead code | Low | Depends on missing `opensre_core` |
| MCP untested | Medium | Model Context Protocol modules |
| Low coverage | Low | 41% vs target 80% |

## Metrics

```
Before:
- Tests: 842 passing
- Coverage: 39%

After:
- Tests: 873 passing (+31)
- Coverage: 41% (+2%)
```

### Coverage by Module Type

| Module Type | Coverage |
|-------------|----------|
| Web Routes | 54-68% |
| CLI Commands | 28-100% |
| Foundation | 90-100% |
| Security | 71-99% |
| Agent | 86-91% |
| Sandbox | 17-32% |
| Watch/MCP/API | 0% |

## Bugs Fixed

1. **evals.py:189** - `TemplateResponse` using positional args with dict context
2. **feedback.py:79** - Same issue, old-style template response

## Files Changed

```
autosre/web/routes/evals.py      # Fixed TemplateResponse
autosre/web/routes/feedback.py   # Fixed TemplateResponse
tests/test_web_routes.py         # New: 31 tests
```

## Next Steps (Iteration 3)

1. Polish web UI - ensure all templates render correctly
2. Add loading states to HTMX interactions
3. Fix any broken templates
4. Test web server under load
5. Add WebSocket for real-time updates

## Commands Reference

```bash
# Run new web tests
uv run pytest tests/test_web_routes.py -v

# Run with coverage
uv run pytest tests/ --cov=autosre --cov-report=term

# Check specific module coverage
uv run pytest tests/ --cov=autosre.web --cov-report=term-missing
```
