# Log Analyzer Agent

Pattern detection in logs, anomaly detection, and automated log-based alerting.

## Overview

The Log Analyzer agent monitors application logs for critical patterns, detects anomalies in error rates, and provides AI-powered analysis of log events.

## Features

- **Pattern Detection** - Match critical and warning patterns in logs
- **Anomaly Detection** - Statistical anomaly detection using z-score
- **AI Analysis** - LLM-powered root cause analysis
- **Multi-source Support** - Elasticsearch and Loki
- **Error Rate Tracking** - Monitor error percentages
- **Noise Filtering** - Exclude health checks and debug logs

## Configuration

```yaml
config:
  slack_channel: "#log-alerts"
  log_sources:
    - type: elasticsearch
      index: "logs-*"
      url: "https://elasticsearch.example.com"
    - type: loki
      url: "https://loki.example.com"
  analysis_window_minutes: 10
  patterns:
    critical:
      - pattern: "FATAL|CRITICAL|PANIC"
        min_count: 1
        description: "Fatal errors"
      - pattern: "OutOfMemoryError|OOMKilled"
        min_count: 1
        description: "Memory exhaustion"
    warning:
      - pattern: "ERROR|Exception"
        min_count: 100
        description: "High error rate"
  anomaly_detection:
    enabled: true
    baseline_hours: 24
    deviation_threshold: 3.0
  error_rate_threshold_percent: 5
```

## Pattern Matching

Define regex patterns to match in logs:

### Critical Patterns (Page immediately)
- `FATAL|CRITICAL|PANIC` - Fatal errors
- `OutOfMemoryError|OOMKilled` - Memory exhaustion
- `Connection refused` (50+ occurrences) - Mass connection failures

### Warning Patterns (Alert)
- `ERROR|Exception` (100+ occurrences) - High error rate
- `timeout|Timeout` (20+ occurrences) - Timeout spike
- `retry|Retry` (50+ occurrences) - High retry rate

## Anomaly Detection

Uses statistical anomaly detection:

1. Calculate baseline from past 24 hours
2. Compare current window to baseline
3. Alert if z-score exceeds threshold (default: 3.0)

```
Z-score = (current - mean) / stddev
```

## Triggers

- **Schedule**: Every 10 minutes
- **Manual**: `/webhook/log-analyze`
- **Fluentd**: `/webhook/log-alert`

## Alert Examples

### Critical Pattern Alert
```
🚨 Critical Log Patterns Detected

2 critical pattern(s) found in the last 10 minutes:

• Fatal errors (FATAL|CRITICAL|PANIC)
  Count: 15 | Services: api-server, worker

• Memory exhaustion (OutOfMemoryError|OOMKilled)
  Count: 3 | Services: data-processor

Sample Messages:
```java.lang.OutOfMemoryError: Java heap space...```

AI Analysis:
The OOM errors in data-processor correlate with a spike in 
incoming batch jobs. Consider increasing heap size or adding 
rate limiting.
```

### Anomaly Alert
```
📈 Log Volume Anomaly Detected

Error count in last 10 minutes: 523
Baseline average: 45.2
Z-score: 4.52 (threshold: 3.0)

Top Error Services:
• payment-service: 312 errors
• api-gateway: 156 errors
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_log_error_count` | Error logs in window |
| `opensre_log_error_rate_percent` | Error rate percentage |
| `opensre_log_critical_patterns` | Critical patterns found |
| `opensre_log_anomaly_detected` | Anomaly flag (0/1) |

## Prerequisites

- Elasticsearch or Loki with logs indexed
- Proper log level fields (ERROR, WARN, etc.)
- Service/namespace labels in logs

## Usage

```bash
# Run analysis
opensre agent run agents/log-analyzer/agent.yaml

# Custom time window
opensre agent run agents/log-analyzer/agent.yaml \
  -c "config.analysis_window_minutes=30"

# Dry run
opensre agent run agents/log-analyzer/agent.yaml --dry-run
```

## Related Agents

- [incident-responder](../incident-responder/) - Respond to log-triggered incidents
- [pod-crash-handler](../pod-crash-handler/) - Handle crash loops detected in logs
