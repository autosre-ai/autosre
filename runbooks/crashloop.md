---
symptoms: CrashLoopBackOff, container crash, restart loop, pod restarting, exit code
services: any
tags: crash, restart, failure, crashloop, backoff
---

# CrashLoopBackOff

## Symptoms
- Pod status shows `CrashLoopBackOff`
- High restart count in `kubectl get pods`
- Container exits immediately or shortly after starting
- Exponential backoff delay between restarts

## Investigation Steps

### 1. Check pod events and status
```bash
kubectl describe pod <pod> -n <namespace>
kubectl get pod <pod> -o yaml | grep -A20 "containerStatuses"
```

### 2. Check container logs (including previous instance)
```bash
kubectl logs <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous
```

### 3. Check exit code
```bash
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
```

### 4. Check if init containers are failing
```bash
kubectl get pod <pod> -o jsonpath='{.status.initContainerStatuses}'
```

## Common Exit Codes

| Exit Code | Signal | Meaning | Common Cause |
|-----------|--------|---------|--------------|
| 0 | - | Success | Container finished (wrong for long-running) |
| 1 | - | Application error | Code bug, unhandled exception |
| 126 | - | Command not executable | Permission issue, wrong binary |
| 127 | - | Command not found | Missing binary, bad entrypoint |
| 137 | SIGKILL (9) | OOMKilled | Memory limit exceeded |
| 139 | SIGSEGV (11) | Segmentation fault | Native code crash |
| 143 | SIGTERM (15) | Graceful shutdown timeout | Slow shutdown handler |

## Root Causes by Category

### Configuration Issues
- Missing or invalid environment variables
- ConfigMap/Secret not mounted or incorrect
- Invalid command arguments
- Missing dependencies

### Resource Issues
- OOMKilled (exit 137) - memory limits too low
- Liveness probe failing - probe misconfigured or app too slow

### Application Issues
- Unhandled exceptions during startup
- Failed database/service connections
- Invalid application configuration
- Missing required files

### Infrastructure Issues
- Image pull failures
- Volume mount failures
- DNS resolution failures
- Network policy blocking required connections

## Remediation

### For exit code 1 (application error)
1. Check logs for stack trace: `kubectl logs <pod> --previous`
2. Verify environment variables: `kubectl exec <pod> -- env`
3. Check ConfigMaps/Secrets are mounted correctly
4. Verify database/service connectivity

### For exit code 137 (OOMKilled)
1. Increase memory limits
2. Check for memory leaks
3. See [memory-issues.md](./memory-issues.md) runbook

### For exit code 139 (segfault)
1. Check for native library issues
2. Verify image is built for correct architecture (amd64 vs arm64)
3. Check for corrupted container image

### For exit code 143 (SIGTERM)
1. Increase `terminationGracePeriodSeconds`
2. Implement proper shutdown handler
3. Check for slow cleanup operations

### For command not found (127)
```bash
# Verify entrypoint
kubectl run debug --rm -it --image=<image> -- /bin/sh
which <expected-binary>
```

## Prevention
1. Add proper health checks (readiness/liveness probes)
2. Implement graceful shutdown handling
3. Use init containers for dependency checks
4. Set appropriate resource limits
5. Use PodDisruptionBudgets for availability
