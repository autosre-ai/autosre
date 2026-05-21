#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Creating Kind cluster: autosre-e2e"

# Create data directory for persistence
mkdir -p ./data

# Delete existing cluster if present
kind delete cluster --name autosre-e2e 2>/dev/null || true

# Create cluster
kind create cluster --config kind-config.yaml

echo ""
echo "✅ Cluster created successfully!"
echo ""

# Show cluster info
kubectl cluster-info --context kind-autosre-e2e

echo ""
echo "📊 Nodes:"
kubectl get nodes
