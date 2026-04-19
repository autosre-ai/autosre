---
symptoms: disk pressure, DiskPressure, disk full, no space left, volume full, ephemeral storage
services: any
tags: disk, storage, volume, space, pressure
---

# Disk Pressure / Storage Issues

## Symptoms
- Node condition `DiskPressure: True`
- Pod evictions due to disk pressure
- "No space left on device" errors
- Failed writes to volumes
- Pod scheduling failures (insufficient ephemeral storage)

## Investigation Steps

### 1. Check node disk pressure
```bash
kubectl describe node <node> | grep -A5 "Conditions"
kubectl get nodes -o custom-columns=NAME:.metadata.name,DISK_PRESSURE:.status.conditions[?(@.type=="DiskPressure")].status
```

### 2. Check node disk usage
```bash
# SSH to node or use debug pod
kubectl debug node/<node> -it --image=busybox -- df -h
```

### 3. Check pod ephemeral storage
```bash
kubectl describe pod <pod> | grep -A10 "ephemeral-storage"

# Get ephemeral storage usage (if metrics available)
kubectl get --raw /api/v1/nodes/<node>/proxy/stats/summary | jq '.pods[] | select(.podRef.name=="<pod>") | .ephemeralStorage'
```

### 4. Check PVC usage
```bash
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>

# Check actual usage in pod
kubectl exec <pod> -n <namespace> -- df -h /path/to/volume
```

### 5. Find large files/directories in pods
```bash
kubectl exec <pod> -n <namespace> -- du -sh /* 2>/dev/null | sort -h | tail -20
```

## Common Causes

| Issue | Indicators | Solution |
|-------|-----------|----------|
| **Log files** | /var/log filling up | Configure log rotation |
| **Container images** | /var/lib/containerd or /var/lib/docker full | Clean unused images |
| **Ephemeral storage** | Pod using more than requested | Set limits, clean tmp files |
| **PVC full** | Volume at capacity | Resize PVC or clean data |
| **Core dumps** | Large core files | Disable core dumps or manage space |

## Remediation

### For node disk pressure

1. **Clean up container images**:
   ```bash
   # On the node
   crictl rmi --prune
   # Or for Docker
   docker system prune -a
   ```

2. **Clean container logs**:
   ```bash
   # Truncate logs for specific container
   truncate -s 0 /var/log/containers/<container>*.log
   ```

3. **Remove evicted pods**:
   ```bash
   kubectl get pods --all-namespaces -o json | \
     jq -r '.items[] | select(.status.reason=="Evicted") | .metadata.namespace + " " + .metadata.name' | \
     xargs -L1 kubectl delete pod -n
   ```

### For ephemeral storage pressure

1. **Set ephemeral storage limits**:
   ```yaml
   resources:
     requests:
       ephemeral-storage: "1Gi"
     limits:
       ephemeral-storage: "2Gi"
   ```

2. **Clean up in the pod**:
   ```bash
   kubectl exec <pod> -- rm -rf /tmp/* /var/tmp/*
   kubectl exec <pod> -- find /app/logs -type f -mtime +7 -delete
   ```

### For PVC full

1. **Expand PVC** (if storage class supports it):
   ```bash
   kubectl patch pvc <pvc-name> -n <namespace> -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
   ```

2. **Clean up data in volume**:
   ```bash
   kubectl exec <pod> -n <namespace> -- find /data -type f -mtime +30 -delete
   ```

3. **Add new PVC and migrate data**

### For log buildup

1. **Configure log rotation in application**

2. **Use sidecar for log shipping**:
   ```yaml
   - name: log-shipper
     image: fluent/fluent-bit
     volumeMounts:
     - name: logs
       mountPath: /var/log/app
   ```

3. **Set container log limits in containerd/docker**:
   ```json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "100m",
       "max-file": "3"
     }
   }
   ```

## Prevention

1. **Set resource quotas** for namespaces:
   ```yaml
   apiVersion: v1
   kind: ResourceQuota
   metadata:
     name: storage-quota
   spec:
     hard:
       requests.storage: "100Gi"
   ```

2. **Configure monitoring**:
   ```yaml
   - alert: NodeDiskPressure
     expr: kube_node_status_condition{condition="DiskPressure",status="true"} == 1
     for: 5m
   ```

3. **Regular cleanup jobs**:
   ```yaml
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: log-cleanup
   spec:
     schedule: "0 2 * * *"
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: cleanup
               image: busybox
               command: ["find", "/logs", "-mtime", "+7", "-delete"]
               volumeMounts:
               - name: logs
                 mountPath: /logs
   ```

4. **Use separate volumes** for data vs logs
5. **Implement retention policies** for databases and logs
