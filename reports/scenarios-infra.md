# Infrastructure Fault Scenarios - Progress Report

**Generated:** 2025-01-15  
**Status:** ✅ Complete (50/50 scenarios)

## Summary

All 50 infrastructure fault scenarios have been created for the OpenSRE demo bookstore example.

## Categories

### Node Issues (10/10) ✅
| # | File | Description |
|---|------|-------------|
| 1 | `node-not-ready.yaml` | Kubelet issues causing node NotReady |
| 2 | `node-memory-pressure.yaml` | Node OOM and memory pressure |
| 3 | `node-disk-pressure.yaml` | Node disk full |
| 4 | `node-network-unavailable.yaml` | CNI issues |
| 5 | `node-pid-pressure.yaml` | Too many processes |
| 6 | `node-cordoned.yaml` | Scheduling disabled |
| 7 | `node-tainted.yaml` | Pods can't schedule due to taints |
| 8 | `node-clock-skew.yaml` | Time sync issues |
| 9 | `node-kernel-panic.yaml` | Simulated crash/drain |
| 10 | `node-unresponsive.yaml` | Kubelet stopped |

### Cluster Issues (10/10) ✅
| # | File | Description |
|---|------|-------------|
| 11 | `api-server-slow.yaml` | Control plane latency |
| 12 | `etcd-leader-election.yaml` | etcd instability |
| 13 | `scheduler-backlog.yaml` | Pending pods queue |
| 14 | `controller-manager-lag.yaml` | Slow reconciliation |
| 15 | `admission-webhook-slow.yaml` | Webhook latency |
| 16 | `crd-validation-failed.yaml` | Custom resource rejected |
| 17 | `namespace-terminating.yaml` | Stuck namespace deletion |
| 18 | `cluster-autoscaler-lag.yaml` | Slow scale-up |
| 19 | `kube-proxy-misconfigured.yaml` | Service routing broken |
| 20 | `coredns-overloaded.yaml` | DNS latency spike |

### Storage Issues (10/10) ✅
| # | File | Description |
|---|------|-------------|
| 21 | `pv-lost.yaml` | Persistent volume gone |
| 22 | `pvc-resize-failed.yaml` | Volume expansion error |
| 23 | `storage-class-missing.yaml` | StorageClass doesn't exist |
| 24 | `csi-driver-crash.yaml` | Storage driver failure |
| 25 | `snapshot-failed.yaml` | Backup error |
| 26 | `volume-attachment-stuck.yaml` | Mount issues |
| 27 | `nfs-server-down.yaml` | NFS unavailable |
| 28 | `local-storage-node-affinity.yaml` | Wrong node affinity |
| 29 | `storage-iops-throttled.yaml` | Cloud provider limits |
| 30 | `storage-quota-exceeded.yaml` | Quota hit |

### Networking Infrastructure (10/10) ✅
| # | File | Description |
|---|------|-------------|
| 31 | `load-balancer-unhealthy.yaml` | LB health check failing |
| 32 | `ingress-controller-crash.yaml` | nginx/traefik down |
| 33 | `service-mesh-config-error.yaml` | Istio misconfigured |
| 34 | `network-partition.yaml` | Split brain |
| 35 | `mtu-mismatch.yaml` | Packet fragmentation |
| 36 | `nat-gateway-exhausted.yaml` | Port exhaustion |
| 37 | `firewall-blocking.yaml` | Security group issues |
| 38 | `dns-ttl-cache-stale.yaml` | Stale DNS records |
| 39 | `proxy-protocol-mismatch.yaml` | Header issues |
| 40 | `tls-version-incompatible.yaml` | TLS 1.0 rejected |

### Observability Infrastructure (10/10) ✅
| # | File | Description |
|---|------|-------------|
| 41 | `prometheus-down.yaml` | Metrics unavailable |
| 42 | `prometheus-storage-full.yaml` | TSDB full |
| 43 | `prometheus-scrape-failed.yaml` | Target unreachable |
| 44 | `alertmanager-misconfigured.yaml` | Alerts not firing |
| 45 | `logging-pipeline-broken.yaml` | Logs not shipping |
| 46 | `tracing-sampler-misconfigured.yaml` | Missing traces |
| 47 | `grafana-datasource-error.yaml` | Dashboard broken |
| 48 | `metric-cardinality-explosion.yaml` | Too many series |
| 49 | `log-rotation-failed.yaml` | Disk filling up |
| 50 | `audit-logging-disabled.yaml` | Compliance violation |

## Schema Structure

Each fault scenario follows a consistent YAML schema:

```yaml
apiVersion: opensre.io/v1alpha1
kind: FaultScenario
metadata:
  name: <scenario-name>
  labels:
    category: <category>
    severity: <critical|high|medium|low>
    component: <affected-component>
spec:
  description: |
    <detailed description>
  symptoms:
    - type: <symptom-type>
      ...
  affectedResources:
    - kind: <resource-kind>
      ...
  metrics:
    - name: <metric-name>
      ...
  logs:
    - source: <log-source>
      level: <log-level>
      patterns: [...]
  rootCause:
    component: <component>
    type: <failure-type>
    details: |
      <root cause explanation>
  remediation:
    steps:
      - action: <action-name>
        command: <command>
        description: <step description>
  detection:
    promql: <prometheus-query>
    alertName: <alert-name>
    severity: <alert-severity>
```

## File Location

All scenarios are located in:
```
~/clawd/projects/opensre/examples/bookstore/faults/
```

## Statistics

- **Total scenarios:** 50
- **Critical severity:** 16
- **High severity:** 18
- **Medium severity:** 16
- **Total file size:** ~160KB
- **Average scenario size:** ~3.2KB
