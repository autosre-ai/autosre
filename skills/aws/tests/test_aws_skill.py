"""Tests for AWS Skill."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add skills directory to path for imports
skills_dir = Path(__file__).parent.parent.parent.parent
if str(skills_dir) not in sys.path:
    sys.path.insert(0, str(skills_dir))

from skills.aws.skill import (
    AWSSkill,
)


@pytest.fixture
def aws_skill():
    """Create AWS skill with test config."""
    return AWSSkill({
        'region': 'us-west-2',
        'max_retries': 1,
        'retry_delay': 0.1
    })


class TestEC2Operations:
    """Tests for EC2 operations."""

    @pytest.mark.asyncio
    async def test_ec2_list_instances(self, aws_skill):
        """Test listing EC2 instances."""
        mock_response = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-1234567890abcdef0',
                    'InstanceType': 't3.micro',
                    'State': {'Name': 'running'},
                    'PrivateIpAddress': '10.0.0.1',
                    'PublicIpAddress': '54.123.45.67',
                    'Placement': {'AvailabilityZone': 'us-west-2a'},
                    'LaunchTime': datetime(2024, 1, 1, tzinfo=timezone.utc),
                    'Tags': [
                        {'Key': 'Name', 'Value': 'web-server-1'},
                        {'Key': 'Environment', 'Value': 'prod'}
                    ]
                }]
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ec2 = AsyncMock()
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_response].__iter__()
            mock_ec2.get_paginator.return_value = mock_paginator
            mock_client.return_value.__aenter__.return_value = mock_ec2

            instances = await aws_skill.ec2_list_instances()

            assert len(instances) == 1
            assert instances[0].instance_id == 'i-1234567890abcdef0'
            assert instances[0].name == 'web-server-1'
            assert instances[0].state == 'running'
            assert instances[0].tags['Environment'] == 'prod'

    @pytest.mark.asyncio
    async def test_ec2_get_instance(self, aws_skill):
        """Test getting a specific EC2 instance."""
        mock_response = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-1234567890abcdef0',
                    'InstanceType': 't3.micro',
                    'State': {'Name': 'running'},
                    'Placement': {'AvailabilityZone': 'us-west-2a'},
                    'Tags': []
                }]
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ec2 = AsyncMock()
            mock_ec2.describe_instances.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_ec2

            instance = await aws_skill.ec2_get_instance('i-1234567890abcdef0')

            assert instance is not None
            assert instance.instance_id == 'i-1234567890abcdef0'
            mock_ec2.describe_instances.assert_called_once_with(
                InstanceIds=['i-1234567890abcdef0']
            )

    @pytest.mark.asyncio
    async def test_ec2_start_instance(self, aws_skill):
        """Test starting an EC2 instance."""
        mock_response = {
            'StartingInstances': [{
                'InstanceId': 'i-1234567890abcdef0',
                'PreviousState': {'Name': 'stopped'},
                'CurrentState': {'Name': 'pending'}
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ec2 = AsyncMock()
            mock_ec2.start_instances.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_ec2

            result = await aws_skill.ec2_start_instance('i-1234567890abcdef0')

            assert result['success'] is True
            assert result['previous_state'] == 'stopped'
            assert result['current_state'] == 'pending'

    @pytest.mark.asyncio
    async def test_ec2_stop_instance(self, aws_skill):
        """Test stopping an EC2 instance."""
        mock_response = {
            'StoppingInstances': [{
                'InstanceId': 'i-1234567890abcdef0',
                'PreviousState': {'Name': 'running'},
                'CurrentState': {'Name': 'stopping'}
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ec2 = AsyncMock()
            mock_ec2.stop_instances.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_ec2

            result = await aws_skill.ec2_stop_instance('i-1234567890abcdef0')

            assert result['success'] is True
            assert result['previous_state'] == 'running'
            assert result['current_state'] == 'stopping'


class TestECSOperations:
    """Tests for ECS operations."""

    @pytest.mark.asyncio
    async def test_ecs_list_services(self, aws_skill):
        """Test listing ECS services."""
        mock_list_response = {'serviceArns': ['arn:aws:ecs:...:service/my-service']}
        mock_describe_response = {
            'services': [{
                'serviceName': 'my-service',
                'clusterArn': 'arn:aws:ecs:...:cluster/my-cluster',
                'status': 'ACTIVE',
                'desiredCount': 2,
                'runningCount': 2,
                'pendingCount': 0,
                'taskDefinition': 'arn:aws:ecs:...:task-definition/my-task:1',
                'launchType': 'FARGATE'
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ecs = AsyncMock()
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_list_response].__iter__()
            mock_ecs.get_paginator.return_value = mock_paginator
            mock_ecs.describe_services.return_value = mock_describe_response
            mock_client.return_value.__aenter__.return_value = mock_ecs

            services = await aws_skill.ecs_list_services('my-cluster')

            assert len(services) == 1
            assert services[0].service_name == 'my-service'
            assert services[0].running_count == 2

    @pytest.mark.asyncio
    async def test_ecs_update_service(self, aws_skill):
        """Test updating ECS service."""
        mock_response = {
            'service': {
                'serviceName': 'my-service',
                'clusterArn': 'arn:aws:ecs:...:cluster/my-cluster',
                'desiredCount': 5,
                'runningCount': 2,
                'status': 'ACTIVE'
            }
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_ecs = AsyncMock()
            mock_ecs.update_service.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_ecs

            result = await aws_skill.ecs_update_service(
                'my-cluster', 'my-service', desired_count=5
            )

            assert result['success'] is True
            assert result['desired_count'] == 5


class TestLambdaOperations:
    """Tests for Lambda operations."""

    @pytest.mark.asyncio
    async def test_lambda_invoke(self, aws_skill):
        """Test invoking a Lambda function."""
        mock_payload = AsyncMock()
        mock_payload.read.return_value = b'{"result": "success"}'

        mock_response = {
            'StatusCode': 200,
            'ExecutedVersion': '$LATEST',
            'Payload': mock_payload
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_lambda = AsyncMock()
            mock_lambda.invoke.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_lambda

            result = await aws_skill.lambda_invoke(
                'my-function',
                payload={'key': 'value'}
            )

            assert result['success'] is True
            assert result['response'] == {'result': 'success'}


class TestCloudWatchOperations:
    """Tests for CloudWatch operations."""

    @pytest.mark.asyncio
    async def test_cloudwatch_get_metrics(self, aws_skill):
        """Test getting CloudWatch metrics."""
        mock_response = {
            'Datapoints': [
                {
                    'Timestamp': datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                    'Average': 45.5,
                    'Unit': 'Percent'
                }
            ]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_cw = AsyncMock()
            mock_cw.get_metric_statistics.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_cw

            metrics = await aws_skill.cloudwatch_get_metrics(
                namespace='AWS/EC2',
                metric_name='CPUUtilization',
                dimensions={'InstanceId': 'i-1234567890abcdef0'}
            )

            assert len(metrics) == 1
            assert metrics[0]['value'] == 45.5

    @pytest.mark.asyncio
    async def test_cloudwatch_get_alarms(self, aws_skill):
        """Test listing CloudWatch alarms."""
        mock_response = {
            'MetricAlarms': [{
                'AlarmName': 'high-cpu',
                'StateValue': 'ALARM',
                'MetricName': 'CPUUtilization',
                'Namespace': 'AWS/EC2',
                'Threshold': 80.0,
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'AlarmDescription': 'CPU is too high'
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_cw = AsyncMock()
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_response].__iter__()
            mock_cw.get_paginator.return_value = mock_paginator
            mock_client.return_value.__aenter__.return_value = mock_cw

            alarms = await aws_skill.cloudwatch_get_alarms(state='ALARM')

            assert len(alarms) == 1
            assert alarms[0].name == 'high-cpu'
            assert alarms[0].state == 'ALARM'


class TestRDSOperations:
    """Tests for RDS operations."""

    @pytest.mark.asyncio
    async def test_rds_describe_instances(self, aws_skill):
        """Test describing RDS instances."""
        mock_response = {
            'DBInstances': [{
                'DBInstanceIdentifier': 'my-database',
                'DBInstanceClass': 'db.t3.micro',
                'Engine': 'postgres',
                'EngineVersion': '15.3',
                'DBInstanceStatus': 'available',
                'Endpoint': {
                    'Address': 'my-database.xxx.us-west-2.rds.amazonaws.com',
                    'Port': 5432
                },
                'AvailabilityZone': 'us-west-2a',
                'MultiAZ': False
            }]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_rds = AsyncMock()
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [mock_response].__iter__()
            mock_rds.get_paginator.return_value = mock_paginator
            mock_client.return_value.__aenter__.return_value = mock_rds

            instances = await aws_skill.rds_describe_instances()

            assert len(instances) == 1
            assert instances[0].db_instance_id == 'my-database'
            assert instances[0].engine == 'postgres'


class TestS3Operations:
    """Tests for S3 operations."""

    @pytest.mark.asyncio
    async def test_s3_list_buckets(self, aws_skill):
        """Test listing S3 buckets."""
        mock_response = {
            'Buckets': [
                {
                    'Name': 'my-bucket',
                    'CreationDate': datetime(2024, 1, 1, tzinfo=timezone.utc)
                }
            ]
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_s3 = AsyncMock()
            mock_s3.list_buckets.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_s3

            buckets = await aws_skill.s3_list_buckets()

            assert len(buckets) == 1
            assert buckets[0].name == 'my-bucket'


class TestHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, aws_skill):
        """Test successful health check."""
        mock_response = {
            'Account': '123456789012',
            'Arn': 'arn:aws:iam::123456789012:user/test',
            'UserId': 'AIDAXXXXXXXXXXXXXXXXX'
        }

        with patch.object(aws_skill, '_get_client') as mock_client:
            mock_sts = AsyncMock()
            mock_sts.get_caller_identity.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_sts

            result = await aws_skill.health_check()

            assert result['status'] == 'connected'
            assert result['account'] == '123456789012'
