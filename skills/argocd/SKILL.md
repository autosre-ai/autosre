# ArgoCD Skill

Integration with ArgoCD for GitOps application management.

## Actions

| Action | Description |
|--------|-------------|
| `list_applications` | List all applications |
| `get_application` | Get application details |
| `sync_application` | Trigger application sync |
| `rollback_application` | Rollback to revision |
| `get_application_health` | Get health status |

## Configuration

Required environment variables:
- `ARGOCD_SERVER` — ArgoCD server URL
- `ARGOCD_TOKEN` — API token

Optional:
- `ARGOCD_INSECURE` — Skip TLS verification (default: false)

## Usage

```python
from skills.argocd import ArgoCDSkill

skill = ArgoCDSkill()

# List applications
apps = await skill.list_applications()

# Get application details
app = await skill.get_application("my-app")
print(f"Status: {app.health_status}, Sync: {app.sync_status}")

# Trigger sync
await skill.sync_application("my-app")

# Rollback
await skill.rollback_application("my-app", revision=5)

# Check health
health = await skill.get_application_health("my-app")
if health.is_degraded:
    print(f"Degraded: {health.message}")
```

## Rate Limiting

Built-in rate limiting to avoid overwhelming the ArgoCD server.

## Dependencies

- `aiohttp>=3.8.0`
- `pydantic>=2.0.0`
