# OpenSRE Documentation

Welcome to the OpenSRE documentation! This guide will help you get started with AI-powered incident response.

## Quick Links

| Getting Started | Reference | Deployment |
|-----------------|-----------|------------|
| [Getting Started](getting-started.md) | [CLI Reference](cli-reference.md) | [Docker](deployment/docker.md) |
| [Installation](installation.md) | [API Reference](api-reference.md) | [Kubernetes](deployment/kubernetes.md) |
| [Configuration](CONFIGURATION.md) | [Architecture](ARCHITECTURE.md) | [systemd](deployment/systemd.md) |

## Documentation Structure

### Core Guides

- **[Getting Started](getting-started.md)** — Your first investigation in 5 minutes
- **[Installation](installation.md)** — pip, Docker, Helm, and more
- **[Configuration](CONFIGURATION.md)** — Environment variables and config files
- **[CLI Reference](cli-reference.md)** — Complete command-line interface guide
- **[API Reference](api-reference.md)** — REST API and WebSocket documentation

### Skills

Skills are plugins that connect OpenSRE to your infrastructure:

- **[Skills Overview](skills/overview.md)** — How skills work
- **[Prometheus](skills/prometheus.md)** — Query metrics, manage alerts
- **[Kubernetes](skills/kubernetes.md)** — Manage pods, deployments
- **[Slack](skills/slack.md)** — Notifications and approvals
- **[Creating Skills](skills/creating-skills.md)** — Build custom skills

### Agents

Agents are automated workflows that respond to events:

- **[Agents Overview](agents/overview.md)** — How agents work
- **[Writing Agents](agents/writing-agents.md)** — Create custom agents
- **[Agent Reference](agents/agent-reference.md)** — Agent YAML schema
- **[Agent Catalog](../agents/CATALOG.md)** — Pre-built agents

### Architecture

- **[System Architecture](ARCHITECTURE.md)** — Multi-agent design
- **[Security](security.md)** — RBAC, approvals, audit logging

### Deployment

- **[Docker](deployment/docker.md)** — Single container and Compose
- **[Kubernetes](deployment/kubernetes.md)** — Helm and raw manifests
- **[systemd](deployment/systemd.md)** — Linux service deployment

### Operations

- **[Troubleshooting](troubleshooting.md)** — Common issues and solutions
- **[Security](security.md)** — Security model and best practices

### Integration Guides

- **[Slack Setup](SLACK_SETUP.md)** — Configure Slack app
- **[PagerDuty](PAGERDUTY.md)** — PagerDuty integration
- **[Runbooks](RUNBOOKS.md)** — Runbook integration

## Version

Current version: **0.1.0**

See the [Changelog](../CHANGELOG.md) for release notes.

## Getting Help

- **[GitHub Issues](https://github.com/srisainath/opensre/issues)** — Bug reports
- **[GitHub Discussions](https://github.com/srisainath/opensre/discussions)** — Questions
- **[Discord](https://discord.gg/opensre)** — Real-time chat

## Contributing

See the [Contributing Guide](../CONTRIBUTING.md) for information on how to contribute.
