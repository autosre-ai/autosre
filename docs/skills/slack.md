# Slack Skill

Send messages, notifications, and interactive buttons to Slack.

## Overview

| Property | Value |
|----------|-------|
| **Name** | `slack` |
| **Version** | 1.0.0 |
| **Category** | Notifications |
| **Approval** | Auto-approved |

## Configuration

```yaml
# config/opensre.yaml
slack:
  bot_token: ${SLACK_BOT_TOKEN}
  app_token: ${SLACK_APP_TOKEN}  # For Socket Mode
  signing_secret: ${SLACK_SIGNING_SECRET}
  default_channel: "#incidents"
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENSRE_SLACK_BOT_TOKEN` | Bot user OAuth token (xoxb-...) |
| `OPENSRE_SLACK_APP_TOKEN` | App-level token (xapp-...) |
| `OPENSRE_SLACK_SIGNING_SECRET` | Request signing secret |
| `OPENSRE_SLACK_CHANNEL` | Default notification channel |

### Required OAuth Scopes

Your Slack app needs these scopes:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Send messages |
| `chat:write.public` | Send to channels without joining |
| `channels:read` | List channels |
| `groups:read` | List private channels |
| `users:read` | Look up user info |
| `reactions:write` | Add emoji reactions |
| `files:write` | Upload files |

### Setting Up Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create New App → From scratch
3. Add OAuth scopes under "OAuth & Permissions"
4. Install to workspace
5. Copy Bot User OAuth Token

For interactive buttons (approvals):
1. Enable Socket Mode
2. Generate App-Level Token with `connections:write`
3. Enable Interactivity

## Actions

### `post_message`

Send a message to a channel.

```yaml
action: slack.post_message
params:
  channel: "#incidents"
  text: "🚨 High error rate detected on checkout service"
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel name or ID |
| `text` | string | yes | Message text (supports mrkdwn) |
| `thread_ts` | string | no | Thread timestamp for replies |
| `username` | string | no | Custom username |
| `icon_emoji` | string | no | Custom emoji icon |
| `unfurl_links` | boolean | no | Unfurl URLs |

**Returns:**

```json
{
  "ok": true,
  "channel": "C1234567890",
  "ts": "1710511200.123456",
  "message": {
    "text": "🚨 High error rate detected on checkout service"
  }
}
```

### `post_blocks`

Send a rich message with Block Kit.

```yaml
action: slack.post_blocks
params:
  channel: "#incidents"
  blocks:
    - type: header
      text:
        type: plain_text
        text: "🚨 Incident Alert"
    - type: section
      text:
        type: mrkdwn
        text: "*Service:* checkout\n*Error Rate:* 8.3%"
    - type: actions
      elements:
        - type: button
          text:
            type: plain_text
            text: "✅ Acknowledge"
          action_id: ack_incident
          style: primary
        - type: button
          text:
            type: plain_text
            text: "👁️ View Details"
          action_id: view_details
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel name or ID |
| `blocks` | array | yes | Block Kit blocks |
| `text` | string | no | Fallback text |
| `thread_ts` | string | no | Thread timestamp |

### `post_approval`

Send an approval request with interactive buttons.

```yaml
action: slack.post_approval
params:
  channel: "#sre"
  title: "Rollback Approval Required"
  description: |
    Agent wants to rollback checkout-service to v2.4.0
    Reason: Memory leak detected
  approve_text: "✅ Approve Rollback"
  deny_text: "❌ Deny"
  timeout: 300
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel for approval request |
| `title` | string | yes | Approval title |
| `description` | string | yes | Action description |
| `approve_text` | string | no | Approve button text |
| `deny_text` | string | no | Deny button text |
| `timeout` | integer | no | Timeout in seconds |
| `approvers` | array | no | Restrict to specific users |

**Returns:**

```json
{
  "approved": true,
  "approved_by": "U1234567890",
  "approved_at": "2024-03-15T14:32:05Z"
}
```

### `update_message`

Update an existing message.

```yaml
action: slack.update_message
params:
  channel: "#incidents"
  ts: "{{ previous_message.ts }}"
  text: "✅ Incident resolved"
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel ID |
| `ts` | string | yes | Message timestamp |
| `text` | string | no | New text |
| `blocks` | array | no | New blocks |

### `add_reaction`

Add an emoji reaction to a message.

```yaml
action: slack.add_reaction
params:
  channel: "#incidents"
  ts: "{{ message.ts }}"
  emoji: "white_check_mark"
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel ID |
| `ts` | string | yes | Message timestamp |
| `emoji` | string | yes | Emoji name (without colons) |

### `create_channel`

Create a new channel.

```yaml
action: slack.create_channel
params:
  name: "incident-20240315-checkout"
  is_private: false
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | yes | Channel name |
| `is_private` | boolean | no | Create as private channel |

**Returns:**

```json
{
  "channel": {
    "id": "C1234567890",
    "name": "incident-20240315-checkout"
  }
}
```

### `invite_users`

Invite users to a channel.

```yaml
action: slack.invite_users
params:
  channel: "#incident-20240315-checkout"
  users:
    - "@alice"
    - "@bob"
```

### `upload_file`

Upload a file to a channel.

```yaml
action: slack.upload_file
params:
  channel: "#incidents"
  filename: "pod-logs.txt"
  content: "{{ logs.output }}"
  title: "Pod logs from checkout-abc123"
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | string | yes | Channel ID |
| `filename` | string | yes | File name |
| `content` | string | yes | File content |
| `title` | string | no | File title |
| `filetype` | string | no | File type (auto-detected) |

### `lookup_user`

Look up user information.

```yaml
action: slack.lookup_user
params:
  email: "alice@example.com"
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `email` | string | no | User email |
| `user_id` | string | no | User ID |

## Examples

### Incident Notification Agent

```yaml
name: incident-notifier
skills:
  - slack
  - prometheus

steps:
  - name: post-alert
    action: slack.post_blocks
    params:
      channel: "#incidents"
      blocks:
        - type: header
          text:
            type: plain_text
            text: "🚨 {{ alert.name }}"
        - type: section
          fields:
            - type: mrkdwn
              text: "*Service:*\n{{ alert.labels.service }}"
            - type: mrkdwn
              text: "*Severity:*\n{{ alert.labels.severity }}"
            - type: mrkdwn
              text: "*Namespace:*\n{{ alert.labels.namespace }}"
            - type: mrkdwn
              text: "*Started:*\n{{ alert.startsAt }}"
        - type: section
          text:
            type: mrkdwn
            text: "{{ alert.annotations.description }}"
        - type: actions
          elements:
            - type: button
              text:
                type: plain_text
                text: "🔍 Investigate"
              action_id: investigate
              style: primary
            - type: button
              text:
                type: plain_text
                text: "🔕 Silence (2h)"
              action_id: silence_2h
    output: alert_message

  - name: create-incident-channel
    action: slack.create_channel
    params:
      name: "inc-{{ now | strftime('%Y%m%d') }}-{{ alert.labels.service }}"
    output: incident_channel
    condition: "{{ alert.labels.severity == 'critical' }}"

  - name: invite-oncall
    action: slack.invite_users
    params:
      channel: "{{ incident_channel.channel.id }}"
      users:
        - "@oncall-primary"
        - "@oncall-secondary"
    condition: "{{ incident_channel is defined }}"
```

### Approval Workflow

```yaml
name: rollback-with-approval
skills:
  - kubernetes
  - slack

steps:
  - name: request-approval
    action: slack.post_approval
    params:
      channel: "#sre"
      title: "🔄 Rollback Approval Required"
      description: |
        *Deployment:* {{ deployment }}
        *Namespace:* {{ namespace }}
        *Current Version:* {{ current_version }}
        *Target Version:* {{ target_version }}
        
        *Reason:* {{ reason }}
        
        This action will rollback the deployment to the previous version.
      timeout: 300
    output: approval

  - name: execute-rollback
    action: kubernetes.rollback_deployment
    params:
      name: "{{ deployment }}"
      namespace: "{{ namespace }}"
    condition: "{{ approval.approved }}"
    output: rollback_result

  - name: notify-success
    action: slack.post_message
    params:
      channel: "#sre"
      text: "✅ Rollback completed successfully by <@{{ approval.approved_by }}>"
    condition: "{{ rollback_result.success }}"
```

## Message Formatting

### Markdown (mrkdwn)

```
*bold*
_italic_
~strikethrough~
`code`
```code block```
>quote
<https://example.com|Link Text>
<@U1234567890> (mention user)
<#C1234567890> (mention channel)
<!here> <!channel> <!everyone>
```

### Common Block Patterns

**Header + Section:**
```yaml
blocks:
  - type: header
    text:
      type: plain_text
      text: "Alert Title"
  - type: section
    text:
      type: mrkdwn
      text: "Alert description with *formatting*"
```

**Two-Column Layout:**
```yaml
blocks:
  - type: section
    fields:
      - type: mrkdwn
        text: "*Status:* 🔴 Critical"
      - type: mrkdwn
        text: "*Service:* checkout"
```

**Button Actions:**
```yaml
blocks:
  - type: actions
    elements:
      - type: button
        text:
          type: plain_text
          text: "Primary Action"
        action_id: primary
        style: primary
      - type: button
        text:
          type: plain_text
          text: "Danger Action"
        action_id: danger
        style: danger
```

## Troubleshooting

### invalid_auth

```bash
# Test your token
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer xoxb-your-token"
```

Make sure:
- Token starts with `xoxb-` (bot token)
- App is installed to workspace
- Token hasn't been revoked

### channel_not_found

- Use channel ID instead of name for private channels
- Ensure bot is member of the channel (`/invite @opensre`)

### missing_scope

Check OAuth scopes in app settings:
- `chat:write` for posting
- `channels:read` for channel lookup
- `reactions:write` for reactions

### Rate Limiting

Slack rate limits API calls. OpenSRE handles this automatically with:
- Exponential backoff
- Request queuing
- Tier-aware throttling

## See Also

- [Skills Overview](overview.md)
- [Slack Setup Guide](../SLACK_SETUP.md)
- [PagerDuty Skill](pagerduty.md)
