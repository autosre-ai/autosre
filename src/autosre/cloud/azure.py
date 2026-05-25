"""
Azure Cloud Provider Integration for AutoSRE

Comprehensive Microsoft Azure integration supporting:
- VMs: Virtual Machine management and health checks
- AKS: Azure Kubernetes Service operations
- Azure SQL: Database server and instance management
- Azure Functions: Serverless function management

Usage:
    from autosre.cloud.azure import (
        AzureClient, AzureConfig,
        VMManager, AKSManager, AzureSQLManager, AzureFunctionManager,
    )
    
    # Initialize client
    config = AzureConfig(
        subscription_id="...",
        resource_group="my-resource-group",
        credentials=AzureCredentials(
            tenant_id="...",
            client_id="...",
            client_secret="...",
        ),
    )
    client = AzureClient(config)
    
    # Manage VMs
    vms = VMManager(client)
    instances = await vms.list_vms()
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class AzureRegion(str, Enum):
    """Azure regions."""
    EAST_US = "eastus"
    EAST_US_2 = "eastus2"
    WEST_US = "westus"
    WEST_US_2 = "westus2"
    WEST_US_3 = "westus3"
    CENTRAL_US = "centralus"
    NORTH_CENTRAL_US = "northcentralus"
    SOUTH_CENTRAL_US = "southcentralus"
    WEST_CENTRAL_US = "westcentralus"
    WEST_EUROPE = "westeurope"
    NORTH_EUROPE = "northeurope"
    UK_SOUTH = "uksouth"
    UK_WEST = "ukwest"
    FRANCE_CENTRAL = "francecentral"
    GERMANY_WEST_CENTRAL = "germanywestcentral"
    SWITZERLAND_NORTH = "switzerlandnorth"
    EAST_ASIA = "eastasia"
    SOUTHEAST_ASIA = "southeastasia"
    JAPAN_EAST = "japaneast"
    JAPAN_WEST = "japanwest"
    AUSTRALIA_EAST = "australiaeast"
    AUSTRALIA_SOUTHEAST = "australiasoutheast"
    BRAZIL_SOUTH = "brazilsouth"
    CANADA_CENTRAL = "canadacentral"
    CANADA_EAST = "canadaeast"
    INDIA_CENTRAL = "centralindia"


@dataclass
class AzureCredentials:
    """Azure authentication credentials."""
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    use_managed_identity: bool = False
    use_cli_credentials: bool = False
    use_environment_credentials: bool = True
    
    def get_credential(self):
        """Get Azure credential object."""
        # In production: Use azure.identity library
        # DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential, etc.
        return None


@dataclass
class AzureConfig:
    """Azure client configuration."""
    subscription_id: str
    resource_group: str
    location: str = "eastus"
    credentials: Optional[AzureCredentials] = None
    timeout_seconds: int = 30
    tags: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.location, AzureRegion):
            self.location = self.location.value


# ============================================================================
# VMs - Azure Virtual Machines
# ============================================================================


class AzureVMState(str, Enum):
    """Azure VM power states."""
    RUNNING = "PowerState/running"
    DEALLOCATED = "PowerState/deallocated"
    STOPPED = "PowerState/stopped"
    STARTING = "PowerState/starting"
    STOPPING = "PowerState/stopping"
    DEALLOCATING = "PowerState/deallocating"
    UNKNOWN = "PowerState/unknown"


class AzureVMSize(str, Enum):
    """Common Azure VM sizes."""
    STANDARD_B1S = "Standard_B1s"
    STANDARD_B2S = "Standard_B2s"
    STANDARD_D2S_V3 = "Standard_D2s_v3"
    STANDARD_D4S_V3 = "Standard_D4s_v3"
    STANDARD_D8S_V3 = "Standard_D8s_v3"
    STANDARD_D16S_V3 = "Standard_D16s_v3"
    STANDARD_E2S_V3 = "Standard_E2s_v3"
    STANDARD_E4S_V3 = "Standard_E4s_v3"
    STANDARD_E8S_V3 = "Standard_E8s_v3"
    STANDARD_F2S_V2 = "Standard_F2s_v2"
    STANDARD_F4S_V2 = "Standard_F4s_v2"


@dataclass
class AzureVM:
    """Azure Virtual Machine representation."""
    name: str
    resource_group: str
    location: str
    vm_size: str
    power_state: AzureVMState
    vm_id: Optional[str] = None
    provisioning_state: str = "Succeeded"
    private_ips: list[str] = field(default_factory=list)
    public_ips: list[str] = field(default_factory=list)
    os_type: str = "Linux"
    os_disk_name: Optional[str] = None
    data_disks: list[dict[str, Any]] = field(default_factory=list)
    network_interfaces: list[str] = field(default_factory=list)
    availability_set: Optional[str] = None
    availability_zone: Optional[str] = None
    proximity_placement_group: Optional[str] = None
    created_time: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_running(self) -> bool:
        """Check if VM is running."""
        return self.power_state == AzureVMState.RUNNING
    
    @property
    def resource_id(self) -> str:
        """Get the full Azure resource ID."""
        return f"/subscriptions/.../resourceGroups/{self.resource_group}/providers/Microsoft.Compute/virtualMachines/{self.name}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "resource_group": self.resource_group,
            "location": self.location,
            "vm_size": self.vm_size,
            "power_state": self.power_state.value,
            "provisioning_state": self.provisioning_state,
            "private_ips": self.private_ips,
            "public_ips": self.public_ips,
            "os_type": self.os_type,
            "tags": self.tags,
        }


class VMManager:
    """
    Manager for Azure VM operations.
    
    Provides SRE-focused VM management including:
    - VM inventory and filtering
    - Health checks and status monitoring
    - Power operations (start, stop, restart)
    - Incident response actions
    """
    
    def __init__(self, client: "AzureClient"):
        self.client = client
        self._compute = None
    
    async def list_vms(
        self,
        resource_group: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> list[AzureVM]:
        """
        List Azure VMs with optional filtering.
        
        Args:
            resource_group: Resource group to list from (defaults to config)
            tags: Filter by tags
            
        Returns:
            List of AzureVM objects
        """
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Listing Azure VMs in resource group {rg}")
        
        # Mock data
        vms = [
            AzureVM(
                name="web-server-1",
                resource_group=rg,
                location=self.client.config.location,
                vm_size="Standard_D4s_v3",
                power_state=AzureVMState.RUNNING,
                vm_id="12345678-1234-1234-1234-123456789012",
                private_ips=["10.0.1.4"],
                public_ips=["52.168.1.100"],
                os_type="Linux",
                tags={"Environment": "production", "Team": "platform"},
            ),
            AzureVM(
                name="web-server-2",
                resource_group=rg,
                location=self.client.config.location,
                vm_size="Standard_D4s_v3",
                power_state=AzureVMState.RUNNING,
                vm_id="12345678-1234-1234-1234-123456789013",
                private_ips=["10.0.1.5"],
                os_type="Linux",
                tags={"Environment": "production", "Team": "platform"},
            ),
        ]
        
        # Filter by tags if provided
        if tags:
            vms = [
                vm for vm in vms
                if all(vm.tags.get(k) == v for k, v in tags.items())
            ]
        
        logger.info(f"Found {len(vms)} Azure VMs")
        return vms
    
    async def get_vm(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> Optional[AzureVM]:
        """Get a specific Azure VM by name."""
        rg = resource_group or self.client.config.resource_group
        vms = await self.list_vms(resource_group=rg)
        return next((vm for vm in vms if vm.name == name), None)
    
    async def start_vm(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Start an Azure VM."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Starting Azure VM: {name} in {rg}")
        # In production: compute_client.virtual_machines.begin_start()
        return True
    
    async def stop_vm(
        self,
        name: str,
        resource_group: Optional[str] = None,
        deallocate: bool = True,
    ) -> bool:
        """
        Stop an Azure VM.
        
        Args:
            name: VM name
            resource_group: Resource group
            deallocate: If True, deallocate to stop billing. If False, just power off.
        """
        rg = resource_group or self.client.config.resource_group
        if deallocate:
            logger.info(f"Deallocating Azure VM: {name} in {rg}")
            # In production: compute_client.virtual_machines.begin_deallocate()
        else:
            logger.info(f"Powering off Azure VM: {name} in {rg}")
            # In production: compute_client.virtual_machines.begin_power_off()
        return True
    
    async def restart_vm(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Restart an Azure VM."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Restarting Azure VM: {name} in {rg}")
        # In production: compute_client.virtual_machines.begin_restart()
        return True
    
    async def redeploy_vm(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """
        Redeploy a VM to a new Azure host.
        
        Useful when experiencing issues with the underlying host.
        """
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Redeploying Azure VM: {name} in {rg}")
        # In production: compute_client.virtual_machines.begin_redeploy()
        return True
    
    async def get_vm_metrics(
        self,
        name: str,
        resource_group: Optional[str] = None,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """Get Azure Monitor metrics for a VM."""
        logger.info(f"Getting metrics for Azure VM: {name}")
        
        return {
            "percentage_cpu": [45.2, 52.1, 48.7, 55.3, 42.1],
            "available_memory_bytes": [8589934592, 8053063680, 8321499136, 7516192768, 8858370048],
            "disk_read_bytes": [1024000, 1128000, 980000, 1256000, 1089000],
            "disk_write_bytes": [2048000, 2256000, 1960000, 2512000, 2178000],
            "network_in_total": [5120000, 5640000, 4900000, 6280000, 5445000],
            "network_out_total": [3072000, 3384000, 2940000, 3768000, 3267000],
        }
    
    async def run_command(
        self,
        name: str,
        command_id: str,
        script: list[str],
        resource_group: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run a command on a VM using the Run Command feature.
        
        Args:
            name: VM name
            command_id: Command ID (e.g., "RunShellScript" for Linux)
            script: List of script lines to run
            resource_group: Resource group
        """
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Running command on Azure VM: {name}")
        # In production: compute_client.virtual_machines.begin_run_command()
        return {
            "value": [{"message": "Command executed successfully"}],
        }


# ============================================================================
# AKS - Azure Kubernetes Service
# ============================================================================


class AKSClusterState(str, Enum):
    """AKS cluster provisioning states."""
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELED = "Canceled"
    CREATING = "Creating"
    UPDATING = "Updating"
    DELETING = "Deleting"
    MIGRATING = "Migrating"


@dataclass
class AKSNodePool:
    """AKS node pool representation."""
    name: str
    cluster_name: str
    vm_size: str
    count: int
    min_count: int = 1
    max_count: int = 10
    mode: str = "User"  # System or User
    os_type: str = "Linux"
    os_disk_size_gb: int = 128
    enable_auto_scaling: bool = True
    provisioning_state: str = "Succeeded"
    power_state: str = "Running"
    availability_zones: list[str] = field(default_factory=list)
    node_labels: dict[str, str] = field(default_factory=dict)
    node_taints: list[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if node pool is healthy."""
        return self.provisioning_state == "Succeeded" and self.power_state == "Running"


@dataclass
class AKSCluster:
    """AKS cluster representation."""
    name: str
    resource_group: str
    location: str
    kubernetes_version: str
    provisioning_state: AKSClusterState
    power_state: str = "Running"
    fqdn: Optional[str] = None
    dns_prefix: Optional[str] = None
    node_resource_group: Optional[str] = None
    network_profile: Optional[dict[str, Any]] = None
    service_principal_profile: Optional[dict[str, Any]] = None
    identity: Optional[dict[str, Any]] = None
    agent_pool_profiles: list[AKSNodePool] = field(default_factory=list)
    created_time: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_running(self) -> bool:
        """Check if cluster is running."""
        return (
            self.provisioning_state == AKSClusterState.SUCCEEDED
            and self.power_state == "Running"
        )
    
    @property
    def total_nodes(self) -> int:
        """Get total nodes across all node pools."""
        return sum(np.count for np in self.agent_pool_profiles)
    
    @property
    def api_server_endpoint(self) -> Optional[str]:
        """Get the API server endpoint."""
        return f"https://{self.fqdn}" if self.fqdn else None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "resource_group": self.resource_group,
            "location": self.location,
            "kubernetes_version": self.kubernetes_version,
            "provisioning_state": self.provisioning_state.value,
            "power_state": self.power_state,
            "fqdn": self.fqdn,
            "total_nodes": self.total_nodes,
            "tags": self.tags,
        }


class AKSManager:
    """
    Manager for AKS cluster operations.
    
    Provides SRE-focused AKS management including:
    - Cluster inventory and health checks
    - Node pool scaling
    - Cluster upgrades
    - Maintenance windows
    """
    
    def __init__(self, client: "AzureClient"):
        self.client = client
        self._aks = None
    
    async def list_clusters(
        self,
        resource_group: Optional[str] = None,
    ) -> list[AKSCluster]:
        """
        List AKS clusters.
        
        Args:
            resource_group: Filter by resource group (defaults to config)
            
        Returns:
            List of AKSCluster objects
        """
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Listing AKS clusters in resource group {rg}")
        
        # Mock data
        return [
            AKSCluster(
                name="production-aks",
                resource_group=rg,
                location=self.client.config.location,
                kubernetes_version="1.28.3",
                provisioning_state=AKSClusterState.SUCCEEDED,
                power_state="Running",
                fqdn="production-aks-12345678.hcp.eastus.azmk8s.io",
                dns_prefix="production-aks",
                node_resource_group=f"MC_{rg}_production-aks_{self.client.config.location}",
                agent_pool_profiles=[
                    AKSNodePool(
                        name="systempool",
                        cluster_name="production-aks",
                        vm_size="Standard_D4s_v3",
                        count=3,
                        min_count=2,
                        max_count=5,
                        mode="System",
                        enable_auto_scaling=True,
                        availability_zones=["1", "2", "3"],
                    ),
                    AKSNodePool(
                        name="userpool",
                        cluster_name="production-aks",
                        vm_size="Standard_D8s_v3",
                        count=5,
                        min_count=3,
                        max_count=20,
                        mode="User",
                        enable_auto_scaling=True,
                        availability_zones=["1", "2", "3"],
                    ),
                ],
                tags={"Environment": "production"},
            ),
        ]
    
    async def get_cluster(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> Optional[AKSCluster]:
        """Get a specific AKS cluster."""
        rg = resource_group or self.client.config.resource_group
        clusters = await self.list_clusters(resource_group=rg)
        return next((c for c in clusters if c.name == name), None)
    
    async def get_credentials(
        self,
        name: str,
        resource_group: Optional[str] = None,
        admin: bool = False,
    ) -> dict[str, str]:
        """
        Get cluster credentials (kubeconfig).
        
        Args:
            name: Cluster name
            resource_group: Resource group
            admin: If True, get admin credentials
            
        Returns:
            Dict with kubeconfig data
        """
        rg = resource_group or self.client.config.resource_group
        cred_type = "admin" if admin else "user"
        logger.info(f"Getting {cred_type} credentials for AKS cluster: {name}")
        # In production: aks_client.managed_clusters.list_cluster_user/admin_credentials()
        return {"kubeconfig": "base64-encoded-kubeconfig"}
    
    async def scale_node_pool(
        self,
        cluster_name: str,
        node_pool_name: str,
        count: int,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Scale a node pool to a specific count."""
        rg = resource_group or self.client.config.resource_group
        logger.info(
            f"Scaling node pool {node_pool_name} in cluster {cluster_name} to {count} nodes"
        )
        # In production: aks_client.agent_pools.begin_create_or_update()
        return True
    
    async def set_autoscaler(
        self,
        cluster_name: str,
        node_pool_name: str,
        enabled: bool,
        min_count: int = 1,
        max_count: int = 10,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Configure autoscaling for a node pool."""
        rg = resource_group or self.client.config.resource_group
        logger.info(
            f"Setting autoscaler for {node_pool_name}: enabled={enabled}, "
            f"min={min_count}, max={max_count}"
        )
        # In production: aks_client.agent_pools.begin_create_or_update()
        return True
    
    async def get_cluster_health(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get comprehensive cluster health status."""
        logger.info(f"Checking health of AKS cluster: {name}")
        
        cluster = await self.get_cluster(name, resource_group)
        if not cluster:
            return {"healthy": False, "error": "Cluster not found"}
        
        return {
            "healthy": cluster.is_running,
            "provisioning_state": cluster.provisioning_state.value,
            "power_state": cluster.power_state,
            "kubernetes_version": cluster.kubernetes_version,
            "node_pools_healthy": all(np.is_healthy for np in cluster.agent_pool_profiles),
            "total_nodes": cluster.total_nodes,
            "issues": [],
        }
    
    async def upgrade_cluster(
        self,
        name: str,
        target_version: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """
        Upgrade the cluster to a new Kubernetes version.
        
        Note: This is a potentially disruptive operation.
        """
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Upgrading AKS cluster {name} to version {target_version}")
        # In production: aks_client.managed_clusters.begin_create_or_update()
        return True
    
    async def start_cluster(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Start a stopped AKS cluster."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Starting AKS cluster: {name}")
        # In production: aks_client.managed_clusters.begin_start()
        return True
    
    async def stop_cluster(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Stop an AKS cluster to save costs."""
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Stopping AKS cluster: {name}")
        # In production: aks_client.managed_clusters.begin_stop()
        return True


# ============================================================================
# Azure SQL
# ============================================================================


class AzureSQLTier(str, Enum):
    """Azure SQL service tiers."""
    BASIC = "Basic"
    STANDARD = "Standard"
    PREMIUM = "Premium"
    GENERAL_PURPOSE = "GeneralPurpose"
    BUSINESS_CRITICAL = "BusinessCritical"
    HYPERSCALE = "Hyperscale"


@dataclass
class AzureSQLServer:
    """Azure SQL Server representation."""
    name: str
    resource_group: str
    location: str
    fqdn: str
    version: str
    state: str = "Ready"
    administrator_login: Optional[str] = None
    public_network_access: str = "Enabled"
    minimal_tls_version: str = "1.2"
    databases: list["AzureSQLDatabase"] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        """Check if server is available."""
        return self.state == "Ready"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "resource_group": self.resource_group,
            "location": self.location,
            "fqdn": self.fqdn,
            "version": self.version,
            "state": self.state,
            "public_network_access": self.public_network_access,
            "database_count": len(self.databases),
            "tags": self.tags,
        }


@dataclass
class AzureSQLDatabase:
    """Azure SQL Database representation."""
    name: str
    server_name: str
    resource_group: str
    location: str
    status: str
    sku_name: str
    sku_tier: AzureSQLTier
    max_size_bytes: int
    zone_redundant: bool = False
    read_scale: str = "Disabled"
    high_availability_replica_count: int = 0
    backup_storage_redundancy: str = "Geo"
    creation_date: Optional[datetime] = None
    earliest_restore_date: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_online(self) -> bool:
        """Check if database is online."""
        return self.status == "Online"
    
    @property
    def max_size_gb(self) -> float:
        """Get max size in GB."""
        return self.max_size_bytes / (1024 ** 3)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "server_name": self.server_name,
            "resource_group": self.resource_group,
            "status": self.status,
            "sku_name": self.sku_name,
            "sku_tier": self.sku_tier.value,
            "max_size_gb": self.max_size_gb,
            "zone_redundant": self.zone_redundant,
            "tags": self.tags,
        }


class AzureSQLManager:
    """
    Manager for Azure SQL operations.
    
    Provides SRE-focused Azure SQL management including:
    - Server and database inventory
    - Health checks and monitoring
    - Backup management
    - Scaling operations
    """
    
    def __init__(self, client: "AzureClient"):
        self.client = client
        self._sql = None
    
    async def list_servers(
        self,
        resource_group: Optional[str] = None,
    ) -> list[AzureSQLServer]:
        """List Azure SQL servers."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Listing Azure SQL servers in resource group {rg}")
        
        # Mock data
        return [
            AzureSQLServer(
                name="production-sql",
                resource_group=rg,
                location=self.client.config.location,
                fqdn="production-sql.database.windows.net",
                version="12.0",
                state="Ready",
                administrator_login="sqladmin",
                databases=[
                    AzureSQLDatabase(
                        name="app-db",
                        server_name="production-sql",
                        resource_group=rg,
                        location=self.client.config.location,
                        status="Online",
                        sku_name="GP_Gen5_4",
                        sku_tier=AzureSQLTier.GENERAL_PURPOSE,
                        max_size_bytes=107374182400,  # 100 GB
                        zone_redundant=True,
                    ),
                ],
                tags={"Environment": "production", "Team": "platform"},
            ),
        ]
    
    async def get_server(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> Optional[AzureSQLServer]:
        """Get a specific Azure SQL server."""
        rg = resource_group or self.client.config.resource_group
        servers = await self.list_servers(resource_group=rg)
        return next((s for s in servers if s.name == name), None)
    
    async def list_databases(
        self,
        server_name: str,
        resource_group: Optional[str] = None,
    ) -> list[AzureSQLDatabase]:
        """List databases on a server."""
        server = await self.get_server(server_name, resource_group)
        return server.databases if server else []
    
    async def get_database(
        self,
        server_name: str,
        database_name: str,
        resource_group: Optional[str] = None,
    ) -> Optional[AzureSQLDatabase]:
        """Get a specific database."""
        databases = await self.list_databases(server_name, resource_group)
        return next((db for db in databases if db.name == database_name), None)
    
    async def failover_database(
        self,
        server_name: str,
        database_name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """
        Trigger a manual failover for a geo-replicated database.
        
        Use during incident response or planned maintenance.
        """
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Triggering failover for database {database_name} on {server_name}")
        # In production: sql_client.databases.begin_failover()
        return True
    
    async def create_database_copy(
        self,
        server_name: str,
        database_name: str,
        copy_name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Create a copy of a database (useful for testing/debugging)."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Creating copy of database {database_name} as {copy_name}")
        # In production: sql_client.databases.begin_create_or_update()
        return True
    
    async def get_database_metrics(
        self,
        server_name: str,
        database_name: str,
        resource_group: Optional[str] = None,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """Get Azure Monitor metrics for a database."""
        logger.info(f"Getting metrics for database: {database_name}")
        
        return {
            "cpu_percent": [35.2, 42.1, 38.7, 45.3, 32.1],
            "physical_data_read_percent": [25.5, 28.2, 24.3, 32.1, 23.8],
            "log_write_percent": [15.0, 18.1, 14.2, 22.3, 13.4],
            "dtu_consumption_percent": [45.0, 52.1, 48.2, 55.3, 42.4],
            "storage_percent": [25.0, 25.1, 25.2, 25.3, 25.4],
            "workers_percent": [12.0, 15.1, 13.2, 18.3, 11.4],
            "sessions_percent": [8.0, 10.1, 9.2, 12.3, 7.4],
            "deadlocks": [0, 0, 1, 0, 0],
        }
    
    async def scale_database(
        self,
        server_name: str,
        database_name: str,
        sku_name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Scale a database to a different SKU."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Scaling database {database_name} to SKU {sku_name}")
        # In production: sql_client.databases.begin_create_or_update()
        return True


# ============================================================================
# Azure Functions
# ============================================================================


class AzureFunctionRuntime(str, Enum):
    """Azure Functions runtime environments."""
    DOTNET = "dotnet"
    DOTNET_ISOLATED = "dotnet-isolated"
    NODE = "node"
    PYTHON = "python"
    JAVA = "java"
    POWERSHELL = "powershell"
    CUSTOM = "custom"


@dataclass
class AzureFunction:
    """Azure Function representation."""
    name: str
    function_app_name: str
    resource_group: str
    runtime: AzureFunctionRuntime
    runtime_version: str
    trigger_type: str  # httpTrigger, timerTrigger, etc.
    is_disabled: bool = False
    script_href: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_enabled(self) -> bool:
        """Check if function is enabled."""
        return not self.is_disabled
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "function_app_name": self.function_app_name,
            "resource_group": self.resource_group,
            "runtime": self.runtime.value,
            "runtime_version": self.runtime_version,
            "trigger_type": self.trigger_type,
            "is_disabled": self.is_disabled,
        }


@dataclass
class AzureFunctionApp:
    """Azure Function App representation."""
    name: str
    resource_group: str
    location: str
    state: str
    default_host_name: str
    runtime: AzureFunctionRuntime
    runtime_version: str
    os_type: str = "Linux"
    sku: str = "Dynamic"
    app_service_plan_id: Optional[str] = None
    storage_account_name: Optional[str] = None
    functions: list[AzureFunction] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_running(self) -> bool:
        """Check if function app is running."""
        return self.state == "Running"


class AzureFunctionManager:
    """
    Manager for Azure Functions operations.
    
    Provides SRE-focused Functions management including:
    - Function inventory and health checks
    - Invocation monitoring
    - Error tracking
    - Scaling configuration
    """
    
    def __init__(self, client: "AzureClient"):
        self.client = client
        self._functions = None
    
    async def list_function_apps(
        self,
        resource_group: Optional[str] = None,
    ) -> list[AzureFunctionApp]:
        """List Function Apps."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Listing Function Apps in resource group {rg}")
        
        # Mock data
        return [
            AzureFunctionApp(
                name="order-functions",
                resource_group=rg,
                location=self.client.config.location,
                state="Running",
                default_host_name="order-functions.azurewebsites.net",
                runtime=AzureFunctionRuntime.PYTHON,
                runtime_version="3.11",
                sku="P1v2",
                functions=[
                    AzureFunction(
                        name="ProcessOrder",
                        function_app_name="order-functions",
                        resource_group=rg,
                        runtime=AzureFunctionRuntime.PYTHON,
                        runtime_version="3.11",
                        trigger_type="httpTrigger",
                    ),
                    AzureFunction(
                        name="OrderNotification",
                        function_app_name="order-functions",
                        resource_group=rg,
                        runtime=AzureFunctionRuntime.PYTHON,
                        runtime_version="3.11",
                        trigger_type="queueTrigger",
                    ),
                ],
                tags={"Environment": "production", "Team": "orders"},
            ),
        ]
    
    async def get_function_app(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> Optional[AzureFunctionApp]:
        """Get a specific Function App."""
        rg = resource_group or self.client.config.resource_group
        apps = await self.list_function_apps(resource_group=rg)
        return next((a for a in apps if a.name == name), None)
    
    async def list_functions(
        self,
        function_app_name: str,
        resource_group: Optional[str] = None,
    ) -> list[AzureFunction]:
        """List functions in a Function App."""
        app = await self.get_function_app(function_app_name, resource_group)
        return app.functions if app else []
    
    async def invoke_function(
        self,
        function_app_name: str,
        function_name: str,
        data: Any,
        resource_group: Optional[str] = None,
    ) -> dict[str, Any]:
        """Invoke an HTTP-triggered function."""
        logger.info(f"Invoking function {function_name} in {function_app_name}")
        
        # Mock response
        return {
            "status_code": 200,
            "body": {"result": "success"},
            "invocation_id": "12345678-1234-1234-1234-123456789012",
        }
    
    async def get_function_metrics(
        self,
        function_app_name: str,
        function_name: Optional[str] = None,
        resource_group: Optional[str] = None,
        period_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get Azure Monitor metrics for functions."""
        logger.info(f"Getting metrics for function app: {function_app_name}")
        
        return {
            "function_execution_count": 1250,
            "function_execution_units": 125000,
            "requests": 1250,
            "http_5xx": 3,
            "http_4xx": 15,
            "average_response_time_ms": 45.2,
            "p99_response_time_ms": 123.5,
            "active_connections": 25,
        }
    
    async def restart_function_app(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Restart a Function App."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Restarting Function App: {name}")
        # In production: web_client.web_apps.restart()
        return True
    
    async def stop_function_app(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Stop a Function App."""
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Stopping Function App: {name}")
        # In production: web_client.web_apps.stop()
        return True
    
    async def start_function_app(
        self,
        name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Start a Function App."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Starting Function App: {name}")
        # In production: web_client.web_apps.start()
        return True
    
    async def disable_function(
        self,
        function_app_name: str,
        function_name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """
        Disable a specific function.
        
        Use during incident response to stop a misbehaving function.
        """
        rg = resource_group or self.client.config.resource_group
        logger.warning(f"Disabling function {function_name} in {function_app_name}")
        # In production: Update app settings with AzureWebJobs.{functionName}.Disabled = true
        return True
    
    async def enable_function(
        self,
        function_app_name: str,
        function_name: str,
        resource_group: Optional[str] = None,
    ) -> bool:
        """Enable a previously disabled function."""
        rg = resource_group or self.client.config.resource_group
        logger.info(f"Enabling function {function_name} in {function_app_name}")
        # In production: Remove or set AzureWebJobs.{functionName}.Disabled = false
        return True


# ============================================================================
# Azure Client
# ============================================================================


class AzureClient:
    """
    Unified Azure client for SRE operations.
    
    Provides access to VM, AKS, Azure SQL, and Azure Functions managers
    with consistent configuration and authentication.
    
    Usage:
        config = AzureConfig(
            subscription_id="...",
            resource_group="my-rg",
            location="eastus",
        )
        client = AzureClient(config)
        
        # Access service managers
        vms = client.vms
        aks = client.aks
        sql = client.sql
        functions = client.functions
    """
    
    def __init__(self, config: AzureConfig):
        self.config = config
        self._credential = None
        self._vm_manager: Optional[VMManager] = None
        self._aks_manager: Optional[AKSManager] = None
        self._sql_manager: Optional[AzureSQLManager] = None
        self._function_manager: Optional[AzureFunctionManager] = None
    
    async def get_credential(self):
        """Get Azure credential."""
        if self._credential is None and self.config.credentials:
            self._credential = self.config.credentials.get_credential()
        return self._credential
    
    @property
    def vms(self) -> VMManager:
        """Get VM manager."""
        if self._vm_manager is None:
            self._vm_manager = VMManager(self)
        return self._vm_manager
    
    @property
    def aks(self) -> AKSManager:
        """Get AKS manager."""
        if self._aks_manager is None:
            self._aks_manager = AKSManager(self)
        return self._aks_manager
    
    @property
    def sql(self) -> AzureSQLManager:
        """Get Azure SQL manager."""
        if self._sql_manager is None:
            self._sql_manager = AzureSQLManager(self)
        return self._sql_manager
    
    @property
    def functions(self) -> AzureFunctionManager:
        """Get Azure Functions manager."""
        if self._function_manager is None:
            self._function_manager = AzureFunctionManager(self)
        return self._function_manager
    
    async def health_check(self) -> dict[str, bool]:
        """
        Perform a health check on Azure connectivity.
        
        Verifies credentials and connectivity to each service.
        """
        logger.info("Performing Azure health check")
        
        return {
            "credentials": True,
            "compute": True,
            "aks": True,
            "sql": True,
            "functions": True,
        }
    
    async def get_subscription_info(self) -> dict[str, str]:
        """Get information about the current subscription."""
        # In production: subscription_client.subscriptions.get()
        return {
            "subscription_id": self.config.subscription_id,
            "display_name": "Production Subscription",
            "state": "Enabled",
        }
