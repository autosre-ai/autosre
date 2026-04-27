"""AutoSRE init command."""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def run_init(directory: str, quiet: bool = False):
    """Initialize AutoSRE in the specified directory."""
    base_dir = Path(directory).resolve()
    
    if not quiet:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]🚀 Initializing AutoSRE[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=quiet,
    ) as progress:
        # Create .autosre directory
        task = progress.add_task("Creating .autosre directory...", total=None)
        autosre_dir = base_dir / ".autosre"
        autosre_dir.mkdir(parents=True, exist_ok=True)
        (autosre_dir / "scenarios").mkdir(exist_ok=True)
        progress.update(task, description="[green]✓[/] Created .autosre directory")
        progress.remove_task(task)
        
        # Create runbooks directory
        task = progress.add_task("Creating runbooks directory...", total=None)
        runbooks_dir = base_dir / "runbooks"
        runbooks_dir.mkdir(parents=True, exist_ok=True)
        progress.update(task, description="[green]✓[/] Created runbooks directory")
        progress.remove_task(task)
        
        # Create .env.example
        task = progress.add_task("Creating configuration template...", total=None)
        env_example = base_dir / ".env.example"
        if not env_example.exists():
            env_example.write_text(_ENV_TEMPLATE)
        progress.update(task, description="[green]✓[/] Created .env.example")
        progress.remove_task(task)
        
        # Create sample runbook
        task = progress.add_task("Creating sample runbook...", total=None)
        sample_runbook = runbooks_dir / "high-cpu.yaml"
        if not sample_runbook.exists():
            sample_runbook.write_text(_SAMPLE_RUNBOOK)
        progress.update(task, description="[green]✓[/] Created sample runbook")
        progress.remove_task(task)
        
        # Create sample scenario
        task = progress.add_task("Creating sample scenario...", total=None)
        sample_scenario = autosre_dir / "scenarios" / "deployment-failure.yaml"
        if not sample_scenario.exists():
            sample_scenario.write_text(_SAMPLE_SCENARIO)
        progress.update(task, description="[green]✓[/] Created sample scenario")
        progress.remove_task(task)
    
    if not quiet:
        console.print()
        console.print("[bold green]✓ AutoSRE initialized successfully![/bold green]")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. [cyan]cp .env.example .env[/cyan] and configure your settings")
        console.print("  2. [cyan]autosre sandbox start[/cyan] to create a local test cluster")
        console.print("  3. [cyan]autosre context sync --all[/cyan] to populate context")
        console.print("  4. [cyan]autosre eval run --scenario deployment-failure[/cyan] to test")
        console.print()


_ENV_TEMPLATE = '''# AutoSRE Configuration
# Copy this to .env and fill in your values

# ==============================================================================
# LLM Provider Configuration
# ==============================================================================

# Provider: ollama (default, local), openai, anthropic, azure
OPENSRE_LLM_PROVIDER=ollama

# Ollama (default - runs locally)
OPENSRE_OLLAMA_HOST=http://localhost:11434
OPENSRE_OLLAMA_MODEL=llama3.1:8b

# OpenAI (optional)
# OPENSRE_OPENAI_API_KEY=sk-...
# OPENSRE_OPENAI_MODEL=gpt-4o-mini

# Anthropic (optional)
# OPENSRE_ANTHROPIC_API_KEY=sk-ant-...
# OPENSRE_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Azure OpenAI (optional)
# OPENSRE_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# OPENSRE_AZURE_OPENAI_API_KEY=...
# OPENSRE_AZURE_OPENAI_DEPLOYMENT=gpt-4
# OPENSRE_AZURE_OPENAI_API_VERSION=2024-02-01

# ==============================================================================
# Infrastructure Connections
# ==============================================================================

# Prometheus
OPENSRE_PROMETHEUS_URL=http://localhost:9090

# Kubernetes
# OPENSRE_KUBECONFIG=~/.kube/config
OPENSRE_K8S_NAMESPACES=default

# Loki (optional - for log aggregation)
# OPENSRE_LOKI_URL=http://localhost:3100

# ==============================================================================
# Integrations
# ==============================================================================

# Slack (optional)
# OPENSRE_SLACK_BOT_TOKEN=xoxb-...
# OPENSRE_SLACK_SIGNING_SECRET=...
# OPENSRE_SLACK_CHANNEL=#incidents

# PagerDuty (optional)
# OPENSRE_PAGERDUTY_API_KEY=...

# ==============================================================================
# Agent Behavior
# ==============================================================================

# Require human approval before executing remediation
OPENSRE_REQUIRE_APPROVAL=true

# Auto-approve low-risk actions (e.g., pod restarts)
OPENSRE_AUTO_APPROVE_LOW_RISK=false

# Minimum confidence threshold for automated actions (0.0 - 1.0)
OPENSRE_CONFIDENCE_THRESHOLD=0.7

# Maximum iterations for analysis
OPENSRE_MAX_ITERATIONS=10

# Timeout for analysis in seconds
OPENSRE_TIMEOUT_SECONDS=300

# ==============================================================================
# MCP (Model Context Protocol)
# ==============================================================================

# Enable MCP client for extended context
OPENSRE_MCP_ENABLED=false
# OPENSRE_MCP_CONFIG_PATH=./mcp-clients.json

# ==============================================================================
# Logging
# ==============================================================================

OPENSRE_LOG_LEVEL=INFO
OPENSRE_LOG_FORMAT=text
'''

_SAMPLE_RUNBOOK = '''# Sample runbook for high CPU troubleshooting
id: high-cpu
title: High CPU Troubleshooting
description: Steps to investigate and resolve high CPU usage

alerts:
  - HighCPUUsage
  - ContainerCPUHigh
  - NodeCPUHigh

services: []

keywords:
  - cpu
  - performance
  - throttling

steps:
  - name: Check current CPU usage
    command: kubectl top pods -n {{ namespace }}
    description: View current CPU usage for all pods
    
  - name: Check for CPU throttling
    command: kubectl get pods -n {{ namespace }} -o jsonpath='{range .items[*]}{.metadata.name}{"\\t"}{.status.containerStatuses[*].restartCount}{"\\n"}{end}'
    description: Check if pods are being throttled
    
  - name: Check recent deployments
    command: kubectl rollout history deployment/{{ service }} -n {{ namespace }}
    description: See if a recent deployment caused the issue
    
  - name: Check resource requests/limits
    command: kubectl describe pod {{ pod }} -n {{ namespace }} | grep -A 10 "Limits:"
    description: Verify resource configuration
    
  - name: Check logs for errors
    command: kubectl logs {{ pod }} -n {{ namespace }} --tail=100
    description: Look for application errors or warnings

automated: false
requires_approval: true

tags:
  - cpu
  - performance
  - troubleshooting
'''

_SAMPLE_SCENARIO = '''# Sample evaluation scenario
name: deployment-failure
description: Diagnose a failed deployment causing service degradation
difficulty: medium

# Alert that triggers the investigation
alert:
  name: DeploymentFailed
  severity: high
  source: prometheus
  summary: "Deployment frontend-v2 in namespace production failed to roll out"
  labels:
    deployment: frontend-v2
    namespace: production
    reason: ImagePullBackOff

# Services in the scenario
services:
  - name: frontend
    namespace: production
    status: degraded
    replicas: 3
    ready_replicas: 2
    labels:
      app: frontend
      version: v2
    dependencies:
      - api
      - redis

  - name: api
    namespace: production
    status: healthy
    replicas: 3
    ready_replicas: 3

# Recent changes
changes:
  - type: deployment
    service_name: frontend
    description: "Update frontend to v2.1.0"
    author: deploy-bot
    timestamp: "2024-01-15T10:30:00Z"
    previous_version: v2.0.0
    new_version: v2.1.0

# Expected outcomes (for evaluation)
expected_root_cause: "Deployment failed due to ImagePullBackOff - image tag v2.1.0 does not exist"
expected_service: frontend
expected_runbook: deployment-rollback
expected_action: "Rollback deployment to previous version or fix image tag"

max_time_seconds: 180
'''
