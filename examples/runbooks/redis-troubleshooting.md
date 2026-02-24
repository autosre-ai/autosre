# Redis Connection Issues Runbook

## Symptoms
- Application logs showing "connection refused" to Redis
- Increased latency in services using Redis
- Timeout errors in dependent services

## Investigation Steps

### 1. Check Redis Pod Status
```bash
kubectl get pods -l app=redis -n <namespace>
```
Expected: All pods should be Running and Ready.

### 2. Check Redis Logs
```bash
kubectl logs -l app=redis -n <namespace> --tail=100
```
Look for:
- Out of memory errors
- Connection limit reached
- Cluster issues

### 3. Check Connection Count
```bash
kubectl exec -it <redis-pod> -- redis-cli INFO clients
```
- `connected_clients` should be below `maxclients`
- `blocked_clients` should be near 0

### 4. Check Memory Usage
```bash
kubectl exec -it <redis-pod> -- redis-cli INFO memory
```
- `used_memory_human` vs `maxmemory_human`
- Check `mem_fragmentation_ratio`

## Remediation

### Connection Pool Exhausted
1. Scale Redis replicas:
   ```bash
   kubectl scale deployment redis --replicas=3 -n <namespace>
   ```

2. Restart dependent services to reset connections:
   ```bash
   kubectl rollout restart deployment/<service> -n <namespace>
   ```

### Memory Issues
1. Check for large keys:
   ```bash
   kubectl exec -it <redis-pod> -- redis-cli --bigkeys
   ```

2. If memory full, consider:
   - Increasing memory limits
   - Setting TTLs on keys
   - Eviction policy adjustment

### Pod CrashLooping
1. Check pod events:
   ```bash
   kubectl describe pod <redis-pod> -n <namespace>
   ```

2. Check resource limits - may need more memory/CPU

## Prevention
- Set up alerts for Redis connection count > 80% of max
- Monitor memory usage trends
- Implement connection pooling in applications
