"""
Metrics Collector for AutoSRE V2.

High-performance Prometheus metrics collection with:
- Adaptive sampling based on metric volatility
- Connection pooling and batched queries
- Metric buffering and caching
- Automatic retry with exponential backoff
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field, ConfigDict

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class SamplingStrategy(str, Enum):
    """Sampling strategy for metric collection."""
    
    FIXED = "fixed"  # Fixed interval sampling
    ADAPTIVE = "adaptive"  # Adapt based on volatility
    BURST = "burst"  # High frequency during anomalies
    DOWNSAMPLED = "downsampled"  # Lower frequency for stable metrics


@dataclass
class CollectorConfig:
    """Configuration for the metrics collector."""
    
    prometheus_url: str = "http://localhost:9090"
    scrape_interval_seconds: float = 15.0
    scrape_timeout_seconds: float = 10.0
    max_concurrent_queries: int = 10
    max_samples_per_query: int = 11000  # Prometheus default limit
    buffer_size: int = 10000
    enable_caching: bool = True
    cache_ttl_seconds: float = 5.0
    retry_attempts: int = 3
    retry_base_delay: float = 1.0
    adaptive_sampling_enabled: bool = True
    min_sampling_interval: float = 5.0
    max_sampling_interval: float = 60.0
    volatility_window_samples: int = 20
    volatility_threshold_high: float = 0.5
    volatility_threshold_low: float = 0.1
    batch_size: int = 50


@dataclass
class MetricSample:
    """A single metric sample."""
    
    timestamp: datetime
    value: float
    
    def __hash__(self) -> int:
        return hash((self.timestamp.timestamp(), self.value))


@dataclass
class MetricSeries:
    """A time series of metric samples."""
    
    name: str
    labels: dict[str, str]
    samples: list[MetricSample] = field(default_factory=list)
    metric_type: str = "gauge"
    
    @property
    def fingerprint(self) -> str:
        """Generate unique fingerprint for this series."""
        label_str = ",".join(f"{k}={v}" for k, v in sorted(self.labels.items()))
        content = f"{self.name}{{{label_str}}}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @property
    def latest_value(self) -> Optional[float]:
        """Get the most recent value."""
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s.timestamp).value
    
    @property
    def time_range(self) -> Optional[tuple[datetime, datetime]]:
        """Get the time range of samples."""
        if not self.samples:
            return None
        sorted_samples = sorted(self.samples, key=lambda s: s.timestamp)
        return (sorted_samples[0].timestamp, sorted_samples[-1].timestamp)
    
    def add_sample(self, timestamp: datetime, value: float) -> None:
        """Add a sample to the series."""
        self.samples.append(MetricSample(timestamp=timestamp, value=value))
    
    def values_array(self) -> list[float]:
        """Get values as a sorted array by timestamp."""
        return [s.value for s in sorted(self.samples, key=lambda s: s.timestamp)]
    
    def timestamps_array(self) -> list[datetime]:
        """Get timestamps as a sorted array."""
        return [s.timestamp for s in sorted(self.samples, key=lambda s: s.timestamp)]


@dataclass
class CollectionResult:
    """Result of a metric collection operation."""
    
    series: list[MetricSeries]
    query: str
    duration_ms: float
    samples_count: int
    cached: bool = False
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class CollectionStats:
    """Statistics for metric collection."""
    
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_samples: int = 0
    total_series: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_duration_ms: float = 0.0
    last_collection_time: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.successful_queries / self.total_queries
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    @property
    def average_query_time_ms(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.total_duration_ms / self.total_queries


class AdaptiveSampler:
    """
    Adaptive sampling based on metric volatility.
    
    Increases sampling frequency for volatile metrics,
    decreases for stable ones.
    """
    
    def __init__(
        self,
        min_interval: float = 5.0,
        max_interval: float = 60.0,
        window_size: int = 20,
        high_threshold: float = 0.5,
        low_threshold: float = 0.1,
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.window_size = window_size
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        
        # Track volatility per metric fingerprint
        self._volatility_cache: dict[str, list[float]] = defaultdict(list)
        self._interval_cache: dict[str, float] = {}
        self._last_sample: dict[str, datetime] = {}
    
    def compute_volatility(self, values: list[float]) -> float:
        """
        Compute coefficient of variation as volatility measure.
        
        Returns 0 for constant series, higher values for more volatile.
        """
        if len(values) < 2:
            return 0.0
        
        import statistics
        mean = statistics.mean(values)
        if mean == 0:
            return 0.0
        
        std = statistics.stdev(values)
        return std / abs(mean)
    
    def update_volatility(self, fingerprint: str, value: float) -> float:
        """Update volatility tracking for a metric and return current volatility."""
        values = self._volatility_cache[fingerprint]
        values.append(value)
        
        # Keep only window_size recent values
        if len(values) > self.window_size:
            self._volatility_cache[fingerprint] = values[-self.window_size:]
        
        return self.compute_volatility(self._volatility_cache[fingerprint])
    
    def get_sampling_interval(self, fingerprint: str, volatility: float) -> float:
        """
        Get the recommended sampling interval based on volatility.
        
        High volatility -> shorter interval (more samples)
        Low volatility -> longer interval (fewer samples)
        """
        if volatility >= self.high_threshold:
            interval = self.min_interval
        elif volatility <= self.low_threshold:
            interval = self.max_interval
        else:
            # Linear interpolation between thresholds
            ratio = (volatility - self.low_threshold) / (self.high_threshold - self.low_threshold)
            interval = self.max_interval - ratio * (self.max_interval - self.min_interval)
        
        self._interval_cache[fingerprint] = interval
        return interval
    
    def should_sample(self, fingerprint: str, current_time: datetime) -> bool:
        """Check if we should sample this metric now."""
        if fingerprint not in self._last_sample:
            self._last_sample[fingerprint] = current_time
            return True
        
        interval = self._interval_cache.get(fingerprint, self.min_interval)
        elapsed = (current_time - self._last_sample[fingerprint]).total_seconds()
        
        if elapsed >= interval:
            self._last_sample[fingerprint] = current_time
            return True
        
        return False
    
    def reset(self, fingerprint: Optional[str] = None) -> None:
        """Reset sampling state for a metric or all metrics."""
        if fingerprint:
            self._volatility_cache.pop(fingerprint, None)
            self._interval_cache.pop(fingerprint, None)
            self._last_sample.pop(fingerprint, None)
        else:
            self._volatility_cache.clear()
            self._interval_cache.clear()
            self._last_sample.clear()


class MetricBuffer:
    """
    Thread-safe buffer for metric samples.
    
    Supports:
    - Fixed-size circular buffer
    - Aggregation over time windows
    - Efficient serialization
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._buffer: dict[str, list[MetricSample]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._total_samples = 0
    
    async def add(self, fingerprint: str, sample: MetricSample) -> None:
        """Add a sample to the buffer."""
        async with self._lock:
            samples = self._buffer[fingerprint]
            samples.append(sample)
            self._total_samples += 1
            
            # Enforce size limit per series
            max_per_series = self.max_size // max(len(self._buffer), 1)
            if len(samples) > max_per_series:
                self._buffer[fingerprint] = samples[-max_per_series:]
                self._total_samples -= len(samples) - max_per_series
    
    async def add_batch(
        self,
        fingerprint: str,
        samples: list[MetricSample],
    ) -> None:
        """Add multiple samples to the buffer."""
        async with self._lock:
            existing = self._buffer[fingerprint]
            existing.extend(samples)
            self._total_samples += len(samples)
            
            # Enforce size limit
            max_per_series = self.max_size // max(len(self._buffer), 1)
            if len(existing) > max_per_series:
                removed = len(existing) - max_per_series
                self._buffer[fingerprint] = existing[-max_per_series:]
                self._total_samples -= removed
    
    async def get(
        self,
        fingerprint: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[MetricSample]:
        """Get samples for a fingerprint, optionally filtered by time range."""
        async with self._lock:
            samples = self._buffer.get(fingerprint, [])
            
            if start or end:
                filtered = []
                for s in samples:
                    if start and s.timestamp < start:
                        continue
                    if end and s.timestamp > end:
                        continue
                    filtered.append(s)
                return filtered
            
            return list(samples)
    
    async def get_all(self) -> dict[str, list[MetricSample]]:
        """Get all samples from the buffer."""
        async with self._lock:
            return {k: list(v) for k, v in self._buffer.items()}
    
    async def clear(self, fingerprint: Optional[str] = None) -> None:
        """Clear buffer for a specific fingerprint or all."""
        async with self._lock:
            if fingerprint:
                if fingerprint in self._buffer:
                    self._total_samples -= len(self._buffer[fingerprint])
                    del self._buffer[fingerprint]
            else:
                self._buffer.clear()
                self._total_samples = 0
    
    async def aggregate(
        self,
        fingerprint: str,
        window_seconds: float,
        func: Callable[[list[float]], float],
    ) -> list[MetricSample]:
        """
        Aggregate samples into time windows.
        
        Args:
            fingerprint: Metric fingerprint
            window_seconds: Window size in seconds
            func: Aggregation function (e.g., statistics.mean)
        
        Returns:
            List of aggregated samples (one per window)
        """
        samples = await self.get(fingerprint)
        if not samples:
            return []
        
        sorted_samples = sorted(samples, key=lambda s: s.timestamp)
        result = []
        
        window_start = sorted_samples[0].timestamp
        window_values: list[float] = []
        
        for sample in sorted_samples:
            if (sample.timestamp - window_start).total_seconds() < window_seconds:
                window_values.append(sample.value)
            else:
                # Emit aggregated value for completed window
                if window_values:
                    result.append(MetricSample(
                        timestamp=window_start,
                        value=func(window_values),
                    ))
                
                # Start new window
                window_start = sample.timestamp
                window_values = [sample.value]
        
        # Don't forget the last window
        if window_values:
            result.append(MetricSample(
                timestamp=window_start,
                value=func(window_values),
            ))
        
        return result
    
    @property
    def size(self) -> int:
        """Get total number of samples in buffer."""
        return self._total_samples
    
    @property
    def series_count(self) -> int:
        """Get number of unique series in buffer."""
        return len(self._buffer)


class MetricCache:
    """
    Simple TTL cache for query results.
    """
    
    def __init__(self, ttl_seconds: float = 5.0, max_entries: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[str, tuple[float, CollectionResult]] = {}
        self._lock = asyncio.Lock()
    
    def _hash_query(self, query: str, params: dict[str, Any]) -> str:
        """Generate cache key from query and params."""
        content = f"{query}|{sorted(params.items())}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    async def get(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[CollectionResult]:
        """Get cached result if valid."""
        key = self._hash_query(query, params or {})
        
        async with self._lock:
            if key not in self._cache:
                return None
            
            cached_time, result = self._cache[key]
            if time.time() - cached_time > self.ttl_seconds:
                del self._cache[key]
                return None
            
            return result
    
    async def set(
        self,
        query: str,
        params: Optional[dict[str, Any]],
        result: CollectionResult,
    ) -> None:
        """Cache a query result."""
        key = self._hash_query(query, params or {})
        
        async with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self.max_entries:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            
            self._cache[key] = (time.time(), result)
    
    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()


class MetricsCollector:
    """
    High-performance Prometheus metrics collector.
    
    Features:
    - Concurrent query execution with configurable limits
    - Adaptive sampling based on metric volatility
    - Query result caching
    - Automatic retry with exponential backoff
    - Metric buffering for historical data
    
    Example:
        config = CollectorConfig(prometheus_url="http://prometheus:9090")
        collector = MetricsCollector(config)
        
        # Collect instant values
        result = await collector.query_instant("up{job='api'}")
        
        # Collect range data
        results = await collector.query_range(
            query="rate(http_requests_total[5m])",
            start=datetime.now() - timedelta(hours=1),
            end=datetime.now(),
        )
    """
    
    def __init__(
        self,
        config: Optional[CollectorConfig] = None,
        prometheus_url: Optional[str] = None,
    ):
        self.config = config or CollectorConfig()
        if prometheus_url:
            self.config.prometheus_url = prometheus_url
        
        self._client: Optional[httpx.AsyncClient] = None
        self._sampler = AdaptiveSampler(
            min_interval=self.config.min_sampling_interval,
            max_interval=self.config.max_sampling_interval,
            window_size=self.config.volatility_window_samples,
            high_threshold=self.config.volatility_threshold_high,
            low_threshold=self.config.volatility_threshold_low,
        )
        self._buffer = MetricBuffer(max_size=self.config.buffer_size)
        self._cache = MetricCache(ttl_seconds=self.config.cache_ttl_seconds)
        self._stats = CollectionStats()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_queries)
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.prometheus_url,
                timeout=self.config.scrape_timeout_seconds,
            )
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client and cleanup."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "MetricsCollector":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def _execute_query(
        self,
        endpoint: str,
        params: dict[str, Any],
        query: str,
    ) -> CollectionResult:
        """Execute a Prometheus query with retry logic."""
        start_time = time.time()
        
        # Check cache first
        if self.config.enable_caching:
            cached = await self._cache.get(query, params)
            if cached:
                self._stats.cache_hits += 1
                cached.cached = True
                return cached
            self._stats.cache_misses += 1
        
        async with self._semaphore:
            client = await self._get_client()
            last_error = None
            
            for attempt in range(self.config.retry_attempts):
                try:
                    response = await client.get(endpoint, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("status") != "success":
                        error_msg = data.get("error", "Unknown error")
                        raise ValueError(f"Query failed: {error_msg}")
                    
                    # Parse results
                    result_data = data.get("data", {})
                    result_type = result_data.get("resultType", "")
                    raw_results = result_data.get("result", [])
                    
                    series = []
                    total_samples = 0
                    
                    for item in raw_results:
                        metric_labels = item.get("metric", {})
                        metric_name = metric_labels.pop("__name__", "unknown")
                        
                        metric_series = MetricSeries(
                            name=metric_name,
                            labels=metric_labels,
                        )
                        
                        if result_type == "vector":
                            # Instant query - single value
                            value_data = item.get("value", [])
                            if len(value_data) >= 2:
                                ts = datetime.fromtimestamp(value_data[0], tz=timezone.utc)
                                metric_series.add_sample(ts, float(value_data[1]))
                                total_samples += 1
                        
                        elif result_type == "matrix":
                            # Range query - multiple values
                            values_data = item.get("values", [])
                            for val in values_data:
                                if len(val) >= 2:
                                    ts = datetime.fromtimestamp(val[0], tz=timezone.utc)
                                    metric_series.add_sample(ts, float(val[1]))
                                    total_samples += 1
                        
                        series.append(metric_series)
                    
                    duration_ms = (time.time() - start_time) * 1000
                    
                    result = CollectionResult(
                        series=series,
                        query=query,
                        duration_ms=duration_ms,
                        samples_count=total_samples,
                        warnings=data.get("warnings", []),
                    )
                    
                    # Update stats
                    self._stats.total_queries += 1
                    self._stats.successful_queries += 1
                    self._stats.total_samples += total_samples
                    self._stats.total_series += len(series)
                    self._stats.total_duration_ms += duration_ms
                    self._stats.last_collection_time = datetime.now(timezone.utc)
                    
                    # Cache result
                    if self.config.enable_caching:
                        await self._cache.set(query, params, result)
                    
                    return result
                    
                except httpx.HTTPStatusError as e:
                    last_error = f"HTTP {e.response.status_code}: {e.response.text}"
                    if e.response.status_code in (429, 500, 502, 503, 504):
                        delay = self.config.retry_base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        break
                        
                except httpx.ConnectError as e:
                    last_error = f"Connection error: {e}"
                    delay = self.config.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    last_error = str(e)
                    break
            
            # All retries failed
            duration_ms = (time.time() - start_time) * 1000
            self._stats.total_queries += 1
            self._stats.failed_queries += 1
            self._stats.total_duration_ms += duration_ms
            self._stats.errors.append(last_error or "Unknown error")
            
            return CollectionResult(
                series=[],
                query=query,
                duration_ms=duration_ms,
                samples_count=0,
                error=last_error,
            )
    
    async def query_instant(
        self,
        query: str,
        time: Optional[datetime] = None,
    ) -> CollectionResult:
        """
        Execute an instant query.
        
        Args:
            query: PromQL query string
            time: Evaluation timestamp (default: now)
        
        Returns:
            CollectionResult with instant values
        """
        params: dict[str, Any] = {"query": query}
        if time:
            params["time"] = time.timestamp()
        
        return await self._execute_query("/api/v1/query", params, query)
    
    async def query_range(
        self,
        query: str,
        start: datetime,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> CollectionResult:
        """
        Execute a range query.
        
        Args:
            query: PromQL query string
            start: Start time
            end: End time (default: now)
            step_seconds: Query resolution step
        
        Returns:
            CollectionResult with time series data
        """
        if end is None:
            end = datetime.now(timezone.utc)
        
        if step_seconds is None:
            # Auto-calculate step to stay within sample limits
            duration = (end - start).total_seconds()
            step_seconds = max(1, int(duration / self.config.max_samples_per_query))
        
        params: dict[str, Any] = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": f"{step_seconds}s",
        }
        
        return await self._execute_query("/api/v1/query_range", params, query)
    
    async def query_batch(
        self,
        queries: list[str],
        time: Optional[datetime] = None,
    ) -> list[CollectionResult]:
        """
        Execute multiple instant queries concurrently.
        
        Args:
            queries: List of PromQL queries
            time: Evaluation timestamp
        
        Returns:
            List of CollectionResults
        """
        tasks = [self.query_instant(q, time) for q in queries]
        return await asyncio.gather(*tasks)
    
    async def query_range_batch(
        self,
        queries: list[str],
        start: datetime,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> list[CollectionResult]:
        """
        Execute multiple range queries concurrently.
        
        Args:
            queries: List of PromQL queries
            start: Start time
            end: End time
            step_seconds: Query resolution step
        
        Returns:
            List of CollectionResults
        """
        tasks = [self.query_range(q, start, end, step_seconds) for q in queries]
        return await asyncio.gather(*tasks)
    
    async def collect_with_adaptive_sampling(
        self,
        queries: list[str],
        duration_seconds: float = 60.0,
        callback: Optional[Callable[[MetricSeries], None]] = None,
    ) -> list[MetricSeries]:
        """
        Collect metrics with adaptive sampling over a duration.
        
        Automatically adjusts sampling frequency based on metric volatility.
        
        Args:
            queries: List of PromQL queries
            duration_seconds: Total collection duration
            callback: Optional callback for each collected series
        
        Returns:
            All collected metric series
        """
        if not self.config.adaptive_sampling_enabled:
            # Fall back to fixed interval
            result = await self.query_batch(queries)
            all_series = []
            for r in result:
                all_series.extend(r.series)
            return all_series
        
        start_time = time.time()
        collected: dict[str, MetricSeries] = {}
        
        while (time.time() - start_time) < duration_seconds:
            current_time = datetime.now(timezone.utc)
            
            for query in queries:
                result = await self.query_instant(query)
                
                for series in result.series:
                    fp = series.fingerprint
                    
                    # Update volatility tracking
                    if series.latest_value is not None:
                        volatility = self._sampler.update_volatility(
                            fp, series.latest_value
                        )
                        interval = self._sampler.get_sampling_interval(fp, volatility)
                        
                        logger.debug(
                            f"Metric {series.name}: volatility={volatility:.3f}, "
                            f"interval={interval:.1f}s"
                        )
                    
                    # Check if we should sample
                    if self._sampler.should_sample(fp, current_time):
                        if fp not in collected:
                            collected[fp] = MetricSeries(
                                name=series.name,
                                labels=series.labels,
                            )
                        
                        if series.latest_value is not None:
                            collected[fp].add_sample(
                                current_time, series.latest_value
                            )
                            
                            # Buffer for later analysis
                            await self._buffer.add(
                                fp,
                                MetricSample(
                                    timestamp=current_time,
                                    value=series.latest_value,
                                ),
                            )
                        
                        if callback:
                            callback(series)
            
            # Sleep for minimum interval
            await asyncio.sleep(self.config.min_sampling_interval)
        
        return list(collected.values())
    
    async def get_labels(
        self,
        match: Optional[list[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[str]:
        """
        Get all label names.
        
        Args:
            match: Optional series selectors
            start: Start time filter
            end: End time filter
        
        Returns:
            List of label names
        """
        client = await self._get_client()
        params: dict[str, Any] = {}
        
        if match:
            params["match[]"] = match
        if start:
            params["start"] = start.timestamp()
        if end:
            params["end"] = end.timestamp()
        
        response = await client.get("/api/v1/labels", params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            return []
        
        return data.get("data", [])
    
    async def get_label_values(
        self,
        label_name: str,
        match: Optional[list[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[str]:
        """
        Get values for a specific label.
        
        Args:
            label_name: Name of the label
            match: Optional series selectors
            start: Start time filter
            end: End time filter
        
        Returns:
            List of label values
        """
        client = await self._get_client()
        params: dict[str, Any] = {}
        
        if match:
            params["match[]"] = match
        if start:
            params["start"] = start.timestamp()
        if end:
            params["end"] = end.timestamp()
        
        response = await client.get(
            f"/api/v1/label/{label_name}/values",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            return []
        
        return data.get("data", [])
    
    async def get_series(
        self,
        match: list[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, str]]:
        """
        Get series matching selectors.
        
        Args:
            match: Series selectors
            start: Start time
            end: End time
        
        Returns:
            List of label sets for matching series
        """
        client = await self._get_client()
        
        params: dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = start.timestamp()
        if end:
            params["end"] = end.timestamp()
        
        response = await client.get("/api/v1/series", params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            return []
        
        return data.get("data", [])
    
    async def get_metadata(
        self,
        metric: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, list[dict[str, str]]]:
        """
        Get metric metadata.
        
        Args:
            metric: Optional metric name filter
            limit: Maximum results per metric
        
        Returns:
            Dictionary mapping metric names to metadata
        """
        client = await self._get_client()
        
        params: dict[str, Any] = {"limit": limit}
        if metric:
            params["metric"] = metric
        
        response = await client.get("/api/v1/metadata", params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            return {}
        
        return data.get("data", {})
    
    @property
    def stats(self) -> CollectionStats:
        """Get collection statistics."""
        return self._stats
    
    @property
    def buffer(self) -> MetricBuffer:
        """Get the metric buffer."""
        return self._buffer
    
    @property
    def sampler(self) -> AdaptiveSampler:
        """Get the adaptive sampler."""
        return self._sampler
    
    async def reset_stats(self) -> None:
        """Reset collection statistics."""
        self._stats = CollectionStats()
        await self._cache.clear()
