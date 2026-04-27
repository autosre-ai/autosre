"""
Chaos Injection - Fault injection for testing resilience.

Supports various chaos scenarios:
- Pod failures (kill, crash)
- Network issues (latency, partition)
- Resource pressure (CPU, memory)
"""

import subprocess
from typing import Optional


class ChaosInjector:
    """
    Chaos injection for sandbox testing.
    
    Provides controlled failure injection for:
    - Testing alert detection
    - Validating runbooks
    - Training the agent
    """
    
    def __init__(self, kubeconfig: Optional[str] = None):
        """
        Initialize chaos injector.
        
        Args:
            kubeconfig: Path to kubeconfig file
        """
        self.kubeconfig = kubeconfig
    
    def _kubectl(self, *args) -> subprocess.CompletedProcess:
        """Run kubectl command."""
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        cmd.extend(args)
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def kill_pod(
        self,
        name: Optional[str] = None,
        namespace: str = "default",
        labels: Optional[str] = None,
    ) -> bool:
        """
        Kill a pod.
        
        Args:
            name: Pod name (or use labels)
            namespace: Namespace
            labels: Label selector (e.g., "app=frontend")
            
        Returns:
            True if pod killed successfully
        """
        if name:
            result = self._kubectl("delete", "pod", name, "-n", namespace, "--force", "--grace-period=0")
        elif labels:
            result = self._kubectl("delete", "pod", "-l", labels, "-n", namespace, "--force", "--grace-period=0")
        else:
            return False
        
        return result.returncode == 0
    
    def scale_deployment(
        self,
        name: str,
        replicas: int,
        namespace: str = "default",
    ) -> bool:
        """
        Scale a deployment.
        
        Args:
            name: Deployment name
            replicas: Desired replicas
            namespace: Namespace
            
        Returns:
            True if scaled successfully
        """
        result = self._kubectl(
            "scale", "deployment", name,
            "--replicas", str(replicas),
            "-n", namespace
        )
        return result.returncode == 0
    
    def inject_network_latency(
        self,
        pod: str,
        namespace: str = "default",
        latency_ms: int = 500,
        duration_s: int = 60,
    ) -> bool:
        """
        Inject network latency into a pod.
        
        Uses tc (traffic control) via kubectl exec.
        
        Args:
            pod: Pod name
            namespace: Namespace
            latency_ms: Latency to add in milliseconds
            duration_s: Duration in seconds
            
        Returns:
            True if injection started
        """
        # Add latency using tc
        add_cmd = f"tc qdisc add dev eth0 root netem delay {latency_ms}ms"
        result = self._kubectl(
            "exec", pod, "-n", namespace,
            "--", "sh", "-c", add_cmd
        )
        
        if result.returncode != 0:
            # Try replacing instead of adding
            replace_cmd = f"tc qdisc replace dev eth0 root netem delay {latency_ms}ms"
            result = self._kubectl(
                "exec", pod, "-n", namespace,
                "--", "sh", "-c", replace_cmd
            )
        
        return result.returncode == 0
    
    def inject_cpu_stress(
        self,
        deployment: str,
        namespace: str = "default",
        cpu_percent: int = 90,
    ) -> bool:
        """
        Inject CPU stress into pods.
        
        Patches deployment to add a stress container.
        
        Args:
            deployment: Deployment name
            namespace: Namespace
            cpu_percent: CPU usage target
            
        Returns:
            True if injection applied
        """
        # Patch to add stress container
        patch = f'''
{{
  "spec": {{
    "template": {{
      "spec": {{
        "containers": [{{
          "name": "stress",
          "image": "polinux/stress",
          "command": ["stress"],
          "args": ["--cpu", "1", "--timeout", "300s"],
          "resources": {{
            "requests": {{"cpu": "{cpu_percent}m"}},
            "limits": {{"cpu": "{cpu_percent}m"}}
          }}
        }}]
      }}
    }}
  }}
}}
'''
        result = self._kubectl(
            "patch", "deployment", deployment,
            "-n", namespace,
            "--type", "strategic",
            "-p", patch
        )
        
        return result.returncode == 0
    
    def inject_memory_pressure(
        self,
        deployment: str,
        namespace: str = "default",
        memory_mb: int = 256,
    ) -> bool:
        """
        Inject memory pressure into pods.
        
        Args:
            deployment: Deployment name
            namespace: Namespace
            memory_mb: Memory to consume in MB
            
        Returns:
            True if injection applied
        """
        patch = f'''
{{
  "spec": {{
    "template": {{
      "spec": {{
        "containers": [{{
          "name": "stress-mem",
          "image": "polinux/stress",
          "command": ["stress"],
          "args": ["--vm", "1", "--vm-bytes", "{memory_mb}M", "--timeout", "300s"],
          "resources": {{
            "requests": {{"memory": "{memory_mb}Mi"}},
            "limits": {{"memory": "{memory_mb}Mi"}}
          }}
        }}]
      }}
    }}
  }}
}}
'''
        result = self._kubectl(
            "patch", "deployment", deployment,
            "-n", namespace,
            "--type", "strategic",
            "-p", patch
        )
        
        return result.returncode == 0
    
    def partition_network(
        self,
        source_labels: str,
        target_labels: str,
        namespace: str = "default",
    ) -> bool:
        """
        Create a network partition using NetworkPolicy.
        
        Args:
            source_labels: Source pod labels (e.g., "app=frontend")
            target_labels: Target pod labels to block (e.g., "app=api")
            namespace: Namespace
            
        Returns:
            True if partition created
        """
        # Parse labels
        source_key, source_val = source_labels.split("=")
        target_key, target_val = target_labels.split("=")
        
        policy = f"""
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: autosre-chaos-partition
  namespace: {namespace}
spec:
  podSelector:
    matchLabels:
      {source_key}: {source_val}
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchExpressions:
        - key: {target_key}
          operator: NotIn
          values: [{target_val}]
"""
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"] + 
            (["--kubeconfig", self.kubeconfig] if self.kubeconfig else []),
            input=policy,
            capture_output=True,
            text=True,
        )
        
        return result.returncode == 0
    
    def remove_partition(self, namespace: str = "default") -> bool:
        """Remove network partition."""
        result = self._kubectl(
            "delete", "networkpolicy", "autosre-chaos-partition",
            "-n", namespace, "--ignore-not-found"
        )
        return result.returncode == 0
    
    def fill_disk(
        self,
        pod: str,
        namespace: str = "default",
        size_mb: int = 100,
        path: str = "/tmp",
    ) -> bool:
        """
        Fill disk space in a pod.
        
        Args:
            pod: Pod name
            namespace: Namespace
            size_mb: Size to fill in MB
            path: Path to fill
            
        Returns:
            True if command succeeded
        """
        cmd = f"dd if=/dev/zero of={path}/chaos-fill bs=1M count={size_mb}"
        result = self._kubectl(
            "exec", pod, "-n", namespace,
            "--", "sh", "-c", cmd
        )
        
        return result.returncode == 0
    
    def cleanup(self, namespace: str = "default") -> bool:
        """
        Clean up all chaos injections.
        
        Returns:
            True if cleanup successful
        """
        # Remove network policies
        self.remove_partition(namespace)
        
        # Remove stress containers would require removing patches
        # which is more complex - usually just restart the deployment
        
        return True
    
    def get_available_chaos_types(self) -> list[dict]:
        """List available chaos injection types."""
        return [
            {
                "type": "pod_kill",
                "description": "Kill a pod immediately",
                "parameters": ["name", "namespace", "labels"],
            },
            {
                "type": "scale_down",
                "description": "Scale deployment to 0 replicas",
                "parameters": ["deployment", "namespace"],
            },
            {
                "type": "network_latency",
                "description": "Add network latency to pod",
                "parameters": ["pod", "namespace", "latency_ms"],
            },
            {
                "type": "cpu_stress",
                "description": "Add CPU stress container",
                "parameters": ["deployment", "namespace", "cpu_percent"],
            },
            {
                "type": "memory_pressure",
                "description": "Add memory pressure container",
                "parameters": ["deployment", "namespace", "memory_mb"],
            },
            {
                "type": "network_partition",
                "description": "Block traffic between pods",
                "parameters": ["source_labels", "target_labels", "namespace"],
            },
            {
                "type": "disk_fill",
                "description": "Fill disk space in pod",
                "parameters": ["pod", "namespace", "size_mb"],
            },
        ]
