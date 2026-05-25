# AutoSRE Workflow Examples

This directory contains example workflow definitions demonstrating the AutoSRE workflow engine capabilities.

## Files

- `incident-triage.yaml` - Basic incident triage workflow
- `canary-deployment.yaml` - Canary deployment with automated rollback  
- `database-maintenance.yaml` - Scheduled database maintenance workflow
- `cost-optimization.yaml` - Cost optimization automation

## Usage

```python
from autosre.workflows import WorkflowEngine, parse_workflow_file

# Create engine
engine = WorkflowEngine()

# Load and register workflow
workflow = parse_workflow_file("incident-triage.yaml")
engine.register_workflow(workflow)

# Execute
execution = await engine.execute(
    workflow_id=workflow.id,
    inputs={"alert_id": "alert-123"}
)
```

## DSL Reference

See the [Workflows Guide](../../docs/guides/workflows.md) for full DSL documentation.
