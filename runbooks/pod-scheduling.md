---
symptoms: pending pods, pod scheduling, unschedulable, insufficient resources, node selector
services: any
tags: scheduling, pending, resources, nodes, affinity
---

# Pod Scheduling Issues / Pending Pods

## Symptoms
- Pods stuck in `Pending` state
- Events showing scheduling failures
- "Insufficient cpu/memory" messages
- "No nodes match node selector" errors
- "Pod has unbound PersistentVolumeClaims"

## Investigation Steps

### 1. Check pod status and events
```bash
kubectl describe pod <pod> -n <namespace> | grep -A20 "Events"
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20
```

### 2. Check resource requests vs available
```bash
kubectl describe nodes | grep -A10 "Allocated resources"
kubectl top nodes
```

### 3. Check for node selector/affinity mismatches
```bash
kubectl get pod <pod> -o yaml | grep -A10 "nodeSelector\|affinity"
kubectl get nodes --show-labels
```

### 4. Check PVC binding
```bash
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>
```

### 5. Check taints and tolerations
```bash
kubectl describe nodes | grep -A3 "Taints"
kubectl get pod <pod> -o yaml | grep -A10 "tolerations"
```

## Common Causes

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Insufficient cpu` | Not enough CPU on any node | Scale cluster or reduce requests |
| `Insufficient memory` | Not enough memory on any node | Scale cluster or reduce requests |
| `0/N nodes are available` | No schedulable nodes | Check taints, cordons, resource constraints |
| `node(s) didn't match node selector` | Node selector too restrictive | Add labels to nodes or relax selector |
| `pod has unbound PersistentVolumeClaims` | PVC not bound | Check storage class, PV availability |
| `pod anti-affinity rules` | Affinity spreading requirements | Ensure enough nodes in required zones |

## Remediation

### For insufficient resources

1. **Check which nodes have capacity**:
   ```bash
   kubectl describe nodes | grep -E "Name:|Allocatable:|Allocated"
   ```

2. **Scale the cluster** (if using managed K8s):
   ```bash
   # AWS EKS
   eksctl scale nodegroup --cluster=<cluster> --name=<ng> --nodes=<n>
   
   # GKE
   gcloud container clusters resize <cluster> --node-pool=<pool> --num-nodes=<n>
   ```

3. **Reduce resource requests**:
   ```bash
   kubectl set resources deployment/<name> --requests=cpu=100m,memory=256Mi
   ```

4. **Evict lower-priority pods** (if using PriorityClasses):
   ```bash
   kubectl get pods --all-namespaces -o custom-columns=NAME:.metadata.name,PRIORITY:.spec.priority
   ```

### For node selector issues

1. **List node labels**:
   ```bash
   kubectl get nodes --show-labels
   ```

2. **Add label to node**:
   ```bash
   kubectl label node <node> <key>=<value>
   ```

3. **Or update deployment** to remove/change selector:
   ```bash
   kubectl patch deployment <name> --type='json' \
     -p='[{"op": "remove", "path": "/spec/template/spec/nodeSelector"}]'
   ```

### For PVC binding issues

1. **Check StorageClass exists**:
   ```bash
   kubectl get sc
   ```

2. **Check PV availability**:
   ```bash
   kubectl get pv
   ```

3. **For dynamic provisioning issues**, check storage provisioner:
   ```bash
   kubectl get pods -n kube-system -l app=ebs-csi-controller
   kubectl logs -n kube-system -l app=ebs-csi-controller
   ```

### For taint/toleration issues

1. **Check node taints**:
   ```bash
   kubectl describe nodes | grep Taints
   ```

2. **Add toleration to deployment**:
   ```yaml
   tolerations:
   - key: "key"
     operator: "Equal"
     value: "value"
     effect: "NoSchedule"
   ```

3. **Remove taint from node** (if appropriate):
   ```bash
   kubectl taint nodes <node> <key>-
   ```

## Prevention

1. Set up alerts for pending pods:
   ```yaml
   - alert: PodsPending
     expr: sum(kube_pod_status_phase{phase="Pending"}) > 0
     for: 10m
   ```

2. Use `PodDisruptionBudgets` for availability

3. Implement cluster autoscaling

4. Use `ResourceQuotas` to prevent namespace over-commit

5. Regular capacity planning reviews
