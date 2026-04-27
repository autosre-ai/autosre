# Example Configurations

This directory contains example configuration files for different deployment scenarios.

## Quick Start

```bash
# Copy the configuration that matches your setup
cp examples/configs/local-ollama.env .env

# Or for production
cp examples/configs/production.env .env
```

## Available Configurations

### `local-ollama.env`
Local development with Ollama for LLM inference. No cloud dependencies.

### `openai-cloud.env`
Production setup using OpenAI API. Suitable for most cloud deployments.

### `anthropic-cloud.env`
Production setup using Anthropic Claude. Better for complex reasoning tasks.

### `azure-enterprise.env`
Enterprise deployment with Azure OpenAI, full compliance features.

### `full-stack.env`
Complete configuration with all integrations enabled.

## Configuration Reference

See [docs/CONFIGURATION.md](../../docs/CONFIGURATION.md) for complete documentation.
