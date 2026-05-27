"""Log analysis tools for SRE agents.

Provides tools for searching and analyzing logs:
- Elasticsearch (ELK stack)
- Loki (Grafana Loki)
- Generic log tailing
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlencode

from langchain_core.tools import BaseTool, tool

from .base import BaseSRETool, SREToolError, ConnectionError, AuthenticationError

logger = logging.getLogger(__name__)


def _make_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Make HTTP request using urllib."""
    import ssl
    import urllib.request
    import urllib.error
    
    if params:
        url = f"{url}?{urlencode(params)}"
    
    headers = headers or {}
    headers.setdefault("Accept", "application/json")
    
    body = None
    if data:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    context = None
    if not verify_ssl:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            response_data = response.read().decode("utf-8")
            if response_data:
                return json.loads(response_data)
            return {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthenticationError(url)
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise SREToolError(f"HTTP {e.code}: {error_body[:200]}")
    except urllib.error.URLError as e:
        raise ConnectionError(url, str(e.reason))
    except json.JSONDecodeError as e:
        raise SREToolError(f"Invalid JSON response: {e}")


@dataclass
class ElasticsearchConfig:
    """Configuration for Elasticsearch client."""
    
    url: str = "http://localhost:9200"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    index_pattern: str = "logs-*"
    timeout_seconds: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "ElasticsearchConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
            username=os.getenv("ELASTICSEARCH_USERNAME"),
            password=os.getenv("ELASTICSEARCH_PASSWORD"),
            api_key=os.getenv("ELASTICSEARCH_API_KEY"),
            index_pattern=os.getenv("ELASTICSEARCH_INDEX", "logs-*"),
            timeout_seconds=int(os.getenv("ELASTICSEARCH_TIMEOUT", "30")),
            verify_ssl=os.getenv("ELASTICSEARCH_VERIFY_SSL", "true").lower() == "true",
        )


@dataclass
class LokiConfig:
    """Configuration for Loki client."""
    
    url: str = "http://localhost:3100"
    username: Optional[str] = None
    password: Optional[str] = None
    tenant_id: Optional[str] = None
    timeout_seconds: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "LokiConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("LOKI_URL", "http://localhost:3100"),
            username=os.getenv("LOKI_USERNAME"),
            password=os.getenv("LOKI_PASSWORD"),
            tenant_id=os.getenv("LOKI_TENANT_ID"),
            timeout_seconds=int(os.getenv("LOKI_TIMEOUT", "30")),
            verify_ssl=os.getenv("LOKI_VERIFY_SSL", "true").lower() == "true",
        )


class LogsTools(BaseSRETool):
    """Log analysis tools for SRE agents."""
    
    name = "logs"
    description = "Search and analyze logs from Elasticsearch, Loki, and local files"
    
    def __init__(
        self,
        elasticsearch_config: Optional[ElasticsearchConfig] = None,
        loki_config: Optional[LokiConfig] = None,
        mock_mode: bool = False,
    ):
        """Initialize log tools.
        
        Args:
            elasticsearch_config: Elasticsearch configuration.
            loki_config: Loki configuration.
            mock_mode: If True, return mock data.
        """
        super().__init__(mock_mode=mock_mode)
        self.elasticsearch = elasticsearch_config or ElasticsearchConfig.from_env()
        self.loki = loki_config or LokiConfig.from_env()
    
    def get_tools(self) -> list[BaseTool]:
        """Return list of log tools."""
        return [
            self._make_search_elasticsearch_tool(),
            self._make_search_loki_tool(),
            self._make_tail_logs_tool(),
        ]
    
    def _make_search_elasticsearch_tool(self) -> BaseTool:
        """Create search_elasticsearch tool."""
        parent = self
        
        @tool
        def search_elasticsearch(
            query: str,
            index: str = "",
            time_range: str = "1h",
            size: int = 100,
            fields: str = "",
            sort_field: str = "@timestamp",
            sort_order: str = "desc",
        ) -> str:
            """Search logs in Elasticsearch.
            
            Args:
                query: Search query in Lucene or Elasticsearch Query String syntax.
                    Examples:
                    - 'error AND service:api'
                    - 'status:500 AND NOT path:/health'
                    - '"connection refused"'
                    - 'level:ERROR OR level:CRITICAL'
                index: Index pattern to search (default from config).
                time_range: Time range (e.g., '15m', '1h', '6h', '1d').
                size: Maximum number of results to return (max 1000).
                fields: Comma-separated list of fields to return (empty for all).
                sort_field: Field to sort by (default '@timestamp').
                sort_order: 'asc' or 'desc'.
                
            Returns:
                JSON with matching log entries.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("search_elasticsearch", {
                    "total": 1,
                    "hits": [
                        {
                            "@timestamp": "2024-01-15T10:30:00Z",
                            "level": "ERROR",
                            "message": "Connection refused to database",
                            "service": "api",
                        }
                    ],
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                # Build auth headers
                headers = {}
                if parent.elasticsearch.api_key:
                    headers["Authorization"] = f"ApiKey {parent.elasticsearch.api_key}"
                elif parent.elasticsearch.username and parent.elasticsearch.password:
                    import base64
                    creds = f"{parent.elasticsearch.username}:{parent.elasticsearch.password}"
                    encoded = base64.b64encode(creds.encode()).decode()
                    headers["Authorization"] = f"Basic {encoded}"
                
                # Calculate time range
                now = datetime.now(timezone.utc)
                duration_map = {"m": "minutes", "h": "hours", "d": "days"}
                unit = time_range[-1]
                value = int(time_range[:-1])
                
                # Build Elasticsearch query
                index_pattern = index or parent.elasticsearch.index_pattern
                url = urljoin(parent.elasticsearch.url, f"/{index_pattern}/_search")
                
                es_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"query_string": {"query": query}},
                            ],
                            "filter": [
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": f"now-{value}{unit}",
                                            "lte": "now",
                                        }
                                    }
                                }
                            ],
                        }
                    },
                    "size": min(size, 1000),
                    "sort": [{sort_field: {"order": sort_order}}],
                }
                
                # Filter fields if specified
                if fields:
                    es_query["_source"] = fields.split(",")
                
                result = _make_request(
                    "POST",
                    url,
                    headers=headers,
                    data=es_query,
                    timeout=parent.elasticsearch.timeout_seconds,
                    verify_ssl=parent.elasticsearch.verify_ssl,
                )
                
                # Format results
                hits = result.get("hits", {})
                total = hits.get("total", {})
                if isinstance(total, dict):
                    total_count = total.get("value", 0)
                else:
                    total_count = total
                
                formatted = {
                    "total": total_count,
                    "returned": len(hits.get("hits", [])),
                    "index": index_pattern,
                    "query": query,
                    "hits": [],
                }
                
                for hit in hits.get("hits", []):
                    source = hit.get("_source", {})
                    formatted["hits"].append(source)
                
                return json.dumps(formatted, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Elasticsearch search error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return search_elasticsearch
    
    def _make_search_loki_tool(self) -> BaseTool:
        """Create search_loki tool."""
        parent = self
        
        @tool
        def search_loki(
            query: str,
            time_range: str = "1h",
            limit: int = 100,
            direction: str = "backward",
        ) -> str:
            """Search logs in Grafana Loki.
            
            Args:
                query: LogQL query string.
                    Label matchers: {app="nginx", env="prod"}
                    Line filters: {app="nginx"} |= "error"
                    Regex: {app="nginx"} |~ "status=5.."
                    JSON parsing: {app="nginx"} | json | status >= 500
                    Examples:
                    - '{namespace="default"}' - All logs from namespace
                    - '{app="api"} |= "error"' - Lines containing "error"
                    - '{app="api"} |~ "status=[45].."' - 4xx or 5xx status
                    - '{app="api"} | json | latency > 1000' - High latency (JSON logs)
                time_range: Time range (e.g., '15m', '1h', '6h', '1d').
                limit: Maximum number of log lines to return.
                direction: 'backward' (newest first) or 'forward' (oldest first).
                
            Returns:
                JSON with matching log entries.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("search_loki", {
                    "resultType": "streams",
                    "result": [
                        {
                            "stream": {"app": "api", "namespace": "default"},
                            "values": [
                                ["1705315200000000000", "ERROR: Connection refused"],
                            ],
                        }
                    ],
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                headers = {}
                if parent.loki.tenant_id:
                    headers["X-Scope-OrgID"] = parent.loki.tenant_id
                if parent.loki.username and parent.loki.password:
                    import base64
                    creds = f"{parent.loki.username}:{parent.loki.password}"
                    encoded = base64.b64encode(creds.encode()).decode()
                    headers["Authorization"] = f"Basic {encoded}"
                
                # Calculate time range
                now_ns = int(time.time() * 1e9)
                duration_map = {"m": 60, "h": 3600, "d": 86400}
                unit = time_range[-1]
                value = int(time_range[:-1])
                duration_ns = int(value * duration_map.get(unit, 3600) * 1e9)
                
                start = now_ns - duration_ns
                end = now_ns
                
                url = urljoin(parent.loki.url, "/loki/api/v1/query_range")
                params = {
                    "query": query,
                    "start": start,
                    "end": end,
                    "limit": limit,
                    "direction": direction,
                }
                
                result = _make_request(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    timeout=parent.loki.timeout_seconds,
                    verify_ssl=parent.loki.verify_ssl,
                )
                
                # Format results
                data = result.get("data", {})
                formatted = {
                    "status": result.get("status"),
                    "resultType": data.get("resultType"),
                    "query": query,
                    "streams": [],
                }
                
                total_lines = 0
                for stream in data.get("result", []):
                    labels = stream.get("stream", {})
                    values = stream.get("values", [])
                    
                    formatted["streams"].append({
                        "labels": labels,
                        "lineCount": len(values),
                        "lines": [
                            {
                                "timestamp": datetime.fromtimestamp(int(v[0]) / 1e9).isoformat(),
                                "line": v[1],
                            }
                            for v in values[:50]  # Limit lines per stream
                        ],
                    })
                    total_lines += len(values)
                
                formatted["totalLines"] = total_lines
                
                return json.dumps(formatted, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Loki search error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return search_loki
    
    def _make_tail_logs_tool(self) -> BaseTool:
        """Create tail_logs tool."""
        parent = self
        
        @tool
        def tail_logs(
            source: str,
            lines: int = 100,
            grep_pattern: str = "",
            since: str = "",
        ) -> str:
            """Tail logs from a file or kubectl logs.
            
            Args:
                source: Log source. Can be:
                    - File path: '/var/log/app.log'
                    - kubectl: 'kubectl:namespace/pod-name' or 'kubectl:namespace/pod-name/container'
                lines: Number of recent lines to return.
                grep_pattern: Filter lines matching this pattern (grep -E).
                since: For kubectl logs, time duration (e.g., '1h', '30m').
                
            Returns:
                Log lines as text.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("tail_logs", 
                    "2024-01-15T10:30:00Z INFO Starting application\n"
                    "2024-01-15T10:30:01Z INFO Connected to database\n"
                    "2024-01-15T10:30:05Z ERROR Connection timeout\n"
                )
                return mock_data
            
            try:
                if source.startswith("kubectl:"):
                    # Parse kubectl source
                    # Format: kubectl:namespace/pod or kubectl:namespace/pod/container
                    parts = source[8:].split("/")
                    if len(parts) < 2:
                        return "Error: kubectl source format: kubectl:namespace/pod[/container]"
                    
                    namespace = parts[0]
                    pod = parts[1]
                    container = parts[2] if len(parts) > 2 else None
                    
                    cmd = ["kubectl", "logs", "-n", namespace, pod, f"--tail={lines}"]
                    if container:
                        cmd.extend(["-c", container])
                    if since:
                        cmd.extend(["--since", since])
                else:
                    # File path
                    cmd = ["tail", f"-n{lines}", source]
                
                # Add grep if pattern specified
                if grep_pattern:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    grep_process = subprocess.Popen(
                        ["grep", "-E", grep_pattern],
                        stdin=process.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    stdout, stderr = grep_process.communicate(timeout=30)
                else:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    stdout = result.stdout
                    stderr = result.stderr
                
                if stderr and not stdout:
                    return f"Error: {stderr.strip()}"
                
                return stdout if stdout else "(no logs)"
                
            except subprocess.TimeoutExpired:
                return "Error: Command timed out after 30 seconds"
            except FileNotFoundError as e:
                return f"Error: Command not found - {e}"
            except Exception as e:
                logger.exception("Tail logs error")
                return f"Error: {e}"
        
        return tail_logs


# Convenience function to get all log tools
def get_logs_tools(
    elasticsearch_config: Optional[ElasticsearchConfig] = None,
    loki_config: Optional[LokiConfig] = None,
    mock_mode: bool = False,
) -> list[BaseTool]:
    """Get all log analysis tools.
    
    Args:
        elasticsearch_config: Elasticsearch configuration.
        loki_config: Loki configuration.
        mock_mode: If True, return mock data.
        
    Returns:
        List of LangChain tools.
    """
    logs = LogsTools(
        elasticsearch_config=elasticsearch_config,
        loki_config=loki_config,
        mock_mode=mock_mode,
    )
    return logs.get_tools()
