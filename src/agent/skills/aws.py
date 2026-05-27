"""AWS investigation tools for SRE agents.

Provides tools for investigating AWS infrastructure:
- EC2 instances
- RDS databases
- CloudWatch metrics
- ECS services
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from langchain_core.tools import BaseTool, tool

from .base import BaseSRETool, SREToolError

logger = logging.getLogger(__name__)


@dataclass
class AWSConfig:
    """Configuration for AWS client."""
    
    region: str = "us-east-1"
    profile: Optional[str] = None
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> "AWSConfig":
        """Create config from environment variables."""
        return cls(
            region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
            profile=os.getenv("AWS_PROFILE"),
            timeout_seconds=int(os.getenv("AWS_TIMEOUT", "30")),
        )


class AWSTools(BaseSRETool):
    """AWS infrastructure investigation tools.
    
    Uses AWS CLI for maximum compatibility. Also supports boto3 if available.
    """
    
    name = "aws"
    description = "AWS infrastructure investigation tools"
    
    def __init__(
        self,
        config: Optional[AWSConfig] = None,
        mock_mode: bool = False,
    ):
        """Initialize AWS tools.
        
        Args:
            config: AWS configuration.
            mock_mode: If True, return mock data.
        """
        super().__init__(mock_mode=mock_mode)
        self.config = config or AWSConfig.from_env()
        self._aws_cli_available: Optional[bool] = None
        self._boto3_available: Optional[bool] = None
    
    def _check_aws_cli(self) -> bool:
        """Check if AWS CLI is available."""
        if self._aws_cli_available is None:
            try:
                subprocess.run(
                    ["aws", "--version"],
                    capture_output=True,
                    timeout=5,
                )
                self._aws_cli_available = True
            except (subprocess.SubprocessError, FileNotFoundError):
                self._aws_cli_available = False
        return self._aws_cli_available
    
    def _check_boto3(self) -> bool:
        """Check if boto3 is available."""
        if self._boto3_available is None:
            try:
                import boto3
                self._boto3_available = True
            except ImportError:
                self._boto3_available = False
        return self._boto3_available
    
    def _build_aws_cmd(self, service: str, command: str, *args: str) -> list[str]:
        """Build AWS CLI command."""
        cmd = ["aws", service, command, "--region", self.config.region, "--output", "json"]
        if self.config.profile:
            cmd.extend(["--profile", self.config.profile])
        cmd.extend(args)
        return cmd
    
    def _run_aws_cli(self, service: str, command: str, *args: str) -> dict[str, Any]:
        """Run AWS CLI command and return parsed output."""
        if not self._check_aws_cli():
            raise SREToolError("AWS CLI is not available", recoverable=False)
        
        cmd = self._build_aws_cmd(service, command, *args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
            
            if result.returncode != 0:
                raise SREToolError(f"AWS CLI failed: {result.stderr.strip()}")
            
            if result.stdout.strip():
                return json.loads(result.stdout)
            return {}
            
        except subprocess.TimeoutExpired:
            raise SREToolError(f"AWS CLI timed out after {self.config.timeout_seconds}s")
        except json.JSONDecodeError as e:
            raise SREToolError(f"Failed to parse AWS CLI output: {e}")
    
    def get_tools(self) -> list[BaseTool]:
        """Return list of AWS tools."""
        return [
            self._make_describe_ec2_tool(),
            self._make_describe_rds_tool(),
            self._make_get_cloudwatch_metrics_tool(),
            self._make_describe_ecs_services_tool(),
        ]
    
    def _make_describe_ec2_tool(self) -> BaseTool:
        """Create describe_ec2 tool."""
        parent = self
        
        @tool
        def describe_ec2(
            instance_ids: str = "",
            filters: str = "",
            state: str = "",
        ) -> str:
            """Describe EC2 instances.
            
            Args:
                instance_ids: Comma-separated instance IDs (e.g., 'i-1234,i-5678').
                filters: Comma-separated filters (e.g., 'tag:Name=web-*,tag:env=prod').
                state: Filter by instance state ('running', 'stopped', 'terminated').
                
            Returns:
                JSON with EC2 instance details including state, IPs, and tags.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("describe_ec2", {
                    "instances": [
                        {
                            "instanceId": "i-1234567890abcdef0",
                            "instanceType": "t3.medium",
                            "state": "running",
                            "privateIp": "10.0.1.100",
                            "publicIp": "54.123.45.67",
                            "tags": {"Name": "web-server-1", "env": "prod"},
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                args = []
                
                if instance_ids:
                    args.extend(["--instance-ids"] + instance_ids.split(","))
                
                filter_list = []
                if filters:
                    for f in filters.split(","):
                        if "=" in f:
                            key, value = f.split("=", 1)
                            filter_list.append(f"Name={key},Values={value}")
                
                if state:
                    filter_list.append(f"Name=instance-state-name,Values={state}")
                
                if filter_list:
                    args.extend(["--filters"] + filter_list)
                
                result = parent._run_aws_cli("ec2", "describe-instances", *args)
                
                # Format instances
                instances = []
                for reservation in result.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                        
                        # Get security groups
                        security_groups = [
                            {"id": sg.get("GroupId"), "name": sg.get("GroupName")}
                            for sg in instance.get("SecurityGroups", [])
                        ]
                        
                        instances.append({
                            "instanceId": instance.get("InstanceId"),
                            "instanceType": instance.get("InstanceType"),
                            "state": instance.get("State", {}).get("Name"),
                            "launchTime": instance.get("LaunchTime"),
                            "privateIp": instance.get("PrivateIpAddress"),
                            "publicIp": instance.get("PublicIpAddress"),
                            "vpcId": instance.get("VpcId"),
                            "subnetId": instance.get("SubnetId"),
                            "availabilityZone": instance.get("Placement", {}).get("AvailabilityZone"),
                            "tags": tags,
                            "securityGroups": security_groups,
                            "iamRole": instance.get("IamInstanceProfile", {}).get("Arn", "").split("/")[-1] if instance.get("IamInstanceProfile") else None,
                        })
                
                return json.dumps({"instances": instances, "count": len(instances)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return describe_ec2
    
    def _make_describe_rds_tool(self) -> BaseTool:
        """Create describe_rds tool."""
        parent = self
        
        @tool
        def describe_rds(
            db_instance_id: str = "",
            db_cluster_id: str = "",
        ) -> str:
            """Describe RDS database instances and clusters.
            
            Args:
                db_instance_id: Specific DB instance identifier (optional).
                db_cluster_id: Specific DB cluster identifier for Aurora (optional).
                
            Returns:
                JSON with RDS instance/cluster details including status and endpoints.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("describe_rds", {
                    "instances": [
                        {
                            "dbInstanceId": "prod-db-1",
                            "engine": "postgres",
                            "engineVersion": "14.9",
                            "status": "available",
                            "endpoint": "prod-db-1.xxx.us-east-1.rds.amazonaws.com",
                            "port": 5432,
                            "instanceClass": "db.r5.large",
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                results = {"instances": [], "clusters": []}
                
                # Get DB instances
                instance_args = []
                if db_instance_id:
                    instance_args.extend(["--db-instance-identifier", db_instance_id])
                
                try:
                    instances_result = parent._run_aws_cli("rds", "describe-db-instances", *instance_args)
                    
                    for db in instances_result.get("DBInstances", []):
                        endpoint = db.get("Endpoint", {})
                        results["instances"].append({
                            "dbInstanceId": db.get("DBInstanceIdentifier"),
                            "engine": db.get("Engine"),
                            "engineVersion": db.get("EngineVersion"),
                            "status": db.get("DBInstanceStatus"),
                            "endpoint": endpoint.get("Address"),
                            "port": endpoint.get("Port"),
                            "instanceClass": db.get("DBInstanceClass"),
                            "allocatedStorage": db.get("AllocatedStorage"),
                            "multiAz": db.get("MultiAZ"),
                            "availabilityZone": db.get("AvailabilityZone"),
                            "vpcId": db.get("DBSubnetGroup", {}).get("VpcId"),
                            "storageType": db.get("StorageType"),
                            "storageEncrypted": db.get("StorageEncrypted"),
                            "iops": db.get("Iops"),
                            "clusterIdentifier": db.get("DBClusterIdentifier"),
                        })
                except SREToolError:
                    pass  # May not have instances
                
                # Get DB clusters (Aurora)
                cluster_args = []
                if db_cluster_id:
                    cluster_args.extend(["--db-cluster-identifier", db_cluster_id])
                
                try:
                    clusters_result = parent._run_aws_cli("rds", "describe-db-clusters", *cluster_args)
                    
                    for cluster in clusters_result.get("DBClusters", []):
                        results["clusters"].append({
                            "clusterId": cluster.get("DBClusterIdentifier"),
                            "engine": cluster.get("Engine"),
                            "engineVersion": cluster.get("EngineVersion"),
                            "status": cluster.get("Status"),
                            "endpoint": cluster.get("Endpoint"),
                            "readerEndpoint": cluster.get("ReaderEndpoint"),
                            "port": cluster.get("Port"),
                            "multiAz": cluster.get("MultiAZ"),
                            "members": [
                                {
                                    "instanceId": m.get("DBInstanceIdentifier"),
                                    "isWriter": m.get("IsClusterWriter"),
                                }
                                for m in cluster.get("DBClusterMembers", [])
                            ],
                            "storageEncrypted": cluster.get("StorageEncrypted"),
                            "allocatedStorage": cluster.get("AllocatedStorage"),
                        })
                except SREToolError:
                    pass  # May not have clusters
                
                return json.dumps(results, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return describe_rds
    
    def _make_get_cloudwatch_metrics_tool(self) -> BaseTool:
        """Create get_cloudwatch_metrics tool."""
        parent = self
        
        @tool
        def get_cloudwatch_metrics(
            namespace: str,
            metric_name: str,
            dimensions: str = "",
            statistic: str = "Average",
            period: int = 300,
            time_range: str = "1h",
        ) -> str:
            """Get CloudWatch metrics.
            
            Args:
                namespace: CloudWatch namespace (e.g., 'AWS/EC2', 'AWS/RDS', 'AWS/ECS').
                metric_name: Metric name (e.g., 'CPUUtilization', 'DatabaseConnections').
                dimensions: Comma-separated dimensions (e.g., 'InstanceId=i-123,Name=Value').
                statistic: Statistic type ('Average', 'Sum', 'Maximum', 'Minimum', 'SampleCount').
                period: Data point period in seconds (60, 300, 3600).
                time_range: Time range (e.g., '1h', '6h', '1d').
                
            Returns:
                JSON with metric datapoints.
                
            Common metrics:
                EC2: CPUUtilization, NetworkIn, NetworkOut, DiskReadOps, StatusCheckFailed
                RDS: CPUUtilization, DatabaseConnections, FreeStorageSpace, ReadLatency
                ECS: CPUUtilization, MemoryUtilization
                ALB: RequestCount, TargetResponseTime, HTTPCode_Target_5XX_Count
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_cloudwatch_metrics", {
                    "namespace": namespace,
                    "metricName": metric_name,
                    "datapoints": [
                        {"timestamp": "2024-01-15T10:00:00Z", "value": 45.2, "unit": "Percent"},
                        {"timestamp": "2024-01-15T10:05:00Z", "value": 47.8, "unit": "Percent"},
                    ],
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                # Calculate time range
                now = datetime.now(timezone.utc)
                duration_map = {"m": 1, "h": 60, "d": 1440}
                unit = time_range[-1]
                value = int(time_range[:-1])
                minutes = value * duration_map.get(unit, 60)
                start_time = (now - timedelta(minutes=minutes)).isoformat() + "Z"
                end_time = now.isoformat() + "Z"
                
                # Build dimensions
                dim_args = []
                if dimensions:
                    for dim in dimensions.split(","):
                        if "=" in dim:
                            name, val = dim.split("=", 1)
                            dim_args.extend(["--dimensions", f"Name={name},Value={val}"])
                
                args = [
                    "--namespace", namespace,
                    "--metric-name", metric_name,
                    "--start-time", start_time,
                    "--end-time", end_time,
                    "--period", str(period),
                    "--statistics", statistic,
                ] + dim_args
                
                result = parent._run_aws_cli("cloudwatch", "get-metric-statistics", *args)
                
                # Format datapoints
                datapoints = []
                for dp in result.get("Datapoints", []):
                    datapoints.append({
                        "timestamp": dp.get("Timestamp"),
                        "value": dp.get(statistic),
                        "unit": dp.get("Unit"),
                    })
                
                # Sort by timestamp
                datapoints.sort(key=lambda x: x["timestamp"] or "")
                
                # Calculate summary
                values = [dp["value"] for dp in datapoints if dp["value"] is not None]
                summary = {}
                if values:
                    summary = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "latest": values[-1] if values else None,
                    }
                
                return json.dumps({
                    "namespace": namespace,
                    "metricName": metric_name,
                    "dimensions": dimensions,
                    "statistic": statistic,
                    "period": period,
                    "datapoints": datapoints,
                    "summary": summary,
                }, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return get_cloudwatch_metrics
    
    def _make_describe_ecs_services_tool(self) -> BaseTool:
        """Create describe_ecs_services tool."""
        parent = self
        
        @tool
        def describe_ecs_services(
            cluster: str,
            services: str = "",
        ) -> str:
            """Describe ECS services in a cluster.
            
            Args:
                cluster: ECS cluster name or ARN.
                services: Comma-separated service names (optional, lists all if empty).
                
            Returns:
                JSON with ECS service details including task counts and deployments.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("describe_ecs_services", {
                    "services": [
                        {
                            "serviceName": "api-service",
                            "status": "ACTIVE",
                            "desiredCount": 3,
                            "runningCount": 3,
                            "pendingCount": 0,
                            "taskDefinition": "api-task:42",
                            "deployments": [
                                {"status": "PRIMARY", "runningCount": 3, "desiredCount": 3}
                            ],
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                # If no services specified, list all services first
                service_list = []
                if services:
                    service_list = services.split(",")
                else:
                    # List services in cluster
                    list_result = parent._run_aws_cli(
                        "ecs", "list-services",
                        "--cluster", cluster,
                    )
                    service_arns = list_result.get("serviceArns", [])
                    # Get service names from ARNs
                    service_list = [arn.split("/")[-1] for arn in service_arns]
                
                if not service_list:
                    return json.dumps({"services": [], "message": "No services found in cluster"})
                
                # Describe services (max 10 at a time)
                all_services = []
                for i in range(0, len(service_list), 10):
                    batch = service_list[i:i+10]
                    result = parent._run_aws_cli(
                        "ecs", "describe-services",
                        "--cluster", cluster,
                        "--services", *batch,
                    )
                    
                    for svc in result.get("services", []):
                        deployments = []
                        for dep in svc.get("deployments", []):
                            deployments.append({
                                "id": dep.get("id"),
                                "status": dep.get("status"),
                                "taskDefinition": dep.get("taskDefinition", "").split("/")[-1],
                                "desiredCount": dep.get("desiredCount"),
                                "runningCount": dep.get("runningCount"),
                                "pendingCount": dep.get("pendingCount"),
                                "failedTasks": dep.get("failedTasks", 0),
                                "createdAt": dep.get("createdAt"),
                            })
                        
                        # Get load balancers
                        load_balancers = [
                            {
                                "targetGroupArn": lb.get("targetGroupArn"),
                                "containerName": lb.get("containerName"),
                                "containerPort": lb.get("containerPort"),
                            }
                            for lb in svc.get("loadBalancers", [])
                        ]
                        
                        all_services.append({
                            "serviceName": svc.get("serviceName"),
                            "serviceArn": svc.get("serviceArn"),
                            "status": svc.get("status"),
                            "taskDefinition": svc.get("taskDefinition", "").split("/")[-1],
                            "desiredCount": svc.get("desiredCount"),
                            "runningCount": svc.get("runningCount"),
                            "pendingCount": svc.get("pendingCount"),
                            "launchType": svc.get("launchType"),
                            "deployments": deployments,
                            "loadBalancers": load_balancers,
                            "events": [
                                {
                                    "createdAt": e.get("createdAt"),
                                    "message": e.get("message"),
                                }
                                for e in svc.get("events", [])[:5]  # Last 5 events
                            ],
                        })
                
                return json.dumps({
                    "cluster": cluster,
                    "services": all_services,
                    "count": len(all_services),
                }, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return describe_ecs_services


# Convenience function to get all AWS tools
def get_aws_tools(
    config: Optional[AWSConfig] = None,
    mock_mode: bool = False,
) -> list[BaseTool]:
    """Get all AWS investigation tools.
    
    Args:
        config: AWS configuration.
        mock_mode: If True, return mock data.
        
    Returns:
        List of LangChain tools.
    """
    aws = AWSTools(config=config, mock_mode=mock_mode)
    return aws.get_tools()
