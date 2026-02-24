# Pod CrashLoopBackOff Troubleshooting Runbook

## Symptoms
- Pods repeatedly restarting
- Status shows CrashLoopBackOff or Error
- Service unavailability

## Investigation Steps

### 1. Get Pod Status
```bash
kubectl get pods -l app=<service> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```

### 2. Check Container Logs
```bash
# Current logs
kubectl logs <pod-name> -n <namespace>

# Previous container logs (if restarted)
kubectl logs <pod-name> -n <namespace> --previous
```

### 3. Check Events
```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>
```

## Common Causes

### Application Error
**Symptoms**: Exception in logs, non-zero exit code

**Fix**:
1. Check application logs for stack trace
2. Rollback to last known good version:
   ```bash
   kubectl rollout undo deployment/<service> -n <namespace>
   ```

### OOMKilled (Out of Memory)
**Symptoms**: OOMKilled in pod events, exit code 137

**Fix**:
1. Increase memory limit:
   ```bash
   kubectl patch deployment <service> -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
   ```
2. Investigate memory leak in application

### Liveness Probe Failure
**Symptoms**: "Liveness probe failed" in events

**Fix**:
1. Check if probe endpoint is responding
2. Increase probe timeout/threshold:
   ```yaml
   livenessProbe:
     httpGet:
       path: /health
       port: 8080
     initialDelaySeconds: 30
     periodSeconds: 10
     failureThreshold: 5
   ```

### Missing ConfigMap/Secret
**Symptoms**: "configmap not found" or "secret not found" in events

**Fix**:
1. Verify ConfigMap/Secret exists:
   ```bash
   kubectl get configmaps,secrets -n <namespace>
   ```
2. Create missing resource or fix reference

### Image Pull Error
**Symptoms**: ImagePullBackOff, ErrImagePull

**Fix**:
1. Verify image exists and tag is correct
2. Check image pull secrets:
   ```bash
   kubectl get secrets -n <namespace> | grep docker
   ```

### Resource Limits Too Low
**Symptoms**: Container killed immediately, very short run time

**Fix**:
1. Review and increase resource limits
2. Check actual resource usage from metrics

## Quick Fixes

### Restart Deployment
```bash
kubectl rollout restart deployment/<service> -n <namespace>
```

### Scale Down and Up
```bash
kubectl scale deployment/<service> --replicas=0 -n <namespace>
kubectl scale deployment/<service> --replicas=3 -n <namespace>
```

### Force Delete Stuck Pod
```bash
kubectl delete pod <pod-name> -n <namespace> --force --grace-period=0
```

## Prevention
- Set appropriate resource requests and limits
- Use proper health checks
- Implement graceful shutdown handling
- Monitor container restart counts
