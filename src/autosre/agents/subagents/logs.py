"""
Logs Subagent — Investigates log data for errors and patterns.

Capabilities:
- Log search (Elasticsearch, Loki, etc.)
- Error pattern detection
- Log aggregation and analysis
- Correlation with timestamps
"""

import json
import logging
from typing import Any, Optional

from .base import BaseSubagent, SubagentConfig
from .react import Tool, create_tool

logger = logging.getLogger(__name__)


LOGS_CAPABILITIES = """
**Log Investigation**:
- Search logs by service, level, message
- Filter by time range and severity
- Pattern matching and regex search
- Error aggregation and counting
- Trace correlation via trace_id

**Common searches**:
1. Recent errors: level:error AND service:{service}
2. Exception traces: message:*Exception* OR message:*Error*
3. Timeout issues: message:*timeout* OR message:*timed out*
4. Connection problems: message:*connection* AND (message:*refused* OR message:*reset*)
5. OOM issues: message:*OutOfMemory* OR message:*OOM*
"""


class LogsSubagent(BaseSubagent):
    """Log analysis domain investigation subagent."""
    
    agent_id = "logs"
    agent_name = "Logs Investigation Agent"
    capabilities_description = LOGS_CAPABILITIES
    
    def __init__(
        self,
        config: Optional[SubagentConfig] = None,
        backend: str = "elasticsearch",
        backend_url: str = "http://elasticsearch:9200",
        index_pattern: str = "logs-*",
        dry_run: bool = False,
    ):
        super().__init__(config)
        self.backend = backend
        self.backend_url = backend_url.rstrip("/")
        self.index_pattern = index_pattern
        self.dry_run = dry_run
    
    async def _search_elasticsearch(
        self,
        query: dict[str, Any],
        index: Optional[str] = None,
        size: int = 100,
    ) -> dict[str, Any]:
        """Execute an Elasticsearch search query."""
        if self.dry_run:
            return {
                "hits": {
                    "total": {"value": 0},
                    "hits": [],
                },
                "_dry_run": True,
                "_query": query,
            }
        
        try:
            import httpx
        except ImportError:
            return {"error": "httpx not installed"}
        
        url = f"{self.backend_url}/{index or self.index_pattern}/_search"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json={**query, "size": size},
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def _format_es_results(self, data: dict[str, Any], max_logs: int = 20) -> str:
        """Format Elasticsearch search results for display."""
        if "error" in data:
            return f"Error: {data['error']}"
        
        if data.get("_dry_run"):
            return f"[DRY RUN] Would search: {json.dumps(data.get('_query', {}), indent=2)}"
        
        hits = data.get("hits", {})
        total = hits.get("total", {})
        total_count = total.get("value", 0) if isinstance(total, dict) else total
        results = hits.get("hits", [])
        
        if not results:
            return f"No logs found. Total: {total_count}"
        
        lines = [f"Found {total_count} logs (showing {min(len(results), max_logs)}):", ""]
        
        for hit in results[:max_logs]:
            source = hit.get("_source", {})
            timestamp = source.get("@timestamp", source.get("timestamp", "?"))
            level = source.get("level", source.get("log.level", "?"))
            message = source.get("message", source.get("log", "?"))
            service = source.get("service", source.get("service.name", "?"))
            
            # Truncate long messages
            if len(message) > 200:
                message = message[:200] + "..."
            
            lines.append(f"[{timestamp}] [{level}] {service}: {message}")
        
        if len(results) > max_logs:
            lines.append(f"... and {len(results) - max_logs} more in this batch")
        
        if total_count > len(results):
            lines.append(f"Total matching: {total_count}")
        
        return "\n".join(lines)
    
    def _build_es_query(
        self,
        must: Optional[list[dict]] = None,
        should: Optional[list[dict]] = None,
        filter_: Optional[list[dict]] = None,
        time_range: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build an Elasticsearch bool query."""
        query: dict[str, Any] = {"bool": {}}
        
        if must:
            query["bool"]["must"] = must
        if should:
            query["bool"]["should"] = should
            query["bool"]["minimum_should_match"] = 1
        if filter_:
            query["bool"]["filter"] = filter_
        
        # Add time range filter
        if time_range:
            duration_map = {
                "5m": "now-5m",
                "15m": "now-15m",
                "30m": "now-30m",
                "1h": "now-1h",
                "3h": "now-3h",
                "6h": "now-6h",
                "12h": "now-12h",
                "24h": "now-24h",
                "1d": "now-1d",
                "7d": "now-7d",
            }
            gte = duration_map.get(time_range, "now-1h")
            
            if "filter" not in query["bool"]:
                query["bool"]["filter"] = []
            query["bool"]["filter"].append({
                "range": {
                    "@timestamp": {"gte": gte, "lte": "now"}
                }
            })
        
        return {"query": query, "sort": [{"@timestamp": "desc"}]}
    
    async def get_tools(self) -> list[Tool]:
        """Return log investigation tools."""
        
        # ----- Tool Implementations -----
        
        async def search_logs(
            query: str,
            service: Optional[str] = None,
            level: Optional[str] = None,
            time_range: str = "1h",
            size: int = 50,
        ) -> str:
            """Search logs with a text query."""
            must = [{"query_string": {"query": query}}]
            filter_ = []
            
            if service:
                filter_.append({"term": {"service": service}})
            if level:
                filter_.append({"term": {"level": level}})
            
            es_query = self._build_es_query(
                must=must,
                filter_=filter_ if filter_ else None,
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=size)
            return self._format_es_results(result)
        
        async def get_errors(
            service: str,
            time_range: str = "1h",
            size: int = 50,
        ) -> str:
            """Get error-level logs for a service."""
            es_query = self._build_es_query(
                must=[{"term": {"service": service}}],
                filter_=[{"term": {"level": "error"}}],
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=size)
            return f"Errors for {service} in last {time_range}:\n{self._format_es_results(result)}"
        
        async def get_exceptions(
            service: Optional[str] = None,
            time_range: str = "1h",
            size: int = 30,
        ) -> str:
            """Search for exception stack traces in logs."""
            must = [
                {
                    "query_string": {
                        "query": "Exception OR Traceback OR Error OR error OR exception",
                        "default_field": "message"
                    }
                }
            ]
            filter_ = []
            
            if service:
                filter_.append({"term": {"service": service}})
            
            es_query = self._build_es_query(
                must=must,
                filter_=filter_ if filter_ else None,
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=size)
            svc_str = f" for {service}" if service else ""
            return f"Exceptions{svc_str} in last {time_range}:\n{self._format_es_results(result, max_logs=30)}"
        
        async def count_by_level(
            service: str,
            time_range: str = "1h",
        ) -> str:
            """Aggregate log counts by level for a service."""
            if self.dry_run:
                return f"[DRY RUN] Would count logs by level for {service}"
            
            es_query = {
                "query": {
                    "bool": {
                        "must": [{"term": {"service": service}}],
                        "filter": [{"range": {"@timestamp": {"gte": f"now-{time_range}"}}}],
                    }
                },
                "aggs": {
                    "by_level": {
                        "terms": {"field": "level"}
                    }
                },
                "size": 0,
            }
            
            try:
                import httpx
            except ImportError:
                return "Error: httpx not installed"
            
            url = f"{self.backend_url}/{self.index_pattern}/_search"
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=es_query, timeout=30)
                    data = resp.json()
                    
                    buckets = data.get("aggregations", {}).get("by_level", {}).get("buckets", [])
                    
                    lines = [f"Log counts for {service} over {time_range}:", ""]
                    total = 0
                    for bucket in buckets:
                        level = bucket.get("key", "?")
                        count = bucket.get("doc_count", 0)
                        total += count
                        lines.append(f"  {level}: {count}")
                    lines.append(f"  TOTAL: {total}")
                    
                    return "\n".join(lines)
                    
            except Exception as e:
                return f"Error: {e}"
        
        async def search_by_trace_id(
            trace_id: str,
            time_range: str = "24h",
        ) -> str:
            """Find all logs for a specific trace ID."""
            es_query = self._build_es_query(
                must=[{"term": {"trace_id": trace_id}}],
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=100)
            return f"Logs for trace {trace_id}:\n{self._format_es_results(result, max_logs=50)}"
        
        async def get_error_patterns(
            service: str,
            time_range: str = "1h",
            top_n: int = 10,
        ) -> str:
            """Aggregate error messages to find common patterns."""
            if self.dry_run:
                return f"[DRY RUN] Would analyze error patterns for {service}"
            
            # This requires the message field to be keyword or have a keyword sub-field
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"service": service}},
                            {"term": {"level": "error"}},
                        ],
                        "filter": [{"range": {"@timestamp": {"gte": f"now-{time_range}"}}}],
                    }
                },
                "aggs": {
                    "error_patterns": {
                        "terms": {
                            "field": "message.keyword",
                            "size": top_n,
                        }
                    }
                },
                "size": 0,
            }
            
            try:
                import httpx
            except ImportError:
                return "Error: httpx not installed"
            
            url = f"{self.backend_url}/{self.index_pattern}/_search"
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=es_query, timeout=30)
                    data = resp.json()
                    
                    buckets = data.get("aggregations", {}).get("error_patterns", {}).get("buckets", [])
                    
                    if not buckets:
                        return f"No error patterns found for {service} in {time_range}"
                    
                    lines = [f"Top {len(buckets)} error patterns for {service}:", ""]
                    for i, bucket in enumerate(buckets, 1):
                        message = bucket.get("key", "?")[:100]
                        count = bucket.get("doc_count", 0)
                        lines.append(f"{i}. ({count}x) {message}")
                    
                    return "\n".join(lines)
                    
            except Exception as e:
                return f"Error: {e}"
        
        async def tail_logs(
            service: str,
            level: Optional[str] = None,
            lines: int = 20,
        ) -> str:
            """Get the most recent logs for a service."""
            filter_ = [{"term": {"service": service}}]
            if level:
                filter_.append({"term": {"level": level}})
            
            es_query = self._build_es_query(
                filter_=filter_,
                time_range="1h",
            )
            
            result = await self._search_elasticsearch(es_query, size=lines)
            return f"Recent logs for {service}:\n{self._format_es_results(result, max_logs=lines)}"
        
        async def search_connection_issues(
            service: Optional[str] = None,
            time_range: str = "1h",
        ) -> str:
            """Search for connection-related errors (timeout, refused, reset)."""
            must = [
                {
                    "query_string": {
                        "query": "connection AND (refused OR reset OR timeout OR closed OR failed)",
                        "default_field": "message"
                    }
                }
            ]
            filter_ = []
            
            if service:
                filter_.append({"term": {"service": service}})
            
            es_query = self._build_es_query(
                must=must,
                filter_=filter_ if filter_ else None,
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=50)
            svc_str = f" for {service}" if service else ""
            return f"Connection issues{svc_str} in last {time_range}:\n{self._format_es_results(result)}"
        
        async def search_oom_events(
            service: Optional[str] = None,
            time_range: str = "24h",
        ) -> str:
            """Search for out-of-memory events."""
            must = [
                {
                    "query_string": {
                        "query": "OutOfMemory OR OOM OR OOMKilled OR \"out of memory\"",
                        "default_field": "message"
                    }
                }
            ]
            filter_ = []
            
            if service:
                filter_.append({"term": {"service": service}})
            
            es_query = self._build_es_query(
                must=must,
                filter_=filter_ if filter_ else None,
                time_range=time_range,
            )
            
            result = await self._search_elasticsearch(es_query, size=30)
            svc_str = f" for {service}" if service else ""
            return f"OOM events{svc_str} in last {time_range}:\n{self._format_es_results(result)}"
        
        # ----- Build Tool Objects -----
        
        return [
            create_tool(
                name="search_logs",
                description="Search logs with a text query. Supports Lucene query syntax.",
                executor=search_logs,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (Lucene syntax)"},
                        "service": {"type": "string", "description": "Filter by service name"},
                        "level": {"type": "string", "description": "Filter by log level (error, warn, info, debug)"},
                        "time_range": {"type": "string", "description": "Time range (5m, 1h, 24h, etc.)"},
                        "size": {"type": "integer", "description": "Max results to return"},
                    },
                    "required": ["query"],
                },
            ),
            create_tool(
                name="get_errors",
                description="Get error-level logs for a service. Quick way to see recent errors.",
                executor=get_errors,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "time_range": {"type": "string", "description": "Time range (default: 1h)"},
                        "size": {"type": "integer", "description": "Max results"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="get_exceptions",
                description="Search for exception stack traces and error messages.",
                executor=get_exceptions,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Filter by service"},
                        "time_range": {"type": "string", "description": "Time range (default: 1h)"},
                        "size": {"type": "integer", "description": "Max results"},
                    },
                },
            ),
            create_tool(
                name="count_by_level",
                description="Count logs by level (error, warn, info) for a service. Good for spotting spikes.",
                executor=count_by_level,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "time_range": {"type": "string", "description": "Time range (default: 1h)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="search_by_trace_id",
                description="Find all logs for a specific distributed trace. Follow a request across services.",
                executor=search_by_trace_id,
                parameters={
                    "type": "object",
                    "properties": {
                        "trace_id": {"type": "string", "description": "Trace ID to search"},
                        "time_range": {"type": "string", "description": "Time range (default: 24h)"},
                    },
                    "required": ["trace_id"],
                },
            ),
            create_tool(
                name="get_error_patterns",
                description="Find the most common error messages. Helps identify systemic issues.",
                executor=get_error_patterns,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "time_range": {"type": "string", "description": "Time range (default: 1h)"},
                        "top_n": {"type": "integer", "description": "Number of top patterns (default: 10)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="tail_logs",
                description="Get the most recent logs for a service. Like 'tail -f' for logs.",
                executor=tail_logs,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "level": {"type": "string", "description": "Filter by level"},
                        "lines": {"type": "integer", "description": "Number of lines (default: 20)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="search_connection_issues",
                description="Find connection-related errors (timeout, refused, reset, closed).",
                executor=search_connection_issues,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Filter by service"},
                        "time_range": {"type": "string", "description": "Time range (default: 1h)"},
                    },
                },
            ),
            create_tool(
                name="search_oom_events",
                description="Search for out-of-memory (OOM) events. Common cause of pod crashes.",
                executor=search_oom_events,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Filter by service"},
                        "time_range": {"type": "string", "description": "Time range (default: 24h)"},
                    },
                },
            ),
        ]
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build logs-focused hypothesis."""
        if hypotheses:
            return f"Log investigation: {'; '.join(hypotheses)}"
        
        alert_name = alert.get("name", alert.get("alert_name", "Unknown"))
        service = alert.get("service", alert.get("labels", {}).get("service", "unknown"))
        
        return f"""Investigating logs for {service}:
- Search for error-level logs and exceptions
- Look for stack traces and error patterns
- Check for connection issues (timeout, refused)
- Identify recurring error messages
- Check for OOM or resource exhaustion

Alert: {alert_name}"""


def create_logs_subagent(
    backend: str = "elasticsearch",
    backend_url: str = "http://elasticsearch:9200",
    index_pattern: str = "logs-*",
    config: Optional[SubagentConfig] = None,
    dry_run: bool = False,
) -> LogsSubagent:
    """Factory function to create Logs subagent.
    
    Args:
        backend: Log backend type (elasticsearch, loki)
        backend_url: Backend API URL
        index_pattern: Elasticsearch index pattern
        config: Subagent configuration
        dry_run: If True, don't actually query the backend
    """
    return LogsSubagent(
        config=config,
        backend=backend,
        backend_url=backend_url,
        index_pattern=index_pattern,
        dry_run=dry_run,
    )
