"""Chat models for conversational interface."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageType(str, Enum):
    """Type of message content."""
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    STATUS = "status"


class ToolCall(BaseModel):
    """A tool call made by the assistant."""
    model_config = ConfigDict(validate_assignment=True)
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    
    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ToolResult(BaseModel):
    """Result of a tool call."""
    model_config = ConfigDict(validate_assignment=True)
    
    tool_call_id: str = Field(..., description="ID of the tool call this is a result for")
    output: Any = Field(..., description="Tool output")
    error: Optional[str] = Field(default=None, description="Error message if tool failed")
    duration_ms: Optional[int] = Field(default=None, ge=0, description="Execution time in milliseconds")


class ChatMessage(BaseModel):
    """A message in a chat session."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    role: MessageRole = Field(..., description="Message sender role")
    type: MessageType = Field(default=MessageType.TEXT, description="Type of message")
    content: str = Field(default="", description="Text content of the message")
    
    # Tool interactions
    tool_calls: list[ToolCall] = Field(default_factory=list, description="Tool calls in this message")
    tool_result: Optional[ToolResult] = Field(default=None, description="Tool result if this is a tool response")
    
    # Context
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context for the message")
    
    # Timing
    timestamp: datetime = Field(default_factory=utc_now)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def user(cls, content: str, **kwargs) -> "ChatMessage":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content, **kwargs)
    
    @classmethod
    def assistant(cls, content: str, tool_calls: list[ToolCall] | None = None, **kwargs) -> "ChatMessage":
        """Create an assistant message."""
        return cls(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
            type=MessageType.TOOL_CALL if tool_calls else MessageType.TEXT,
            **kwargs
        )
    
    @classmethod
    def system(cls, content: str, **kwargs) -> "ChatMessage":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content, **kwargs)
    
    @classmethod
    def tool(cls, tool_call_id: str, output: Any, error: str | None = None, **kwargs) -> "ChatMessage":
        """Create a tool result message."""
        return cls(
            role=MessageRole.TOOL,
            type=MessageType.TOOL_RESULT,
            tool_result=ToolResult(tool_call_id=tool_call_id, output=output, error=error),
            **kwargs
        )


class SessionStatus(str, Enum):
    """Status of a chat session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"


class ChatSession(BaseModel):
    """A chat session with conversation history."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    title: str = Field(default="New Session", description="Session title")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    
    # Messages
    messages: list[ChatMessage] = Field(default_factory=list)
    system_prompt: Optional[str] = Field(default=None, description="System prompt for this session")
    
    # Context
    alert_id: Optional[str] = Field(default=None, description="Related alert ID")
    investigation_id: Optional[str] = Field(default=None, description="Related investigation ID")
    context: dict[str, Any] = Field(default_factory=dict, description="Session context/state")
    
    # Timing
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    # Metadata
    user_id: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = utc_now()
    
    def add_user_message(self, content: str) -> ChatMessage:
        """Add a user message and return it."""
        message = ChatMessage.user(content)
        self.add_message(message)
        return message
    
    def add_assistant_message(self, content: str, tool_calls: list[ToolCall] | None = None) -> ChatMessage:
        """Add an assistant message and return it."""
        message = ChatMessage.assistant(content, tool_calls)
        self.add_message(message)
        return message
    
    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """Get messages formatted for API consumption."""
        result = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            result.append({
                "role": msg.role.value if isinstance(msg.role, MessageRole) else msg.role,
                "content": msg.content,
            })
        return result
    
    def message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)
    
    def last_message(self) -> Optional[ChatMessage]:
        """Get the last message in the session."""
        if not self.messages:
            return None
        return self.messages[-1]
