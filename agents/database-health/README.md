# Database Health Agent

Monitor database health including connection pools, replication lag, deadlocks, and query performance.

## Overview

The Database Health agent provides comprehensive monitoring for PostgreSQL, MySQL, and Redis databases. It checks connection pool utilization, replication lag, deadlocks, long-running queries, and cache performance.

## Features

- **Connection Pool Monitoring** - Track pool utilization and alert before exhaustion
- **Replication Lag Tracking** - Monitor replica lag with tiered alerts
- **Deadlock Detection** - Alert on database deadlocks
- **Long-Running Query Detection** - Identify and optionally kill stuck queries
- **Cache Health** - Monitor Redis hit ratios and memory usage
- **Table Bloat Analysis** - Identify tables needing vacuum
- **Disk Usage Tracking** - Monitor database disk consumption

## Configuration

```yaml
config:
  slack_channel: "#database-alerts"
  databases:
    - name: primary-postgres
      type: postgres
      host: "primary.db.example.com"
      port: 5432
      metrics_job: "postgres-exporter"
    - name: cache-redis
      type: redis
      host: "redis.example.com"
      port: 6379
  thresholds:
    connection_pool_usage_warning: 70
    connection_pool_usage_critical: 90
    replication_lag_warning_seconds: 5
    replication_lag_critical_seconds: 30
    deadlock_count_alert: 1
    long_running_query_seconds: 60
    cache_hit_ratio_warning: 0.90
```

## Checks Performed

### Connection Pool
- Active connections
- Idle connections
- Pool utilization percentage
- Connection trends

### Replication
- Lag in seconds
- WAL position delta
- Replication slot status

### Performance
- Long-running queries (>60s default)
- Slow query rate
- Query duration P99
- Deadlock count

### Cache (Redis)
- Hit ratio
- Memory usage
- Eviction rate
- Connected clients

## Triggers

- **Schedule**: Every 5 minutes
- **Manual**: `/webhook/db-check`
- **Alertmanager**: `/webhook/db-alert`

## Alert Examples

### Connection Pool Critical
```
🚨 Database Connection Pool Critical

Pool Usage: 92.5%
Active Connections: 85
Idle Connections: 20
Max Connections: 100

Recommended Actions:
1. Increase max_connections (requires restart)
2. Review connection pooling (PgBouncer)
3. Check for connection leaks in applications
```

### Long-Running Queries
```
⏱️ Long-Running Queries Detected

3 queries running longer than 60s:

• PID 12345 - 5m 32s
  User: app_user | State: active
  SELECT * FROM large_table WHERE...
```

## Metrics

| Metric | Description |
|--------|-------------|
| `opensre_db_connection_pool_percent` | Connection pool utilization |
| `opensre_db_replication_lag_seconds` | Replication lag |
| `opensre_db_deadlocks_total` | Deadlock count |
| `opensre_db_long_queries_count` | Long-running queries |
| `opensre_cache_hit_ratio` | Cache hit ratio |

## Prerequisites

- PostgreSQL with `pg_stat_statements` extension
- Prometheus postgres-exporter
- Prometheus redis-exporter (for Redis)
- Database credentials with monitoring permissions

## Usage

```bash
# Run check
opensre agent run agents/database-health/agent.yaml

# Dry run
opensre agent run agents/database-health/agent.yaml --dry-run

# Verbose output
opensre agent run agents/database-health/agent.yaml -v
```

## Related Agents

- [incident-responder](../incident-responder/) - Respond to database incidents
- [capacity-planner](../capacity-planner/) - Plan database capacity
