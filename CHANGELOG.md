# Changelog

All notable changes to AutoSRE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Local LLM support via Ollama (zero API cost)
- Confidence scoring for root cause analysis
- Human approval workflow for critical actions
- Comprehensive audit logging

## [2.0.0] - 2024-05-15

### Added
- Complete architecture rewrite with multi-agent system
- **Triage Agent** - Alert classification and severity assessment
- **Kubernetes Agent** - Pod, deployment, and event analysis
- **Metrics Agent** - Prometheus query and anomaly detection
- **Logs Agent** - Loki search and pattern correlation
- **Remediation Agent** - Safe, reversible fix generation
- ReAct (Reasoning + Acting) investigation pattern
- Knowledge base for runbooks and incident history
- WebSocket support for real-time investigation updates
- Docker Compose demo stack with Prometheus and Alertmanager
- Helm chart for Kubernetes deployment
- Comprehensive test suite (unit, integration, e2e)

### Changed
- Migrated from monolithic to multi-agent architecture
- Improved LLM abstraction layer (OpenAI, Anthropic, Ollama)
- Better error handling and retry logic
- Enhanced API documentation with OpenAPI schemas

### Security
- Non-root Docker containers
- Trivy vulnerability scanning in CI
- Secret management via environment variables
- Rate limiting on API endpoints

## [1.0.0] - 2024-02-15

### Added
- Initial release
- Basic incident investigation workflow
- Prometheus and Kubernetes integration
- OpenAI GPT-4 support
- CLI interface
- REST API

[Unreleased]: https://github.com/autosre-ai/autosre/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/autosre-ai/autosre/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/autosre-ai/autosre/releases/tag/v1.0.0
