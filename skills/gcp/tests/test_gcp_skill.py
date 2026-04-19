"""Tests for GCP Skill."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import sys
from pathlib import Path

# Add skills directory to path for imports
skills_dir = Path(__file__).parent.parent.parent.parent
if str(skills_dir) not in sys.path:
    sys.path.insert(0, str(skills_dir))

google = pytest.importorskip("google.cloud")
google_auth = pytest.importorskip("google.auth")

from skills.gcp.skill import (
    GCPSkill,
    GCEInstance,
    GKECluster,
    CloudRunService,
    MetricDataPoint,
    LogEntry,
    BigQueryResult,
)


@pytest.fixture
def gcp_skill():
    """Create GCP skill with test config."""
    with patch.object(GCPSkill, '_init_credentials'):
        skill = GCPSkill({
            'project': 'test-project',
            'region': 'us-central1',
            'zone': 'us-central1-a',
            'max_retries': 1,
            'retry_delay': 0.1
        })
        skill._credentials = MagicMock()
        return skill


class TestGCEOperations:
    """Tests for Compute Engine operations."""
    
    @pytest.mark.asyncio
    async def test_gce_list_instances(self, gcp_skill):
        """Test listing GCE instances."""
        mock_instance = MagicMock()
        mock_instance.name = 'web-server-1'
        mock_instance.machine_type = 'zones/us-central1-a/machineTypes/e2-micro'
        mock_instance.status = 'RUNNING'
        mock_instance.creation_timestamp = '2024-01-01T00:00:00Z'
        mock_instance.labels = {'env': 'prod'}
        mock_instance.tags = MagicMock(items=['http-server'])
        
        mock_interface = MagicMock()
        mock_interface.network_i_p = '10.0.0.1'
        mock_access = MagicMock()
        mock_access.nat_i_p = '34.123.45.67'
        mock_interface.access_configs = [mock_access]
        mock_instance.network_interfaces = [mock_interface]
        
        with patch('gcp.skill.compute_v1') as mock_compute:
            mock_client = MagicMock()
            mock_compute.InstancesClient.return_value = mock_client
            mock_client.list.return_value = [mock_instance]
            
            instances = await gcp_skill.gce_list_instances()
            
            assert len(instances) == 1
            assert instances[0].name == 'web-server-1'
            assert instances[0].status == 'RUNNING'
            assert instances[0].internal_ip == '10.0.0.1'
            assert instances[0].external_ip == '34.123.45.67'
    
    @pytest.mark.asyncio
    async def test_gce_start_instance(self, gcp_skill):
        """Test starting a GCE instance."""
        with patch('gcp.skill.compute_v1') as mock_compute:
            mock_client = MagicMock()
            mock_op_client = MagicMock()
            mock_compute.InstancesClient.return_value = mock_client
            mock_compute.ZoneOperationsClient.return_value = mock_op_client
            
            mock_operation = MagicMock()
            mock_operation.name = 'operation-123'
            mock_operation.status = mock_compute.Operation.Status.DONE
            mock_operation.error = None
            mock_client.start.return_value = mock_operation
            mock_op_client.get.return_value = mock_operation
            
            result = await gcp_skill.gce_start_instance(instance='web-server-1')
            
            assert result['success'] is True
            assert result['instance'] == 'web-server-1'
            assert result['status'] == 'DONE'
    
    @pytest.mark.asyncio
    async def test_gce_stop_instance(self, gcp_skill):
        """Test stopping a GCE instance."""
        with patch('gcp.skill.compute_v1') as mock_compute:
            mock_client = MagicMock()
            mock_op_client = MagicMock()
            mock_compute.InstancesClient.return_value = mock_client
            mock_compute.ZoneOperationsClient.return_value = mock_op_client
            
            mock_operation = MagicMock()
            mock_operation.name = 'operation-456'
            mock_operation.status = mock_compute.Operation.Status.DONE
            mock_operation.error = None
            mock_client.stop.return_value = mock_operation
            mock_op_client.get.return_value = mock_operation
            
            result = await gcp_skill.gce_stop_instance(instance='web-server-1')
            
            assert result['success'] is True


class TestGKEOperations:
    """Tests for GKE operations."""
    
    @pytest.mark.asyncio
    async def test_gke_list_clusters(self, gcp_skill):
        """Test listing GKE clusters."""
        with patch('gcp.skill.container_v1') as mock_container:
            mock_client = MagicMock()
            mock_container.ClusterManagerClient.return_value = mock_client
            mock_container.Cluster.Status.return_value = 'RUNNING'
            
            mock_cluster = MagicMock()
            mock_cluster.name = 'my-cluster'
            mock_cluster.location = 'us-central1'
            mock_cluster.status = 2  # RUNNING
            mock_cluster.current_master_version = '1.27.3-gke.100'
            mock_cluster.endpoint = '35.123.45.67'
            mock_cluster.autopilot = MagicMock(enabled=False)
            
            mock_pool = MagicMock()
            mock_pool.name = 'default-pool'
            mock_pool.initial_node_count = 3
            mock_pool.config = MagicMock(machine_type='e2-medium')
            mock_cluster.node_pools = [mock_pool]
            
            mock_response = MagicMock()
            mock_response.clusters = [mock_cluster]
            mock_client.list_clusters.return_value = mock_response
            
            clusters = await gcp_skill.gke_list_clusters()
            
            assert len(clusters) == 1
            assert clusters[0].name == 'my-cluster'
            assert clusters[0].node_count == 3
    
    @pytest.mark.asyncio
    async def test_gke_get_cluster(self, gcp_skill):
        """Test getting a specific GKE cluster."""
        with patch('gcp.skill.container_v1') as mock_container:
            mock_client = MagicMock()
            mock_container.ClusterManagerClient.return_value = mock_client
            
            mock_cluster = MagicMock()
            mock_cluster.name = 'my-cluster'
            mock_cluster.location = 'us-central1'
            mock_cluster.status = 2
            mock_cluster.current_master_version = '1.27.3-gke.100'
            mock_cluster.endpoint = '35.123.45.67'
            mock_cluster.autopilot = MagicMock(enabled=True)
            mock_cluster.node_pools = []
            mock_client.get_cluster.return_value = mock_cluster
            
            cluster = await gcp_skill.gke_get_cluster(cluster='my-cluster')
            
            assert cluster is not None
            assert cluster.name == 'my-cluster'
            assert cluster.autopilot is True


class TestCloudRunOperations:
    """Tests for Cloud Run operations."""
    
    @pytest.mark.asyncio
    async def test_cloud_run_list_services(self, gcp_skill):
        """Test listing Cloud Run services."""
        with patch('gcp.skill.ServicesClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_service = MagicMock()
            mock_service.name = 'projects/test/locations/us-central1/services/my-service'
            mock_service.uri = 'https://my-service-xxx.run.app'
            mock_service.latest_ready_revision = 'projects/test/locations/us-central1/services/my-service/revisions/my-service-00001'
            mock_service.traffic = []
            mock_service.conditions = []
            mock_client.list_services.return_value = [mock_service]
            
            services = await gcp_skill.cloud_run_list_services()
            
            assert len(services) == 1
            assert services[0].name == 'my-service'
            assert services[0].latest_revision == 'my-service-00001'


class TestMonitoringOperations:
    """Tests for Monitoring operations."""
    
    @pytest.mark.asyncio
    async def test_monitoring_query(self, gcp_skill):
        """Test running a monitoring query."""
        with patch('gcp.skill.monitoring_v3') as mock_monitoring:
            mock_client = MagicMock()
            mock_monitoring.QueryServiceClient.return_value = mock_client
            
            mock_point = MagicMock()
            mock_point.time_interval.end_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            mock_value = MagicMock()
            mock_value.double_value = 42.5
            mock_value.int64_value = 0
            mock_point.values = [mock_value]
            
            mock_ts = MagicMock()
            mock_ts.point_data = [mock_point]
            mock_client.query_time_series.return_value = [mock_ts]
            
            results = await gcp_skill.monitoring_query(
                query='fetch gce_instance::compute.googleapis.com/instance/cpu/utilization'
            )
            
            assert len(results) == 1
            assert results[0].value == 42.5


class TestLoggingOperations:
    """Tests for Logging operations."""
    
    @pytest.mark.asyncio
    async def test_logging_query(self, gcp_skill):
        """Test querying logs."""
        with patch('gcp.skill.cloud_logging') as mock_logging:
            mock_client = MagicMock()
            mock_logging.Client.return_value = mock_client
            
            mock_entry = MagicMock()
            mock_entry.timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            mock_entry.severity = 'ERROR'
            mock_entry.payload = {'message': 'Test error'}
            mock_entry.resource = MagicMock(type='gce_instance', labels={'instance_id': '123'})
            mock_entry.labels = {'env': 'prod'}
            mock_client.list_entries.return_value = [mock_entry]
            
            entries = await gcp_skill.logging_query(filter='severity>=ERROR')
            
            assert len(entries) == 1
            assert entries[0].severity == 'ERROR'


class TestBigQueryOperations:
    """Tests for BigQuery operations."""
    
    @pytest.mark.asyncio
    async def test_bigquery_query(self, gcp_skill):
        """Test executing a BigQuery query."""
        with patch('gcp.skill.bigquery') as mock_bq:
            mock_client = MagicMock()
            mock_bq.Client.return_value = mock_client
            
            mock_row = MagicMock()
            mock_row.items.return_value = [('name', 'test'), ('count', 42)]
            
            mock_job = MagicMock()
            mock_job.job_id = 'job-123'
            mock_result = MagicMock()
            mock_result.total_rows = 1
            mock_result.__iter__ = lambda x: iter([mock_row])
            mock_result.schema = [
                MagicMock(name='name', field_type='STRING'),
                MagicMock(name='count', field_type='INTEGER')
            ]
            mock_job.result.return_value = mock_result
            mock_client.query.return_value = mock_job
            
            result = await gcp_skill.bigquery_query(sql='SELECT * FROM test')
            
            assert result.total_rows == 1
            assert len(result.rows) == 1
            assert result.rows[0]['name'] == 'test'


class TestHealthCheck:
    """Tests for health check."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, gcp_skill):
        """Test successful health check."""
        with patch('gcp.skill.resourcemanager_v3', create=True) as mock_rm:
            mock_client = MagicMock()
            mock_rm.ProjectsClient.return_value = mock_client
            
            mock_project = MagicMock()
            mock_project.project_id = 'test-project'
            mock_project.display_name = 'Test Project'
            mock_project.state = MagicMock(name='ACTIVE')
            mock_client.get_project.return_value = mock_project
            
            result = await gcp_skill.health_check()
            
            assert result['status'] == 'connected'
            assert result['project_id'] == 'test-project'
