# Jenkins Skill

CI/CD integration with Jenkins.

## Configuration

```yaml
jenkins:
  url: https://jenkins.example.com
  username: ${JENKINS_USER}
  api_token: ${JENKINS_TOKEN}
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `get_jobs` | List jobs | `folder` |
| `get_job` | Get job details | `name` |
| `trigger_build` | Trigger build | `name`, `parameters` |
| `get_build` | Get build details | `job_name`, `build_number` |
| `get_build_log` | Get console output | `job_name`, `build_number` |
| `stop_build` | Stop running build | `job_name`, `build_number` |

## Example Usage

```python
# List all jobs
result = await jenkins.get_jobs()

# Trigger a build with parameters
result = await jenkins.trigger_build(
    name="deploy-app",
    parameters={"ENVIRONMENT": "staging", "VERSION": "1.2.3"}
)

# Get build status
result = await jenkins.get_build(job_name="deploy-app", build_number=123)

# Get build log
result = await jenkins.get_build_log(job_name="deploy-app", build_number=123)
```

## API Token

Generate an API token in Jenkins:
1. Go to User → Configure
2. API Token → Add new token
