# Changelog

All notable changes to AutoSRE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Testing & Coverage Sprint (Iterations 1-10)**
  - Tests for ownership management module (18 tests)
  - Tests for change tracking module (17 tests) 
  - Tests for runbook indexing module (26 tests)
  - Tests for learning patterns and incident store (27 tests)
  - Tests for skills base class and registry (28 tests)
  - Tests for real-time streaming module (28 tests)
  - Tests for Prometheus metrics exporter (23 tests)
  - Tests for structured logging module (24 tests)
  - Total: **556 tests, 34% coverage** (up from 281/21%)

- **Evals Expansion**
  - Expanded evaluation scenarios to 33 total:
    - Kafka consumer lag
    - Load balancer unhealthy hosts
    - S3 bucket permissions
    - Kubernetes OOM limits

- **Evals & Polish Sprint**
  - Expanded evaluation scenarios from 10 to 33:
    - Database incidents: connection pool, replication lag, slow queries
    - Kubernetes failures: node not ready, pod eviction, HPA thrashing, image pull
    - Network issues: DNS resolution, packet loss
    - Memory issues: gradual leaks, Redis exhaustion  
    - Security/auth: certificate chain, secret rotation
    - Infrastructure: disk I/O saturation, cronjob cascades
    - Advanced patterns: thundering herd, service mesh, API rate limiting
  - New `autosre/logging.py` module with structured logging:
    - JSON formatter for production
    - Human-readable formatter for development
    - Configurable log levels
    - Extra field support for structured context
  - New `autosre/exceptions.py` with actionable error messages
  - Added `types-PyYAML` to dev dependencies for mypy

- **Testing Sprint (Previous)**
  - 236 new tests (281 total) - from 7% to 21% coverage
  - Comprehensive fixtures in conftest.py

- **New CLI Commands**
  - `autosre init` - Initialize AutoSRE in a directory
  - `autosre status` - Show overall system status

- Updated GitHub Actions CI to use uv for faster builds
- Added Python 3.13 to test matrix
- Added pydantic-settings and python-dotenv dependencies

### Changed
- Fixed license in pyproject.toml: Apache-2.0 (matches LICENSE file)
- Added MANIFEST.in for source distributions
- Replaced deprecated `datetime.utcnow()` with timezone-aware alternative throughout codebase

### Fixed
- Type hint fixes across multiple modules for mypy compliance
- All deprecation warnings for datetime handling
- Fixed evals module exports (load_scenario, get_all_scenarios, etc.)

---

### Previous Changes

## [0.1.0] - 2024-03-15

### Added
- 🎉 **Initial release of OpenSRE**

#### Core Architecture
- Multi-agent system with Observer, Reasoner, Actor, and Notifier agents
- Skill-based plugin architecture for extensibility
- YAML-based agent definitions with templating support
- Context passing between agent steps

#### LLM Integration
- **Ollama** support for local, privacy-first LLM
- **OpenAI** support (GPT-4, GPT-4o)
- **Anthropic** support (Claude 3.5 Sonnet)
- Configurable prompts and context windows

#### Built-in Skills
- **prometheus** — Query metrics, manage alerts and silences
- **kubernetes** — Manage pods, deployments, get logs, rollback
- **slack** — Send messages, interactive approval buttons
- **pagerduty** — Acknowledge, resolve incidents
- **http** — Generic HTTP requests
- **aws** — AWS cloud operations
- **gcp** — GCP cloud operations
- **azure** — Azure cloud operations
- **github** — Repository operations
- **jira** — Ticket management
- **argocd** — GitOps deployments
- **telegram** — Telegram notifications
- **dynatrace** — Dynatrace integration

#### Pre-built Agents
- **incident-responder** — Auto-responds to PagerDuty/Alertmanager alerts
- **pod-crash-handler** — Handles Kubernetes pod crashes with analysis
- **deploy-validator** — Post-deployment health validation
- **cert-checker** — SSL certificate expiry monitoring
- **cost-anomaly** — Cloud cost anomaly detection
- **capacity-planner** — Resource capacity forecasting
- **runbook-executor** — Generic runbook execution engine

#### CLI Interface
- `opensre start` — Start daemon or foreground server
- `opensre investigate` — Manual investigation trigger
- `opensre status` — System status check
- `opensre skill list|install|info` — Skill management
- `opensre agent run|deploy|config|logs` — Agent management
- `opensre config show|validate` — Configuration management
- `opensre test` — Connectivity testing

#### API Server
- REST API for investigations and management
- WebSocket for real-time updates
- Webhook endpoints for Alertmanager, PagerDuty
- OpenAPI/Swagger documentation
- CORS support

#### MCP Server
- Model Context Protocol support for AI assistant integration
- Tool definitions for all skills
- Resource definitions for infrastructure state

#### Safety & Security
- Human-in-the-loop approval workflows
- Action allowlists and blocklists
- Protected namespace support
- API key authentication
- Slack signature verification
- Comprehensive audit logging
- Role-based action permissions

#### Knowledge Layer
- Runbook integration with semantic search
- Incident memory and pattern matching
- Vector store for context retrieval

#### Deployment
- Docker support with compose files
- Helm chart for Kubernetes
- systemd service configuration
- Multi-environment configuration

### Security
- API key authentication for all endpoints
- Webhook signature verification (Slack, PagerDuty)
- Audit logging for all actions
- No secrets logged or exposed

## [0.0.1] - 2024-02-01

### Added
- Project scaffolding
- Initial architecture design document
- Basic Prometheus integration proof of concept
- CLI skeleton

---

[Unreleased]: https://github.com/srisainath/opensre/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/srisainath/opensre/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/srisainath/opensre/releases/tag/v0.0.1
