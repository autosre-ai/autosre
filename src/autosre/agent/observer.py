"""
Observer - Watch for alerts, metrics, logs, and changes.

The observer layer is responsible for:
- Watching for incoming alerts
- Analyzing metrics for anomalies
- Correlating logs with incidents
- Detecting recent changes
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Any
from collections import deque


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Alert, ChangeEvent, Severity


class AlertWatcher:
    """
    Watch for alerts from monitoring systems.
    
    Polls Prometheus/Alertmanager and triggers callbacks
    when new alerts are detected.
    """
    
    def __init__(
        self,
        context_store: ContextStore,
        poll_interval: int = 30,
    ):
        """
        Initialize alert watcher.
        
        Args:
            context_store: Context store for alert storage
            poll_interval: Seconds between polls
        """
        self.context_store = context_store
        self.poll_interval = poll_interval
        self._callbacks: list[Callable[[Alert], Any]] = []
        self._seen_alerts: set[str] = set()
        self._running = False
    
    def on_alert(self, callback: Callable[[Alert], Any]) -> None:
        """
        Register a callback for new alerts.
        
        Args:
            callback: Function to call with new alerts
        """
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Start watching for alerts."""
        self._running = True
        
        while self._running:
            await self._check_alerts()
            await asyncio.sleep(self.poll_interval)
    
    def stop(self) -> None:
        """Stop watching for alerts."""
        self._running = False
    
    async def _check_alerts(self) -> None:
        """Check for new alerts."""
        alerts = self.context_store.get_firing_alerts()
        
        for alert in alerts:
            if alert.id not in self._seen_alerts:
                self._seen_alerts.add(alert.id)
                
                # Trigger callbacks
                for callback in self._callbacks:
                    try:
                        result = callback(alert)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        print(f"Alert callback error: {e}")
    
    def get_alert_history(self, hours: int = 24) -> list[Alert]:
        """Get alert history."""
        # Would need to query alerts including resolved ones
        return self.context_store.get_firing_alerts()


class MetricAnalyzer:
    """
    Analyze metrics for anomalies.
    
    Detects:
    - Sudden spikes/drops
    - Trend changes
    - Threshold violations
    """
    
    def __init__(self, prometheus_url: Optional[str] = None):
        """
        Initialize metric analyzer.
        
        Args:
            prometheus_url: Prometheus server URL
        """
        self.prometheus_url = prometheus_url or "http://localhost:9090"
        self._baselines: dict[str, dict] = {}
    
    async def analyze_service(self, service_name: str) -> dict:
        """
        Analyze metrics for a service.
        
        Args:
            service_name: Service to analyze
            
        Returns:
            Analysis results with anomalies
        """
        results = {
            "service": service_name,
            "timestamp": utcnow().isoformat(),
            "anomalies": [],
            "metrics": {},
        }
        
        # Check CPU usage
        cpu_anomaly = await self._check_cpu(service_name)
        if cpu_anomaly:
            results["anomalies"].append(cpu_anomaly)
        
        # Check memory usage
        memory_anomaly = await self._check_memory(service_name)
        if memory_anomaly:
            results["anomalies"].append(memory_anomaly)
        
        # Check error rate
        error_anomaly = await self._check_error_rate(service_name)
        if error_anomaly:
            results["anomalies"].append(error_anomaly)
        
        # Check latency
        latency_anomaly = await self._check_latency(service_name)
        if latency_anomaly:
            results["anomalies"].append(latency_anomaly)
        
        return results
    
    async def _query_prometheus(self, query: str) -> Optional[float]:
        """Execute a PromQL query."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                )
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("data", {}).get("result", [])
                    if results:
                        return float(results[0]["value"][1])
        except Exception:
            pass
        return None
    
    async def _check_cpu(self, service: str) -> Optional[dict]:
        """Check CPU usage for anomalies."""
        query = f'sum(rate(container_cpu_usage_seconds_total{{pod=~"{service}.*"}}[5m])) / sum(kube_pod_container_resource_limits{{pod=~"{service}.*",resource="cpu"}})'
        value = await self._query_prometheus(query)
        
        if value and value > 0.9:
            return {
                "type": "high_cpu",
                "metric": "cpu_usage_percent",
                "value": value * 100,
                "threshold": 90,
                "severity": "warning" if value < 0.95 else "critical",
            }
        return None
    
    async def _check_memory(self, service: str) -> Optional[dict]:
        """Check memory usage for anomalies."""
        query = f'sum(container_memory_usage_bytes{{pod=~"{service}.*"}}) / sum(kube_pod_container_resource_limits{{pod=~"{service}.*",resource="memory"}})'
        value = await self._query_prometheus(query)
        
        if value and value > 0.85:
            return {
                "type": "high_memory",
                "metric": "memory_usage_percent",
                "value": value * 100,
                "threshold": 85,
                "severity": "warning" if value < 0.95 else "critical",
            }
        return None
    
    async def _check_error_rate(self, service: str) -> Optional[dict]:
        """Check error rate for anomalies."""
        query = f'sum(rate(http_requests_total{{pod=~"{service}.*",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{pod=~"{service}.*"}}[5m]))'
        value = await self._query_prometheus(query)
        
        if value and value > 0.01:  # > 1% error rate
            return {
                "type": "high_error_rate",
                "metric": "error_rate_percent",
                "value": value * 100,
                "threshold": 1,
                "severity": "warning" if value < 0.05 else "critical",
            }
        return None
    
    async def _check_latency(self, service: str) -> Optional[dict]:
        """Check latency for anomalies."""
        query = f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{pod=~"{service}.*"}}[5m])) by (le))'
        value = await self._query_prometheus(query)
        
        if value and value > 1.0:  # > 1s p99
            return {
                "type": "high_latency",
                "metric": "p99_latency_seconds",
                "value": value,
                "threshold": 1.0,
                "severity": "warning" if value < 2.0 else "critical",
            }
        return None


class LogCorrelator:
    """
    Correlate logs with incidents.
    
    Finds log patterns that correlate with alerts
    and anomalies.
    """
    
    def __init__(self):
        """Initialize log correlator."""
        self._error_patterns = [
            r"(?i)error",
            r"(?i)exception",
            r"(?i)failed",
            r"(?i)timeout",
            r"(?i)connection refused",
            r"(?i)out of memory",
            r"(?i)oom",
        ]
    
    async def find_related_logs(
        self,
        service_name: str,
        alert_time: datetime,
        window_minutes: int = 15,
    ) -> list[dict]:
        """
        Find logs related to an alert.
        
        Args:
            service_name: Service to search
            alert_time: When the alert fired
            window_minutes: Time window to search
            
        Returns:
            List of relevant log entries
        """
        # This would integrate with Loki, Elasticsearch, etc.
        # For now, return empty - real implementation would query log backend
        return []
    
    def extract_error_context(self, logs: list[dict]) -> dict:
        """
        Extract error context from logs.
        
        Args:
            logs: List of log entries
            
        Returns:
            Summary of errors found
        """
        import re
        
        errors = []
        for log in logs:
            message = log.get("message", "")
            for pattern in self._error_patterns:
                if re.search(pattern, message):
                    errors.append({
                        "timestamp": log.get("timestamp"),
                        "message": message[:200],
                        "pattern": pattern,
                    })
                    break
        
        return {
            "error_count": len(errors),
            "errors": errors[:10],  # Limit to 10
        }


class ChangeDetector:
    """
    Detect recent changes that may be relevant.
    
    Correlates alerts with recent deployments,
    config changes, and other changes.
    """
    
    def __init__(self, context_store: ContextStore):
        """
        Initialize change detector.
        
        Args:
            context_store: Context store for change history
        """
        self.context_store = context_store
    
    def find_relevant_changes(
        self,
        service_name: str,
        alert_time: datetime,
        lookback_hours: int = 24,
    ) -> list[dict]:
        """
        Find changes that may have caused an alert.
        
        Args:
            service_name: Affected service
            alert_time: When the alert fired
            lookback_hours: How far back to look
            
        Returns:
            List of potentially relevant changes with scores
        """
        changes = self.context_store.get_recent_changes(
            service_name=None,  # Get all, we'll score them
            hours=lookback_hours,
        )
        
        scored_changes = []
        for change in changes:
            if change.timestamp > alert_time:
                continue  # Skip changes after the alert
            
            score = self._score_relevance(change, service_name, alert_time)
            if score > 0:
                scored_changes.append({
                    "change": change,
                    "score": score,
                    "minutes_before": (alert_time - change.timestamp).total_seconds() / 60,
                })
        
        # Sort by score
        scored_changes.sort(key=lambda x: -x["score"])
        
        return scored_changes[:10]
    
    def _score_relevance(
        self,
        change: ChangeEvent,
        service_name: str,
        alert_time: datetime,
    ) -> float:
        """Score how relevant a change is to an alert."""
        score = 0.0
        
        # Direct service match
        if change.service_name == service_name:
            score += 5.0
        
        # Time proximity (changes closer to alert are more suspicious)
        minutes_before = (alert_time - change.timestamp).total_seconds() / 60
        if minutes_before < 30:
            score += 3.0
        elif minutes_before < 60:
            score += 2.0
        elif minutes_before < 120:
            score += 1.0
        
        # Deployment is highest risk
        if change.change_type.value == "deployment":
            score += 2.0
        elif change.change_type.value == "config_change":
            score += 1.5
        elif change.change_type.value == "rollback":
            score += 1.0
        
        # Failed changes are very suspicious
        if not change.successful:
            score += 3.0
        
        return score
    
    def get_change_summary(self, hours: int = 24) -> dict:
        """
        Get summary of recent changes.
        
        Returns:
            Summary with counts and notable changes
        """
        changes = self.context_store.get_recent_changes(hours=hours)
        
        by_type = {}
        by_service = {}
        failed = []
        
        for change in changes:
            # Count by type
            t = change.change_type.value
            by_type[t] = by_type.get(t, 0) + 1
            
            # Count by service
            by_service[change.service_name] = by_service.get(change.service_name, 0) + 1
            
            # Track failures
            if not change.successful:
                failed.append(change)
        
        return {
            "total_changes": len(changes),
            "by_type": by_type,
            "by_service": by_service,
            "failed_changes": len(failed),
            "failed": failed[:5],
        }
