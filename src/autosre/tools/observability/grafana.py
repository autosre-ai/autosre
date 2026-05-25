"""Grafana tool for dashboard and annotation management.

Provides a standalone tool for interacting with Grafana dashboards,
creating snapshots, and searching annotations.
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


class GrafanaTool:
    """Tool for interacting with Grafana dashboards and annotations.
    
    Provides capabilities for listing dashboards, getting dashboard details,
    creating snapshots, and searching annotations.
    
    Example:
        grafana = GrafanaTool(grafana_url="http://grafana:3000", api_key="...")
        
        # List dashboards
        result = await grafana.list_dashboards(query="kubernetes")
        
        # Get dashboard details
        result = await grafana.get_dashboard(uid="abc123")
        
        # Create snapshot for sharing
        result = await grafana.create_snapshot(uid="abc123", snapshot_name="Incident 2024-01")
        
        # Search annotations
        result = await grafana.search_annotations(start="24h", tag="deployment")
    """
    
    def __init__(
        self,
        grafana_url: str = "http://localhost:3000",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize the Grafana tool.
        
        Args:
            grafana_url: Base URL of Grafana server
            api_key: Grafana API key for authentication
            timeout: Request timeout in seconds
        """
        self.grafana_url = grafana_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Grafana API."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _parse_time(self, time_str: str) -> int:
        """Parse time string to Unix timestamp in milliseconds."""
        if not time_str or time_str == "now":
            return int(datetime.now().timestamp() * 1000)
        
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
            return int(dt.timestamp() * 1000)
        
        # Try ISO 8601 format
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass
        
        # Return current time as fallback
        return int(datetime.now().timestamp() * 1000)
    
    async def _http_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Grafana API."""
        import aiohttp
        
        url = f"{self.grafana_url}{endpoint}"
        
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
                    # Handle different response types
                    content_type = response.content_type
                    
                    if response.status >= 400:
                        try:
                            body = await response.json()
                            error_msg = body.get("message", f"HTTP {response.status}")
                        except Exception:
                            error_msg = f"HTTP {response.status}"
                        return {
                            "success": False,
                            "error": error_msg,
                            "status": response.status,
                        }
                    
                    if "application/json" in content_type:
                        body = await response.json()
                    else:
                        body = await response.text()
                    
                    return {"success": True, "data": body}
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Request timed out after {self.timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_dashboards(
        self,
        query: Optional[str] = None,
        folder_id: Optional[int] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> ToolResult:
        """List available dashboards.
        
        Args:
            query: Search query string
            folder_id: Filter by folder ID
            tag: Filter by tag
            limit: Maximum number of results
            
        Returns:
            ToolResult with list of dashboards including UID, title, folder, and tags
        """
        params: Dict[str, Any] = {
            "type": "dash-db",
            "limit": limit,
        }
        
        if query:
            params["query"] = query
        if folder_id:
            params["folderIds"] = folder_id
        if tag:
            params["tag"] = tag
        
        result = await self._http_request("GET", "/api/search", params=params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        dashboards = result["data"]
        
        # Format dashboard list
        formatted_dashboards = []
        for dash in dashboards:
            formatted_dashboards.append({
                "uid": dash.get("uid"),
                "title": dash.get("title"),
                "uri": dash.get("uri"),
                "url": dash.get("url"),
                "folder_title": dash.get("folderTitle", "General"),
                "folder_id": dash.get("folderId"),
                "tags": dash.get("tags", []),
                "is_starred": dash.get("isStarred", False),
            })
        
        # Group by folder
        by_folder: Dict[str, List[str]] = {}
        for dash in formatted_dashboards:
            folder = dash["folder_title"]
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(dash["title"])
        
        return ToolResult(
            success=True,
            data={
                "dashboards": formatted_dashboards,
                "count": len(formatted_dashboards),
                "by_folder": by_folder,
            },
            metadata={
                "query": query,
                "tag": tag,
                "folder_id": folder_id,
            },
        )
    
    async def get_dashboard(self, uid: str) -> ToolResult:
        """Get dashboard details by UID.
        
        Args:
            uid: Dashboard UID
            
        Returns:
            ToolResult with dashboard details including panels, variables,
            metadata, and folder information
        """
        if not uid:
            return ToolResult(success=False, error="Dashboard UID is required")
        
        result = await self._http_request("GET", f"/api/dashboards/uid/{uid}")
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        dashboard = data.get("dashboard", {})
        meta = data.get("meta", {})
        
        # Extract panel information
        panels = []
        for panel in dashboard.get("panels", []):
            panel_info = {
                "id": panel.get("id"),
                "title": panel.get("title"),
                "type": panel.get("type"),
                "description": panel.get("description", ""),
            }
            
            # Extract datasource if available
            datasource = panel.get("datasource")
            if datasource:
                if isinstance(datasource, dict):
                    panel_info["datasource"] = datasource.get("type", str(datasource))
                else:
                    panel_info["datasource"] = str(datasource)
            
            # Extract targets (queries)
            targets = panel.get("targets", [])
            panel_info["query_count"] = len(targets)
            
            panels.append(panel_info)
        
        # Extract variables
        variables = []
        templating = dashboard.get("templating", {})
        for var in templating.get("list", []):
            variables.append({
                "name": var.get("name"),
                "type": var.get("type"),
                "label": var.get("label", var.get("name")),
                "current_value": var.get("current", {}).get("value"),
            })
        
        return ToolResult(
            success=True,
            data={
                "uid": dashboard.get("uid"),
                "title": dashboard.get("title"),
                "description": dashboard.get("description", ""),
                "tags": dashboard.get("tags", []),
                "timezone": dashboard.get("timezone", "browser"),
                "version": dashboard.get("version"),
                "panels": panels,
                "panel_count": len(panels),
                "variables": variables,
                "folder_title": meta.get("folderTitle", "General"),
                "folder_uid": meta.get("folderUid"),
                "created": meta.get("created"),
                "updated": meta.get("updated"),
                "created_by": meta.get("createdBy"),
                "updated_by": meta.get("updatedBy"),
                "url": meta.get("url"),
            },
        )
    
    async def create_snapshot(
        self,
        uid: str,
        snapshot_name: Optional[str] = None,
        expires: int = 3600,
    ) -> ToolResult:
        """Create a dashboard snapshot for sharing.
        
        Args:
            uid: Dashboard UID
            snapshot_name: Name for the snapshot
            expires: Expiration time in seconds (0 for never)
            
        Returns:
            ToolResult with snapshot URL and delete key
        """
        if not uid:
            return ToolResult(success=False, error="Dashboard UID is required")
        
        # First, get the dashboard
        dash_result = await self._http_request("GET", f"/api/dashboards/uid/{uid}")
        
        if not dash_result["success"]:
            return ToolResult(success=False, error=f"Failed to get dashboard: {dash_result.get('error')}")
        
        dashboard = dash_result["data"].get("dashboard", {})
        
        # Create snapshot
        snapshot_data = {
            "dashboard": dashboard,
            "name": snapshot_name or f"Snapshot of {dashboard.get('title', 'Unknown')}",
            "expires": expires,
        }
        
        result = await self._http_request("POST", "/api/snapshots", json_data=snapshot_data)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        data = result["data"]
        
        return ToolResult(
            success=True,
            data={
                "key": data.get("key"),
                "delete_key": data.get("deleteKey"),
                "url": data.get("url"),
                "delete_url": data.get("deleteUrl"),
                "expires": expires,
                "expires_at": (datetime.now() + timedelta(seconds=expires)).isoformat() if expires > 0 else "never",
                "dashboard_title": dashboard.get("title"),
            },
            metadata={"dashboard_uid": uid},
        )
    
    async def search_annotations(
        self,
        start: Optional[str] = None,
        end: str = "now",
        tag: Optional[str] = None,
        dashboard_id: Optional[int] = None,
        annotation_type: Optional[str] = None,
        limit: int = 100,
    ) -> ToolResult:
        """Search annotations and events.
        
        Args:
            start: Start time (ISO 8601 or relative like '1h', '24h')
            end: End time (ISO 8601 or 'now')
            tag: Filter by tag
            dashboard_id: Filter by dashboard ID
            annotation_type: Filter by type ('annotation' or 'alert')
            limit: Maximum number of results
            
        Returns:
            ToolResult with list of annotations including text, tags, time range,
            and associated dashboard
        """
        params: Dict[str, Any] = {
            "limit": limit,
        }
        
        if start:
            params["from"] = self._parse_time(start)
        if end:
            params["to"] = self._parse_time(end)
        if tag:
            params["tags"] = tag
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if annotation_type:
            params["type"] = annotation_type
        
        result = await self._http_request("GET", "/api/annotations", params=params)
        
        if not result["success"]:
            return ToolResult(success=False, error=result.get("error"))
        
        annotations = result["data"]
        
        # Format annotations
        formatted_annotations = []
        for ann in annotations:
            time_ms = ann.get("time", 0)
            time_end_ms = ann.get("timeEnd", time_ms)
            
            formatted_annotations.append({
                "id": ann.get("id"),
                "dashboard_id": ann.get("dashboardId"),
                "dashboard_uid": ann.get("dashboardUID"),
                "panel_id": ann.get("panelId"),
                "text": ann.get("text", ""),
                "tags": ann.get("tags", []),
                "time": datetime.fromtimestamp(time_ms / 1000).isoformat() if time_ms else None,
                "time_end": datetime.fromtimestamp(time_end_ms / 1000).isoformat() if time_end_ms else None,
                "is_region": ann.get("isRegion", False),
                "type": "alert" if ann.get("alertId") else "annotation",
                "alert_id": ann.get("alertId"),
                "created_by": ann.get("login", ann.get("email")),
            })
        
        # Group by tag
        by_tag: Dict[str, int] = {}
        for ann in formatted_annotations:
            for t in ann["tags"]:
                by_tag[t] = by_tag.get(t, 0) + 1
        
        return ToolResult(
            success=True,
            data={
                "annotations": formatted_annotations,
                "count": len(formatted_annotations),
                "by_tag": by_tag,
            },
            metadata={
                "start": start,
                "end": end,
                "tag_filter": tag,
                "dashboard_id": dashboard_id,
            },
        )
