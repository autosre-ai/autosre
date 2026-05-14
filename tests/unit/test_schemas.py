"""Unit tests for Pydantic schemas.

Tests schema validation, serialization, deserialization,
default values, and edge cases.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from autosre.api.schemas.common import (
    ComponentHealth,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    PaginatedResponse,
    PaginationParams,
    SortOrder,
    SortParams,
    SuccessResponse,
    TimestampMixin,
)
from autosre.api.schemas.requests import (
    AlertCreate,
    AlertUpdate,
    ChatMessage,
    InvestigationAction,
    InvestigationTrigger,
    RunbookCreate,
    RunbookExecute,
    RunbookUpdate,
)
from autosre.api.schemas.responses import (
    AlertDetail,
    AlertList,
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatSession,
    InvestigationDetail,
    InvestigationList,
    InvestigationStep,
    InvestigationSummary,
    InvestigationTimeline,
    RunbookDetail,
    RunbookExecution,
    RunbookList,
)


# ============================================================================
# Request Schema Tests
# ============================================================================


class TestAlertCreateSchema:
    """Tests for AlertCreate schema."""

    def test_valid_alert_create(self):
        """Test valid alert creation."""
        alert = AlertCreate(
            alertname="HighErrorRate",
            severity="critical",
            summary="Error rate above 5%",
            source="prometheus",
        )

        assert alert.alertname == "HighErrorRate"
        assert alert.severity == "critical"
        assert alert.labels == {}  # Default

    def test_alert_create_all_fields(self):
        """Test alert creation with all fields."""
        alert = AlertCreate(
            alertname="TestAlert",
            severity="warning",
            summary="Test summary",
            description="Test description",
            source="custom",
            labels={"env": "prod"},
            annotations={"runbook": "https://runbook.example.com"},
            external_url="https://alert.example.com/123",
        )

        assert alert.description == "Test description"
        assert alert.labels["env"] == "prod"
        assert alert.external_url == "https://alert.example.com/123"

    def test_alert_create_missing_required(self):
        """Test alert creation fails without required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreate(
                severity="critical",
                summary="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alertname",) for e in errors)

    def test_alert_create_empty_alertname(self):
        """Test alert creation fails with empty alertname."""
        with pytest.raises(ValidationError):
            AlertCreate(
                alertname="",
                severity="critical",
                summary="Test",
                source="test",
            )

    def test_alert_create_invalid_severity(self):
        """Test alert creation fails with invalid severity."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreate(
                alertname="Test",
                severity="invalid",
                summary="Test",
                source="test",
            )

        errors = exc_info.value.errors()
        assert any("severity" in str(e) for e in errors)

    def test_alert_create_severity_valid_values(self):
        """Test alert creation with all valid severity values."""
        for severity in ["critical", "warning", "info"]:
            alert = AlertCreate(
                alertname="Test",
                severity=severity,
                summary="Test",
                source="test",
            )
            assert alert.severity == severity

    def test_alert_create_summary_max_length(self):
        """Test alert creation summary max length."""
        with pytest.raises(ValidationError):
            AlertCreate(
                alertname="Test",
                severity="warning",
                summary="x" * 1001,  # Max 1000
                source="test",
            )

    def test_alert_create_description_max_length(self):
        """Test alert creation description max length."""
        with pytest.raises(ValidationError):
            AlertCreate(
                alertname="Test",
                severity="warning",
                summary="Test",
                source="test",
                description="x" * 5001,  # Max 5000
            )


class TestAlertUpdateSchema:
    """Tests for AlertUpdate schema."""

    def test_alert_update_partial(self):
        """Test partial alert update."""
        update = AlertUpdate(status="acknowledged")

        assert update.status == "acknowledged"
        assert update.severity is None
        assert update.labels is None

    def test_alert_update_all_fields(self):
        """Test alert update with all fields."""
        update = AlertUpdate(
            status="resolved",
            severity="info",
            summary="Updated summary",
            description="Updated description",
            labels={"env": "staging"},
            annotations={"note": "test"},
            assigned_to="user@example.com",
        )

        assert update.status == "resolved"
        assert update.assigned_to == "user@example.com"

    def test_alert_update_invalid_status(self):
        """Test alert update with invalid status."""
        with pytest.raises(ValidationError):
            AlertUpdate(status="invalid_status")

    def test_alert_update_valid_statuses(self):
        """Test alert update with valid status values."""
        for status in ["firing", "acknowledged", "resolved"]:
            update = AlertUpdate(status=status)
            assert update.status == status


class TestInvestigationTriggerSchema:
    """Tests for InvestigationTrigger schema."""

    def test_investigation_trigger_defaults(self):
        """Test investigation trigger with defaults."""
        trigger = InvestigationTrigger()

        assert trigger.auto_remediate is False
        assert trigger.runbook_ids == []
        assert trigger.priority == "normal"
        assert trigger.context == {}

    def test_investigation_trigger_all_fields(self):
        """Test investigation trigger with all fields."""
        runbook_id = uuid4()
        trigger = InvestigationTrigger(
            auto_remediate=True,
            runbook_ids=[runbook_id],
            priority="critical",
            context={"foo": "bar"},
        )

        assert trigger.auto_remediate is True
        assert runbook_id in trigger.runbook_ids
        assert trigger.priority == "critical"

    def test_investigation_trigger_invalid_priority(self):
        """Test investigation trigger with invalid priority."""
        with pytest.raises(ValidationError):
            InvestigationTrigger(priority="urgent")

    def test_investigation_trigger_valid_priorities(self):
        """Test investigation trigger with valid priorities."""
        for priority in ["low", "normal", "high", "critical"]:
            trigger = InvestigationTrigger(priority=priority)
            assert trigger.priority == priority


class TestChatMessageSchema:
    """Tests for ChatMessage request schema."""

    def test_chat_message_valid(self):
        """Test valid chat message."""
        msg = ChatMessage(content="What's the status?")

        assert msg.content == "What's the status?"
        assert msg.context == {}

    def test_chat_message_with_context(self):
        """Test chat message with context."""
        msg = ChatMessage(
            content="Analyze this",
            context={"alert_ids": ["uuid-1"], "time_range": "1h"},
        )

        assert "alert_ids" in msg.context

    def test_chat_message_empty_content(self):
        """Test chat message with empty content fails."""
        with pytest.raises(ValidationError):
            ChatMessage(content="")

    def test_chat_message_content_too_long(self):
        """Test chat message content max length."""
        with pytest.raises(ValidationError):
            ChatMessage(content="x" * 10001)  # Max 10000


class TestInvestigationActionSchema:
    """Tests for InvestigationAction schema."""

    def test_investigation_action_valid(self):
        """Test valid investigation action."""
        action = InvestigationAction(
            action_type="approve",
            target="remediation-123",
            message="Approved",
        )

        assert action.action_type == "approve"
        assert action.target == "remediation-123"

    def test_investigation_action_add_note(self):
        """Test add_note action."""
        action = InvestigationAction(
            action_type="add_note",
            message="Checked logs, no obvious errors",
        )

        assert action.action_type == "add_note"
        assert action.message is not None

    def test_investigation_action_invalid_type(self):
        """Test investigation action with invalid type."""
        with pytest.raises(ValidationError):
            InvestigationAction(action_type="delete")

    def test_investigation_action_valid_types(self):
        """Test all valid action types."""
        for action_type in ["approve", "reject", "escalate", "add_note", "run_command"]:
            action = InvestigationAction(action_type=action_type)
            assert action.action_type == action_type


class TestRunbookCreateSchema:
    """Tests for RunbookCreate schema."""

    def test_runbook_create_valid(self):
        """Test valid runbook creation."""
        runbook = RunbookCreate(
            name="Restart Service",
            category="remediation",
            steps=[{"type": "action", "action": "restart"}],
        )

        assert runbook.name == "Restart Service"
        assert len(runbook.steps) == 1

    def test_runbook_create_all_fields(self):
        """Test runbook creation with all fields."""
        runbook = RunbookCreate(
            name="Complex Runbook",
            description="Multi-step remediation",
            category="remediation",
            trigger_conditions={"severity": "critical"},
            steps=[
                {"type": "check", "action": "health_check"},
                {"type": "action", "action": "restart"},
                {"type": "wait", "seconds": 30},
            ],
            parameters=[
                {"name": "service", "type": "string", "required": True},
            ],
            tags=["restart", "service"],
            enabled=True,
        )

        assert len(runbook.steps) == 3
        assert len(runbook.parameters) == 1
        assert "restart" in runbook.tags

    def test_runbook_create_empty_steps(self):
        """Test runbook creation fails with empty steps."""
        with pytest.raises(ValidationError):
            RunbookCreate(
                name="Test",
                category="test",
                steps=[],
            )

    def test_runbook_create_name_max_length(self):
        """Test runbook name max length."""
        with pytest.raises(ValidationError):
            RunbookCreate(
                name="x" * 256,  # Max 255
                category="test",
                steps=[{"type": "action"}],
            )


class TestRunbookExecuteSchema:
    """Tests for RunbookExecute schema."""

    def test_runbook_execute_defaults(self):
        """Test runbook execute with defaults."""
        execute = RunbookExecute()

        assert execute.parameters == {}
        assert execute.dry_run is False
        assert execute.alert_id is None
        assert execute.investigation_id is None

    def test_runbook_execute_with_params(self):
        """Test runbook execute with parameters."""
        execute = RunbookExecute(
            parameters={"service_name": "api-gateway"},
            dry_run=True,
        )

        assert execute.parameters["service_name"] == "api-gateway"
        assert execute.dry_run is True

    def test_runbook_execute_with_context(self):
        """Test runbook execute with alert/investigation context."""
        alert_id = uuid4()
        inv_id = uuid4()

        execute = RunbookExecute(
            parameters={},
            alert_id=alert_id,
            investigation_id=inv_id,
        )

        assert execute.alert_id == alert_id
        assert execute.investigation_id == inv_id


# ============================================================================
# Response Schema Tests
# ============================================================================


class TestAlertListSchema:
    """Tests for AlertList response schema."""

    def test_alert_list_valid(self):
        """Test valid alert list item."""
        now = datetime.now(timezone.utc)
        alert = AlertList(
            id=uuid4(),
            alertname="TestAlert",
            severity="warning",
            status="firing",
            summary="Test alert",
            source="prometheus",
            labels={"env": "prod"},
            created_at=now,
            updated_at=now,
        )

        assert alert.alertname == "TestAlert"
        assert alert.acknowledged_at is None

    def test_alert_list_with_timestamps(self):
        """Test alert list with acknowledgement/resolution."""
        now = datetime.now(timezone.utc)
        alert = AlertList(
            id=uuid4(),
            alertname="TestAlert",
            severity="critical",
            status="resolved",
            summary="Test",
            source="test",
            labels={},
            created_at=now,
            updated_at=now,
            acknowledged_at=now,
            resolved_at=now,
        )

        assert alert.acknowledged_at is not None
        assert alert.resolved_at is not None


class TestAlertDetailSchema:
    """Tests for AlertDetail response schema."""

    def test_alert_detail_extends_list(self):
        """Test AlertDetail extends AlertList."""
        now = datetime.now(timezone.utc)
        alert = AlertDetail(
            id=uuid4(),
            alertname="TestAlert",
            severity="critical",
            status="firing",
            summary="Test",
            source="prometheus",
            labels={},
            created_at=now,
            updated_at=now,
            description="Detailed description",
            annotations={"dashboard": "https://grafana.local"},
            investigation_id=uuid4(),
            investigation_status="running",
        )

        assert alert.description == "Detailed description"
        assert alert.investigation_id is not None


class TestInvestigationSchemas:
    """Tests for investigation response schemas."""

    def test_investigation_summary(self):
        """Test InvestigationSummary schema."""
        now = datetime.now(timezone.utc)
        summary = InvestigationSummary(
            id=uuid4(),
            alert_id=uuid4(),
            status="running",
            created_at=now,
        )

        assert summary.started_at is None
        assert summary.completed_at is None

    def test_investigation_list(self):
        """Test InvestigationList extends summary."""
        now = datetime.now(timezone.utc)
        inv = InvestigationList(
            id=uuid4(),
            alert_id=uuid4(),
            status="completed",
            created_at=now,
            alert_name="HighErrorRate",
            alert_severity="critical",
            findings_count=5,
            actions_taken=2,
        )

        assert inv.alert_name == "HighErrorRate"
        assert inv.findings_count == 5

    def test_investigation_step(self):
        """Test InvestigationStep schema."""
        now = datetime.now(timezone.utc)
        step = InvestigationStep(
            id=uuid4(),
            investigation_id=uuid4(),
            step_number=1,
            step_type="gather_context",
            description="Collecting metrics",
            status="completed",
            input_data={"query": "up"},
            output_data={"result": 1},
            started_at=now,
            completed_at=now,
            duration_ms=1500,
        )

        assert step.step_type == "gather_context"
        assert step.duration_ms == 1500

    def test_investigation_timeline(self):
        """Test InvestigationTimeline schema."""
        timeline = InvestigationTimeline(
            investigation_id=uuid4(),
            events=[
                {"timestamp": "2024-01-15T10:00:00Z", "type": "started"},
                {"timestamp": "2024-01-15T10:01:00Z", "type": "completed"},
            ],
            total_duration_ms=60000,
            phases=[
                {"name": "gathering", "duration_ms": 20000},
                {"name": "analysis", "duration_ms": 40000},
            ],
        )

        assert len(timeline.events) == 2
        assert len(timeline.phases) == 2


class TestChatSchemas:
    """Tests for chat response schemas."""

    def test_chat_session(self):
        """Test ChatSession schema."""
        now = datetime.now(timezone.utc)
        session = ChatSession(
            id=uuid4(),
            user_id="user-123",
            created_at=now,
            updated_at=now,
            message_count=10,
            title="Investigation Discussion",
        )

        assert session.message_count == 10
        assert session.investigation_id is None

    def test_chat_history_response(self):
        """Test ChatHistoryResponse schema."""
        response = ChatHistoryResponse(
            messages=[
                ChatHistoryMessage(
                    id=uuid4(),
                    role="user",
                    content="What's happening?",
                    created_at=datetime.now(timezone.utc),
                ),
                ChatHistoryMessage(
                    id=uuid4(),
                    role="assistant",
                    content="Looking into it...",
                    created_at=datetime.now(timezone.utc),
                    tokens_used=150,
                ),
            ],
            has_more=True,
            next_cursor="msg-123",
        )

        assert len(response.messages) == 2
        assert response.has_more is True

    def test_chat_message_response(self):
        """Test ChatMessageResponse schema."""
        response = ChatMessageResponse(
            id=uuid4(),
            role="assistant",
            content="Analysis complete. Found memory leak.",
            created_at=datetime.now(timezone.utc),
            sources=[{"type": "metrics", "query": "memory_usage"}],
            tool_calls=[{"name": "query_prometheus", "result": "success"}],
            suggested_actions=[{"action": "restart", "confidence": 0.8}],
            tokens_used=250,
            response_time_ms=1500,
        )

        assert len(response.sources) == 1
        assert response.response_time_ms == 1500


class TestRunbookSchemas:
    """Tests for runbook response schemas."""

    def test_runbook_list(self):
        """Test RunbookList schema."""
        now = datetime.now(timezone.utc)
        runbook = RunbookList(
            id=uuid4(),
            name="Restart Service",
            description="Safely restart a service",
            category="remediation",
            tags=["restart"],
            enabled=True,
            created_at=now,
            updated_at=now,
            execution_count=42,
            last_executed_at=now,
        )

        assert runbook.execution_count == 42
        assert "restart" in runbook.tags

    def test_runbook_detail(self):
        """Test RunbookDetail extends list."""
        now = datetime.now(timezone.utc)
        runbook = RunbookDetail(
            id=uuid4(),
            name="Complex Runbook",
            category="remediation",
            enabled=True,
            created_at=now,
            updated_at=now,
            trigger_conditions={"severity": "critical"},
            steps=[
                {"type": "check", "action": "health"},
                {"type": "action", "action": "restart"},
            ],
            parameters=[{"name": "service", "required": True}],
            created_by="admin@example.com",
            updated_by="admin@example.com",
            version=3,
        )

        assert len(runbook.steps) == 2
        assert runbook.version == 3

    def test_runbook_execution(self):
        """Test RunbookExecution schema."""
        now = datetime.now(timezone.utc)
        execution = RunbookExecution(
            id=uuid4(),
            runbook_id=uuid4(),
            runbook_name="Restart Service",
            status="completed",
            dry_run=False,
            parameters={"service": "api-gateway"},
            executed_by="user@example.com",
            created_at=now,
            started_at=now,
            completed_at=now,
            duration_ms=45000,
            steps_completed=3,
            steps_total=3,
            output={"success": True},
        )

        assert execution.status == "completed"
        assert execution.steps_completed == execution.steps_total


# ============================================================================
# Common Schema Tests
# ============================================================================


class TestPaginatedResponse:
    """Tests for PaginatedResponse schema."""

    def test_paginated_response_empty(self):
        """Test empty paginated response."""
        response = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
        )

        assert response.items == []
        assert response.total == 0

    def test_paginated_response_with_items(self):
        """Test paginated response with items."""
        response = PaginatedResponse(
            items=["item1", "item2"],
            total=100,
            page=2,
            page_size=20,
            total_pages=5,
        )

        assert len(response.items) == 2
        assert response.total_pages == 5


class TestPaginationParams:
    """Tests for PaginationParams schema."""

    def test_pagination_defaults(self):
        """Test pagination default values."""
        params = PaginationParams()

        assert params.page == 1
        assert params.per_page == 20

    def test_pagination_offset_calculation(self):
        """Test offset calculation."""
        params = PaginationParams(page=3, per_page=25)

        assert params.offset == 50  # (3-1) * 25

    def test_pagination_validation(self):
        """Test pagination validation."""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)  # Must be >= 1

        with pytest.raises(ValidationError):
            PaginationParams(per_page=101)  # Max 100


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_error_response_basic(self):
        """Test basic error response."""
        error = ErrorResponse(
            error="not_found",
            message="Resource not found",
        )

        assert error.error == "not_found"
        assert error.details == []

    def test_error_response_with_details(self):
        """Test error response with details."""
        error = ErrorResponse(
            error="validation_error",
            message="Invalid input",
            details=[
                ErrorDetail(field="name", message="Required field"),
                ErrorDetail(field="email", message="Invalid format", code="INVALID_EMAIL"),
            ],
            request_id="req-123",
        )

        assert len(error.details) == 2
        assert error.request_id == "req-123"


class TestSuccessResponse:
    """Tests for SuccessResponse schema."""

    def test_success_response_defaults(self):
        """Test success response defaults."""
        response = SuccessResponse()

        assert response.success is True
        assert response.data is None

    def test_success_response_with_data(self):
        """Test success response with data."""
        response = SuccessResponse(
            message="Created successfully",
            data={"id": "uuid-123"},
        )

        assert response.data["id"] == "uuid-123"


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_health_response_healthy(self):
        """Test healthy response."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="2.0.0",
            uptime_seconds=3600.5,
            components=[
                ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    latency_ms=2.5,
                ),
            ],
        )

        assert response.status == HealthStatus.HEALTHY
        assert len(response.components) == 1

    def test_health_response_degraded(self):
        """Test degraded response."""
        response = HealthResponse(
            status=HealthStatus.DEGRADED,
            version="2.0.0",
            uptime_seconds=100.0,
            components=[
                ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                ),
                ComponentHealth(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    message="Connection refused",
                ),
            ],
        )

        assert response.status == HealthStatus.DEGRADED


class TestSortParams:
    """Tests for SortParams schema."""

    def test_sort_defaults(self):
        """Test sort default values."""
        params = SortParams()

        assert params.sort_by is None
        assert params.sort_order == SortOrder.DESC

    def test_sort_asc(self):
        """Test ascending sort."""
        params = SortParams(sort_by="created_at", sort_order=SortOrder.ASC)

        assert params.sort_order == SortOrder.ASC


# ============================================================================
# Schema Serialization Tests
# ============================================================================


class TestSchemaSerialization:
    """Tests for schema serialization/deserialization."""

    def test_alert_create_json_serialization(self):
        """Test AlertCreate JSON serialization."""
        alert = AlertCreate(
            alertname="Test",
            severity="warning",
            summary="Test alert",
            source="test",
        )

        json_data = alert.model_dump()
        restored = AlertCreate(**json_data)

        assert restored.alertname == alert.alertname

    def test_datetime_serialization(self):
        """Test datetime fields serialize properly."""
        now = datetime.now(timezone.utc)
        alert = AlertList(
            id=uuid4(),
            alertname="Test",
            severity="info",
            status="firing",
            summary="Test",
            source="test",
            labels={},
            created_at=now,
            updated_at=now,
        )

        json_data = alert.model_dump(mode="json")
        assert isinstance(json_data["created_at"], str)

    def test_uuid_serialization(self):
        """Test UUID fields serialize properly."""
        alert_id = uuid4()
        summary = InvestigationSummary(
            id=alert_id,
            alert_id=alert_id,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )

        json_data = summary.model_dump(mode="json")
        assert isinstance(json_data["id"], str)
        assert json_data["id"] == str(alert_id)


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestSchemaEdgeCases:
    """Tests for schema edge cases."""

    def test_empty_labels(self):
        """Test schemas with empty labels dict."""
        alert = AlertCreate(
            alertname="Test",
            severity="info",
            summary="Test",
            source="test",
            labels={},
        )

        assert alert.labels == {}

    def test_unicode_content(self):
        """Test schemas handle unicode content."""
        msg = ChatMessage(
            content="What's causing the 🔥 in production? 日本語",
        )

        assert "🔥" in msg.content
        assert "日本語" in msg.content

    def test_large_context_dict(self):
        """Test schemas handle large context dicts."""
        large_context = {f"key_{i}": f"value_{i}" for i in range(100)}

        msg = ChatMessage(
            content="Test",
            context=large_context,
        )

        assert len(msg.context) == 100

    def test_nested_annotations(self):
        """Test schemas handle nested annotation values."""
        alert = AlertCreate(
            alertname="Test",
            severity="warning",
            summary="Test",
            source="test",
            annotations={
                "nested": '{"key": "value"}',  # JSON as string
                "list": "[1, 2, 3]",
            },
        )

        assert "nested" in alert.annotations

    def test_optional_fields_none(self):
        """Test optional fields accept None."""
        update = AlertUpdate(
            status=None,
            severity=None,
            summary=None,
        )

        assert update.status is None
        assert update.severity is None

    def test_list_fields_immutability(self):
        """Test list fields don't share references."""
        alert1 = AlertCreate(
            alertname="Test1",
            severity="info",
            summary="Test",
            source="test",
        )
        alert2 = AlertCreate(
            alertname="Test2",
            severity="info",
            summary="Test",
            source="test",
        )

        alert1.labels["key"] = "value"
        assert "key" not in alert2.labels


# ============================================================================
# Validation Message Tests
# ============================================================================


class TestValidationMessages:
    """Tests for validation error messages."""

    def test_pattern_validation_message(self):
        """Test pattern validation provides useful message."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreate(
                alertname="Test",
                severity="CRITICAL",  # Wrong case
                summary="Test",
                source="test",
            )

        errors = exc_info.value.errors()
        assert any("pattern" in str(e).lower() or "string_pattern" in str(e).get("type", "") for e in errors)

    def test_min_length_validation_message(self):
        """Test min_length validation provides useful message."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(content="")

        errors = exc_info.value.errors()
        assert any("min_length" in str(e).lower() or "too_short" in str(e).get("type", "") for e in errors)

    def test_max_length_validation_message(self):
        """Test max_length validation provides useful message."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(content="x" * 10001)

        errors = exc_info.value.errors()
        assert any("max_length" in str(e).lower() or "too_long" in str(e).get("type", "") for e in errors)
