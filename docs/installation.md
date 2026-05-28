# Installation

This guide covers all installation methods for AutoSRE.

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.11+ | 3.12+ |
| Memory | 512 MB | 2 GB |
| Disk | 100 MB | 500 MB |

### Dependencies

- **Prometheus** — For metrics collection
- **Kubernetes** — For container orchestration (optional)
- **Slack** — For notifications (optional)
- **LLM Provider** — Ollama, OpenAI, or Anthropic

## Installation Methods

### Method 1: pip (Recommended)

```bash
# Install from PyPI
pip install autosre-ai

# Verify installation
autosre --version
```

### Method 2: pipx (Isolated)

```bash
# Install pipx if needed
pip install pipx
pipx ensurepath

# Install AutoSRE
pipx install autosre-ai

# Verify
autosre --version
```

### Method 3: From Source

```bash
# Clone repository
git clone https://github.com/autosre-ai/autosre.git
cd autosre

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install in editable mode
pip install -e .

# Install dev dependencies (optional)
pip install -e ".[dev]"
```

### Method 4: Docker

```bash
# Pull image
docker pull ghcr.io/autosre-ai/autosre:latest

# Run
docker run -d \
  --name autosre \
  -p 8000:8000 \
  -e OPENSRE_PROMETHEUS_URL=http://prometheus:9090 \
  -e OPENSRE_LLM_PROVIDER=ollama \
  -e OPENSRE_OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.kube/config:/app/.kube/config:ro \
  ghcr.io/autosre-ai/autosre:latest
```

### Method 5: Helm (Kubernetes)

```bash
# Add Helm repository
helm repo add autosre https://autosre-ai.github.io/autosre
helm repo update

# Install
helm install autosre autosre/autosre \
  --namespace autosre \
  --create-namespace \
  --values values.yaml
```

See [Deployment Guide](deployment.md) for Kubernetes configuration.

## Post-Installation

### 1. Verify Installation

```bash
autosre --version
autosre status
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
nano .env
```

### 3. Run Doctor Check

```bash
# Check all connections
autosre doctor

# Test model connection
autosre model test
```

## Upgrading

### pip

```bash
pip install --upgrade autosre-ai
```

### Docker

```bash
docker pull ghcr.io/autosre-ai/autosre:latest
docker-compose up -d
```

### Helm

```bash
helm repo update
helm upgrade autosre autosre/autosre --namespace autosre
```

## Uninstalling

### pip

```bash
pip uninstall autosre-ai
```

### Docker

```bash
docker stop autosre
docker rm autosre
docker rmi ghcr.io/autosre-ai/autosre:latest
```

### Helm

```bash
helm uninstall autosre --namespace autosre
kubectl delete namespace autosre
```

## Troubleshooting Installation

### Python Version Issues

```bash
# Check Python version
python --version

# Use specific Python version
python3.11 -m pip install autosre-ai
```

### Permission Issues

```bash
# Install to user directory
pip install --user autosre-ai

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install autosre-ai
```

### Missing Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev build-essential

# macOS
xcode-select --install

# Then reinstall
pip install autosre-ai
```

### SSL Certificate Issues

```bash
# Update certificates
pip install --upgrade certifi

# Or skip verification (not recommended for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org autosre-ai
```

## Next Steps

- **[Getting Started](getting-started.md)** — First-time setup
- **[Configuration](configuration.md)** — Configure AutoSRE
- **[Deployment](deployment.md)** — Production deployment
