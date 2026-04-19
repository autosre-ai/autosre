# Elasticsearch Skill

Query Elasticsearch for logs and metrics.

## Configuration

```yaml
elasticsearch:
  hosts:
    - http://localhost:9200
  username: ${ES_USERNAME}
  password: ${ES_PASSWORD}
  # Or use API key
  api_key: ${ES_API_KEY}
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `search` | Execute query | `index`, `query`, `size`, `sort` |
| `count` | Count documents | `index`, `query` |
| `get_indices` | List indices | `pattern` |
| `cluster_health` | Get cluster health | |

## Example Usage

```python
# Search for errors
result = await elasticsearch.search(
    index="logs-*",
    query={"match": {"level": "ERROR"}},
    size=50,
    sort=[{"@timestamp": "desc"}]
)

# Count documents
result = await elasticsearch.count(
    index="logs-*",
    query={"range": {"@timestamp": {"gte": "now-1h"}}}
)

# Check cluster health
result = await elasticsearch.cluster_health()
```

## Query DSL

Uses standard Elasticsearch Query DSL:
- `match` - Full-text search
- `term` - Exact match
- `range` - Range queries
- `bool` - Combine queries
