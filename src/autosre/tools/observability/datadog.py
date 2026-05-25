"""Datadog tool for metrics, monitors, events, and incidents.

Provides a standalone tool for interacting with Datadog's API for
metrics querying, monitor management, events, and incident creation.
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


class DatadogTool:
    """Tool for interacting with Datadog metrics, monitors, events, and incidents.
    
    Provides capabilities for querying metrics, listing monitors,
    getting events, and creating incidents.
    
    Example:
        dd = DatadogTool(api_key="...", app_key="...")
        
        # Query metrics
        result = await dd.query_metrics(
            query="avg:system.cpu.user{host:web-01}",
            start="1h"
        )
        
        # List monitors
        result = await dd.list_monitors(status="Alert")
        
        # Get events
        result = await dd.get_events(start="24h", priority="high")
        
        # Create incident
        result = await dd.create_incident(
            title="Production Outage",
            severity="SEV-1"
        )
    """
    
    # Site to API URL mapping
    SITE_URLS: Dict[str, str] = {
        "datadoghq.com": "https://api.datadoghq.com",
        "us3.datadoghq.com": "https://api.us3.datadoghq.com",
        "us5.datadoghq.com": "https://api.us5.datadoghq.com",
        "datadoghq.eu": "https://api.datadoghq.eu",
        "ddog-gov.com": "https://api.ddog-gov.com",
        "ap1.datadoghq.com": "https://api.ap1.datadoghq.com",
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        app_key: Optional[str] = None,
        site: str = "datadoghq.com",
        timeout: int = 30,
    ):
        """Initialize the Datadog tool.
        
        Args:
            api_key: Datadog API key
            app_key: Datadog Application key
            site: Datadog site (datadoghq.com, datadoghq.eu, etc.)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self.base_url = self.SITE_URLS.get(site, f"https://api.{site}")
        self.timeout = timeout
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Datadog API."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["DD-API-KEY"] = self.api_key
        if self.app_key:
            headers["DD-APPLICATION-KEY"] = self.app_key
        return headers
    
    def _parse_time(self, time_str: str) -> int:
        """Parse time string to Unix timestamp."""
        if not time_str or time_str == "now":
            return int(datetime.now().timestamp())
        
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
            return int(dt.timestamp())
        
        # Try ISO 8601 format
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except ValueError:
            pass
        
        # Return current time as fallback
        return int(datetime.now().timestamp())
    
    async def _http_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Datadog API."""
        import aiohttp
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status >= 400:
                        try:
                            body = await response.json()
                            errors = body.get("errors", [])
                            error_msg = ", ".join(errors) if errors else f"HTTP {response.status}"
                        except Exception:
                            error_msg = f"HTTP {response.status}"
                        return {
                            "success": False,
                            "error": error_msg,
                            "status": response.status,
                        }
                    
                    body = await response.json()
                    return {"success": True, "data": body}
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Request timed out after {self.timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def query_metrics(
        self,
        query: str,
        start: str,
        end: str = "now",
    ) -> ToolResult:
        """Query Datadog metrics.
        
        Args:
            query: Datadog metrics query string
                   (e.g., 'avg:system.cpu.user{host:web-01}')
            start: Start time (ISO 8601 or relative like '1h', '30m')
            end: End time (ISO 8601 or 'now')
            
        Returns:
            ToolResult with metrics time series data including metric name,
            scope, unit, and values over time
        """
        if not query:
            return ToolResult(success=False, error="Query is required")
        if not start:
            return ToolResult(success=False, error="Start time is required")
        
        params = {
            "query": query,
            "from": self._parse_time(start),
            "to": self._parse_time(end),
        }
        
        result = await self._http_request("GET", "/api/v1/query", params=params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        series = data.get("series", [])
        
        # Format series data
        formatted_series = []
        for s in series:
            # Extract points
            pointlist = s.get("pointlist", [])
            values = []
            for point in pointlist:
                if len(point) >= 2:
                    values.append({
                        "timestamp": datetime.fromtimestamp(point[0] / 1000).isoformat(),
                        "value": point[1],
                    })
            
            formatted_series.append({
                "metric": s.get("metric"),
                "display_name": s.get("display_name"),
                "scope": s.get("scope"),
                "expression": s.get("expression"),
                "unit": s.get("unit", [{}])[0].get("name") if s.get("unit") else None,
                "values": values,
                "value_count": len(values),
                "tags": s.get("tag_set", []),
            })
        
        return ToolResult(
            success=True,
            data={
                "series": formatted_series,
                "series_count": len(formatted_series),
                "status": data.get("status"),
                "query": query,
            },
            metadata={
                "from_epoch": data.get("from_date"),
                "to_epoch": data.get("to_date"),
                "group_by": data.get("group_by", []),
            },
        )
    
    async def list_monitors(
        self,
        tags: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> ToolResult:
        """List Datadog monitors.
        
        Args:
            tags: Filter by tags (comma-separated)
            status: Filter by status ('Alert', 'Warn', 'No Data', 'OK')
            limit: Maximum number of results
            
        Returns:
            ToolResult with list of monitors including name, type, status,
            query, tags, and threshold configuration
        """
        params: Dict[str, Any] = {
            "page_size": min(limit, 100),
        }
        
        if tags:
            params["monitor_tags"] = tags
        
        result = await self._http_request("GET", "/api/v1/monitor", params=params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        monitors = result["data"]
        
        # Filter by status if specified
        if status:
            monitors = [m for m in monitors if m.get("overall_state") == status]
        
        # Format monitors
        formatted_monitors = []
        status_counts: Dict[str, int] = {}
        
        for monitor in monitors[:limit]:
            overall_state = monitor.get("overall_state", "Unknown")
            status_counts[overall_state] = status_counts.get(overall_state, 0) + 1
            
            formatted_monitors.append({
                "id": monitor.get("id"),
                "name": monitor.get("name"),
                "type": monitor.get("type"),
                "query": monitor.get("query"),
                "message": monitor.get("message", "")[:200],  # Truncate
                "overall_state": overall_state,
                "tags": monitor.get("tags", []),
                "priority": monitor.get("priority"),
                "created": monitor.get("created"),
                "modified": monitor.get("modified"),
                "creator": monitor.get("creator", {}).get("email"),
                "options": {
                    "thresholds": monitor.get("options", {}).get("thresholds"),
                    "notify_no_data": monitor.get("options", {}).get("notify_no_data"),
                    "silenced": monitor.get("options", {}).get("silenced", {}),
                },
            })
        
        return ToolResult(
            success=True,
            data={
                "monitors": formatted_monitors,
                "count": len(formatted_monitors),
                "by_status": status_counts,
            },
            metadata={
                "tag_filter": tags,
                "status_filter": status,
            },
        )
    
    async def get_events(
        self,
        start: str,
        end: str = "now",
        priority: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 100,
    ) -> ToolResult:
        """Get events from Datadog event stream.
        
        Args:
            start: Start time (ISO 8601 or relative like '24h')
            end: End time (ISO 8601 or 'now')
            priority: Filter by priority ('low', 'normal', 'high', 'critical')
            source: Filter by source
            tags: Filter by tags (comma-separated)
            limit: Maximum number of results
            
        Returns:
            ToolResult with list of events including title, text, timestamp,
            priority, source, host, and tags
        """
        if not start:
            return ToolResult(success=False, error="Start time is required")
        
        params: Dict[str, Any] = {
            "start": self._parse_time(start),
            "end": self._parse_time(end),
        }
        
        if priority:
            params["priority"] = priority
        if source:
            params["sources"] = source
        if tags:
            params["tags"] = tags
        
        result = await self._http_request("GET", "/api/v1/events", params=params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        events = data.get("events", [])
        
        # Format events
        formatted_events = []
        source_counts: Dict[str, int] = {}
        priority_counts: Dict[str, int] = {}
        
        for event in events[:limit]:
            event_source = event.get("source", "unknown")
            event_priority = event.get("priority", "normal")
            
            source_counts[event_source] = source_counts.get(event_source, 0) + 1
            priority_counts[event_priority] = priority_counts.get(event_priority, 0) + 1
            
            date_happened = event.get("date_happened", 0)
            
            formatted_events.append({
                "id": event.get("id"),
                "title": event.get("title"),
                "text": event.get("text", "")[:500],  # Truncate
                "date_happened": datetime.fromtimestamp(date_happened).isoformat() if date_happened else None,
                "priority": event_priority,
                "source": event_source,
                "host": event.get("host"),
                "tags": event.get("tags", []),
                "alert_type": event.get("alert_type"),
                "is_aggregate": event.get("is_aggregate", False),
                "device_name": event.get("device_name"),
            })
        
        return ToolResult(
            success=True,
            data={
                "events": formatted_events,
                "count": len(formatted_events),
                "by_source": source_counts,
                "by_priority": priority_counts,
            },
            metadata={
                "start": start,
                "end": end,
                "priority_filter": priority,
                "source_filter": source,
            },
        )
    
    async def create_incident(
        self,
        title: str,
        severity: str = "SEV-3",
        commander: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> ToolResult:
        """Create a new incident in Datadog.
        
        Args:
            title: Incident title
            severity: Severity level ('SEV-1' through 'SEV-5')
            commander: Incident commander (user ID)
            tags: Tags (comma-separated)
            
        Returns:
            ToolResult with incident details including ID, status, severity,
            and creation timestamp
        """
        if not title:
            return ToolResult(success=False, error="Incident title is required")
        
        # Map severity to Datadog format
        severity_map = {
            "SEV-1": "SEV-1",
            "SEV-2": "SEV-2",
            "SEV-3": "SEV-3",
            "SEV-4": "SEV-4",
            "SEV-5": "SEV-5",
        }
        
        dd_severity = severity_map.get(severity, "SEV-3")
        
        # Build incident data
        incident_data: Dict[str, Any] = {
            "data": {
                "type": "incidents",
                "attributes": {
                    "title": title,
                    "customer_impacted": dd_severity in ["SEV-1", "SEV-2"],
                    "fields": {
                        "severity": {
                            "type": "dropdown",
                            "value": dd_severity,
                        },
                    },
                },
            },
        }
        
        # Add commander if specified
        if commander:
            incident_data["data"]["relationships"] = {
                "commander_user": {
                    "data": {
                        "type": "users",
                        "id": commander,
                    },
                },
            }
        
        result = await self._http_request("POST", "/api/v2/incidents", json_data=incident_data)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        incident = data.get("data", {})
        attributes = incident.get("attributes", {})
        
        return ToolResult(
            success=True,
            data={
                "id": incident.get("id"),
                "title": attributes.get("title"),
                "status": attributes.get("status"),
                "severity": attributes.get("fields", {}).get("severity", {}).get("value"),
                "customer_impacted": attributes.get("customer_impacted"),
                "created": attributes.get("created"),
                "modified": attributes.get("modified"),
                "public_id": attributes.get("public_id"),
            },
            metadata={
                "requested_severity": severity,
                "commander": commander,
            },
        )
