"""Tests for Postmortem Generator and Policy."""

import pytest
from datetime import datetime, date, timedelta
from pathlib import Path
import tempfile

from autosre.postmortem.generator import (
    PostmortemGenerator,
    PostmortemDraft,
    ActionItem,
    ActionPriority,
    AIPerformanceReview,
    TimelineEvent,
)
from autosre.postmortem.policy import (
    PostmortemPolicy,
    PostmortemTrigger,
    TriggerType,
    PolicyConfig,
    load_policy_from_yaml,
    save_policy_to_yaml,
)


class TestPostmortemGenerator:
    """Tests for PostmortemGenerator."""
    
    def test_generate_from_investigation(self):
        """Test generating postmortem from investigation data."""
        investigation = {
            "alert": {
                "name": "HighLatencyAlert",
                "failure_mode": "P99 latency exceeded 5s on payment service",
                "user_impact": "Checkout taking 10+ seconds",
                "fired_at": "2024-01-15T10:30:00Z",
            },
            "synthesis": {
                "root_cause": "Database query missing index on orders table",
                "summary": "Payment service latency spike due to slow DB queries",
                "lessons_learned": [
                    "Need query performance monitoring",
                    "Missing index detection in CI/CD",
                ],
            },
            "metrics": {
                "ttd_minutes": 5,
                "ttm_minutes": 15,
                "ttr_minutes": 45,
            },
            "timeline": [
                {
                    "timestamp": "2024-01-15T10:25:00Z",
                    "description": "First slow queries observed",
                    "actor": "system",
                },
                {
                    "timestamp": "2024-01-15T10:30:00Z",
                    "description": "Alert fired",
                    "actor": "monitoring",
                },
            ],
        }
        
        generator = PostmortemGenerator()
        draft = generator.generate_from_investigation(
            investigation=investigation,
            incident_id="INC-2024-001",
            title="Payment Service Latency Spike",
        )
        
        assert draft.incident_id == "INC-2024-001"
        assert draft.title == "Payment Service Latency Spike"
        assert "database" in draft.root_cause.lower() or "index" in draft.root_cause.lower()
        assert draft.time_to_resolve_minutes == 45
        assert len(draft.timeline) > 0
        assert len(draft.lessons_learned) > 0
    
    def test_blameless_system_failures(self):
        """Test that system failures focus on systems, not people."""
        investigation = {
            "alert": {"name": "TestAlert"},
            "synthesis": {
                "root_cause": "The monitoring system failed to detect the issue",
                "system_failures": [
                    "Monitoring gaps in payment flow",
                    "Missing alerting for edge cases",
                ],
            },
        }
        
        generator = PostmortemGenerator()
        draft = generator.generate_from_investigation(
            investigation=investigation,
            incident_id="INC-001",
        )
        
        # Should have system failures, not blaming individuals
        assert len(draft.system_failures) > 0
        for failure in draft.system_failures:
            # No personal names or blame
            assert "should have" not in failure.lower()
            assert "failed to" not in failure.lower() or "system" in failure.lower() or "monitoring" in failure.lower()
    
    def test_ai_performance_review(self):
        """Test AI performance review generation."""
        investigation = {
            "alert": {"name": "TestAlert"},
            "synthesis": {"root_cause": "Test cause"},
            "ai_metrics": {
                "total_actions": 10,
                "correct_actions": 8,
                "incorrect_actions": 2,
                "deliberation_time_seconds": 120,
                "action_time_seconds": 300,
                "evidence_citations": 5,
                "hypotheses_tested": 3,
                "false_positives": 1,
            },
        }
        
        generator = PostmortemGenerator()
        draft = generator.generate_from_investigation(
            investigation=investigation,
            incident_id="INC-001",
        )
        
        assert draft.ai_performance is not None
        assert draft.ai_performance.total_actions == 10
        assert draft.ai_performance.accuracy_rate == 0.8
        assert draft.ai_performance.evidence_citations == 5
    
    def test_action_items_generated(self):
        """Test that action items are generated from failures."""
        investigation = {
            "alert": {"name": "TestAlert"},
            "synthesis": {
                "root_cause": "Missing runbook",
                "system_failures": [
                    "No runbook was available for this alert",
                    "Monitoring did not catch the issue",
                ],
            },
        }
        
        generator = PostmortemGenerator(default_owner="SRE Team")
        draft = generator.generate_from_investigation(
            investigation=investigation,
            incident_id="INC-001",
        )
        
        assert len(draft.action_items) > 0
        # Should have action items for each system failure
        for item in draft.action_items:
            assert item.owner is not None
            assert item.due_date is not None
            assert item.priority is not None
    
    def test_markdown_generation(self):
        """Test markdown document generation."""
        draft = PostmortemDraft(
            title="Test Incident",
            incident_id="INC-001",
            summary="Test summary",
            root_cause="Test root cause",
            system_failures=["System A failed", "Process B was missing"],
            lessons_learned=["Lesson 1", "Lesson 2"],
        )
        
        draft.action_items.append(ActionItem(
            title="Fix monitoring",
            description="Add missing alerts",
            owner="SRE Team",
            priority=ActionPriority.P1,
            due_date=date.today() + timedelta(days=7),
            category="monitoring",
        ))
        
        markdown = draft.to_markdown()
        
        assert "# Incident Postmortem: Test Incident" in markdown
        assert "## Summary" in markdown
        assert "## Root Cause" in markdown
        assert "## What SYSTEMS Failed (Not People)" in markdown
        assert "## Action Items" in markdown
        assert "## Lessons Learned" in markdown
        assert "blameless" in markdown.lower()
    
    def test_add_action_item(self):
        """Test adding action items to draft."""
        generator = PostmortemGenerator()
        draft = PostmortemDraft(
            title="Test",
            incident_id="INC-001",
        )
        
        generator.add_action_item(
            draft=draft,
            title="Improve monitoring",
            description="Add better alerts",
            owner="alice@example.com",
            priority=ActionPriority.P1,
            due_date=date.today() + timedelta(days=5),
            category="monitoring",
        )
        
        assert len(draft.action_items) == 1
        assert draft.action_items[0].title == "Improve monitoring"
        assert draft.action_items[0].owner == "alice@example.com"
    
    def test_add_lesson_learned(self):
        """Test adding lessons learned."""
        generator = PostmortemGenerator()
        draft = PostmortemDraft(
            title="Test",
            incident_id="INC-001",
        )
        
        generator.add_lesson_learned(draft, "Always verify config before deploy")
        generator.add_lesson_learned(draft, "Add pre-deploy checklist")
        
        assert len(draft.lessons_learned) == 2


class TestAIPerformanceReview:
    """Tests for AIPerformanceReview."""
    
    def test_accuracy_rate(self):
        """Test accuracy rate calculation."""
        review = AIPerformanceReview(
            total_actions=10,
            correct_actions=8,
            incorrect_actions=2,
        )
        
        assert review.accuracy_rate == 0.8
    
    def test_deliberation_ratio(self):
        """Test deliberation ratio calculation."""
        review = AIPerformanceReview(
            time_spent_deliberating_seconds=60,
            time_spent_acting_seconds=240,
        )
        
        assert review.deliberation_ratio == 0.2  # 60 / (60 + 240)
    
    def test_observations_for_low_accuracy(self):
        """Test observations are generated for low accuracy."""
        review = AIPerformanceReview(
            total_actions=10,
            correct_actions=5,
            incorrect_actions=5,
        )
        
        # Add observation manually (normally done by generator)
        if review.accuracy_rate < 0.8:
            review.observations.append(
                f"Accuracy rate was {review.accuracy_rate:.1%}, below 80% target"
            )
        
        assert len(review.observations) > 0
        assert "50.0%" in review.observations[0]
    
    def test_markdown_output(self):
        """Test markdown formatting."""
        review = AIPerformanceReview(
            total_actions=5,
            correct_actions=4,
            incorrect_actions=1,
            time_spent_deliberating_seconds=30,
            time_spent_acting_seconds=120,
            evidence_citations=3,
        )
        review.observations.append("Good deliberation time")
        review.improvements.append("Could cite more evidence")
        
        markdown = review.to_markdown()
        
        assert "AI Performance Metrics" in markdown
        assert "Total actions: 5" in markdown
        assert "Observations" in markdown
        assert "Recommended Improvements" in markdown


class TestPostmortemPolicy:
    """Tests for PostmortemPolicy."""
    
    def test_evaluate_user_impact_trigger(self):
        """Test user visible degradation trigger."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "user_impact": "Users seeing 500 errors",
        }
        
        requires, triggers = policy.evaluate_incident("INC-001", incident_data)
        
        assert requires
        assert TriggerType.USER_VISIBLE_DEGRADATION in triggers
    
    def test_evaluate_data_loss_trigger(self):
        """Test data loss trigger."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "data_loss": True,
            "description": "Some records were corrupted",
        }
        
        requires, triggers = policy.evaluate_incident("INC-002", incident_data)
        
        assert requires
        assert TriggerType.DATA_LOSS in triggers
    
    def test_evaluate_long_resolution_trigger(self):
        """Test long resolution time trigger."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "time_to_resolve_minutes": 45,  # > 30 minute threshold
        }
        
        requires, triggers = policy.evaluate_incident("INC-003", incident_data)
        
        assert requires
        assert TriggerType.LONG_RESOLUTION in triggers
    
    def test_evaluate_on_call_intervention_trigger(self):
        """Test on-call intervention trigger."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "on_call_paged": True,
        }
        
        requires, triggers = policy.evaluate_incident("INC-004", incident_data)
        
        assert requires
        assert TriggerType.ON_CALL_INTERVENTION in triggers
    
    def test_evaluate_monitoring_failure_trigger(self):
        """Test monitoring failure trigger."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "monitoring_failure": True,
        }
        
        requires, triggers = policy.evaluate_incident("INC-005", incident_data)
        
        assert requires
        assert TriggerType.MONITORING_FAILURE in triggers
    
    def test_no_triggers_fire(self):
        """Test incident that doesn't trigger postmortem."""
        policy = PostmortemPolicy()
        
        incident_data = {
            "time_to_resolve_minutes": 10,  # Under threshold
            "user_facing": False,
        }
        
        requires, triggers = policy.evaluate_incident("INC-006", incident_data)
        
        assert not requires
        assert len(triggers) == 0
    
    def test_create_postmortem_ticket(self):
        """Test postmortem ticket creation."""
        policy = PostmortemPolicy()
        
        ticket = policy.create_postmortem_ticket(
            incident_id="INC-007",
            title="Database outage",
            triggered_by=[TriggerType.USER_VISIBLE_DEGRADATION, TriggerType.ON_CALL_INTERVENTION],
            assignee="alice@example.com",
        )
        
        assert ticket.incident_id == "INC-007"
        assert "Postmortem" in ticket.title
        assert ticket.assignee == "alice@example.com"
        assert ticket.status == "open"
        assert ticket.due_date > datetime.utcnow()
    
    def test_complete_postmortem(self):
        """Test marking postmortem as complete."""
        policy = PostmortemPolicy()
        
        policy.create_postmortem_ticket(
            incident_id="INC-008",
            title="Test incident",
            triggered_by=[TriggerType.MANUAL],
        )
        
        ticket = policy.complete_postmortem(
            incident_id="INC-008",
            postmortem_url="https://docs.example.com/postmortems/inc-008",
        )
        
        assert ticket is not None
        assert ticket.status == "completed"
        assert ticket.completed_at is not None
        assert ticket.postmortem_url is not None
    
    def test_get_overdue_postmortems(self):
        """Test getting overdue postmortems."""
        config = PolicyConfig(default_due_days=0)  # Due immediately
        policy = PostmortemPolicy(config=config)
        
        # Create a ticket that's already overdue
        policy.create_postmortem_ticket(
            incident_id="INC-009",
            title="Old incident",
            triggered_by=[TriggerType.MANUAL],
        )
        
        # Manually backdate it
        ticket = policy.get_ticket("INC-009")
        ticket.due_date = datetime.utcnow() - timedelta(days=1)
        
        overdue = policy.get_overdue_postmortems()
        
        assert len(overdue) == 1
        assert overdue[0].incident_id == "INC-009"
        assert overdue[0].status == "overdue"
    
    def test_completion_rate(self):
        """Test completion rate calculation."""
        policy = PostmortemPolicy()
        
        # Create 3 tickets
        for i in range(3):
            policy.create_postmortem_ticket(
                incident_id=f"INC-{i:03d}",
                title=f"Incident {i}",
                triggered_by=[TriggerType.MANUAL],
            )
        
        # Complete 2 of them
        policy.complete_postmortem("INC-000")
        policy.complete_postmortem("INC-001")
        
        stats = policy.get_completion_rate()
        
        assert stats["total"] == 3
        assert stats["completed"] == 2
        assert stats["completion_rate"] == pytest.approx(0.667, rel=0.01)
    
    def test_list_tickets(self):
        """Test listing tickets with filter."""
        policy = PostmortemPolicy()
        
        # Create tickets
        policy.create_postmortem_ticket("INC-A", "A", [TriggerType.MANUAL])
        policy.create_postmortem_ticket("INC-B", "B", [TriggerType.MANUAL])
        
        # Complete one
        policy.complete_postmortem("INC-A")
        
        # List all
        all_tickets = policy.list_tickets()
        assert len(all_tickets) == 2
        
        # List completed only
        completed = policy.list_tickets(status="completed")
        assert len(completed) == 1
        assert completed[0].incident_id == "INC-A"


class TestPolicyYAML:
    """Tests for YAML policy loading/saving."""
    
    def test_load_policy_from_yaml(self):
        """Test loading policy from YAML file."""
        yaml_content = """
triggers:
  - type: user_visible_degradation
    description: User impact detected
    enabled: true
  - type: long_resolution
    description: Resolution > 30 min
    threshold: 30
    enabled: true
resolution_time_threshold_minutes: 30
default_due_days: 7
require_action_items: true
require_ai_review: true
auto_create_ticket: false
notify_on_trigger: true
notification_channel: "#incidents"
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = load_policy_from_yaml(f.name)
        
        assert len(config.triggers) == 2
        assert config.resolution_time_threshold_minutes == 30
        assert config.default_due_days == 7
        assert config.auto_create_ticket is False
        assert config.notification_channel == "#incidents"
    
    def test_save_policy_to_yaml(self):
        """Test saving policy to YAML file."""
        config = PolicyConfig.default()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            save_policy_to_yaml(config, f.name)
            
            # Load it back
            loaded = load_policy_from_yaml(f.name)
        
        assert len(loaded.triggers) == len(config.triggers)
        assert loaded.resolution_time_threshold_minutes == config.resolution_time_threshold_minutes
    
    def test_default_config(self):
        """Test default policy configuration."""
        config = PolicyConfig.default()
        
        assert len(config.triggers) >= 5
        
        # Check required triggers exist
        trigger_types = [t.trigger_type for t in config.triggers]
        assert TriggerType.USER_VISIBLE_DEGRADATION in trigger_types
        assert TriggerType.DATA_LOSS in trigger_types
        assert TriggerType.ON_CALL_INTERVENTION in trigger_types
        assert TriggerType.LONG_RESOLUTION in trigger_types
        assert TriggerType.MONITORING_FAILURE in trigger_types


class TestTimelineEvent:
    """Tests for TimelineEvent."""
    
    def test_to_markdown(self):
        """Test timeline event markdown formatting."""
        event = TimelineEvent(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            description="Alert fired for high latency",
            actor="monitoring",
            event_type="detection",
        )
        
        markdown = event.to_markdown()
        
        assert "2024-01-15 10:30:00 UTC" in markdown
        assert "[monitoring]" in markdown
        assert "Alert fired for high latency" in markdown


class TestActionItem:
    """Tests for ActionItem."""
    
    def test_to_markdown(self):
        """Test action item markdown formatting."""
        item = ActionItem(
            title="Add monitoring for edge case",
            description="Cover the failure scenario that wasn't caught",
            owner="alice@example.com",
            priority=ActionPriority.P1,
            due_date=date(2024, 1, 20),
            category="monitoring",
            completed=False,
        )
        
        markdown = item.to_markdown()
        
        assert "[P1]" in markdown
        assert "Add monitoring for edge case" in markdown
        assert "alice@example.com" in markdown
        assert "2024-01-20" in markdown
        assert "⬜" in markdown  # Not completed
    
    def test_completed_item(self):
        """Test completed action item."""
        item = ActionItem(
            title="Fixed item",
            description="Done",
            owner="bob@example.com",
            priority=ActionPriority.P2,
            due_date=date.today(),
            completed=True,
        )
        
        markdown = item.to_markdown()
        
        assert "✅" in markdown


class TestDeliberateReasoning:
    """Tests for deliberate reasoning utilities."""
    
    def test_pause_checklist_prompt(self):
        """Test PAUSE checklist prompt is included."""
        from autosre.utils.deliberate import PAUSE_CHECKLIST_PROMPT
        
        assert "Evidence" in PAUSE_CHECKLIST_PROMPT or "Proof" in PAUSE_CHECKLIST_PROMPT
        assert "Alternatives" in PAUSE_CHECKLIST_PROMPT or "safer" in PAUSE_CHECKLIST_PROMPT.lower()
        assert "Assumptions" in PAUSE_CHECKLIST_PROMPT
        assert "Disprove" in PAUSE_CHECKLIST_PROMPT or "contradict" in PAUSE_CHECKLIST_PROMPT.lower()
        assert "Consult" in PAUSE_CHECKLIST_PROMPT or "Expert" in PAUSE_CHECKLIST_PROMPT
    
    def test_deliberation_record(self):
        """Test deliberation record tracking."""
        from autosre.utils.deliberate import (
            DeliberateReasoner,
            EvidenceCitation,
        )
        
        reasoner = DeliberateReasoner()
        record = reasoner.start_deliberation("Restart the database pod")
        
        # Add PAUSE checklist items
        reasoner.add_evidence(
            record,
            source="Pod logs",
            data="OOMKilled event at 10:30",
            confidence=0.9,
        )
        
        reasoner.add_disprove_attempt(
            record,
            "Checked if issue is upstream - network is healthy",
        )
        
        reasoner.add_assumption(
            record,
            "Assuming memory leak is in application, not infrastructure",
        )
        
        reasoner.add_safer_alternative(
            record,
            "Could increase memory limit instead of restart",
        )
        
        # Complete deliberation
        can_proceed, warnings = reasoner.complete_deliberation(
            record,
            proceed=True,
            reason="Evidence strongly suggests OOM, restart is quick fix",
        )
        
        assert can_proceed
        assert record.proceed
        assert record.checklist_completion >= 0.8
        assert record.deliberation_seconds > 0
    
    def test_require_evidence(self):
        """Test evidence requirement enforcement."""
        from autosre.utils.deliberate import DeliberateReasoner
        
        reasoner = DeliberateReasoner(require_evidence=True)
        record = reasoner.start_deliberation("Delete old logs")
        
        # Try to proceed without evidence
        can_proceed, warnings = reasoner.complete_deliberation(
            record,
            proceed=True,
            reason="Logs are old",
        )
        
        assert not can_proceed
        assert any("evidence" in w.lower() for w in warnings)
    
    def test_metrics_tracking(self):
        """Test deliberation metrics tracking."""
        from autosre.utils.deliberate import DeliberateReasoner
        
        reasoner = DeliberateReasoner()
        
        # Complete a deliberation
        record = reasoner.start_deliberation("Test action")
        reasoner.add_evidence(record, "test", "data")
        reasoner.complete_deliberation(record, proceed=True)
        
        # Record action time
        reasoner.record_action_time(60)
        
        metrics = reasoner.get_metrics()
        
        assert metrics["total_deliberations"] == 1
        assert metrics["total_action_seconds"] == 60
        assert metrics["evidence_citations"] == 1
