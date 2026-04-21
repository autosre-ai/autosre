# Metrics Instrumentation Status

**Date:** 2024-04-21  
**Status:** ✅ COMPLETE

## Summary

Successfully instrumented all bookstore services with Prometheus metrics.

## What Was Done

### Approach: Modified Inline Python + Nginx Exporter Sidecar

Since the bookstore services use inline Python code (embedded in deployment YAML), I:

1. **Modified the Python services** (catalog, checkout, payment) to:
   - Install `prometheus_client` at container startup via pip
   - Add Counter, Histogram, and Gauge metrics for HTTP requests
   - Expose `/metrics` endpoint on the same port (8080)

2. **Added nginx-prometheus-exporter sidecar** to frontend:
   - Enabled nginx stub_status
   - Added nginx-prometheus-exporter container exposing port 9113

3. **Created ServiceMonitors** for all services

4. **Instrumented fault injection services** (memory-leak variant with `memory_leaked_megabytes` metric)

### Files Created

```
~/clawd/projects/opensre/examples/bookstore/instrumented/
├── catalog-service.yaml              # Instrumented catalog service
├── checkout-service.yaml             # Instrumented checkout service
├── payment-service.yaml              # Instrumented payment service
├── frontend.yaml                     # Frontend with nginx-exporter sidecar
├── servicemonitors.yaml              # Prometheus ServiceMonitors
└── memory-leak-instrumented.yaml     # Memory leak fault with metrics
```

### Metrics Exposed

| Service | Port | Metrics |
|---------|------|---------|
| catalog-service | 8080 | `http_requests_total`, `http_request_duration_seconds`, `catalog_books_total`, `up` |
| checkout-service | 8080 | `http_requests_total`, `http_request_duration_seconds`, `checkout_orders_total`, `up` |
| payment-service | 8080 | `http_requests_total`, `http_request_duration_seconds`, `payment_transactions_total`, `payment_amount_total`, `up` |
| frontend | 9113 | nginx_* metrics (connections, requests, etc.) |
| catalog-service-memory-leak | 8080 | `http_requests_total`, `http_request_duration_seconds`, `memory_leaked_megabytes`, `up` |

## Verification

```bash
# Check targets in Prometheus (all showing UP)
curl -s --data-urlencode 'query=up{namespace="bookstore"}==1' http://localhost:9090/api/v1/query | jq -r '.data.result[] | .metric.service' | sort -u
# Output:
# catalog-service
# checkout-service
# frontend
# payment-service

# http_requests_total is being collected
curl -s --data-urlencode 'query=http_requests_total' http://localhost:9090/api/v1/query
```

### Current Status

- **catalog-service:** ✅ UP (2 pods)
- **checkout-service:** ✅ UP (2 pods)
- **payment-service:** ✅ UP (2 pods)  
- **frontend:** ✅ UP (2 pods)
- **catalog-service-memory-leak:** ✅ UP (2 pods)

## Applied Changes

All instrumented deployments have been applied:
```bash
kubectl apply -f ~/clawd/projects/opensre/examples/bookstore/instrumented/
```

## Notes

- Services install `prometheus_client` at startup (adds ~10-15s to boot time)
- Old pods may briefly show as "down" targets while Prometheus reconciles
- Services now have proper SLI metrics for building SLOs

## Next Steps

1. Define SLOs using these metrics (e.g., `rate(http_requests_total{status="200"}[5m]) / rate(http_requests_total[5m]) > 0.99`)
2. Create alerting rules based on SLOs
3. Build Grafana dashboards
