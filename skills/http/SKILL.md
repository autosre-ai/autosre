# HTTP Skill

Generic HTTP client for API calls, health checks, and webhook integrations.

## Configuration

```yaml
base_url: https://api.example.com    # Optional base URL for requests
timeout: 30                          # Request timeout in seconds
headers:                             # Default headers for all requests
  Authorization: Bearer ${API_TOKEN}
  Content-Type: application/json
verify_ssl: true                     # Verify SSL certificates
```

## Actions

### `get(url, headers, params)`
Make HTTP GET request.

**Parameters:**
- `url` (str, required): URL to request (or path if base_url configured)
- `headers` (dict, optional): Additional headers
- `params` (dict, optional): Query parameters

**Returns:** Response with status, headers, and body

### `post(url, body, headers)`
Make HTTP POST request.

**Parameters:**
- `url` (str, required): URL to request
- `body` (dict|str, required): Request body (JSON or string)
- `headers` (dict, optional): Additional headers

**Returns:** Response with status, headers, and body

### `health_check(url, expected_status, timeout)`
Check if an endpoint is healthy.

**Parameters:**
- `url` (str, required): URL to check
- `expected_status` (int, optional): Expected HTTP status (default: 200)
- `timeout` (int, optional): Timeout in seconds (default: 5)

**Returns:** Health status with response time

## Dependencies

- `httpx>=0.24.0`
