"""
End-to-end tests for chat interactions.

Test chat scenarios:
1. User asks about alert
2. AI provides context
3. User requests investigation
4. AI starts and updates
5. User approves action
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from autosre.api.app import create_app


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_client(app):
    """Create sync test client for WebSocket tests."""
    return TestClient(app)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for chat."""
    return {
        "content": "Based on my analysis of the alert, I can see that the payment service is experiencing high CPU usage...",
        "tool_calls": [],
        "metadata": {"tokens_used": 150},
    }


@pytest.fixture
def active_alert_context() -> dict[str, Any]:
    """Context with active alert for chat."""
    return {
        "alert_id": str(uuid4()),
        "alert_name": "HighCPU",
        "service": "payment-service",
        "severity": "critical",
        "status": "firing",
        "started_at": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def investigation_context() -> dict[str, Any]:
    """Context with active investigation."""
    return {
        "investigation_id": str(uuid4()),
        "alert_id": str(uuid4()),
        "status": "in_progress",
        "findings": [
            "CPU usage at 95% on pod payment-service-abc123",
            "Memory usage trending upward",
            "No recent deployments",
        ],
        "hypotheses": [
            {"statement": "Memory leak causing CPU spike", "confidence": 0.7},
        ],
    }


# ============================================================================
# Test: Basic Chat Operations
# ============================================================================


class TestBasicChatOperations:
    """Tests for basic chat message operations."""

    @pytest.mark.asyncio
    async def test_send_simple_message(self, client: AsyncClient):
        """Test sending a simple chat message."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What alerts are currently firing?",
            },
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "response" in result
        assert "session_id" in result
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_send_message_with_session(self, client: AsyncClient):
        """Test maintaining conversation context with session ID."""
        # First message
        response1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Show me the current alerts"},
        )
        
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        
        # Follow-up message with same session
        response2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Tell me more about the first one",
                "session_id": session_id,
            },
        )
        
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_send_message_with_context(
        self, client: AsyncClient, active_alert_context: dict[str, Any]
    ):
        """Test sending message with alert context."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What's happening with this alert?",
                "context": active_alert_context,
            },
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "response" in result

    @pytest.mark.asyncio
    async def test_get_chat_history(self, client: AsyncClient):
        """Test retrieving chat history."""
        # Create some messages first
        response1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "First message"},
        )
        session_id = response1.json()["session_id"]
        
        await client.post(
            "/api/v1/chat/message",
            json={"message": "Second message", "session_id": session_id},
        )
        
        # Get history
        response = await client.get(
            "/api/v1/chat/history",
            params={"session_id": session_id},
        )
        
        assert response.status_code == 200
        history = response.json()
        assert "messages" in history
        assert history["total_messages"] >= 2

    @pytest.mark.asyncio
    async def test_clear_chat_history(self, client: AsyncClient):
        """Test clearing chat history."""
        # Create a message
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test message"},
        )
        session_id = response.json()["session_id"]
        
        # Clear history
        clear_response = await client.delete(
            f"/api/v1/chat/history/{session_id}",
        )
        
        assert clear_response.status_code == 200
        assert clear_response.json()["status"] == "cleared"

    @pytest.mark.asyncio
    async def test_pagination_of_history(self, client: AsyncClient):
        """Test paginating through chat history."""
        # Create session with multiple messages
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Message 1"},
        )
        session_id = response.json()["session_id"]
        
        for i in range(2, 6):
            await client.post(
                "/api/v1/chat/message",
                json={"message": f"Message {i}", "session_id": session_id},
            )
        
        # Get first page
        page1 = await client.get(
            "/api/v1/chat/history",
            params={"session_id": session_id, "limit": 2, "offset": 0},
        )
        
        # Get second page
        page2 = await client.get(
            "/api/v1/chat/history",
            params={"session_id": session_id, "limit": 2, "offset": 2},
        )
        
        assert page1.status_code == 200
        assert page2.status_code == 200
        assert len(page1.json()["messages"]) <= 2


# ============================================================================
# Test: Alert-Related Chat
# ============================================================================


class TestAlertChat:
    """Tests for chat interactions about alerts."""

    @pytest.mark.asyncio
    async def test_ask_about_firing_alerts(self, client: AsyncClient):
        """Test asking about currently firing alerts."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "What alerts are currently firing?"},
        )
        
        assert response.status_code == 200
        # Response should mention alerts or that there are none
        assert "response" in response.json()

    @pytest.mark.asyncio
    async def test_ask_about_specific_alert(
        self, client: AsyncClient, active_alert_context: dict[str, Any]
    ):
        """Test asking about a specific alert."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Give me details about this alert",
                "context": active_alert_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ask_for_alert_runbook(self, client: AsyncClient):
        """Test asking for runbook for an alert."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Do we have a runbook for high CPU alerts?",
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ask_for_similar_alerts(
        self, client: AsyncClient, active_alert_context: dict[str, Any]
    ):
        """Test asking about similar past alerts."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Have we seen similar alerts before?",
                "context": active_alert_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_alert_severity_query(self, client: AsyncClient):
        """Test asking about alerts by severity."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Show me all critical alerts"},
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_alert_service_query(self, client: AsyncClient):
        """Test asking about alerts by service."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Are there any alerts for the payment service?"},
        )
        
        assert response.status_code == 200


# ============================================================================
# Test: Investigation Chat
# ============================================================================


class TestInvestigationChat:
    """Tests for chat interactions during investigations."""

    @pytest.mark.asyncio
    async def test_request_investigation(
        self, client: AsyncClient, active_alert_context: dict[str, Any]
    ):
        """Test requesting to start an investigation."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Start an investigation for this alert",
                "context": active_alert_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_check_investigation_status(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test checking investigation status."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What's the status of the investigation?",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ask_about_findings(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test asking about investigation findings."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What have you found so far?",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ask_about_hypotheses(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test asking about current hypotheses."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What do you think is causing this?",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_suggest_investigation_direction(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test user suggesting investigation direction."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Check if there were any recent deployments",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_specific_data(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test requesting specific data during investigation."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Show me the CPU metrics for the last hour",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200


# ============================================================================
# Test: Action Approval Chat
# ============================================================================


class TestActionApprovalChat:
    """Tests for chat interactions for action approval."""

    @pytest.mark.asyncio
    async def test_approve_action_via_chat(self, client: AsyncClient):
        """Test approving an action through chat."""
        action_context = {
            "action_id": str(uuid4()),
            "action_type": "scale",
            "name": "scale_up_replicas",
            "description": "Scale payment-service to 5 replicas",
            "requires_approval": True,
            "risk_level": "medium",
        }
        
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Yes, approve scaling up the replicas",
                "context": {"pending_action": action_context},
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reject_action_via_chat(self, client: AsyncClient):
        """Test rejecting an action through chat."""
        action_context = {
            "action_id": str(uuid4()),
            "action_type": "restart",
            "name": "restart_pod",
            "description": "Restart pod payment-service-abc123",
            "requires_approval": True,
            "risk_level": "high",
        }
        
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "No, don't restart the pod yet",
                "context": {"pending_action": action_context},
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ask_about_action_impact(self, client: AsyncClient):
        """Test asking about action impact before approval."""
        action_context = {
            "action_id": str(uuid4()),
            "action_type": "rollback",
            "name": "rollback_deployment",
            "description": "Rollback to previous version",
            "requires_approval": True,
            "risk_level": "high",
        }
        
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What will happen if I approve this rollback?",
                "context": {"pending_action": action_context},
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_alternative_action(self, client: AsyncClient):
        """Test requesting an alternative to proposed action."""
        action_context = {
            "action_id": str(uuid4()),
            "action_type": "restart",
            "name": "restart_deployment",
            "description": "Restart all pods",
            "requires_approval": True,
        }
        
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Can we try scaling up instead of restarting?",
                "context": {"pending_action": action_context},
            },
        )
        
        assert response.status_code == 200


# ============================================================================
# Test: WebSocket Chat
# ============================================================================


class TestWebSocketChat:
    """Tests for WebSocket-based real-time chat."""

    def test_websocket_connection(self, sync_client: TestClient):
        """Test WebSocket connection establishment."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            # Should receive connection confirmation
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "session_id" in data

    def test_websocket_send_message(self, sync_client: TestClient):
        """Test sending message via WebSocket."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            # Receive connection
            ws.receive_json()
            
            # Send message
            ws.send_json({
                "type": "message",
                "content": "What alerts are firing?",
            })
            
            # Might receive thinking status first
            response = ws.receive_json()
            if response["type"] == "status":
                response = ws.receive_json()
            
            assert response["type"] == "response"
            assert "content" in response

    def test_websocket_ping_pong(self, sync_client: TestClient):
        """Test WebSocket keepalive with ping/pong."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()  # connection message
            
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            
            assert response["type"] == "pong"

    def test_websocket_with_context(self, sync_client: TestClient):
        """Test WebSocket message with context."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            
            ws.send_json({
                "type": "message",
                "content": "Tell me about this alert",
                "context": {
                    "alert_id": str(uuid4()),
                    "alert_name": "HighCPU",
                },
            })
            
            # Get response (skip status messages)
            response = ws.receive_json()
            while response.get("type") == "status":
                response = ws.receive_json()
            
            assert response["type"] == "response"

    def test_websocket_error_handling(self, sync_client: TestClient):
        """Test WebSocket error handling."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            
            # Send empty message
            ws.send_json({
                "type": "message",
                "content": "",
            })
            
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_websocket_invalid_json(self, sync_client: TestClient):
        """Test WebSocket handles invalid JSON."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            
            # Send invalid JSON
            ws.send_text("not json")
            
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_websocket_unknown_message_type(self, sync_client: TestClient):
        """Test WebSocket handles unknown message types."""
        with sync_client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            
            ws.send_json({
                "type": "unknown_type",
                "data": "test",
            })
            
            response = ws.receive_json()
            assert response["type"] == "error"


# ============================================================================
# Test: Conversational Flow
# ============================================================================


class TestConversationalFlow:
    """Tests for multi-turn conversational flows."""

    @pytest.mark.asyncio
    async def test_full_investigation_conversation(self, client: AsyncClient):
        """Test complete conversation flow for investigation."""
        # Start conversation
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "I'm seeing high CPU on payment service"},
        )
        session_id = r1.json()["session_id"]
        
        # AI asks for more info, user provides
        r2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "It started about 30 minutes ago",
                "session_id": session_id,
            },
        )
        
        # User requests investigation
        r3 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Can you investigate this?",
                "session_id": session_id,
            },
        )
        
        # User checks status
        r4 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What have you found?",
                "session_id": session_id,
            },
        )
        
        # All should succeed
        assert all(r.status_code == 200 for r in [r1, r2, r3, r4])

    @pytest.mark.asyncio
    async def test_clarification_flow(self, client: AsyncClient):
        """Test AI asking for clarification."""
        # Ambiguous request
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Something is broken"},
        )
        session_id = r1.json()["session_id"]
        
        # User provides clarification
        r2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "The checkout service is returning 500 errors",
                "session_id": session_id,
            },
        )
        
        assert r1.status_code == 200
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_topic_switch_in_conversation(self, client: AsyncClient):
        """Test switching topics in conversation."""
        # Start with one topic
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Show me CPU metrics"},
        )
        session_id = r1.json()["session_id"]
        
        # Switch to different topic
        r2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Actually, show me the current alerts instead",
                "session_id": session_id,
            },
        )
        
        assert r1.status_code == 200
        assert r2.status_code == 200


# ============================================================================
# Test: Chat Context Awareness
# ============================================================================


class TestChatContextAwareness:
    """Tests for chat context awareness."""

    @pytest.mark.asyncio
    async def test_remembers_mentioned_service(self, client: AsyncClient):
        """Test chat remembers previously mentioned service."""
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "I'm looking at the payment service"},
        )
        session_id = r1.json()["session_id"]
        
        r2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What alerts does it have?",
                "session_id": session_id,
            },
        )
        
        assert r2.status_code == 200
        # Response should understand "it" refers to payment service

    @pytest.mark.asyncio
    async def test_uses_alert_context(
        self, client: AsyncClient, active_alert_context: dict[str, Any]
    ):
        """Test chat uses provided alert context."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Is this critical?",
                "context": active_alert_context,
            },
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_uses_investigation_context(
        self, client: AsyncClient, investigation_context: dict[str, Any]
    ):
        """Test chat uses investigation context."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What's the main hypothesis?",
                "context": investigation_context,
            },
        )
        
        assert response.status_code == 200


# ============================================================================
# Test: Chat Edge Cases
# ============================================================================


class TestChatEdgeCases:
    """Tests for chat edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_message(self, client: AsyncClient):
        """Test handling empty message."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": ""},
        )
        
        # Should be rejected
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_very_long_message(self, client: AsyncClient):
        """Test handling very long message."""
        long_message = "a" * 15000  # Exceeds max_length=10000
        
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": long_message},
        )
        
        # Should be rejected
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_special_characters(self, client: AsyncClient):
        """Test handling special characters in message."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "What's happening with service <test>? 🔥"},
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self, client: AsyncClient):
        """Test handling SQL injection attempt."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "'; DROP TABLE alerts; --"},
        )
        
        # Should be handled safely
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_session_id(self, client: AsyncClient):
        """Test handling invalid session ID."""
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Test",
                "session_id": "invalid-session-id-that-does-not-exist",
            },
        )
        
        # Should create new session or handle gracefully
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_concurrent_messages_same_session(self, client: AsyncClient):
        """Test handling concurrent messages in same session."""
        # Create session
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "First"},
        )
        session_id = r1.json()["session_id"]
        
        # Send multiple concurrent messages
        tasks = [
            client.post(
                "/api/v1/chat/message",
                json={"message": f"Concurrent {i}", "session_id": session_id},
            )
            for i in range(5)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    async def test_history_for_nonexistent_session(self, client: AsyncClient):
        """Test getting history for non-existent session."""
        response = await client.get(
            "/api/v1/chat/history",
            params={"session_id": "nonexistent-session-12345"},
        )
        
        assert response.status_code == 200
        assert response.json()["messages"] == []


# ============================================================================
# Test: Chat Response Quality
# ============================================================================


class TestChatResponseQuality:
    """Tests for chat response quality indicators."""

    @pytest.mark.asyncio
    async def test_response_has_metadata(self, client: AsyncClient):
        """Test response includes metadata."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test message"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "timestamp" in result
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_response_has_session_continuity(self, client: AsyncClient):
        """Test session continuity in responses."""
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "First"},
        )
        session_id = r1.json()["session_id"]
        
        r2 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Second", "session_id": session_id},
        )
        
        assert r2.json()["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_message_ids_are_unique(self, client: AsyncClient):
        """Test that message IDs are unique."""
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "First"},
        )
        
        r2 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Second"},
        )
        
        assert r1.json()["message_id"] != r2.json()["message_id"]
