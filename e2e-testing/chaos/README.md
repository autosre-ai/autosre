# Chaos Testing for AutoSRE E2E

This directory contains chaos injection scenarios for testing AutoSRE's detection and diagnosis capabilities.

## Quick Start

```bash
# Run a scenario
./run-scenario.sh 1              # High error rate
./run-scenario.sh 2              # OOM kill
./run-scenario.sh 3              # DB connection exhaustion
./run-scenario.sh 4              # Cascade failure
./run-scenario.sh 5              # Latency spike
./run-scenario.sh 6              # CPU throttling

# With options
./run-scenario.sh 1 --trigger-autosre    # Also trigger AutoSRE investigation
./run-scenario.sh 3 --no-wait            # Skip metrics accumulation wait
./run-scenario.sh 5 --wait 60            # Custom wait time

# Clean up
./reset-all.sh
```

## Directory Structure

```
chaos/
├── README.md                      # This file
├── run-scenario.sh                # Main test runner
├── reset-all.sh                   # Cleanup script
├── expected-outcomes.yaml         # What AutoSRE should detect
└── scenarios/
    ├── scenario-1-high-error-rate.sh
    ├── scenario-2-oom-kill.sh
    ├── scenario-3-db-connection-exhaustion.sh
    ├── scenario-4-cascade-failure.sh
    ├── scenario-5-latency-spike.sh
    └── scenario-6-cpu-throttling.sh
```

## Scenarios Overview

| # | Name | Chaos Type | Duration | Key Detection |
|---|------|------------|----------|---------------|
| 1 | High Error Rate | Error injection | ~30s | 5xx spike |
| 2 | OOM Kill | Memory exhaustion | 1-3min | OOMKilled event |
| 3 | DB Connection Exhaustion | Pool saturation | Immediate | Timeouts |
| 4 | Cascade Failure | Dependency outage | Until recovery | Root cause attribution |
| 5 | Latency Spike | Latency injection | Until reset | P99 latency |
| 6 | CPU Throttling | CPU stress | Until reset | Throttling metrics |

## Prerequisites

- Kubernetes cluster with bookstore namespace deployed
- bookstore-api with chaos endpoints enabled (`/chaos/*`)
- kubectl configured and authenticated
- (Optional) AutoSRE CLI installed for `--trigger-autosre`

## Environment Variables

```bash
export NAMESPACE=bookstore           # K8s namespace (default: bookstore)
export API_HOST=localhost:8080       # API endpoint (default: localhost:8080)
export ERROR_RATE=0.5                # For scenario 1 (default: 0.5)
export LATENCY_MS=2000               # For scenario 5 (default: 2000)
export WATCH_TIMEOUT=120             # For scenario 2 (default: 120)
```

## Expected Outcomes

See `expected-outcomes.yaml` for detailed documentation of:
- What signals AutoSRE should detect
- Expected diagnosis and root cause
- Recommended actions
- Success criteria for each scenario

## Safety Notes

- **Scenario 4** (Cascade Failure) deletes postgres pods - ensure auto-recovery is working
- Always run `reset-all.sh` after testing
- Monitor your cluster during chaos injection
- Consider running in a test/staging environment first
