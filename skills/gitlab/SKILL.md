# GitLab Skill

Pipeline, issue, and merge request management for GitLab.

## Configuration

```yaml
gitlab:
  url: https://gitlab.com  # or self-hosted GitLab URL
  token: ${GITLAB_TOKEN}
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `get_pipelines` | List pipelines | `project_id`, `status` |
| `get_pipeline` | Get pipeline details | `project_id`, `pipeline_id` |
| `trigger_pipeline` | Trigger new pipeline | `project_id`, `ref`, `variables` |
| `cancel_pipeline` | Cancel running pipeline | `project_id`, `pipeline_id` |
| `retry_pipeline` | Retry failed pipeline | `project_id`, `pipeline_id` |
| `get_merge_requests` | List merge requests | `project_id`, `state` |
| `get_jobs` | List pipeline jobs | `project_id`, `pipeline_id` |

## Example Usage

```python
# List running pipelines
result = await gitlab.get_pipelines(
    project_id="mygroup/myproject",
    status="running"
)

# Trigger a pipeline
result = await gitlab.trigger_pipeline(
    project_id="mygroup/myproject",
    ref="main",
    variables={"DEPLOY_ENV": "staging"}
)

# List open merge requests
result = await gitlab.get_merge_requests(
    project_id="mygroup/myproject",
    state="opened"
)
```

## Token Permissions

Required scopes: `api`, `read_repository`
