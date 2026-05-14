"""End-to-end tests for complete investigation flows."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autosre.agents.kubernetes import KubernetesAgent
from autosre.agents.logs import LogAnalysisAgent
from autosre.agents.metrics import MetricsAgent
from autosre.agents.planner import Planner
from autosre.agents.synthesizer import Synthesizer
from autosre.models.investigation import (
    Investigation,
    InvestigationPlan,
    InvestigationStatus,
    SynthesisDecision,
)


class MockLLM:
    """Mock LLM for e2e tests."""

    def __init__(self, responses: dict[str, str]):
        """Initialize with response map based on prompt content."""
        self.responses = responses
        self.calls = []

    def invoke(self, messages):
        """Return response based on message content."""
        system_content = ""
        for msg in messages:
            if hasattr(msg, "content"):
                system_content += msg.content

        self.calls.append(system_content)

        # Return appropriate response based on content
        for keyword, response in self.responses.items():
            if keyword.lower() in system_content.lower():
                mock_response = MagicMock()
                mock_response.content = response
                return mock_response

        # Default response
        mock_response = MagicMock()
        mock_response.content = "{}"
        return mock_response


class TestFullInvestigationFlow:
    """Test complete investigation flow from alert to report."""

    @pytest.fixture
    def planner_response(self):
        return json.dumps({
            "hypotheses": [
                {
                    "hypothesis": "Memory leak causing OOM kills in payment pods",
                    "priority": "high",
                    "agents_to_test": ["kubernetes", "metrics"],
                },
                {
                    "hypothesis": "Database connection exhaustion",
                    "priority": "medium",
                    "agents_to_test": ["metrics", "log_analysis"],
                },
            ],
            "selected_agents": ["kubernetes", "metrics", "log_analysis"],
            "reasoning": "Error rate spike with pod restarts suggests resource issues",
        })

    @pytest.fixture
    def synthesizer_response_insufficient(self):
        return json.dumps({
            "sufficient_evidence": False,
            "confidence": 0.4,
            "summary": "Initial findings suggest memory issues but need more data",
            "gaps": ["Need pod memory metrics", "Log analysis pending"],
            "feedback": "Check memory limits and recent deployments",
            "recommended_agents": ["metrics"],
        })

    @pytest.fixture
    def synthesizer_response_sufficient(self):
        return json.dumps({
            "sufficient_evidence": True,
            "confidence": 0.85,
            "summary": "Root cause identified: OOMKilled pods due to memory leak",
            "gaps": [],
            "feedback": "",
            "recommended_agents": [],
        })

    @pytest.fixture
    def mock_llm(
        self,
        planner_response,
        synthesizer_response_sufficient,
    ):
        return MockLLM({
            "planner": planner_response,
            "synthesizer": synthesizer_response_sufficient,
        })

    @pytest.mark.asyncio
    async def test_full_investigation_single_iteration(
        self,
        sample_investigation_state,
        mock_llm,
    ):
        """Test complete investigation in single iteration."""
        # Create agents
        planner = Planner(llm=mock_llm)
        synthesizer = Synthesizer(llm=mock_llm)
        k8s_agent = KubernetesAgent()
        metrics_agent = MetricsAgent()

        # Step 1: Plan
        plan = await planner.plan(sample_investigation_state)

        assert isinstance(plan, InvestigationPlan)
        assert len(plan.hypotheses) >= 1
        assert len(plan.selected_agents) >= 1

        # Update state with plan
        sample_investigation_state["hypotheses"] = [
            h.model_dump() for h in plan.hypotheses
        ]
        sample_investigation_state["selected_agents"] = plan.selected_agents

        # Step 2: Run agents
        agent_states = {}

        if "kubernetes" in plan.selected_agents:
            k8s_state = await k8s_agent.investigate(
                sample_investigation_state,
                sample_investigation_state["hypotheses"],
            )
            agent_states["kubernetes"] = k8s_state.model_dump()

        if "metrics" in plan.selected_agents:
            metrics_state = await metrics_agent.investigate(
                sample_investigation_state,
                sample_investigation_state["hypotheses"],
            )
            agent_states["metrics"] = metrics_state.model_dump()

        sample_investigation_state["agent_states"] = agent_states

        # Step 3: Synthesize
        decision = await synthesizer.synthesize(sample_investigation_state)

        assert isinstance(decision, SynthesisDecision)
        assert decision.sufficient_evidence is True
        assert decision.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_investigation_with_iterations(
        self,
        sample_investigation_state,
        synthesizer_response_insufficient,
        synthesizer_response_sufficient,
    ):
        """Test investigation that requires multiple iterations."""
        # Create LLM that returns insufficient first, then sufficient
        call_count = {"count": 0}

        def get_response(messages):
            system_content = ""
            for msg in messages:
                if hasattr(msg, "content"):
                    system_content += msg.content

            mock_response = MagicMock()

            if "synthesizer" in system_content.lower():
                call_count["count"] += 1
                if call_count["count"] == 1:
                    mock_response.content = synthesizer_response_insufficient
                else:
                    mock_response.content = synthesizer_response_sufficient
            else:
                # Planner response
                mock_response.content = json.dumps({
                    "hypotheses": [{"hypothesis": "test", "priority": "high", "agents_to_test": ["kubernetes"]}],
                    "selected_agents": ["kubernetes"],
                    "reasoning": "test",
                })

            return mock_response

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = get_response

        planner = Planner(llm=mock_llm)
        synthesizer = Synthesizer(llm=mock_llm)
        k8s_agent = KubernetesAgent()

        max_iterations = 3
        iteration = 0

        while iteration < max_iterations:
            # Plan
            plan = await planner.plan(sample_investigation_state)
            sample_investigation_state["hypotheses"] = [h.model_dump() for h in plan.hypotheses]
            sample_investigation_state["selected_agents"] = plan.selected_agents

            # Run agent
            k8s_state = await k8s_agent.investigate(
                sample_investigation_state,
                sample_investigation_state["hypotheses"],
            )
            sample_investigation_state["agent_states"] = {"kubernetes": k8s_state.model_dump()}

            # Synthesize
            decision = await synthesizer.synthesize(sample_investigation_state)

            if decision.sufficient_evidence:
                break

            iteration += 1
            sample_investigation_state["iteration"] = iteration
            sample_investigation_state["messages"].append({
                "role": "synthesizer",
                "content": decision.feedback,
            })

        # Should have converged
        assert iteration < max_iterations
        assert decision.sufficient_evidence is True

    @pytest.mark.asyncio
    async def test_investigation_model_lifecycle(self, sample_alert):
        """Test Investigation model lifecycle."""
        # Create investigation
        investigation = Investigation(alert=sample_alert)

        assert investigation.status == InvestigationStatus.PENDING
        assert investigation.investigation_id is not None
        assert not investigation.is_complete

        # Simulate running
        investigation.status = InvestigationStatus.RUNNING

        # Add agent states
        k8s_state = investigation.get_agent_state("kubernetes")
        k8s_state.mark_started()

        from autosre.models.investigation import Finding
        k8s_state.add_finding(Finding(
            category="kubernetes",
            detail="Pod crash detected",
            severity="high",
            confidence=0.9,
        ))
        k8s_state.mark_completed("Found OOMKilled pods")

        # Add message
        investigation.add_message("planner", "Starting investigation")

        # Complete investigation
        from autosre.models.investigation import StructuredReport
        report = StructuredReport(
            title="Payment Service Incident",
            severity="critical",
            services=["payment-service"],
            root_cause="Memory leak",
        )
        investigation.mark_completed(
            conclusion="Root cause: OOMKilled pods",
            report=report,
        )

        # Verify final state
        assert investigation.is_complete
        assert investigation.status == InvestigationStatus.COMPLETED
        assert len(investigation.all_findings) == 1
        assert investigation.structured_report is not None
        assert investigation.duration_seconds > 0


class TestAlertLifecycle:
    """Tests for alert lifecycle."""

    @pytest.mark.asyncio
    async def test_prometheus_alert_to_investigation(
        self,
        api_client,
        prometheus_alert_payload,
    ):
        """Test flow from Prometheus alert to investigation."""
        # Step 1: Receive Prometheus webhook
        webhook_response = await api_client.post(
            "/api/v1/alerts/webhook/prometheus",
            json={"alerts": [prometheus_alert_payload]},
        )

        assert webhook_response.status_code == 200
        assert webhook_response.json()["created"] == 1

        # Step 2: Get created alert
        alerts_response = await api_client.get("/api/v1/alerts")
        alerts = alerts_response.json()
        assert len(alerts) >= 1

        alert = alerts[0]
        alert_data = {
            "name": alert["name"],
            "service": alert["service"],
            "severity": alert["severity"],
        }

        # Step 3: Start investigation
        inv_response = await api_client.post(
            "/api/v1/investigations",
            json={"alert": alert_data},
        )

        assert inv_response.status_code == 201
        inv_id = inv_response.json()["investigation_id"]

        # Step 4: Check investigation status
        status_response = await api_client.get(f"/api/v1/investigations/{inv_id}")

        assert status_response.status_code == 200
        assert status_response.json()["investigation_id"] == inv_id


class TestInvestigationFlow:
    """Tests for investigation flow scenarios."""

    @pytest.mark.asyncio
    async def test_investigation_api_flow(self, api_client, sample_alert):
        """Test investigation via API."""
        # Start investigation
        response = await api_client.post(
            "/api/v1/investigations",
            json={"alert": sample_alert},
        )

        assert response.status_code == 201
        inv_id = response.json()["investigation_id"]

        # Get investigation
        get_response = await api_client.get(f"/api/v1/investigations/{inv_id}")

        assert get_response.status_code == 200
        investigation = get_response.json()
        assert investigation["investigation_id"] == inv_id

        # Get findings (may be empty initially)
        findings_response = await api_client.get(
            f"/api/v1/investigations/{inv_id}/findings"
        )

        assert findings_response.status_code == 200
        assert isinstance(findings_response.json(), list)

    @pytest.mark.asyncio
    async def test_cancel_investigation_flow(self, api_client, sample_alert):
        """Test canceling an investigation."""
        # Start investigation
        start_response = await api_client.post(
            "/api/v1/investigations",
            json={"alert": sample_alert},
        )
        inv_id = start_response.json()["investigation_id"]

        # Cancel
        cancel_response = await api_client.post(
            f"/api/v1/investigations/{inv_id}/cancel"
        )

        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"

        # Verify cancelled
        get_response = await api_client.get(f"/api/v1/investigations/{inv_id}")
        assert get_response.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_investigations(self, api_client, sample_alert):
        """Test running multiple investigations concurrently."""
        # Start multiple investigations
        inv_ids = []
        for i in range(3):
            alert = {**sample_alert, "name": f"Alert-{i}"}
            response = await api_client.post(
                "/api/v1/investigations",
                json={"alert": alert},
            )
            inv_ids.append(response.json()["investigation_id"])

        # All should be created
        assert len(inv_ids) == 3
        assert len(set(inv_ids)) == 3  # All unique

        # List investigations
        list_response = await api_client.get("/api/v1/investigations")
        investigations = list_response.json()

        assert len(investigations) >= 3
