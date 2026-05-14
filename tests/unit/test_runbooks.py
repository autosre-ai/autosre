"""
Unit tests for runbook automation.

Tests for:
- RunbookParser
- StepExecutor
- VariableResolver
- ConditionEvaluator
- RunbookGenerator
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime
from typing import Any
from uuid import uuid4

from autosre.runbooks import (
    RunbookParser,
    ParseError,
)
from autosre.runbooks.models import (
    Runbook,
    RunbookStep,
    RunbookVariable,
    StepType,
    VariableType,
    Condition,
    ConditionOperator,
    RunbookExecution,
    ExecutionStatus,
    StepResult,
)
from autosre.runbooks.executor import (
    StepExecutor,
    RunbookExecutor,
)
from autosre.runbooks.executor_config import (
    ExecutorConfig,
    ExecutionContext,
)
from autosre.runbooks.variables import (
    VariableResolver,
    VariableStore,
    VariableResolutionError,
)
from autosre.runbooks.conditions import (
    ConditionEvaluator,
    EvaluationResult,
)
from autosre.runbooks.generator import (
    RunbookGenerator,
    GenerationConfig,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def parser() -> RunbookParser:
    """Create a runbook parser."""
    return RunbookParser()


@pytest.fixture
def sample_yaml_runbook() -> str:
    """Sample YAML runbook content."""
    return """
name: Restart API Server
description: Safely restart the API server deployment
version: 1.0.0
author: sre-team

variables:
  - name: namespace
    type: string
    default: production
    required: true
    description: Target namespace
  - name: deployment
    type: string
    default: api-server
    required: true
  - name: grace_period
    type: integer
    default: 30
    min_value: 0
    max_value: 300

triggers:
  - alert_name: HighErrorRate
    conditions:
      - service: api-server
  - alert_name: PodCrashLooping

steps:
  - id: check-health
    name: Check current health
    type: command
    command: kubectl get pods -n {{ namespace }} -l app={{ deployment }}
    output_variable: pod_status
    timeout_seconds: 30
    
  - id: verify-replicas
    name: Verify sufficient replicas
    type: kubernetes
    parameters:
      action: get_deployment
      namespace: "{{ namespace }}"
      name: "{{ deployment }}"
    condition:
      left: "{{ pod_count }}"
      operator: greater_than
      right: 1
    on_failure: abort
    
  - id: restart-pods
    name: Restart deployment
    type: kubernetes
    parameters:
      action: restart_deployment
      namespace: "{{ namespace }}"
      name: "{{ deployment }}"
    timeout_seconds: 120
    continue_on_failure: false
    
  - id: wait-healthy
    name: Wait for healthy state
    type: command
    command: |
      kubectl rollout status deployment/{{ deployment }} -n {{ namespace }} --timeout=180s
    delay_seconds: 10
    max_retries: 3
    retry_delay_seconds: 10
    
  - id: verify-health
    name: Verify health after restart
    type: command
    command: curl -sf http://{{ deployment }}.{{ namespace }}/health
    expected_output: "ok"

requires_approval: false
dry_run_by_default: true
max_concurrent_executions: 1
default_timeout_seconds: 600

tags:
  - restart
  - api
  - kubernetes
"""


@pytest.fixture
def sample_markdown_runbook() -> str:
    """Sample Markdown runbook content."""
    return """
# Database Failover Runbook

This runbook handles failover from primary to secondary database.

## Variables
- primary_host: db-primary.production.svc
- secondary_host: db-secondary.production.svc
- failover_timeout: 300

## Steps

### 1. Check primary database health
```command
pg_isready -h {{ primary_host }} -p 5432
```

### 2. Verify secondary is ready
```command
pg_isready -h {{ secondary_host }} -p 5432
```

### 3. Promote secondary to primary
```kubernetes
action: run_job
namespace: database
job_name: promote-secondary
parameters:
  target_host: "{{ secondary_host }}"
```

### 4. Update DNS records
```command
aws route53 change-resource-record-sets --hosted-zone-id Z123 --change-batch file://dns-update.json
```

### 5. Verify failover complete
Ensure all connections are now going to the new primary.

```command
psql -h db.production.svc -c "SELECT pg_is_in_recovery()"
```

The output should show `f` (false) indicating it's the primary.
"""


@pytest.fixture
def sample_runbook() -> Runbook:
    """Create a sample runbook for testing."""
    return Runbook(
        name="Test Runbook",
        description="A test runbook",
        version="1.0.0",
        variables=[
            RunbookVariable(
                name="namespace",
                type=VariableType.STRING,
                default="default",
            ),
            RunbookVariable(
                name="replicas",
                type=VariableType.INTEGER,
                default=3,
            ),
            RunbookVariable(
                name="enabled",
                type=VariableType.BOOLEAN,
                default=True,
            ),
        ],
        steps=[
            RunbookStep(
                id="step-1",
                name="First step",
                type=StepType.COMMAND,
                command="echo 'Hello from {{ namespace }}'",
            ),
            RunbookStep(
                id="step-2",
                name="Second step",
                type=StepType.COMMAND,
                command="echo 'Replicas: {{ replicas }}'",
                condition=Condition(
                    left="{{ enabled }}",
                    operator=ConditionOperator.EQUALS,
                    right=True,
                ),
            ),
        ],
    )


# ============================================================================
# RunbookParser Tests
# ============================================================================

class TestRunbookParser:
    """Tests for RunbookParser."""
    
    def test_parse_yaml_runbook(
        self,
        parser: RunbookParser,
        sample_yaml_runbook: str,
    ):
        """Test parsing YAML runbook."""
        runbook = parser.parse_yaml(sample_yaml_runbook)
        
        assert runbook.name == "Restart API Server"
        assert runbook.version == "1.0.0"
        assert len(runbook.variables) == 3
        assert len(runbook.steps) == 5
        assert len(runbook.triggers) == 2
    
    def test_parse_markdown_runbook(
        self,
        parser: RunbookParser,
        sample_markdown_runbook: str,
    ):
        """Test parsing Markdown runbook."""
        runbook = parser.parse_markdown(sample_markdown_runbook)
        
        assert runbook.name == "Database Failover Runbook"
        assert len(runbook.variables) == 3
        assert len(runbook.steps) == 5
    
    def test_parse_variables_from_yaml(
        self,
        parser: RunbookParser,
        sample_yaml_runbook: str,
    ):
        """Test variable parsing from YAML."""
        runbook = parser.parse_yaml(sample_yaml_runbook)
        
        namespace_var = next(
            v for v in runbook.variables if v.name == "namespace"
        )
        assert namespace_var.type == VariableType.STRING
        assert namespace_var.default == "production"
        assert namespace_var.required is True
        
        grace_var = next(
            v for v in runbook.variables if v.name == "grace_period"
        )
        assert grace_var.type == VariableType.INTEGER
        assert grace_var.default == 30
    
    def test_parse_steps_from_yaml(
        self,
        parser: RunbookParser,
        sample_yaml_runbook: str,
    ):
        """Test step parsing from YAML."""
        runbook = parser.parse_yaml(sample_yaml_runbook)
        
        check_step = next(
            s for s in runbook.steps if s.id == "check-health"
        )
        assert check_step.name == "Check current health"
        assert check_step.type == StepType.COMMAND
        assert "kubectl get pods" in check_step.command
        assert check_step.output_variable == "pod_status"
        
        restart_step = next(
            s for s in runbook.steps if s.id == "restart-pods"
        )
        assert restart_step.type == StepType.KUBERNETES
        assert restart_step.parameters["action"] == "restart_deployment"
    
    def test_parse_conditions_from_yaml(
        self,
        parser: RunbookParser,
        sample_yaml_runbook: str,
    ):
        """Test condition parsing from YAML."""
        runbook = parser.parse_yaml(sample_yaml_runbook)
        
        verify_step = next(
            s for s in runbook.steps if s.id == "verify-replicas"
        )
        
        assert verify_step.condition is not None
        assert verify_step.condition.operator == ConditionOperator.GREATER_THAN
    
    def test_validate_runbook_success(
        self,
        parser: RunbookParser,
        sample_yaml_runbook: str,
    ):
        """Test runbook validation success."""
        runbook = parser.parse_yaml(sample_yaml_runbook)
        
        errors = parser.validate_runbook(runbook)
        
        assert len(errors) == 0
    
    def test_validate_runbook_missing_name(self, parser: RunbookParser):
        """Test validation fails for missing name."""
        runbook = Runbook(
            name="",
            description="Test",
            steps=[
                RunbookStep(
                    id="step-1",
                    name="Step",
                    type=StepType.COMMAND,
                    command="echo test",
                )
            ],
        )
        
        errors = parser.validate_runbook(runbook)
        
        assert len(errors) > 0
        assert any("name" in e.lower() for e in errors)
    
    def test_validate_runbook_no_steps(self, parser: RunbookParser):
        """Test validation fails for no steps."""
        runbook = Runbook(
            name="Test",
            description="Test",
            steps=[],
        )
        
        errors = parser.validate_runbook(runbook)
        
        assert len(errors) > 0
        assert any("step" in e.lower() for e in errors)
    
    def test_validate_runbook_duplicate_step_ids(self, parser: RunbookParser):
        """Test validation fails for duplicate step IDs."""
        runbook = Runbook(
            name="Test",
            description="Test",
            steps=[
                RunbookStep(id="step-1", name="Step 1", type=StepType.COMMAND, command="echo 1"),
                RunbookStep(id="step-1", name="Step 2", type=StepType.COMMAND, command="echo 2"),
            ],
        )
        
        errors = parser.validate_runbook(runbook)
        
        assert len(errors) > 0
        assert any("duplicate" in e.lower() for e in errors)
    
    def test_parse_invalid_yaml(self, parser: RunbookParser):
        """Test parsing invalid YAML."""
        invalid_yaml = """
name: Test
  invalid indentation:
- not: valid
"""
        
        with pytest.raises(ParseError):
            parser.parse_yaml(invalid_yaml)
    
    @pytest.mark.asyncio
    async def test_parse_file_yaml(
        self,
        parser: RunbookParser,
        tmp_path,
        sample_yaml_runbook: str,
    ):
        """Test parsing runbook from file."""
        file_path = tmp_path / "runbook.yaml"
        file_path.write_text(sample_yaml_runbook)
        
        runbook = await parser.parse_file(file_path)
        
        assert runbook.name == "Restart API Server"
    
    @pytest.mark.asyncio
    async def test_parse_file_markdown(
        self,
        parser: RunbookParser,
        tmp_path,
        sample_markdown_runbook: str,
    ):
        """Test parsing markdown runbook from file."""
        file_path = tmp_path / "runbook.md"
        file_path.write_text(sample_markdown_runbook)
        
        runbook = await parser.parse_file(file_path)
        
        assert runbook.name == "Database Failover Runbook"
    
    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, parser: RunbookParser):
        """Test parsing non-existent file."""
        with pytest.raises(ParseError):
            await parser.parse_file("/nonexistent/path/runbook.yaml")


# ============================================================================
# VariableResolver Tests
# ============================================================================

class TestVariableResolver:
    """Tests for VariableResolver."""
    
    @pytest.fixture
    def resolver(self) -> VariableResolver:
        """Create a variable resolver."""
        return VariableResolver()
    
    @pytest.fixture
    def store(self) -> VariableStore:
        """Create a variable store with sample data."""
        store = VariableStore()
        store.set("namespace", "production")
        store.set("deployment", "api-server")
        store.set("replicas", 3)
        store.set("enabled", True)
        return store
    
    def test_resolve_simple_variable(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving simple variable."""
        result = resolver.resolve(
            "{{ namespace }}",
            store,
        )
        
        assert result == "production"
    
    def test_resolve_multiple_variables(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving multiple variables in string."""
        result = resolver.resolve(
            "kubectl get pods -n {{ namespace }} -l app={{ deployment }}",
            store,
        )
        
        assert result == "kubectl get pods -n production -l app=api-server"
    
    def test_resolve_integer_variable(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving integer variable."""
        result = resolver.resolve(
            "Scale to {{ replicas }} replicas",
            store,
        )
        
        assert "3" in result
    
    def test_resolve_with_whitespace(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving with various whitespace."""
        result1 = resolver.resolve("{{namespace}}", store)
        result2 = resolver.resolve("{{ namespace }}", store)
        result3 = resolver.resolve("{{  namespace  }}", store)
        
        assert result1 == result2 == result3 == "production"
    
    def test_resolve_undefined_variable(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving undefined variable raises error."""
        with pytest.raises(VariableResolutionError):
            resolver.resolve(
                "{{ undefined_var }}",
                store,
            )
    
    def test_resolve_undefined_with_default(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving undefined variable with default."""
        result = resolver.resolve(
            "{{ undefined_var | default:fallback }}",
            store,
        )
        
        assert result == "fallback"
    
    def test_resolve_dict(
        self,
        resolver: VariableResolver,
        store: VariableStore,
    ):
        """Test resolving variables in dictionary."""
        data = {
            "namespace": "{{ namespace }}",
            "name": "{{ deployment }}",
            "replicas": "{{ replicas }}",
        }
        
        result = resolver.resolve_dict(data, store)
        
        assert result["namespace"] == "production"
        assert result["name"] == "api-server"
    
    def test_variable_store_operations(self):
        """Test VariableStore operations."""
        store = VariableStore()
        
        # Set and get
        store.set("key1", "value1")
        assert store.get("key1") == "value1"
        
        # Has
        assert store.has("key1")
        assert not store.has("nonexistent")
        
        # Get with default
        assert store.get("nonexistent", "default") == "default"
        
        # Delete
        store.delete("key1")
        assert not store.has("key1")
        
        # All
        store.set("a", 1)
        store.set("b", 2)
        all_vars = store.all()
        assert "a" in all_vars
        assert "b" in all_vars
    
    def test_variable_store_update(self):
        """Test updating variable store from dict."""
        store = VariableStore()
        
        store.update({
            "var1": "value1",
            "var2": "value2",
        })
        
        assert store.get("var1") == "value1"
        assert store.get("var2") == "value2"
    
    def test_resolve_from_environment(
        self,
        resolver: VariableResolver,
        store: VariableStore,
        monkeypatch,
    ):
        """Test resolving variable from environment."""
        monkeypatch.setenv("MY_VAR", "env_value")
        
        # Add env variable to store
        store.set_from_env("my_var", "MY_VAR")
        
        result = resolver.resolve("{{ my_var }}", store)
        
        assert result == "env_value"


# ============================================================================
# ConditionEvaluator Tests
# ============================================================================

class TestConditionEvaluator:
    """Tests for ConditionEvaluator."""
    
    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        """Create a condition evaluator."""
        return ConditionEvaluator()
    
    @pytest.fixture
    def store(self) -> VariableStore:
        """Create a variable store."""
        store = VariableStore()
        store.set("status", "healthy")
        store.set("count", 5)
        store.set("enabled", True)
        store.set("tags", ["a", "b", "c"])
        return store
    
    @pytest.mark.asyncio
    async def test_evaluate_equals(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test equals condition."""
        condition = Condition(
            left="{{ status }}",
            operator=ConditionOperator.EQUALS,
            right="healthy",
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
        assert result.condition == condition
    
    @pytest.mark.asyncio
    async def test_evaluate_not_equals(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test not equals condition."""
        condition = Condition(
            left="{{ status }}",
            operator=ConditionOperator.NOT_EQUALS,
            right="unhealthy",
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_greater_than(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test greater than condition."""
        condition = Condition(
            left="{{ count }}",
            operator=ConditionOperator.GREATER_THAN,
            right=3,
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_less_than(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test less than condition."""
        condition = Condition(
            left="{{ count }}",
            operator=ConditionOperator.LESS_THAN,
            right=10,
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_contains(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test contains condition."""
        condition = Condition(
            left="{{ status }}",
            operator=ConditionOperator.CONTAINS,
            right="alth",
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_exists(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test exists condition."""
        condition = Condition(
            left="{{ enabled }}",
            operator=ConditionOperator.EXISTS,
            right=True,
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_matches_regex(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test regex match condition."""
        condition = Condition(
            left="{{ status }}",
            operator=ConditionOperator.MATCHES,
            right=r"^health.*$",
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_and_conditions(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test AND condition."""
        condition = Condition(
            operator=ConditionOperator.AND,
            conditions=[
                Condition(left="{{ status }}", operator=ConditionOperator.EQUALS, right="healthy"),
                Condition(left="{{ count }}", operator=ConditionOperator.GREATER_THAN, right=3),
            ],
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed
    
    @pytest.mark.asyncio
    async def test_evaluate_or_conditions(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test OR condition."""
        condition = Condition(
            operator=ConditionOperator.OR,
            conditions=[
                Condition(left="{{ status }}", operator=ConditionOperator.EQUALS, right="failed"),
                Condition(left="{{ count }}", operator=ConditionOperator.GREATER_THAN, right=3),
            ],
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed  # Second condition passes
    
    @pytest.mark.asyncio
    async def test_evaluate_not_condition(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test NOT condition."""
        condition = Condition(
            operator=ConditionOperator.NOT,
            conditions=[
                Condition(left="{{ status }}", operator=ConditionOperator.EQUALS, right="failed"),
            ],
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert result.passed  # status is not "failed"
    
    @pytest.mark.asyncio
    async def test_evaluate_failed_condition(
        self,
        evaluator: ConditionEvaluator,
        store: VariableStore,
    ):
        """Test failed condition evaluation."""
        condition = Condition(
            left="{{ status }}",
            operator=ConditionOperator.EQUALS,
            right="unhealthy",
        )
        
        result = await evaluator.evaluate(condition, store)
        
        assert not result.passed


# ============================================================================
# StepExecutor Tests
# ============================================================================

class TestStepExecutor:
    """Tests for StepExecutor."""
    
    @pytest.fixture
    def executor(self) -> StepExecutor:
        """Create a step executor."""
        config = ExecutorConfig(
            dry_run=False,
            timeout_seconds=30,
        )
        return StepExecutor(config=config)
    
    @pytest.fixture
    def context(self) -> ExecutionContext:
        """Create an execution context."""
        return ExecutionContext(
            execution_id=uuid4(),
            runbook_id="test-runbook",
            variables=VariableStore(),
        )
    
    @pytest.mark.asyncio
    async def test_execute_command_step(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test executing command step."""
        step = RunbookStep(
            id="step-1",
            name="Echo test",
            type=StepType.COMMAND,
            command="echo 'Hello World'",
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success
        assert result.step_id == "step-1"
        assert "Hello World" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_step_with_variable(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test executing step with variable substitution."""
        context.variables.set("message", "test message")
        
        step = RunbookStep(
            id="step-1",
            name="Echo variable",
            type=StepType.COMMAND,
            command="echo '{{ message }}'",
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success
        assert "test message" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_step_capture_output(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test capturing step output to variable."""
        step = RunbookStep(
            id="step-1",
            name="Capture output",
            type=StepType.COMMAND,
            command="echo 'captured_value'",
            output_variable="my_output",
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success
        assert context.variables.has("my_output")
        assert "captured_value" in context.variables.get("my_output")
    
    @pytest.mark.asyncio
    async def test_execute_step_with_condition_pass(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test executing step when condition passes."""
        context.variables.set("should_run", True)
        
        step = RunbookStep(
            id="step-1",
            name="Conditional step",
            type=StepType.COMMAND,
            command="echo 'executed'",
            condition=Condition(
                left="{{ should_run }}",
                operator=ConditionOperator.EQUALS,
                right=True,
            ),
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success
        assert result.executed
    
    @pytest.mark.asyncio
    async def test_execute_step_with_condition_skip(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test skipping step when condition fails."""
        context.variables.set("should_run", False)
        
        step = RunbookStep(
            id="step-1",
            name="Conditional step",
            type=StepType.COMMAND,
            command="echo 'executed'",
            condition=Condition(
                left="{{ should_run }}",
                operator=ConditionOperator.EQUALS,
                right=True,
            ),
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success  # Skipped is still success
        assert result.skipped
    
    @pytest.mark.asyncio
    async def test_execute_step_timeout(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test step timeout."""
        step = RunbookStep(
            id="step-1",
            name="Slow step",
            type=StepType.COMMAND,
            command="sleep 10",
            timeout_seconds=1,
        )
        
        result = await executor.execute_step(step, context)
        
        assert not result.success
        assert "timeout" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_step_failure(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test step failure handling."""
        step = RunbookStep(
            id="step-1",
            name="Failing step",
            type=StepType.COMMAND,
            command="exit 1",
        )
        
        result = await executor.execute_step(step, context)
        
        assert not result.success
        assert result.exit_code == 1
    
    @pytest.mark.asyncio
    async def test_execute_step_with_retries(
        self,
        executor: StepExecutor,
        context: ExecutionContext,
    ):
        """Test step with retries."""
        # This will fail on first attempts
        step = RunbookStep(
            id="step-1",
            name="Retry step",
            type=StepType.COMMAND,
            command="exit 1",
            max_retries=2,
            retry_delay_seconds=0.1,
        )
        
        result = await executor.execute_step(step, context)
        
        assert not result.success
        assert result.attempts == 3  # Original + 2 retries
    
    @pytest.mark.asyncio
    async def test_execute_step_dry_run(
        self,
        context: ExecutionContext,
    ):
        """Test dry-run execution."""
        config = ExecutorConfig(dry_run=True)
        executor = StepExecutor(config=config)
        
        step = RunbookStep(
            id="step-1",
            name="Would execute",
            type=StepType.COMMAND,
            command="echo 'executed'",
        )
        
        result = await executor.execute_step(step, context)
        
        assert result.success
        assert result.dry_run


# ============================================================================
# RunbookGenerator Tests
# ============================================================================

class TestRunbookGenerator:
    """Tests for RunbookGenerator."""
    
    @pytest.fixture
    def generator(self) -> RunbookGenerator:
        """Create a runbook generator."""
        return RunbookGenerator()
    
    @pytest.mark.asyncio
    async def test_generate_from_incident(self, generator: RunbookGenerator):
        """Test generating runbook from incident data."""
        incident_data = {
            "id": "INC-123",
            "title": "High API latency",
            "service": "api-server",
            "namespace": "production",
            "symptoms": [
                "P99 latency > 500ms",
                "Error rate increased",
            ],
            "resolution_steps": [
                "Scaled deployment to 10 replicas",
                "Restarted pods",
                "Cleared cache",
            ],
            "root_cause": "Memory pressure on pods",
        }
        
        runbook = await generator.generate_from_incident(incident_data)
        
        assert runbook is not None
        assert "api" in runbook.name.lower() or "latency" in runbook.name.lower()
        assert len(runbook.steps) > 0
    
    @pytest.mark.asyncio
    async def test_generate_from_alert(self, generator: RunbookGenerator):
        """Test generating runbook from alert."""
        alert_data = {
            "name": "PodCrashLooping",
            "namespace": "production",
            "pod": "api-server-xyz",
            "deployment": "api-server",
            "labels": {
                "app": "api-server",
                "team": "platform",
            },
        }
        
        runbook = await generator.generate_from_alert(alert_data)
        
        assert runbook is not None
        assert len(runbook.steps) > 0
    
    @pytest.mark.asyncio
    async def test_generate_restart_runbook(self, generator: RunbookGenerator):
        """Test generating a restart runbook."""
        runbook = await generator.generate_restart_runbook(
            service_name="api-server",
            namespace="production",
        )
        
        assert runbook is not None
        assert "restart" in runbook.name.lower()
        assert any("restart" in s.name.lower() for s in runbook.steps)
    
    @pytest.mark.asyncio
    async def test_generate_scale_runbook(self, generator: RunbookGenerator):
        """Test generating a scale runbook."""
        runbook = await generator.generate_scale_runbook(
            service_name="api-server",
            namespace="production",
            target_replicas=10,
        )
        
        assert runbook is not None
        assert "scale" in runbook.name.lower()
    
    @pytest.mark.asyncio
    async def test_generate_rollback_runbook(self, generator: RunbookGenerator):
        """Test generating a rollback runbook."""
        runbook = await generator.generate_rollback_runbook(
            service_name="api-server",
            namespace="production",
        )
        
        assert runbook is not None
        assert "rollback" in runbook.name.lower()


# ============================================================================
# Model Tests
# ============================================================================

class TestRunbookModels:
    """Tests for runbook models."""
    
    def test_runbook_creation(self, sample_runbook: Runbook):
        """Test runbook model creation."""
        assert sample_runbook.name == "Test Runbook"
        assert len(sample_runbook.variables) == 3
        assert len(sample_runbook.steps) == 2
    
    def test_runbook_variable_validation(self):
        """Test variable validation."""
        var = RunbookVariable(
            name="replicas",
            type=VariableType.INTEGER,
            min_value=1,
            max_value=100,
        )
        
        # Valid value
        is_valid, error = var.validate_value(5)
        assert is_valid
        
        # Too low
        is_valid, error = var.validate_value(0)
        assert not is_valid
        
        # Too high
        is_valid, error = var.validate_value(200)
        assert not is_valid
    
    def test_runbook_step_is_skippable(self):
        """Test step skippability."""
        step = RunbookStep(
            id="step-1",
            name="Test",
            type=StepType.COMMAND,
            command="echo test",
            condition=Condition(
                left="x",
                operator=ConditionOperator.EQUALS,
                right="y",
            ),
        )
        
        assert step.has_condition
    
    def test_execution_status_transitions(self):
        """Test execution status model."""
        execution = RunbookExecution(
            runbook_id="test",
            runbook_name="Test",
            status=ExecutionStatus.PENDING,
        )
        
        assert execution.status == ExecutionStatus.PENDING
        assert not execution.is_complete
        
        execution.status = ExecutionStatus.RUNNING
        assert not execution.is_complete
        
        execution.status = ExecutionStatus.COMPLETED
        assert execution.is_complete
    
    def test_step_result_model(self):
        """Test step result model."""
        result = StepResult(
            step_id="step-1",
            step_name="Test Step",
            success=True,
            output="output text",
            exit_code=0,
        )
        
        assert result.success
        assert result.duration_seconds >= 0
