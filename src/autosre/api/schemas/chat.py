"""Chat API schemas for AutoSRE V2.

Defines request/response models for the chat interface,
including synchronous messages and WebSocket streaming.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatContext(BaseModel):
    """Context for a chat message."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "alert_id": "alert_abc123",
                "investigation_id": "inv_xyz789",
                "service": "api-gateway",
                "namespace": "production",
            }
        },
    )

    alert_id: str | None = Field(
        default=None,
        alias="alertId",
        description="Associated alert ID",
        json_schema_extra={"example": "alert_abc123"},
    )
    investigation_id: str | None = Field(
        default=None,
        alias="investigationId",
        description="Associated investigation ID",
        json_schema_extra={"example": "inv_xyz789"},
    )
    service: str | None = Field(
        default=None,
        description="Service context",
        json_schema_extra={"example": "api-gateway"},
    )
    namespace: str | None = Field(
        default=None,
        description="Namespace context",
        json_schema_extra={"example": "production"},
    )
    additional: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data",
    )


class ChatMessageBase(BaseModel):
    """Base chat message fields."""

    model_config = ConfigDict(
        populate_by_name=True,
    )

    role: MessageRole = Field(
        ...,
        description="Message role (user, assistant, or system)",
        json_schema_extra={"example": "user"},
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Message content",
        json_schema_extra={"example": "What's causing the high CPU on api-gateway?"},
    )


class ChatMessage(ChatMessageBase):
    """Full chat message with metadata."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "msg_abc123",
                "role": "assistant",
                "content": "Based on my analysis, the high CPU is caused by increased traffic...",
                "timestamp": "2024-01-15T10:40:00Z",
                "metadata": {
                    "tokens_used": 150,
                    "model": "claude-sonnet-4-20250514",
                },
            }
        },
    )

    id: str = Field(
        ...,
        description="Message ID",
        json_schema_extra={"example": "msg_abc123"},
    )
    timestamp: datetime = Field(
        ...,
        description="Message timestamp",
        json_schema_extra={"example": "2024-01-15T10:40:00Z"},
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
        json_schema_extra={"example": {"tokens_used": 150}},
    )


class SendMessageRequest(BaseModel):
    """Request to send a chat message."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "message": "What's causing the high CPU on api-gateway?",
                "session_id": "sess_xyz789",
                "context": {
                    "alert_id": "alert_abc123",
                    "service": "api-gateway",
                },
                "stream": False,
            }
        },
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message to send",
        json_schema_extra={"example": "What's causing the high CPU on api-gateway?"},
    )
    session_id: str | None = Field(
        default=None,
        alias="sessionId",
        max_length=100,
        description="Session ID for conversation continuity (auto-generated if not provided)",
        json_schema_extra={"example": "sess_xyz789"},
    )
    context: ChatContext | None = Field(
        default=None,
        description="Additional context (alert, investigation, etc.)",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response (for SSE/WebSocket)",
    )
    include_history: bool = Field(
        default=True,
        alias="includeHistory",
        description="Whether to include conversation history in the response",
    )
    max_history: int = Field(
        default=20,
        ge=0,
        le=100,
        alias="maxHistory",
        description="Maximum number of history messages to include",
    )


class SendMessageResponse(BaseModel):
    """Response from sending a chat message."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "message_id": "msg_def456",
                "session_id": "sess_xyz789",
                "response": "Based on my analysis, the high CPU is caused by...",
                "timestamp": "2024-01-15T10:40:30Z",
                "metadata": {
                    "user_message_id": "msg_abc123",
                    "tokens_used": 250,
                    "model": "claude-sonnet-4-20250514",
                    "latency_ms": 1500.0,
                },
            }
        },
    )

    message_id: str = Field(
        ...,
        alias="messageId",
        description="ID of the assistant's response message",
        json_schema_extra={"example": "msg_def456"},
    )
    session_id: str = Field(
        ...,
        alias="sessionId",
        description="Session ID (may be newly created)",
        json_schema_extra={"example": "sess_xyz789"},
    )
    response: str = Field(
        ...,
        description="Assistant's response",
        json_schema_extra={"example": "Based on my analysis, the high CPU is caused by..."},
    )
    timestamp: datetime = Field(
        ...,
        description="Response timestamp",
        json_schema_extra={"example": "2024-01-15T10:40:30Z"},
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata",
        json_schema_extra={
            "example": {
                "user_message_id": "msg_abc123",
                "tokens_used": 250,
            }
        },
    )


class ChatHistoryResponse(BaseModel):
    """Response containing chat history."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "session_id": "sess_xyz789",
                "messages": [
                    {
                        "id": "msg_001",
                        "role": "user",
                        "content": "What's the status?",
                        "timestamp": "2024-01-15T10:35:00Z",
                    },
                    {
                        "id": "msg_002",
                        "role": "assistant",
                        "content": "There's an active alert...",
                        "timestamp": "2024-01-15T10:35:05Z",
                    },
                ],
                "total_messages": 10,
                "has_more": True,
            }
        },
    )

    session_id: str = Field(
        ...,
        alias="sessionId",
        description="Session ID",
        json_schema_extra={"example": "sess_xyz789"},
    )
    messages: list[ChatMessage] = Field(
        ...,
        description="List of messages in chronological order",
    )
    total_messages: int = Field(
        ...,
        alias="totalMessages",
        ge=0,
        description="Total number of messages in the session",
        json_schema_extra={"example": 10},
    )
    has_more: bool = Field(
        ...,
        alias="hasMore",
        description="Whether there are more messages available",
        json_schema_extra={"example": True},
    )


class ClearHistoryResponse(BaseModel):
    """Response from clearing chat history."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "status": "cleared",
                "session_id": "sess_xyz789",
                "messages_deleted": 15,
            }
        },
    )

    status: str = Field(
        default="cleared",
        description="Operation status",
    )
    session_id: str = Field(
        ...,
        alias="sessionId",
        description="Session that was cleared",
    )
    messages_deleted: int = Field(
        default=0,
        alias="messagesDeleted",
        ge=0,
        description="Number of messages deleted",
    )


class StreamChunkType(str, Enum):
    """Types of streaming chunks."""

    START = "start"
    CONTENT = "content"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATUS = "status"
    ERROR = "error"
    END = "end"


class StreamChunk(BaseModel):
    """A chunk of a streaming response."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "content",
                "content": "Based on my analysis",
                "message_id": "msg_abc123",
                "session_id": "sess_xyz789",
                "timestamp": "2024-01-15T10:40:00Z",
            }
        },
    )

    type: StreamChunkType = Field(
        ...,
        description="Type of chunk",
        json_schema_extra={"example": "content"},
    )
    content: str | None = Field(
        default=None,
        description="Text content (for content chunks)",
        json_schema_extra={"example": "Based on my analysis"},
    )
    message_id: str | None = Field(
        default=None,
        alias="messageId",
        description="Message ID being streamed",
    )
    session_id: str | None = Field(
        default=None,
        alias="sessionId",
        description="Session ID",
    )
    tool_name: str | None = Field(
        default=None,
        alias="toolName",
        description="Tool name (for tool_call/tool_result)",
    )
    tool_input: dict[str, Any] | None = Field(
        default=None,
        alias="toolInput",
        description="Tool input parameters",
    )
    tool_output: Any | None = Field(
        default=None,
        alias="toolOutput",
        description="Tool output/result",
    )
    status: str | None = Field(
        default=None,
        description="Status message (for status chunks)",
        json_schema_extra={"example": "thinking"},
    )
    error: str | None = Field(
        default=None,
        description="Error message (for error chunks)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Chunk timestamp",
    )


class WebSocketMessage(BaseModel):
    """WebSocket message format (bidirectional)."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "message",
                "content": "What's the status?",
                "context": {"alert_id": "alert_abc123"},
            }
        },
    )

    type: str = Field(
        ...,
        description="Message type (message, ping, subscribe, etc.)",
        json_schema_extra={"example": "message"},
    )
    content: str | None = Field(
        default=None,
        description="Message content (for message type)",
    )
    context: ChatContext | None = Field(
        default=None,
        description="Context for the message",
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Additional data",
    )


class WebSocketResponse(BaseModel):
    """WebSocket response from server."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "response",
                "message_id": "msg_abc123",
                "content": "Here's what I found...",
                "timestamp": "2024-01-15T10:40:00Z",
            }
        },
    )

    type: str = Field(
        ...,
        description="Response type (response, status, error, connected, pong)",
    )
    message_id: str | None = Field(
        default=None,
        alias="messageId",
        description="Message ID",
    )
    content: str | None = Field(
        default=None,
        description="Response content",
    )
    session_id: str | None = Field(
        default=None,
        alias="sessionId",
        description="Session ID",
    )
    status: str | None = Field(
        default=None,
        description="Status (for status type)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (for error type)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp",
    )


class ChatSession(BaseModel):
    """Chat session information."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "sess_xyz789",
                "created_at": "2024-01-15T10:30:00Z",
                "last_message_at": "2024-01-15T10:45:00Z",
                "message_count": 15,
                "context": {"investigation_id": "inv_abc123"},
            }
        },
    )

    id: str = Field(..., description="Session ID")
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="When the session was created",
    )
    last_message_at: datetime | None = Field(
        default=None,
        alias="lastMessageAt",
        description="When the last message was sent",
    )
    message_count: int = Field(
        default=0,
        alias="messageCount",
        ge=0,
        description="Number of messages in the session",
    )
    context: ChatContext | None = Field(
        default=None,
        description="Session context",
    )


class ChatSessionList(BaseModel):
    """List of chat sessions."""

    model_config = ConfigDict(
        populate_by_name=True,
    )

    sessions: list[ChatSession] = Field(
        ...,
        description="List of sessions",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of sessions",
    )
