# OpenSRE Runbooks Guide

Runbooks are your team's documented knowledge for handling incidents. OpenSRE uses them to provide context-aware recommendations.

## How OpenSRE Uses Runbooks

When investigating an issue, OpenSRE:

1. **Searches** runbooks for matching symptoms
2. **Extracts** relevant investigation steps
3. **Considers** documented root causes
4. **Recommends** remediation from proven solutions
5. **Links** relevant runbooks in output

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 OpenSRE Analysis                                        │
├─────────────────────────────────────────────────────────────┤
│  Root Cause: Memory leak in v2.3.2                          │
│                                                             │
│  📚 Relevant Runbook: memory-issues.md                      │
│  "Check for memory leaks after recent deployments..."       │
│                                                             │
│  ✅ Recommended (from runbook):                             │
│  kubectl rollout undo deployment/payment-service            │
└─────────────────────────────────────────────────────────────┘
```

---

## Runbook Format

### Basic Structure

```markdown
---
symptoms: keyword1, keyword2, keyword3
services: service-name, all
tags: category, severity
---

# Runbook Title

## Symptoms
- Observable symptom 1
- Observable symptom 2

## Investigation Steps

### 1. First check
```bash
command to run
```

### 2. Second check
```promql
prometheus query
```

## Root Causes

| Cause | Indicators | Resolution |
|-------|------------|------------|
| Cause 1 | What to look for | How to fix |
| Cause 2 | What to look for | How to fix |

## Remediation

### Immediate
1. First emergency step
2. Second emergency step

### Long-term
1. Permanent fix
2. Prevention measures

## Prevention
- How to avoid this in the future
```

### Frontmatter (YAML Header)

The YAML frontmatter enables semantic matching:

```yaml
---
# Keywords that trigger this runbook (comma-separated)
symptoms: high latency, slow response, timeout, p99, response time

# Services this applies to (or "all", "any")
services: api-gateway, checkout-service

# Categorical tags
tags: performance, network, database

# Optional: severity for prioritization
severity: high

# Optional: estimated time to resolve
estimated_time: 15m
---
```

---

## Directory Structure

```
runbooks/
├── high-latency.md         # Performance issues
├── memory-issues.md        # Memory/OOM problems
├── crashloop.md            # Pod restart loops
├── 5xx-errors.md           # HTTP errors
├── cpu-throttling.md       # CPU limits
├── disk-pressure.md        # Storage issues
├── network-issues.md       # Connectivity
├── database/
│   ├── postgres-issues.md
│   ├── redis-issues.md
│   └── connection-pool.md
└── services/
    ├── checkout-service.md
    └── payment-gateway.md
```

### Configuring Runbook Paths

```yaml
# config/agents.yaml
runbooks:
  directories:
    - ./runbooks           # Default location
    - /shared/runbooks     # Team shared runbooks
    - ./service-runbooks   # Service-specific
  
  patterns:
    - "*.md"
    - "*.yaml"
```

---

## Complete Example

```markdown
---
symptoms: high memory, OOMKilled, memory leak, out of memory, container killed
services: any
tags: memory, resources, oom
severity: high
---

# Memory Issues & OOMKilled

## Symptoms
- Pod status shows `OOMKilled`
- Container restarts with exit code 137
- Memory usage approaching limits
- Application slowdown before crash
- Alerts: `ContainerMemoryUsageHigh`, `OOMKilled`

## Investigation Steps

### 1. Check current memory usage

```bash
# View memory usage for pods in namespace
kubectl top pods -n <namespace>

# Check specific pod
kubectl top pod <pod-name> -n <namespace> --containers
```

### 2. Query memory trends

```promql
# Memory usage over time
container_memory_usage_bytes{namespace="<namespace>", pod=~"<pod-prefix>.*"}

# Memory vs limit (percentage)
container_memory_usage_bytes / container_spec_memory_limit_bytes * 100
```

### 3. Check for OOMKilled events

```bash
# Recent events
kubectl get events -n <namespace> --field-selector reason=OOMKilled

# Pod describe for exit codes
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Last State"
```

### 4. Review recent changes

```bash
# Check deployment history
kubectl rollout history deployment/<name> -n <namespace>

# Compare with previous version
kubectl rollout history deployment/<name> -n <namespace> --revision=<N>
```

## Root Causes

| Cause | Indicators | Check |
|-------|-----------|-------|
| **Memory leak** | Steady growth, crash after uptime | `kubectl top` over time |
| **Undersized limits** | Consistent OOM at same level | Compare usage to limits |
| **Traffic spike** | Correlates with request rate | Check request metrics |
| **Large payloads** | Specific endpoints affected | Check request sizes |
| **Cache growth** | In-memory cache unbounded | Application metrics |

## Remediation

### Immediate (Stop the Bleeding)

1. **Scale out** to distribute load:
   ```bash
   kubectl scale deployment/<name> --replicas=<n> -n <namespace>
   ```

2. **Rollback** if recent deploy caused issue:
   ```bash
   kubectl rollout undo deployment/<name> -n <namespace>
   ```

3. **Increase memory limit** temporarily:
   ```bash
   kubectl set resources deployment/<name> \
     --limits=memory=4Gi -n <namespace>
   ```

### For Memory Leaks

1. Enable heap profiling (Java):
   ```bash
   kubectl exec <pod> -- jmap -histo <pid> | head -20
   ```

2. Capture heap dump:
   ```bash
   kubectl exec <pod> -- jmap -dump:format=b,file=/tmp/heap.hprof <pid>
   kubectl cp <pod>:/tmp/heap.hprof ./heap.hprof
   ```

3. Analyze with profiler (MAT, VisualVM)

### For Undersized Limits

1. Review actual usage patterns
2. Set limits to 1.5x average + buffer for spikes
3. Consider Vertical Pod Autoscaler (VPA)

## Prevention

1. **Set resource requests and limits** on all containers
2. **Use memory profiling** in CI/CD pipeline
3. **Implement circuit breakers** for runaway requests
4. **Monitor memory trends** with alerting before OOM
5. **Load test** with production-like data volumes

## Related Runbooks

- [CPU Throttling](./cpu-throttling.md)
- [Pod CrashLoopBackOff](./crashloop.md)

## External Resources

- [Kubernetes Memory Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [JVM Heap Analysis Guide](https://example.com/jvm-heap)
```

---

## Best Practices

### 1. Use Specific Symptoms

```yaml
# Good - specific and searchable
symptoms: p99 latency spike, database connection timeout, postgres slow query

# Bad - too generic
symptoms: slow, error, problem
```

### 2. Include Real Commands

```markdown
## Investigation

### Check pod status
```bash
# ✅ Good - specific and copy-pasteable
kubectl get pods -n production -l app=payment-service -o wide

# ❌ Bad - vague
check the pods
```
```

### 3. Add Prometheus Queries

```markdown
### Check error rate
```promql
# Rate of 5xx errors over 5 minutes
sum(rate(http_requests_total{status=~"5..", service="payment"}[5m])) 
/ 
sum(rate(http_requests_total{service="payment"}[5m]))
```
```

### 4. Document Root Causes

Use tables for quick scanning:

```markdown
| Cause | Indicators | Resolution |
|-------|------------|------------|
| Database timeout | Error logs show "connection timeout" | Check DB health |
| Rate limiting | 429 responses spike | Increase limits or scale |
| Memory leak | Gradual increase until OOM | Rollback recent deploy |
```

### 5. Prioritize Remediation Steps

```markdown
## Remediation

### Immediate (< 5 min)
1. Scale out if load-related
2. Rollback if deploy-related

### Short-term (< 1 hour)
1. Increase resource limits
2. Enable debug logging

### Long-term (next sprint)
1. Fix underlying code issue
2. Add monitoring/alerting
```

### 6. Keep Runbooks Updated

- Review after every incident
- Add new failure modes
- Remove outdated information
- Track last-updated date

---

## Template

Copy this template for new runbooks:

```markdown
---
symptoms: 
services: 
tags: 
severity: 
---

# [Issue Name]

## Symptoms
- 

## Investigation Steps

### 1. Initial assessment
```bash
```

### 2. Check metrics
```promql
```

### 3. Review logs
```bash
```

## Root Causes

| Cause | Indicators | Resolution |
|-------|------------|------------|

## Remediation

### Immediate

### Long-term

## Prevention

## Related Runbooks

```

---

## Importing Existing Runbooks

### From Confluence

Export as markdown and add frontmatter:

```bash
# Add frontmatter to existing runbooks
for f in runbooks/*.md; do
  # Check if frontmatter exists
  if ! head -1 "$f" | grep -q "^---"; then
    echo "Adding frontmatter to $f"
    # Prepend minimal frontmatter
    echo -e "---\nsymptoms: \nservices: any\ntags: \n---\n$(cat $f)" > "$f"
  fi
done
```

### From YAML/JSON

OpenSRE supports YAML runbooks:

```yaml
# runbooks/pod-restart.yaml
metadata:
  symptoms: [pod restart, crashloop, backoff]
  services: [any]
  tags: [kubernetes, pods]

title: Pod Restart / CrashLoopBackOff

symptoms:
  - Pod shows CrashLoopBackOff status
  - Frequent restarts
  - Exit code 1 or 137

investigation:
  - step: Check pod status
    command: kubectl get pods -n ${namespace}
  - step: Check events
    command: kubectl describe pod ${pod} -n ${namespace}
  - step: Check logs
    command: kubectl logs ${pod} -n ${namespace} --previous

root_causes:
  - name: Application crash
    indicators: Exit code 1, stack trace in logs
    resolution: Fix application bug, rollback
  - name: OOMKilled
    indicators: Exit code 137, OOMKilled in events
    resolution: Increase memory limits

remediation:
  immediate:
    - Rollback if recent deploy
    - Scale down to reduce load
  long_term:
    - Fix underlying issue
    - Add health checks
```
