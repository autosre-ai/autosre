"""
Sandbox Cluster - Kind-based Kubernetes cluster for testing.

Provides automated setup and teardown of a local Kubernetes cluster
with all necessary components for testing AutoSRE.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import yaml


class SandboxCluster:
    """
    Kind-based sandbox Kubernetes cluster.
    
    Features:
    - Single command create/destroy
    - Pre-configured for observability
    - Sample workloads included
    """
    
    def __init__(self, name: str = "autosre-sandbox"):
        """
        Initialize sandbox cluster.
        
        Args:
            name: Cluster name (used by kind)
        """
        self.name = name
        self._kubeconfig: Optional[str] = None
    
    @property
    def kubeconfig(self) -> Optional[str]:
        """Get the kubeconfig path for this cluster."""
        return self._kubeconfig
    
    def create(
        self,
        nodes: int = 1,
        kubernetes_version: str = "v1.29.0",
        wait_timeout: str = "5m",
    ) -> bool:
        """
        Create the sandbox cluster.
        
        Args:
            nodes: Number of worker nodes (1-3 recommended)
            kubernetes_version: Kubernetes version to use
            wait_timeout: Timeout for cluster to be ready
            
        Returns:
            True if cluster created successfully
        """
        # Generate kind config
        config = self._generate_kind_config(nodes, kubernetes_version)
        
        # Write config to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            # Create cluster
            result = subprocess.run(
                [
                    "kind", "create", "cluster",
                    "--name", self.name,
                    "--config", config_path,
                    "--wait", wait_timeout,
                ],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                print(f"Failed to create cluster: {result.stderr}")
                return False
            
            # Get kubeconfig
            kubeconfig_result = subprocess.run(
                ["kind", "get", "kubeconfig", "--name", self.name],
                capture_output=True,
                text=True,
            )
            
            if kubeconfig_result.returncode == 0:
                kubeconfig_path = Path.home() / ".autosre" / f"kubeconfig-{self.name}"
                kubeconfig_path.parent.mkdir(parents=True, exist_ok=True)
                kubeconfig_path.write_text(kubeconfig_result.stdout)
                self._kubeconfig = str(kubeconfig_path)
            
            return True
            
        finally:
            # Cleanup temp file
            Path(config_path).unlink(missing_ok=True)
    
    def destroy(self) -> bool:
        """
        Destroy the sandbox cluster.
        
        Returns:
            True if cluster destroyed successfully
        """
        result = subprocess.run(
            ["kind", "delete", "cluster", "--name", self.name],
            capture_output=True,
            text=True,
        )
        
        # Clean up kubeconfig
        if self._kubeconfig:
            Path(self._kubeconfig).unlink(missing_ok=True)
            self._kubeconfig = None
        
        return result.returncode == 0
    
    def exists(self) -> bool:
        """Check if the cluster exists."""
        result = subprocess.run(
            ["kind", "get", "clusters"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            return False
        
        return self.name in result.stdout.split()
    
    def get_status(self) -> dict:
        """Get cluster status."""
        if not self.exists():
            return {"status": "not_found"}
        
        # Get nodes
        result = subprocess.run(
            [
                "kubectl", "get", "nodes",
                "--kubeconfig", self._kubeconfig or "",
                "-o", "json",
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}
        
        import json
        nodes_data = json.loads(result.stdout)
        
        nodes = []
        for node in nodes_data.get("items", []):
            conditions = {c["type"]: c["status"] for c in node.get("status", {}).get("conditions", [])}
            nodes.append({
                "name": node["metadata"]["name"],
                "ready": conditions.get("Ready") == "True",
                "roles": [k.replace("node-role.kubernetes.io/", "") for k in node["metadata"].get("labels", {}) if k.startswith("node-role.kubernetes.io/")],
            })
        
        return {
            "status": "running",
            "name": self.name,
            "kubeconfig": self._kubeconfig,
            "nodes": nodes,
            "ready_nodes": sum(1 for n in nodes if n["ready"]),
        }
    
    def _generate_kind_config(self, nodes: int, k8s_version: str) -> dict:
        """Generate kind cluster config."""
        config = {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "nodes": [
                {
                    "role": "control-plane",
                    "image": f"kindest/node:{k8s_version}",
                    "kubeadmConfigPatches": [
                        """
kind: InitConfiguration
nodeRegistration:
  kubeletExtraArgs:
    node-labels: "ingress-ready=true"
"""
                    ],
                    "extraPortMappings": [
                        # Ingress HTTP
                        {"containerPort": 80, "hostPort": 80, "protocol": "TCP"},
                        # Ingress HTTPS
                        {"containerPort": 443, "hostPort": 443, "protocol": "TCP"},
                        # Prometheus
                        {"containerPort": 30090, "hostPort": 9090, "protocol": "TCP"},
                        # Grafana
                        {"containerPort": 30030, "hostPort": 3000, "protocol": "TCP"},
                    ],
                }
            ],
        }
        
        # Add worker nodes
        for _ in range(nodes):
            config["nodes"].append({
                "role": "worker",
                "image": f"kindest/node:{k8s_version}",
            })
        
        return config
    
    def deploy_sample_app(self, app: str = "podinfo") -> bool:
        """
        Deploy a sample application for testing.
        
        Args:
            app: Application to deploy (podinfo, bookstore)
            
        Returns:
            True if deployed successfully
        """
        if not self._kubeconfig:
            print("Cluster not created or kubeconfig not available")
            return False
        
        if app == "podinfo":
            return self._deploy_podinfo()
        elif app == "bookstore":
            return self._deploy_bookstore()
        else:
            print(f"Unknown app: {app}")
            return False
    
    def _deploy_podinfo(self) -> bool:
        """Deploy podinfo application."""
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: podinfo
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: podinfo
  template:
    metadata:
      labels:
        app: podinfo
      annotations:
        autosre.io/team: platform
    spec:
      containers:
      - name: podinfo
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
        readinessProbe:
          httpGet:
            path: /readyz
            port: 9898
        livenessProbe:
          httpGet:
            path: /healthz
            port: 9898
---
apiVersion: v1
kind: Service
metadata:
  name: podinfo
  namespace: default
spec:
  selector:
    app: podinfo
  ports:
  - port: 80
    targetPort: 9898
  type: ClusterIP
"""
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-", "--kubeconfig", self._kubeconfig],
            input=manifest,
            capture_output=True,
            text=True,
        )
        
        return result.returncode == 0
    
    def _deploy_bookstore(self) -> bool:
        """Deploy bookstore sample application."""
        manifest = """
apiVersion: v1
kind: Namespace
metadata:
  name: bookstore
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
      annotations:
        autosre.io/dependencies: "api,catalog"
    spec:
      containers:
      - name: frontend
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: bookstore
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
      annotations:
        autosre.io/dependencies: "catalog,orders,database"
    spec:
      containers:
      - name: api
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catalog
  namespace: bookstore
spec:
  replicas: 2
  selector:
    matchLabels:
      app: catalog
  template:
    metadata:
      labels:
        app: catalog
      annotations:
        autosre.io/dependencies: "database"
    spec:
      containers:
      - name: catalog
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders
  namespace: bookstore
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orders
  template:
    metadata:
      labels:
        app: orders
      annotations:
        autosre.io/dependencies: "database,payment"
    spec:
      containers:
      - name: orders
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment
  template:
    metadata:
      labels:
        app: payment
    spec:
      containers:
      - name: payment
        image: stefanprodan/podinfo:6.5.0
        ports:
        - containerPort: 9898
"""
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-", "--kubeconfig", self._kubeconfig],
            input=manifest,
            capture_output=True,
            text=True,
        )
        
        return result.returncode == 0
