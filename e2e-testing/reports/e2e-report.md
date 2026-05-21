# AutoSRE E2E Test Report

**Date:** 2026-05-11 19:16:11  
**Cluster:** kind-autosre-e2e  
**App:** Bookstore (httpbin + postgres)

---

## Summary

| # | Scenario | Status | Detection Time | Root Cause |
|---|----------|--------|----------------|------------|
| 1 | Pod Failure / High Error Rate | ✅ DETECTED | 0.62s | ✅ |
| 2 | Resource Exhaustion / OOM | ✅ DETECTED | 0.31s | ✅ |
| 3 | Database Failure / Cascade | ✅ DETECTED | 0.54s | ✅ |
| 4 | Complete Outage / Scale Down | ✅ DETECTED | 0.35s | ✅ |
| 5 | Image Pull Failure | ✅ DETECTED | 0.67s | ✅ |
| 6 | Liveness Probe Failure | ✅ DETECTED | 2.52s | ✅ |

---

## Results: 6/6 scenarios detected successfully

### Scenario 1: Pod Failure / High Error Rate

- **Status:** ✅ DETECTED
- **Detection Time:** 0.62s
- **Hypothesis:** [Unhealthy] Readiness probe failed: Get "http://10.244.1.7:80/status/200": dial tcp 10.244.1.7:80: connect: conn

**Evidence:**
- [Unhealthy] Readiness probe failed: Get "http://10.244.1.7:80/status/200": dial tcp 10.244.1.7:80: connect: conn
- Pod bookstore-api-6bd554dbcd-gnjhh not ready
- Pod bookstore-api-6bd554dbcd-twlh8 not ready

### Scenario 2: Resource Exhaustion / OOM

- **Status:** ✅ DETECTED
- **Detection Time:** 0.31s
- **Hypothesis:** [Killing] Stopping container metrics

**Evidence:**
- [Killing] Stopping container metrics
- [Killing] Stopping container api
- [Killing] Stopping container metrics
- [Killing] Stopping container api

### Scenario 3: Database Failure / Cascade

- **Status:** ✅ DETECTED
- **Detection Time:** 0.54s
- **Hypothesis:** [Killing] Stopping container api

**Evidence:**
- [Killing] Stopping container api
- [Killing] Stopping container postgres
- [Killing] Stopping container metrics

### Scenario 4: Complete Outage / Scale Down

- **Status:** ✅ DETECTED
- **Detection Time:** 0.35s
- **Hypothesis:** Deployment scaled to 0 - service unavailable

**Evidence:**
- No available replicas - complete outage
- [Unhealthy] Readiness probe failed: Get "http://10.244.1.11:80/status/200": dial tcp 10.244.1.11:80: connect: co
- [Unhealthy] Readiness probe failed: Get "http://10.244.1.11:80/status/200": context deadline exceeded (Client.Ti
- [Killing] Stopping container api
- [Killing] Stopping container metrics
- [Killing] Stopping container metrics

### Scenario 5: Image Pull Failure

- **Status:** ✅ DETECTED
- **Detection Time:** 0.67s
- **Hypothesis:** [Killing] Stopping container api

**Evidence:**
- [Killing] Stopping container api
- [Killing] Stopping container metrics
- [Failed] Error: ErrImagePull
- [Failed] Failed to pull image "invalid-image:nonexistent": failed to pull and unpack image "docker.io/library
- [BackOff] Back-off pulling image "invalid-image:nonexistent"

### Scenario 6: Liveness Probe Failure

- **Status:** ✅ DETECTED
- **Detection Time:** 2.52s
- **Hypothesis:** [Unhealthy] Liveness probe failed: Get "http://10.244.2.27:80/nonexistent": dial tcp 10.244.2.27:80: connect: co

**Evidence:**
- [Unhealthy] Liveness probe failed: Get "http://10.244.2.27:80/nonexistent": dial tcp 10.244.2.27:80: connect: co
- [Killing] Container api failed liveness probe, will be restarted
- [Unhealthy] Readiness probe failed: Get "http://10.244.2.27:80/status/200": context deadline exceeded (Client.Ti
- [Killing] Stopping container api
- [Killing] Stopping container metrics

