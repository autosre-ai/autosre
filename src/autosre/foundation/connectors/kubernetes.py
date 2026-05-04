"""
Kubernetes Connector - Pull service topology from Kubernetes clusters.

This connector discovers:
- Deployments/StatefulSets/DaemonSets as services
- Service dependencies (via labels/annotations)
- Current replica status
- Recent events
"""

from datetime import datetime, timezone
from typing import Any, Optional

from autosre.foundation.connectors.base import BaseConnector
from autosre.foundation.models import Service, ServiceStatus, ChangeEvent, ChangeType


class KubernetesConnector(BaseConnector):
    """
    Kubernetes connector for discovering services and their state.
    
    Requires either:
    - In-cluster config (when running in K8s)
    - Kubeconfig file (when running locally)
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client = None
        self._apps_v1 = None
        self._core_v1 = None
    
    @property
    def name(self) -> str:
        return "kubernetes"
    
    async def connect(self) -> bool:
        """Connect to Kubernetes cluster."""
        try:
            from kubernetes import client, config as k8s_config
            
            # Try in-cluster config first, fall back to kubeconfig
            kubeconfig = self.config.get("kubeconfig")
            context = self.config.get("context")
            
            try:
                if kubeconfig:
                    k8s_config.load_kube_config(config_file=kubeconfig, context=context)
                else:
                    try:
                        k8s_config.load_incluster_config()
                    except k8s_config.ConfigException:
                        k8s_config.load_kube_config(context=context)
            except Exception as e:
                self._last_error = f"Failed to load kubeconfig: {e}"
                return False
            
            self._client = client
            self._apps_v1 = client.AppsV1Api()
            self._core_v1 = client.CoreV1Api()
            self._connected = True
            return True
            
        except ImportError:
            self._last_error = "kubernetes package not installed"
            return False
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Kubernetes."""
        self._client = None
        self._apps_v1 = None
        self._core_v1 = None
        self._connected = False
    
    async def health_check(self) -> bool:
        """Check if Kubernetes API is reachable."""
        if not self._connected or not self._core_v1:
            return False
        
        try:
            self._core_v1.get_api_versions()
            return True
        except Exception:
            return False
    
    async def sync(self, context_store: Any) -> int:
        """
        Sync Kubernetes resources to context store.
        
        Discovers deployments, statefulsets, and daemonsets as services.
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kubernetes")
        
        count = 0
        namespaces = self.config.get("namespaces", [])
        cluster_name = self.config.get("cluster_name", "default")
        
        # Get all namespaces if not specified
        if not namespaces:
            ns_list = self._core_v1.list_namespace()
            namespaces = [ns.metadata.name for ns in ns_list.items]
        
        for namespace in namespaces:
            # Skip system namespaces unless explicitly included
            if namespace.startswith("kube-") and namespace not in self.config.get("namespaces", []):
                continue
            
            # Sync deployments
            count += await self._sync_deployments(context_store, namespace, cluster_name)
            
            # Sync statefulsets
            count += await self._sync_statefulsets(context_store, namespace, cluster_name)
            
            # Sync daemonsets
            count += await self._sync_daemonsets(context_store, namespace, cluster_name)
        
        return count
    
    async def _sync_deployments(self, context_store: Any, namespace: str, cluster: str) -> int:
        """Sync deployments from a namespace."""
        count = 0
        
        try:
            deployments = self._apps_v1.list_namespaced_deployment(namespace)
            
            for deploy in deployments.items:
                service = self._deployment_to_service(deploy, namespace, cluster)
                context_store.add_service(service)
                count += 1
                
        except Exception as e:
            self._last_error = f"Error syncing deployments in {namespace}: {e}"
        
        return count
    
    async def _sync_statefulsets(self, context_store: Any, namespace: str, cluster: str) -> int:
        """Sync statefulsets from a namespace."""
        count = 0
        
        try:
            statefulsets = self._apps_v1.list_namespaced_stateful_set(namespace)
            
            for sts in statefulsets.items:
                service = self._statefulset_to_service(sts, namespace, cluster)
                context_store.add_service(service)
                count += 1
                
        except Exception as e:
            self._last_error = f"Error syncing statefulsets in {namespace}: {e}"
        
        return count
    
    async def _sync_daemonsets(self, context_store: Any, namespace: str, cluster: str) -> int:
        """Sync daemonsets from a namespace."""
        count = 0
        
        try:
            daemonsets = self._apps_v1.list_namespaced_daemon_set(namespace)
            
            for ds in daemonsets.items:
                service = self._daemonset_to_service(ds, namespace, cluster)
                context_store.add_service(service)
                count += 1
                
        except Exception as e:
            self._last_error = f"Error syncing daemonsets in {namespace}: {e}"
        
        return count
    
    def _deployment_to_service(self, deploy, namespace: str, cluster: str) -> Service:
        """Convert a Kubernetes Deployment to a Service model."""
        meta = deploy.metadata
        spec = deploy.spec
        status = deploy.status
        
        # Determine service status
        replicas = spec.replicas or 1
        ready = status.ready_replicas or 0
        
        if ready == 0:
            svc_status = ServiceStatus.DOWN
        elif ready < replicas:
            svc_status = ServiceStatus.DEGRADED
        else:
            svc_status = ServiceStatus.HEALTHY
        
        # Extract dependencies from annotations
        dependencies = []
        if meta.annotations:
            deps = meta.annotations.get("autosre.io/dependencies", "")
            if deps:
                dependencies = [d.strip() for d in deps.split(",")]
        
        return Service(
            name=meta.name,
            namespace=namespace,
            cluster=cluster,
            dependencies=dependencies,
            status=svc_status,
            replicas=replicas,
            ready_replicas=ready,
            labels=meta.labels or {},
            annotations=meta.annotations or {},
            created_at=meta.creation_timestamp,
            last_updated=datetime.now(timezone.utc),
        )
    
    def _statefulset_to_service(self, sts, namespace: str, cluster: str) -> Service:
        """Convert a Kubernetes StatefulSet to a Service model."""
        meta = sts.metadata
        spec = sts.spec
        status = sts.status
        
        replicas = spec.replicas or 1
        ready = status.ready_replicas or 0
        
        if ready == 0:
            svc_status = ServiceStatus.DOWN
        elif ready < replicas:
            svc_status = ServiceStatus.DEGRADED
        else:
            svc_status = ServiceStatus.HEALTHY
        
        dependencies = []
        if meta.annotations:
            deps = meta.annotations.get("autosre.io/dependencies", "")
            if deps:
                dependencies = [d.strip() for d in deps.split(",")]
        
        return Service(
            name=meta.name,
            namespace=namespace,
            cluster=cluster,
            dependencies=dependencies,
            status=svc_status,
            replicas=replicas,
            ready_replicas=ready,
            labels=meta.labels or {},
            annotations=meta.annotations or {},
            created_at=meta.creation_timestamp,
            last_updated=datetime.now(timezone.utc),
        )
    
    def _daemonset_to_service(self, ds, namespace: str, cluster: str) -> Service:
        """Convert a Kubernetes DaemonSet to a Service model."""
        meta = ds.metadata
        status = ds.status
        
        desired = status.desired_number_scheduled or 1
        ready = status.number_ready or 0
        
        if ready == 0:
            svc_status = ServiceStatus.DOWN
        elif ready < desired:
            svc_status = ServiceStatus.DEGRADED
        else:
            svc_status = ServiceStatus.HEALTHY
        
        dependencies = []
        if meta.annotations:
            deps = meta.annotations.get("autosre.io/dependencies", "")
            if deps:
                dependencies = [d.strip() for d in deps.split(",")]
        
        return Service(
            name=meta.name,
            namespace=namespace,
            cluster=cluster,
            dependencies=dependencies,
            status=svc_status,
            replicas=desired,
            ready_replicas=ready,
            labels=meta.labels or {},
            annotations=meta.annotations or {},
            created_at=meta.creation_timestamp,
            last_updated=datetime.now(timezone.utc),
        )
    
    async def get_recent_events(self, namespace: str = "default", limit: int = 50) -> list[ChangeEvent]:
        """Get recent Kubernetes events as change events."""
        if not self._connected:
            return []
        
        events = []
        try:
            k8s_events = self._core_v1.list_namespaced_event(
                namespace,
                limit=limit,
            )
            
            for event in k8s_events.items:
                # Only include deployment-related events
                if event.involved_object.kind not in ["Deployment", "StatefulSet", "DaemonSet", "Pod"]:
                    continue
                
                change = ChangeEvent(
                    id=event.metadata.uid,
                    change_type=ChangeType.DEPLOYMENT,
                    service_name=event.involved_object.name,
                    description=f"{event.reason}: {event.message}",
                    author="kubernetes",
                    timestamp=event.last_timestamp or event.first_timestamp or datetime.now(timezone.utc),
                )
                events.append(change)
                
        except Exception as e:
            self._last_error = f"Error getting events: {e}"
        
        return events
