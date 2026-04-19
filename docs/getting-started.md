# Getting Started with OpenSRE

This guide will help you get OpenSRE running in under 5 minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** — [Download Python](https://www.python.org/downloads/)
- **Kubernetes cluster** — Local (minikube, kind) or remote
- **Prometheus** — Running and accessible
- **Slack workspace** — For notifications (optional but recommended)

## Quick Installation

### Option 1: pip (Recommended)

```bash
pip install opensre
```

### Option 2: From Source

```bash
git clone https://github.com/srisainath/opensre.git
cd opensre
pip install -e .
```

## Configuration

### 1. Set Environment Variables

```bash
# Create config from template
cp .env.example .env

# Or set directly
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
export OPENSRE_KUBECONFIG=~/.kube/config
```

### 2. Choose Your LLM

**Option A: Local with Ollama (Recommended for Privacy)**

```bash
# Install Ollama: https://ollama.ai
ollama pull llama3.1:8b

export OPENSRE_LLM_PROVIDER=ollama
export OPENSRE_OLLAMA_MODEL=llama3.1:8b
```

**Option B: OpenAI**

```bash
export OPENSRE_LLM_PROVIDER=openai
export OPENSRE_OPENAI_API_KEY=sk-your-key
export OPENSRE_OPENAI_MODEL=gpt-4o
```

**Option C: Anthropic**

```bash
export OPENSRE_LLM_PROVIDER=anthropic
export OPENSRE_ANTHROPIC_API_KEY=sk-ant-your-key
export OPENSRE_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 3. Optional: Slack Integration

```bash
export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
export OPENSRE_SLACK_CHANNEL=#incidents
```

## Verify Installation

```bash
# Check OpenSRE is installed
opensre --version

# Check system status
opensre status
```

Expected output:

```
OpenSRE v0.1.0

✓ Prometheus    http://prometheus:9090    Connected
✓ Kubernetes    ~/.kube/config            Connected (3 nodes)
✓ LLM           ollama/llama3.1:8b        Ready
✓ Slack         #incidents                Connected

Ready to investigate incidents!
```

## Your First Investigation

### Manual Investigation

```bash
opensre investigate "high error rate on checkout service"
```

OpenSRE will:
1. Query Prometheus for relevant metrics
2. Check Kubernetes for pod health and events
3. Look at recent deployments
4. Correlate signals to find root cause
5. Output analysis and recommendations

### Watch Mode (Daemon)

```bash
# Start daemon to watch for alerts
opensre start

# Or run in foreground
opensre start --foreground
```

Configure Alertmanager to send webhooks to `http://localhost:8000/webhook/alertmanager`.

## Example Output

```
╭────────────────────────────────────────────────────────────────╮
│                  🔍 OpenSRE Investigation                       │
├────────────────────────────────────────────────────────────────┤
│ Alert: checkout-service high error rate                        │
│ Time: 2024-03-15 03:02:14                                      │
│                                                                │
│ 📊 Observations:                                               │
│ • Error rate: 0.1% → 8.3% (started 12m ago)                    │
│ • Affected endpoint: /api/v1/checkout/payment                  │
│ • 3 pods showing OOMKilled restarts                            │
│ • Deployment v2.4.1 rolled out 15m ago                         │
│                                                                │
│ 🎯 Root Cause (Confidence: 94%):                               │
│ Memory leak in checkout-service v2.4.1                         │
│ Connection pool not releasing connections properly             │
│                                                                │
│ ✅ Recommended Actions:                                        │
│ 1. Rollback to v2.4.0 (immediate)                              │
│ 2. Scale replicas 3 → 5 (temporary mitigation)                 │
│                                                                │
│ 📚 Related Runbook: memory-leak-remediation.md                 │
╰────────────────────────────────────────────────────────────────╯
```

## Next Steps

- **[Installation Guide](installation.md)** — Detailed installation options
- **[Configuration](configuration.md)** — All configuration options
- **[Skills Overview](skills/overview.md)** — Extend OpenSRE with skills
- **[Writing Agents](agents/writing-agents.md)** — Create custom automation
- **[Deployment](deployment.md)** — Production deployment guide

## Need Help?

- **GitHub Issues**: [Report bugs](https://github.com/srisainath/opensre/issues)
- **Discussions**: [Ask questions](https://github.com/srisainath/opensre/discussions)
- **Discord**: [Join community](https://discord.gg/opensre)
