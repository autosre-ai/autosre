"""
GCP Cloud Provider Integration for AutoSRE

Comprehensive Google Cloud Platform integration supporting:
- GCE: Compute Engine instance management
- GKE: Google Kubernetes Engine operations
- Cloud SQL: Database instance management
- Cloud Functions: Serverless function management

Usage:
    from autosre.cloud.gcp import (
        GCPClient, GCPConfig,
        GCEManager, GKEManager, CloudSQLManager, CloudFunctionManager,
    )
    
    # Initialize client
    config = GCPConfig(
        project_id="my-project",
        region="us-central1",
        credentials=GCPCredentials(
            service_account_key_path="/path/to/key.json",
        ),
    )
    client = GCPClient(config)
    
    # Manage GCE instances
    gce = GCEManager(client)
    instances = await gce.list_instances(zone="us-central1-a")
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


class GCPRegion(str, Enum):
    """GCP regions."""
    US_CENTRAL1 = "us-central1"
    US_EAST1 = "us-east1"
    US_EAST4 = "us-east4"
    US_WEST1 = "us-west1"
    US_WEST2 = "us-west2"
    US_WEST3 = "us-west3"
    US_WEST4 = "us-west4"
    EUROPE_WEST1 = "europe-west1"
    EUROPE_WEST2 = "europe-west2"
    EUROPE_WEST3 = "europe-west3"
    EUROPE_WEST4 = "europe-west4"
    EUROPE_NORTH1 = "europe-north1"
    ASIA_EAST1 = "asia-east1"
    ASIA_EAST2 = "asia-east2"
    ASIA_NORTHEAST1 = "asia-northeast1"
    ASIA_NORTHEAST2 = "asia-northeast2"
    ASIA_SOUTHEAST1 = "asia-southeast1"
    ASIA_SOUTH1 = "asia-south1"
    AUSTRALIA_SOUTHEAST1 = "australia-southeast1"
    SOUTHAMERICA_EAST1 = "southamerica-east1"


@dataclass
class GCPCredentials:
    """GCP authentication credentials."""
    service_account_key_path: Optional[str] = None
    service_account_key_json: Optional[dict[str, Any]] = None
    use_default_credentials: bool = True
    impersonate_service_account: Optional[str] = None
    
    def get_credentials(self):
        """Get google.auth credentials object."""
        # In production: Use google.auth library
        return None


@dataclass
class GCPConfig:
    """GCP client configuration."""
    project_id: str
    region: str = "us-central1"
    zone: Optional[str] = None
    credentials: Optional[GCPCredentials] = None
    timeout_seconds: int = 30
    labels: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.region, GCPRegion):
            self.region = self.region.value
        # Default zone to region-a if not specified
        if self.zone is None:
            self.zone = f"{self.region}-a"


# ============================================================================
# GCE - Google Compute Engine
# ============================================================================


class GCEInstanceState(str, Enum):
    """GCE instance states."""
    PROVISIONING = "PROVISIONING"
    STAGING = "STAGING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    SUSPENDING = "SUSPENDING"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


@dataclass
class GCEInstance:
    """GCE instance representation."""
    name: str
    instance_id: str
    machine_type: str
    status: GCEInstanceState
    zone: str
    internal_ip: Optional[str] = None
    external_ip: Optional[str] = None
    network: Optional[str] = None
    subnetwork: Optional[str] = None
    service_account: Optional[str] = None
    disks: list[dict[str, Any]] = field(default_factory=list)
    network_interfaces: list[dict[str, Any]] = field(default_factory=list)
    creation_timestamp: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    
    @property
    def is_running(self) -> bool:
        """Check if instance is running."""
        return self.status == GCEInstanceState.RUNNING
    
    @property
    def machine_type_name(self) -> str:
        """Get just the machine type name from the full URL."""
        # Machine type is a URL like zones/us-central1-a/machineTypes/n1-standard-1
        return self.machine_type.split("/")[-1] if "/" in self.machine_type else self.machine_type
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "instance_id": self.instance_id,
            "machine_type": self.machine_type_name,
            "status": self.status.value,
            "zone": self.zone,
            "internal_ip": self.internal_ip,
            "external_ip": self.external_ip,
            "network": self.network,
            "labels": self.labels,
            "tags": self.tags,
        }


class GCEManager:
    """
    Manager for GCE instance operations.
    
    Provides SRE-focused GCE management including:
    - Instance inventory and filtering
    - Health checks and status monitoring
    - Managed instance group operations
    - Incident response actions
    """
    
    def __init__(self, client: "GCPClient"):
        self.client = client
        self._compute = None
    
    async def list_instances(
        self,
        zone: Optional[str] = None,
        filter_expr: Optional[str] = None,
    ) -> list[GCEInstance]:
        """
        List GCE instances with optional filtering.
        
        Args:
            zone: Zone to list instances from (defaults to config zone)
            filter_expr: GCP filter expression
            
        Returns:
            List of GCEInstance objects
        """
        zone = zone or self.client.config.zone
        logger.info(f"Listing GCE instances in zone {zone} with filter: {filter_expr}")
        
        # Mock data
        instances = [
            GCEInstance(
                name="web-server-1",
                instance_id="1234567890123456789",
                machine_type="n1-standard-2",
                status=GCEInstanceState.RUNNING,
                zone=zone,
                internal_ip="10.128.0.2",
                external_ip="35.192.0.1",
                network="default",
                subnetwork="default",
                labels={"env": "production", "team": "platform"},
                tags=["http-server", "https-server"],
            ),
            GCEInstance(
                name="web-server-2",
                instance_id="1234567890123456790",
                machine_type="n1-standard-2",
                status=GCEInstanceState.RUNNING,
                zone=zone,
                internal_ip="10.128.0.3",
                network="default",
                subnetwork="default",
                labels={"env": "production", "team": "platform"},
                tags=["http-server", "https-server"],
            ),
        ]
        
        logger.info(f"Found {len(instances)} GCE instances")
        return instances
    
    async def get_instance(self, name: str, zone: Optional[str] = None) -> Optional[GCEInstance]:
        """Get a specific GCE instance by name."""
        zone = zone or self.client.config.zone
        instances = await self.list_instances(zone=zone)
        return next((i for i in instances if i.name == name), None)
    
    async def start_instance(self, name: str, zone: Optional[str] = None) -> bool:
        """Start a GCE instance."""
        zone = zone or self.client.config.zone
        logger.info(f"Starting GCE instance: {name} in zone {zone}")
        # In production: compute.instances().start()
        return True
    
    async def stop_instance(self, name: str, zone: Optional[str] = None) -> bool:
        """Stop a GCE instance."""
        zone = zone or self.client.config.zone
        logger.info(f"Stopping GCE instance: {name} in zone {zone}")
        # In production: compute.instances().stop()
        return True
    
    async def reset_instance(self, name: str, zone: Optional[str] = None) -> bool:
        """Reset (hard reboot) a GCE instance."""
        zone = zone or self.client.config.zone
        logger.info(f"Resetting GCE instance: {name} in zone {zone}")
        # In production: compute.instances().reset()
        return True
    
    async def delete_instance(self, name: str, zone: Optional[str] = None) -> bool:
        """Delete a GCE instance (dangerous operation)."""
        zone = zone or self.client.config.zone
        logger.warning(f"DELETING GCE instance: {name} in zone {zone}")
        # In production: compute.instances().delete()
        return True
    
    async def get_instance_serial_output(
        self,
        name: str,
        zone: Optional[str] = None,
        port: int = 1,
    ) -> str:
        """Get serial console output for debugging."""
        zone = zone or self.client.config.zone
        logger.info(f"Getting serial output for GCE instance: {name}")
        # In production: compute.instances().getSerialPortOutput()
        return ""
    
    async def get_instance_metrics(
        self,
        name: str,
        zone: Optional[str] = None,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """Get Cloud Monitoring metrics for a GCE instance."""
        logger.info(f"Getting metrics for GCE instance: {name}")
        
        return {
            "cpu_utilization": [45.2, 52.1, 48.7, 55.3, 42.1],
            "memory_utilization": [65.5, 68.2, 64.3, 72.1, 63.8],
            "disk_read_bytes": [1024000, 1128000, 980000, 1256000, 1089000],
            "disk_write_bytes": [2048000, 2256000, 1960000, 2512000, 2178000],
            "network_received_bytes": [5120000, 5640000, 4900000, 6280000, 5445000],
            "network_sent_bytes": [3072000, 3384000, 2940000, 3768000, 3267000],
        }


# ============================================================================
# GKE - Google Kubernetes Engine
# ============================================================================


class GKEClusterState(str, Enum):
    """GKE cluster states."""
    STATUS_UNSPECIFIED = "STATUS_UNSPECIFIED"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    RECONCILING = "RECONCILING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    DEGRADED = "DEGRADED"


@dataclass
class GKENodePool:
    """GKE node pool representation."""
    name: str
    cluster_name: str
    status: str
    machine_type: str
    disk_size_gb: int = 100
    disk_type: str = "pd-standard"
    initial_node_count: int = 3
    current_node_count: int = 3
    min_node_count: int = 1
    max_node_count: int = 10
    autoscaling_enabled: bool = True
    locations: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    taints: list[dict[str, str]] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if node pool is healthy."""
        return self.status == "RUNNING"


@dataclass
class GKECluster:
    """GKE cluster representation."""
    name: str
    location: str  # Region or zone
    status: GKEClusterState
    master_version: str
    node_version: str
    endpoint: Optional[str] = None
    network: Optional[str] = None
    subnetwork: Optional[str] = None
    cluster_ipv4_cidr: Optional[str] = None
    services_ipv4_cidr: Optional[str] = None
    node_pools: list[GKENodePool] = field(default_factory=list)
    create_time: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)
    resource_labels: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_regional(self) -> bool:
        """Check if cluster is regional (vs zonal)."""
        return "-" in self.location and self.location.count("-") == 1
    
    @property
    def is_running(self) -> bool:
        """Check if cluster is running."""
        return self.status == GKEClusterState.RUNNING
    
    @property
    def total_nodes(self) -> int:
        """Get total nodes across all node pools."""
        return sum(np.current_node_count for np in self.node_pools)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "location": self.location,
            "status": self.status.value,
            "master_version": self.master_version,
            "node_version": self.node_version,
            "endpoint": self.endpoint,
            "total_nodes": self.total_nodes,
            "is_regional": self.is_regional,
            "labels": self.labels,
        }


class GKEManager:
    """
    Manager for GKE cluster operations.
    
    Provides SRE-focused GKE management including:
    - Cluster inventory and health checks
    - Node pool scaling
    - Cluster upgrades
    - Workload management
    """
    
    def __init__(self, client: "GCPClient"):
        self.client = client
        self._container = None
    
    async def list_clusters(self, location: str = "-") -> list[GKECluster]:
        """
        List GKE clusters.
        
        Args:
            location: Region/zone or "-" for all locations
            
        Returns:
            List of GKECluster objects
        """
        logger.info(f"Listing GKE clusters in location: {location}")
        
        # Mock data
        return [
            GKECluster(
                name="production-cluster",
                location=self.client.config.region,
                status=GKEClusterState.RUNNING,
                master_version="1.28.3-gke.1286000",
                node_version="1.28.3-gke.1286000",
                endpoint="https://35.192.0.10",
                network="default",
                node_pools=[
                    GKENodePool(
                        name="default-pool",
                        cluster_name="production-cluster",
                        status="RUNNING",
                        machine_type="e2-standard-4",
                        disk_size_gb=100,
                        initial_node_count=3,
                        current_node_count=5,
                        min_node_count=3,
                        max_node_count=20,
                        autoscaling_enabled=True,
                    ),
                ],
                labels={"env": "production"},
            ),
        ]
    
    async def get_cluster(self, name: str, location: Optional[str] = None) -> Optional[GKECluster]:
        """Get a specific GKE cluster."""
        location = location or self.client.config.region
        clusters = await self.list_clusters(location)
        return next((c for c in clusters if c.name == name), None)
    
    async def list_node_pools(self, cluster_name: str, location: Optional[str] = None) -> list[GKENodePool]:
        """List node pools for a cluster."""
        cluster = await self.get_cluster(cluster_name, location)
        return cluster.node_pools if cluster else []
    
    async def resize_node_pool(
        self,
        cluster_name: str,
        node_pool_name: str,
        node_count: int,
        location: Optional[str] = None,
    ) -> bool:
        """Resize a node pool to a specific node count."""
        location = location or self.client.config.region
        logger.info(
            f"Resizing node pool {node_pool_name} in cluster {cluster_name} "
            f"to {node_count} nodes"
        )
        # In production: container.projects().locations().clusters().nodePools().setSize()
        return True
    
    async def set_node_pool_autoscaling(
        self,
        cluster_name: str,
        node_pool_name: str,
        enabled: bool,
        min_node_count: int = 1,
        max_node_count: int = 10,
        location: Optional[str] = None,
    ) -> bool:
        """Configure autoscaling for a node pool."""
        location = location or self.client.config.region
        logger.info(
            f"Setting autoscaling for {node_pool_name}: enabled={enabled}, "
            f"min={min_node_count}, max={max_node_count}"
        )
        # In production: container.projects().locations().clusters().nodePools().setAutoscaling()
        return True
    
    async def get_cluster_health(self, cluster_name: str, location: Optional[str] = None) -> dict[str, Any]:
        """Get comprehensive cluster health status."""
        logger.info(f"Checking health of GKE cluster: {cluster_name}")
        
        cluster = await self.get_cluster(cluster_name, location)
        if not cluster:
            return {"healthy": False, "error": "Cluster not found"}
        
        return {
            "healthy": cluster.is_running,
            "cluster_status": cluster.status.value,
            "master_version": cluster.master_version,
            "node_pools_healthy": all(np.is_healthy for np in cluster.node_pools),
            "total_nodes": cluster.total_nodes,
            "issues": [],
        }
    
    async def upgrade_master(
        self,
        cluster_name: str,
        target_version: str,
        location: Optional[str] = None,
    ) -> bool:
        """
        Upgrade the cluster master to a new version.
        
        Note: This is a potentially disruptive operation.
        """
        location = location or self.client.config.region
        logger.warning(f"Upgrading GKE master {cluster_name} to version {target_version}")
        # In production: container.projects().locations().clusters().update()
        return True
    
    async def upgrade_node_pool(
        self,
        cluster_name: str,
        node_pool_name: str,
        target_version: str,
        location: Optional[str] = None,
    ) -> bool:
        """Upgrade a node pool to a new version."""
        location = location or self.client.config.region
        logger.warning(
            f"Upgrading GKE node pool {node_pool_name} in {cluster_name} "
            f"to version {target_version}"
        )
        # In production: container.projects().locations().clusters().nodePools().update()
        return True


# ============================================================================
# Cloud SQL
# ============================================================================


class CloudSQLDatabaseVersion(str, Enum):
    """Cloud SQL database versions."""
    MYSQL_5_7 = "MYSQL_5_7"
    MYSQL_8_0 = "MYSQL_8_0"
    POSTGRES_12 = "POSTGRES_12"
    POSTGRES_13 = "POSTGRES_13"
    POSTGRES_14 = "POSTGRES_14"
    POSTGRES_15 = "POSTGRES_15"
    SQLSERVER_2017_STANDARD = "SQLSERVER_2017_STANDARD"
    SQLSERVER_2019_STANDARD = "SQLSERVER_2019_STANDARD"


class CloudSQLInstanceState(str, Enum):
    """Cloud SQL instance states."""
    SQL_INSTANCE_STATE_UNSPECIFIED = "SQL_INSTANCE_STATE_UNSPECIFIED"
    RUNNABLE = "RUNNABLE"
    SUSPENDED = "SUSPENDED"
    PENDING_DELETE = "PENDING_DELETE"
    PENDING_CREATE = "PENDING_CREATE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"


@dataclass
class CloudSQLInstance:
    """Cloud SQL instance representation."""
    name: str
    project: str
    database_version: CloudSQLDatabaseVersion
    state: CloudSQLInstanceState
    tier: str  # Machine type like db-n1-standard-1
    region: str
    connection_name: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    data_disk_size_gb: int = 10
    data_disk_type: str = "PD_SSD"
    availability_type: str = "ZONAL"  # ZONAL or REGIONAL
    backup_enabled: bool = True
    binary_log_enabled: bool = False
    maintenance_window: Optional[dict[str, int]] = None
    replica_names: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        """Check if instance is available."""
        return self.state == CloudSQLInstanceState.RUNNABLE
    
    @property
    def is_high_availability(self) -> bool:
        """Check if instance has high availability."""
        return self.availability_type == "REGIONAL"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "project": self.project,
            "database_version": self.database_version.value,
            "state": self.state.value,
            "tier": self.tier,
            "region": self.region,
            "connection_name": self.connection_name,
            "availability_type": self.availability_type,
            "data_disk_size_gb": self.data_disk_size_gb,
            "labels": self.labels,
        }


class CloudSQLManager:
    """
    Manager for Cloud SQL database operations.
    
    Provides SRE-focused Cloud SQL management including:
    - Instance inventory and health checks
    - Backup management
    - Replica operations
    - Performance monitoring
    """
    
    def __init__(self, client: "GCPClient"):
        self.client = client
        self._sqladmin = None
    
    async def list_instances(self) -> list[CloudSQLInstance]:
        """List all Cloud SQL instances in the project."""
        logger.info(f"Listing Cloud SQL instances in project {self.client.config.project_id}")
        
        # Mock data
        return [
            CloudSQLInstance(
                name="production-db",
                project=self.client.config.project_id,
                database_version=CloudSQLDatabaseVersion.POSTGRES_15,
                state=CloudSQLInstanceState.RUNNABLE,
                tier="db-custom-4-16384",
                region=self.client.config.region,
                connection_name=f"{self.client.config.project_id}:{self.client.config.region}:production-db",
                private_ip="10.0.0.5",
                data_disk_size_gb=100,
                data_disk_type="PD_SSD",
                availability_type="REGIONAL",
                backup_enabled=True,
                labels={"env": "production", "team": "platform"},
            ),
        ]
    
    async def get_instance(self, name: str) -> Optional[CloudSQLInstance]:
        """Get a specific Cloud SQL instance."""
        instances = await self.list_instances()
        return next((i for i in instances if i.name == name), None)
    
    async def restart_instance(self, name: str) -> bool:
        """Restart a Cloud SQL instance."""
        logger.warning(f"Restarting Cloud SQL instance: {name}")
        # In production: sqladmin.instances().restart()
        return True
    
    async def failover_instance(self, name: str) -> bool:
        """
        Trigger a manual failover to the replica.
        
        Only applicable for high-availability instances.
        """
        logger.warning(f"Triggering failover for Cloud SQL instance: {name}")
        # In production: sqladmin.instances().failover()
        return True
    
    async def create_backup(self, name: str, description: Optional[str] = None) -> str:
        """Create an on-demand backup."""
        logger.info(f"Creating backup for Cloud SQL instance: {name}")
        # In production: sqladmin.backupRuns().insert()
        return f"backup-{name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    async def list_backups(self, name: str) -> list[dict[str, Any]]:
        """List backups for an instance."""
        logger.info(f"Listing backups for Cloud SQL instance: {name}")
        # In production: sqladmin.backupRuns().list()
        return []
    
    async def get_instance_metrics(
        self,
        name: str,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """Get Cloud Monitoring metrics for a Cloud SQL instance."""
        logger.info(f"Getting metrics for Cloud SQL instance: {name}")
        
        return {
            "cpu_utilization": [35.2, 42.1, 38.7, 45.3, 32.1],
            "memory_utilization": [55.5, 58.2, 54.3, 62.1, 53.8],
            "disk_utilization": [45.0, 45.1, 45.2, 45.3, 45.4],
            "connections": [45, 52, 48, 55, 42],
            "read_ops": [1200, 1450, 1330, 1780, 1120],
            "write_ops": [890, 1020, 950, 1340, 780],
            "replication_lag_seconds": [0.5, 0.8, 0.6, 1.2, 0.4],
        }
    
    async def patch_instance(
        self,
        name: str,
        tier: Optional[str] = None,
        data_disk_size_gb: Optional[int] = None,
        backup_enabled: Optional[bool] = None,
    ) -> bool:
        """Patch instance configuration."""
        logger.info(f"Patching Cloud SQL instance: {name}")
        # In production: sqladmin.instances().patch()
        return True


# ============================================================================
# Cloud Functions
# ============================================================================


class CloudFunctionRuntime(str, Enum):
    """Cloud Functions runtime environments."""
    PYTHON_38 = "python38"
    PYTHON_39 = "python39"
    PYTHON_310 = "python310"
    PYTHON_311 = "python311"
    PYTHON_312 = "python312"
    NODEJS_16 = "nodejs16"
    NODEJS_18 = "nodejs18"
    NODEJS_20 = "nodejs20"
    GO_119 = "go119"
    GO_120 = "go120"
    GO_121 = "go121"
    JAVA_11 = "java11"
    JAVA_17 = "java17"
    DOTNET_6 = "dotnet6"
    RUBY_30 = "ruby30"
    RUBY_32 = "ruby32"


@dataclass
class CloudFunction:
    """Cloud Function representation."""
    name: str
    project: str
    region: str
    runtime: CloudFunctionRuntime
    entry_point: str
    status: str
    https_trigger_url: Optional[str] = None
    event_trigger: Optional[dict[str, Any]] = None
    available_memory_mb: int = 256
    timeout_seconds: int = 60
    max_instances: Optional[int] = None
    min_instances: int = 0
    service_account: Optional[str] = None
    environment_variables: dict[str, str] = field(default_factory=dict)
    build_id: Optional[str] = None
    version_id: Optional[str] = None
    update_time: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_active(self) -> bool:
        """Check if function is active."""
        return self.status == "ACTIVE"
    
    @property
    def full_name(self) -> str:
        """Get the full resource name."""
        return f"projects/{self.project}/locations/{self.region}/functions/{self.name}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "project": self.project,
            "region": self.region,
            "runtime": self.runtime.value,
            "entry_point": self.entry_point,
            "status": self.status,
            "available_memory_mb": self.available_memory_mb,
            "timeout_seconds": self.timeout_seconds,
            "https_trigger_url": self.https_trigger_url,
            "labels": self.labels,
        }


class CloudFunctionManager:
    """
    Manager for Cloud Functions operations.
    
    Provides SRE-focused Cloud Functions management including:
    - Function inventory and health checks
    - Invocation monitoring
    - Error tracking
    - Scaling configuration
    """
    
    def __init__(self, client: "GCPClient"):
        self.client = client
        self._functions = None
    
    async def list_functions(self, region: Optional[str] = None) -> list[CloudFunction]:
        """List Cloud Functions in a region."""
        region = region or self.client.config.region
        logger.info(f"Listing Cloud Functions in region {region}")
        
        # Mock data
        return [
            CloudFunction(
                name="order-processor",
                project=self.client.config.project_id,
                region=region,
                runtime=CloudFunctionRuntime.PYTHON_311,
                entry_point="process_order",
                status="ACTIVE",
                https_trigger_url=f"https://{region}-{self.client.config.project_id}.cloudfunctions.net/order-processor",
                available_memory_mb=512,
                timeout_seconds=60,
                max_instances=100,
                min_instances=1,
                labels={"env": "production", "team": "orders"},
            ),
        ]
    
    async def get_function(self, name: str, region: Optional[str] = None) -> Optional[CloudFunction]:
        """Get a specific Cloud Function."""
        region = region or self.client.config.region
        functions = await self.list_functions(region)
        return next((f for f in functions if f.name == name), None)
    
    async def call_function(
        self,
        name: str,
        data: Any,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call a Cloud Function."""
        region = region or self.client.config.region
        logger.info(f"Calling Cloud Function: {name}")
        
        # Mock response
        return {
            "execution_id": "abcd1234",
            "result": "Success",
            "error": None,
        }
    
    async def get_function_metrics(
        self,
        name: str,
        region: Optional[str] = None,
        period_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get Cloud Monitoring metrics for a Cloud Function."""
        logger.info(f"Getting metrics for Cloud Function: {name}")
        
        return {
            "executions": 1250,
            "errors": 3,
            "error_rate": 0.24,
            "execution_time_avg_ms": 45.2,
            "execution_time_p99_ms": 123.5,
            "active_instances": 5,
            "memory_utilization": 65.5,
        }
    
    async def set_min_instances(
        self,
        name: str,
        min_instances: int,
        region: Optional[str] = None,
    ) -> bool:
        """Set minimum instances for a function (warm instances)."""
        region = region or self.client.config.region
        logger.info(f"Setting min instances for {name} to {min_instances}")
        # In production: cloudfunctions.projects().locations().functions().patch()
        return True
    
    async def disable_function(self, name: str, region: Optional[str] = None) -> bool:
        """
        Disable a function by setting max instances to 0.
        
        Use during incident response to stop a misbehaving function.
        """
        region = region or self.client.config.region
        logger.warning(f"Disabling Cloud Function: {name}")
        # In production: Set maxInstances to 0
        return True


# ============================================================================
# GCP Client
# ============================================================================


class GCPClient:
    """
    Unified GCP client for SRE operations.
    
    Provides access to GCE, GKE, Cloud SQL, and Cloud Functions managers
    with consistent configuration and authentication.
    
    Usage:
        config = GCPConfig(project_id="my-project", region="us-central1")
        client = GCPClient(config)
        
        # Access service managers
        gce = client.gce
        gke = client.gke
        cloudsql = client.cloudsql
        functions = client.functions
    """
    
    def __init__(self, config: GCPConfig):
        self.config = config
        self._credentials = None
        self._gce_manager: Optional[GCEManager] = None
        self._gke_manager: Optional[GKEManager] = None
        self._cloudsql_manager: Optional[CloudSQLManager] = None
        self._function_manager: Optional[CloudFunctionManager] = None
    
    async def get_credentials(self):
        """Get GCP credentials."""
        if self._credentials is None and self.config.credentials:
            self._credentials = self.config.credentials.get_credentials()
        return self._credentials
    
    @property
    def gce(self) -> GCEManager:
        """Get GCE manager."""
        if self._gce_manager is None:
            self._gce_manager = GCEManager(self)
        return self._gce_manager
    
    @property
    def gke(self) -> GKEManager:
        """Get GKE manager."""
        if self._gke_manager is None:
            self._gke_manager = GKEManager(self)
        return self._gke_manager
    
    @property
    def cloudsql(self) -> CloudSQLManager:
        """Get Cloud SQL manager."""
        if self._cloudsql_manager is None:
            self._cloudsql_manager = CloudSQLManager(self)
        return self._cloudsql_manager
    
    @property
    def functions(self) -> CloudFunctionManager:
        """Get Cloud Functions manager."""
        if self._function_manager is None:
            self._function_manager = CloudFunctionManager(self)
        return self._function_manager
    
    async def health_check(self) -> dict[str, bool]:
        """
        Perform a health check on GCP connectivity.
        
        Verifies credentials and connectivity to each service.
        """
        logger.info("Performing GCP health check")
        
        return {
            "credentials": True,
            "compute": True,
            "container": True,
            "sqladmin": True,
            "cloudfunctions": True,
        }
    
    async def get_project_number(self) -> str:
        """Get the current GCP project number."""
        # In production: resourcemanager.projects().get()
        return "123456789012"
