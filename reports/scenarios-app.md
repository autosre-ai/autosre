# Application Fault Scenarios - Progress Report

Generated: 2025-01-15

## Summary
**Total Application Fault Scenarios Created: 50**

All 50 application-level fault scenarios have been created as Kubernetes YAML deployments.

## Categories

### Database Issues (10 scenarios) ✅
| # | File | Description |
|---|------|-------------|
| 1 | `db-connection-pool-exhausted.yaml` | Max connections reached (95% exhaustion rate) |
| 2 | `db-slow-queries.yaml` | Queries taking 5-30s with 80% probability |
| 3 | `db-deadlock.yaml` | Transaction deadlocks (40% probability) |
| 4 | `db-connection-timeout.yaml` | 30s connection timeout (90% probability) |
| 5 | `db-authentication-failed.yaml` | Wrong credentials - auth failures |
| 6 | `db-schema-mismatch.yaml` | Missing columns/table structure errors |
| 7 | `db-replication-lag.yaml` | Read replicas 30s behind primary |
| 8 | `db-disk-full.yaml` | No space for writes (99.8% full) |
| 9 | `redis-connection-failed.yaml` | Cache unreachable with DB fallback |
| 10 | `redis-memory-full.yaml` | Cache eviction (90% miss rate) |

### HTTP/API Issues (10 scenarios) ✅
| # | File | Description |
|---|------|-------------|
| 11 | `http-500-errors.yaml` | Random internal server errors (60% rate) |
| 12 | `http-503-service-unavailable.yaml` | Load shedding (80% rate) |
| 13 | `http-429-rate-limited.yaml` | Rate limit exceeded (70% rate) |
| 14 | `http-timeout.yaml` | Requests hang 120s (70% probability) |
| 15 | `http-circuit-breaker-open.yaml` | Circuit tripped, failing fast |
| 16 | `api-response-malformed.yaml` | Invalid/corrupt JSON (60% rate) |
| 17 | `api-version-mismatch.yaml` | Deprecated endpoint (410 Gone) |
| 18 | `grpc-deadline-exceeded.yaml` | gRPC timeout (70% rate) |
| 19 | `websocket-disconnect.yaml` | Connection drops (50% rate) |
| 20 | `cors-blocked.yaml` | CORS policy blocking requests |

### Performance Issues (10 scenarios) ✅
| # | File | Description |
|---|------|-------------|
| 21 | `high-latency.yaml` | (pre-existing, enhanced) |
| 22 | `cpu-spike.yaml` | (pre-existing, enhanced) |
| 23 | `memory-pressure.yaml` | GC thrashing (40% pause probability) |
| 24 | `thread-pool-exhausted.yaml` | All worker threads busy (80% rate) |
| 25 | `connection-leak.yaml` | Connections not closed (30% leak rate) |
| 26 | `file-descriptor-exhaustion.yaml` | Too many open files |
| 27 | `disk-io-saturation.yaml` | Slow writes (70% saturation rate) |
| 28 | `network-bandwidth-saturated.yaml` | Throughput maxed (80% rate) |
| 29 | `cold-start-latency.yaml` | First 10 requests slow (5s delay) |
| 30 | `cache-miss-storm.yaml` | Cache invalidation (90% miss rate) |

### Business Logic Errors (10 scenarios) ✅
| # | File | Description |
|---|------|-------------|
| 31 | `payment-processing-failed.yaml` | Payment gateway errors (80% rate) |
| 32 | `inventory-sync-error.yaml` | Stock quantity mismatch (50% rate) |
| 33 | `order-validation-failed.yaml` | Bad order data (70% rate) |
| 34 | `user-auth-expired.yaml` | JWT token expired (80% rate) |
| 35 | `feature-flag-misconfigured.yaml` | Wrong flag state (60% rate) |
| 36 | `rate-limit-misconfigured.yaml` | Blocking legit users (5/min instead of 1000) |
| 37 | `data-corruption.yaml` | Inconsistent state (50% rate) |
| 38 | `cascade-failure.yaml` | One service takes down others |
| 39 | `retry-storm.yaml` | Exponential backoff failure |
| 40 | `idempotency-violation.yaml` | Duplicate processing (40% rate) |

### External Dependencies (10 scenarios) ✅
| # | File | Description |
|---|------|-------------|
| 41 | `third-party-api-down.yaml` | External service unavailable |
| 42 | `third-party-api-slow.yaml` | Degraded external service (8s latency) |
| 43 | `third-party-rate-limited.yaml` | Hit API quota |
| 44 | `cdn-failure.yaml` | Static assets unavailable |
| 45 | `email-service-down.yaml` | Notifications failing |
| 46 | `sms-gateway-error.yaml` | SMS delivery fails (80% rate) |
| 47 | `payment-gateway-timeout.yaml` | Payment processor slow (30s timeout) |
| 48 | `shipping-api-error.yaml` | Shipping calculation fails (70% rate) |
| 49 | `oauth-provider-down.yaml` | Login service unavailable |
| 50 | `webhook-delivery-failed.yaml` | Outbound webhooks failing (80% rate) |

## Implementation Details

Each scenario:
- Is a complete Kubernetes Deployment YAML
- Uses Python HTTP server for simulation
- Has configurable fault rates via environment variables
- Includes health/ready probes that pass (to keep pod running)
- Returns detailed JSON error responses with:
  - Error codes and messages
  - Contextual details
  - Troubleshooting suggestions
- Logs fault activity to stdout

## Usage

Deploy a fault scenario:
```bash
kubectl apply -f faults/db-connection-pool-exhausted.yaml
```

Remove the fault:
```bash
kubectl delete -f faults/db-connection-pool-exhausted.yaml
```

## Notes

- All scenarios are designed to be realistic and representative of actual production issues
- Fault rates and delays are configurable via environment variables
- Health probes are designed to pass so pods stay running while exhibiting faulty behavior
- JSON responses include enough detail for AI/SRE agents to diagnose the issue
