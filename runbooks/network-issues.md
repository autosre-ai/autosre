---
symptoms: network error, connection refused, connection timeout, DNS failure, no route to host, connection reset
services: any
tags: network, connectivity, dns, timeout, connection
---

# Network Issues

## Symptoms
- Connection refused errors
- Connection timeouts
- DNS resolution failures
- Intermittent connectivity
- High network latency
- Packet loss

## Investigation Steps

### 1. Test basic connectivity
```bash
# From inside the pod
kubectl exec -it <pod> -n <namespace> -- /bin/sh

# Test DNS resolution
nslookup <service-name>
nslookup <service-name>.<namespace>.svc.cluster.local

# Test connectivity
nc -zv <service-name> <port>
wget -O- --timeout=5 http://<service-name>:<port>/health
```

### 2. Check service and endpoints
```bash
# Does the service exist?
kubectl get svc <service-name> -n <namespace>

# Does it have endpoints?
kubectl get endpoints <service-name> -n <namespace>

# Are pods selected by service?
kubectl get pods -l <service-selector> -n <namespace>
```

### 3. Check network policies
```bash
kubectl get networkpolicies -n <namespace>
kubectl describe networkpolicy <name> -n <namespace>
```

### 4. Check DNS (CoreDNS)
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
```

### 5. Check node connectivity
```bash
# Ping between nodes
kubectl debug node/<node-name> -it --image=nicolaka/netshoot -- ping <other-node-ip>
```

## Common Issues

### Connection Refused
- Target pod not running
- Target pod not listening on expected port
- Service port mapping incorrect
- Readiness probe failing (removed from endpoints)

**Fix:**
```bash
# Check pods are ready
kubectl get pods -l app=<service> -n <namespace>

# Check service port mapping
kubectl describe svc <service>

# Check container is listening
kubectl exec <pod> -- netstat -tlnp
```

### DNS Resolution Failures
- CoreDNS pods unhealthy
- Pod DNS config incorrect
- Service name typo
- Wrong namespace

**Fix:**
```bash
# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Test DNS from pod
kubectl exec <pod> -- cat /etc/resolv.conf
kubectl exec <pod> -- nslookup kubernetes.default
```

### Connection Timeout
- Network policy blocking traffic
- Firewall rules
- Target service overloaded
- Routing issues

**Fix:**
```bash
# Check network policies
kubectl get networkpolicy -A

# Test with policy disabled (temporarily)
kubectl delete networkpolicy <blocking-policy> -n <namespace>
```

### Intermittent Issues
- Load balancer health check failures
- Pod scheduling across failure domains
- Resource contention
- CNI issues

## Network Debugging Tools

### From inside a pod
```bash
# If busybox or similar is available
nslookup <hostname>
ping <hostname>
nc -zv <hostname> <port>
traceroute <hostname>
```

### Using debug container
```bash
kubectl debug <pod> -it --image=nicolaka/netshoot -n <namespace>

# Inside netshoot:
curl -v http://<service>:<port>
tcpdump -i any port <port>
iptables -L -n
```

### Using temporary debug pod
```bash
kubectl run netdebug --rm -it --image=nicolaka/netshoot -- /bin/bash
```

## Remediation

### For connection refused
1. Verify target pods are running and ready
2. Check service selector matches pod labels
3. Verify container is listening on correct port

### For DNS failures
1. Restart CoreDNS: `kubectl rollout restart deployment/coredns -n kube-system`
2. Check CoreDNS configmap
3. Verify cluster DNS is reachable from pod

### For network policy blocks
1. Review network policies in both namespaces
2. Add allow rule if traffic should be permitted:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: allow-from-namespace
   spec:
     podSelector: {}
     ingress:
     - from:
       - namespaceSelector:
           matchLabels:
             name: <source-namespace>
   ```

### For CNI issues
1. Check CNI pods (e.g., calico, cilium, weave)
2. Review CNI logs
3. May require node restart in severe cases

## Prevention
1. Use network policies with explicit allow rules
2. Implement service mesh for observability
3. Set up connectivity checks between critical services
4. Use health checks and circuit breakers
