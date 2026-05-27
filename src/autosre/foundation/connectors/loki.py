"""
Loki Connector - Pull logs from Grafana Loki.

This connector provides:
- Log queries using LogQL
- Error log aggregation
- Log pattern detection
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from autosre.foundation.connectors.base import BaseConnector


class LokiConnector(BaseConnector):
    """
    Grafana Loki connector for querying logs.
    
    Supports:
    - LogQL queries
    - Label-based filtering
    - Time-range queries
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._loki_url: str = ""
    
    @property
    def name(self) -> str:
        return "loki"
    
    async def connect(self) -> bool:
        """Connect to Loki."""
        try:
            self._loki_url = (
                self.config.get("loki_url") or 
                self.config.get("url") or 
                os.environ.get("LOKI_URL", "http://localhost:3100")
            )
            
            # Create HTTP client
            headers = {}
            if auth_token := (self.config.get("auth_token") or os.environ.get("LOKI_TOKEN")):
                headers["Authorization"] = f"Bearer {auth_token}"
            
            # Support basic auth
            auth = None
            if username := (self.config.get("username") or os.environ.get("LOKI_USER")):
                password = self.config.get("password") or os.environ.get("LOKI_PASSWORD", "")
                auth = (username, password)
            
            self._client = httpx.AsyncClient(
                timeout=self.config.get("timeout", 30.0),
                headers=headers,
                auth=auth,
            )
            
            # Test connection by checking ready endpoint
            response = await self._client.get(f"{self._loki_url}/ready")
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                self._last_error = f"Loki returned status {response.status_code}"
                return False
                
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Loki."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
    
    async def health_check(self) -> bool:
        """Check if Loki is healthy."""
        if not self._connected or not self._client:
            return False
        
        try:
            response = await self._client.get(f"{self._loki_url}/ready")
            return response.status_code == 200
        except Exception:
            return False
    
    async def sync(self, context_store: Any) -> int:
        """
        Sync logs to context store.
        
        Note: Unlike other connectors, logs are typically queried on-demand
        rather than synced periodically. This method syncs recent error logs.
        """
        if not self._connected:
            raise RuntimeError("Not connected to Loki")
        
        # For now, this is a no-op as logs are queried on-demand
        # Future: Could sync recent errors to a log buffer in context store
        return 0
    
    async def query(
        self,
        logql: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Execute a LogQL query.
        
        Args:
            logql: LogQL query string
            start: Start time (default: 1 hour ago)
            end: End time (default: now)
            limit: Maximum number of log entries to return
            
        Returns:
            List of log entries with timestamp, labels, and line
        """
        if not self._client:
            raise RuntimeError("Not connected to Loki")
        
        now = datetime.now(timezone.utc)
        if end is None:
            end = now
        if start is None:
            start = now - timedelta(hours=1)
        
        response = await self._client.get(
            f"{self._loki_url}/loki/api/v1/query_range",
            params={
                "query": logql,
                "start": int(start.timestamp() * 1e9),  # nanoseconds
                "end": int(end.timestamp() * 1e9),
                "limit": limit,
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Query failed: {response.text}")
        
        data = response.json()
        results = []
        
        for stream in data.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for entry in stream.get("values", []):
                ts_ns, line = entry
                ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
                results.append({
                    "timestamp": ts,
                    "labels": labels,
                    "line": line,
                })
        
        return results
    
    async def query_errors(
        self,
        service: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        namespace: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query error logs for a specific service.
        
        Args:
            service: Service name
            start: Start time
            end: End time
            namespace: Optional namespace filter
            limit: Maximum entries
            
        Returns:
            List of error log entries
        """
        # Build LogQL query
        label_filters = [f'service="{service}"']
        if namespace:
            label_filters.append(f'namespace="{namespace}"')
        
        labels = ",".join(label_filters)
        logql = f'{{{labels}}} |= "error" or |= "ERROR" or |= "Error"'
        
        return await self.query(logql, start, end, limit)
    
    async def get_log_volume(
        self,
        service: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: str = "1m",
    ) -> list[dict[str, Any]]:
        """
        Get log volume over time for a service.
        
        Args:
            service: Service name
            start: Start time
            end: End time
            step: Query step interval
            
        Returns:
            Time series of log counts
        """
        if not self._client:
            raise RuntimeError("Not connected to Loki")
        
        now = datetime.now(timezone.utc)
        if end is None:
            end = now
        if start is None:
            start = now - timedelta(hours=1)
        
        logql = f'sum(count_over_time({{service="{service}"}}[{step}]))'
        
        response = await self._client.get(
            f"{self._loki_url}/loki/api/v1/query_range",
            params={
                "query": logql,
                "start": int(start.timestamp() * 1e9),
                "end": int(end.timestamp() * 1e9),
                "step": step,
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Query failed: {response.text}")
        
        data = response.json()
        results = []
        
        for result in data.get("data", {}).get("result", []):
            for value in result.get("values", []):
                ts, count = value
                results.append({
                    "timestamp": datetime.fromtimestamp(float(ts), tz=timezone.utc),
                    "count": float(count),
                })
        
        return results
    
    async def get_labels(self, start: Optional[datetime] = None) -> list[str]:
        """Get available label names."""
        if not self._client:
            raise RuntimeError("Not connected to Loki")
        
        params = {}
        if start:
            params["start"] = int(start.timestamp() * 1e9)
        
        response = await self._client.get(
            f"{self._loki_url}/loki/api/v1/labels",
            params=params,
        )
        
        if response.status_code != 200:
            return []
        
        return response.json().get("data", [])
    
    async def get_label_values(
        self,
        label: str,
        start: Optional[datetime] = None,
    ) -> list[str]:
        """Get values for a specific label."""
        if not self._client:
            raise RuntimeError("Not connected to Loki")
        
        params = {}
        if start:
            params["start"] = int(start.timestamp() * 1e9)
        
        response = await self._client.get(
            f"{self._loki_url}/loki/api/v1/label/{label}/values",
            params=params,
        )
        
        if response.status_code != 200:
            return []
        
        return response.json().get("data", [])
