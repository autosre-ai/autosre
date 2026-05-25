"""Prometheus tool for metrics, alerts, and monitoring.

Provides a standalone tool for querying Prometheus metrics, alerts, targets,
and alerting rules from the Prometheus API.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin


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


class PrometheusTool:
    """Tool for querying Prometheus metrics, alerts, and targets.
    
    Supports instant queries, range queries, and accessing alerts,
    targets, and alerting rules from the Prometheus API.
    
    Example:
        prom = PrometheusTool(prometheus_url="http://prometheus:9090")
        
        # Instant query
        result = await prom.query("up")
        
        # Range query
        result = await prom.query_range("rate(http_requests_total[5m])", start="1h")
        
        # Get active alerts
        result = await prom.alerts(state="firing")
        
        # Get scrape targets
        result = await prom.targets()
        
        # Get alerting rules
        result = await prom.rules(rule_type="alert")
    """
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        timeout: int = 30,
        auth_token: Optional[str] = None,
    ):
        """Initialize the Prometheus tool.
        
        Args:
            prometheus_url: Base URL of Prometheus server
            timeout: Query timeout in seconds
            auth_token: Optional bearer token for authentication
        """
        self.prometheus_url = prometheus_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
    
    def _parse_time(self, time_str: str) -> str:
        """Parse time string to Unix timestamp or Prometheus-compatible format."""
        if not time_str or time_str == "now":
            return str(datetime.now().timestamp())
        
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
            return str(dt.timestamp())
        
        # Try ISO 8601 format
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return str(dt.timestamp())
        except ValueError:
            pass
        
        # Return as-is (might be Unix timestamp)
        return time_str
    
    async def _http_get(self, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make HTTP GET request to Prometheus."""
        import aiohttp
        
        url = urljoin(self.prometheus_url, endpoint)
        
        headers = {}
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
                    body = await response.json()
                    
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": body.get("error", f"HTTP {response.status}"),
                        }
                    
                    return {
                        "success": True,
                        "data": body,
                    }
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Request timed out after {self.timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def query(self, query: str) -> ToolResult:
        """Execute instant PromQL query.
        
        Args:
            query: PromQL query expression (e.g., 'up', 'rate(http_requests_total[5m])')
            
        Returns:
            ToolResult with query results including metric names and current values
        """
        if not query:
            return ToolResult(success=False, error="query is required")
        
        params = {"query": query}
        result = await self._http_get("/api/v1/query", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(
                success=False,
                error=data.get("error", "Query failed"),
            )
        
        result_data = data.get("data", {})
        result_type = result_data.get("resultType")
        results = result_data.get("result", [])
        
        # Format results for readability
        formatted_results = []
        for r in results:
            if result_type == "vector":
                formatted_results.append({
                    "metric": r.get("metric", {}),
                    "value": r.get("value", [None, None])[1],
                    "timestamp": r.get("value", [None, None])[0],
                })
            elif result_type == "scalar":
                formatted_results.append({
                    "value": r[1] if len(r) > 1 else r,
                    "timestamp": r[0] if len(r) > 0 else None,
                })
            else:
                formatted_results.append(r)
        
        return ToolResult(
            success=True,
            data={
                "result_type": result_type,
                "results": formatted_results,
                "count": len(formatted_results),
            },
            metadata={"query": query},
        )
    
    async def query_range(
        self,
        query: str,
        start: str,
        end: str = "now",
        step: str = "1m",
    ) -> ToolResult:
        """Execute range PromQL query for time series data.
        
        Args:
            query: PromQL query expression
            start: Start time (ISO 8601 or relative like '1h', '30m')
            end: End time (ISO 8601 or 'now')
            step: Query resolution step (e.g., '15s', '1m')
            
        Returns:
            ToolResult with time series data including values over time
        """
        if not query:
            return ToolResult(success=False, error="query is required")
        if not start:
            return ToolResult(success=False, error="start time is required for range query")
        
        params = {
            "query": query,
            "start": self._parse_time(start),
            "end": self._parse_time(end),
            "step": step,
        }
        
        result = await self._http_get("/api/v1/query_range", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(
                success=False,
                error=data.get("error", "Query failed"),
            )
        
        result_data = data.get("data", {})
        results = result_data.get("result", [])
        
        # Format results
        formatted_results = []
        for r in results:
            values = r.get("values", [])
            formatted_results.append({
                "metric": r.get("metric", {}),
                "values": [
                    {"timestamp": v[0], "value": v[1]}
                    for v in values
                ],
                "value_count": len(values),
            })
        
        return ToolResult(
            success=True,
            data={
                "result_type": "matrix",
                "results": formatted_results,
                "series_count": len(formatted_results),
            },
            metadata={
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            },
        )
    
    async def alerts(self, state: Optional[str] = None) -> ToolResult:
        """Get active alerts from Prometheus.
        
        Args:
            state: Filter by alert state ('firing', 'pending', 'inactive')
            
        Returns:
            ToolResult with list of alerts including name, severity, and labels
        """
        result = await self._http_get("/api/v1/alerts", {})
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get alerts"))
        
        alerts_data = data.get("data", {}).get("alerts", [])
        
        # Filter by state if specified
        if state:
            alerts_data = [a for a in alerts_data if a.get("state", "").lower() == state.lower()]
        
        # Format alerts
        formatted_alerts = []
        for alert in alerts_data:
            formatted_alerts.append({
                "name": alert.get("labels", {}).get("alertname", "Unknown"),
                "state": alert.get("state"),
                "severity": alert.get("labels", {}).get("severity", "unknown"),
                "labels": alert.get("labels", {}),
                "annotations": alert.get("annotations", {}),
                "active_at": alert.get("activeAt"),
                "value": alert.get("value"),
            })
        
        # Group by state
        state_counts: Dict[str, int] = {}
        for alert in formatted_alerts:
            s = alert["state"]
            state_counts[s] = state_counts.get(s, 0) + 1
        
        return ToolResult(
            success=True,
            data={
                "alerts": formatted_alerts,
                "count": len(formatted_alerts),
                "by_state": state_counts,
            },
            metadata={"filter_state": state},
        )
    
    async def targets(self) -> ToolResult:
        """Get scrape targets from Prometheus.
        
        Returns:
            ToolResult with list of targets including job, instance, health status,
            last scrape time, and any errors
        """
        result = await self._http_get("/api/v1/targets", {})
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get targets"))
        
        targets_data = data.get("data", {})
        active_targets = targets_data.get("activeTargets", [])
        dropped_targets = targets_data.get("droppedTargets", [])
        
        # Format active targets
        formatted_active = []
        for target in active_targets:
            formatted_active.append({
                "job": target.get("labels", {}).get("job", "unknown"),
                "instance": target.get("labels", {}).get("instance", "unknown"),
                "health": target.get("health"),
                "labels": target.get("labels", {}),
                "last_scrape": target.get("lastScrape"),
                "last_scrape_duration": target.get("lastScrapeDuration"),
                "last_error": target.get("lastError"),
                "scrape_pool": target.get("scrapePool"),
                "scrape_url": target.get("scrapeUrl"),
            })
        
        # Count by health
        health_counts: Dict[str, int] = {}
        for target in formatted_active:
            h = target["health"]
            health_counts[h] = health_counts.get(h, 0) + 1
        
        return ToolResult(
            success=True,
            data={
                "active_targets": formatted_active,
                "active_count": len(formatted_active),
                "dropped_count": len(dropped_targets),
                "by_health": health_counts,
            },
        )
    
    async def rules(self, rule_type: Optional[str] = None) -> ToolResult:
        """Get alerting and recording rules from Prometheus.
        
        Args:
            rule_type: Filter by type ('alert' or 'record')
            
        Returns:
            ToolResult with list of rules grouped by rule group, including
            rule name, query, duration, labels, and health
        """
        result = await self._http_get("/api/v1/rules", {})
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Failed to get rules"))
        
        groups = data.get("data", {}).get("groups", [])
        
        formatted_groups = []
        total_rules = 0
        alert_rules = 0
        recording_rules = 0
        
        for group in groups:
            group_rules = []
            for rule in group.get("rules", []):
                rule_info = {
                    "name": rule.get("name"),
                    "type": rule.get("type"),
                    "query": rule.get("query"),
                    "duration": rule.get("duration"),
                    "labels": rule.get("labels", {}),
                    "annotations": rule.get("annotations", {}),
                    "health": rule.get("health"),
                    "state": rule.get("state"),
                    "last_error": rule.get("lastError"),
                }
                
                # Filter by type if specified
                if rule_type:
                    if rule_type == "alert" and rule.get("type") != "alerting":
                        continue
                    if rule_type == "record" and rule.get("type") != "recording":
                        continue
                
                group_rules.append(rule_info)
                total_rules += 1
                
                if rule.get("type") == "alerting":
                    alert_rules += 1
                elif rule.get("type") == "recording":
                    recording_rules += 1
            
            if group_rules:  # Only include groups with rules after filtering
                formatted_groups.append({
                    "name": group.get("name"),
                    "file": group.get("file"),
                    "interval": group.get("interval"),
                    "rules": group_rules,
                    "rule_count": len(group_rules),
                })
        
        return ToolResult(
            success=True,
            data={
                "groups": formatted_groups,
                "group_count": len(formatted_groups),
                "total_rules": total_rules,
                "alert_rules": alert_rules,
                "recording_rules": recording_rules,
            },
            metadata={"filter_type": rule_type},
        )
    
    async def series(
        self,
        match: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> ToolResult:
        """Get series matching a selector.
        
        Args:
            match: Series selector (e.g., 'http_requests_total', '{job="prometheus"}')
            start: Start time for filtering
            end: End time for filtering
            
        Returns:
            ToolResult with list of matching series and their labels
        """
        if not match:
            return ToolResult(success=False, error="match selector is required")
        
        params: Dict[str, str] = {"match[]": match}
        if start:
            params["start"] = self._parse_time(start)
        if end:
            params["end"] = self._parse_time(end)
        
        result = await self._http_get("/api/v1/series", params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Query failed"))
        
        series = data.get("data", [])
        
        return ToolResult(
            success=True,
            data={
                "series": series,
                "count": len(series),
            },
            metadata={"match": match},
        )
    
    async def label_values(self, label_name: str) -> ToolResult:
        """Get values for a label.
        
        Args:
            label_name: Name of the label (e.g., 'job', 'instance')
            
        Returns:
            ToolResult with list of label values
        """
        if not label_name:
            return ToolResult(success=False, error="label_name is required")
        
        result = await self._http_get(f"/api/v1/label/{label_name}/values", {})
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        if data.get("status") != "success":
            return ToolResult(success=False, error=data.get("error", "Query failed"))
        
        values = data.get("data", [])
        
        return ToolResult(
            success=True,
            data={
                "label": label_name,
                "values": values,
                "count": len(values),
            },
        )


# Backward compatibility alias
PrometheusQueryTool = PrometheusTool
