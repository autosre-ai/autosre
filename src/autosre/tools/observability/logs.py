"""Log query tool for searching and analyzing logs.

Provides a standalone tool for querying logs via Loki or similar
log aggregation backends.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class LogsQueryTool:
    """Tool for querying and analyzing logs via Loki backend.
    
    Provides capabilities for searching logs using LogQL, filtering by
    labels, time ranges, and extracting log patterns.
    
    Example:
        logs = LogsQueryTool(loki_url="http://loki:3100")
        
        # Simple query
        result = await logs.query('{job="nginx"} |~ "error"')
        
        # Query with time range
        result = await logs.query_range(
            query='{app="api"}',
            start="1h",
            limit=100
        )
        
        # Get label values
        result = await logs.label_values("namespace")
    """
    
    def __init__(
        self,
        loki_url: str = "http://localhost:3100",
        timeout: int = 30,
        auth_token: Optional[str] = None,
    ):
        """Initialize the Logs query tool.
        
        Args:
            loki_url: Base URL of Loki server
            timeout: Query timeout in seconds
            auth_token: Optional bearer token for authentication
        """
        self.loki_url = loki_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
    
    def _parse_time(self, time_str: str) -> int:
        """Parse time string to nanoseconds (Loki format)."""
        if not time_str or time_str == "now":
            return int(datetime.now().timestamp() * 1e9)
        
        # Check for relative time format
        match = re.match(r'^(\d+)([smhdw])$', time_str.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            delta_map = {
                's': timedelta(seconds=value),
                'm': timedelta(minutes=value),
                'h': timedelta(hours=value),
                'd': timedelta(days=value),
                'w': timedelta(weeks=value),
            }
            
            dt = datetime.now() - delta_map[unit]
            return int(dt.timestamp() * 1e9)
        
        # Try ISO 8601 format
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1e9)
        except ValueError:
            pass
        
        # Return current time as fallback
        return int(datetime.now().timestamp() * 1e9)
    
    async def _http_get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP GET request to Loki API."""
        import aiohttp
        
        url = f"{self.loki_url}{endpoint}"
        
        headers = {"Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status >= 400:
                        try:
                            body = await response.json()
                            error_msg = body.get("message", f"HTTP {response.status}")
                        except Exception:
                            error_msg = f"HTTP {response.status}"
                        return {"success": False, "error": error_msg}
                    
                    body = await response.json()
                    return {"success": True, "data": body}
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Request timed out after {self.timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def query(
        self,
        query: str,
        limit: int = 100,
        direction: str = "backward",
    ) -> ToolResult:
        """Execute instant LogQL query.
        
        Args:
            query: LogQL query expression (e.g., '{job="nginx"} |~ "error"')
            limit: Maximum number of log lines to return
            direction: Query direction ('forward' or 'backward')
            
        Returns:
            ToolResult with log entries including timestamp, labels, and content
        """
        if not query:
            return ToolResult(success=False, error="Query is required")
        
        params = {
            "query": query,
            "limit": limit,
            "direction": direction,
        }
        
        result = await self._http_get("/loki/api/v1/query", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Query failed"))
        
        result_data = data.get("data", {})
        result_type = result_data.get("resultType")
        results = result_data.get("result", [])
        
        # Format log entries
        formatted_entries = []
        for stream in results:
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            
            for entry in values:
                if len(entry) >= 2:
                    timestamp_ns = int(entry[0])
                    line = entry[1]
                    
                    formatted_entries.append({
                        "timestamp": datetime.fromtimestamp(timestamp_ns / 1e9).isoformat(),
                        "timestamp_ns": timestamp_ns,
                        "labels": labels,
                        "line": line,
                    })
        
        return ToolResult(
            success=True,
            data={
                "result_type": result_type,
                "entries": formatted_entries,
                "count": len(formatted_entries),
            },
            metadata={
                "query": query,
                "limit": limit,
                "direction": direction,
            },
        )
    
    async def query_range(
        self,
        query: str,
        start: str,
        end: str = "now",
        limit: int = 100,
        direction: str = "backward",
        step: Optional[str] = None,
    ) -> ToolResult:
        """Execute range LogQL query for log entries over time.
        
        Args:
            query: LogQL query expression
            start: Start time (ISO 8601 or relative like '1h', '24h')
            end: End time (ISO 8601 or 'now')
            limit: Maximum number of log lines to return
            direction: Query direction ('forward' or 'backward')
            step: Query step for metrics queries (e.g., '15s', '1m')
            
        Returns:
            ToolResult with log entries including timestamp, labels, and content
        """
        if not query:
            return ToolResult(success=False, error="Query is required")
        if not start:
            return ToolResult(success=False, error="Start time is required")
        
        params: Dict[str, Any] = {
            "query": query,
            "start": self._parse_time(start),
            "end": self._parse_time(end),
            "limit": limit,
            "direction": direction,
        }
        
        if step:
            params["step"] = step
        
        result = await self._http_get("/loki/api/v1/query_range", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Query failed"))
        
        result_data = data.get("data", {})
        result_type = result_data.get("resultType")
        results = result_data.get("result", [])
        
        # Format based on result type
        if result_type == "streams":
            # Log entries
            formatted_entries = []
            for stream in results:
                labels = stream.get("stream", {})
                values = stream.get("values", [])
                
                for entry in values:
                    if len(entry) >= 2:
                        timestamp_ns = int(entry[0])
                        line = entry[1]
                        
                        formatted_entries.append({
                            "timestamp": datetime.fromtimestamp(timestamp_ns / 1e9).isoformat(),
                            "timestamp_ns": timestamp_ns,
                            "labels": labels,
                            "line": line,
                        })
            
            return ToolResult(
                success=True,
                data={
                    "result_type": result_type,
                    "entries": formatted_entries,
                    "count": len(formatted_entries),
                },
                metadata={
                    "query": query,
                    "start": start,
                    "end": end,
                },
            )
        else:
            # Metric results (matrix)
            formatted_series = []
            for s in results:
                metric = s.get("metric", {})
                values = s.get("values", [])
                
                formatted_series.append({
                    "metric": metric,
                    "values": [
                        {
                            "timestamp": datetime.fromtimestamp(v[0]).isoformat(),
                            "value": float(v[1]),
                        }
                        for v in values
                    ],
                    "value_count": len(values),
                })
            
            return ToolResult(
                success=True,
                data={
                    "result_type": result_type,
                    "series": formatted_series,
                    "series_count": len(formatted_series),
                },
                metadata={
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step,
                },
            )
    
    async def labels(self) -> ToolResult:
        """Get available label names.
        
        Returns:
            ToolResult with list of available label names
        """
        result = await self._http_get("/loki/api/v1/labels")
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get labels"))
        
        labels = data.get("data", [])
        
        return ToolResult(
            success=True,
            data={
                "labels": labels,
                "count": len(labels),
            },
        )
    
    async def label_values(self, label_name: str) -> ToolResult:
        """Get values for a specific label.
        
        Args:
            label_name: Name of the label to get values for
            
        Returns:
            ToolResult with list of values for the specified label
        """
        if not label_name:
            return ToolResult(success=False, error="Label name is required")
        
        result = await self._http_get(f"/loki/api/v1/label/{label_name}/values")
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get label values"))
        
        values = data.get("data", [])
        
        return ToolResult(
            success=True,
            data={
                "label": label_name,
                "values": values,
                "count": len(values),
            },
        )
    
    async def series(
        self,
        match: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> ToolResult:
        """Get series matching a selector.
        
        Args:
            match: Series selector (e.g., '{job="nginx"}')
            start: Start time for filtering
            end: End time for filtering
            
        Returns:
            ToolResult with list of matching series and their labels
        """
        if not match:
            return ToolResult(success=False, error="Match selector is required")
        
        params: Dict[str, Any] = {"match[]": match}
        
        if start:
            params["start"] = self._parse_time(start)
        if end:
            params["end"] = self._parse_time(end)
        
        result = await self._http_get("/loki/api/v1/series", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get series"))
        
        series = data.get("data", [])
        
        return ToolResult(
            success=True,
            data={
                "series": series,
                "count": len(series),
            },
            metadata={"match": match},
        )
