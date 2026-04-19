# OpenSRE Quickstart Guide

Get up and running with OpenSRE in 5 minutes.

## Prerequisites

Before starting, ensure you have:

- **Python 3.11+** installed
- **Kubernetes cluster** access (via `kubectl`)
- **Prometheus** instance running
- **Ollama** (optional, for local LLM) or API keys for OpenAI/Anthropic

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/srisainath/opensre.git
cd opensre

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install OpenSRE
pip install -e .
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your settings
nano .env  # or your preferred editor
```

**Minimum required settings:**

```bash
# LLM (choose one)
OPENSRE_LLM_PROVIDER=ollama
OPENSRE_OLLAMA_MODEL=llama3.1:8b

# Infrastructure
OPENSRE_PROMETHEUS_URL=http://localhost:9090
```

### 3. Verify Setup

```bash
# Check system status
opensre status
```

You should see:

```
┌─────────────────────────────────────┐
│         OpenSRE Status              │
├──────────────┬──────────────────────┤
│ Prometheus   │ ✅ Connected         │
│ Kubernetes   │ ✅ Connected         │
│ LLM (Ollama) │ ✅ Connected         │
│ Slack        │ ⚪ Not configured    │
└──────────────┴──────────────────────┘
```

## Your First Investigation

### Option 1: CLI Investigation

```bash
# Investigate an issue
opensre investigate "High memory usage on payment-service"
```

OpenSRE will:
1. Query Prometheus for metrics
2. Check Kubernetes pod status
3. Look for relevant events
4. Analyze with LLM
5. Suggest remediation actions

### Option 2: Web UI

```bash
# Start the web server
opensre ui

# Open http://localhost:8080 in your browser
```

### Option 3: API Request

```bash
curl -X POST http://localhost:8080/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"issue": "Checkout service 500 errors", "namespace": "production"}'
```

## Example Output

```
🔍 Investigation: High memory usage on payment-service

📊 Observations:
  • Memory at 4.2GB (92% of 4.5GB limit)
  • Pod restarted 3 times in last hour (OOMKilled)
  • Deploy payment-v2.3.2 rolled out 2 hours ago
  • No similar memory issues before v2.3.2

🎯 Root Cause (confidence: 87%)
   Memory leak introduced in v2.3.2 causing OOM restarts

✅ Recommended Actions:
  [1] 🟡 Rollback deployment: kubectl rollout undo deployment/payment-service
  [2] 🟢 Get pod logs: kubectl logs payment-service-xxx --previous

Would you like to execute action [1]? (y/n):
```

## Next Steps

1. **Set up Slack Integration** — Get investigations delivered to your #incidents channel
   - See [Slack Setup Guide](./SLACK_SETUP.md)

2. **Add Your Runbooks** — Help OpenSRE make better recommendations
   - See [Runbooks Guide](./RUNBOOKS.md)

3. **Connect to Alertmanager** — Trigger automatic investigations on alerts
   - See [Integrations](./INTEGRATIONS.md)

4. **Deploy to Production** — Run OpenSRE in your cluster
   - See [Deployment Guide](./DEPLOYMENT.md)

## Quick Docker Setup

Don't want to install locally? Use Docker:

```bash
# Start OpenSRE with Ollama and Prometheus
docker-compose up -d

# Wait for Ollama to download model (first run only)
docker-compose logs -f ollama

# Open http://localhost:8080
```

## Troubleshooting

### "LLM not responding"

If using Ollama, ensure it's running:

```bash
ollama serve
ollama pull llama3.1:8b
```

### "Cannot connect to Kubernetes"

Check your kubeconfig:

```bash
kubectl cluster-info
kubectl config current-context
```

### "Prometheus connection refused"

Verify Prometheus URL:

```bash
curl http://localhost:9090/api/v1/status/config
```

For more issues, see [Troubleshooting](./TROUBLESHOOTING.md).

---

**Need help?** Open an issue on [GitHub](https://github.com/srisainath/opensre/issues).
