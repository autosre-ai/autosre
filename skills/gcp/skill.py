"""
GCP Cloud Provider Skill for OpenSRE

Provides actions for Compute Engine, GKE, Cloud Run, Monitoring, Logging, and BigQuery.
Uses google-cloud SDK with async wrappers for non-blocking operations.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

from google.api_core import exceptions as gcp_exceptions
from google.auth import default as google_default_auth
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery, compute_v1, container_v1, monitoring_v3
from google.cloud import logging as cloud_logging
from google.cloud.run_v2 import ServicesClient, TrafficTarget
from google.oauth2 import service_account

try:
    from opensre.core.exceptions import SkillExecutionError
except ImportError:
    # Fallback for standalone skill usage
    class SkillExecutionError(Exception):
        """Raised when a skill method fails during execution."""
        def __init__(self, skill_name: str, method: str, reason: str):
            self.skill_name = skill_name
            self.method = method
            self.reason = reason
            super().__init__(f"Skill '{skill_name}.{method}' failed: {reason}")


logger = logging.getLogger(__name__)


@dataclass
class GCEInstance:
    """Represents a GCE VM instance."""
    name: str
    zone: str
    machine_type: str
    status: str
    internal_ip: str | None
    external_ip: str | None
    creation_timestamp: str | None
    labels: dict[str, str] = field(default_factory=dict)
    network_tags: list[str] = field(default_factory=list)


@dataclass
class GKECluster:
    """Represents a GKE cluster."""
    name: str
    location: str
    status: str
    node_count: int
    kubernetes_version: str
    endpoint: str | None
    autopilot: bool = False
    node_pools: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CloudRunService:
    """Represents a Cloud Run service."""
    name: str
    region: str
    uri: str | None
    latest_revision: str | None
    traffic: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MetricDataPoint:
    """Represents a monitoring metric data point."""
    timestamp: datetime
    value: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class LogEntry:
    """Represents a log entry."""
    timestamp: datetime
    severity: str
    message: str
    resource: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class BigQueryResult:
    """Represents BigQuery query results."""
    total_rows: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    schema: list[dict[str, str]] = field(default_factory=list)
    job_id: str | None = None


class GCPSkill:
    """
    GCP Cloud Provider Skill.

    Provides async methods for interacting with GCP services:
    - Compute Engine: List, start, stop instances
    - GKE: List clusters, get cluster details
    - Cloud Run: List services, update traffic
    - Monitoring: Run MQL queries
    - Logging: Query logs
    - BigQuery: Execute SQL queries
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize GCP Skill.

        Args:
            config: Configuration dict with credentials and settings.
                   If not provided, uses application default credentials.
        """
        self.config = config or {}
        self._credentials = None
        self._project = self.config.get('project')
        self._region = self.config.get('region', 'us-central1')
        self._zone = self.config.get('zone', 'us-central1-a')
        self._max_retries = self.config.get('max_retries', 3)
        self._retry_delay = self.config.get('retry_delay', 1.0)
        self._timeout = self.config.get('timeout', 60)

        # Initialize credentials
        self._init_credentials()

    def _init_credentials(self):
        """Initialize GCP credentials."""
        try:
            if self.config.get('credentials_file'):
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.config['credentials_file']
                )
                # Get project from credentials if not set
                if not self._project:
                    with open(self.config['credentials_file']) as f:
                        creds_data = json.load(f)
                        self._project = creds_data.get('project_id')

            elif self.config.get('credentials_json'):
                creds_data = json.loads(self.config['credentials_json'])
                self._credentials = service_account.Credentials.from_service_account_info(
                    creds_data
                )
                if not self._project:
                    self._project = creds_data.get('project_id')
            else:
                # Use application default credentials
                self._credentials, project = google_default_auth()
                if not self._project:
                    self._project = project

        except GoogleAuthError as e:
            logger.warning(f"Failed to initialize GCP credentials: {e}")

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def _retry_with_backoff(
        self,
        operation: str,
        func,
        *args,
        max_retries: int | None = None,
        **kwargs
    ) -> Any:
        """
        Execute an operation with exponential backoff retry.

        Args:
            operation: Name of the operation (for logging)
            func: Callable to execute
            max_retries: Override default max retries
        """
        retries = max_retries or self._max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                return await self._run_sync(func, *args, **kwargs)
            except gcp_exceptions.NotFound as e:
                raise SkillExecutionError(
                    skill_name='gcp',
                    method=operation,
                    reason=f"Resource not found: {e}"
                )
            except gcp_exceptions.PermissionDenied as e:
                raise SkillExecutionError(
                    skill_name='gcp',
                    method=operation,
                    reason=f"Permission denied: {e}"
                )
            except gcp_exceptions.InvalidArgument as e:
                raise SkillExecutionError(
                    skill_name='gcp',
                    method=operation,
                    reason=f"Invalid argument: {e}"
                )
            except (gcp_exceptions.ServiceUnavailable,
                    gcp_exceptions.DeadlineExceeded,
                    gcp_exceptions.ResourceExhausted) as e:
                last_error = e
                if attempt < retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"GCP {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"GCP {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise SkillExecutionError(
            skill_name='gcp',
            method=operation,
            reason=f"Failed after {retries + 1} attempts: {last_error}"
        )

    # =========================================================================
    # Compute Engine Operations
    # =========================================================================

    async def gce_list_instances(
        self,
        project: str | None = None,
        zone: str | None = None
    ) -> list[GCEInstance]:
        """
        List GCE VM instances.

        Args:
            project: GCP project ID (defaults to configured project)
            zone: GCP zone (defaults to configured zone, or all zones if '-')

        Returns:
            List of GCEInstance dataclass objects
        """
        project = project or self._project
        zone = zone or self._zone

        if not project:
            raise SkillExecutionError(
                skill_name='gcp',
                method='gce_list_instances',
                reason='No project specified'
            )

        def _list():
            client = compute_v1.InstancesClient(credentials=self._credentials)
            instances = []

            if zone == '-':
                # List all zones
                request = compute_v1.AggregatedListInstancesRequest(project=project)
                for zone_name, response in client.aggregated_list(request=request):
                    if response.instances:
                        for instance in response.instances:
                            instances.append(self._parse_gce_instance(instance, zone_name.replace('zones/', '')))
            else:
                request = compute_v1.ListInstancesRequest(project=project, zone=zone)
                for instance in client.list(request=request):
                    instances.append(self._parse_gce_instance(instance, zone))

            return instances

        return await self._retry_with_backoff('gce_list_instances', _list)

    def _parse_gce_instance(self, instance, zone: str) -> GCEInstance:
        """Parse a GCE instance proto to dataclass."""
        # Extract IPs
        internal_ip = None
        external_ip = None

        for interface in instance.network_interfaces:
            if interface.network_i_p:
                internal_ip = interface.network_i_p
            for access_config in interface.access_configs:
                if access_config.nat_i_p:
                    external_ip = access_config.nat_i_p

        return GCEInstance(
            name=instance.name,
            zone=zone,
            machine_type=instance.machine_type.split('/')[-1] if instance.machine_type else '',
            status=instance.status,
            internal_ip=internal_ip,
            external_ip=external_ip,
            creation_timestamp=instance.creation_timestamp,
            labels=dict(instance.labels) if instance.labels else {},
            network_tags=list(instance.tags.items) if instance.tags else []
        )

    async def gce_start_instance(
        self,
        project: str | None = None,
        zone: str | None = None,
        instance: str = ''
    ) -> dict[str, Any]:
        """
        Start a GCE VM instance.

        Args:
            project: GCP project ID
            zone: GCP zone
            instance: Instance name

        Returns:
            Dict with operation result
        """
        project = project or self._project
        zone = zone or self._zone

        if not project or not instance:
            raise SkillExecutionError(
                skill_name='gcp',
                method='gce_start_instance',
                reason='Project and instance name required'
            )

        def _start():
            client = compute_v1.InstancesClient(credentials=self._credentials)
            operation = client.start(project=project, zone=zone, instance=instance)

            # Wait for operation to complete
            operation_client = compute_v1.ZoneOperationsClient(credentials=self._credentials)
            while operation.status != compute_v1.Operation.Status.DONE:
                operation = operation_client.get(
                    project=project, zone=zone, operation=operation.name
                )

            return {
                'instance': instance,
                'zone': zone,
                'operation': operation.name,
                'status': 'DONE' if operation.status == compute_v1.Operation.Status.DONE else 'PENDING',
                'success': operation.error is None
            }

        return await self._retry_with_backoff('gce_start_instance', _start)

    async def gce_stop_instance(
        self,
        project: str | None = None,
        zone: str | None = None,
        instance: str = ''
    ) -> dict[str, Any]:
        """
        Stop a GCE VM instance.

        Args:
            project: GCP project ID
            zone: GCP zone
            instance: Instance name

        Returns:
            Dict with operation result
        """
        project = project or self._project
        zone = zone or self._zone

        if not project or not instance:
            raise SkillExecutionError(
                skill_name='gcp',
                method='gce_stop_instance',
                reason='Project and instance name required'
            )

        def _stop():
            client = compute_v1.InstancesClient(credentials=self._credentials)
            operation = client.stop(project=project, zone=zone, instance=instance)

            # Wait for operation to complete
            operation_client = compute_v1.ZoneOperationsClient(credentials=self._credentials)
            while operation.status != compute_v1.Operation.Status.DONE:
                operation = operation_client.get(
                    project=project, zone=zone, operation=operation.name
                )

            return {
                'instance': instance,
                'zone': zone,
                'operation': operation.name,
                'status': 'DONE' if operation.status == compute_v1.Operation.Status.DONE else 'PENDING',
                'success': operation.error is None
            }

        return await self._retry_with_backoff('gce_stop_instance', _stop)

    # =========================================================================
    # GKE Operations
    # =========================================================================

    async def gke_list_clusters(
        self,
        project: str | None = None,
        location: str = '-'
    ) -> list[GKECluster]:
        """
        List GKE clusters.

        Args:
            project: GCP project ID
            location: Region/zone, or '-' for all locations

        Returns:
            List of GKECluster dataclass objects
        """
        project = project or self._project

        if not project:
            raise SkillExecutionError(
                skill_name='gcp',
                method='gke_list_clusters',
                reason='No project specified'
            )

        def _list():
            client = container_v1.ClusterManagerClient(credentials=self._credentials)
            parent = f"projects/{project}/locations/{location}"

            response = client.list_clusters(parent=parent)
            clusters = []

            for cluster in response.clusters:
                node_count = sum(
                    pool.initial_node_count or 0
                    for pool in cluster.node_pools
                )

                clusters.append(GKECluster(
                    name=cluster.name,
                    location=cluster.location,
                    status=container_v1.Cluster.Status(cluster.status).name,
                    node_count=node_count,
                    kubernetes_version=cluster.current_master_version,
                    endpoint=cluster.endpoint,
                    autopilot=cluster.autopilot.enabled if cluster.autopilot else False,
                    node_pools=[
                        {
                            'name': pool.name,
                            'machine_type': pool.config.machine_type if pool.config else None,
                            'node_count': pool.initial_node_count
                        }
                        for pool in cluster.node_pools
                    ]
                ))

            return clusters

        return await self._retry_with_backoff('gke_list_clusters', _list)

    async def gke_get_cluster(
        self,
        project: str | None = None,
        location: str | None = None,
        cluster: str = ''
    ) -> GKECluster | None:
        """
        Get details of a specific GKE cluster.

        Args:
            project: GCP project ID
            location: Cluster location (region or zone)
            cluster: Cluster name

        Returns:
            GKECluster dataclass or None if not found
        """
        project = project or self._project
        location = location or self._region

        if not project or not cluster:
            raise SkillExecutionError(
                skill_name='gcp',
                method='gke_get_cluster',
                reason='Project and cluster name required'
            )

        def _get():
            client = container_v1.ClusterManagerClient(credentials=self._credentials)
            name = f"projects/{project}/locations/{location}/clusters/{cluster}"

            try:
                c = client.get_cluster(name=name)
            except gcp_exceptions.NotFound:
                return None

            node_count = sum(
                pool.initial_node_count or 0
                for pool in c.node_pools
            )

            return GKECluster(
                name=c.name,
                location=c.location,
                status=container_v1.Cluster.Status(c.status).name,
                node_count=node_count,
                kubernetes_version=c.current_master_version,
                endpoint=c.endpoint,
                autopilot=c.autopilot.enabled if c.autopilot else False,
                node_pools=[
                    {
                        'name': pool.name,
                        'machine_type': pool.config.machine_type if pool.config else None,
                        'node_count': pool.initial_node_count,
                        'autoscaling': {
                            'enabled': pool.autoscaling.enabled if pool.autoscaling else False,
                            'min': pool.autoscaling.min_node_count if pool.autoscaling else 0,
                            'max': pool.autoscaling.max_node_count if pool.autoscaling else 0
                        }
                    }
                    for pool in c.node_pools
                ]
            )

        return await self._retry_with_backoff('gke_get_cluster', _get)

    # =========================================================================
    # Cloud Run Operations
    # =========================================================================

    async def cloud_run_list_services(
        self,
        project: str | None = None,
        region: str | None = None
    ) -> list[CloudRunService]:
        """
        List Cloud Run services.

        Args:
            project: GCP project ID
            region: Region (defaults to configured region)

        Returns:
            List of CloudRunService dataclass objects
        """
        project = project or self._project
        region = region or self._region

        if not project:
            raise SkillExecutionError(
                skill_name='gcp',
                method='cloud_run_list_services',
                reason='No project specified'
            )

        def _list():
            client = ServicesClient(credentials=self._credentials)
            parent = f"projects/{project}/locations/{region}"

            services = []
            for service in client.list_services(parent=parent):
                traffic = []
                if service.traffic:
                    for t in service.traffic:
                        traffic.append({
                            'revision': t.revision,
                            'percent': t.percent,
                            'type': t.type_.name if t.type_ else None
                        })

                conditions = []
                if service.conditions:
                    for c in service.conditions:
                        conditions.append({
                            'type': c.type_,
                            'state': c.state.name if c.state else None,
                            'message': c.message
                        })

                services.append(CloudRunService(
                    name=service.name.split('/')[-1],
                    region=region,
                    uri=service.uri,
                    latest_revision=service.latest_ready_revision.split('/')[-1] if service.latest_ready_revision else None,
                    traffic=traffic,
                    conditions=conditions
                ))

            return services

        return await self._retry_with_backoff('cloud_run_list_services', _list)

    async def cloud_run_update_traffic(
        self,
        project: str | None = None,
        region: str | None = None,
        service: str = '',
        revisions: dict[str, int] | None = None
    ) -> dict[str, Any]:
        """
        Update traffic split for a Cloud Run service.

        Args:
            project: GCP project ID
            region: Region
            service: Service name
            revisions: Dict mapping revision names to traffic percentages
                      e.g., {"my-service-00001": 90, "my-service-00002": 10}

        Returns:
            Dict with update result
        """
        project = project or self._project
        region = region or self._region

        if not project or not service or not revisions:
            raise SkillExecutionError(
                skill_name='gcp',
                method='cloud_run_update_traffic',
                reason='Project, service, and revisions required'
            )

        # Validate percentages sum to 100
        total = sum(revisions.values())
        if total != 100:
            raise SkillExecutionError(
                skill_name='gcp',
                method='cloud_run_update_traffic',
                reason=f'Traffic percentages must sum to 100, got {total}'
            )

        def _update():
            client = ServicesClient(credentials=self._credentials)
            name = f"projects/{project}/locations/{region}/services/{service}"

            # Build traffic targets
            traffic_targets = []
            for revision, percent in revisions.items():
                traffic_targets.append(TrafficTarget(
                    revision=revision,
                    percent=percent
                ))

            # Get current service and update traffic
            current_service = client.get_service(name=name)
            current_service.traffic = traffic_targets

            # Update the service
            operation = client.update_service(service=current_service)
            result = operation.result()  # Wait for completion

            return {
                'service': service,
                'region': region,
                'traffic': [
                    {'revision': t.revision, 'percent': t.percent}
                    for t in result.traffic
                ],
                'success': True
            }

        return await self._retry_with_backoff('cloud_run_update_traffic', _update)

    # =========================================================================
    # Monitoring Operations
    # =========================================================================

    async def monitoring_query(
        self,
        project: str | None = None,
        query: str = '',
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> list[MetricDataPoint]:
        """
        Run a Monitoring Query Language (MQL) query.

        Args:
            project: GCP project ID
            query: MQL query string
            start_time: Start of time range (default: 1 hour ago)
            end_time: End of time range (default: now)

        Returns:
            List of MetricDataPoint dataclass objects
        """
        project = project or self._project

        if not project or not query:
            raise SkillExecutionError(
                skill_name='gcp',
                method='monitoring_query',
                reason='Project and query required'
            )

        def _query():
            client = monitoring_v3.QueryServiceClient(credentials=self._credentials)

            now = datetime.now(timezone.utc)
            monitoring_v3.TimeInterval(
                start_time=(start_time or (now - timedelta(hours=1))),
                end_time=(end_time or now)
            )

            request = monitoring_v3.QueryTimeSeriesRequest(
                name=f"projects/{project}",
                query=query
            )

            results = []
            for time_series in client.query_time_series(request=request):
                for point in time_series.point_data:
                    for value in point.values:
                        results.append(MetricDataPoint(
                            timestamp=point.time_interval.end_time,
                            value=value.double_value or value.int64_value or 0,
                            labels=dict(time_series.label_values) if hasattr(time_series, 'label_values') else {}
                        ))

            return results

        return await self._retry_with_backoff('monitoring_query', _query)

    # =========================================================================
    # Logging Operations
    # =========================================================================

    async def logging_query(
        self,
        project: str | None = None,
        filter: str = '',
        limit: int = 100,
        order_by: str = 'timestamp desc'
    ) -> list[LogEntry]:
        """
        Query Cloud Logging logs.

        Args:
            project: GCP project ID
            filter: Log filter string (e.g., 'severity>=ERROR')
            limit: Maximum number of entries to return
            order_by: Sort order ('timestamp desc' or 'timestamp asc')

        Returns:
            List of LogEntry dataclass objects
        """
        project = project or self._project

        if not project:
            raise SkillExecutionError(
                skill_name='gcp',
                method='logging_query',
                reason='No project specified'
            )

        def _query():
            client = cloud_logging.Client(project=project, credentials=self._credentials)

            entries = []
            for entry in client.list_entries(
                filter_=filter,
                order_by=order_by,
                page_size=limit,
                max_results=limit
            ):
                # Parse message
                if isinstance(entry.payload, dict):
                    message = json.dumps(entry.payload)
                else:
                    message = str(entry.payload)

                entries.append(LogEntry(
                    timestamp=entry.timestamp,
                    severity=entry.severity or 'DEFAULT',
                    message=message,
                    resource={
                        'type': entry.resource.type if entry.resource else None,
                        'labels': dict(entry.resource.labels) if entry.resource else {}
                    },
                    labels=dict(entry.labels) if entry.labels else {}
                ))

            return entries

        return await self._retry_with_backoff('logging_query', _query)

    # =========================================================================
    # BigQuery Operations
    # =========================================================================

    async def bigquery_query(
        self,
        project: str | None = None,
        sql: str = '',
        timeout: int | None = None,
        max_results: int = 1000
    ) -> BigQueryResult:
        """
        Execute a BigQuery SQL query.

        Args:
            project: GCP project ID
            sql: SQL query string
            timeout: Query timeout in seconds
            max_results: Maximum number of rows to return

        Returns:
            BigQueryResult dataclass with rows and schema
        """
        project = project or self._project

        if not project or not sql:
            raise SkillExecutionError(
                skill_name='gcp',
                method='bigquery_query',
                reason='Project and SQL query required'
            )

        def _query():
            client = bigquery.Client(project=project, credentials=self._credentials)

            job_config = bigquery.QueryJobConfig()
            job = client.query(sql, job_config=job_config)

            # Wait for results
            result = job.result(timeout=timeout or self._timeout)

            # Convert to list of dicts
            rows = []
            for row in result:
                rows.append(dict(row.items()))
                if len(rows) >= max_results:
                    break

            # Get schema
            schema = [
                {'name': field.name, 'type': field.field_type}
                for field in result.schema
            ]

            return BigQueryResult(
                total_rows=result.total_rows,
                rows=rows,
                schema=schema,
                job_id=job.job_id
            )

        return await self._retry_with_backoff('bigquery_query', _query)

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check GCP connectivity by attempting to list projects.

        Returns:
            Dict with connection status and identity info
        """
        def _check():
            from google.cloud import resourcemanager_v3

            client = resourcemanager_v3.ProjectsClient(credentials=self._credentials)

            # Try to get the current project
            if self._project:
                try:
                    project = client.get_project(name=f"projects/{self._project}")
                    return {
                        'status': 'connected',
                        'project_id': project.project_id,
                        'project_name': project.display_name,
                        'state': project.state.name
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'error': str(e),
                        'project': self._project
                    }

            return {
                'status': 'connected',
                'project': None,
                'note': 'No project configured'
            }

        try:
            return await self._run_sync(_check)
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'configured': self._credentials is not None
            }
