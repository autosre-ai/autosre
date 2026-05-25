# Deployment Safety Guide

This guide covers AutoSRE's deployment safety features for implementing safe, controlled deployments with verification, gates, and automated rollback.

## Overview

AutoSRE provides a comprehensive deployment safety module with four key components:

1. **Canary Analysis** - Compare new versions against baselines using statistical methods
2. **Automated Rollback** - Automatic rollback based on metrics and health checks
3. **Deployment Verification** - Health checks, readiness checks, and smoke tests
4. **Deployment Gates** - Approval, metric, time, and manual gates for controlled rollouts

## Quick Start

```python
from autosre.deploy import (
    # Verification
    DeploymentVerifier,
    VerificationConfig,
    HealthCheck,
    HealthCheckType,
    SmokeTest,
    ReadinessCheck,
    # Gates
    DeploymentGate,
    GateConfig,
    ApprovalGate,
    ApprovalConfig,
    MetricGate,
    MetricGateConfig,
    TimeGate,
    TimeGateConfig,
    GatePipeline,
    GatePolicy,
    # Canary
    CanaryAnalyzer,
    CanaryConfig,
    # Rollback
    RollbackManager,
    RollbackConfig,
    AutoRollbackPolicy,
)
```

## Deployment Verification

### Health Checks

Health checks verify that your service is responding correctly after deployment.

```python
# Create verifier
verifier = DeploymentVerifier(
    config=VerificationConfig(
        name="my-deployment-verification",
        global_timeout_seconds=600,
        fail_fast=True,
    )
)

# Add HTTP health check
verifier.add_health_check(HealthCheck(
    name="api-health",
    check_type=HealthCheckType.HTTP,
    endpoint="http://my-service:8080/health",
    expected_status_codes=[200],
    timeout_seconds=10,
    retries=3,
    critical=True,
))

# Add TCP health check
verifier.add_health_check(HealthCheck(
    name="db-connectivity",
    check_type=HealthCheckType.TCP,
    host="postgres.default.svc",
    port=5432,
    timeout_seconds=5,
))

# Add gRPC health check
verifier.add_health_check(HealthCheck(
    name="grpc-service",
    check_type=HealthCheckType.GRPC,
    host="grpc-service.default.svc",
    port=50051,
    grpc_service="myapp.MyService",
))

# Run verification
result = await verifier.verify(
    deployment_name="my-app",
    namespace="production",
)

if result.status == VerificationStatus.PASSED:
    print("Deployment verified successfully!")
else:
    print(f"Verification failed: {result.message}")
```

### Readiness Checks

Readiness checks ensure pods are ready to serve traffic.

```python
verifier.add_readiness_check(ReadinessCheck(
    name="pods-ready",
    deployment_name="my-app",
    namespace="production",
    min_ready_replicas=3,
    min_ready_percentage=1.0,
    timeout_seconds=300,
    poll_interval_seconds=5,
))
```

### Smoke Tests

Smoke tests verify critical functionality after deployment.

```python
# Add smoke test for API endpoint
verifier.add_smoke_test(SmokeTest(
    name="api-smoke-test",
    endpoint="http://my-service:8080/api/v1/status",
    method="GET",
    expected_status_codes=[200],
    expected_body_contains="healthy",
    request_count=10,
    concurrency=2,
    min_success_rate=1.0,
    max_avg_latency_ms=500,
    max_p99_latency_ms=1000,
    critical=True,
))

# Add smoke test for critical path
verifier.add_smoke_test(SmokeTest(
    name="checkout-flow",
    endpoint="http://my-service:8080/api/v1/cart/validate",
    method="POST",
    headers={"Content-Type": "application/json"},
    body='{"test": true}',
    expected_status_codes=[200, 201],
    request_count=5,
    min_success_rate=1.0,
))
```

### Complete Verification Pipeline

```python
async def verify_deployment(deployment_name: str, namespace: str):
    """Run complete deployment verification."""
    
    verifier = DeploymentVerifier(
        config=VerificationConfig(
            run_pre_deployment=True,
            run_post_deployment=True,
            run_smoke_tests=True,
            fail_fast=True,
        )
    )
    
    # Add all checks
    verifier.add_health_check(HealthCheck(...))
    verifier.add_readiness_check(ReadinessCheck(...))
    verifier.add_smoke_test(SmokeTest(...))
    
    # Run verification
    result = await verifier.verify(deployment_name, namespace)
    
    # Generate report
    report = result.to_report()
    print(report.generate_summary())
    
    return result
```

## Deployment Gates

### Approval Gates

Require manual approval before deploying to production.

```python
# Configure approval gate
approval_gate = ApprovalGate(
    config=ApprovalConfig(
        approvers=["lead@example.com", "oncall@example.com"],
        min_approvers=2,
        require_different_approvers=True,
        approval_timeout_seconds=3600,  # 1 hour
        auto_approve_for_rollback=True,
    ),
    gate_config=GateConfig(
        name="production-approval",
        notify_on_pending=True,
    ),
)

# Evaluate gate
result = await approval_gate.evaluate({
    "deployment_name": "my-app",
    "namespace": "production",
    "requested_by": "developer@example.com",
    "version": "v2.1.0",
    "change_description": "Add new payment provider",
    "risk_level": "medium",
})

if result.status == GateStatus.APPROVED:
    print(f"Approved by: {result.approver}")
elif result.status == GateStatus.DENIED:
    print(f"Denied: {result.message}")
```

### Metric Gates

Ensure metrics meet thresholds before proceeding.

```python
metric_gate = MetricGate(
    config=MetricGateConfig(
        conditions=[
            MetricCondition(
                metric="error_rate",
                operator="<=",
                threshold=0.01,  # 1% max error rate
                required=True,
            ),
            MetricCondition(
                metric="success_rate",
                operator=">=",
                threshold=0.99,  # 99% min success rate
                required=True,
            ),
            MetricCondition(
                metric="latency_p99",
                operator="<=",
                threshold=500,  # 500ms max p99 latency
                required=False,
            ),
        ],
        require_all_conditions=True,
        min_evaluation_duration_seconds=300,
    ),
    metrics_client=prometheus_client,
)

result = await metric_gate.evaluate({
    "deployment_name": "my-app",
    "namespace": "production",
})
```

### Time Gates

Control when deployments can occur.

```python
time_gate = TimeGate(
    config=TimeGateConfig(
        enforce_business_hours=True,
        business_hours_start="09:00",
        business_hours_end="17:00",
        business_days=[0, 1, 2, 3, 4],  # Monday-Friday
        freeze_periods=[
            {
                "start": "2024-12-20T00:00:00",
                "end": "2024-12-27T00:00:00",
                "reason": "Holiday freeze",
            },
        ],
    ),
)

result = await time_gate.evaluate({})
if result.status == GateStatus.DENIED:
    print(f"Cannot deploy: {result.message}")
```

### Manual Gates

Require explicit manual confirmation.

```python
manual_gate = ManualGate(
    config=ManualGateConfig(
        prompt_message="Confirm deployment to production?",
        require_confirmation_text=True,
        confirmation_text="DEPLOY",
        checklist=[
            "Database migrations completed",
            "Feature flags configured",
            "Rollback plan reviewed",
        ],
        runbook_url="https://docs.example.com/runbook/deploy",
    ),
)
```

### Gate Pipelines

Chain multiple gates together.

```python
# Create gate pipeline
pipeline = GatePipeline(
    name="production-deployment-pipeline",
    policy=GatePolicy(
        enforce_all_gates=True,
        sequential=True,
    ),
)

# Add stages
pipeline.add_stage(
    name="time-check",
    gate=DeploymentGate(GateConfig(name="time-gate")),
    required=True,
)

pipeline.add_stage(
    name="metric-validation",
    gate=DeploymentGate(GateConfig(name="metric-gate")),
    required=True,
    depends_on=["time-check"],
)

pipeline.add_stage(
    name="approval",
    gate=DeploymentGate(GateConfig(name="approval-gate")),
    required=True,
    depends_on=["metric-validation"],
)

# Execute pipeline
result = await pipeline.execute({
    "deployment_name": "my-app",
    "namespace": "production",
    "requested_by": "developer@example.com",
})

print(f"Pipeline result: {result.status.value}")
print(f"Passed: {result.passed_stages}/{result.total_stages}")
```

## Canary Analysis

### Basic Canary Deployment

```python
analyzer = CanaryAnalyzer(
    config=CanaryConfig(
        name="my-app-canary",
        canary_service="my-app-canary",
        baseline_service="my-app-stable",
        warmup_duration_seconds=60,
        analysis_duration_seconds=300,
        initial_weight=10,
        max_weight=50,
        success_threshold=0.95,
        auto_promote=True,
        auto_rollback_on_failure=True,
    ),
    metrics_client=prometheus_client,
    traffic_manager=istio_client,
)

# Run analysis
result = await analyzer.analyze()

if result.verdict == CanaryVerdict.PASS:
    print("Canary passed! Safe to promote.")
elif result.verdict == CanaryVerdict.FAIL:
    print(f"Canary failed: {result.message}")
```

### Custom Metrics

```python
from autosre.deploy import CanaryMetric, TestType

# Add custom metric
analyzer.add_metric(CanaryMetric(
    name="checkout_success_rate",
    query='sum(rate(checkout_completed_total[5m])) / sum(rate(checkout_started_total[5m]))',
    direction="higher_is_better",
    threshold_value=0.05,  # Max 5% degradation
    test_type=TestType.MANN_WHITNEY,
    is_critical=True,
))
```

## Automated Rollback

### Configure Rollback Manager

```python
rollback_manager = RollbackManager(
    config=RollbackConfig(
        strategy=RollbackStrategy.GRADUAL,
        gradual_steps=[75, 50, 25, 0],
        step_interval_seconds=30,
        verify_after_rollback=True,
        notify_on_trigger=True,
        notify_on_complete=True,
    ),
    policy=AutoRollbackPolicy(
        max_error_rate=0.05,
        max_latency_p99_ms=5000,
        min_success_rate=0.95,
        evaluation_window_seconds=300,
        enable_circuit_breaker=True,
        circuit_breaker_threshold=3,
    ),
    kubernetes_client=k8s_client,
    metrics_client=prometheus_client,
)
```

### Automatic Rollback Triggers

```python
from autosre.deploy import RollbackTrigger, TriggerCondition

# Add custom triggers
rollback_manager.policy.triggers.append(
    RollbackTrigger(
        id="high-error-rate",
        name="High Error Rate",
        metric_query='sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))',
        condition=TriggerCondition.GREATER_THAN,
        threshold=0.1,
        duration_seconds=60,
        priority=1,
        strategy=RollbackStrategy.IMMEDIATE,
    )
)

# Start monitoring
await rollback_manager.start_monitoring(
    deployment_name="my-app",
    namespace="production",
    interval_seconds=30,
)
```

### Manual Rollback

```python
result = await rollback_manager.rollback(
    deployment_name="my-app",
    namespace="production",
    reason=RollbackReason.MANUAL,
    target_version="v2.0.5",
    strategy=RollbackStrategy.IMMEDIATE,
)

if result.success:
    print(f"Rollback completed in {result.execution.duration_seconds():.1f}s")
else:
    print(f"Rollback failed: {result.message}")
```

## Complete Safe Deployment Flow

Here's a complete example combining all safety features:

```python
async def safe_deploy(
    deployment_name: str,
    namespace: str,
    new_version: str,
    deployer: str,
) -> bool:
    """Execute a safe deployment with full verification and gates."""
    
    # 1. Pre-deployment gates
    pipeline = GatePipeline(
        name="pre-deployment",
        policy=GatePolicy(enforce_all_gates=True),
    )
    
    # Add time gate
    time_gate = DeploymentGate(GateConfig(name="time-check"))
    time_gate.set_time_gate(TimeGate(TimeGateConfig(
        enforce_business_hours=True,
    )))
    pipeline.add_stage("time-check", time_gate)
    
    # Add approval gate
    approval_gate = DeploymentGate(GateConfig(name="approval"))
    approval_gate.set_approval_gate(ApprovalGate(ApprovalConfig(
        approvers=["lead@example.com"],
        min_approvers=1,
    )))
    pipeline.add_stage("approval", approval_gate, depends_on=["time-check"])
    
    # Execute gates
    gate_result = await pipeline.execute({
        "deployment_name": deployment_name,
        "namespace": namespace,
        "requested_by": deployer,
        "version": new_version,
    })
    
    if gate_result.status != GateStatus.APPROVED:
        print(f"Gates failed: {gate_result.message}")
        return False
    
    # 2. Deploy canary
    print("Deploying canary...")
    # ... deploy canary pods ...
    
    # 3. Canary analysis
    analyzer = CanaryAnalyzer(
        config=CanaryConfig(
            analysis_duration_seconds=300,
            auto_promote=False,
            auto_rollback_on_failure=True,
        ),
    )
    
    canary_result = await analyzer.analyze()
    
    if canary_result.verdict != CanaryVerdict.PASS:
        print(f"Canary failed: {canary_result.message}")
        return False
    
    # 4. Full deployment
    print("Promoting to full deployment...")
    # ... deploy all pods ...
    
    # 5. Post-deployment verification
    verifier = DeploymentVerifier()
    verifier.add_health_check(HealthCheck(
        name="health",
        check_type=HealthCheckType.HTTP,
        endpoint=f"http://{deployment_name}:8080/health",
        critical=True,
    ))
    verifier.add_smoke_test(SmokeTest(
        name="api-smoke",
        endpoint=f"http://{deployment_name}:8080/api/v1/status",
        request_count=10,
        min_success_rate=1.0,
    ))
    
    verify_result = await verifier.verify(deployment_name, namespace)
    
    if verify_result.status != VerificationStatus.PASSED:
        print(f"Verification failed: {verify_result.message}")
        # Trigger rollback
        rollback_mgr = RollbackManager()
        await rollback_mgr.rollback(
            deployment_name,
            namespace,
            reason=RollbackReason.HEALTH_CHECK_FAILURE,
        )
        return False
    
    # 6. Start rollback monitoring
    rollback_mgr = RollbackManager(
        policy=AutoRollbackPolicy(
            max_error_rate=0.05,
            min_success_rate=0.95,
        ),
    )
    
    asyncio.create_task(rollback_mgr.start_monitoring(
        deployment_name,
        namespace,
    ))
    
    print(f"Deployment {new_version} successful!")
    return True
```

## Best Practices

### 1. Layered Safety

Always implement multiple layers of safety:

```
Pre-deployment Gates
       ↓
  Canary Analysis
       ↓
Post-deployment Verification
       ↓
Continuous Rollback Monitoring
```

### 2. Progressive Rollouts

Use gradual traffic shifting:

```python
CanaryConfig(
    initial_weight=5,      # Start with 5% traffic
    weight_increment=10,   # Increase by 10%
    max_weight=50,         # Max 50% before promotion
)
```

### 3. Critical Metrics

Mark critical metrics to fail fast:

```python
HealthCheck(
    name="database",
    critical=True,  # Fail immediately if this fails
)

CanaryMetric(
    name="error_rate",
    is_critical=True,  # Stop canary immediately
)
```

### 4. Timeout Configuration

Set appropriate timeouts:

```python
VerificationConfig(
    global_timeout_seconds=600,       # 10 min overall
    individual_check_timeout_seconds=30,  # 30s per check
)

ApprovalConfig(
    approval_timeout_seconds=3600,    # 1 hour for approval
)
```

### 5. Notification Integration

Always configure notifications:

```python
GateConfig(
    notify_on_pending=True,
    notify_on_result=True,
    notification_channels=["slack", "pagerduty"],
)
```

## Troubleshooting

### Verification Failures

1. Check health check endpoints are accessible
2. Verify network policies allow traffic
3. Increase timeouts for slow-starting services
4. Check readiness probe configuration matches

### Gate Timeouts

1. Verify approvers are notified
2. Check escalation configuration
3. Consider auto-approval for low-risk changes

### Canary Analysis Issues

1. Ensure sufficient sample size
2. Check metric queries return data
3. Adjust thresholds based on baseline variance
4. Extend analysis duration for low-traffic services

### Rollback Failures

1. Verify previous version is still deployable
2. Check resource quotas
3. Ensure rollback strategy matches deployment type
4. Verify Kubernetes permissions

## API Reference

For detailed API documentation, see:

- [Verification API](../reference/api.md#verification)
- [Gates API](../reference/api.md#gates)
- [Canary API](../reference/api.md#canary)
- [Rollback API](../reference/api.md#rollback)
