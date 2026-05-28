"""
Metrics Skills

Skills for querying and analyzing metrics (Prometheus, Datadog, etc.).
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode

import httpx


class MetricsSkill:
    """
    Metrics investigation skills.
    
    Capabilities:
    - Query Prometheus metrics
    - Detect anomalies
    - Compare baselines
    - Find correlations
    """
    
    def __init__(self, prometheus_url: Optional[str] = None, timeout: float = 30.0):
        self.prometheus_url = prometheus_url or "http://localhost:9090"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.prometheus_url,
                timeout=self.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def query(
        self,
        query: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: str = "1m",
    ) -> Dict[str, Any]:
        """Execute a PromQL range query.
        
        Args:
            query: PromQL query string
            start: Start time (defaults to 1 hour ago)
            end: End time (defaults to now)
            step: Query resolution step (default: 1m)
            
        Returns:
            Prometheus API response with status and data
        """
        client = await self._get_client()
        
        end_time = end or datetime.utcnow()
        start_time = start or (end_time - timedelta(hours=1))
        
        params = {
            "query": query,
            "start": start_time.timestamp(),
            "end": end_time.timestamp(),
            "step": step,
        }
        
        try:
            response = await client.get("/api/v1/query_range", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": str(e), "errorType": "http_error"}
        except httpx.RequestError as e:
            return {"status": "error", "error": str(e), "errorType": "request_error"}
    
    async def query_instant(self, query: str, time: Optional[datetime] = None) -> Dict[str, Any]:
        """Execute an instant PromQL query.
        
        Args:
            query: PromQL query string
            time: Evaluation time (defaults to now)
            
        Returns:
            Prometheus API response with status and data
        """
        client = await self._get_client()
        
        params = {"query": query}
        if time:
            params["time"] = str(time.timestamp())
        
        try:
            response = await client.get("/api/v1/query", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": str(e), "errorType": "http_error"}
        except httpx.RequestError as e:
            return {"status": "error", "error": str(e), "errorType": "request_error"}
    
    async def get_error_rate(
        self,
        service: str,
        duration: str = "5m",
    ) -> float:
        """Get error rate for a service.
        
        Uses standard http_requests_total metric with status codes.
        
        Args:
            service: Service name to query
            duration: Time window for rate calculation
            
        Returns:
            Error rate as a float (0.0 to 1.0)
        """
        # Standard RED metrics query for error rate
        query = f"""
            sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[{duration}])) 
            / 
            sum(rate(http_requests_total{{service="{service}"}}[{duration}]))
        """
        
        result = await self.query_instant(query.strip())
        
        if result.get("status") == "success":
            data = result.get("data", {})
            if data.get("resultType") == "vector" and data.get("result"):
                value = data["result"][0].get("value", [None, "0"])
                try:
                    return float(value[1])
                except (ValueError, IndexError, TypeError):
                    return 0.0
        return 0.0
    
    async def get_latency_percentiles(
        self,
        service: str,
        percentiles: Optional[List[float]] = None,
        duration: str = "5m",
    ) -> Dict[float, float]:
        """Get latency percentiles for a service.
        
        Args:
            service: Service name to query
            percentiles: List of percentiles to calculate (default: [0.5, 0.95, 0.99])
            duration: Time window for histogram calculation
            
        Returns:
            Dictionary mapping percentile to latency value in seconds
        """
        if percentiles is None:
            percentiles = [0.5, 0.95, 0.99]
        
        results = {}
        for p in percentiles:
            # Standard histogram_quantile query
            query = f"""
                histogram_quantile({p}, 
                    sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[{duration}])) by (le)
                )
            """
            
            result = await self.query_instant(query.strip())
            
            if result.get("status") == "success":
                data = result.get("data", {})
                if data.get("resultType") == "vector" and data.get("result"):
                    value = data["result"][0].get("value", [None, "0"])
                    try:
                        results[p] = float(value[1])
                    except (ValueError, IndexError, TypeError):
                        results[p] = 0.0
                else:
                    results[p] = 0.0
            else:
                results[p] = 0.0
        
        return results
    
    async def detect_anomaly(
        self,
        metric: str,
        service: str,
        window: str = "1h",
        stddev_threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """Detect anomalies in a metric using statistical analysis.
        
        Compares current value against the mean +/- N standard deviations.
        
        Args:
            metric: Metric name to check
            service: Service label value
            window: Time window for baseline calculation
            stddev_threshold: Number of standard deviations for anomaly detection
            
        Returns:
            Dictionary with is_anomaly flag and anomaly score
        """
        # Get current value
        current_query = f'{metric}{{service="{service}"}}'
        current_result = await self.query_instant(current_query)
        
        # Get stats over window
        avg_query = f'avg_over_time({metric}{{service="{service}"}}[{window}])'
        stddev_query = f'stddev_over_time({metric}{{service="{service}"}}[{window}])'
        
        avg_result = await self.query_instant(avg_query)
        stddev_result = await self.query_instant(stddev_query)
        
        def extract_value(result: Dict[str, Any]) -> Optional[float]:
            if result.get("status") == "success":
                data = result.get("data", {})
                if data.get("resultType") == "vector" and data.get("result"):
                    try:
                        return float(data["result"][0]["value"][1])
                    except (ValueError, IndexError, TypeError, KeyError):
                        pass
            return None
        
        current = extract_value(current_result)
        avg = extract_value(avg_result)
        stddev = extract_value(stddev_result)
        
        if current is None or avg is None or stddev is None:
            return {"is_anomaly": False, "score": 0.0, "reason": "insufficient_data"}
        
        if stddev == 0:
            return {"is_anomaly": False, "score": 0.0, "reason": "no_variance"}
        
        # Calculate z-score
        z_score = abs(current - avg) / stddev
        is_anomaly = z_score > stddev_threshold
        
        return {
            "is_anomaly": is_anomaly,
            "score": z_score,
            "current_value": current,
            "average": avg,
            "stddev": stddev,
            "threshold": stddev_threshold,
        }
    
    async def compare_to_baseline(
        self,
        metric: str,
        current_window: str = "5m",
        baseline_window: str = "1d",
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare current values to baseline.
        
        Args:
            metric: Metric name to compare
            current_window: Window for current average
            baseline_window: Window for baseline average
            service: Optional service label filter
            
        Returns:
            Dictionary with deviation percentage and significance flag
        """
        label_filter = f'{{service="{service}"}}' if service else ""
        
        current_query = f'avg_over_time({metric}{label_filter}[{current_window}])'
        baseline_query = f'avg_over_time({metric}{label_filter}[{baseline_window}])'
        
        current_result = await self.query_instant(current_query)
        baseline_result = await self.query_instant(baseline_query)
        
        def extract_value(result: Dict[str, Any]) -> Optional[float]:
            if result.get("status") == "success":
                data = result.get("data", {})
                if data.get("resultType") == "vector" and data.get("result"):
                    try:
                        return float(data["result"][0]["value"][1])
                    except (ValueError, IndexError, TypeError, KeyError):
                        pass
            return None
        
        current = extract_value(current_result)
        baseline = extract_value(baseline_result)
        
        if current is None or baseline is None:
            return {"deviation": 0.0, "is_significant": False, "reason": "insufficient_data"}
        
        if baseline == 0:
            return {"deviation": 0.0, "is_significant": False, "reason": "zero_baseline"}
        
        deviation = ((current - baseline) / baseline) * 100
        # Consider >10% deviation as significant
        is_significant = abs(deviation) > 10.0
        
        return {
            "deviation": deviation,
            "is_significant": is_significant,
            "current_value": current,
            "baseline_value": baseline,
        }


# Export for discovery
skill = MetricsSkill
skill_name = "metrics"
skill_description = "Prometheus/metrics investigation skills"
