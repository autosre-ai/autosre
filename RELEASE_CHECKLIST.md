# AutoSRE V2 Release Checklist

## ✅ Completed

### Git & Repository
- [x] V2 code committed (460 files)
- [x] Pushed to `v2` branch on github.com/autosre-ai/autosre
- [x] Proper .gitignore
- [x] Proper .dockerignore

### Docker & Deployment
- [x] Root `Dockerfile` (multi-stage, slim)
- [x] `docker-compose.yml` (dev stack)
- [x] `docker-compose.demo.yml` (full demo with Prometheus, Alertmanager, Ollama)
- [x] `docker/Dockerfile.api` and `docker/Dockerfile.ui`
- [x] Demo app + load generator for testing
- [x] Prometheus alert rules (`demo/prometheus/alerts.yml`)
- [x] Alertmanager webhook config (`demo/alertmanager/alertmanager.yml`)
- [x] Grafana datasource provisioning

### CI/CD
- [x] `.github/workflows/ci.yaml` - Tests, lint, type check, Docker build
- [x] `.github/workflows/release.yaml` - PyPI + GHCR on tag
- [x] Dependabot configured

### Documentation
- [x] README.md with badges, architecture, quick start
- [x] CHANGELOG.md
- [x] CONTRIBUTING.md
- [x] LICENSE (Apache 2.0)
- [x] pyproject.toml with proper URLs and metadata

### Package
- [x] `uv build --sdist` works
- [x] Package name: `autosre` version 2.0.0
- [x] Entry point: `autosre` CLI

### Testing
- [x] Core tests pass (21/21)
- [x] Some unit tests have import issues (module refactoring needed)

### Makefile
- [x] `make demo` - Start full demo stack
- [x] `make demo-down/demo-logs/demo-clean` - Manage demo
- [x] `make demo-trigger-alert` - Trigger test alert

## 🔄 Coordinating with Other Sub-Agent

The other sub-agent is adding:
- Ollama client enhancements
- Confidence scoring
- Approval workflow
- Audit logging

Files they've modified (don't overwrite):
- `src/autosre/core/ollama_client.py`
- `src/autosre/core/confidence.py`
- `src/autosre/core/approval_gate.py`
- `src/autosre/core/audit.py`

## 📋 TODO Before Public Release

### High Priority
- [ ] Merge v2 to main (create PR: https://github.com/autosre-ai/autosre/pull/new/v2)
- [ ] Fix remaining test import issues
- [ ] Test full PyPI publish workflow (may need PYPI_API_TOKEN secret)
- [ ] Create v2.0.0 release tag
- [ ] Configure trusted publisher on PyPI

### Medium Priority
- [ ] Add demo GIF/video to README
- [ ] Test Docker image build and run
- [ ] Test Helm chart deployment
- [ ] Add code coverage badge

### Low Priority
- [ ] Add Discord/community links
- [ ] Set up GitHub Discussions
- [ ] Create initial documentation site

## 🚀 Quick Start Commands

```bash
# Clone and setup
git clone https://github.com/autosre-ai/autosre.git
cd autosre
git checkout v2

# Install
pip install -e ".[all,dev]"

# Run demo
make demo
# Open http://localhost:8000 (API), http://localhost:9090 (Prometheus)

# Trigger test alert
make demo-trigger-alert
```

## 📊 Stats

- Python files: 232
- Total files: 460+
- Test files: 51
- Core tests passing: 21/21
