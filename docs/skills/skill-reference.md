# Skill Reference

Complete reference for all built-in OpenSRE skills.

## Prometheus Skill

Query metrics and manage alerts from Prometheus.

### Configuration

```bash
export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
export OPENSRE_PROMETHEUS_AUTH=none  # or: basic, bearer
export OPENSRE_PROMETHEUS_USERNAME=admin  # for basic auth
export OPENSRE_PROMETHEUS_PASSWORD=secret  # for basic auth
```

### Actions

#### prometheus.query

Execute an instant PromQL query.

```python
result = await prometheus.query(
    query='rate(http_requests_total{status=~"5.."}[5m])',
    time="2024-01-01T00:00:00Z"  # optional, defaults to now
)

# Result:
# {
#   "data": [
#     {"metric": {"job": "api"}, "value": [1704067200, "0.05"]}
#   ],
#   "result_type": "vector"
# }
```

#### prometheus.query_range

Execute a range query over time.

```python
result = await prometheus.query_range(
    query='rate(http_requests_total[5m])',
    start="-1h",  # or absolute timestamp
    end="now",
    step="1m"
)
```

#### prometheus.alerts

Get active alerts.

```python
alerts = await prometheus.alerts(
    state="firing",  # firing, pending, inactive
    match='alertname=~"High.*"'  # label filter
)
```

#### prometheus.silence

Create a silence.

```python
silence_id = await prometheus.silence(
    matchers=[
        {"name": "alertname", "value": "HighErrorRate", "isRegex": False}
    ],
    duration="2h",  # or end_time
    comment="Investigating issue"
)
```

#### prometheus.targets

Get scrape targets.

```python
targets = await prometheus.targets(
    state="up"  # up, down, unknown
)
```

---

## Kubernetes Skill

Manage Kubernetes resources.

### Configuration

```bash
export OPENSRE_KUBECONFIG=~/.kube/config
export OPENSRE_KUBE_CONTEXT=production  # optional
```

### Actions

#### kubernetes.get_pods

List or get pods.

```python
pods = await kubernetes.get_pods(
    namespace="production",
    label_selector="app=checkout",
    field_selector="status.phase=Running"
)

# Get specific pod
pod = await kubernetes.get_pods(
    namespace="production",
    name="checkout-abc123"
)
```

#### kubernetes.get_deployments

List or get deployments.

```python
deployments = await kubernetes.get_deployments(
    namespace="production",
    label_selector="team=platform"
)
```

#### kubernetes.get_events

Get events for a resource.

```python
events = await kubernetes.get_events(
    namespace="production",
    resource="deployment/checkout",
    limit=20
)
```

#### kubernetes.get_logs

Get logs from a pod.

```python
logs = await kubernetes.get_logs(
    namespace="production",
    pod="checkout-abc123",
    container="app",  # optional if single container
    tail_lines=100,
    since="1h"
)
```

#### kubernetes.describe

Describe any resource.

```python
details = await kubernetes.describe(
    resource_type="deployment",
    name="checkout",
    namespace="production"
)
```

#### kubernetes.scale

Scale a deployment.

```python
await kubernetes.scale(
    deployment="checkout",
    namespace="production",
    replicas=5
)
```

**⚠️ Requires approval by default**

#### kubernetes.rollback

Rollback a deployment.

```python
await kubernetes.rollback(
    deployment="checkout",
    namespace="production",
    revision=2  # optional, defaults to previous
)
```

**⚠️ Requires approval by default**

#### kubernetes.restart

Restart a deployment (rolling restart).

```python
await kubernetes.restart(
    deployment="checkout",
    namespace="production"
)
```

**⚠️ Requires approval by default**

#### kubernetes.delete_pod

Delete a pod.

```python
await kubernetes.delete_pod(
    namespace="production",
    name="checkout-abc123"
)
```

**⚠️ Requires approval by default**

---

## Slack Skill

Send messages and interactive notifications.

### Configuration

```bash
export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
export OPENSRE_SLACK_APP_TOKEN=xapp-your-token  # for Socket Mode
export OPENSRE_SLACK_CHANNEL=#incidents
```

### Actions

#### slack.post_message

Send a simple message.

```python
await slack.post_message(
    channel="#incidents",
    text="🚨 High error rate detected on checkout service"
)
```

#### slack.post_thread

Reply in a thread.

```python
await slack.post_thread(
    channel="#incidents",
    thread_ts="1234567890.123456",
    text="Update: Error rate now at 2%"
)
```

#### slack.post_blocks

Send a rich message with blocks.

```python
await slack.post_blocks(
    channel="#incidents",
    blocks=[
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔍 Investigation Complete"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Root Cause:* Memory leak in checkout-v2.4.1"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Error Rate:* 8.3%"},
                {"type": "mrkdwn", "text": "*Duration:* 15 minutes"}
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve Rollback"},
                    "style": "primary",
                    "action_id": "approve_rollback"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Dismiss"},
                    "action_id": "dismiss"
                }
            ]
        }
    ],
    text="Investigation complete - approval needed"  # Fallback
)
```

#### slack.react

Add an emoji reaction.

```python
await slack.react(
    channel="#incidents",
    timestamp="1234567890.123456",
    emoji="white_check_mark"
)
```

#### slack.update_message

Update an existing message.

```python
await slack.update_message(
    channel="#incidents",
    timestamp="1234567890.123456",
    text="✅ Issue resolved - rollback complete"
)
```

---

## AWS Skill

Manage AWS resources.

### Configuration

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
# Or use IAM roles
```

### Actions

#### aws.ec2_describe

Describe EC2 instances.

```python
instances = await aws.ec2_describe(
    filters=[
        {"Name": "tag:Environment", "Values": ["production"]}
    ]
)
```

#### aws.ec2_stop

Stop an EC2 instance.

```python
await aws.ec2_stop(instance_id="i-1234567890abcdef0")
```

**⚠️ Requires approval**

#### aws.rds_describe

Describe RDS instances.

```python
databases = await aws.rds_describe(
    db_instance_identifier="production-db"
)
```

#### aws.cloudwatch_query

Query CloudWatch metrics.

```python
metrics = await aws.cloudwatch_query(
    namespace="AWS/EC2",
    metric_name="CPUUtilization",
    dimensions=[{"Name": "InstanceId", "Value": "i-123"}],
    start_time="-1h",
    period=300
)
```

#### aws.cost_report

Get cost and usage report.

```python
report = await aws.cost_report(
    start_date="2024-01-01",
    end_date="2024-01-31",
    granularity="DAILY",
    group_by=["SERVICE"]
)
```

---

## PagerDuty Skill

Manage PagerDuty incidents.

### Configuration

```bash
export OPENSRE_PAGERDUTY_API_KEY=your-api-key
export OPENSRE_PAGERDUTY_ROUTING_KEY=your-routing-key
```

### Actions

#### pagerduty.get_incidents

Get incidents.

```python
incidents = await pagerduty.get_incidents(
    statuses=["triggered", "acknowledged"],
    urgency="high"
)
```

#### pagerduty.acknowledge

Acknowledge an incident.

```python
await pagerduty.acknowledge(
    incident_id="P12345",
    message="Investigating"
)
```

#### pagerduty.resolve

Resolve an incident.

```python
await pagerduty.resolve(
    incident_id="P12345",
    message="Root cause identified and fixed"
)
```

#### pagerduty.add_note

Add a note to an incident.

```python
await pagerduty.add_note(
    incident_id="P12345",
    note="Error rate decreased to 1%"
)
```

#### pagerduty.get_oncall

Get on-call schedule.

```python
oncall = await pagerduty.get_oncall(
    schedule_id="P67890"
)
```

---

## GitHub Skill

Manage GitHub issues and PRs.

### Configuration

```bash
export GITHUB_TOKEN=ghp_your_token
export OPENSRE_GITHUB_REPO=owner/repo
```

### Actions

#### github.create_issue

Create an issue.

```python
issue = await github.create_issue(
    title="Post-incident: Checkout service memory leak",
    body="## Summary\n\nMemory leak in v2.4.1 caused OOM crashes...",
    labels=["incident", "postmortem"]
)
```

#### github.search_issues

Search issues.

```python
issues = await github.search_issues(
    query="label:incident state:open"
)
```

#### github.get_workflow_runs

Get GitHub Actions runs.

```python
runs = await github.get_workflow_runs(
    workflow="deploy.yaml",
    status="completed"
)
```

---

## ArgoCD Skill

Manage ArgoCD applications.

### Configuration

```bash
export OPENSRE_ARGOCD_URL=https://argocd.example.com
export OPENSRE_ARGOCD_TOKEN=your-token
```

### Actions

#### argocd.get_apps

List applications.

```python
apps = await argocd.get_apps(
    project="production"
)
```

#### argocd.sync

Sync an application.

```python
await argocd.sync(
    app="checkout-service",
    revision="HEAD"
)
```

#### argocd.rollback

Rollback an application.

```python
await argocd.rollback(
    app="checkout-service",
    revision="abc123"
)
```

**⚠️ Requires approval**

---

## Common Patterns

### Chaining Skills

```python
# Get metrics, check K8s, notify Slack
error_rate = await prometheus.query("rate(errors[5m])")

if error_rate > 0.05:
    pods = await kubernetes.get_pods(
        namespace="production",
        label_selector="app=checkout"
    )
    
    failing_pods = [p for p in pods if p["status"] != "Running"]
    
    await slack.post_message(
        channel="#incidents",
        text=f"🚨 High error rate ({error_rate:.1%}), {len(failing_pods)} failing pods"
    )
```

### Error Handling

```python
from opensre.skills import SkillError

try:
    await kubernetes.rollback(deployment="checkout", namespace="production")
except SkillError as e:
    await slack.post_message(
        channel="#incidents",
        text=f"❌ Rollback failed: {e}"
    )
```

### Approval Workflow

```python
# Post with approval buttons
msg = await slack.post_blocks(
    channel="#incidents",
    blocks=[...approval_buttons...],
    metadata={"action": "rollback", "deployment": "checkout"}
)

# OpenSRE handles button clicks and executes approved actions
```

## Next Steps

- **[Creating Skills](creating-skills.md)** — Write your own skills
- **[Agent Configuration](../agents/overview.md)** — Use skills in agents
