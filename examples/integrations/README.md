# AutoSRE Integration Examples

This directory contains example configuration files for integrating AutoSRE with popular incident management and notification platforms.

## Available Integrations

| Integration | File | Description |
|-------------|------|-------------|
| Slack | `slack.yaml` | Real-time notifications, bot commands, approval workflows |
| PagerDuty | `pagerduty.yaml` | Incident creation, on-call integration, escalation automation |
| OpsGenie | `opsgenie.yaml` | Alert management, team routing, incident coordination |

## Quick Start

### 1. Copy the Configuration

Copy the desired integration config to your AutoSRE config directory:

```bash
# For Slack integration
cp examples/integrations/slack.yaml ~/.autosre/integrations/slack.yaml

# For PagerDuty integration
cp examples/integrations/pagerduty.yaml ~/.autosre/integrations/pagerduty.yaml

# For OpsGenie integration
cp examples/integrations/opsgenie.yaml ~/.autosre/integrations/opsgenie.yaml
```

### 2. Set Environment Variables

Each integration requires credentials stored as environment variables. Create a `.env` file or set them in your shell:

```bash
# Slack
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
export SLACK_SIGNING_SECRET="..."

# PagerDuty
export PAGERDUTY_API_TOKEN="u+..."
export PAGERDUTY_ROUTING_KEY="R0..."
export PAGERDUTY_WEBHOOK_SECRET="..."

# OpsGenie
export OPSGENIE_API_KEY="..."
export OPSGENIE_WEBHOOK_SECRET="..."
```

### 3. Enable the Integration

Add the integration to your main AutoSRE config:

```yaml
# config.yaml
integrations:
  slack:
    enabled: true
    config_path: ~/.autosre/integrations/slack.yaml
  
  pagerduty:
    enabled: true
    config_path: ~/.autosre/integrations/pagerduty.yaml
  
  opsgenie:
    enabled: false  # Enable as needed
    config_path: ~/.autosre/integrations/opsgenie.yaml
```

## Integration Features

### Slack (`slack.yaml`)

- **Real-time notifications**: Alerts posted to configurable channels
- **Bot commands**: `/autosre investigate`, `/autosre status`, etc.
- **Approval workflows**: Require human approval for remediation actions
- **Rich formatting**: Block Kit messages with action buttons
- **Threading**: Related alerts grouped in threads
- **On-call integration**: Mention on-call responders

### PagerDuty (`pagerduty.yaml`)

- **Incident creation**: Auto-create incidents from critical alerts
- **Service mapping**: Route to correct PagerDuty services
- **On-call lookup**: Include on-call info in investigations
- **Escalation automation**: Auto-escalate stale incidents
- **Bi-directional sync**: PagerDuty updates sync to AutoSRE
- **Change events**: Report deployments and remediations

### OpsGenie (`opsgenie.yaml`)

- **Team-based routing**: Route alerts to appropriate teams
- **Priority mapping**: Map severity to OpsGenie priorities
- **Custom actions**: Trigger investigations from OpsGenie UI
- **On-call integration**: Include schedule info in context
- **Incident management**: Create incidents, update status pages
- **Heartbeat monitoring**: Monitor AutoSRE health via OpsGenie

## Using Multiple Integrations

AutoSRE supports using multiple integrations simultaneously. Common patterns:

### Slack + PagerDuty

- PagerDuty for on-call paging and incident management
- Slack for team communication and investigation updates

### Slack + OpsGenie

- OpsGenie for alert routing and on-call management
- Slack for collaboration and runbook approvals

### All Three

- OpsGenie/PagerDuty as primary alerting (choose one)
- Slack for all team communication
- Deduplicate notifications to avoid alert fatigue

## Configuration Tips

### Environment-Specific Settings

Use environment variable substitution for different environments:

```yaml
# In your integration config
connection:
  api_url: "${PAGERDUTY_API_URL:-https://api.pagerduty.com}"
```

### Secrets Management

For production deployments:

1. **Kubernetes**: Use Secrets or External Secrets Operator
2. **AWS**: Use AWS Secrets Manager with IAM roles
3. **Vault**: Use HashiCorp Vault with dynamic secrets
4. **Local**: Use `.env` files (not committed to git)

### Testing Integrations

Test your integration in a safe environment:

```bash
# Validate config syntax
autosre config validate --integration slack

# Test connection (dry-run mode)
autosre integration test slack --dry-run

# Send a test alert
autosre integration test slack --send-test-alert
```

## Customization

All configuration files are extensively commented. Key areas to customize:

1. **Channels/Teams**: Update channel names and team IDs
2. **Service Mappings**: Map your services to notification routes
3. **Templates**: Customize message formats for your team
4. **Severity Mapping**: Adjust priority thresholds
5. **Approval Workflows**: Configure which actions need approval

## Troubleshooting

### Common Issues

**Slack: Messages not appearing**
- Verify bot token has correct scopes
- Check bot is invited to the channel
- Ensure Socket Mode is enabled for the app

**PagerDuty: Incidents not creating**
- Verify routing key is from the correct service
- Check API token has incident write permissions
- Ensure service is not in maintenance mode

**OpsGenie: Alerts not routing**
- Verify API key is from an API integration (not OAuth)
- Check team IDs are correct
- Ensure region setting matches your account (US/EU)

### Debug Mode

Enable debug logging for troubleshooting:

```yaml
# In integration config
advanced:
  debug: true
```

Then check AutoSRE logs:

```bash
autosre logs --integration slack --level debug
```

## Contributing

Have a new integration to add? We welcome contributions!

1. Create a new YAML file following the existing patterns
2. Include comprehensive comments
3. Add examples for all major features
4. Update this README
5. Submit a pull request

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.
