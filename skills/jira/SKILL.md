# Jira Skill

Integration with Jira for issue tracking and project management.

## Actions

| Action | Description |
|--------|-------------|
| `create_issue` | Create a new issue |
| `update_issue` | Update issue fields |
| `add_comment` | Add comment to issue |
| `transition_issue` | Change issue status |
| `search_issues` | Search with JQL |
| `get_issue` | Get issue details |

## Configuration

Required environment variables:
- `JIRA_URL` — Jira instance URL (e.g., https://company.atlassian.net)
- `JIRA_EMAIL` — Account email
- `JIRA_API_TOKEN` — API token

## Usage

```python
from skills.jira import JiraSkill

skill = JiraSkill()

# Create an issue
issue = await skill.create_issue(
    project="OPS",
    type="Bug",
    summary="Service degradation detected",
    description="Error rate increased to 5%"
)

# Search issues
results = await skill.search_issues(
    jql="project = OPS AND status = 'In Progress' ORDER BY created DESC"
)

# Transition issue
await skill.transition_issue(
    issue_key="OPS-123",
    transition="Done"
)

# Add comment
await skill.add_comment(
    issue_key="OPS-123",
    comment="Resolved by scaling up replicas"
)
```

## Rate Limiting

Built-in rate limiting respects Atlassian's API limits.

## Dependencies

- `aiohttp>=3.8.0`
- `pydantic>=2.0.0`
