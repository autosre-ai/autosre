#!/bin/bash
# OpenSRE Quick Install
# curl -fsSL https://opensre.dev/install.sh | bash

set -e

REPO="srisainath/opensre"
MODEL="opensre"

echo "🚀 Installing OpenSRE..."
echo ""

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "📦 Ollama not found. Installing..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "🔄 Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 2
fi

# Pull base model if needed
if ! ollama list | grep -q "llama3.1:8b"; then
    echo "📥 Pulling llama3.1:8b (this may take a few minutes)..."
    ollama pull llama3.1:8b
fi

# Download Modelfile
echo "📄 Downloading OpenSRE model..."
TMPDIR=$(mktemp -d)
curl -fsSL "https://raw.githubusercontent.com/$REPO/main/ollama/Modelfile" -o "$TMPDIR/Modelfile"

# Create OpenSRE model
echo "🔨 Building opensre model..."
ollama create opensre -f "$TMPDIR/Modelfile"

# Cleanup
rm -rf "$TMPDIR"

echo ""
echo "✅ OpenSRE installed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Try it now:"
echo ""
echo "    ollama run opensre"
echo ""
echo "  Then ask:"
echo ""
echo "    Investigate high latency on checkout-service"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📖 Docs: https://opensre.dev"
echo "💬 Discord: https://discord.gg/opensre"
echo ""
