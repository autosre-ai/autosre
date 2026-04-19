# Multi-Cloud Monitoring Example

Monitor AWS, GCP, and Azure from a single agent.

## What This Does

1. Aggregates health data from multiple clouds
2. Detects cross-cloud issues
3. Provides unified alerting
4. Generates cost comparisons

## Setup

### Configure Cloud Credentials

```bash
# AWS
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1

# GCP
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Azure
export AZURE_SUBSCRIPTION_ID=...
export AZURE_TENANT_ID=...
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...
```

### Install Cloud Skills

```bash
opensre skill install aws gcp azure
```

### Deploy Agent

```bash
cp examples/multi-cloud-monitoring/agent.yaml agents/
opensre start
```

## Use Cases

### Cross-Cloud Health Check

Monitor resources across all clouds:
- AWS EC2 instances
- GCP Compute Engine VMs
- Azure Virtual Machines

### Unified Cost Reporting

Daily cost summary across all providers.

### Multi-Cloud Incident Response

Correlate issues that span cloud boundaries.

## Files

- `agent.yaml` — Agent configuration
- `health-check.yaml` — Health check agent
- `cost-report.yaml` — Cost reporting agent
