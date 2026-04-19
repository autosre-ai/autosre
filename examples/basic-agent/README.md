# Basic Agent Example

A minimal OpenSRE agent to get you started.

## What This Does

This agent listens for high error rate alerts and:
1. Queries Prometheus for more details
2. Posts a summary to Slack
3. Suggests next steps

## Files

- `agent.yaml` — Agent configuration
- `config.yaml` — Environment configuration

## Setup

1. Copy this directory to your OpenSRE installation:
   ```bash
   cp -r examples/basic-agent agents/
   ```

2. Configure environment:
   ```bash
   export OPENSRE_PROMETHEUS_URL=http://prometheus:9090
   export OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
   export OPENSRE_SLACK_CHANNEL=#alerts
   ```

3. Start OpenSRE:
   ```bash
   opensre start
   ```

## Testing

Trigger a test alert:

```bash
opensre agent test basic-agent \
  --alert '{"alertname": "HighErrorRate", "labels": {"service": "api"}}'
```

## Customization

Edit `agent.yaml` to:
- Change trigger conditions
- Add more skills
- Modify the runbook

## Next Steps

- Add more sophisticated analysis
- Add remediation actions
- Integrate with your incident management system
