"""Tests for External Integrations."""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from autosre.integrations.external.jira import (
    JiraIntegration,
    JiraConfig,
    JiraIssue,
    JiraTransition,
    JiraComment,
    JiraPriority,
    JiraIssueType,
)
from autosre.integrations.external.servicenow import (
    ServiceNowIntegration,
    ServiceNowConfig,
    ServiceNowIncident,
    ServiceNowChangeRequest,
    ServiceNowState,
    ServiceNowImpact,
    ServiceNowUrgency,
)
from autosre.integrations.external.github import (
    GitHubIntegration,
    GitHubConfig,
    GitHubPullRequest,
    GitHubDeployment,
    GitHubCommit,
    DeploymentState,
    PRState,
)
from autosre.integrations.external.terraform import (
    TerraformIntegration,
    TerraformConfig,
    TerraformPlan,
    TerraformState,
    TerraformResource,
    RunStatus,
)
from autosre.integrations.external.vault import (
    VaultIntegration,
    VaultConfig,
    VaultSecret,
    VaultToken,
    VaultAuthMethod,
)
from autosre.integrations.external.datadog import (
    DatadogIntegration,
    DatadogConfig,
    DatadogMetric,
    DatadogEvent,
    DatadogMonitor,
    MetricType,
    AlertType,
)
from autosre.integrations.external.newrelic import (
    NewRelicIntegration,
    NewRelicConfig,
    NewRelicMetric,
    NewRelicEvent,
    NewRelicDeployment,
)


class TestJiraIntegration:
    """Tests for Jira integration."""
    
    @pytest.fixture
    def config(self):
        """Create Jira config."""
        return JiraConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            default_project="TEST",
        )
    
    @pytest.mark.asyncio
    async def test_issue_to_payload(self, config):
        """Test JiraIssue to API payload conversion."""
        issue = JiraIssue(
            project="TEST",
            summary="Test issue",
            description="Test description",
            issue_type="Bug",
            priority="High",
            labels=["urgent", "production"],
        )
        
        payload = issue.to_create_payload()
        
        assert payload["fields"]["project"]["key"] == "TEST"
        assert payload["fields"]["summary"] == "Test issue"
        assert payload["fields"]["issuetype"]["name"] == "Bug"
        assert payload["fields"]["priority"]["name"] == "High"
        assert payload["fields"]["labels"] == ["urgent", "production"]
    
    @pytest.mark.asyncio
    async def test_create_incident_issue(self, config):
        """Test incident issue creation helper."""
        with patch.object(JiraIntegration, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "id": "12345",
                "key": "TEST-1",
                "self": "https://test.atlassian.net/rest/api/3/issue/12345",
            }
            
            integration = JiraIntegration(config)
            integration._client = AsyncMock()
            
            result = await integration.create_incident_issue(
                title="High Latency Alert",
                description="P99 latency exceeded threshold",
                severity="critical",
                investigation_id="inv-123",
            )
            
            assert result.key == "TEST-1"
            
            # Check the payload
            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            
            assert "autosre" in payload["fields"]["labels"]
            assert "severity:critical" in payload["fields"]["labels"]


class TestServiceNowIntegration:
    """Tests for ServiceNow integration."""
    
    @pytest.fixture
    def config(self):
        """Create ServiceNow config."""
        return ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="admin",
            password="password",
            default_assignment_group="SRE",
        )
    
    def test_incident_to_payload(self):
        """Test ServiceNowIncident to API payload conversion."""
        incident = ServiceNowIncident(
            short_description="Test incident",
            description="Detailed description",
            impact=ServiceNowImpact.HIGH,
            urgency=ServiceNowUrgency.HIGH,
            category="Software",
        )
        
        payload = incident.to_create_payload()
        
        assert payload["short_description"] == "Test incident"
        assert payload["impact"] == "1"
        assert payload["urgency"] == "1"
        assert payload["category"] == "Software"
    
    def test_state_enum_values(self):
        """Test ServiceNow state enum values."""
        assert ServiceNowState.NEW.value == "1"
        assert ServiceNowState.IN_PROGRESS.value == "2"
        assert ServiceNowState.RESOLVED.value == "6"
        assert ServiceNowState.CLOSED.value == "7"


class TestGitHubIntegration:
    """Tests for GitHub integration."""
    
    @pytest.fixture
    def config(self):
        """Create GitHub config."""
        return GitHubConfig(
            token="ghp_test_token",
            default_owner="testorg",
            default_repo="testrepo",
        )
    
    def test_pr_state_mapping(self):
        """Test PR state enum."""
        assert PRState.OPEN.value == "open"
        assert PRState.CLOSED.value == "closed"
        assert PRState.MERGED.value == "merged"
    
    def test_deployment_state_mapping(self):
        """Test deployment state enum."""
        assert DeploymentState.SUCCESS.value == "success"
        assert DeploymentState.FAILURE.value == "failure"
        assert DeploymentState.IN_PROGRESS.value == "in_progress"
    
    @pytest.mark.asyncio
    async def test_repo_path(self, config):
        """Test repository path generation."""
        integration = GitHubIntegration(config)
        
        path = integration._repo_path()
        assert path == "/repos/testorg/testrepo"
        
        path = integration._repo_path("other", "repo")
        assert path == "/repos/other/repo"


class TestTerraformIntegration:
    """Tests for Terraform integration."""
    
    @pytest.fixture
    def config(self):
        """Create Terraform config."""
        return TerraformConfig(
            token="test-token",
            organization="test-org",
        )
    
    def test_run_status_enum(self):
        """Test run status enum."""
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.PLANNING.value == "planning"
        assert RunStatus.APPLIED.value == "applied"
        assert RunStatus.ERRORED.value == "errored"
    
    def test_terraform_resource_model(self):
        """Test TerraformResource model."""
        resource = TerraformResource(
            type="aws_instance",
            name="web",
            provider="registry.terraform.io/hashicorp/aws",
            attributes={"instance_type": "t3.micro"},
        )
        
        assert resource.type == "aws_instance"
        assert resource.name == "web"


class TestVaultIntegration:
    """Tests for Vault integration."""
    
    @pytest.fixture
    def config(self):
        """Create Vault config."""
        return VaultConfig(
            address="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            token="s.test-token",
        )
    
    def test_token_expiry(self):
        """Test token expiry checking."""
        token = VaultToken(
            client_token="test",
            accessor="acc",
            lease_duration=3600,
            renewable=True,
            expires_at=datetime.now(timezone.utc),
        )
        
        assert token.is_expired()
    
    def test_token_needs_renewal(self):
        """Test token renewal detection."""
        from datetime import timedelta
        
        # Token expiring soon
        token = VaultToken(
            client_token="test",
            accessor="acc",
            lease_duration=3600,
            renewable=True,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=100),
        )
        
        assert token.needs_renewal(threshold_seconds=300)
        
        # Token not expiring soon
        token.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert not token.needs_renewal(threshold_seconds=300)
    
    def test_secret_model(self):
        """Test VaultSecret model."""
        secret = VaultSecret(
            path="secret/data/myapp",
            data={"username": "admin", "password": "secret"},
            version=3,
        )
        
        assert secret.data["username"] == "admin"
        assert secret.version == 3


class TestDatadogIntegration:
    """Tests for Datadog integration."""
    
    @pytest.fixture
    def config(self):
        """Create Datadog config."""
        return DatadogConfig(
            api_key="test-api-key",
            app_key="test-app-key",
            site="us1",
        )
    
    def test_config_url_generation(self):
        """Test URL generation based on site."""
        config_us1 = DatadogConfig(
            api_key="key",
            app_key="key",
            site="us1",
        )
        assert config_us1.base_url == "https://api.datadoghq.com"
        
        config_eu = DatadogConfig(
            api_key="key",
            app_key="key",
            site="eu1",
        )
        assert config_eu.base_url == "https://api.datadoghq.eu"
    
    def test_metric_model(self):
        """Test DatadogMetric model."""
        metric = DatadogMetric(
            metric="autosre.test.metric",
            type=MetricType.GAUGE,
            tags=["env:test"],
        )
        
        metric.add_point(42.0)
        
        assert len(metric.points) == 1
        assert metric.points[0][1] == 42.0
    
    def test_event_model(self):
        """Test DatadogEvent model."""
        event = DatadogEvent(
            title="Test Event",
            text="Event description",
            alert_type=AlertType.INFO,
            tags=["test"],
        )
        
        assert event.title == "Test Event"
        assert event.alert_type == AlertType.INFO


class TestNewRelicIntegration:
    """Tests for New Relic integration."""
    
    @pytest.fixture
    def config(self):
        """Create New Relic config."""
        return NewRelicConfig(
            api_key="NRAK-test",
            account_id="12345",
            insert_key="NRII-test",
            region="us",
        )
    
    def test_config_url_generation(self):
        """Test URL generation based on region."""
        config_us = NewRelicConfig(
            api_key="key",
            account_id="123",
            region="us",
        )
        assert config_us.api_url == "https://api.newrelic.com"
        
        config_eu = NewRelicConfig(
            api_key="key",
            account_id="123",
            region="eu",
        )
        assert config_eu.api_url == "https://api.eu.newrelic.com"
    
    def test_metric_model(self):
        """Test NewRelicMetric model."""
        from autosre.integrations.external.newrelic import MetricType as NRMetricType
        
        metric = NewRelicMetric(
            name="autosre.test.metric",
            value=42.0,
            type=NRMetricType.GAUGE,
            attributes={"environment": "test"},
        )
        
        assert metric.name == "autosre.test.metric"
        assert metric.value == 42.0
    
    def test_event_model(self):
        """Test NewRelicEvent model."""
        event = NewRelicEvent(
            eventType="AutoSRETest",
            attributes={
                "testId": "123",
                "status": "ok",
            },
        )
        
        payload = event.to_payload()
        
        assert payload["eventType"] == "AutoSRETest"
        assert payload["testId"] == "123"
    
    def test_deployment_model(self):
        """Test NewRelicDeployment model."""
        deployment = NewRelicDeployment(
            entity_guid="MXxBUE18QVBQTElDQVRJT058MTIz",
            version="1.0.0",
            description="Test deployment",
            user="deployer",
        )
        
        assert deployment.version == "1.0.0"
        assert deployment.entity_guid.startswith("MX")


class TestScheduledReports:
    """Tests for Scheduled Reports."""
    
    @pytest.mark.asyncio
    async def test_schedule_config_next_run(self):
        """Test schedule next run calculation."""
        from autosre.reporting.scheduled_reports import (
            ScheduleConfig,
            ScheduleFrequency,
        )
        
        # Daily schedule
        config = ScheduleConfig(
            frequency=ScheduleFrequency.DAILY,
            hour=9,
            minute=0,
            timezone="UTC",
        )
        
        now = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        next_run = config.next_run(now)
        
        assert next_run.hour == 9
        assert next_run.day == 15
    
    @pytest.mark.asyncio
    async def test_schedule_crud(self):
        """Test schedule CRUD operations."""
        from autosre.reporting.scheduled_reports import (
            ScheduledReports,
            ReportSchedule,
            ScheduleConfig,
            DeliveryConfig,
            DeliveryChannel,
        )
        
        scheduler = ScheduledReports()
        
        # Create schedule
        schedule = ReportSchedule(
            name="Test Report",
            report_type="incident",
            schedule=ScheduleConfig(),
            deliveries=[
                DeliveryConfig(
                    channel=DeliveryChannel.EMAIL,
                    email_recipients=["test@example.com"],
                ),
            ],
        )
        
        created = await scheduler.create_schedule(schedule)
        assert created.id is not None
        assert created.next_run_at is not None
        
        # Get schedule
        retrieved = await scheduler.get_schedule(created.id)
        assert retrieved.name == "Test Report"
        
        # Update schedule
        updated = await scheduler.update_schedule(
            created.id,
            {"name": "Updated Report"},
        )
        assert updated.name == "Updated Report"
        
        # List schedules
        schedules = await scheduler.list_schedules()
        assert len(schedules) == 1
        
        # Delete schedule
        deleted = await scheduler.delete_schedule(created.id)
        assert deleted
        
        schedules = await scheduler.list_schedules()
        assert len(schedules) == 0
    
    @pytest.mark.asyncio
    async def test_report_generation(self):
        """Test report generation and delivery."""
        from autosre.reporting.scheduled_reports import (
            ScheduledReports,
            ReportSchedule,
            DeliveryConfig,
            DeliveryChannel,
        )
        
        scheduler = ScheduledReports()
        
        # Register mock generator
        async def mock_generator(report_type, params):
            return b"PDF report content"
        
        scheduler.register_generator("test", mock_generator)
        
        # Register mock delivery handler
        delivered = []
        
        async def mock_delivery(report_bytes, config):
            delivered.append(config)
            return {"message_id": "123"}
        
        scheduler.register_delivery_handler(
            DeliveryChannel.EMAIL,
            mock_delivery,
        )
        
        # Create and run schedule
        schedule = ReportSchedule(
            name="Test Report",
            report_type="test",
            deliveries=[
                DeliveryConfig(
                    channel=DeliveryChannel.EMAIL,
                    email_recipients=["test@example.com"],
                ),
            ],
        )
        
        await scheduler.create_schedule(schedule)
        
        delivery = await scheduler.run_schedule_now(schedule.id)
        
        assert delivery is not None
        assert delivery.status.value == "completed"
        assert len(delivered) == 1
