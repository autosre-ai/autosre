"""
Observability Stack - Prometheus + Grafana for sandbox.

Deploys and manages the observability stack needed
for testing AutoSRE's metric and alert handling.
"""

import subprocess
from typing import Optional


class ObservabilityStack:
    """
    Observability stack deployment for sandbox.
    
    Includes:
    - Prometheus (metrics + alerting)
    - Grafana (dashboards)
    - Alertmanager (alert routing)
    """
    
    def __init__(self, kubeconfig: Optional[str] = None):
        """
        Initialize observability stack.
        
        Args:
            kubeconfig: Path to kubeconfig file
        """
        self.kubeconfig = kubeconfig
        self.namespace = "monitoring"
    
    def _kubectl(self, *args, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run kubectl command."""
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        cmd.extend(args)
        
        return subprocess.run(cmd, capture_output=True, text=True, input=input_text)
    
    def _helm(self, *args) -> subprocess.CompletedProcess:
        """Run helm command."""
        cmd = ["helm"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        cmd.extend(args)
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def deploy(self, use_helm: bool = True) -> bool:
        """
        Deploy the observability stack.
        
        Args:
            use_helm: Use helm charts (recommended)
            
        Returns:
            True if deployed successfully
        """
        # Create namespace
        self._kubectl("create", "namespace", self.namespace, "--dry-run=client", "-o", "yaml")
        self._kubectl("apply", "-f", "-", input_text=f"""
apiVersion: v1
kind: Namespace
metadata:
  name: {self.namespace}
""")
        
        if use_helm:
            return self._deploy_with_helm()
        else:
            return self._deploy_minimal()
    
    def _deploy_with_helm(self) -> bool:
        """Deploy using kube-prometheus-stack helm chart."""
        # Add helm repo
        self._helm("repo", "add", "prometheus-community", 
                   "https://prometheus-community.github.io/helm-charts")
        self._helm("repo", "update")
        
        # Install kube-prometheus-stack
        result = self._helm(
            "upgrade", "--install", "prometheus",
            "prometheus-community/kube-prometheus-stack",
            "-n", self.namespace,
            "--set", "prometheus.service.type=NodePort",
            "--set", "prometheus.service.nodePort=30090",
            "--set", "grafana.service.type=NodePort",
            "--set", "grafana.service.nodePort=30030",
            "--set", "alertmanager.service.type=NodePort",
            "--set", "alertmanager.service.nodePort=30093",
            "--wait", "--timeout", "5m",
        )
        
        return result.returncode == 0
    
    def _deploy_minimal(self) -> bool:
        """Deploy minimal Prometheus without helm."""
        prometheus_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    alerting:
      alertmanagers:
      - static_configs:
        - targets: []
    
    rule_files:
      - /etc/prometheus/rules/*.yaml
    
    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
        - role: pod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
          action: replace
          target_label: __metrics_path__
          regex: (.+)
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
      - name: prometheus
        image: prom/prometheus:v2.50.0
        args:
        - '--config.file=/etc/prometheus/prometheus.yml'
        - '--storage.tsdb.path=/prometheus'
        - '--web.enable-lifecycle'
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: storage
          mountPath: /prometheus
      volumes:
      - name: config
        configMap:
          name: prometheus-config
      - name: storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
    nodePort: 30090
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
- apiGroups: [""]
  resources: ["nodes", "nodes/proxy", "services", "endpoints", "pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get"]
- nonResourceURLs: ["/metrics"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
"""
        
        result = self._kubectl("apply", "-f", "-", input_text=prometheus_manifest)
        return result.returncode == 0
    
    def add_alert_rules(self, rules: list[dict]) -> bool:
        """
        Add alert rules to Prometheus.
        
        Args:
            rules: List of PrometheusRule definitions
            
        Returns:
            True if rules added successfully
        """
        import yaml
        
        for rule in rules:
            rule_manifest = yaml.dump({
                "apiVersion": "monitoring.coreos.com/v1",
                "kind": "PrometheusRule",
                "metadata": {
                    "name": rule.get("name", "autosre-rules"),
                    "namespace": self.namespace,
                },
                "spec": {
                    "groups": rule.get("groups", []),
                },
            })
            
            result = self._kubectl("apply", "-f", "-", input_text=rule_manifest)
            if result.returncode != 0:
                return False
        
        return True
    
    def add_default_alerts(self) -> bool:
        """Add default SRE alert rules."""
        rules = {
            "name": "autosre-default-rules",
            "groups": [
                {
                    "name": "autosre.pods",
                    "rules": [
                        {
                            "alert": "PodCrashLooping",
                            "expr": 'rate(kube_pod_container_status_restarts_total[15m]) > 0',
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Pod {{ $labels.pod }} is crash looping",
                            },
                        },
                        {
                            "alert": "PodNotReady",
                            "expr": 'kube_pod_status_ready{condition="true"} == 0',
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Pod {{ $labels.pod }} is not ready",
                            },
                        },
                    ],
                },
                {
                    "name": "autosre.resources",
                    "rules": [
                        {
                            "alert": "HighCPUUsage",
                            "expr": 'sum(rate(container_cpu_usage_seconds_total[5m])) by (pod) / sum(kube_pod_container_resource_limits{resource="cpu"}) by (pod) > 0.9',
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High CPU usage in pod {{ $labels.pod }}",
                            },
                        },
                        {
                            "alert": "HighMemoryUsage",
                            "expr": 'sum(container_memory_usage_bytes) by (pod) / sum(kube_pod_container_resource_limits{resource="memory"}) by (pod) > 0.9',
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High memory usage in pod {{ $labels.pod }}",
                            },
                        },
                    ],
                },
            ],
        }
        
        return self.add_alert_rules([rules])
    
    def get_prometheus_url(self) -> str:
        """Get Prometheus URL."""
        return "http://localhost:9090"
    
    def get_grafana_url(self) -> str:
        """Get Grafana URL."""
        return "http://localhost:3000"
    
    def get_status(self) -> dict:
        """Get observability stack status."""
        # Check Prometheus
        prom_result = self._kubectl(
            "get", "pods", "-n", self.namespace,
            "-l", "app=prometheus",
            "-o", "jsonpath={.items[0].status.phase}"
        )
        
        # Check Grafana
        grafana_result = self._kubectl(
            "get", "pods", "-n", self.namespace,
            "-l", "app.kubernetes.io/name=grafana",
            "-o", "jsonpath={.items[0].status.phase}"
        )
        
        return {
            "prometheus": {
                "status": prom_result.stdout or "Not Found",
                "url": self.get_prometheus_url(),
            },
            "grafana": {
                "status": grafana_result.stdout or "Not Found",
                "url": self.get_grafana_url(),
            },
        }
    
    def destroy(self) -> bool:
        """Remove the observability stack."""
        # Try helm uninstall first
        self._helm("uninstall", "prometheus", "-n", self.namespace)
        
        # Delete namespace
        result = self._kubectl("delete", "namespace", self.namespace, "--ignore-not-found")
        
        return result.returncode == 0
