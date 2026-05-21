#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Adding Helm repositories..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo ""
echo "🔧 Creating monitoring namespace..."
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "📊 Installing kube-prometheus-stack..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values prometheus-values.yaml \
  --wait \
  --timeout 10m

echo ""
echo "📝 Installing Loki stack..."
helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --values loki-values.yaml \
  --wait \
  --timeout 5m

echo ""
echo "✅ Observability stack installed!"
echo ""
echo "📊 Services:"
kubectl get svc -n monitoring

echo ""
echo "🔗 Access URLs:"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo ""
echo "⏳ Waiting for all pods to be ready..."
kubectl wait --for=condition=Ready pods --all -n monitoring --timeout=300s || true

echo ""
echo "📦 Pod Status:"
kubectl get pods -n monitoring
