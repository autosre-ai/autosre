# GitHub Skill

Integration with GitHub for issue tracking, PR management, and workflow automation.

## Actions

| Action | Description |
|--------|-------------|
| `create_issue` | Create a new issue |
| `close_issue` | Close an issue |
| `create_pr_comment` | Comment on a PR |
| `get_workflow_runs` | List workflow runs |
| `trigger_workflow` | Dispatch a workflow |
| `get_commit` | Get commit details |

## Configuration

Required environment variables:
- `GITHUB_TOKEN` — Personal access token or GitHub App token

## Usage

```python
from skills.github import GitHubSkill

skill = GitHubSkill()

# Create an issue
issue = await skill.create_issue(
    repo="org/repo",
    title="Bug: Service timeout",
    body="Seeing increased timeouts...",
    labels=["bug", "priority:high"]
)

# Comment on a PR
await skill.create_pr_comment(
    repo="org/repo",
    pr_number=42,
    body="LGTM! Tested locally."
)

# Trigger workflow
await skill.trigger_workflow(
    repo="org/repo",
    workflow="deploy.yml",
    inputs={"environment": "staging"}
)

# Get workflow runs
runs = await skill.get_workflow_runs(
    repo="org/repo",
    workflow="ci.yml"
)
```

## Rate Limiting

Built-in rate limiting respects GitHub's API limits:
- 5,000 requests/hour for authenticated requests
- Automatic retry on rate limit with backoff

## Dependencies

- `aiohttp>=3.8.0`
- `pydantic>=2.0.0`
