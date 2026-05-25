"""
Pre-built Workflow Templates

Common SRE workflow templates that can be used as starting points:
- Incident Response
- Auto-scaling
- Deployment Rollback
- Health Check
- Chaos Engineering
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml

from autosre.workflows.dsl import WorkflowDefinition, WorkflowParser


@dataclass
class WorkflowTemplate:
    """
    A workflow template that can be instantiated with parameters.
    
    Templates provide:
    - Pre-built workflow structure
    - Customizable parameters
    - Best practices baked in
    """
    id: str
    name: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    yaml_template: str = ""
    
    def instantiate(
        self, overrides: Optional[Dict[str, Any]] = None
    ) -> WorkflowDefinition:
        """
        Create a WorkflowDefinition from this template.
        
        Args:
            overrides: Parameter overrides to apply
        
        Returns:
            WorkflowDefinition ready for registration
        """
        # Merge parameters with overrides
        params = {**self.parameters, **(overrides or {})}
        
        # Render template with parameters
        rendered = self.yaml_template
        for key, value in params.items():
            placeholder = f"${{{key}}}"
            rendered = rendered.replace(placeholder, str(value))
        
        # Parse into WorkflowDefinition
        parser = WorkflowParser()
        return parser.parse(rendered)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "parameters": self.parameters,
        }


class TemplateRegistry:
    """Registry of workflow templates."""

    def __init__(self):
        self._templates: Dict[str, WorkflowTemplate] = {}

    def register(self, template: WorkflowTemplate) -> None:
        """Register a template."""
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[WorkflowTemplate]:
        """List templates with optional filtering."""
        templates = list(self._templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if tags:
            templates = [
                t for t in templates
                if any(tag in t.tags for tag in tags)
            ]
        
        return templates

    def categories(self) -> List[str]:
        """Get list of all categories."""
        return list(set(t.category for t in self._templates.values()))


# Pre-built templates

INCIDENT_RESPONSE_TEMPLATE = WorkflowTemplate(
    id="incident-response",
    name="Incident Response",
    description="Automated incident response workflow with triage, investigation, and remediation",
    category="incident-management",
    tags=["incident", "response", "automation", "on-call"],
    parameters={
        "service_name": "my-service",
        "slack_channel": "#incidents",
        "pagerduty_service": "default",
        "investigation_timeout": 300,
    },
    yaml_template="""
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: incident-response
  version: 1.0.0
  description: Automated incident response workflow
  author: AutoSRE
  tags:
    - incident
    - response
spec:
  inputs:
    - name: alert_id
      type: string
      required: true
      description: Alert ID that triggered this incident
    - name: severity
      type: string
      required: true
      enum: [critical, high, medium, low]
    - name: service
      type: string
      default: ${service_name}
    - name: namespace
      type: string
      default: default
      
  triggers:
    - type: alert
      severity: [critical, high]
      
  steps:
    # Step 1: Create incident record
    - name: Create Incident
      id: create_incident
      action: incident.create
      inputs:
        alert_id: ${{ inputs.alert_id }}
        severity: ${{ inputs.severity }}
        service: ${{ inputs.service }}
      outputs:
        - incident_id
        
    # Step 2: Notify team
    - name: Notify Team
      id: notify
      action: slack.post_message
      inputs:
        channel: ${slack_channel}
        message: |
          :rotating_light: *Incident Created*
          *ID:* ${{ steps.create_incident.output.incident_id }}
          *Severity:* ${{ inputs.severity }}
          *Service:* ${{ inputs.service }}
          *Alert:* ${{ inputs.alert_id }}
      continueOnError: true
      
    # Step 3: Gather context in parallel
    - name: Gather Context
      id: gather_context
      type: parallel
      steps:
        - name: Get Pod Status
          action: kubernetes.get_pods
          inputs:
            namespace: ${{ inputs.namespace }}
            label_selector: app=${{ inputs.service }}
            
        - name: Get Recent Metrics
          action: prometheus.query_range
          inputs:
            query: rate(http_requests_total{service="${service_name}"}[5m])
            duration: 30m
            
        - name: Get Recent Logs
          action: logs.search
          inputs:
            service: ${{ inputs.service }}
            timerange: 30m
            level: error
            
        - name: Get Recent Deployments
          action: kubernetes.get_deployments
          inputs:
            namespace: ${{ inputs.namespace }}
            
    # Step 4: AI-powered investigation
    - name: Investigate
      id: investigate
      action: autosre.investigate
      timeout: ${investigation_timeout}
      inputs:
        incident_id: ${{ steps.create_incident.output.incident_id }}
        context:
          pods: ${{ steps.gather_context.output.get_pod_status }}
          metrics: ${{ steps.gather_context.output.get_recent_metrics }}
          logs: ${{ steps.gather_context.output.get_recent_logs }}
          deployments: ${{ steps.gather_context.output.get_recent_deployments }}
      outputs:
        - root_cause
        - confidence
        - remediation_steps
        
    # Step 5: Auto-remediate if confidence is high
    - name: Auto-Remediate
      id: remediate
      if: steps.investigate.output.confidence > 0.8
      type: condition
      then:
        - name: Execute Remediation
          action: remediation.execute
          inputs:
            steps: ${{ steps.investigate.output.remediation_steps }}
            incident_id: ${{ steps.create_incident.output.incident_id }}
      else:
        - name: Escalate to Human
          action: pagerduty.create_incident
          inputs:
            service: ${pagerduty_service}
            title: "Manual review needed: ${{ steps.create_incident.output.incident_id }}"
            body: |
              Automated investigation complete but confidence too low for auto-remediation.
              Root cause hypothesis: ${{ steps.investigate.output.root_cause }}
              Confidence: ${{ steps.investigate.output.confidence }}
              
    # Step 6: Update incident status
    - name: Update Incident
      action: incident.update
      inputs:
        incident_id: ${{ steps.create_incident.output.incident_id }}
        status: investigating
        investigation_result: ${{ steps.investigate.output }}
        
  onSuccess:
    - name: Close Notification
      action: slack.post_message
      inputs:
        channel: ${slack_channel}
        message: ":white_check_mark: Incident workflow completed successfully"
        
  onFailure:
    - name: Alert Failure
      action: slack.post_message
      inputs:
        channel: ${slack_channel}
        message: ":x: Incident workflow failed - manual intervention required"
"""
)


SCALING_TEMPLATE = WorkflowTemplate(
    id="auto-scaling",
    name="Auto-Scaling Response",
    description="Automated scaling workflow triggered by resource pressure",
    category="capacity-management",
    tags=["scaling", "capacity", "kubernetes", "automation"],
    parameters={
        "min_replicas": 2,
        "max_replicas": 20,
        "scale_up_threshold": 80,
        "scale_down_threshold": 30,
        "cooldown_minutes": 5,
    },
    yaml_template="""
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: auto-scaling-response
  version: 1.0.0
  description: Automated scaling response workflow
spec:
  inputs:
    - name: namespace
      type: string
      required: true
    - name: deployment
      type: string
      required: true
    - name: metric_value
      type: number
      required: true
      description: Current utilization percentage
    - name: direction
      type: string
      enum: [up, down]
      
  triggers:
    - type: alert
      alert_names:
        - HighCPUUtilization
        - HighMemoryUtilization
        - LowResourceUtilization
        
  steps:
    # Check cooldown
    - name: Check Cooldown
      id: check_cooldown
      action: state.get
      inputs:
        key: scaling_cooldown_${{ inputs.namespace }}_${{ inputs.deployment }}
        
    - name: Cooldown Active
      if: steps.check_cooldown.output != null
      action: log.info
      inputs:
        message: "Scaling in cooldown, skipping"
      # Will skip remaining steps due to condition below
      
    # Get current state
    - name: Get Current Replicas
      id: get_replicas
      if: steps.check_cooldown.output == null
      action: kubernetes.get_deployment
      inputs:
        namespace: ${{ inputs.namespace }}
        name: ${{ inputs.deployment }}
      outputs:
        - current_replicas
        
    # Calculate new replicas
    - name: Calculate Scale
      id: calculate
      if: steps.check_cooldown.output == null
      action: math.scale_replicas
      inputs:
        current: ${{ steps.get_replicas.output.current_replicas }}
        direction: ${{ inputs.direction }}
        metric_value: ${{ inputs.metric_value }}
        min: ${min_replicas}
        max: ${max_replicas}
        up_threshold: ${scale_up_threshold}
        down_threshold: ${scale_down_threshold}
      outputs:
        - new_replicas
        - should_scale
        
    # Execute scaling
    - name: Scale Deployment
      if: steps.calculate.output.should_scale == true
      action: kubernetes.scale
      inputs:
        namespace: ${{ inputs.namespace }}
        deployment: ${{ inputs.deployment }}
        replicas: ${{ steps.calculate.output.new_replicas }}
        
    # Set cooldown
    - name: Set Cooldown
      if: steps.calculate.output.should_scale == true
      action: state.set
      inputs:
        key: scaling_cooldown_${{ inputs.namespace }}_${{ inputs.deployment }}
        value: true
        ttl: ${cooldown_minutes}m
        
    # Notify
    - name: Notify Scaling
      if: steps.calculate.output.should_scale == true
      action: slack.post_message
      inputs:
        channel: "#platform-alerts"
        message: |
          :chart_with_upwards_trend: *Scaling Event*
          Deployment: ${{ inputs.namespace }}/${{ inputs.deployment }}
          Direction: ${{ inputs.direction }}
          ${{ steps.get_replicas.output.current_replicas }} → ${{ steps.calculate.output.new_replicas }} replicas
      continueOnError: true
"""
)


DEPLOYMENT_ROLLBACK_TEMPLATE = WorkflowTemplate(
    id="deployment-rollback",
    name="Deployment Rollback",
    description="Automated deployment rollback workflow",
    category="deployment",
    tags=["deployment", "rollback", "kubernetes", "safety"],
    parameters={
        "error_rate_threshold": 5,
        "latency_threshold_ms": 1000,
        "evaluation_window": "5m",
    },
    yaml_template="""
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: deployment-rollback
  version: 1.0.0
  description: Automated deployment rollback on degradation
spec:
  inputs:
    - name: namespace
      type: string
      required: true
    - name: deployment
      type: string
      required: true
    - name: alert_type
      type: string
      description: Type of degradation detected
      
  triggers:
    - type: alert
      alert_names:
        - DeploymentDegradation
        - HighErrorRate
        - HighLatency
        
  steps:
    # Get deployment info
    - name: Get Deployment
      id: get_deployment
      action: kubernetes.get_deployment
      inputs:
        namespace: ${{ inputs.namespace }}
        name: ${{ inputs.deployment }}
        
    # Check if recent deployment
    - name: Check Recent Deploy
      id: check_recent
      action: kubernetes.get_rollout_history
      inputs:
        namespace: ${{ inputs.namespace }}
        deployment: ${{ inputs.deployment }}
        limit: 2
        
    # Verify degradation with metrics
    - name: Verify Degradation
      id: verify
      type: parallel
      steps:
        - name: Check Error Rate
          action: prometheus.query
          inputs:
            query: |
              sum(rate(http_requests_total{status=~"5..", deployment="${inputs.deployment}"}[${evaluation_window}])) /
              sum(rate(http_requests_total{deployment="${inputs.deployment}"}[${evaluation_window}])) * 100
              
        - name: Check Latency
          action: prometheus.query
          inputs:
            query: |
              histogram_quantile(0.99, 
                sum(rate(http_request_duration_seconds_bucket{deployment="${inputs.deployment}"}[${evaluation_window}])) by (le)
              ) * 1000
              
    # Decision: rollback or not
    - name: Evaluate Rollback
      id: evaluate
      type: condition
      if: |
        steps.verify.output.check_error_rate > ${error_rate_threshold} or
        steps.verify.output.check_latency > ${latency_threshold_ms}
      then:
        # Notify before rollback
        - name: Notify Rollback Start
          action: slack.post_message
          inputs:
            channel: "#deployments"
            message: |
              :warning: *Initiating Rollback*
              Deployment: ${{ inputs.namespace }}/${{ inputs.deployment }}
              Reason: ${{ inputs.alert_type }}
              Error rate: ${{ steps.verify.output.check_error_rate }}%
              P99 latency: ${{ steps.verify.output.check_latency }}ms
              
        # Execute rollback
        - name: Rollback
          id: rollback
          action: kubernetes.rollback
          inputs:
            namespace: ${{ inputs.namespace }}
            deployment: ${{ inputs.deployment }}
            revision: ${{ steps.check_recent.output.revisions[1].revision }}
            
        # Wait for rollout
        - name: Wait for Rollout
          action: kubernetes.wait_rollout
          inputs:
            namespace: ${{ inputs.namespace }}
            deployment: ${{ inputs.deployment }}
            timeout: 300
            
        # Verify recovery
        - name: Verify Recovery
          action: prometheus.query
          inputs:
            query: |
              sum(rate(http_requests_total{status=~"5..", deployment="${inputs.deployment}"}[2m])) /
              sum(rate(http_requests_total{deployment="${inputs.deployment}"}[2m])) * 100
              
        # Notify completion
        - name: Notify Complete
          action: slack.post_message
          inputs:
            channel: "#deployments"
            message: |
              :white_check_mark: *Rollback Complete*
              Deployment: ${{ inputs.namespace }}/${{ inputs.deployment }}
              Rolled back to revision: ${{ steps.check_recent.output.revisions[1].revision }}
              
      else:
        - name: Log No Action
          action: log.info
          inputs:
            message: "Degradation within acceptable limits, no rollback needed"
            
  onFailure:
    - name: Alert Rollback Failure
      action: pagerduty.create_incident
      inputs:
        service: platform
        urgency: high
        title: "Rollback failed: ${{ inputs.namespace }}/${{ inputs.deployment }}"
"""
)


HEALTH_CHECK_TEMPLATE = WorkflowTemplate(
    id="health-check",
    name="Comprehensive Health Check",
    description="Periodic health check workflow for service validation",
    category="observability",
    tags=["health", "monitoring", "validation"],
    parameters={
        "check_interval": "5m",
        "failure_threshold": 3,
    },
    yaml_template="""
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: health-check
  version: 1.0.0
  description: Comprehensive service health check
spec:
  inputs:
    - name: service
      type: string
      required: true
    - name: namespace
      type: string
      default: default
    - name: endpoints
      type: array
      description: List of endpoints to check
      
  triggers:
    - type: schedule
      cron: "*/5 * * * *"  # Every 5 minutes
      
  steps:
    # Check all endpoints in parallel
    - name: Check Endpoints
      id: check_endpoints
      type: loop
      forEach: ${{ inputs.endpoints }}
      itemVar: endpoint
      steps:
        - name: HTTP Health Check
          action: http.request
          inputs:
            url: ${{ endpoint.url }}
            method: GET
            timeout: 10
            expected_status: 200
          retries: 2
          retryDelay: 5
          
    # Check Kubernetes resources
    - name: Check K8s Resources
      id: check_k8s
      type: parallel
      steps:
        - name: Check Pods
          action: kubernetes.get_pods
          inputs:
            namespace: ${{ inputs.namespace }}
            label_selector: app=${{ inputs.service }}
            
        - name: Check Services
          action: kubernetes.get_service
          inputs:
            namespace: ${{ inputs.namespace }}
            name: ${{ inputs.service }}
            
        - name: Check Endpoints Object
          action: kubernetes.get_endpoints
          inputs:
            namespace: ${{ inputs.namespace }}
            name: ${{ inputs.service }}
            
    # Evaluate health
    - name: Evaluate Health
      id: evaluate
      action: health.evaluate
      inputs:
        endpoint_results: ${{ steps.check_endpoints.output }}
        pod_status: ${{ steps.check_k8s.output.check_pods }}
        service_status: ${{ steps.check_k8s.output.check_services }}
        endpoints_status: ${{ steps.check_k8s.output.check_endpoints_object }}
      outputs:
        - health_score
        - issues
        - status
        
    # Alert if unhealthy
    - name: Alert Unhealthy
      if: steps.evaluate.output.status == "unhealthy"
      action: alert.fire
      inputs:
        name: ServiceUnhealthy
        severity: high
        service: ${{ inputs.service }}
        message: |
          Service health check failed.
          Health score: ${{ steps.evaluate.output.health_score }}
          Issues: ${{ steps.evaluate.output.issues }}
          
    # Record metrics
    - name: Record Metrics
      action: prometheus.push_metrics
      inputs:
        metrics:
          - name: service_health_score
            value: ${{ steps.evaluate.output.health_score }}
            labels:
              service: ${{ inputs.service }}
              namespace: ${{ inputs.namespace }}
"""
)


CHAOS_ENGINEERING_TEMPLATE = WorkflowTemplate(
    id="chaos-engineering",
    name="Chaos Engineering Experiment",
    description="Controlled chaos experiment workflow",
    category="reliability",
    tags=["chaos", "resilience", "testing"],
    parameters={
        "experiment_duration": 300,
        "rollback_on_failure": True,
    },
    yaml_template="""
apiVersion: autosre.io/v1
kind: Workflow
metadata:
  name: chaos-engineering
  version: 1.0.0
  description: Controlled chaos engineering experiment
spec:
  inputs:
    - name: experiment_type
      type: string
      required: true
      enum: [pod-kill, network-delay, cpu-stress, memory-stress]
    - name: target_namespace
      type: string
      required: true
    - name: target_selector
      type: string
      required: true
      description: Label selector for target pods
    - name: intensity
      type: string
      default: medium
      enum: [low, medium, high]
      
  triggers:
    - type: manual
      required_inputs: [experiment_type, target_namespace, target_selector]
      require_confirmation: true
      confirmation_message: "Are you sure you want to run this chaos experiment?"
      
  steps:
    # Pre-checks
    - name: Pre-flight Checks
      id: preflight
      type: parallel
      steps:
        - name: Verify Target Exists
          action: kubernetes.get_pods
          inputs:
            namespace: ${{ inputs.target_namespace }}
            label_selector: ${{ inputs.target_selector }}
            
        - name: Check Current Health
          action: health.check
          inputs:
            namespace: ${{ inputs.target_namespace }}
            selector: ${{ inputs.target_selector }}
            
        - name: Snapshot Metrics
          action: prometheus.query
          inputs:
            query: |
              avg(rate(http_requests_total{namespace="${inputs.target_namespace}"}[5m]))
              
    # Validate pre-conditions
    - name: Validate Ready
      if: steps.preflight.output.check_current_health.status != "healthy"
      action: workflow.fail
      inputs:
        message: "Target is not healthy, aborting experiment"
        
    # Create experiment record
    - name: Create Experiment
      id: create_experiment
      action: chaos.create_experiment
      inputs:
        type: ${{ inputs.experiment_type }}
        namespace: ${{ inputs.target_namespace }}
        selector: ${{ inputs.target_selector }}
        intensity: ${{ inputs.intensity }}
        duration: ${experiment_duration}
        
    # Notify start
    - name: Notify Start
      action: slack.post_message
      inputs:
        channel: "#chaos-engineering"
        message: |
          :test_tube: *Chaos Experiment Started*
          Type: ${{ inputs.experiment_type }}
          Target: ${{ inputs.target_namespace }} / ${{ inputs.target_selector }}
          Intensity: ${{ inputs.intensity }}
          Duration: ${experiment_duration}s
          
    # Execute experiment
    - name: Execute Chaos
      id: execute
      action: chaos.execute
      inputs:
        experiment_id: ${{ steps.create_experiment.output.experiment_id }}
      timeout: ${experiment_duration}
      
    # Monitor during experiment
    - name: Monitor Experiment
      type: loop
      until: steps.execute.output.completed == true
      maxIterations: 60
      delay: 5
      steps:
        - name: Check Health
          id: monitor_health
          action: health.check
          inputs:
            namespace: ${{ inputs.target_namespace }}
            selector: ${{ inputs.target_selector }}
            
        - name: Abort if Critical
          if: steps.monitor_health.output.status == "critical"
          action: chaos.abort
          inputs:
            experiment_id: ${{ steps.create_experiment.output.experiment_id }}
            reason: "Critical health degradation detected"
            
    # Wait for recovery
    - name: Wait Recovery
      action: health.wait_healthy
      inputs:
        namespace: ${{ inputs.target_namespace }}
        selector: ${{ inputs.target_selector }}
        timeout: 300
        
    # Collect results
    - name: Collect Results
      id: results
      type: parallel
      steps:
        - name: Get Metrics During
          action: prometheus.query_range
          inputs:
            query: |
              rate(http_requests_total{namespace="${inputs.target_namespace}"}[1m])
            start: ${{ steps.create_experiment.output.start_time }}
            end: ${{ steps.execute.output.end_time }}
            
        - name: Get Error Rate
          action: prometheus.query
          inputs:
            query: |
              sum(increase(http_requests_total{status=~"5..", namespace="${inputs.target_namespace}"}[${experiment_duration}s])) /
              sum(increase(http_requests_total{namespace="${inputs.target_namespace}"}[${experiment_duration}s])) * 100
              
    # Generate report
    - name: Generate Report
      id: report
      action: chaos.generate_report
      inputs:
        experiment_id: ${{ steps.create_experiment.output.experiment_id }}
        baseline_metrics: ${{ steps.preflight.output.snapshot_metrics }}
        experiment_metrics: ${{ steps.results.output }}
        
    # Notify completion
    - name: Notify Complete
      action: slack.post_message
      inputs:
        channel: "#chaos-engineering"
        message: |
          :clipboard: *Chaos Experiment Complete*
          Type: ${{ inputs.experiment_type }}
          Result: ${{ steps.report.output.result }}
          Recovery time: ${{ steps.report.output.recovery_time }}s
          Error rate during: ${{ steps.results.output.get_error_rate }}%
          
  onFailure:
    - name: Emergency Rollback
      if: ${rollback_on_failure}
      action: chaos.emergency_stop
      inputs:
        namespace: ${{ inputs.target_namespace }}
        
    - name: Alert Failure
      action: pagerduty.create_incident
      inputs:
        service: platform
        urgency: high
        title: "Chaos experiment failed: ${{ inputs.experiment_type }}"
"""
)


def get_builtin_templates() -> List[WorkflowTemplate]:
    """Get all built-in workflow templates."""
    return [
        INCIDENT_RESPONSE_TEMPLATE,
        SCALING_TEMPLATE,
        DEPLOYMENT_ROLLBACK_TEMPLATE,
        HEALTH_CHECK_TEMPLATE,
        CHAOS_ENGINEERING_TEMPLATE,
    ]


def create_default_registry() -> TemplateRegistry:
    """Create a registry with all built-in templates."""
    registry = TemplateRegistry()
    for template in get_builtin_templates():
        registry.register(template)
    return registry
