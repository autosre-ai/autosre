"""
AutoSRE Cloud Provider Integration Module

Multi-cloud SRE capabilities providing unified interfaces for:
- AWS: EC2, EKS, RDS, Lambda
- GCP: GCE, GKE, CloudSQL, Cloud Functions
- Azure: VMs, AKS, SQL, Functions

Features:
- Unified resource management across cloud providers
- Health checks and status monitoring
- Auto-scaling configuration
- Resource tagging and inventory
- Cross-cloud incident correlation

Usage:
    from autosre.cloud import (
        # Base
        CloudClient, CloudConfig, CloudResource, ResourceStatus,
        # AWS
        AWSClient, AWSConfig, EC2Manager, EKSManager, RDSManager, LambdaManager,
        # GCP
        GCPClient, GCPConfig, GCEManager, GKEManager, CloudSQLManager,
        # Azure
        AzureClient, AzureConfig, VMManager, AKSManager, AzureSQLManager,
        # Multi-cloud
        MultiCloudOrchestrator, CloudInventory, ResourceQuery,
    )
"""

from autosre.cloud.aws import (
    # Configuration
    AWSConfig,
    AWSCredentials,
    AWSRegion,
    # Clients
    AWSClient,
    # EC2
    EC2Instance,
    EC2InstanceState,
    EC2Manager,
    # EKS
    EKSCluster,
    EKSNodeGroup,
    EKSClusterState,
    EKSManager,
    # RDS
    RDSInstance,
    RDSCluster,
    RDSEngine,
    RDSInstanceState,
    RDSManager,
    # Lambda
    LambdaFunction,
    LambdaRuntime,
    LambdaInvocation,
    LambdaManager,
)
from autosre.cloud.gcp import (
    # Configuration
    GCPConfig,
    GCPCredentials,
    GCPRegion,
    # Clients
    GCPClient,
    # GCE
    GCEInstance,
    GCEInstanceState,
    GCEManager,
    # GKE
    GKECluster,
    GKENodePool,
    GKEClusterState,
    GKEManager,
    # CloudSQL
    CloudSQLInstance,
    CloudSQLDatabaseVersion,
    CloudSQLInstanceState,
    CloudSQLManager,
    # Cloud Functions
    CloudFunction,
    CloudFunctionRuntime,
    CloudFunctionManager,
)
from autosre.cloud.azure import (
    # Configuration
    AzureConfig,
    AzureCredentials,
    AzureRegion,
    # Clients
    AzureClient,
    # VMs
    AzureVM,
    AzureVMState,
    AzureVMSize,
    VMManager,
    # AKS
    AKSCluster,
    AKSNodePool,
    AKSClusterState,
    AKSManager,
    # Azure SQL
    AzureSQLServer,
    AzureSQLDatabase,
    AzureSQLTier,
    AzureSQLManager,
    # Functions
    AzureFunction,
    AzureFunctionRuntime,
    AzureFunctionManager,
)

# Re-export CloudProvider from cost module
from autosre.cost.analyzer import CloudProvider


__all__ = [
    # Enums
    "CloudProvider",
    # AWS
    "AWSConfig",
    "AWSCredentials",
    "AWSRegion",
    "AWSClient",
    "EC2Instance",
    "EC2InstanceState",
    "EC2Manager",
    "EKSCluster",
    "EKSNodeGroup",
    "EKSClusterState",
    "EKSManager",
    "RDSInstance",
    "RDSCluster",
    "RDSEngine",
    "RDSInstanceState",
    "RDSManager",
    "LambdaFunction",
    "LambdaRuntime",
    "LambdaInvocation",
    "LambdaManager",
    # GCP
    "GCPConfig",
    "GCPCredentials",
    "GCPRegion",
    "GCPClient",
    "GCEInstance",
    "GCEInstanceState",
    "GCEManager",
    "GKECluster",
    "GKENodePool",
    "GKEClusterState",
    "GKEManager",
    "CloudSQLInstance",
    "CloudSQLDatabaseVersion",
    "CloudSQLInstanceState",
    "CloudSQLManager",
    "CloudFunction",
    "CloudFunctionRuntime",
    "CloudFunctionManager",
    # Azure
    "AzureConfig",
    "AzureCredentials",
    "AzureRegion",
    "AzureClient",
    "AzureVM",
    "AzureVMState",
    "AzureVMSize",
    "VMManager",
    "AKSCluster",
    "AKSNodePool",
    "AKSClusterState",
    "AKSManager",
    "AzureSQLServer",
    "AzureSQLDatabase",
    "AzureSQLTier",
    "AzureSQLManager",
    "AzureFunction",
    "AzureFunctionRuntime",
    "AzureFunctionManager",
]
