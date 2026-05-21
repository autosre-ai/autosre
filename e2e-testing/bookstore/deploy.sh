#!/bin/bash
# Deploy bookstore app to Kind cluster

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Docker image ==="
cd api
docker build -t bookstore-api:latest .
cd ..

echo "=== Loading image into Kind ==="
kind load docker-image bookstore-api:latest --name autosre 2>/dev/null || \
kind load docker-image bookstore-api:latest 2>/dev/null || \
echo "Warning: Could not load into Kind (cluster may not exist yet)"

echo "=== Applying Kubernetes manifests ==="
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

echo "=== Waiting for PostgreSQL to be ready ==="
kubectl wait --for=condition=ready pod -l app=bookstore-postgres -n bookstore --timeout=120s

echo "=== Deploying API ==="
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml

echo "=== Applying ServiceMonitor (if CRD exists) ==="
kubectl apply -f k8s/api-servicemonitor.yaml 2>/dev/null || \
echo "ServiceMonitor CRD not found (Prometheus Operator not installed)"

echo "=== Waiting for API to be ready ==="
kubectl wait --for=condition=ready pod -l app=bookstore-api -n bookstore --timeout=120s

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To access the API:"
echo "  kubectl port-forward svc/bookstore-api 8080:80 -n bookstore"
echo ""
echo "Then test with:"
echo "  curl http://localhost:8080/health"
echo "  curl http://localhost:8080/books"
echo "  curl http://localhost:8080/metrics"
echo ""
echo "Chaos endpoints:"
echo "  curl -X POST 'http://localhost:8080/chaos/error-rate?rate=0.5'"
echo "  curl -X POST 'http://localhost:8080/chaos/latency?ms=2000'"
echo "  curl -X POST http://localhost:8080/chaos/memory-leak"
echo "  curl -X POST http://localhost:8080/chaos/reset"
echo "  curl http://localhost:8080/chaos/status"
