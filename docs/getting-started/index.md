# Getting Started

Welcome to AutoSRE! This section will help you get up and running quickly.

## Overview

AutoSRE is an AI-powered Site Reliability Engineering agent that automates incident investigation. Whether you're a solo developer or running a large SRE team, AutoSRE helps you:

- **Reduce MTTR** — Automate the tedious context-gathering phase of incidents
- **Capture knowledge** — Build organizational memory from every incident
- **Scale on-call** — Provide 24/7 first-responder capabilities

## Quick Links

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Install AutoSRE via pip, Docker, or Helm

    [:octicons-arrow-right-24: Installation Guide](installation.md)

-   :material-rocket-launch:{ .lg .middle } **Quickstart**

    ---

    Run your first investigation in 5 minutes

    [:octicons-arrow-right-24: Quickstart Guide](quickstart.md)

-   :material-cog:{ .lg .middle } **Configuration**

    ---

    Configure integrations and customize behavior

    [:octicons-arrow-right-24: Configuration Guide](configuration.md)

</div>

## Prerequisites

Before installing AutoSRE, ensure you have:

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Python** | 3.11+ | 3.12 |
| **Memory** | 2 GB | 4 GB |
| **Disk** | 1 GB | 5 GB |
| **LLM Access** | Any supported provider | Claude or GPT-4 |

### Supported LLM Providers

AutoSRE requires an LLM for analysis. Choose one:

| Provider | Model | Notes |
|----------|-------|-------|
| **Anthropic** | Claude 3.5 Sonnet | Best reasoning, recommended |
| **OpenAI** | GPT-4o | Good balance of speed/quality |
| **Ollama** | Llama 3.1 | Local, privacy-focused |
| **Azure OpenAI** | GPT-4 | Enterprise, compliance |
| **LiteLLM** | Any | Unified API for 100+ models |

## Installation Methods

Choose the method that fits your use case:

| Method | Best For | Time |
|--------|----------|------|
| [pip](#pip) | Development, testing | 2 min |
| [Docker](#docker) | Quick evaluation | 3 min |
| [Docker Compose](#docker-compose) | Full stack locally | 5 min |
| [Helm](#helm) | Kubernetes production | 10 min |

## What's Next?

After installation:

1. **[Configure integrations](configuration.md)** — Connect Kubernetes, metrics, and alerting
2. **[Run your first investigation](quickstart.md)** — Test with a sample alert
3. **[Set up Slack](../guides/slack-integration.md)** — Enable team notifications

## Need Help?

- 💬 [Slack Community](https://autosre.io/slack)
- 📖 [Troubleshooting Guide](../guides/troubleshooting.md)
- 🐛 [GitHub Issues](https://github.com/autosre/autosre/issues)
