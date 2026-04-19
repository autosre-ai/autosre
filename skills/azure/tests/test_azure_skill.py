"""Tests for Azure Skill."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, AsyncMock

import sys
from pathlib import Path

# Add skills directory to path for imports
skills_dir = Path(__file__).parent.parent.parent.parent
if str(skills_dir) not in sys.path:
    sys.path.insert(0, str(skills_dir))

pytest.importorskip("azure.identity")

from skills.azure.skill import (
    AzureSkill,
    AzureVM,
    AKSCluster,
    LogQueryResult,
)


@pytest.fixture
def azure_skill():
    """Create Azure skill with test config."""
    with patch.object(AzureSkill, '_init_credentials'):
        skill = AzureSkill({
            'subscription_id': 'test-sub-123',
            'resource_group': 'test-rg',
            'max_retries': 1,
            'retry_delay': 0.1
        })
        skill._credential = MagicMock()
        return skill


class TestVMOperations:
    """Tests for VM operations."""
    
    @pytest.mark.asyncio
    async def test_vm_list(self, azure_skill):
        """Test listing VMs."""
        with patch.object(azure_skill, '_get_compute_client') as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            
            mock_vm = MagicMock()
            mock_vm.id = '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/web-server'
            mock_vm.name = 'web-server'
            mock_vm.location = 'eastus'
            mock_vm.provisioning_state = 'Succeeded'
            mock_vm.hardware_profile = MagicMock(vm_size='Standard_B2s')
            mock_vm.storage_profile = MagicMock(
                os_disk=MagicMock(os_type='Linux')
            )
            mock_vm.tags = {'env': 'prod'}
            
            # Mock instance view for power state
            mock_instance_view = MagicMock()
            mock_status = MagicMock()
            mock_status.code = 'PowerState/running'
            mock_instance_view.statuses = [mock_status]
            mock_client.virtual_machines.instance_view.return_value = mock_instance_view
            
            mock_client.virtual_machines.list.return_value = [mock_vm]
            
            vms = await azure_skill.vm_list(resource_group='test-rg')
            
            assert len(vms) == 1
            assert vms[0].name == 'web-server'
            assert vms[0].power_state == 'running'
            assert vms[0].vm_size == 'Standard_B2s'
    
    @pytest.mark.asyncio
    async def test_vm_start(self, azure_skill):
        """Test starting a VM."""
        with patch.object(azure_skill, '_get_compute_client') as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            
            mock_poller = MagicMock()
            mock_client.virtual_machines.begin_start.return_value = mock_poller
            
            result = await azure_skill.vm_start(
                resource_group='test-rg',
                vm_name='web-server'
            )
            
            assert result['success'] is True
            assert result['status'] == 'Started'
            mock_poller.wait.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_vm_stop(self, azure_skill):
        """Test stopping a VM."""
        with patch.object(azure_skill, '_get_compute_client') as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            
            mock_poller = MagicMock()
            mock_client.virtual_machines.begin_deallocate.return_value = mock_poller
            
            result = await azure_skill.vm_stop(
                resource_group='test-rg',
                vm_name='web-server',
                deallocate=True
            )
            
            assert result['success'] is True
            assert result['status'] == 'Deallocated'


class TestAKSOperations:
    """Tests for AKS operations."""
    
    @pytest.mark.asyncio
    async def test_aks_list_clusters(self, azure_skill):
        """Test listing AKS clusters."""
        with patch.object(azure_skill, '_get_aks_client') as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            
            mock_cluster = MagicMock()
            mock_cluster.id = '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerService/managedClusters/my-cluster'
            mock_cluster.name = 'my-cluster'
            mock_cluster.location = 'eastus'
            mock_cluster.kubernetes_version = '1.27.3'
            mock_cluster.provisioning_state = 'Succeeded'
            mock_cluster.fqdn = 'my-cluster-xxx.hcp.eastus.azmk8s.io'
            mock_cluster.tags = {'env': 'prod'}
            
            mock_pool = MagicMock()
            mock_pool.name = 'default'
            mock_pool.vm_size = 'Standard_D2s_v3'
            mock_pool.count = 3
            mock_pool.mode = 'System'
            mock_pool.os_type = 'Linux'
            mock_pool.enable_auto_scaling = True
            mock_pool.min_count = 2
            mock_pool.max_count = 5
            mock_cluster.agent_pool_profiles = [mock_pool]
            
            mock_client.managed_clusters.list_by_resource_group.return_value = [mock_cluster]
            
            clusters = await azure_skill.aks_list_clusters(resource_group='test-rg')
            
            assert len(clusters) == 1
            assert clusters[0].name == 'my-cluster'
            assert clusters[0].node_count == 3
            assert clusters[0].node_pools[0]['autoscaling']['enabled'] is True
    
    @pytest.mark.asyncio
    async def test_aks_get_credentials(self, azure_skill):
        """Test getting AKS credentials."""
        with patch.object(azure_skill, '_get_aks_client') as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            
            import base64
            kubeconfig = "apiVersion: v1\nkind: Config"
            encoded = base64.b64encode(kubeconfig.encode()).decode()
            
            mock_kc = MagicMock()
            mock_kc.name = 'clusterUser'
            mock_kc.value = encoded.encode()
            
            mock_creds = MagicMock()
            mock_creds.kubeconfigs = [mock_kc]
            mock_client.managed_clusters.list_cluster_user_credentials.return_value = mock_creds
            
            result = await azure_skill.aks_get_credentials(
                resource_group='test-rg',
                cluster='my-cluster'
            )
            
            assert result['success'] is True
            assert len(result['kubeconfigs']) == 1
            assert 'apiVersion' in result['kubeconfigs'][0]['kubeconfig']


class TestMonitorOperations:
    """Tests for Monitor operations."""
    
    @pytest.mark.asyncio
    async def test_monitor_query(self, azure_skill):
        """Test running a Log Analytics query."""
        with patch('azure.skill.LogsQueryClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_column = MagicMock()
            mock_column.name = 'TimeGenerated'
            
            mock_table = MagicMock()
            mock_table.name = 'PrimaryResult'
            mock_table.columns = [mock_column]
            mock_table.rows = [[datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)]]
            
            from azure.monitor.query import LogsQueryStatus
            mock_response = MagicMock()
            mock_response.status = LogsQueryStatus.SUCCESS
            mock_response.tables = [mock_table]
            mock_response.statistics = {'query': {'executionTime': 0.5}}
            mock_client.query_workspace.return_value = mock_response
            
            result = await azure_skill.monitor_query(
                workspace_id='workspace-123',
                query='AzureActivity | take 10'
            )
            
            assert result.status == 'Success'
            assert len(result.tables) == 1
            assert result.tables[0]['row_count'] == 1


class TestAppInsightsOperations:
    """Tests for App Insights operations."""
    
    @pytest.mark.asyncio
    async def test_app_insights_query(self, azure_skill):
        """Test running an App Insights query."""
        with patch('azure.skill.LogsQueryClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_column = MagicMock()
            mock_column.name = 'operation_Name'
            
            mock_table = MagicMock()
            mock_table.name = 'PrimaryResult'
            mock_table.columns = [mock_column]
            mock_table.rows = [['GET /api/health']]
            
            from azure.monitor.query import LogsQueryStatus
            mock_response = MagicMock()
            mock_response.status = LogsQueryStatus.SUCCESS
            mock_response.tables = [mock_table]
            mock_response.statistics = None
            mock_client.query_workspace.return_value = mock_response
            
            result = await azure_skill.app_insights_query(
                app_id='app-123',
                query='requests | take 10'
            )
            
            assert result.status == 'Success'
            assert len(result.tables) == 1


class TestHealthCheck:
    """Tests for health check."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, azure_skill):
        """Test successful health check."""
        with patch('azure.skill.ResourceManagementClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_rg1 = MagicMock()
            mock_rg1.name = 'rg-1'
            mock_rg2 = MagicMock()
            mock_rg2.name = 'rg-2'
            mock_client.resource_groups.list.return_value = [mock_rg1, mock_rg2]
            
            result = await azure_skill.health_check()
            
            assert result['status'] == 'connected'
            assert result['resource_group_count'] == 2
    
    @pytest.mark.asyncio
    async def test_health_check_no_subscription(self):
        """Test health check without subscription ID."""
        with patch.object(AzureSkill, '_init_credentials'):
            skill = AzureSkill({})  # No subscription_id
            skill._credential = MagicMock()
            
            result = await skill.health_check()
            
            assert result['status'] == 'not_configured'
            assert 'subscription' in result['error'].lower()
