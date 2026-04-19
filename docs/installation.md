# Installation

This guide covers all installation methods for OpenSRE.

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
pip install opensre

# Verify installation
opensre --version
```

### Method 2: pipx (Isolated)

```bash
# Install pipx if needed
pip install pipx
pipx ensurepath

# Install OpenSRE
pipx install opensre

# Verify
opensre --version
```

### Method 3: From Source

```bash
# Clone repository
git clone https://github.com/srisainath/opensre.git
cd opensre

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
docker pull ghcr.io/srisainath/opensre:latest

# Run
docker run -d \
  --name opensre \
  -p 8000:8000 \
  -e OPENSRE_PROMETHEUS_URL=http://prometheus:9090 \
  -e OPENSRE_LLM_PROVIDER=ollama \
  -e OPENSRE_OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.kube/config:/app/.kube/config:ro \
  ghcr.io/srisainath/opensre:latest
```

### Method 5: Helm (Kubernetes)

```bash
# Add Helm repository
helm repo add opensre https://srisainath.github.io/opensre
helm repo update

# Install
helm install opensre opensre/opensre \
  --namespace opensre \
  --create-namespace \
  --values values.yaml
```

See [Deployment Guide](deployment.md) for Kubernetes configuration.

## Post-Installation

### 1. Verify Installation

```bash
opensre --version
opensre status
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
nano .env
```

### 3. Install Skills

```bash
# List available skills
opensre skill list

# Install skills you need
opensre skill install prometheus kubernetes slack
```

### 4. Test Connection

```bash
# Test Prometheus
opensre test prometheus

# Test Kubernetes
opensre test kubernetes

# Test LLM
opensre test llm
```

## Upgrading

### pip

```bash
pip install --upgrade opensre
```

### Docker

```bash
docker pull ghcr.io/srisainath/opensre:latest
docker-compose up -d
```

### Helm

```bash
helm repo update
helm upgrade opensre opensre/opensre --namespace opensre
```

## Uninstalling

### pip

```bash
pip uninstall opensre
```

### Docker

```bash
docker stop opensre
docker rm opensre
docker rmi ghcr.io/srisainath/opensre:latest
```

### Helm

```bash
helm uninstall opensre --namespace opensre
kubectl delete namespace opensre
```

## Troubleshooting Installation

### Python Version Issues

```bash
# Check Python version
python --version

# Use specific Python version
python3.11 -m pip install opensre
```

### Permission Issues

```bash
# Install to user directory
pip install --user opensre

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install opensre
```

### Missing Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev build-essential

# macOS
xcode-select --install

# Then reinstall
pip install opensre
```

### SSL Certificate Issues

```bash
# Update certificates
pip install --upgrade certifi

# Or skip verification (not recommended for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org opensre
```

## Next Steps

- **[Getting Started](getting-started.md)** — First-time setup
- **[Configuration](configuration.md)** — Configure OpenSRE
- **[Deployment](deployment.md)** — Production deployment
