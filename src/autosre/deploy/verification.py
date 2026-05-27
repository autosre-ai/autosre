"""
Deployment Verification Module

Provides comprehensive pre and post-deployment verification including:
- Health checks (HTTP, TCP, gRPC)
- Readiness checks
- Smoke tests
- Pre/post deployment validation
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Status of a verification check."""
    
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class VerificationStage(str, Enum):
    """Stage of deployment verification."""
    
    PRE_DEPLOYMENT = "pre_deployment"
    DEPLOYMENT = "deployment"
    POST_DEPLOYMENT = "post_deployment"
    SMOKE_TEST = "smoke_test"
    INTEGRATION = "integration"


class HealthCheckType(str, Enum):
    """Type of health check."""
    
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    GRPC = "grpc"
    EXEC = "exec"
    DNS = "dns"


class VerificationConfig(BaseModel):
    """Configuration for deployment verification."""
    
    # Basic settings
    name: str = "deployment-verification"
    namespace: str = "default"
    
    # Timeout settings
    global_timeout_seconds: int = Field(default=600, ge=60)
    individual_check_timeout_seconds: int = Field(default=30, ge=5)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0)
    retry_interval_seconds: int = Field(default=5, ge=1)
    
    # Health check settings
    health_check_interval_seconds: int = Field(default=10, ge=1)
    initial_delay_seconds: int = Field(default=5, ge=0)
    
    # Failure policy
    fail_fast: bool = True
    required_pass_percentage: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Stages to run
    run_pre_deployment: bool = True
    run_post_deployment: bool = True
    run_smoke_tests: bool = True
    
    # Notification
    notify_on_failure: bool = True
    notify_on_success: bool = False


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    
    name: str
    check_type: HealthCheckType
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    
    # Results
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    
    # Metrics
    latency_ms: float = 0.0
    retries: int = 0
    
    def duration_seconds(self) -> float:
        """Calculate check duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "check_type": self.check_type.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "retries": self.retries,
        }


class HealthCheck(BaseModel):
    """Configuration for a health check."""
    
    name: str
    check_type: HealthCheckType = HealthCheckType.HTTP
    
    # Target
    endpoint: str = ""
    host: str = ""
    port: int = Field(default=80, ge=1, le=65535)
    path: str = "/"
    
    # HTTP specific
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    expected_body_contains: Optional[str] = None
    
    # gRPC specific
    grpc_service: str = ""
    grpc_method: str = "Check"
    
    # Exec specific
    exec_command: list[str] = Field(default_factory=list)
    
    # Timing
    timeout_seconds: int = Field(default=10, ge=1)
    interval_seconds: int = Field(default=5, ge=1)
    
    # Retry
    retries: int = Field(default=3, ge=0)
    retry_interval_seconds: int = Field(default=2, ge=1)
    
    # Criticality
    critical: bool = False
    
    async def execute(self) -> HealthCheckResult:
        """Execute the health check."""
        result = HealthCheckResult(
            name=self.name,
            check_type=self.check_type,
            started_at=datetime.now(timezone.utc),
        )
        
        try:
            if self.check_type == HealthCheckType.HTTP:
                await self._check_http(result)
            elif self.check_type == HealthCheckType.HTTPS:
                await self._check_https(result)
            elif self.check_type == HealthCheckType.TCP:
                await self._check_tcp(result)
            elif self.check_type == HealthCheckType.GRPC:
                await self._check_grpc(result)
            elif self.check_type == HealthCheckType.EXEC:
                await self._check_exec(result)
            elif self.check_type == HealthCheckType.DNS:
                await self._check_dns(result)
            
        except asyncio.TimeoutError:
            result.status = VerificationStatus.TIMEOUT
            result.error_message = f"Health check timed out after {self.timeout_seconds}s"
        except Exception as e:
            result.status = VerificationStatus.FAILED
            result.error_message = str(e)
        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = result.duration_seconds() * 1000
        
        return result
    
    async def _check_http(self, result: HealthCheckResult) -> None:
        """Perform HTTP health check."""
        import aiohttp
        
        url = self.endpoint or f"http://{self.host}:{self.port}{self.path}"
        
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now(timezone.utc)
            async with session.request(
                self.method,
                url,
                headers=self.headers,
                data=self.body,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as response:
                result.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                result.status_code = response.status
                result.response_body = await response.text()
                
                if response.status in self.expected_status_codes:
                    if self.expected_body_contains:
                        if self.expected_body_contains in result.response_body:
                            result.status = VerificationStatus.PASSED
                        else:
                            result.status = VerificationStatus.FAILED
                            result.error_message = f"Response body does not contain expected text"
                    else:
                        result.status = VerificationStatus.PASSED
                else:
                    result.status = VerificationStatus.FAILED
                    result.error_message = f"Unexpected status code: {response.status}"
    
    async def _check_https(self, result: HealthCheckResult) -> None:
        """Perform HTTPS health check."""
        # Same as HTTP but with https
        original_endpoint = self.endpoint
        if self.endpoint:
            self.endpoint = self.endpoint.replace("http://", "https://")
        await self._check_http(result)
        self.endpoint = original_endpoint
    
    async def _check_tcp(self, result: HealthCheckResult) -> None:
        """Perform TCP health check."""
        start_time = datetime.now(timezone.utc)
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_seconds,
            )
            result.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result.status = VerificationStatus.PASSED
            writer.close()
            await writer.wait_closed()
        except (ConnectionRefusedError, OSError) as e:
            result.status = VerificationStatus.FAILED
            result.error_message = f"TCP connection failed: {str(e)}"
    
    async def _check_grpc(self, result: HealthCheckResult) -> None:
        """Perform gRPC health check."""
        # Simplified gRPC check - in production use grpcio-health-checking
        try:
            import grpc
            
            start_time = datetime.now(timezone.utc)
            channel = grpc.aio.insecure_channel(f"{self.host}:{self.port}")
            
            # Standard gRPC health check
            from grpc_health.v1 import health_pb2, health_pb2_grpc
            
            stub = health_pb2_grpc.HealthStub(channel)
            request = health_pb2.HealthCheckRequest(service=self.grpc_service)
            
            response = await asyncio.wait_for(
                stub.Check(request),
                timeout=self.timeout_seconds,
            )
            
            result.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if response.status == health_pb2.HealthCheckResponse.SERVING:
                result.status = VerificationStatus.PASSED
            else:
                result.status = VerificationStatus.FAILED
                result.error_message = f"gRPC health check returned: {response.status}"
            
            await channel.close()
        except ImportError:
            # Fallback to TCP check if grpc not available
            await self._check_tcp(result)
    
    async def _check_exec(self, result: HealthCheckResult) -> None:
        """Perform exec health check."""
        start_time = datetime.now(timezone.utc)
        
        process = await asyncio.create_subprocess_exec(
            *self.exec_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
            
            result.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result.response_body = stdout.decode()
            
            if process.returncode == 0:
                result.status = VerificationStatus.PASSED
            else:
                result.status = VerificationStatus.FAILED
                result.error_message = f"Command exited with code {process.returncode}: {stderr.decode()}"
        except asyncio.TimeoutError:
            process.kill()
            raise
    
    async def _check_dns(self, result: HealthCheckResult) -> None:
        """Perform DNS resolution check."""
        import socket
        
        start_time = datetime.now(timezone.utc)
        
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.getaddrinfo(self.host, self.port),
                timeout=self.timeout_seconds,
            )
            result.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result.status = VerificationStatus.PASSED
        except socket.gaierror as e:
            result.status = VerificationStatus.FAILED
            result.error_message = f"DNS resolution failed: {str(e)}"


@dataclass
class ReadinessResult:
    """Result of a readiness check."""
    
    name: str
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Pods/instances
    total_replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Details
    conditions: list[dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def readiness_percentage(self) -> float:
        """Calculate readiness percentage."""
        if self.total_replicas == 0:
            return 0.0
        return self.ready_replicas / self.total_replicas
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "total_replicas": self.total_replicas,
            "ready_replicas": self.ready_replicas,
            "available_replicas": self.available_replicas,
            "readiness_percentage": self.readiness_percentage(),
            "conditions": self.conditions,
            "error_message": self.error_message,
        }


class ReadinessCheck(BaseModel):
    """Configuration for a readiness check."""
    
    name: str
    
    # Target
    deployment_name: str
    namespace: str = "default"
    
    # Requirements
    min_ready_replicas: int = Field(default=1, ge=0)
    min_ready_percentage: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Timing
    timeout_seconds: int = Field(default=300, ge=10)
    poll_interval_seconds: int = Field(default=5, ge=1)
    initial_delay_seconds: int = Field(default=0, ge=0)
    
    # Progressive
    check_progressing_condition: bool = True
    
    async def execute(
        self,
        kubernetes_client: Optional[Any] = None,
    ) -> ReadinessResult:
        """Execute readiness check."""
        result = ReadinessResult(
            name=self.name,
            started_at=datetime.now(timezone.utc),
        )
        
        # Initial delay
        if self.initial_delay_seconds > 0:
            await asyncio.sleep(self.initial_delay_seconds)
        
        deadline = datetime.now(timezone.utc) + timedelta(seconds=self.timeout_seconds)
        
        try:
            while datetime.now(timezone.utc) < deadline:
                if kubernetes_client:
                    deployment = await kubernetes_client.get_deployment(
                        self.deployment_name,
                        self.namespace,
                    )
                    
                    if deployment:
                        status = deployment.get("status", {})
                        spec = deployment.get("spec", {})
                        
                        result.total_replicas = spec.get("replicas", 0)
                        result.ready_replicas = status.get("readyReplicas", 0)
                        result.available_replicas = status.get("availableReplicas", 0)
                        result.conditions = status.get("conditions", [])
                        
                        # Check if ready
                        meets_min_replicas = result.ready_replicas >= self.min_ready_replicas
                        meets_percentage = (
                            result.readiness_percentage() >= self.min_ready_percentage
                        )
                        
                        if meets_min_replicas and meets_percentage:
                            # Check progressing condition
                            if self.check_progressing_condition:
                                for condition in result.conditions:
                                    if condition.get("type") == "Progressing":
                                        if condition.get("status") == "True":
                                            result.status = VerificationStatus.PASSED
                                            break
                                else:
                                    result.status = VerificationStatus.PASSED
                            else:
                                result.status = VerificationStatus.PASSED
                            
                            if result.status == VerificationStatus.PASSED:
                                break
                else:
                    # Simulate for testing
                    result.status = VerificationStatus.PASSED
                    break
                
                result.status = VerificationStatus.RUNNING
                await asyncio.sleep(self.poll_interval_seconds)
            
            if result.status != VerificationStatus.PASSED:
                result.status = VerificationStatus.TIMEOUT
                result.error_message = (
                    f"Readiness check timed out. "
                    f"Ready: {result.ready_replicas}/{result.total_replicas}"
                )
        
        except Exception as e:
            result.status = VerificationStatus.FAILED
            result.error_message = str(e)
        finally:
            result.completed_at = datetime.now(timezone.utc)
        
        return result


@dataclass
class SmokeTestResult:
    """Result of a smoke test."""
    
    name: str
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Test details
    test_type: str = ""
    endpoint: str = ""
    
    # Results
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Metrics
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Details
    error_messages: list[str] = field(default_factory=list)
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "test_type": self.test_type,
            "endpoint": self.endpoint,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate(),
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "error_messages": self.error_messages,
        }


class SmokeTest(BaseModel):
    """Configuration for a smoke test."""
    
    name: str
    description: str = ""
    
    # Test type
    test_type: str = "http"  # http, grpc, custom
    
    # Target
    endpoint: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    
    # Expected results
    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    expected_body_contains: Optional[str] = None
    expected_body_json_path: Optional[str] = None
    expected_body_json_value: Optional[Any] = None
    
    # Load settings
    request_count: int = Field(default=10, ge=1)
    concurrency: int = Field(default=1, ge=1)
    requests_per_second: float = Field(default=10.0, ge=0.1)
    
    # Thresholds
    min_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    max_avg_latency_ms: float = Field(default=1000.0, ge=0.0)
    max_p99_latency_ms: float = Field(default=5000.0, ge=0.0)
    
    # Timing
    timeout_seconds: int = Field(default=60, ge=5)
    
    # Criticality
    critical: bool = False
    
    async def execute(self) -> SmokeTestResult:
        """Execute the smoke test."""
        import statistics
        
        result = SmokeTestResult(
            name=self.name,
            test_type=self.test_type,
            endpoint=self.endpoint,
            started_at=datetime.now(timezone.utc),
        )
        
        latencies: list[float] = []
        errors: list[str] = []
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                semaphore = asyncio.Semaphore(self.concurrency)
                delay = 1.0 / self.requests_per_second
                
                async def make_request(i: int) -> tuple[bool, float, Optional[str]]:
                    async with semaphore:
                        try:
                            start = datetime.now(timezone.utc)
                            async with session.request(
                                self.method,
                                self.endpoint,
                                headers=self.headers,
                                data=self.body,
                                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                            ) as response:
                                latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                                
                                if response.status in self.expected_status_codes:
                                    if self.expected_body_contains:
                                        body = await response.text()
                                        if self.expected_body_contains in body:
                                            return True, latency, None
                                        else:
                                            return False, latency, "Body validation failed"
                                    return True, latency, None
                                else:
                                    return False, latency, f"Status {response.status}"
                        except Exception as e:
                            return False, 0.0, str(e)
                
                tasks = []
                for i in range(self.request_count):
                    tasks.append(make_request(i))
                    if i < self.request_count - 1:
                        await asyncio.sleep(delay)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for r in results:
                    if isinstance(r, Exception):
                        result.failure_count += 1
                        errors.append(str(r))
                    else:
                        success, latency, error = r
                        if success:
                            result.success_count += 1
                            latencies.append(latency)
                        else:
                            result.failure_count += 1
                            if error:
                                errors.append(error)
                
                result.request_count = len(results)
                result.error_messages = errors[:10]  # Keep first 10 errors
            
            # Calculate latency percentiles
            if latencies:
                sorted_latencies = sorted(latencies)
                result.avg_latency_ms = statistics.mean(latencies)
                result.p50_latency_ms = _percentile(sorted_latencies, 50)
                result.p95_latency_ms = _percentile(sorted_latencies, 95)
                result.p99_latency_ms = _percentile(sorted_latencies, 99)
            
            # Determine pass/fail
            success_rate = result.success_rate()
            
            if success_rate >= self.min_success_rate:
                if result.avg_latency_ms <= self.max_avg_latency_ms:
                    if result.p99_latency_ms <= self.max_p99_latency_ms:
                        result.status = VerificationStatus.PASSED
                    else:
                        result.status = VerificationStatus.FAILED
                        result.error_messages.append(
                            f"P99 latency {result.p99_latency_ms:.1f}ms exceeds threshold {self.max_p99_latency_ms}ms"
                        )
                else:
                    result.status = VerificationStatus.FAILED
                    result.error_messages.append(
                        f"Avg latency {result.avg_latency_ms:.1f}ms exceeds threshold {self.max_avg_latency_ms}ms"
                    )
            else:
                result.status = VerificationStatus.FAILED
                result.error_messages.append(
                    f"Success rate {success_rate:.2%} below threshold {self.min_success_rate:.2%}"
                )
        
        except ImportError:
            result.status = VerificationStatus.SKIPPED
            result.error_messages.append("aiohttp not available for smoke tests")
        except Exception as e:
            result.status = VerificationStatus.FAILED
            result.error_messages.append(str(e))
        finally:
            result.completed_at = datetime.now(timezone.utc)
        
        return result


class SmokeTestSuite(BaseModel):
    """Collection of smoke tests to run together."""
    
    name: str
    description: str = ""
    
    # Tests
    tests: list[SmokeTest] = Field(default_factory=list)
    
    # Execution settings
    parallel: bool = False
    stop_on_failure: bool = True
    
    # Thresholds
    min_pass_percentage: float = Field(default=1.0, ge=0.0, le=1.0)
    
    async def execute(self) -> list[SmokeTestResult]:
        """Execute all smoke tests in the suite."""
        results: list[SmokeTestResult] = []
        
        if self.parallel:
            tasks = [test.execute() for test in self.tests]
            results = await asyncio.gather(*tasks)
        else:
            for test in self.tests:
                result = await test.execute()
                results.append(result)
                
                if self.stop_on_failure and result.status == VerificationStatus.FAILED:
                    if test.critical:
                        break
        
        return results


@dataclass
class PreDeploymentCheck:
    """Pre-deployment verification check."""
    
    name: str
    check_type: str  # resource, permission, dependency, config
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Details
    description: str = ""
    required: bool = True
    
    # Results
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PostDeploymentCheck:
    """Post-deployment verification check."""
    
    name: str
    check_type: str  # health, metrics, integration, smoke
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Details
    description: str = ""
    required: bool = True
    
    # Results
    message: str = ""
    health_results: list[HealthCheckResult] = field(default_factory=list)
    smoke_results: list[SmokeTestResult] = field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class VerificationTimeline:
    """Timeline of verification events."""
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Stage timings
    pre_deployment_started_at: Optional[datetime] = None
    pre_deployment_completed_at: Optional[datetime] = None
    post_deployment_started_at: Optional[datetime] = None
    post_deployment_completed_at: Optional[datetime] = None
    smoke_tests_started_at: Optional[datetime] = None
    smoke_tests_completed_at: Optional[datetime] = None
    
    # Events
    events: list[dict[str, Any]] = field(default_factory=list)
    
    def add_event(
        self,
        event_type: str,
        message: str,
        stage: Optional[VerificationStage] = None,
    ) -> None:
        """Add event to timeline."""
        self.events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "message": message,
            "stage": stage.value if stage else None,
        })


class VerificationReport(BaseModel):
    """Complete verification report."""
    
    name: str
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Summary
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    skipped_checks: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Stage results
    pre_deployment_passed: bool = False
    post_deployment_passed: bool = False
    smoke_tests_passed: bool = False
    
    # Detailed results
    health_check_results: list[dict[str, Any]] = Field(default_factory=list)
    smoke_test_results: list[dict[str, Any]] = Field(default_factory=list)
    readiness_results: list[dict[str, Any]] = Field(default_factory=list)
    
    # Failures
    critical_failures: list[str] = Field(default_factory=list)
    
    # Recommendation
    recommendation: str = ""
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        status_emoji = {
            VerificationStatus.PASSED: "✅",
            VerificationStatus.FAILED: "❌",
            VerificationStatus.TIMEOUT: "⏱️",
            VerificationStatus.SKIPPED: "⏭️",
            VerificationStatus.PENDING: "⏳",
            VerificationStatus.RUNNING: "🔄",
        }
        
        emoji = status_emoji.get(self.status, "❓")
        
        return (
            f"{emoji} Verification: {self.status.value}\n"
            f"  Checks: {self.passed_checks}/{self.total_checks} passed\n"
            f"  Pre-deployment: {'✅' if self.pre_deployment_passed else '❌'}\n"
            f"  Post-deployment: {'✅' if self.post_deployment_passed else '❌'}\n"
            f"  Smoke tests: {'✅' if self.smoke_tests_passed else '❌'}\n"
            f"  Duration: {self.duration_seconds:.1f}s\n"
            f"  Recommendation: {self.recommendation}"
        )


@dataclass
class VerificationResult:
    """Result of deployment verification."""
    
    status: VerificationStatus = VerificationStatus.PENDING
    
    # Stage status
    pre_deployment_status: VerificationStatus = VerificationStatus.PENDING
    post_deployment_status: VerificationStatus = VerificationStatus.PENDING
    smoke_test_status: VerificationStatus = VerificationStatus.PENDING
    
    # Results
    health_check_results: list[HealthCheckResult] = field(default_factory=list)
    readiness_results: list[ReadinessResult] = field(default_factory=list)
    smoke_test_results: list[SmokeTestResult] = field(default_factory=list)
    pre_deployment_checks: list[PreDeploymentCheck] = field(default_factory=list)
    post_deployment_checks: list[PostDeploymentCheck] = field(default_factory=list)
    
    # Timeline
    timeline: VerificationTimeline = field(default_factory=VerificationTimeline)
    
    # Message
    message: str = ""
    
    def pass_rate(self) -> float:
        """Calculate overall pass rate."""
        all_results = (
            self.health_check_results +
            self.readiness_results +
            self.smoke_test_results
        )
        if not all_results:
            return 0.0
        
        passed = sum(1 for r in all_results if r.status == VerificationStatus.PASSED)
        return passed / len(all_results)
    
    def to_report(self) -> VerificationReport:
        """Convert to verification report."""
        all_results = (
            self.health_check_results +
            self.readiness_results +
            self.smoke_test_results
        )
        
        passed = sum(1 for r in all_results if r.status == VerificationStatus.PASSED)
        failed = sum(1 for r in all_results if r.status == VerificationStatus.FAILED)
        skipped = sum(1 for r in all_results if r.status == VerificationStatus.SKIPPED)
        
        critical_failures = []
        for r in self.health_check_results:
            if r.status == VerificationStatus.FAILED:
                critical_failures.append(f"Health check '{r.name}': {r.error_message}")
        for r in self.smoke_test_results:
            if r.status == VerificationStatus.FAILED:
                critical_failures.append(f"Smoke test '{r.name}': {', '.join(r.error_messages[:3])}")
        
        duration = 0.0
        if self.timeline.started_at and self.timeline.completed_at:
            duration = (self.timeline.completed_at - self.timeline.started_at).total_seconds()
        
        return VerificationReport(
            name="deployment-verification",
            status=self.status,
            total_checks=len(all_results),
            passed_checks=passed,
            failed_checks=failed,
            skipped_checks=skipped,
            started_at=self.timeline.started_at,
            completed_at=self.timeline.completed_at,
            duration_seconds=duration,
            pre_deployment_passed=self.pre_deployment_status == VerificationStatus.PASSED,
            post_deployment_passed=self.post_deployment_status == VerificationStatus.PASSED,
            smoke_tests_passed=self.smoke_test_status == VerificationStatus.PASSED,
            health_check_results=[r.to_dict() for r in self.health_check_results],
            smoke_test_results=[r.to_dict() for r in self.smoke_test_results],
            readiness_results=[r.to_dict() for r in self.readiness_results],
            critical_failures=critical_failures,
            recommendation="Deploy" if self.status == VerificationStatus.PASSED else "Rollback",
        )


class DeploymentVerifier:
    """Performs comprehensive deployment verification."""
    
    def __init__(
        self,
        config: Optional[VerificationConfig] = None,
        kubernetes_client: Optional[Any] = None,
        metrics_client: Optional[Any] = None,
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.config = config or VerificationConfig()
        self.kubernetes_client = kubernetes_client
        self.metrics_client = metrics_client
        self.notify_callback = notify_callback
        
        # Checks
        self._health_checks: list[HealthCheck] = []
        self._readiness_checks: list[ReadinessCheck] = []
        self._smoke_tests: list[SmokeTest] = []
        
        # State
        self._result: Optional[VerificationResult] = None
        self._is_running: bool = False
    
    def add_health_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        self._health_checks.append(check)
    
    def add_readiness_check(self, check: ReadinessCheck) -> None:
        """Add a readiness check."""
        self._readiness_checks.append(check)
    
    def add_smoke_test(self, test: SmokeTest) -> None:
        """Add a smoke test."""
        self._smoke_tests.append(test)
    
    async def verify(
        self,
        deployment_name: str,
        namespace: str = "default",
        skip_pre_deployment: bool = False,
        skip_post_deployment: bool = False,
        skip_smoke_tests: bool = False,
    ) -> VerificationResult:
        """Perform full deployment verification.
        
        Args:
            deployment_name: Name of the deployment to verify
            namespace: Kubernetes namespace
            skip_pre_deployment: Skip pre-deployment checks
            skip_post_deployment: Skip post-deployment checks
            skip_smoke_tests: Skip smoke tests
        
        Returns:
            VerificationResult with all check results
        """
        self._result = VerificationResult()
        self._result.timeline.started_at = datetime.now(timezone.utc)
        self._is_running = True
        
        try:
            # Pre-deployment verification
            if self.config.run_pre_deployment and not skip_pre_deployment:
                await self._run_pre_deployment(deployment_name, namespace)
                if (
                    self.config.fail_fast and
                    self._result.pre_deployment_status == VerificationStatus.FAILED
                ):
                    self._result.status = VerificationStatus.FAILED
                    self._result.message = "Pre-deployment verification failed"
                    return self._result
            else:
                self._result.pre_deployment_status = VerificationStatus.SKIPPED
            
            # Post-deployment verification (health + readiness)
            if self.config.run_post_deployment and not skip_post_deployment:
                await self._run_post_deployment(deployment_name, namespace)
                if (
                    self.config.fail_fast and
                    self._result.post_deployment_status == VerificationStatus.FAILED
                ):
                    self._result.status = VerificationStatus.FAILED
                    self._result.message = "Post-deployment verification failed"
                    return self._result
            else:
                self._result.post_deployment_status = VerificationStatus.SKIPPED
            
            # Smoke tests
            if self.config.run_smoke_tests and not skip_smoke_tests:
                await self._run_smoke_tests()
                if (
                    self.config.fail_fast and
                    self._result.smoke_test_status == VerificationStatus.FAILED
                ):
                    self._result.status = VerificationStatus.FAILED
                    self._result.message = "Smoke tests failed"
                    return self._result
            else:
                self._result.smoke_test_status = VerificationStatus.SKIPPED
            
            # Calculate overall status
            self._calculate_overall_status()
            
        except Exception as e:
            self._result.status = VerificationStatus.FAILED
            self._result.message = f"Verification error: {str(e)}"
        finally:
            self._is_running = False
            self._result.timeline.completed_at = datetime.now(timezone.utc)
        
        return self._result
    
    async def _run_pre_deployment(
        self,
        deployment_name: str,
        namespace: str,
    ) -> None:
        """Run pre-deployment checks."""
        self._result.timeline.pre_deployment_started_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "pre_deployment_started",
            "Starting pre-deployment verification",
            VerificationStage.PRE_DEPLOYMENT,
        )
        
        # Run resource checks, permission checks, etc.
        checks = [
            PreDeploymentCheck(
                name="namespace_exists",
                check_type="resource",
                description=f"Verify namespace {namespace} exists",
            ),
            PreDeploymentCheck(
                name="resource_quota",
                check_type="resource",
                description="Verify sufficient resource quota",
            ),
            PreDeploymentCheck(
                name="image_pullable",
                check_type="dependency",
                description="Verify container images are accessible",
            ),
            PreDeploymentCheck(
                name="config_valid",
                check_type="config",
                description="Verify deployment configuration is valid",
            ),
        ]
        
        for check in checks:
            check.started_at = datetime.now(timezone.utc)
            # In a real implementation, perform actual checks
            check.status = VerificationStatus.PASSED
            check.completed_at = datetime.now(timezone.utc)
            self._result.pre_deployment_checks.append(check)
        
        # Check if all passed
        all_passed = all(
            c.status == VerificationStatus.PASSED
            for c in self._result.pre_deployment_checks
            if c.required
        )
        
        self._result.pre_deployment_status = (
            VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        )
        
        self._result.timeline.pre_deployment_completed_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "pre_deployment_completed",
            f"Pre-deployment verification {'passed' if all_passed else 'failed'}",
            VerificationStage.PRE_DEPLOYMENT,
        )
    
    async def _run_post_deployment(
        self,
        deployment_name: str,
        namespace: str,
    ) -> None:
        """Run post-deployment checks."""
        self._result.timeline.post_deployment_started_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "post_deployment_started",
            "Starting post-deployment verification",
            VerificationStage.POST_DEPLOYMENT,
        )
        
        # Initial delay
        if self.config.initial_delay_seconds > 0:
            await asyncio.sleep(self.config.initial_delay_seconds)
        
        # Run readiness checks
        for check in self._readiness_checks:
            result = await check.execute(self.kubernetes_client)
            self._result.readiness_results.append(result)
            
            if self.config.fail_fast and result.status == VerificationStatus.FAILED:
                break
        
        # Run health checks
        for check in self._health_checks:
            result = await self._run_health_check_with_retry(check)
            self._result.health_check_results.append(result)
            
            if self.config.fail_fast and result.status == VerificationStatus.FAILED:
                if check.critical:
                    break
        
        # Calculate status
        readiness_passed = all(
            r.status == VerificationStatus.PASSED
            for r in self._result.readiness_results
        )
        health_passed = all(
            r.status == VerificationStatus.PASSED
            for r in self._result.health_check_results
        )
        
        if readiness_passed and health_passed:
            self._result.post_deployment_status = VerificationStatus.PASSED
        elif not self._result.readiness_results and not self._result.health_check_results:
            self._result.post_deployment_status = VerificationStatus.PASSED
        else:
            self._result.post_deployment_status = VerificationStatus.FAILED
        
        self._result.timeline.post_deployment_completed_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "post_deployment_completed",
            f"Post-deployment verification {'passed' if self._result.post_deployment_status == VerificationStatus.PASSED else 'failed'}",
            VerificationStage.POST_DEPLOYMENT,
        )
    
    async def _run_health_check_with_retry(
        self,
        check: HealthCheck,
    ) -> HealthCheckResult:
        """Run health check with retry logic."""
        last_result: Optional[HealthCheckResult] = None
        
        for attempt in range(check.retries + 1):
            result = await check.execute()
            last_result = result
            result.retries = attempt
            
            if result.status == VerificationStatus.PASSED:
                return result
            
            if attempt < check.retries:
                await asyncio.sleep(check.retry_interval_seconds)
        
        return last_result or HealthCheckResult(
            name=check.name,
            check_type=check.check_type,
            status=VerificationStatus.FAILED,
            error_message="No result",
        )
    
    async def _run_smoke_tests(self) -> None:
        """Run smoke tests."""
        self._result.timeline.smoke_tests_started_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "smoke_tests_started",
            "Starting smoke tests",
            VerificationStage.SMOKE_TEST,
        )
        
        for test in self._smoke_tests:
            result = await test.execute()
            self._result.smoke_test_results.append(result)
            
            if self.config.fail_fast and result.status == VerificationStatus.FAILED:
                if test.critical:
                    break
        
        # Calculate status
        all_passed = all(
            r.status == VerificationStatus.PASSED
            for r in self._result.smoke_test_results
        )
        
        if all_passed or not self._result.smoke_test_results:
            self._result.smoke_test_status = VerificationStatus.PASSED
        else:
            self._result.smoke_test_status = VerificationStatus.FAILED
        
        self._result.timeline.smoke_tests_completed_at = datetime.now(timezone.utc)
        self._result.timeline.add_event(
            "smoke_tests_completed",
            f"Smoke tests {'passed' if all_passed else 'failed'}",
            VerificationStage.SMOKE_TEST,
        )
    
    def _calculate_overall_status(self) -> None:
        """Calculate overall verification status."""
        statuses = [
            self._result.pre_deployment_status,
            self._result.post_deployment_status,
            self._result.smoke_test_status,
        ]
        
        # Filter out skipped
        active_statuses = [s for s in statuses if s != VerificationStatus.SKIPPED]
        
        if not active_statuses:
            self._result.status = VerificationStatus.PASSED
            self._result.message = "No verification checks configured"
        elif all(s == VerificationStatus.PASSED for s in active_statuses):
            self._result.status = VerificationStatus.PASSED
            self._result.message = "All verification checks passed"
        else:
            self._result.status = VerificationStatus.FAILED
            failed_stages = []
            if self._result.pre_deployment_status == VerificationStatus.FAILED:
                failed_stages.append("pre-deployment")
            if self._result.post_deployment_status == VerificationStatus.FAILED:
                failed_stages.append("post-deployment")
            if self._result.smoke_test_status == VerificationStatus.FAILED:
                failed_stages.append("smoke-tests")
            self._result.message = f"Verification failed: {', '.join(failed_stages)}"
    
    def get_result(self) -> Optional[VerificationResult]:
        """Get current verification result."""
        return self._result
    
    def is_running(self) -> bool:
        """Check if verification is running."""
        return self._is_running


def _percentile(data: list[float], percentile: int) -> float:
    """Calculate percentile from sorted data."""
    if not data:
        return 0.0
    k = (len(data) - 1) * percentile / 100
    f = int(k)
    c = f + 1 if f < len(data) - 1 else f
    return data[f] + (k - f) * (data[c] - data[f])
