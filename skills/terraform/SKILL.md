# Terraform Skill

Terraform Cloud/Enterprise workspace and run management.

## Configuration

```yaml
terraform:
  url: https://app.terraform.io  # or self-hosted TFE URL
  token: ${TF_API_TOKEN}
  organization: my-org
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `list_workspaces` | List workspaces | `search` |
| `get_workspace` | Get workspace details | `name` |
| `get_runs` | List workspace runs | `workspace_name`, `status` |
| `get_run` | Get run details | `run_id` |
| `apply_run` | Apply confirmed run | `run_id`, `comment` |
| `cancel_run` | Cancel pending run | `run_id`, `comment` |
| `lock_workspace` | Lock workspace | `workspace_name`, `reason` |
| `unlock_workspace` | Unlock workspace | `workspace_name` |

## Example Usage

```python
# List workspaces
result = await terraform.list_workspaces(search="prod")

# Get runs for a workspace
result = await terraform.get_runs(
    workspace_name="prod-infrastructure",
    status="pending"
)

# Apply a confirmed run
result = await terraform.apply_run(
    run_id="run-abc123",
    comment="Approved by SRE team"
)

# Lock workspace during incident
result = await terraform.lock_workspace(
    workspace_name="prod-infrastructure",
    reason="Locked during incident INC-123"
)
```

## Token Permissions

Required: Organization or Team API Token with workspace access.
