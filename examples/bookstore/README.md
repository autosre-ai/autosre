# Bookstore Demo Application for OpenSRE

A simple microservices bookstore application for testing OpenSRE fault detection and investigation capabilities.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Frontend   │────▶│  Catalog Service │────▶│      Redis       │
│   (nginx)    │     │    (Python)      │     │   (Database)     │
└──────────────┘     └──────────────────┘     └──────────────────┘
       │
       ├────────────▶┌──────────────────┐
       │             │ Checkout Service │
       │             │    (Python)      │
       │             └──────────────────┘
       │                     │
       └────────────▶┌──────────────────┐
                     │ Payment Service  │
                     │    (Python)      │
                     └──────────────────┘
```

## Services

| Service | Replicas | Port | Description |
|---------|----------|------|-------------|
| frontend | 2 | 80 | nginx serving static HTML |
| catalog-service | 2 | 8080 | Returns book catalog |
| checkout-service | 1 | 8080 | Processes checkout orders |
| payment-service | 1 | 8080 | Payment processing |
| redis | 1 | 6379 | Session/cache storage |

## Deployment

```bash
# Deploy the bookstore
kubectl apply -f examples/bookstore/

# Verify all pods are running
kubectl get pods -n bookstore

# Wait for ready
kubectl wait --for=condition=ready pod --all -n bookstore --timeout=120s
```

## Fault Injection Scenarios

### 1. Memory Leak (`faults/memory-leak.yaml`)
Patches `catalog-service` to leak ~1MB every 5 seconds until OOM.

```bash
kubectl apply -f examples/bookstore/faults/memory-leak.yaml

# Test with OpenSRE
opensre investigate "high memory usage in bookstore" --namespace bookstore
```

### 2. High Latency (`faults/high-latency.yaml`)
Patches `checkout-service` to add 3-15 second delays to all requests.

```bash
kubectl apply -f examples/bookstore/faults/high-latency.yaml

# Test with OpenSRE
opensre investigate "slow response times in checkout" --namespace bookstore
```

### 3. Crash Loop (`faults/crash-loop.yaml`)
Patches `payment-service` to crash every 10-30 seconds.

```bash
kubectl apply -f examples/bookstore/faults/crash-loop.yaml

# Test with OpenSRE
opensre investigate "payment service keeps restarting" --namespace bookstore
```

### 4. OOM Kill (`faults/oom-kill.yaml`)
Patches `catalog-service` to immediately allocate memory until OOMKilled.

```bash
kubectl apply -f examples/bookstore/faults/oom-kill.yaml

# Test with OpenSRE
opensre investigate "catalog pods getting OOMKilled" --namespace bookstore
```

### 5. CPU Spike (`faults/cpu-spike.yaml`)
Patches `frontend` to burn CPU cycles aggressively.

```bash
kubectl apply -f examples/bookstore/faults/cpu-spike.yaml

# Test with OpenSRE
opensre investigate "high CPU in frontend pods" --namespace bookstore
```

## Recovery

To restore healthy services after fault injection:

```bash
# Restore all original deployments
kubectl apply -f examples/bookstore/catalog-service.yaml
kubectl apply -f examples/bookstore/checkout-service.yaml
kubectl apply -f examples/bookstore/payment-service.yaml
kubectl apply -f examples/bookstore/frontend.yaml

# Or delete and redeploy
kubectl delete namespace bookstore
kubectl apply -f examples/bookstore/
```

## Cleanup

```bash
kubectl delete namespace bookstore
```
