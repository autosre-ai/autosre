# OpenSRE Friction-Free Installation Plan

## Goal: Match or beat `ollama launch hermes`

### Option 1: One-Line Install (Recommended)
```bash
curl -fsSL https://opensre.dev/install.sh | bash
```

What it does:
- Detects OS (macOS/Linux)
- Installs uv (fast Python)
- Creates isolated env
- Installs opensre
- Pulls default LLM model
- Prints `opensre demo` to run

### Option 2: Docker One-Liner
```bash
docker run -it --rm ghcr.io/srisainath/opensre demo
```

Includes:
- Ollama baked in (or connects to host)
- Pre-pulled llama3:8b
- Demo scenarios ready

### Option 3: pipx Install
```bash
pipx install opensre && opensre demo
```

### Option 4: Homebrew (macOS)
```bash
brew install opensre && opensre demo
```

---

## Implementation Tasks

### 1. Create install.sh
```bash
#!/bin/bash
set -e

echo "🚀 Installing OpenSRE..."

# Detect OS
OS=$(uname -s)

# Install uv if not present
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Install opensre
uv tool install opensre

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    if [ "$OS" = "Darwin" ]; then
        brew install ollama
    else
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
fi

# Pull default model
echo "🧠 Pulling llama3:8b..."
ollama pull llama3:8b

echo ""
echo "✅ OpenSRE installed!"
echo ""
echo "Run the demo:"
echo "  opensre demo"
echo ""
echo "Or investigate your cluster:"
echo "  opensre watch --namespace default"
```

### 2. Slim Dependencies
Move heavy deps to optional:
```toml
[project.optional-dependencies]
embeddings = ["chromadb", "sentence-transformers"]
full = ["opensre[embeddings,slack,mcp]"]
```

Core install should be <10 seconds.

### 3. Docker Image
```dockerfile
FROM python:3.12-slim
RUN pip install opensre
COPY --from=ollama/ollama /usr/bin/ollama /usr/bin/ollama
ENV OLLAMA_MODELS=/models
COPY models/llama3-8b /models/
ENTRYPOINT ["opensre"]
CMD ["demo"]
```

### 4. Auto-Detect LLM
```python
def get_llm():
    # Try in order:
    # 1. Local Ollama
    # 2. OpenAI API key in env
    # 3. Anthropic API key in env
    # 4. Prompt to install Ollama
```

### 5. Zero-Config Demo Mode
```bash
opensre demo  # Works immediately, no config needed
```

- Uses mock data if no cluster
- Uses Ollama if available, falls back to mock LLM
- Beautiful Rich output
- Interactive scenarios

---

## README Update

### Before (6 steps):
```bash
git clone https://github.com/srisainath/opensre.git
cd opensre
python -m venv .venv && source .venv/bin/activate
pip install -e .
ollama serve &
ollama pull llama3:8b
python demo.py
```

### After (1 step):
```bash
curl -fsSL https://opensre.dev/install.sh | bash && opensre demo
```

Or with Docker:
```bash
docker run -it ghcr.io/srisainath/opensre demo
```

---

## Competitive Positioning

| Feature | Hermes | OpenSRE |
|---------|--------|---------|
| Install | `ollama launch hermes` | `curl ... \| bash && opensre demo` |
| Focus | General AI agent | SRE/Incident Response |
| Integrations | Generic | Prometheus, K8s, PagerDuty |
| Runbooks | ❌ | ✅ |
| Human-in-loop | ❌ | ✅ |

**Tagline:** "Hermes is a general agent. OpenSRE is your on-call SRE."

---

## Priority Order

1. ⭐ `opensre demo` works with zero config (mock mode)
2. ⭐ Docker image with everything baked in
3. install.sh script
4. Slim core dependencies
5. pipx support
6. Homebrew formula (later)
