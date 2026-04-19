"""
Azure Cloud Provider Skill for OpenSRE

Provides actions for Virtual Machines, AKS, Monitor, and Application Insights.
Uses azure-mgmt SDK with async wrappers for non-blocking operations.
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

from azure.identity import (
    DefaultAzureCredential,
    ClientSecretCredential,
    AzureCliCredential,
    ManagedIdentityCredential,
)
from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
)
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import VirtualMachine
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.resource import ResourceManagementClient
from azure.monitor.query import LogsQueryClient, MetricsQueryClient, LogsQueryStatus

try:
    from opensre.core.exceptions import SkillExecutionError
except ImportError:
    # Fallback for standalone skill usage
    class SkillExecutionError(Exception):
        """Raised when a skill method fails during execution."""
        def __init__(self, skill_name: str, method: str, reason: str):
            self.skill_name = skill_name
            self.method = method
            self.reason = reason
            super().__init__(f"Skill '{skill_name}.{method}' failed: {reason}")


logger = logging.getLogger(__name__)


@dataclass
class AzureVM:
    """Represents an Azure Virtual Machine."""
    name: str
    resource_group: str
    location: str
    vm_size: str
    provisioning_state: str
    power_state: str | None
    os_type: str | None
    private_ip: str | None = None
    public_ip: str | None = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AKSCluster:
    """Represents an AKS cluster."""
    name: str
    resource_group: str
    location: str
    kubernetes_version: str
    provisioning_state: str
    fqdn: str | None
    node_count: int
    node_pools: list[dict[str, Any]] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class LogQueryResult:
    """Represents a log query result."""
    tables: list[dict[str, Any]] = field(default_factory=list)
    statistics: dict[str, Any] | None = None
    status: str = "Success"


@dataclass
class MetricResult:
    """Represents a metric query result."""
    name: str
    unit: str
    timeseries: list[dict[str, Any]] = field(default_factory=list)


class AzureSkill:
    """
    Azure Cloud Provider Skill.
    
    Provides async methods for interacting with Azure services:
    - Virtual Machines: List, start, stop VMs
    - AKS: List clusters, get credentials
    - Monitor: Run KQL queries against Log Analytics
    - Application Insights: Query application telemetry
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize Azure Skill.
        
        Args:
            config: Configuration dict with credentials and settings.
                   If not provided, uses default credential chain.
        """
        self.config = config or {}
        self._credential = None
        self._subscription_id = self.config.get('subscription_id')
        self._resource_group = self.config.get('resource_group')
        self._max_retries = self.config.get('max_retries', 3)
        self._retry_delay = self.config.get('retry_delay', 1.0)
        self._timeout = self.config.get('timeout', 60)
        
        # Initialize credentials
        self._init_credentials()
    
    def _init_credentials(self):
        """Initialize Azure credentials based on config."""
        try:
            if self.config.get('use_managed_identity'):
                self._credential = ManagedIdentityCredential()
                
            elif self.config.get('use_cli_auth'):
                self._credential = AzureCliCredential()
                
            elif all(self.config.get(k) for k in ['tenant_id', 'client_id', 'client_secret']):
                self._credential = ClientSecretCredential(
                    tenant_id=self.config['tenant_id'],
                    client_id=self.config['client_id'],
                    client_secret=self.config['client_secret']
                )
            else:
                # Use default credential chain
                self._credential = DefaultAzureCredential()
                
        except ClientAuthenticationError as e:
            logger.warning(f"Failed to initialize Azure credentials: {e}")
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
    
    async def _retry_with_backoff(
        self,
        operation: str,
        func,
        *args,
        max_retries: int | None = None,
        **kwargs
    ) -> Any:
        """
        Execute an operation with exponential backoff retry.
        
        Args:
            operation: Name of the operation (for logging)
            func: Callable to execute
            max_retries: Override default max retries
        """
        retries = max_retries or self._max_retries
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                return await self._run_sync(func, *args, **kwargs)
            except ResourceNotFoundError as e:
                raise SkillExecutionError(
                    skill_name='azure',
                    method=operation,
                    reason=f"Resource not found: {e}"
                )
            except ClientAuthenticationError as e:
                raise SkillExecutionError(
                    skill_name='azure',
                    method=operation,
                    reason=f"Authentication failed: {e}"
                )
            except HttpResponseError as e:
                # Check if retryable
                if e.status_code in [429, 500, 502, 503, 504]:
                    last_error = e
                    if attempt < retries:
                        delay = self._retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Azure {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                            f"retrying in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                else:
                    raise SkillExecutionError(
                        skill_name='azure',
                        method=operation,
                        reason=f"Azure API error: {e}"
                    )
            except AzureError as e:
                last_error = e
                if attempt < retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Azure {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
        
        raise SkillExecutionError(
            skill_name='azure',
            method=operation,
            reason=f"Failed after {retries + 1} attempts: {last_error}"
        )
    
    def _get_compute_client(self) -> ComputeManagementClient:
        """Get Compute Management client."""
        if not self._subscription_id:
            raise SkillExecutionError(
                skill_name='azure',
                method='_get_compute_client',
                reason='No subscription ID configured'
            )
        return ComputeManagementClient(
            credential=self._credential,
            subscription_id=self._subscription_id
        )
    
    def _get_aks_client(self) -> ContainerServiceClient:
        """Get Container Service client."""
        if not self._subscription_id:
            raise SkillExecutionError(
                skill_name='azure',
                method='_get_aks_client',
                reason='No subscription ID configured'
            )
        return ContainerServiceClient(
            credential=self._credential,
            subscription_id=self._subscription_id
        )
    
    # =========================================================================
    # Virtual Machine Operations
    # =========================================================================
    
    async def vm_list(
        self,
        resource_group: str | None = None
    ) -> list[AzureVM]:
        """
        List Azure Virtual Machines.
        
        Args:
            resource_group: Resource group name (optional, lists from all if not specified)
        
        Returns:
            List of AzureVM dataclass objects
        """
        def _list():
            client = self._get_compute_client()
            vms = []
            
            if resource_group:
                vm_list = client.virtual_machines.list(resource_group)
            else:
                vm_list = client.virtual_machines.list_all()
            
            for vm in vm_list:
                # Parse resource group from ID
                rg = vm.id.split('/')[4] if vm.id else resource_group or ''
                
                # Get power state (requires instance view)
                power_state = None
                try:
                    instance_view = client.virtual_machines.instance_view(rg, vm.name)
                    for status in instance_view.statuses or []:
                        if status.code and status.code.startswith('PowerState/'):
                            power_state = status.code.replace('PowerState/', '')
                            break
                except Exception:
                    pass
                
                os_type = None
                if vm.storage_profile and vm.storage_profile.os_disk:
                    os_type = vm.storage_profile.os_disk.os_type
                
                vms.append(AzureVM(
                    name=vm.name,
                    resource_group=rg,
                    location=vm.location,
                    vm_size=vm.hardware_profile.vm_size if vm.hardware_profile else '',
                    provisioning_state=vm.provisioning_state or '',
                    power_state=power_state,
                    os_type=str(os_type) if os_type else None,
                    tags=dict(vm.tags) if vm.tags else {}
                ))
            
            return vms
        
        return await self._retry_with_backoff('vm_list', _list)
    
    async def vm_start(
        self,
        resource_group: str | None = None,
        vm_name: str = ''
    ) -> dict[str, Any]:
        """
        Start an Azure Virtual Machine.
        
        Args:
            resource_group: Resource group name
            vm_name: VM name
        
        Returns:
            Dict with operation result
        """
        resource_group = resource_group or self._resource_group
        
        if not resource_group or not vm_name:
            raise SkillExecutionError(
                skill_name='azure',
                method='vm_start',
                reason='Resource group and VM name required'
            )
        
        def _start():
            client = self._get_compute_client()
            
            # Start VM (async operation)
            poller = client.virtual_machines.begin_start(resource_group, vm_name)
            poller.wait()  # Wait for completion
            
            return {
                'vm_name': vm_name,
                'resource_group': resource_group,
                'status': 'Started',
                'success': True
            }
        
        return await self._retry_with_backoff('vm_start', _start)
    
    async def vm_stop(
        self,
        resource_group: str | None = None,
        vm_name: str = '',
        deallocate: bool = True
    ) -> dict[str, Any]:
        """
        Stop an Azure Virtual Machine.
        
        Args:
            resource_group: Resource group name
            vm_name: VM name
            deallocate: If True, deallocates VM (stops billing). If False, just powers off.
        
        Returns:
            Dict with operation result
        """
        resource_group = resource_group or self._resource_group
        
        if not resource_group or not vm_name:
            raise SkillExecutionError(
                skill_name='azure',
                method='vm_stop',
                reason='Resource group and VM name required'
            )
        
        def _stop():
            client = self._get_compute_client()
            
            if deallocate:
                poller = client.virtual_machines.begin_deallocate(resource_group, vm_name)
            else:
                poller = client.virtual_machines.begin_power_off(resource_group, vm_name)
            
            poller.wait()  # Wait for completion
            
            return {
                'vm_name': vm_name,
                'resource_group': resource_group,
                'status': 'Deallocated' if deallocate else 'Stopped',
                'success': True
            }
        
        return await self._retry_with_backoff('vm_stop', _stop)
    
    # =========================================================================
    # AKS Operations
    # =========================================================================
    
    async def aks_list_clusters(
        self,
        resource_group: str | None = None
    ) -> list[AKSCluster]:
        """
        List AKS clusters.
        
        Args:
            resource_group: Resource group name (optional, lists from all if not specified)
        
        Returns:
            List of AKSCluster dataclass objects
        """
        def _list():
            client = self._get_aks_client()
            clusters = []
            
            if resource_group:
                cluster_list = client.managed_clusters.list_by_resource_group(resource_group)
            else:
                cluster_list = client.managed_clusters.list()
            
            for cluster in cluster_list:
                # Parse resource group from ID
                rg = cluster.id.split('/')[4] if cluster.id else resource_group or ''
                
                # Count nodes
                node_count = sum(
                    (pool.count or 0) for pool in (cluster.agent_pool_profiles or [])
                )
                
                # Build node pool info
                node_pools = []
                for pool in cluster.agent_pool_profiles or []:
                    node_pools.append({
                        'name': pool.name,
                        'vm_size': pool.vm_size,
                        'count': pool.count,
                        'mode': pool.mode,
                        'os_type': pool.os_type,
                        'autoscaling': {
                            'enabled': pool.enable_auto_scaling or False,
                            'min': pool.min_count,
                            'max': pool.max_count
                        }
                    })
                
                clusters.append(AKSCluster(
                    name=cluster.name,
                    resource_group=rg,
                    location=cluster.location,
                    kubernetes_version=cluster.kubernetes_version or '',
                    provisioning_state=cluster.provisioning_state or '',
                    fqdn=cluster.fqdn,
                    node_count=node_count,
                    node_pools=node_pools,
                    tags=dict(cluster.tags) if cluster.tags else {}
                ))
            
            return clusters
        
        return await self._retry_with_backoff('aks_list_clusters', _list)
    
    async def aks_get_credentials(
        self,
        resource_group: str | None = None,
        cluster: str = '',
        admin: bool = False
    ) -> dict[str, Any]:
        """
        Get AKS cluster credentials (kubeconfig).
        
        Args:
            resource_group: Resource group name
            cluster: Cluster name
            admin: If True, get admin credentials
        
        Returns:
            Dict with kubeconfig data
        """
        resource_group = resource_group or self._resource_group
        
        if not resource_group or not cluster:
            raise SkillExecutionError(
                skill_name='azure',
                method='aks_get_credentials',
                reason='Resource group and cluster name required'
            )
        
        def _get_creds():
            client = self._get_aks_client()
            
            if admin:
                creds = client.managed_clusters.list_cluster_admin_credentials(
                    resource_group, cluster
                )
            else:
                creds = client.managed_clusters.list_cluster_user_credentials(
                    resource_group, cluster
                )
            
            # Decode kubeconfig
            kubeconfigs = []
            for kc in creds.kubeconfigs or []:
                kubeconfig_data = base64.b64decode(kc.value).decode('utf-8')
                kubeconfigs.append({
                    'name': kc.name,
                    'kubeconfig': kubeconfig_data
                })
            
            return {
                'cluster': cluster,
                'resource_group': resource_group,
                'admin': admin,
                'kubeconfigs': kubeconfigs,
                'success': len(kubeconfigs) > 0
            }
        
        return await self._retry_with_backoff('aks_get_credentials', _get_creds)
    
    # =========================================================================
    # Monitor Operations (Log Analytics)
    # =========================================================================
    
    async def monitor_query(
        self,
        workspace_id: str,
        query: str,
        timespan: timedelta | None = None,
        additional_workspaces: list[str] | None = None
    ) -> LogQueryResult:
        """
        Run a KQL query against Log Analytics workspace.
        
        Args:
            workspace_id: Log Analytics workspace ID
            query: KQL query string
            timespan: Time range for query (default: last 24 hours)
            additional_workspaces: Additional workspace IDs to query
        
        Returns:
            LogQueryResult dataclass with query results
        """
        if not workspace_id or not query:
            raise SkillExecutionError(
                skill_name='azure',
                method='monitor_query',
                reason='Workspace ID and query required'
            )
        
        def _query():
            client = LogsQueryClient(credential=self._credential)
            
            response = client.query_workspace(
                workspace_id=workspace_id,
                query=query,
                timespan=timespan or timedelta(hours=24),
                additional_workspaces=additional_workspaces
            )
            
            # Check status
            if response.status == LogsQueryStatus.PARTIAL:
                status = "Partial"
            elif response.status == LogsQueryStatus.SUCCESS:
                status = "Success"
            else:
                status = "Failed"
            
            # Parse tables
            tables = []
            for table in response.tables:
                columns = [col.name for col in table.columns]
                rows = []
                for row in table.rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert datetime to ISO format
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[col] = value
                    rows.append(row_dict)
                
                tables.append({
                    'name': table.name,
                    'columns': columns,
                    'rows': rows,
                    'row_count': len(rows)
                })
            
            return LogQueryResult(
                tables=tables,
                statistics=dict(response.statistics) if response.statistics else None,
                status=status
            )
        
        return await self._retry_with_backoff('monitor_query', _query)
    
    # =========================================================================
    # Application Insights Operations
    # =========================================================================
    
    async def app_insights_query(
        self,
        app_id: str,
        query: str,
        timespan: timedelta | None = None,
        additional_apps: list[str] | None = None
    ) -> LogQueryResult:
        """
        Run a KQL query against Application Insights.
        
        Args:
            app_id: Application Insights app ID
            query: KQL query string
            timespan: Time range for query (default: last 24 hours)
            additional_apps: Additional app IDs to query
        
        Returns:
            LogQueryResult dataclass with query results
        """
        if not app_id or not query:
            raise SkillExecutionError(
                skill_name='azure',
                method='app_insights_query',
                reason='App ID and query required'
            )
        
        def _query():
            client = LogsQueryClient(credential=self._credential)
            
            # App Insights uses the same query endpoint but with app:// prefix
            response = client.query_workspace(
                workspace_id=app_id,
                query=query,
                timespan=timespan or timedelta(hours=24),
                additional_workspaces=[f"app:{a}" for a in (additional_apps or [])]
            )
            
            # Check status
            if response.status == LogsQueryStatus.PARTIAL:
                status = "Partial"
            elif response.status == LogsQueryStatus.SUCCESS:
                status = "Success"
            else:
                status = "Failed"
            
            # Parse tables
            tables = []
            for table in response.tables:
                columns = [col.name for col in table.columns]
                rows = []
                for row in table.rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[col] = value
                    rows.append(row_dict)
                
                tables.append({
                    'name': table.name,
                    'columns': columns,
                    'rows': rows,
                    'row_count': len(rows)
                })
            
            return LogQueryResult(
                tables=tables,
                statistics=dict(response.statistics) if response.statistics else None,
                status=status
            )
        
        return await self._retry_with_backoff('app_insights_query', _query)
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> dict[str, Any]:
        """
        Check Azure connectivity by listing resource groups.
        
        Returns:
            Dict with connection status
        """
        def _check():
            if not self._subscription_id:
                return {
                    'status': 'not_configured',
                    'error': 'No subscription ID configured'
                }
            
            client = ResourceManagementClient(
                credential=self._credential,
                subscription_id=self._subscription_id
            )
            
            # Try to list resource groups (limited to 1)
            rgs = list(client.resource_groups.list())
            
            return {
                'status': 'connected',
                'subscription_id': self._subscription_id,
                'resource_group_count': len(rgs),
                'sample_resource_groups': [rg.name for rg in rgs[:3]]
            }
        
        try:
            return await self._run_sync(_check)
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'configured': self._credential is not None
            }
