# Azure Skill

Interact with Microsoft Azure for Virtual Machines, AKS, Monitor, and Application Insights.

## Configuration

```yaml
azure:
  tenant_id: ${AZURE_TENANT_ID}
  client_id: ${AZURE_CLIENT_ID}
  client_secret: ${AZURE_CLIENT_SECRET}
  subscription_id: ${AZURE_SUBSCRIPTION_ID}
  use_cli_auth: false          # Use Azure CLI authentication
  use_managed_identity: false  # Use managed identity
  resource_group: my-rg        # Default resource group
```

## Actions

### Virtual Machine Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `vm_list` | List virtual machines | `resource_group` |
| `vm_start` | Start a VM | `name`, `resource_group` |
| `vm_stop` | Stop a VM | `name`, `resource_group` |

### AKS Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `aks_list_clusters` | List AKS clusters | `resource_group` |
| `aks_get_credentials` | Get cluster credentials | `name`, `resource_group` |

### Monitor Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `monitor_query` | Query Azure Monitor | `query`, `workspace_id`, `timespan` |

### Application Insights Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `app_insights_query` | Query App Insights | `query`, `app_id`, `timespan` |

## Authentication

Supports multiple authentication methods:
1. **Service Principal** - `tenant_id`, `client_id`, `client_secret`
2. **Azure CLI** - `use_cli_auth: true`
3. **Managed Identity** - `use_managed_identity: true` (for Azure-hosted workloads)

## Example Usage

```python
# List VMs in a resource group
result = await azure.vm_list(resource_group="production-rg")

# Query Azure Monitor for CPU metrics
result = await azure.monitor_query(
    query="Perf | where ObjectName == 'Processor' | summarize avg(CounterValue) by Computer",
    workspace_id="your-workspace-id",
    timespan="PT1H"
)
```

## Required Azure Permissions

- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/start/action`
- `Microsoft.Compute/virtualMachines/powerOff/action`
- `Microsoft.ContainerService/managedClusters/read`
- `Microsoft.OperationalInsights/workspaces/query/read`
- `Microsoft.Insights/components/query/read`
