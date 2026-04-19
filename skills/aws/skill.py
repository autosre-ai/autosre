"""
AWS Cloud Provider Skill for OpenSRE

Provides actions for EC2, ECS, Lambda, CloudWatch, RDS, and S3.
Uses boto3 with async wrappers via aioboto3 for non-blocking operations.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

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
class EC2Instance:
    """Represents an EC2 instance."""
    instance_id: str
    name: str | None
    state: str
    instance_type: str
    private_ip: str | None
    public_ip: str | None
    availability_zone: str
    launch_time: datetime | None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ECSService:
    """Represents an ECS service."""
    service_name: str
    cluster_arn: str
    status: str
    desired_count: int
    running_count: int
    pending_count: int
    task_definition: str
    launch_type: str | None = None


@dataclass
class CloudWatchAlarm:
    """Represents a CloudWatch alarm."""
    name: str
    state: str
    metric_name: str
    namespace: str
    threshold: float
    comparison: str
    evaluation_periods: int
    description: str | None = None


@dataclass
class RDSInstance:
    """Represents an RDS instance."""
    db_instance_id: str
    db_instance_class: str
    engine: str
    engine_version: str
    status: str
    endpoint: str | None
    port: int | None
    availability_zone: str | None
    multi_az: bool = False


@dataclass
class S3Bucket:
    """Represents an S3 bucket."""
    name: str
    creation_date: datetime | None
    region: str | None = None


class AWSSkill:
    """
    AWS Cloud Provider Skill.

    Provides async methods for interacting with AWS services:
    - EC2: List, get, start, stop instances
    - ECS: List services, update service (scale)
    - Lambda: Invoke functions
    - CloudWatch: Get metrics, list alarms
    - RDS: Describe instances
    - S3: List buckets
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize AWS Skill.

        Args:
            config: Configuration dict with credentials and settings.
                   If not provided, uses default credential chain.
        """
        self.config = config or {}
        self._session: aioboto3.Session | None = None

        # Build boto config
        self._boto_config = Config(
            retries={
                'max_attempts': self.config.get('max_retries', 3),
                'mode': 'adaptive'
            }
        )

        # Session parameters
        self._session_params = {}

        if self.config.get('access_key'):
            self._session_params['aws_access_key_id'] = self.config['access_key']
        if self.config.get('secret_key'):
            self._session_params['aws_secret_access_key'] = self.config['secret_key']
        if self.config.get('session_token'):
            self._session_params['aws_session_token'] = self.config['session_token']
        if self.config.get('region'):
            self._session_params['region_name'] = self.config['region']
        if self.config.get('profile'):
            self._session_params['profile_name'] = self.config['profile']

        self._endpoint_url = self.config.get('endpoint_url')
        self._retry_delay = self.config.get('retry_delay', 1.0)

    @property
    def session(self) -> aioboto3.Session:
        """Get or create aioboto3 session."""
        if self._session is None:
            self._session = aioboto3.Session(**self._session_params)
        return self._session

    @asynccontextmanager
    async def _get_client(self, service_name: str):
        """Get an async client for the specified AWS service."""
        async with self.session.client(
            service_name,
            config=self._boto_config,
            endpoint_url=self._endpoint_url
        ) as client:
            yield client

    async def _retry_with_backoff(
        self,
        operation: str,
        coro_factory,
        max_retries: int | None = None
    ) -> Any:
        """
        Execute an async operation with exponential backoff retry.

        Args:
            operation: Name of the operation (for logging)
            coro_factory: Callable that returns a coroutine
            max_retries: Override default max retries
        """
        retries = max_retries or self.config.get('max_retries', 3)
        last_error = None

        for attempt in range(retries + 1):
            try:
                return await coro_factory()
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')

                # Don't retry on client errors (4xx)
                if error_code.startswith('4') and error_code not in [
                    'ThrottlingException', 'RequestLimitExceeded',
                    'ProvisionedThroughputExceededException'
                ]:
                    raise SkillExecutionError(
                        skill_name='aws',
                        method=operation,
                        reason=f"AWS error: {e.response['Error']['Message']}"
                    )

                last_error = e
                if attempt < retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"AWS {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
            except BotoCoreError as e:
                last_error = e
                if attempt < retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"AWS {operation} failed (attempt {attempt + 1}/{retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise SkillExecutionError(
            skill_name='aws',
            method=operation,
            reason=f"Failed after {retries + 1} attempts: {last_error}"
        )

    # =========================================================================
    # EC2 Operations
    # =========================================================================

    async def ec2_list_instances(
        self,
        filters: dict[str, Any] | None = None
    ) -> list[EC2Instance]:
        """
        List EC2 instances with optional filters.

        Args:
            filters: Optional filter dict. Examples:
                - {"instance-state-name": ["running"]}
                - {"tag:Environment": ["prod"]}
                - {"instance-type": ["t3.micro", "t3.small"]}

        Returns:
            List of EC2Instance dataclass objects
        """
        async def _list():
            async with self._get_client('ec2') as ec2:
                # Build AWS filters format
                aws_filters = []
                if filters:
                    for key, values in filters.items():
                        if not isinstance(values, list):
                            values = [values]
                        aws_filters.append({'Name': key, 'Values': values})

                kwargs = {}
                if aws_filters:
                    kwargs['Filters'] = aws_filters

                instances = []
                paginator = ec2.get_paginator('describe_instances')
                async for page in paginator.paginate(**kwargs):
                    for reservation in page.get('Reservations', []):
                        for instance in reservation.get('Instances', []):
                            # Extract name from tags
                            name = None
                            tags = {}
                            for tag in instance.get('Tags', []):
                                tags[tag['Key']] = tag['Value']
                                if tag['Key'] == 'Name':
                                    name = tag['Value']

                            instances.append(EC2Instance(
                                instance_id=instance['InstanceId'],
                                name=name,
                                state=instance['State']['Name'],
                                instance_type=instance['InstanceType'],
                                private_ip=instance.get('PrivateIpAddress'),
                                public_ip=instance.get('PublicIpAddress'),
                                availability_zone=instance['Placement']['AvailabilityZone'],
                                launch_time=instance.get('LaunchTime'),
                                tags=tags
                            ))

                return instances

        return await self._retry_with_backoff('ec2_list_instances', _list)

    async def ec2_get_instance(self, instance_id: str) -> EC2Instance | None:
        """
        Get details of a specific EC2 instance.

        Args:
            instance_id: The EC2 instance ID (e.g., "i-1234567890abcdef0")

        Returns:
            EC2Instance dataclass or None if not found
        """
        async def _get():
            async with self._get_client('ec2') as ec2:
                try:
                    response = await ec2.describe_instances(InstanceIds=[instance_id])
                except ClientError as e:
                    if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                        return None
                    raise

                for reservation in response.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        name = None
                        tags = {}
                        for tag in instance.get('Tags', []):
                            tags[tag['Key']] = tag['Value']
                            if tag['Key'] == 'Name':
                                name = tag['Value']

                        return EC2Instance(
                            instance_id=instance['InstanceId'],
                            name=name,
                            state=instance['State']['Name'],
                            instance_type=instance['InstanceType'],
                            private_ip=instance.get('PrivateIpAddress'),
                            public_ip=instance.get('PublicIpAddress'),
                            availability_zone=instance['Placement']['AvailabilityZone'],
                            launch_time=instance.get('LaunchTime'),
                            tags=tags
                        )

                return None

        return await self._retry_with_backoff('ec2_get_instance', _get)

    async def ec2_start_instance(self, instance_id: str) -> dict[str, Any]:
        """
        Start an EC2 instance.

        Args:
            instance_id: The EC2 instance ID to start

        Returns:
            Dict with start operation result
        """
        async def _start():
            async with self._get_client('ec2') as ec2:
                response = await ec2.start_instances(InstanceIds=[instance_id])
                state_changes = response.get('StartingInstances', [])

                if state_changes:
                    change = state_changes[0]
                    return {
                        'instance_id': change['InstanceId'],
                        'previous_state': change['PreviousState']['Name'],
                        'current_state': change['CurrentState']['Name'],
                        'success': True
                    }

                return {'instance_id': instance_id, 'success': False}

        return await self._retry_with_backoff('ec2_start_instance', _start)

    async def ec2_stop_instance(
        self,
        instance_id: str,
        force: bool = False
    ) -> dict[str, Any]:
        """
        Stop an EC2 instance.

        Args:
            instance_id: The EC2 instance ID to stop
            force: Force stop (hibernate if enabled, else terminate OS)

        Returns:
            Dict with stop operation result
        """
        async def _stop():
            async with self._get_client('ec2') as ec2:
                response = await ec2.stop_instances(
                    InstanceIds=[instance_id],
                    Force=force
                )
                state_changes = response.get('StoppingInstances', [])

                if state_changes:
                    change = state_changes[0]
                    return {
                        'instance_id': change['InstanceId'],
                        'previous_state': change['PreviousState']['Name'],
                        'current_state': change['CurrentState']['Name'],
                        'success': True
                    }

                return {'instance_id': instance_id, 'success': False}

        return await self._retry_with_backoff('ec2_stop_instance', _stop)

    # =========================================================================
    # ECS Operations
    # =========================================================================

    async def ecs_list_services(self, cluster: str) -> list[ECSService]:
        """
        List ECS services in a cluster.

        Args:
            cluster: ECS cluster name or ARN

        Returns:
            List of ECSService dataclass objects
        """
        async def _list():
            async with self._get_client('ecs') as ecs:
                services = []

                # First, list all service ARNs
                service_arns = []
                paginator = ecs.get_paginator('list_services')
                async for page in paginator.paginate(cluster=cluster):
                    service_arns.extend(page.get('serviceArns', []))

                # Then describe services in batches of 10
                for i in range(0, len(service_arns), 10):
                    batch = service_arns[i:i + 10]
                    response = await ecs.describe_services(
                        cluster=cluster,
                        services=batch
                    )

                    for svc in response.get('services', []):
                        services.append(ECSService(
                            service_name=svc['serviceName'],
                            cluster_arn=svc['clusterArn'],
                            status=svc['status'],
                            desired_count=svc['desiredCount'],
                            running_count=svc['runningCount'],
                            pending_count=svc['pendingCount'],
                            task_definition=svc['taskDefinition'],
                            launch_type=svc.get('launchType')
                        ))

                return services

        return await self._retry_with_backoff('ecs_list_services', _list)

    async def ecs_update_service(
        self,
        cluster: str,
        service: str,
        desired_count: int
    ) -> dict[str, Any]:
        """
        Update an ECS service (typically for scaling).

        Args:
            cluster: ECS cluster name or ARN
            service: ECS service name or ARN
            desired_count: New desired task count

        Returns:
            Dict with update result
        """
        async def _update():
            async with self._get_client('ecs') as ecs:
                response = await ecs.update_service(
                    cluster=cluster,
                    service=service,
                    desiredCount=desired_count
                )

                svc = response.get('service', {})
                return {
                    'service_name': svc.get('serviceName'),
                    'cluster_arn': svc.get('clusterArn'),
                    'desired_count': svc.get('desiredCount'),
                    'running_count': svc.get('runningCount'),
                    'status': svc.get('status'),
                    'success': True
                }

        return await self._retry_with_backoff('ecs_update_service', _update)

    # =========================================================================
    # Lambda Operations
    # =========================================================================

    async def lambda_invoke(
        self,
        function_name: str,
        payload: dict[str, Any] | None = None,
        invocation_type: str = 'RequestResponse'
    ) -> dict[str, Any]:
        """
        Invoke a Lambda function.

        Args:
            function_name: Lambda function name or ARN
            payload: JSON-serializable payload to send
            invocation_type: 'RequestResponse' (sync) or 'Event' (async)

        Returns:
            Dict with function response or invocation status
        """
        async def _invoke():
            async with self._get_client('lambda') as lambda_client:
                kwargs = {
                    'FunctionName': function_name,
                    'InvocationType': invocation_type
                }

                if payload:
                    kwargs['Payload'] = json.dumps(payload)

                response = await lambda_client.invoke(**kwargs)

                result = {
                    'function_name': function_name,
                    'status_code': response['StatusCode'],
                    'executed_version': response.get('ExecutedVersion'),
                    'success': 200 <= response['StatusCode'] < 300
                }

                # Read response payload for sync invocations
                if invocation_type == 'RequestResponse':
                    payload_stream = response.get('Payload')
                    if payload_stream:
                        payload_bytes = await payload_stream.read()
                        try:
                            result['response'] = json.loads(payload_bytes.decode('utf-8'))
                        except json.JSONDecodeError:
                            result['response'] = payload_bytes.decode('utf-8')

                if 'FunctionError' in response:
                    result['function_error'] = response['FunctionError']
                    result['success'] = False

                return result

        return await self._retry_with_backoff('lambda_invoke', _invoke)

    # =========================================================================
    # CloudWatch Operations
    # =========================================================================

    async def cloudwatch_get_metrics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        period: int = 300,
        statistic: str = 'Average'
    ) -> list[dict[str, Any]]:
        """
        Get CloudWatch metrics data.

        Args:
            namespace: CloudWatch namespace (e.g., 'AWS/EC2')
            metric_name: Metric name (e.g., 'CPUUtilization')
            dimensions: Dict of dimension name to value
            start_time: Start of time range (default: 1 hour ago)
            end_time: End of time range (default: now)
            period: Data point period in seconds (default: 300)
            statistic: Statistic type (Average, Sum, Minimum, Maximum, SampleCount)

        Returns:
            List of metric datapoints
        """
        async def _get():
            async with self._get_client('cloudwatch') as cw:
                now = datetime.now(timezone.utc)

                # Build dimensions list
                dim_list = []
                if dimensions:
                    for name, value in dimensions.items():
                        dim_list.append({'Name': name, 'Value': value})

                response = await cw.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=dim_list,
                    StartTime=start_time or (now - timedelta(hours=1)),
                    EndTime=end_time or now,
                    Period=period,
                    Statistics=[statistic]
                )

                datapoints = []
                for dp in response.get('Datapoints', []):
                    datapoints.append({
                        'timestamp': dp['Timestamp'].isoformat(),
                        'value': dp.get(statistic),
                        'unit': dp.get('Unit')
                    })

                # Sort by timestamp
                datapoints.sort(key=lambda x: x['timestamp'])
                return datapoints

        return await self._retry_with_backoff('cloudwatch_get_metrics', _get)

    async def cloudwatch_get_alarms(
        self,
        alarm_names: list[str] | None = None,
        state: str | None = None
    ) -> list[CloudWatchAlarm]:
        """
        List CloudWatch alarms.

        Args:
            alarm_names: Optional list of specific alarm names
            state: Filter by state (OK, ALARM, INSUFFICIENT_DATA)

        Returns:
            List of CloudWatchAlarm dataclass objects
        """
        async def _get():
            async with self._get_client('cloudwatch') as cw:
                alarms = []

                kwargs = {}
                if alarm_names:
                    kwargs['AlarmNames'] = alarm_names
                if state:
                    kwargs['StateValue'] = state

                paginator = cw.get_paginator('describe_alarms')
                async for page in paginator.paginate(**kwargs):
                    for alarm in page.get('MetricAlarms', []):
                        alarms.append(CloudWatchAlarm(
                            name=alarm['AlarmName'],
                            state=alarm['StateValue'],
                            metric_name=alarm['MetricName'],
                            namespace=alarm['Namespace'],
                            threshold=alarm['Threshold'],
                            comparison=alarm['ComparisonOperator'],
                            evaluation_periods=alarm['EvaluationPeriods'],
                            description=alarm.get('AlarmDescription')
                        ))

                return alarms

        return await self._retry_with_backoff('cloudwatch_get_alarms', _get)

    # =========================================================================
    # RDS Operations
    # =========================================================================

    async def rds_describe_instances(
        self,
        db_instance_id: str | None = None
    ) -> list[RDSInstance]:
        """
        Describe RDS database instances.

        Args:
            db_instance_id: Optional specific instance ID

        Returns:
            List of RDSInstance dataclass objects
        """
        async def _describe():
            async with self._get_client('rds') as rds:
                instances = []

                kwargs = {}
                if db_instance_id:
                    kwargs['DBInstanceIdentifier'] = db_instance_id

                paginator = rds.get_paginator('describe_db_instances')
                async for page in paginator.paginate(**kwargs):
                    for db in page.get('DBInstances', []):
                        endpoint = db.get('Endpoint', {})
                        instances.append(RDSInstance(
                            db_instance_id=db['DBInstanceIdentifier'],
                            db_instance_class=db['DBInstanceClass'],
                            engine=db['Engine'],
                            engine_version=db['EngineVersion'],
                            status=db['DBInstanceStatus'],
                            endpoint=endpoint.get('Address'),
                            port=endpoint.get('Port'),
                            availability_zone=db.get('AvailabilityZone'),
                            multi_az=db.get('MultiAZ', False)
                        ))

                return instances

        return await self._retry_with_backoff('rds_describe_instances', _describe)

    # =========================================================================
    # S3 Operations
    # =========================================================================

    async def s3_list_buckets(self) -> list[S3Bucket]:
        """
        List all S3 buckets.

        Returns:
            List of S3Bucket dataclass objects
        """
        async def _list():
            async with self._get_client('s3') as s3:
                response = await s3.list_buckets()

                buckets = []
                for bucket in response.get('Buckets', []):
                    buckets.append(S3Bucket(
                        name=bucket['Name'],
                        creation_date=bucket.get('CreationDate'),
                        region=None  # Would need additional call to get region
                    ))

                return buckets

        return await self._retry_with_backoff('s3_list_buckets', _list)

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check AWS connectivity by calling STS get-caller-identity.

        Returns:
            Dict with connection status and identity info
        """
        try:
            async with self._get_client('sts') as sts:
                response = await sts.get_caller_identity()
                return {
                    'status': 'connected',
                    'account': response['Account'],
                    'arn': response['Arn'],
                    'user_id': response['UserId'],
                    'region': self.config.get('region', 'default')
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'configured': bool(self._session_params)
            }
