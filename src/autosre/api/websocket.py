"""
WebSocket Connection Manager for Real-time Updates

Manages WebSocket connections for real-time dashboard updates,
investigation monitoring, and event streaming.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Types of WebSocket channels."""
    INVESTIGATIONS = "investigations"  # All investigation updates
    INVESTIGATION = "investigation"    # Specific investigation by ID
    METRICS = "metrics"                 # Real-time metrics
    EVENTS = "events"                   # System events
    ALERTS = "alerts"                   # Alert notifications
    ALL = "all"                         # Broadcast to all


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""
    websocket: WebSocket
    client_id: str
    subscriptions: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.now)
    last_ping: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_subscribed(self, channel: str) -> bool:
        """Check if client is subscribed to a channel."""
        return channel in self.subscriptions or ChannelType.ALL.value in self.subscriptions


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    
    Features:
    - Channel-based subscriptions (investigations, metrics, events, alerts)
    - Per-investigation subscriptions for real-time monitoring
    - Broadcast and targeted messaging
    - Automatic cleanup of disconnected clients
    - Heartbeat/ping-pong support
    """

    def __init__(self):
        self._clients: dict[str, WebSocketClient] = {}
        self._lock = asyncio.Lock()
        self._message_handlers: dict[str, Callable] = {}
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def active_connections(self) -> int:
        """Number of active connections."""
        return len(self._clients)

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        initial_subscriptions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WebSocketClient:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            client_id: Unique identifier for this client
            initial_subscriptions: Channels to subscribe to on connect
            metadata: Optional client metadata (user info, etc.)
            
        Returns:
            WebSocketClient: The connected client
        """
        await websocket.accept()
        
        async with self._lock:
            # Close existing connection with same ID
            if client_id in self._clients:
                try:
                    await self._clients[client_id].websocket.close()
                except Exception:
                    pass
            
            client = WebSocketClient(
                websocket=websocket,
                client_id=client_id,
                subscriptions=set(initial_subscriptions or []),
                metadata=metadata or {},
            )
            self._clients[client_id] = client
        
        logger.info(f"WebSocket connected: {client_id} (total: {self.active_connections})")
        
        # Send welcome message
        await self.send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "subscriptions": list(client.subscriptions),
            "timestamp": datetime.now().isoformat(),
        })
        
        return client

    async def disconnect(self, client_id: str):
        """
        Handle client disconnection.
        
        Args:
            client_id: The client to disconnect
        """
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"WebSocket disconnected: {client_id} (total: {self.active_connections})")

    async def subscribe(self, client_id: str, channels: list[str]):
        """
        Subscribe a client to channels.
        
        Args:
            client_id: The client ID
            channels: List of channels to subscribe to
        """
        async with self._lock:
            if client_id in self._clients:
                self._clients[client_id].subscriptions.update(channels)
                await self.send_to_client(client_id, {
                    "type": "subscribed",
                    "channels": channels,
                })

    async def unsubscribe(self, client_id: str, channels: list[str]):
        """
        Unsubscribe a client from channels.
        
        Args:
            client_id: The client ID
            channels: List of channels to unsubscribe from
        """
        async with self._lock:
            if client_id in self._clients:
                self._clients[client_id].subscriptions.difference_update(channels)
                await self.send_to_client(client_id, {
                    "type": "unsubscribed",
                    "channels": channels,
                })

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: The target client ID
            message: Message to send
            
        Returns:
            bool: True if sent successfully
        """
        client = self._clients.get(client_id)
        if not client:
            return False
        
        try:
            await client.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)
            return False

    async def broadcast(self, message: dict[str, Any], channel: str | None = None):
        """
        Broadcast a message to all connected clients or a specific channel.
        
        Args:
            message: Message to broadcast
            channel: Optional channel to broadcast to (None = all clients)
        """
        if channel:
            message["channel"] = channel
        
        disconnected = []
        
        async with self._lock:
            for client_id, client in self._clients.items():
                # Check subscription if channel specified
                if channel and not client.is_subscribed(channel):
                    continue
                
                try:
                    await client.websocket.send_json(message)
                except Exception:
                    disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect(client_id)

    async def broadcast_to_investigation(self, investigation_id: str, message: dict[str, Any]):
        """
        Broadcast to all clients subscribed to a specific investigation.
        
        Args:
            investigation_id: The investigation ID
            message: Message to broadcast
        """
        channel = f"investigation:{investigation_id}"
        message["investigation_id"] = investigation_id
        await self.broadcast(message, channel)

    async def broadcast_metrics(self, metrics: dict[str, Any]):
        """
        Broadcast metrics update to subscribed clients.
        
        Args:
            metrics: Metrics data to broadcast
        """
        await self.broadcast({
            "type": "metrics_update",
            "data": metrics,
            "timestamp": datetime.now().isoformat(),
        }, ChannelType.METRICS.value)

    async def broadcast_event(self, event_type: str, data: dict[str, Any]):
        """
        Broadcast a system event.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        await self.broadcast({
            "type": "event",
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }, ChannelType.EVENTS.value)

    async def broadcast_alert(self, alert: dict[str, Any]):
        """
        Broadcast an alert notification.
        
        Args:
            alert: Alert data
        """
        await self.broadcast({
            "type": "alert",
            "data": alert,
            "timestamp": datetime.now().isoformat(),
        }, ChannelType.ALERTS.value)

    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Async callable to handle the message
        """
        self._message_handlers[message_type] = handler

    async def handle_message(self, client_id: str, data: str):
        """
        Handle an incoming message from a client.
        
        Args:
            client_id: The client sending the message
            data: Raw message data
        """
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await self.send_to_client(client_id, {
                "type": "error",
                "error": "Invalid JSON",
            })
            return
        
        msg_type = message.get("type")
        
        # Built-in message handlers
        if msg_type == "ping":
            await self.send_to_client(client_id, {"type": "pong"})
            if client_id in self._clients:
                self._clients[client_id].last_ping = datetime.now()
            return
        
        if msg_type == "subscribe":
            channels = message.get("channels", [])
            await self.subscribe(client_id, channels)
            return
        
        if msg_type == "unsubscribe":
            channels = message.get("channels", [])
            await self.unsubscribe(client_id, channels)
            return
        
        # Custom handlers
        if msg_type in self._message_handlers:
            try:
                await self._message_handlers[msg_type](client_id, message)
            except Exception as e:
                logger.error(f"Handler error for {msg_type}: {e}")
                await self.send_to_client(client_id, {
                    "type": "error",
                    "error": f"Handler error: {str(e)}",
                })
            return
        
        # Unknown message type
        await self.send_to_client(client_id, {
            "type": "error",
            "error": f"Unknown message type: {msg_type}",
        })

    async def start_heartbeat(self):
        """Start the heartbeat task to keep connections alive."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self):
        """Stop the heartbeat task."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to all clients."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self.broadcast({"type": "heartbeat"})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def get_client_info(self) -> list[dict[str, Any]]:
        """Get information about all connected clients."""
        return [
            {
                "client_id": client.client_id,
                "subscriptions": list(client.subscriptions),
                "connected_at": client.connected_at.isoformat(),
                "last_ping": client.last_ping.isoformat(),
                "metadata": client.metadata,
            }
            for client in self._clients.values()
        ]


# Global connection manager instance
_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
