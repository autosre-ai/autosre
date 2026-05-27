"""
SRE Agent - Context Gatherer

Collects data from multiple sources to build incident context.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .models import (
    Alert,
    DependencyStatus,
    Deployment,
    GitHubData,
    HealthStatus,
    IncidentContext,
    KubernetesData,
    LogEntry,
    LogPattern,
    LogsData,
    MetricSnapshot,
    PodStatus,
    PrometheusData,
    Severity,
    TrafficData,
)


class ContextGatherer:
    """Gathers context from multiple data sources"""

    def __init__(self, config: dict, mock_data_path: Optional[Path] = None):
        self.config = config
        self.mock_data_path = mock_data_path
        self._mock_data = None

    def _load_mock_data(self) -> dict:
        """Load mock data from file"""
        if self._mock_data is None:
            if self.mock_data_path and self.mock_data_path.exists():
                with open(self.mock_data_path) as f:
                    self._mock_data = json.load(f)
            else:
                self._mock_data = {}
        return self._mock_data

    def gather(self, alert_text: str, service: str) -> IncidentContext:
        """Gather all context for an incident"""

        # Create alert object
        alert = self._create_alert(alert_text, service)

        # Gather from all sources
        prometheus_data = self._gather_prometheus(service)
        github_data = self._gather_github(service)
        logs_data = self._gather_logs(service)
        k8s_data = self._gather_kubernetes(service)
        traffic_data = self._gather_traffic(service)
        dependencies = self._gather_dependencies(service)

        return IncidentContext(
            alert=alert,
            prometheus=prometheus_data,
            github=github_data,
            logs=logs_data,
            kubernetes=k8s_data,
            traffic=traffic_data,
            dependencies=dependencies,
            gathered_at=datetime.now(timezone.utc)
        )

    def _create_alert(self, alert_text: str, service: str) -> Alert:
        """Create alert object from input"""
        mock = self._load_mock_data()

        if mock and "alert" in mock:
            alert_data = mock["alert"]
            return Alert(
                id=alert_data.get("id", "MANUAL-001"),
                source=alert_data.get("source", "manual"),
                severity=Severity(alert_data.get("severity", "high")),
                service=service,
                title=alert_text,
                description=alert_data.get("description", alert_text),
                started_at=datetime.fromisoformat(alert_data["started_at"].replace("Z", "+00:00")),
                labels=alert_data.get("labels", {})
            )

        return Alert(
            id="MANUAL-001",
            source="manual",
            severity=Severity.HIGH,
            service=service,
            title=alert_text,
            description=alert_text,
            started_at=datetime.now(timezone.utc),
            labels={}
        )

    def _gather_prometheus(self, service: str) -> Optional[PrometheusData]:
        """Gather metrics from Prometheus"""
        source_config = self.config.get("sources", {}).get("prometheus", {})

        if not source_config.get("enabled", False):
            return None

        if source_config.get("mode") == "mock":
            return self._mock_prometheus()
        else:
            return self._live_prometheus(service, source_config)

    def _mock_prometheus(self) -> PrometheusData:
        """Return mock Prometheus data"""
        mock = self._load_mock_data()
        prom = mock.get("prometheus", {})

        return PrometheusData(
            error_rate=MetricSnapshot(
                current=prom.get("error_rate", {}).get("current", 0),
                baseline=prom.get("error_rate", {}).get("baseline", 0),
                unit=prom.get("error_rate", {}).get("unit", "percent")
            ),
            request_rate=MetricSnapshot(
                current=prom.get("request_rate", {}).get("current", 0),
                baseline=prom.get("request_rate", {}).get("baseline", 0),
                unit=prom.get("request_rate", {}).get("unit", "req/s")
            ),
            latency_p99=MetricSnapshot(
                current=prom.get("latency_p99", {}).get("current", 0),
                baseline=prom.get("latency_p99", {}).get("baseline", 0),
                unit=prom.get("latency_p99", {}).get("unit", "ms")
            ),
            latency_p50=MetricSnapshot(
                current=prom.get("latency_p50", {}).get("current", 0),
                baseline=prom.get("latency_p50", {}).get("baseline", 0),
                unit=prom.get("latency_p50", {}).get("unit", "ms")
            ),
            error_breakdown=prom.get("error_breakdown", {}),
            time_series=prom.get("time_series", [])
        )

    def _live_prometheus(self, service: str, config: dict) -> Optional[PrometheusData]:
        """Query live Prometheus API for metrics."""
        import os
        import httpx
        
        prometheus_url = config.get("url") or os.environ.get("PROMETHEUS_URL")
        if not prometheus_url:
            raise ValueError(
                "Prometheus URL not configured. Set 'url' in config or PROMETHEUS_URL env var."
            )
        
        prometheus_url = prometheus_url.rstrip("/")
        timeout = config.get("timeout", 30.0)
        auth_token = config.get("auth_token") or os.environ.get("PROMETHEUS_TOKEN")
        
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        def query_prometheus(promql: str) -> Optional[float]:
            """Execute a PromQL query and return the first result value."""
            try:
                with httpx.Client(timeout=timeout, headers=headers) as client:
                    resp = client.get(
                        f"{prometheus_url}/api/v1/query",
                        params={"query": promql}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if data.get("status") != "success":
                        return None
                    
                    results = data.get("data", {}).get("result", [])
                    if not results:
                        return None
                    
                    # Get value from first result
                    value = results[0].get("value", [None, None])
                    if len(value) >= 2:
                        v = float(value[1])
                        return None if v != v else v  # NaN check
                    return None
            except Exception:
                return None
        
        # Query error rate (5xx / total)
        error_rate_current = query_prometheus(
            f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / '
            f'sum(rate(http_requests_total{{service="{service}"}}[5m]))'
        )
        error_rate_baseline = query_prometheus(
            f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[1h] offset 1d)) / '
            f'sum(rate(http_requests_total{{service="{service}"}}[1h] offset 1d))'
        )
        
        # Query request rate
        request_rate_current = query_prometheus(
            f'sum(rate(http_requests_total{{service="{service}"}}[5m]))'
        )
        request_rate_baseline = query_prometheus(
            f'sum(rate(http_requests_total{{service="{service}"}}[1h] offset 1d))'
        )
        
        # Query latency p99 (using histogram_quantile, NEVER avg)
        latency_p99_current = query_prometheus(
            f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le))'
        )
        latency_p99_baseline = query_prometheus(
            f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[1h] offset 1d)) by (le))'
        )
        
        # Query latency p50
        latency_p50_current = query_prometheus(
            f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le))'
        )
        latency_p50_baseline = query_prometheus(
            f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[1h] offset 1d)) by (le))'
        )
        
        # Convert latency from seconds to milliseconds
        if latency_p99_current is not None:
            latency_p99_current *= 1000
        if latency_p99_baseline is not None:
            latency_p99_baseline *= 1000
        if latency_p50_current is not None:
            latency_p50_current *= 1000
        if latency_p50_baseline is not None:
            latency_p50_baseline *= 1000
        
        # Convert error rate to percentage
        if error_rate_current is not None:
            error_rate_current *= 100
        if error_rate_baseline is not None:
            error_rate_baseline *= 100
        
        return PrometheusData(
            error_rate=MetricSnapshot(
                current=error_rate_current or 0,
                baseline=error_rate_baseline or 0,
                unit="percent"
            ),
            request_rate=MetricSnapshot(
                current=request_rate_current or 0,
                baseline=request_rate_baseline or 0,
                unit="req/s"
            ),
            latency_p99=MetricSnapshot(
                current=latency_p99_current or 0,
                baseline=latency_p99_baseline or 0,
                unit="ms"
            ),
            latency_p50=MetricSnapshot(
                current=latency_p50_current or 0,
                baseline=latency_p50_baseline or 0,
                unit="ms"
            ),
            error_breakdown={},
            time_series=[]
        )

    def _gather_github(self, service: str) -> Optional[GitHubData]:
        """Gather deployment info from GitHub"""
        source_config = self.config.get("sources", {}).get("github", {})

        if not source_config.get("enabled", False):
            return None

        if source_config.get("mode") == "mock":
            return self._mock_github()
        else:
            return self._live_github(service, source_config)

    def _mock_github(self) -> GitHubData:
        """Return mock GitHub data"""
        mock = self._load_mock_data()
        gh = mock.get("github", {})

        deployments = []
        for dep in gh.get("recent_deployments", []):
            deployments.append(Deployment(
                sha=dep["sha"],
                short_sha=dep["short_sha"],
                author=dep["author"],
                message=dep["message"],
                deployed_at=datetime.fromisoformat(dep["deployed_at"].replace("Z", "+00:00")),
                hours_ago=dep["hours_ago"],
                files_changed=dep.get("files_changed", []),
                additions=dep.get("additions", 0),
                deletions=dep.get("deletions", 0)
            ))

        return GitHubData(
            recent_deployments=deployments,
            open_prs=gh.get("open_prs", [])
        )

    def _live_github(self, service: str, config: dict) -> Optional[GitHubData]:
        """Query live GitHub API for deployment info."""
        import os
        import httpx
        
        github_token = config.get("token") or os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise ValueError(
                "GitHub token not configured. Set 'token' in config or GITHUB_TOKEN env var."
            )
        
        repo = config.get("repo") or os.environ.get("GITHUB_REPO")
        if not repo:
            raise ValueError(
                "GitHub repo not configured. Set 'repo' in config (owner/repo format) or GITHUB_REPO env var."
            )
        
        api_url = config.get("api_url", "https://api.github.com")
        timeout = config.get("timeout", 30.0)
        
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        deployments = []
        open_prs = []
        
        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                # Get recent commits (as a proxy for deployments)
                resp = client.get(
                    f"{api_url}/repos/{repo}/commits",
                    params={"per_page": 10}
                )
                
                if resp.status_code == 200:
                    commits = resp.json()
                    now = datetime.now(timezone.utc)
                    
                    for commit in commits:
                        commit_sha = commit.get("sha", "")
                        commit_data = commit.get("commit", {})
                        author_data = commit.get("author", {}) or {}
                        
                        # Get commit details for files changed
                        detail_resp = client.get(f"{api_url}/repos/{repo}/commits/{commit_sha}")
                        files_changed = []
                        additions = 0
                        deletions = 0
                        
                        if detail_resp.status_code == 200:
                            detail = detail_resp.json()
                            files_changed = [f.get("filename", "") for f in detail.get("files", [])]
                            stats = detail.get("stats", {})
                            additions = stats.get("additions", 0)
                            deletions = stats.get("deletions", 0)
                        
                        # Parse commit date
                        commit_date_str = commit_data.get("committer", {}).get("date", "")
                        if commit_date_str:
                            deployed_at = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
                            hours_ago = (now - deployed_at).total_seconds() / 3600
                        else:
                            deployed_at = now
                            hours_ago = 0
                        
                        deployments.append(Deployment(
                            sha=commit_sha,
                            short_sha=commit_sha[:7],
                            author=author_data.get("login", commit_data.get("author", {}).get("name", "unknown")),
                            message=commit_data.get("message", "").split("\n")[0],
                            deployed_at=deployed_at,
                            hours_ago=round(hours_ago, 1),
                            files_changed=files_changed[:10],  # Limit to first 10 files
                            additions=additions,
                            deletions=deletions,
                        ))
                
                # Get open pull requests
                pr_resp = client.get(
                    f"{api_url}/repos/{repo}/pulls",
                    params={"state": "open", "per_page": 10}
                )
                
                if pr_resp.status_code == 200:
                    prs = pr_resp.json()
                    for pr in prs:
                        open_prs.append({
                            "number": pr.get("number"),
                            "title": pr.get("title", ""),
                            "author": pr.get("user", {}).get("login", "unknown"),
                            "created_at": pr.get("created_at"),
                        })
        
        except Exception as e:
            # Log the error but return partial data
            import logging
            logging.warning(f"Error fetching GitHub data: {e}")
        
        return GitHubData(
            recent_deployments=deployments,
            open_prs=open_prs,
        )

    def _gather_logs(self, service: str) -> Optional[LogsData]:
        """Gather error logs"""
        source_config = self.config.get("sources", {}).get("logs", {})

        if not source_config.get("enabled", False):
            return None

        if source_config.get("mode") == "mock":
            return self._mock_logs()
        else:
            return self._live_logs(service, source_config)

    def _mock_logs(self) -> LogsData:
        """Return mock log data"""
        mock = self._load_mock_data()
        logs = mock.get("logs", {})

        error_samples = []
        for entry in logs.get("error_samples", []):
            error_samples.append(LogEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")),
                level=entry["level"],
                message=entry["message"],
                trace_id=entry.get("trace_id"),
                count=entry.get("count", 1)
            ))

        error_patterns = []
        for pattern in logs.get("error_patterns", []):
            error_patterns.append(LogPattern(
                pattern=pattern["pattern"],
                count=pattern["count"],
                percentage=pattern["percentage"]
            ))

        first_error = None
        if logs.get("first_error_at"):
            first_error = datetime.fromisoformat(logs["first_error_at"].replace("Z", "+00:00"))

        return LogsData(
            error_samples=error_samples,
            error_patterns=error_patterns,
            first_error_at=first_error,
            total_errors_last_5m=logs.get("total_errors_last_5m", 0)
        )

    def _live_logs(self, service: str, config: dict) -> Optional[LogsData]:
        """Query live log aggregator (Loki, Elasticsearch, or CloudWatch)."""
        import os
        
        log_provider = config.get("provider") or os.environ.get("LOG_PROVIDER", "loki")
        
        if log_provider == "loki":
            return self._query_loki(service, config)
        elif log_provider == "elasticsearch":
            return self._query_elasticsearch(service, config)
        elif log_provider == "cloudwatch":
            return self._query_cloudwatch(service, config)
        else:
            raise ValueError(
                f"Unknown log provider: {log_provider}. Supported: loki, elasticsearch, cloudwatch"
            )
    
    def _query_loki(self, service: str, config: dict) -> Optional[LogsData]:
        """Query Grafana Loki for logs."""
        import os
        import httpx
        from collections import Counter
        
        loki_url = config.get("url") or os.environ.get("LOKI_URL")
        if not loki_url:
            raise ValueError(
                "Loki URL not configured. Set 'url' in config or LOKI_URL env var."
            )
        
        loki_url = loki_url.rstrip("/")
        timeout = config.get("timeout", 30.0)
        auth_token = config.get("auth_token") or os.environ.get("LOKI_TOKEN")
        
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        error_samples = []
        error_patterns: Counter = Counter()
        first_error_at = None
        total_errors = 0
        
        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                # Query for error logs in the last 5 minutes
                query = f'{{service="{service}"}} |= "error" or |= "ERROR" or |= "Error"'
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(minutes=5)
                
                resp = client.get(
                    f"{loki_url}/loki/api/v1/query_range",
                    params={
                        "query": query,
                        "start": int(start_time.timestamp() * 1e9),  # nanoseconds
                        "end": int(end_time.timestamp() * 1e9),
                        "limit": 100,
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    streams = data.get("data", {}).get("result", [])
                    
                    for stream in streams:
                        for entry in stream.get("values", []):
                            ts_ns, log_line = entry
                            ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
                            
                            if first_error_at is None or ts < first_error_at:
                                first_error_at = ts
                            
                            total_errors += 1
                            
                            # Sample first 10 errors
                            if len(error_samples) < 10:
                                error_samples.append(LogEntry(
                                    timestamp=ts,
                                    level="error",
                                    message=log_line[:500],  # Truncate long messages
                                    trace_id=None,
                                    count=1,
                                ))
                            
                            # Extract error pattern (first 100 chars normalized)
                            pattern = log_line[:100].strip()
                            error_patterns[pattern] += 1
        
        except Exception as e:
            import logging
            logging.warning(f"Error querying Loki: {e}")
        
        # Convert patterns to LogPattern objects
        patterns_list = []
        for pattern, count in error_patterns.most_common(5):
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            patterns_list.append(LogPattern(
                pattern=pattern,
                count=count,
                percentage=round(percentage, 1),
            ))
        
        return LogsData(
            error_samples=error_samples,
            error_patterns=patterns_list,
            first_error_at=first_error_at,
            total_errors_last_5m=total_errors,
        )
    
    def _query_elasticsearch(self, service: str, config: dict) -> Optional[LogsData]:
        """Query Elasticsearch for logs."""
        import os
        import httpx
        from collections import Counter
        
        es_url = config.get("url") or os.environ.get("ELASTICSEARCH_URL")
        if not es_url:
            raise ValueError(
                "Elasticsearch URL not configured. Set 'url' in config or ELASTICSEARCH_URL env var."
            )
        
        es_url = es_url.rstrip("/")
        index = config.get("index", "logs-*")
        timeout = config.get("timeout", 30.0)
        
        # Authentication
        auth = None
        es_user = config.get("username") or os.environ.get("ELASTICSEARCH_USER")
        es_pass = config.get("password") or os.environ.get("ELASTICSEARCH_PASSWORD")
        if es_user and es_pass:
            auth = (es_user, es_pass)
        
        api_key = config.get("api_key") or os.environ.get("ELASTICSEARCH_API_KEY")
        headers = {}
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"
        
        error_samples = []
        error_patterns: Counter = Counter()
        first_error_at = None
        total_errors = 0
        
        try:
            with httpx.Client(timeout=timeout, headers=headers, auth=auth) as client:
                # Search for error logs
                query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"service.keyword": service}},
                                {"range": {"@timestamp": {"gte": "now-5m"}}},
                            ],
                            "should": [
                                {"match": {"level": "error"}},
                                {"match": {"message": "error"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    "size": 100,
                    "sort": [{"@timestamp": "asc"}],
                }
                
                resp = client.post(
                    f"{es_url}/{index}/_search",
                    json=query,
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    total_errors = data.get("hits", {}).get("total", {}).get("value", len(hits))
                    
                    for hit in hits:
                        source = hit.get("_source", {})
                        ts_str = source.get("@timestamp", "")
                        
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        except ValueError:
                            ts = datetime.now(timezone.utc)
                        
                        if first_error_at is None or ts < first_error_at:
                            first_error_at = ts
                        
                        message = source.get("message", "")
                        
                        if len(error_samples) < 10:
                            error_samples.append(LogEntry(
                                timestamp=ts,
                                level=source.get("level", "error"),
                                message=message[:500],
                                trace_id=source.get("trace_id"),
                                count=1,
                            ))
                        
                        pattern = message[:100].strip()
                        error_patterns[pattern] += 1
        
        except Exception as e:
            import logging
            logging.warning(f"Error querying Elasticsearch: {e}")
        
        patterns_list = []
        for pattern, count in error_patterns.most_common(5):
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            patterns_list.append(LogPattern(
                pattern=pattern,
                count=count,
                percentage=round(percentage, 1),
            ))
        
        return LogsData(
            error_samples=error_samples,
            error_patterns=patterns_list,
            first_error_at=first_error_at,
            total_errors_last_5m=total_errors,
        )
    
    def _query_cloudwatch(self, service: str, config: dict) -> Optional[LogsData]:
        """Query AWS CloudWatch Logs."""
        import os
        from collections import Counter
        
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for CloudWatch logs. Install with: pip install boto3"
            )
        
        log_group = config.get("log_group") or os.environ.get("CLOUDWATCH_LOG_GROUP")
        if not log_group:
            raise ValueError(
                "CloudWatch log group not configured. Set 'log_group' in config or CLOUDWATCH_LOG_GROUP env var."
            )
        
        region = config.get("region") or os.environ.get("AWS_REGION", "us-east-1")
        
        client = boto3.client("logs", region_name=region)
        
        error_samples = []
        error_patterns: Counter = Counter()
        first_error_at = None
        total_errors = 0
        
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=5)
            
            # Use filter_log_events to search for errors
            response = client.filter_log_events(
                logGroupName=log_group,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                filterPattern=f'?ERROR ?Error ?error "{service}"',
                limit=100,
            )
            
            events = response.get("events", [])
            total_errors = len(events)
            
            for event in events:
                ts = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc)
                message = event.get("message", "")
                
                if first_error_at is None or ts < first_error_at:
                    first_error_at = ts
                
                if len(error_samples) < 10:
                    error_samples.append(LogEntry(
                        timestamp=ts,
                        level="error",
                        message=message[:500],
                        trace_id=None,
                        count=1,
                    ))
                
                pattern = message[:100].strip()
                error_patterns[pattern] += 1
        
        except Exception as e:
            import logging
            logging.warning(f"Error querying CloudWatch: {e}")
        
        patterns_list = []
        for pattern, count in error_patterns.most_common(5):
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            patterns_list.append(LogPattern(
                pattern=pattern,
                count=count,
                percentage=round(percentage, 1),
            ))
        
        return LogsData(
            error_samples=error_samples,
            error_patterns=patterns_list,
            first_error_at=first_error_at,
            total_errors_last_5m=total_errors,
        )

    def _gather_kubernetes(self, service: str) -> Optional[KubernetesData]:
        """Gather Kubernetes/OpenShift status"""
        source_config = self.config.get("sources", {}).get("kubernetes", {})

        if not source_config.get("enabled", False):
            return None

        if source_config.get("mode") == "mock":
            return self._mock_kubernetes()
        else:
            return self._live_kubernetes(service, source_config)

    def _mock_kubernetes(self) -> KubernetesData:
        """Return mock Kubernetes data"""
        mock = self._load_mock_data()
        k8s = mock.get("kubernetes", {})

        pods = []
        for pod in k8s.get("pods", []):
            pods.append(PodStatus(
                name=pod["name"],
                status=pod["status"],
                restarts=pod["restarts"],
                cpu_usage=pod["cpu_usage"],
                cpu_limit=pod["cpu_limit"],
                memory_usage=pod["memory_usage"],
                memory_limit=pod["memory_limit"],
                ready=pod["ready"]
            ))

        return KubernetesData(
            pods=pods,
            replica_count=k8s.get("replica_count", {}),
            recent_events=k8s.get("recent_events", []),
            resource_pressure=k8s.get("resource_pressure", False)
        )

    def _live_kubernetes(self, service: str, config: dict) -> Optional[KubernetesData]:
        """Query live Kubernetes API for service status."""
        import os
        
        try:
            from kubernetes import client, config as k8s_config
        except ImportError:
            raise ImportError(
                "kubernetes package is required. Install with: pip install kubernetes"
            )
        
        # Load kubeconfig
        kubeconfig_path = config.get("kubeconfig") or os.environ.get("KUBECONFIG")
        context = config.get("context") or os.environ.get("KUBE_CONTEXT")
        namespace = config.get("namespace") or os.environ.get("KUBE_NAMESPACE", "default")
        
        try:
            if kubeconfig_path:
                k8s_config.load_kube_config(config_file=kubeconfig_path, context=context)
            else:
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config(context=context)
        except Exception as e:
            raise ValueError(f"Failed to load Kubernetes config: {e}")
        
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
        
        pods = []
        replica_count = {}
        recent_events = []
        resource_pressure = False
        
        try:
            # Get pods for this service (by label selector)
            label_selector = f"app={service}"
            pod_list = v1.list_namespaced_pod(namespace, label_selector=label_selector)
            
            for pod in pod_list.items:
                # Calculate resource usage from container specs
                cpu_usage = 0.0
                cpu_limit = 0.0
                memory_usage = 0
                memory_limit = 0
                
                if pod.spec.containers:
                    for container in pod.spec.containers:
                        if container.resources:
                            if container.resources.requests:
                                cpu_req = container.resources.requests.get("cpu", "0")
                                mem_req = container.resources.requests.get("memory", "0")
                                cpu_usage += self._parse_cpu(cpu_req)
                                memory_usage += self._parse_memory(mem_req)
                            if container.resources.limits:
                                cpu_lim = container.resources.limits.get("cpu", "0")
                                mem_lim = container.resources.limits.get("memory", "0")
                                cpu_limit += self._parse_cpu(cpu_lim)
                                memory_limit += self._parse_memory(mem_lim)
                
                # Get restart count
                restarts = 0
                if pod.status.container_statuses:
                    for cs in pod.status.container_statuses:
                        restarts += cs.restart_count
                
                # Check if pod is ready
                ready = False
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            ready = True
                            break
                
                pods.append(PodStatus(
                    name=pod.metadata.name,
                    status=pod.status.phase,
                    restarts=restarts,
                    cpu_usage=f"{cpu_usage:.2f}",
                    cpu_limit=f"{cpu_limit:.2f}",
                    memory_usage=f"{memory_usage}Mi",
                    memory_limit=f"{memory_limit}Mi",
                    ready=ready,
                ))
                
                # Check for resource pressure
                if cpu_limit > 0 and cpu_usage / cpu_limit > 0.9:
                    resource_pressure = True
                if memory_limit > 0 and memory_usage / memory_limit > 0.9:
                    resource_pressure = True
            
            # Get deployment replica count
            try:
                deployment = apps_v1.read_namespaced_deployment(service, namespace)
                replica_count = {
                    "desired": deployment.spec.replicas or 0,
                    "current": deployment.status.replicas or 0,
                    "ready": deployment.status.ready_replicas or 0,
                    "available": deployment.status.available_replicas or 0,
                }
            except client.exceptions.ApiException:
                # May not be a deployment, try statefulset
                try:
                    sts = apps_v1.read_namespaced_stateful_set(service, namespace)
                    replica_count = {
                        "desired": sts.spec.replicas or 0,
                        "current": sts.status.replicas or 0,
                        "ready": sts.status.ready_replicas or 0,
                        "available": sts.status.ready_replicas or 0,
                    }
                except client.exceptions.ApiException:
                    pass
            
            # Get recent events for this service
            events = v1.list_namespaced_event(
                namespace,
                field_selector=f"involvedObject.name={service}"
            )
            
            for event in events.items[:10]:  # Last 10 events
                recent_events.append(
                    f"{event.reason}: {event.message}"
                )
        
        except Exception as e:
            import logging
            logging.warning(f"Error querying Kubernetes: {e}")
        
        return KubernetesData(
            pods=pods,
            replica_count=replica_count,
            recent_events=recent_events,
            resource_pressure=resource_pressure,
        )
    
    def _parse_cpu(self, cpu_str: str) -> float:
        """Parse Kubernetes CPU string to cores."""
        if not cpu_str:
            return 0.0
        cpu_str = str(cpu_str)
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1000
        return float(cpu_str)
    
    def _parse_memory(self, mem_str: str) -> int:
        """Parse Kubernetes memory string to Mi."""
        if not mem_str:
            return 0
        mem_str = str(mem_str)
        if mem_str.endswith("Gi"):
            return int(float(mem_str[:-2]) * 1024)
        if mem_str.endswith("Mi"):
            return int(float(mem_str[:-2]))
        if mem_str.endswith("Ki"):
            return int(float(mem_str[:-2]) / 1024)
        if mem_str.endswith("G"):
            return int(float(mem_str[:-1]) * 1024)
        if mem_str.endswith("M"):
            return int(float(mem_str[:-1]))
        if mem_str.endswith("K"):
            return int(float(mem_str[:-1]) / 1024)
        # Assume bytes
        try:
            return int(float(mem_str) / (1024 * 1024))
        except ValueError:
            return 0

    def _gather_traffic(self, service: str) -> Optional[TrafficData]:
        """Gather traffic analysis data"""
        mock = self._load_mock_data()
        traffic = mock.get("traffic", {})

        return TrafficData(
            suspicious_ips=traffic.get("suspicious_ips", []),
            geo_distribution=traffic.get("geo_distribution", {}),
            is_ddos=traffic.get("is_ddos", False),
            is_malicious=traffic.get("is_malicious", False),
            akamai_status=traffic.get("akamai_status", "unknown")
        )

    def _gather_dependencies(self, service: str) -> list[DependencyStatus]:
        """Gather dependency health status"""
        mock = self._load_mock_data()
        deps_data = mock.get("dependencies", {})

        dependencies = []
        for name, dep in deps_data.items():
            last_healthy = None
            if dep.get("last_healthy"):
                last_healthy = datetime.fromisoformat(dep["last_healthy"].replace("Z", "+00:00"))

            dependencies.append(DependencyStatus(
                name=name,
                status=HealthStatus(dep.get("status", "unknown")),
                latency_p99=dep.get("latency_p99", 0),
                error_rate=dep.get("error_rate", 0),
                last_healthy=last_healthy
            ))

        return dependencies
