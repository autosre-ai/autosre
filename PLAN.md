# AutoSRE - Implementation Plan

**Version:** 1.0.0
**Last Updated:** 2026-05-01

## Current State

| Metric | Value |
|--------|-------|
| Tests | 842 passing |
| Coverage | ~38% |
| CLI Commands | 8 working |
| Web Routes | 5 working |
| Eval Scenarios | 35 |

## 5-Iteration Plan

### Iteration 1: Foundation Validation
**Focus:** Verify core functionality, fix critical bugs

- [x] Install and test CLI commands
- [x] Run full test suite (842 tests passing)
- [x] Test web server startup
- [x] Create SPEC.md
- [x] Create PLAN.md
- [ ] Fix demo mode (`--demo` flag)
- [ ] Test all eval scenarios

### Iteration 2: Testing & Coverage
**Focus:** Increase test coverage to 60%+

- [ ] Add tests for web routes
- [ ] Add tests for MCP client/server
- [ ] Add tests for remediation manager
- [ ] Add tests for watch module
- [ ] Add integration tests for CLI commands

### Iteration 3: Web UI Polish
**Focus:** Ensure web UI is fully functional

- [ ] Fix any broken templates
- [ ] Add responsive design improvements
- [ ] Add WebSocket support for real-time updates
- [ ] Test all HTMX interactions
- [ ] Add loading states and error handling

### Iteration 4: Demo Mode & Examples
**Focus:** Make demo experience seamless

- [ ] Implement mock data generators
- [ ] Create sample runbooks
- [ ] Add example configurations
- [ ] Record demo GIF for README
- [ ] Create quickstart tutorial

### Iteration 5: Production Readiness
**Focus:** Polish and ship

- [ ] Run full E2E tests
- [ ] Update all documentation
- [ ] Verify PyPI packaging
- [ ] Add GitHub Actions CI
- [ ] Create release notes
- [ ] Tag v0.1.0 release

## Task Priority Matrix

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P0 | Fix demo mode | Medium | High |
| P0 | Test web UI | Low | High |
| P1 | Increase test coverage | High | Medium |
| P1 | Fix CLI help messages | Low | Medium |
| P2 | Add WebSocket updates | Medium | Medium |
| P2 | Polish responsive UI | Medium | Low |

## Dependencies

### External (Required)
- Python 3.11+

### External (Optional)
- Docker (for sandbox)
- kubectl (for K8s integration)
- kind (for local clusters)

### Python Packages (Core)
- click >= 8.1.0
- pydantic >= 2.0.0
- rich >= 13.0.0
- fastapi >= 0.110.0
- httpx >= 0.25.0
- uvicorn >= 0.27.0

## Testing Strategy

```bash
# Unit tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=autosre --cov-report=term-missing

# Specific module
uv run pytest tests/test_cli.py -v

# Integration tests
uv run pytest tests/ -m integration
```

## Commands to Verify

```bash
# Core CLI
autosre --version
autosre --help
autosre init
autosre status

# Context management
autosre context show
autosre context sync --all

# Evaluation
autosre eval list
autosre eval run --scenario high_cpu

# Web dashboard
autosre web start --port 8080

# Agent (requires LLM)
autosre agent config
autosre agent run --dry-run
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM costs in eval | Use mock LLM for tests |
| K8s not available | Sandbox mode with Kind |
| Port conflicts | Configurable ports |
| Missing deps | Graceful degradation |

## Success Metrics

- [ ] `pip install autosre && autosre --help` works
- [ ] `autosre eval run --scenario high_cpu` completes
- [ ] Web UI loads at localhost:8080
- [ ] 80%+ test coverage
- [ ] No critical bugs in issue tracker
