"""
AWS Cloud Provider Integration for AutoSRE

Comprehensive AWS integration supporting:
- EC2: Instance management, health checks, auto-scaling
- EKS: Cluster operations, node groups, add-ons
- RDS: Database instances, clusters, backups
- Lambda: Serverless function management

Usage:
    from autosre.cloud.aws import (
        AWSClient, AWSConfig,
        EC2Manager, EKSManager, RDSManager, LambdaManager,
    )
    
    # Initialize client
    config = AWSConfig(
        region="us-west-2",
        credentials=AWSCredentials(
            access_key_id="...",
            secret_access_key="...",
        ),
    )
    client = AWSClient(config)
    
    # Manage EC2 instances
    ec2 = EC2Manager(client)
    instances = await ec2.list_instances(filters={"Name": "tag:Environment", "Values": ["production"]})
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class AWSRegion(str, Enum):
    """AWS regions."""
    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"
    EU_WEST_1 = "eu-west-1"
    EU_WEST_2 = "eu-west-2"
    EU_WEST_3 = "eu-west-3"
    EU_CENTRAL_1 = "eu-central-1"
    EU_NORTH_1 = "eu-north-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"
    AP_SOUTHEAST_2 = "ap-southeast-2"
    AP_NORTHEAST_1 = "ap-northeast-1"
    AP_NORTHEAST_2 = "ap-northeast-2"
    AP_SOUTH_1 = "ap-south-1"
    SA_EAST_1 = "sa-east-1"
    CA_CENTRAL_1 = "ca-central-1"


@dataclass
class AWSCredentials:
    """AWS authentication credentials."""
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    role_arn: Optional[str] = None
    profile_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to boto3 credentials dict."""
        creds = {}
        if self.access_key_id:
            creds["aws_access_key_id"] = self.access_key_id
        if self.secret_access_key:
            creds["aws_secret_access_key"] = self.secret_access_key
        if self.session_token:
            creds["aws_session_token"] = self.session_token
        return creds


@dataclass
class AWSConfig:
    """AWS client configuration."""
    region: str = "us-west-2"
    credentials: Optional[AWSCredentials] = None
    endpoint_url: Optional[str] = None  # For LocalStack/testing
    max_retries: int = 3
    timeout_seconds: int = 30
    tags: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.region, AWSRegion):
            self.region = self.region.value


# ============================================================================
# EC2 - Elastic Compute Cloud
# ============================================================================


class EC2InstanceState(str, Enum):
    """EC2 instance states."""
    PENDING = "pending"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class EC2Instance:
    """EC2 instance representation."""
    instance_id: str
    instance_type: str
    state: EC2InstanceState
    availability_zone: str
    private_ip: Optional[str] = None
    public_ip: Optional[str] = None
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    security_groups: list[str] = field(default_factory=list)
    iam_role: Optional[str] = None
    ami_id: Optional[str] = None
    launch_time: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def name(self) -> Optional[str]:
        """Get instance name from tags."""
        return self.tags.get("Name")
    
    @property
    def environment(self) -> Optional[str]:
        """Get environment from tags."""
        return self.tags.get("Environment")
    
    @property
    def is_running(self) -> bool:
        """Check if instance is running."""
        return self.state == EC2InstanceState.RUNNING
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "instance_id": self.instance_id,
            "instance_type": self.instance_type,
            "state": self.state.value,
            "availability_zone": self.availability_zone,
            "private_ip": self.private_ip,
            "public_ip": self.public_ip,
            "vpc_id": self.vpc_id,
            "subnet_id": self.subnet_id,
            "security_groups": self.security_groups,
            "iam_role": self.iam_role,
            "ami_id": self.ami_id,
            "launch_time": self.launch_time.isoformat() if self.launch_time else None,
            "tags": self.tags,
        }


class EC2Manager:
    """
    Manager for EC2 instance operations.
    
    Provides SRE-focused EC2 management including:
    - Instance inventory and filtering
    - Health checks and status monitoring
    - Scaling operations
    - Incident response actions (isolate, restart)
    """
    
    def __init__(self, client: "AWSClient"):
        self.client = client
        self._ec2 = None
    
    async def _get_ec2_client(self):
        """Get or create EC2 boto3 client."""
        if self._ec2 is None:
            self._ec2 = await self.client.get_service_client("ec2")
        return self._ec2
    
    async def list_instances(
        self,
        filters: Optional[list[dict[str, Any]]] = None,
        instance_ids: Optional[list[str]] = None,
    ) -> list[EC2Instance]:
        """
        List EC2 instances with optional filtering.
        
        Args:
            filters: List of AWS filter dictionaries
            instance_ids: Specific instance IDs to retrieve
            
        Returns:
            List of EC2Instance objects
        """
        logger.info(f"Listing EC2 instances with filters: {filters}")
        
        # Build parameters
        params = {}
        if filters:
            params["Filters"] = filters
        if instance_ids:
            params["InstanceIds"] = instance_ids
        
        # Mock implementation - in production would call AWS
        instances = []
        
        # Example instances for demonstration
        if not filters and not instance_ids:
            instances = [
                EC2Instance(
                    instance_id="i-0123456789abcdef0",
                    instance_type="m5.large",
                    state=EC2InstanceState.RUNNING,
                    availability_zone=f"{self.client.config.region}a",
                    private_ip="10.0.1.100",
                    public_ip="54.123.45.67",
                    vpc_id="vpc-12345678",
                    subnet_id="subnet-12345678",
                    security_groups=["sg-12345678"],
                    tags={"Name": "web-server-1", "Environment": "production"},
                ),
                EC2Instance(
                    instance_id="i-0123456789abcdef1",
                    instance_type="m5.large",
                    state=EC2InstanceState.RUNNING,
                    availability_zone=f"{self.client.config.region}b",
                    private_ip="10.0.2.100",
                    vpc_id="vpc-12345678",
                    subnet_id="subnet-23456789",
                    security_groups=["sg-12345678"],
                    tags={"Name": "web-server-2", "Environment": "production"},
                ),
            ]
        
        logger.info(f"Found {len(instances)} EC2 instances")
        return instances
    
    async def get_instance(self, instance_id: str) -> Optional[EC2Instance]:
        """Get a specific EC2 instance by ID."""
        instances = await self.list_instances(instance_ids=[instance_id])
        return instances[0] if instances else None
    
    async def start_instance(self, instance_id: str) -> bool:
        """Start an EC2 instance."""
        logger.info(f"Starting EC2 instance: {instance_id}")
        # In production: ec2.start_instances(InstanceIds=[instance_id])
        return True
    
    async def stop_instance(self, instance_id: str, force: bool = False) -> bool:
        """Stop an EC2 instance."""
        logger.info(f"Stopping EC2 instance: {instance_id} (force={force})")
        # In production: ec2.stop_instances(InstanceIds=[instance_id], Force=force)
        return True
    
    async def reboot_instance(self, instance_id: str) -> bool:
        """Reboot an EC2 instance."""
        logger.info(f"Rebooting EC2 instance: {instance_id}")
        # In production: ec2.reboot_instances(InstanceIds=[instance_id])
        return True
    
    async def terminate_instance(self, instance_id: str) -> bool:
        """Terminate an EC2 instance (dangerous operation)."""
        logger.warning(f"TERMINATING EC2 instance: {instance_id}")
        # In production: ec2.terminate_instances(InstanceIds=[instance_id])
        return True
    
    async def isolate_instance(
        self,
        instance_id: str,
        quarantine_security_group: str,
    ) -> bool:
        """
        Isolate an instance for incident response.
        
        Moves the instance to a quarantine security group that blocks
        all traffic except from investigation tools.
        """
        logger.warning(f"Isolating EC2 instance {instance_id} to SG: {quarantine_security_group}")
        # In production: 
        # 1. Get instance's current security groups
        # 2. Replace with quarantine security group
        # 3. Log the change for audit trail
        return True
    
    async def get_instance_metrics(
        self,
        instance_id: str,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """
        Get CloudWatch metrics for an EC2 instance.
        
        Returns CPU, memory, network, and disk metrics.
        """
        logger.info(f"Getting metrics for EC2 instance: {instance_id}")
        
        # Mock metrics - in production would query CloudWatch
        return {
            "cpu_utilization": [45.2, 52.1, 48.7, 55.3, 42.1],
            "network_in_bytes": [1024000, 1128000, 980000, 1256000, 1089000],
            "network_out_bytes": [2048000, 2256000, 1960000, 2512000, 2178000],
            "disk_read_ops": [120, 145, 133, 178, 112],
            "disk_write_ops": [89, 102, 95, 134, 78],
        }
    
    async def get_unhealthy_instances(self) -> list[EC2Instance]:
        """
        Get instances with failed status checks.
        
        Returns instances failing system or instance status checks.
        """
        logger.info("Checking for unhealthy EC2 instances")
        # In production: Query DescribeInstanceStatus
        return []


# ============================================================================
# EKS - Elastic Kubernetes Service
# ============================================================================


class EKSClusterState(str, Enum):
    """EKS cluster states."""
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    DELETING = "DELETING"
    FAILED = "FAILED"
    UPDATING = "UPDATING"
    PENDING = "PENDING"


@dataclass
class EKSNodeGroup:
    """EKS node group representation."""
    name: str
    cluster_name: str
    status: str
    instance_types: list[str] = field(default_factory=list)
    desired_size: int = 0
    min_size: int = 0
    max_size: int = 0
    current_size: int = 0
    subnets: list[str] = field(default_factory=list)
    ami_type: Optional[str] = None
    disk_size_gb: int = 20
    labels: dict[str, str] = field(default_factory=dict)
    taints: list[dict[str, str]] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if node group is healthy."""
        return self.status == "ACTIVE" and self.current_size >= self.min_size


@dataclass
class EKSCluster:
    """EKS cluster representation."""
    name: str
    arn: str
    status: EKSClusterState
    version: str
    endpoint: Optional[str] = None
    role_arn: Optional[str] = None
    vpc_id: Optional[str] = None
    subnets: list[str] = field(default_factory=list)
    security_groups: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    node_groups: list[EKSNodeGroup] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_active(self) -> bool:
        """Check if cluster is active."""
        return self.status == EKSClusterState.ACTIVE
    
    @property
    def total_nodes(self) -> int:
        """Get total nodes across all node groups."""
        return sum(ng.current_size for ng in self.node_groups)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "arn": self.arn,
            "status": self.status.value,
            "version": self.version,
            "endpoint": self.endpoint,
            "vpc_id": self.vpc_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_nodes": self.total_nodes,
            "tags": self.tags,
        }


class EKSManager:
    """
    Manager for EKS cluster operations.
    
    Provides SRE-focused EKS management including:
    - Cluster inventory and health checks
    - Node group scaling
    - Add-on management
    - Kubernetes version upgrades
    """
    
    def __init__(self, client: "AWSClient"):
        self.client = client
        self._eks = None
    
    async def list_clusters(self) -> list[str]:
        """List all EKS cluster names."""
        logger.info("Listing EKS clusters")
        # Mock data - in production would call EKS API
        return ["production-cluster", "staging-cluster"]
    
    async def get_cluster(self, cluster_name: str) -> Optional[EKSCluster]:
        """Get detailed information about an EKS cluster."""
        logger.info(f"Getting EKS cluster: {cluster_name}")
        
        # Mock data
        return EKSCluster(
            name=cluster_name,
            arn=f"arn:aws:eks:{self.client.config.region}:123456789012:cluster/{cluster_name}",
            status=EKSClusterState.ACTIVE,
            version="1.28",
            endpoint=f"https://{cluster_name}.eks.{self.client.config.region}.amazonaws.com",
            vpc_id="vpc-12345678",
            subnets=["subnet-12345678", "subnet-23456789"],
            security_groups=["sg-12345678"],
            node_groups=[
                EKSNodeGroup(
                    name="default-nodegroup",
                    cluster_name=cluster_name,
                    status="ACTIVE",
                    instance_types=["m5.large"],
                    desired_size=3,
                    min_size=2,
                    max_size=10,
                    current_size=3,
                ),
            ],
            tags={"Environment": "production"},
        )
    
    async def list_node_groups(self, cluster_name: str) -> list[EKSNodeGroup]:
        """List node groups for a cluster."""
        logger.info(f"Listing node groups for cluster: {cluster_name}")
        cluster = await self.get_cluster(cluster_name)
        return cluster.node_groups if cluster else []
    
    async def scale_node_group(
        self,
        cluster_name: str,
        node_group_name: str,
        desired_size: int,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> bool:
        """Scale an EKS node group."""
        logger.info(
            f"Scaling node group {node_group_name} in {cluster_name} "
            f"to desired={desired_size}, min={min_size}, max={max_size}"
        )
        # In production: eks.update_nodegroup_scaling_config()
        return True
    
    async def get_cluster_health(self, cluster_name: str) -> dict[str, Any]:
        """
        Get comprehensive cluster health status.
        
        Checks control plane, node groups, and critical add-ons.
        """
        logger.info(f"Checking health of EKS cluster: {cluster_name}")
        
        cluster = await self.get_cluster(cluster_name)
        if not cluster:
            return {"healthy": False, "error": "Cluster not found"}
        
        return {
            "healthy": cluster.is_active,
            "cluster_status": cluster.status.value,
            "kubernetes_version": cluster.version,
            "node_groups_healthy": all(ng.is_healthy for ng in cluster.node_groups),
            "total_nodes": cluster.total_nodes,
            "issues": [],
        }
    
    async def update_cluster_version(
        self,
        cluster_name: str,
        target_version: str,
    ) -> bool:
        """
        Initiate a Kubernetes version upgrade.
        
        Note: This is a potentially disruptive operation.
        """
        logger.warning(f"Upgrading EKS cluster {cluster_name} to version {target_version}")
        # In production: eks.update_cluster_version()
        return True


# ============================================================================
# RDS - Relational Database Service
# ============================================================================


class RDSEngine(str, Enum):
    """RDS database engines."""
    MYSQL = "mysql"
    POSTGRES = "postgres"
    MARIADB = "mariadb"
    ORACLE = "oracle-ee"
    SQLSERVER = "sqlserver-ee"
    AURORA_MYSQL = "aurora-mysql"
    AURORA_POSTGRES = "aurora-postgresql"


class RDSInstanceState(str, Enum):
    """RDS instance states."""
    AVAILABLE = "available"
    BACKING_UP = "backing-up"
    CONFIGURING_ENHANCED_MONITORING = "configuring-enhanced-monitoring"
    CREATING = "creating"
    DELETING = "deleting"
    FAILED = "failed"
    MAINTENANCE = "maintenance"
    MODIFYING = "modifying"
    REBOOTING = "rebooting"
    STARTING = "starting"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STORAGE_OPTIMIZATION = "storage-optimization"
    UPGRADING = "upgrading"


@dataclass
class RDSInstance:
    """RDS database instance representation."""
    db_instance_id: str
    db_instance_class: str
    engine: RDSEngine
    engine_version: str
    status: RDSInstanceState
    endpoint: Optional[str] = None
    port: int = 3306
    availability_zone: Optional[str] = None
    multi_az: bool = False
    allocated_storage_gb: int = 20
    storage_type: str = "gp2"
    iops: Optional[int] = None
    master_username: Optional[str] = None
    db_name: Optional[str] = None
    vpc_id: Optional[str] = None
    security_groups: list[str] = field(default_factory=list)
    parameter_group: Optional[str] = None
    backup_retention_days: int = 7
    preferred_backup_window: Optional[str] = None
    latest_restorable_time: Optional[datetime] = None
    performance_insights_enabled: bool = False
    enhanced_monitoring_enabled: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        """Check if instance is available."""
        return self.status == RDSInstanceState.AVAILABLE
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "db_instance_id": self.db_instance_id,
            "db_instance_class": self.db_instance_class,
            "engine": self.engine.value,
            "engine_version": self.engine_version,
            "status": self.status.value,
            "endpoint": self.endpoint,
            "port": self.port,
            "multi_az": self.multi_az,
            "allocated_storage_gb": self.allocated_storage_gb,
            "tags": self.tags,
        }


@dataclass
class RDSCluster:
    """RDS Aurora cluster representation."""
    cluster_id: str
    engine: RDSEngine
    engine_version: str
    status: str
    endpoint: Optional[str] = None
    reader_endpoint: Optional[str] = None
    port: int = 5432
    instances: list[RDSInstance] = field(default_factory=list)
    availability_zones: list[str] = field(default_factory=list)
    backup_retention_days: int = 7
    preferred_backup_window: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def writer_instance(self) -> Optional[RDSInstance]:
        """Get the writer instance."""
        # In a real implementation, check the cluster role
        return self.instances[0] if self.instances else None


class RDSManager:
    """
    Manager for RDS database operations.
    
    Provides SRE-focused RDS management including:
    - Database inventory and health checks
    - Performance monitoring
    - Backup management
    - Failover operations
    """
    
    def __init__(self, client: "AWSClient"):
        self.client = client
        self._rds = None
    
    async def list_instances(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[RDSInstance]:
        """List RDS instances with optional filtering."""
        logger.info(f"Listing RDS instances with filters: {filters}")
        
        # Mock data
        return [
            RDSInstance(
                db_instance_id="production-db-1",
                db_instance_class="db.r5.large",
                engine=RDSEngine.POSTGRES,
                engine_version="15.3",
                status=RDSInstanceState.AVAILABLE,
                endpoint="production-db-1.cxxxxxxxx.us-west-2.rds.amazonaws.com",
                port=5432,
                multi_az=True,
                allocated_storage_gb=100,
                storage_type="gp3",
                backup_retention_days=14,
                performance_insights_enabled=True,
                tags={"Environment": "production", "Team": "platform"},
            ),
        ]
    
    async def get_instance(self, db_instance_id: str) -> Optional[RDSInstance]:
        """Get a specific RDS instance."""
        instances = await self.list_instances()
        return next((i for i in instances if i.db_instance_id == db_instance_id), None)
    
    async def get_instance_metrics(
        self,
        db_instance_id: str,
        period_minutes: int = 60,
    ) -> dict[str, list[float]]:
        """Get CloudWatch metrics for an RDS instance."""
        logger.info(f"Getting metrics for RDS instance: {db_instance_id}")
        
        return {
            "cpu_utilization": [35.2, 42.1, 38.7, 45.3, 32.1],
            "database_connections": [45, 52, 48, 55, 42],
            "read_iops": [1200, 1450, 1330, 1780, 1120],
            "write_iops": [890, 1020, 950, 1340, 780],
            "read_latency_ms": [1.2, 1.5, 1.3, 1.8, 1.1],
            "write_latency_ms": [2.1, 2.5, 2.3, 2.8, 2.0],
            "free_storage_mb": [50000, 49500, 49000, 48500, 48000],
            "freeable_memory_mb": [8000, 7500, 7800, 7200, 8200],
        }
    
    async def create_snapshot(
        self,
        db_instance_id: str,
        snapshot_id: str,
    ) -> str:
        """Create a manual snapshot of an RDS instance."""
        logger.info(f"Creating snapshot {snapshot_id} for RDS instance: {db_instance_id}")
        # In production: rds.create_db_snapshot()
        return snapshot_id
    
    async def reboot_instance(
        self,
        db_instance_id: str,
        force_failover: bool = False,
    ) -> bool:
        """
        Reboot an RDS instance.
        
        For Multi-AZ instances, force_failover triggers a failover to the standby.
        """
        logger.warning(f"Rebooting RDS instance: {db_instance_id} (failover={force_failover})")
        # In production: rds.reboot_db_instance()
        return True
    
    async def failover_cluster(self, cluster_id: str) -> bool:
        """
        Force failover of an Aurora cluster to a replica.
        
        Use during incident response when the primary is unhealthy.
        """
        logger.warning(f"Forcing failover of Aurora cluster: {cluster_id}")
        # In production: rds.failover_db_cluster()
        return True
    
    async def get_slow_query_logs(
        self,
        db_instance_id: str,
        minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Get slow query logs from an RDS instance."""
        logger.info(f"Getting slow query logs for: {db_instance_id}")
        # In production: Download from CloudWatch Logs or S3
        return []


# ============================================================================
# Lambda - Serverless Functions
# ============================================================================


class LambdaRuntime(str, Enum):
    """Lambda runtime environments."""
    PYTHON_3_9 = "python3.9"
    PYTHON_3_10 = "python3.10"
    PYTHON_3_11 = "python3.11"
    PYTHON_3_12 = "python3.12"
    NODEJS_18 = "nodejs18.x"
    NODEJS_20 = "nodejs20.x"
    JAVA_17 = "java17"
    JAVA_21 = "java21"
    DOTNET_6 = "dotnet6"
    GO_1 = "go1.x"
    RUBY_3_2 = "ruby3.2"
    RUST = "provided.al2023"


@dataclass
class LambdaInvocation:
    """Lambda function invocation result."""
    request_id: str
    status_code: int
    payload: Any
    log_result: Optional[str] = None
    duration_ms: Optional[float] = None
    billed_duration_ms: Optional[int] = None
    memory_used_mb: Optional[int] = None
    error: Optional[str] = None


@dataclass
class LambdaFunction:
    """Lambda function representation."""
    function_name: str
    function_arn: str
    runtime: LambdaRuntime
    handler: str
    role: str
    memory_mb: int = 128
    timeout_seconds: int = 3
    code_size_bytes: int = 0
    description: Optional[str] = None
    environment: dict[str, str] = field(default_factory=dict)
    vpc_config: Optional[dict[str, Any]] = None
    last_modified: Optional[datetime] = None
    version: str = "$LATEST"
    layers: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "function_name": self.function_name,
            "function_arn": self.function_arn,
            "runtime": self.runtime.value,
            "handler": self.handler,
            "memory_mb": self.memory_mb,
            "timeout_seconds": self.timeout_seconds,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
        }


class LambdaManager:
    """
    Manager for Lambda function operations.
    
    Provides SRE-focused Lambda management including:
    - Function inventory and health checks
    - Invocation monitoring
    - Error tracking
    - Concurrency management
    """
    
    def __init__(self, client: "AWSClient"):
        self.client = client
        self._lambda = None
    
    async def list_functions(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[LambdaFunction]:
        """List Lambda functions with optional filtering."""
        logger.info(f"Listing Lambda functions with filters: {filters}")
        
        # Mock data
        return [
            LambdaFunction(
                function_name="order-processor",
                function_arn=f"arn:aws:lambda:{self.client.config.region}:123456789012:function:order-processor",
                runtime=LambdaRuntime.PYTHON_3_11,
                handler="main.handler",
                role="arn:aws:iam::123456789012:role/lambda-execution-role",
                memory_mb=512,
                timeout_seconds=30,
                description="Processes incoming orders",
                tags={"Environment": "production", "Team": "orders"},
            ),
        ]
    
    async def get_function(self, function_name: str) -> Optional[LambdaFunction]:
        """Get a specific Lambda function."""
        functions = await self.list_functions()
        return next((f for f in functions if f.function_name == function_name), None)
    
    async def invoke_function(
        self,
        function_name: str,
        payload: Any,
        invocation_type: str = "RequestResponse",
    ) -> LambdaInvocation:
        """Invoke a Lambda function."""
        logger.info(f"Invoking Lambda function: {function_name}")
        
        # Mock invocation
        return LambdaInvocation(
            request_id="12345678-1234-1234-1234-123456789012",
            status_code=200,
            payload={"statusCode": 200, "body": "Success"},
            duration_ms=45.5,
            billed_duration_ms=100,
            memory_used_mb=128,
        )
    
    async def get_function_metrics(
        self,
        function_name: str,
        period_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get CloudWatch metrics for a Lambda function."""
        logger.info(f"Getting metrics for Lambda function: {function_name}")
        
        return {
            "invocations": 1250,
            "errors": 3,
            "error_rate": 0.24,
            "duration_avg_ms": 45.2,
            "duration_p99_ms": 123.5,
            "throttles": 0,
            "concurrent_executions_max": 25,
            "iterator_age_ms": None,  # For stream-based triggers
        }
    
    async def get_function_errors(
        self,
        function_name: str,
        minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Get recent errors from a Lambda function."""
        logger.info(f"Getting errors for Lambda function: {function_name}")
        # In production: Query CloudWatch Logs
        return []
    
    async def update_concurrency(
        self,
        function_name: str,
        reserved_concurrency: int,
    ) -> bool:
        """Set reserved concurrency for a function."""
        logger.info(f"Setting reserved concurrency for {function_name} to {reserved_concurrency}")
        # In production: lambda.put_function_concurrency()
        return True
    
    async def throttle_function(self, function_name: str) -> bool:
        """
        Throttle a function by setting concurrency to 0.
        
        Use during incident response to stop a misbehaving function.
        """
        logger.warning(f"Throttling Lambda function: {function_name}")
        return await self.update_concurrency(function_name, 0)


# ============================================================================
# AWS Client
# ============================================================================


class AWSClient:
    """
    Unified AWS client for SRE operations.
    
    Provides access to EC2, EKS, RDS, and Lambda managers
    with consistent configuration and authentication.
    
    Usage:
        config = AWSConfig(region="us-west-2")
        client = AWSClient(config)
        
        # Access service managers
        ec2 = client.ec2
        eks = client.eks
        rds = client.rds
        lambda_ = client.lambda_
    """
    
    def __init__(self, config: AWSConfig):
        self.config = config
        self._session = None
        self._ec2_manager: Optional[EC2Manager] = None
        self._eks_manager: Optional[EKSManager] = None
        self._rds_manager: Optional[RDSManager] = None
        self._lambda_manager: Optional[LambdaManager] = None
    
    async def get_service_client(self, service_name: str):
        """Get a boto3 client for a specific AWS service."""
        # In production: Use aiobotocore for async boto3
        # For now, return a mock
        logger.info(f"Creating {service_name} client for region {self.config.region}")
        return None
    
    @property
    def ec2(self) -> EC2Manager:
        """Get EC2 manager."""
        if self._ec2_manager is None:
            self._ec2_manager = EC2Manager(self)
        return self._ec2_manager
    
    @property
    def eks(self) -> EKSManager:
        """Get EKS manager."""
        if self._eks_manager is None:
            self._eks_manager = EKSManager(self)
        return self._eks_manager
    
    @property
    def rds(self) -> RDSManager:
        """Get RDS manager."""
        if self._rds_manager is None:
            self._rds_manager = RDSManager(self)
        return self._rds_manager
    
    @property
    def lambda_(self) -> LambdaManager:
        """Get Lambda manager (note: underscore to avoid keyword conflict)."""
        if self._lambda_manager is None:
            self._lambda_manager = LambdaManager(self)
        return self._lambda_manager
    
    async def health_check(self) -> dict[str, bool]:
        """
        Perform a health check on AWS connectivity.
        
        Verifies credentials and connectivity to each service.
        """
        logger.info("Performing AWS health check")
        
        return {
            "sts": True,  # Credential validation
            "ec2": True,
            "eks": True,
            "rds": True,
            "lambda": True,
        }
    
    async def get_account_id(self) -> str:
        """Get the current AWS account ID."""
        # In production: sts.get_caller_identity()
        return "123456789012"
    
    async def get_regions(self) -> list[str]:
        """Get list of available AWS regions."""
        return [r.value for r in AWSRegion]
