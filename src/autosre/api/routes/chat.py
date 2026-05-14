"""Chat Routes.

REST and WebSocket endpoints for interactive chat with the SRE agent.
"""

from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from autosre.api.middleware.auth import get_current_user, validate_ws_token
from autosre.api.schemas.requests import ChatMessage
from autosre.api.schemas.responses import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatSession,
    PaginatedResponse,
)

router = APIRouter()


# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections for chat sessions."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_json(message)


manager = ConnectionManager()


# =============================================================================
# Primary Chat Endpoints (as per spec)
# =============================================================================


@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    message: ChatMessage,
    session_id: Optional[UUID] = Query(None, description="Optional session ID for context"),
    investigation_id: Optional[UUID] = Query(None, description="Optional investigation context"),
    current_user: dict = Depends(get_current_user),
) -> ChatMessageResponse:
    """
    Send a message to the SRE agent and receive a response.

    Can optionally be linked to a session or investigation for context.
    If no session_id is provided, a stateless interaction is performed.
    """
    # TODO: Implement AI agent message handling
    # - Load conversation context if session_id provided
    # - Load investigation context if investigation_id provided
    # - Send to LLM with appropriate system prompt
    # - Store message and response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat message handling not yet implemented",
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    investigation_id: Optional[UUID] = Query(None, description="Filter by investigation ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum messages to return"),
    before: Optional[str] = Query(None, description="Cursor for pagination (message ID)"),
    current_user: dict = Depends(get_current_user),
) -> ChatHistoryResponse:
    """
    Retrieve chat history with optional filtering.

    Returns messages in reverse chronological order (newest first).
    Use 'before' cursor for pagination.
    """
    # TODO: Implement history retrieval with pagination
    return ChatHistoryResponse(
        messages=[],
        has_more=False,
        next_cursor=None,
    )


@router.websocket("/ws")
async def websocket_chat_simple(
    websocket: WebSocket,
):
    """
    WebSocket endpoint for real-time chat (simple endpoint).

    Authentication via query param: ?token=<jwt_token>
    Optional session: ?session_id=<uuid>

    Message format (client -> server):
    {
        "type": "message",
        "content": "Your question here",
        "investigation_id": "optional-uuid"
    }

    Response format (server -> client):
    {
        "type": "message" | "thinking" | "tool_use" | "error",
        "content": "...",
        "metadata": {...}
    }
    """
    token = websocket.query_params.get("token")
    session_id = websocket.query_params.get("session_id", "default")

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        user = await validate_ws_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "message")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message_type == "message":
                content = data.get("content", "")
                # TODO: Process through AI agent with streaming
                # For now, send a placeholder response
                await manager.send_message(
                    {
                        "type": "thinking",
                        "content": "Analyzing your request...",
                    },
                    session_id,
                )
                await manager.send_message(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": f"Received: {content}",
                    },
                    session_id,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        manager.disconnect(websocket, session_id)
        await websocket.close(code=4000, reason=str(e))


# =============================================================================
# Session-based Chat Endpoints (additional functionality)
# =============================================================================


@router.get("/sessions", response_model=PaginatedResponse[ChatSession])
async def list_chat_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> PaginatedResponse[ChatSession]:
    """List all chat sessions for the current user."""
    # TODO: Implement session listing
    return PaginatedResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.post("/sessions", response_model=ChatSession, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    investigation_id: Optional[UUID] = None,
    current_user: dict = Depends(get_current_user),
) -> ChatSession:
    """Create a new chat session, optionally linked to an investigation."""
    # TODO: Implement session creation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Session creation not yet implemented",
    )


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> ChatSession:
    """Get a specific chat session with message history."""
    # TODO: Implement session retrieval
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Chat session {session_id} not found",
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_session_message(
    session_id: UUID,
    message: ChatMessage,
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Send a message within a specific session and get an AI response."""
    # TODO: Implement message handling and AI response
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Chat session {session_id} not found",
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> None:
    """Delete a chat session."""
    # TODO: Implement session deletion
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Chat session {session_id} not found",
    )


@router.websocket("/ws/{session_id}")
async def websocket_chat_session(
    websocket: WebSocket,
    session_id: str,
):
    """WebSocket endpoint for real-time chat within a session."""
    # Validate token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        user = await validate_ws_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            # TODO: Process message and generate AI response
            # For now, echo back
            await manager.send_message(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": f"Received: {data.get('content', '')}",
                },
                session_id,
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        manager.disconnect(websocket, session_id)
        await websocket.close(code=4000, reason=str(e))
