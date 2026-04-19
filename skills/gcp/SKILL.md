# GCP Skill

Interact with Google Cloud Platform for Compute Engine, GKE, Cloud Run, Monitoring, Logging, and BigQuery.

## Configuration

```yaml
gcp:
  credentials_file: /path/to/service-account.json  # Service account JSON
  credentials_json: ${GCP_CREDENTIALS_JSON}        # Or as JSON string
  project: my-project-id                           # Default project
  region: us-central1                              # Default region
  zone: us-central1-a                              # Default zone
```

## Actions

### Compute Engine Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `gce_list_instances` | List VM instances | `zone`, `project` |
| `gce_start_instance` | Start an instance | `name`, `zone` |
| `gce_stop_instance` | Stop an instance | `name`, `zone` |

### GKE Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `gke_list_clusters` | List GKE clusters | `location`, `project` |
| `gke_get_cluster` | Get cluster details | `name`, `location` |

### Cloud Run Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `cloud_run_list_services` | List Cloud Run services | `region`, `project` |
| `cloud_run_update_traffic` | Update traffic split | `service`, `revisions` |

### Monitoring Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `monitoring_query` | Query Cloud Monitoring | `query`, `interval` |

### Logging Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `logging_query` | Query Cloud Logging | `filter`, `project` |

### BigQuery Operations
| Action | Description | Parameters |
|--------|-------------|------------|
| `bigquery_query` | Execute BigQuery SQL | `query`, `project` |

## Authentication

Uses Google Application Default Credentials (ADC):
1. **Service Account JSON file** - `credentials_file`
2. **Service Account JSON string** - `credentials_json`
3. **Environment variable** - `GOOGLE_APPLICATION_CREDENTIALS`
4. **gcloud CLI** - `gcloud auth application-default login`
5. **Compute Engine default** - When running on GCE/GKE

## Example Usage

```python
# List GCE instances
result = await gcp.gce_list_instances(zone="us-central1-a")

# Query Cloud Monitoring for CPU usage
result = await gcp.monitoring_query(
    query='compute.googleapis.com/instance/cpu/utilization',
    interval="300s"
)

# Run BigQuery query
result = await gcp.bigquery_query(
    query="SELECT * FROM `project.dataset.table` LIMIT 10"
)
```

## Required IAM Roles

- `roles/compute.viewer` - For GCE operations
- `roles/container.viewer` - For GKE operations
- `roles/run.viewer` - For Cloud Run operations
- `roles/monitoring.viewer` - For Monitoring queries
- `roles/logging.viewer` - For Logging queries
- `roles/bigquery.dataViewer` - For BigQuery queries
