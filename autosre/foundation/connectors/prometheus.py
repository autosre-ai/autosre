"""
Prometheus Connector - Pull metrics and alerts from Prometheus.

This connector provides:
- Current firing alerts
- Metric queries for investigation
- Alert rule definitions
"""

from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from autosre.foundation.connectors.base import BaseConnector
from autosre.foundation.models import Alert, Severity


class PrometheusConnector(BaseConnector):
    """
    Prometheus connector for querying metrics and alerts.
    
    Works with both Prometheus and Alertmanager APIs.
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._prometheus_url: str = ""
        self._alertmanager_url: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "prometheus"
    
    async def connect(self) -> bool:
        """Connect to Prometheus/Alertmanager."""
        try:
            self._prometheus_url = self.config.get("prometheus_url", "http://localhost:9090")
            self._alertmanager_url = self.config.get("alertmanager_url")
            
            # Create HTTP client
            headers = {}
            if auth_token := self.config.get("auth_token"):
                headers["Authorization"] = f"Bearer {auth_token}"
            
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
            
            # Test connection
            response = await self._client.get(urljoin(self._prometheus_url, "/api/v1/status/config"))
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                self._last_error = f"Prometheus returned status {response.status_code}"
                return False
                
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Prometheus."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
    
    async def health_check(self) -> bool:
        """Check if Prometheus is healthy."""
        if not self._connected or not self._client:
            return False
        
        try:
            response = await self._client.get(urljoin(self._prometheus_url, "/-/healthy"))
            return response.status_code == 200
        except Exception:
            return False
    
    async def sync(self, context_store: Any) -> int:
        """Sync firing alerts to context store."""
        if not self._connected:
            raise RuntimeError("Not connected to Prometheus")
        
        count = 0
        
        # Get firing alerts from Prometheus
        alerts = await self.get_firing_alerts()
        for alert in alerts:
            context_store.add_alert(alert)
            count += 1
        
        # If Alertmanager is configured, also sync from there
        if self._alertmanager_url:
            am_alerts = await self._get_alertmanager_alerts()
            for alert in am_alerts:
                context_store.add_alert(alert)
                count += 1
        
        return count
    
    async def get_firing_alerts(self) -> list[Alert]:
        """Get currently firing alerts from Prometheus."""
        if not self._client:
            return []
        
        alerts = []
        try:
            response = await self._client.get(
                urljoin(self._prometheus_url, "/api/v1/alerts")
            )
            
            if response.status_code != 200:
                self._last_error = f"Failed to get alerts: {response.status_code}"
                return []
            
            data = response.json()
            
            for alert_data in data.get("data", {}).get("alerts", []):
                alert = self._prometheus_alert_to_model(alert_data)
                if alert:
                    alerts.append(alert)
                    
        except Exception as e:
            self._last_error = f"Error getting alerts: {e}"
        
        return alerts
    
    async def _get_alertmanager_alerts(self) -> list[Alert]:
        """Get alerts from Alertmanager API."""
        if not self._client or not self._alertmanager_url:
            return []
        
        alerts = []
        try:
            response = await self._client.get(
                urljoin(self._alertmanager_url, "/api/v2/alerts")
            )
            
            if response.status_code != 200:
                return []
            
            for alert_data in response.json():
                alert = self._alertmanager_alert_to_model(alert_data)
                if alert:
                    alerts.append(alert)
                    
        except Exception as e:
            self._last_error = f"Error getting Alertmanager alerts: {e}"
        
        return alerts
    
    def _prometheus_alert_to_model(self, data: dict) -> Optional[Alert]:
        """Convert Prometheus alert to Alert model."""
        try:
            labels = data.get("labels", {})
            annotations = data.get("annotations", {})
            
            # Extract severity from labels
            severity_str = labels.get("severity", "medium").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "warning": Severity.MEDIUM,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.MEDIUM)
            
            # Extract service name from labels
            service_name = (
                labels.get("service") or
                labels.get("app") or
                labels.get("job") or
                labels.get("instance")
            )
            
            return Alert(
                id=f"prom-{labels.get('alertname', 'unknown')}-{hash(str(labels))}",
                name=labels.get("alertname", "UnknownAlert"),
                severity=severity,
                source="prometheus",
                service_name=service_name,
                namespace=labels.get("namespace"),
                cluster=labels.get("cluster"),
                summary=annotations.get("summary", labels.get("alertname", "")),
                description=annotations.get("description"),
                labels=labels,
                annotations=annotations,
                fired_at=datetime.fromisoformat(data.get("activeAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")),
                resolved_at=None if data.get("state") == "firing" else datetime.utcnow(),
            )
        except Exception:
            return None
    
    def _alertmanager_alert_to_model(self, data: dict) -> Optional[Alert]:
        """Convert Alertmanager alert to Alert model."""
        try:
            labels = data.get("labels", {})
            annotations = data.get("annotations", {})
            
            severity_str = labels.get("severity", "medium").lower()
            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "warning": Severity.MEDIUM,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
                "info": Severity.INFO,
            }
            severity = severity_map.get(severity_str, Severity.MEDIUM)
            
            service_name = (
                labels.get("service") or
                labels.get("app") or
                labels.get("job")
            )
            
            starts_at = data.get("startsAt", datetime.utcnow().isoformat())
            ends_at = data.get("endsAt")
            
            return Alert(
                id=data.get("fingerprint", f"am-{hash(str(labels))}"),
                name=labels.get("alertname", "UnknownAlert"),
                severity=severity,
                source="alertmanager",
                service_name=service_name,
                namespace=labels.get("namespace"),
                cluster=labels.get("cluster"),
                summary=annotations.get("summary", labels.get("alertname", "")),
                description=annotations.get("description"),
                labels=labels,
                annotations=annotations,
                fired_at=datetime.fromisoformat(starts_at.replace("Z", "+00:00")),
                resolved_at=datetime.fromisoformat(ends_at.replace("Z", "+00:00")) if ends_at and ends_at != "0001-01-01T00:00:00Z" else None,
            )
        except Exception:
            return None
    
    async def query(self, promql: str) -> dict:
        """
        Execute a PromQL instant query.
        
        Args:
            promql: PromQL query string
            
        Returns:
            Query result data
        """
        if not self._client:
            raise RuntimeError("Not connected to Prometheus")
        
        response = await self._client.get(
            urljoin(self._prometheus_url, "/api/v1/query"),
            params={"query": promql}
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Query failed: {response.text}")
        
        return response.json().get("data", {})
    
    async def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "1m"
    ) -> dict:
        """
        Execute a PromQL range query.
        
        Args:
            promql: PromQL query string
            start: Start time
            end: End time
            step: Query resolution step
            
        Returns:
            Query result data
        """
        if not self._client:
            raise RuntimeError("Not connected to Prometheus")
        
        response = await self._client.get(
            urljoin(self._prometheus_url, "/api/v1/query_range"),
            params={
                "query": promql,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "step": step,
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Query failed: {response.text}")
        
        return response.json().get("data", {})
    
    async def get_metric_metadata(self, metric_name: str) -> dict:
        """Get metadata for a specific metric."""
        if not self._client:
            raise RuntimeError("Not connected to Prometheus")
        
        response = await self._client.get(
            urljoin(self._prometheus_url, "/api/v1/metadata"),
            params={"metric": metric_name}
        )
        
        if response.status_code != 200:
            return {}
        
        return response.json().get("data", {}).get(metric_name, [{}])[0]
