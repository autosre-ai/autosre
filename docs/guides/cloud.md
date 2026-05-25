# Cloud Provider Integrations

AutoSRE provides unified multi-cloud integrations for AWS, GCP, and Azure, enabling consistent SRE operations across all major cloud providers.

## Overview

The cloud module provides:

- **Unified API**: Consistent interface across AWS, GCP, and Azure
- **SRE-focused operations**: Health checks, scaling, incident response
- **Resource inventory**: List and filter resources across clouds
- **Metrics integration**: Pull metrics from cloud monitoring services
- **Safe operations**: Built-in safeguards for dangerous operations

## Quick Start

### AWS

```python
from autosre.cloud import (
    AWSClient, AWSConfig, AWSCredentials, AWSRegion,
)

# Configure AWS client
config = AWSConfig(
    region=AWSRegion.US_WEST_2,
    credentials=AWSCredentials(
        access_key_id="AKIA...",
        secret_access_key="...",
        # Or use: profile_name="production"
        # Or use: role_arn="arn:aws:iam::123456789012:role/SRERole"
    ),
)

# Create client
client = AWSClient(config)

# List EC2 instances
instances = await client.ec2.list_instances(
    filters=[{"Name": "tag:Environment", "Values": ["production"]}]
)

# Check EKS cluster health
health = await client.eks.get_cluster_health("production-cluster")

# Get RDS metrics
metrics = await client.rds.get_instance_metrics("production-db-1")
```

### GCP

```python
from autosre.cloud import (
    GCPClient, GCPConfig, GCPCredentials, GCPRegion,
)

# Configure GCP client
config = GCPConfig(
    project_id="my-project-123",
    region=GCPRegion.US_CENTRAL1,
    credentials=GCPCredentials(
        service_account_key_path="/path/to/service-account.json",
        # Or use: use_default_credentials=True
    ),
)

# Create client
client = GCPClient(config)

# List GCE instances
instances = await client.gce.list_instances(zone="us-central1-a")

# Check GKE cluster health
health = await client.gke.get_cluster_health("production-cluster")

# Get Cloud SQL metrics
metrics = await client.cloudsql.get_instance_metrics("production-db")
```

### Azure

```python
from autosre.cloud import (
    AzureClient, AzureConfig, AzureCredentials, AzureRegion,
)

# Configure Azure client
config = AzureConfig(
    subscription_id="12345678-1234-1234-1234-123456789012",
    resource_group="production-rg",
    location=AzureRegion.EAST_US,
    credentials=AzureCredentials(
        tenant_id="...",
        client_id="...",
        client_secret="...",
        # Or use: use_managed_identity=True
        # Or use: use_cli_credentials=True
    ),
)

# Create client
client = AzureClient(config)

# List VMs
vms = await client.vms.list_vms(
    tags={"Environment": "production"}
)

# Check AKS cluster health
health = await client.aks.get_cluster_health("production-aks")

# Get Azure SQL metrics
metrics = await client.sql.get_database_metrics(
    "production-sql", "app-db"
)
```

## Service Managers

### Compute (EC2 / GCE / Azure VMs)

All cloud providers support similar compute operations:

```python
# List instances
instances = await client.ec2.list_instances()  # AWS
instances = await client.gce.list_instances()  # GCP
vms = await client.vms.list_vms()              # Azure

# Start/Stop/Restart
await client.ec2.start_instance("i-1234567890abcdef0")
await client.gce.start_instance("web-server-1")
await client.vms.start_vm("web-server-1")

# Get metrics
metrics = await client.ec2.get_instance_metrics("i-1234567890abcdef0")
```

#### Incident Response Operations

```python
# AWS: Isolate instance to quarantine security group
await client.ec2.isolate_instance(
    instance_id="i-1234567890abcdef0",
    quarantine_security_group="sg-quarantine"
)

# GCP: Get serial console output for debugging
output = await client.gce.get_instance_serial_output("web-server-1")

# Azure: Redeploy VM to new host (for host-related issues)
await client.vms.redeploy_vm("web-server-1")
```

### Kubernetes (EKS / GKE / AKS)

All providers support managed Kubernetes operations:

```python
# List clusters
clusters = await client.eks.list_clusters()      # AWS
clusters = await client.gke.list_clusters()      # GCP
clusters = await client.aks.list_clusters()      # Azure

# Get cluster health
health = await client.eks.get_cluster_health("production-cluster")

# Scale node pools
await client.eks.scale_node_group(
    cluster_name="production-cluster",
    node_group_name="default-nodegroup",
    desired_size=10,
    min_size=5,
    max_size=20,
)

# Upgrade cluster (use with caution!)
await client.eks.update_cluster_version(
    cluster_name="staging-cluster",
    target_version="1.29",
)
```

### Databases (RDS / Cloud SQL / Azure SQL)

Managed database operations:

```python
# List instances
instances = await client.rds.list_instances()              # AWS
instances = await client.cloudsql.list_instances()         # GCP
servers = await client.sql.list_servers()                  # Azure

# Get database metrics
metrics = await client.rds.get_instance_metrics("production-db-1")

# Create backup (on-demand)
await client.rds.create_snapshot("production-db-1", "pre-deploy-backup")
await client.cloudsql.create_backup("production-db", "Manual backup")

# Failover for incident response
await client.rds.failover_cluster("aurora-cluster")            # AWS Aurora
await client.cloudsql.failover_instance("production-db")       # GCP
await client.sql.failover_database("server", "database")       # Azure
```

### Serverless (Lambda / Cloud Functions / Azure Functions)

Serverless function operations:

```python
# List functions
functions = await client.lambda_.list_functions()               # AWS
functions = await client.functions.list_functions()             # GCP
apps = await client.functions.list_function_apps()              # Azure

# Invoke function
result = await client.lambda_.invoke_function(
    function_name="order-processor",
    payload={"order_id": "12345"},
)

# Get function metrics
metrics = await client.lambda_.get_function_metrics("order-processor")

# Throttle misbehaving function (incident response)
await client.lambda_.throttle_function("runaway-function")          # AWS
await client.functions.disable_function("runaway-function")         # GCP
await client.functions.disable_function("app", "function")          # Azure
```

## Multi-Cloud Operations

For organizations using multiple cloud providers, you can create a unified view:

```python
from autosre.cloud import AWSClient, GCPClient, AzureClient

class MultiCloudInventory:
    def __init__(self, aws: AWSClient, gcp: GCPClient, azure: AzureClient):
        self.aws = aws
        self.gcp = gcp
        self.azure = azure
    
    async def get_all_kubernetes_clusters(self) -> dict:
        """Get all Kubernetes clusters across clouds."""
        results = {}
        
        # AWS EKS
        eks_clusters = await self.aws.eks.list_clusters()
        for name in eks_clusters:
            cluster = await self.aws.eks.get_cluster(name)
            results[f"aws/{name}"] = {
                "provider": "aws",
                "version": cluster.version,
                "nodes": cluster.total_nodes,
                "healthy": cluster.is_active,
            }
        
        # GCP GKE
        gke_clusters = await self.gcp.gke.list_clusters()
        for cluster in gke_clusters:
            results[f"gcp/{cluster.name}"] = {
                "provider": "gcp",
                "version": cluster.master_version,
                "nodes": cluster.total_nodes,
                "healthy": cluster.is_running,
            }
        
        # Azure AKS
        aks_clusters = await self.azure.aks.list_clusters()
        for cluster in aks_clusters:
            results[f"azure/{cluster.name}"] = {
                "provider": "azure",
                "version": cluster.kubernetes_version,
                "nodes": cluster.total_nodes,
                "healthy": cluster.is_running,
            }
        
        return results
    
    async def health_check_all(self) -> dict:
        """Perform health checks across all cloud providers."""
        return {
            "aws": await self.aws.health_check(),
            "gcp": await self.gcp.health_check(),
            "azure": await self.azure.health_check(),
        }
```

## Authentication Best Practices

### AWS

1. **IAM Roles (Recommended for Production)**
   ```python
   config = AWSConfig(
       region="us-west-2",
       credentials=AWSCredentials(
           role_arn="arn:aws:iam::123456789012:role/SRERole"
       ),
   )
   ```

2. **Instance Profiles (for EC2/EKS)**
   ```python
   # Automatically uses instance metadata
   config = AWSConfig(region="us-west-2")
   ```

3. **AWS Profile**
   ```python
   config = AWSConfig(
       region="us-west-2",
       credentials=AWSCredentials(profile_name="production"),
   )
   ```

### GCP

1. **Service Account Key (Recommended)**
   ```python
   config = GCPConfig(
       project_id="my-project",
       credentials=GCPCredentials(
           service_account_key_path="/path/to/key.json"
       ),
   )
   ```

2. **Default Credentials (GKE/GCE)**
   ```python
   config = GCPConfig(
       project_id="my-project",
       credentials=GCPCredentials(use_default_credentials=True),
   )
   ```

3. **Impersonation**
   ```python
   config = GCPConfig(
       project_id="my-project",
       credentials=GCPCredentials(
           impersonate_service_account="sre-agent@project.iam.gserviceaccount.com"
       ),
   )
   ```

### Azure

1. **Service Principal**
   ```python
   config = AzureConfig(
       subscription_id="...",
       resource_group="production-rg",
       credentials=AzureCredentials(
           tenant_id="...",
           client_id="...",
           client_secret="...",
       ),
   )
   ```

2. **Managed Identity (for Azure VMs/AKS)**
   ```python
   config = AzureConfig(
       subscription_id="...",
       resource_group="production-rg",
       credentials=AzureCredentials(use_managed_identity=True),
   )
   ```

3. **Azure CLI**
   ```python
   config = AzureConfig(
       subscription_id="...",
       resource_group="production-rg",
       credentials=AzureCredentials(use_cli_credentials=True),
   )
   ```

## Incident Response Patterns

### Instance Isolation (AWS)

```python
async def isolate_compromised_instance(client: AWSClient, instance_id: str):
    """Isolate a potentially compromised EC2 instance."""
    
    # 1. Create a snapshot for forensics
    # (Use EC2 directly for this)
    
    # 2. Move to quarantine security group
    await client.ec2.isolate_instance(
        instance_id=instance_id,
        quarantine_security_group="sg-quarantine"
    )
    
    # 3. Log the action
    logger.warning(f"Isolated instance {instance_id} to quarantine")
```

### Database Failover

```python
async def emergency_database_failover(client: AWSClient, cluster_id: str):
    """Perform emergency failover when primary is unhealthy."""
    
    # 1. Verify the issue
    metrics = await client.rds.get_instance_metrics(cluster_id)
    
    # 2. Trigger failover
    await client.rds.failover_cluster(cluster_id)
    
    # 3. Monitor recovery
    logger.warning(f"Initiated failover for {cluster_id}")
```

### Throttle Runaway Function

```python
async def throttle_runaway_lambda(client: AWSClient, function_name: str):
    """Stop a Lambda function that's causing issues."""
    
    # 1. Throttle the function (set concurrency to 0)
    await client.lambda_.throttle_function(function_name)
    
    # 2. Get error logs for investigation
    errors = await client.lambda_.get_function_errors(function_name)
    
    logger.warning(f"Throttled function {function_name}: {len(errors)} recent errors")
```

## Configuration Reference

### AWS Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `region` | str | `us-west-2` | AWS region |
| `credentials` | AWSCredentials | None | Authentication credentials |
| `endpoint_url` | str | None | Custom endpoint (LocalStack) |
| `max_retries` | int | 3 | API retry count |
| `timeout_seconds` | int | 30 | Request timeout |
| `tags` | dict | {} | Default tags for resources |

### GCP Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `project_id` | str | Required | GCP project ID |
| `region` | str | `us-central1` | Default region |
| `zone` | str | Auto | Default zone |
| `credentials` | GCPCredentials | None | Authentication |
| `timeout_seconds` | int | 30 | Request timeout |
| `labels` | dict | {} | Default labels |

### Azure Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `subscription_id` | str | Required | Azure subscription ID |
| `resource_group` | str | Required | Default resource group |
| `location` | str | `eastus` | Default region |
| `credentials` | AzureCredentials | None | Authentication |
| `timeout_seconds` | int | 30 | Request timeout |
| `tags` | dict | {} | Default tags |

## Required Permissions

### AWS IAM Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:RebootInstances",
                "ec2:ModifyInstanceAttribute",
                "eks:Describe*",
                "eks:List*",
                "eks:UpdateNodegroupConfig",
                "rds:Describe*",
                "rds:CreateDBSnapshot",
                "rds:RebootDBInstance",
                "rds:FailoverDBCluster",
                "lambda:List*",
                "lambda:Get*",
                "lambda:Invoke*",
                "lambda:PutFunctionConcurrency",
                "cloudwatch:GetMetricData",
                "logs:GetLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

### GCP IAM Roles

- `roles/compute.viewer` - View GCE instances
- `roles/compute.instanceAdmin.v1` - Manage GCE instances
- `roles/container.viewer` - View GKE clusters
- `roles/container.clusterAdmin` - Manage GKE clusters
- `roles/cloudsql.viewer` - View Cloud SQL
- `roles/cloudsql.admin` - Manage Cloud SQL
- `roles/cloudfunctions.viewer` - View Cloud Functions
- `roles/cloudfunctions.developer` - Manage Cloud Functions
- `roles/monitoring.viewer` - View Cloud Monitoring metrics

### Azure RBAC Roles

- `Reader` - View all resources
- `Virtual Machine Contributor` - Manage VMs
- `Azure Kubernetes Service Cluster Admin Role` - Manage AKS
- `SQL DB Contributor` - Manage Azure SQL
- `Website Contributor` - Manage Functions
- `Monitoring Reader` - View Azure Monitor metrics

## See Also

- [Cost Optimization Guide](cost.md) - Cloud cost management
- [Security Guide](security.md) - Cloud security scanning
- [Chaos Engineering Guide](chaos.md) - Cloud resilience testing
- [Workflows Guide](workflows.md) - Automate cloud operations
