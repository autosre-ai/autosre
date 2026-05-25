"""
WebSocket API Routes

Provides WebSocket endpoints for real-time updates:
- /ws - General WebSocket for subscriptions
- /ws/investigations - Investigation monitoring
- /ws/metrics - Real-time metrics
- /ws/events - System events
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from autosre.api.websocket import ChannelType, get_connection_manager
from autosre.streaming import get_stream_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str | None = Query(None, description="Optional client identifier"),
):
    """
    General WebSocket endpoint for real-time updates.
    
    Connect to receive real-time updates. Send messages to subscribe to channels:
    
    Subscribe: {"type": "subscribe", "channels": ["investigations", "metrics"]}
    Unsubscribe: {"type": "unsubscribe", "channels": ["metrics"]}
    Ping: {"type": "ping"}
    
    Channels:
    - investigations: All investigation updates
    - investigation:<id>: Specific investigation
    - metrics: Real-time metrics
    - events: System events
    - alerts: Alert notifications
    - all: All messages
    """
    manager = get_connection_manager()
    client_id = client_id or f"client-{uuid.uuid4().hex[:8]}"
    
    try:
        client = await manager.connect(
            websocket=websocket,
            client_id=client_id,
            initial_subscriptions=[ChannelType.INVESTIGATIONS.value],
        )
        
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(client_id, data)
            
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)


@router.websocket("/investigations/{investigation_id}")
async def websocket_investigation(
    websocket: WebSocket,
    investigation_id: str,
    replay: bool = Query(True, description="Replay historical events"),
):
    """
    WebSocket endpoint for monitoring a specific investigation.
    
    Automatically subscribes to the investigation channel and streams events
    in real-time. Optionally replays historical events from the start.
    
    Events:
    - started: Investigation started
    - observation: Data collected
    - observation_complete: Collection phase done
    - thinking: Analysis in progress
    - hypothesis: Generated hypothesis
    - root_cause: Root cause identified
    - action: Remediation suggested
    - progress: Progress update
    - completed: Investigation finished
    - error: Error occurred
    """
    manager = get_connection_manager()
    stream_manager = get_stream_manager()
    client_id = f"inv-{investigation_id}-{uuid.uuid4().hex[:8]}"
    
    try:
        await websocket.accept()
        
        # Get the investigation stream if it exists
        stream = await stream_manager.get_stream(investigation_id)
        
        if stream and replay:
            # Replay historical events
            for event in stream.history:
                await websocket.send_json({
                    "type": event.type.value,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                    "replay": True,
                })
        
        # Subscribe to updates via the connection manager
        channel = f"investigation:{investigation_id}"
        client = await manager.connect(
            websocket=websocket,
            client_id=client_id,
            initial_subscriptions=[channel],
        )
        
        # If stream exists and not completed, subscribe to live updates
        if stream and not stream.is_completed:
            async for event in stream.subscribe():
                await websocket.send_json({
                    "type": event.type.value,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                    "replay": False,
                })
        else:
            # Just wait for messages via connection manager
            while True:
                data = await websocket.receive_text()
                await manager.handle_message(client_id, data)
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Investigation WebSocket error: {e}")
        await manager.disconnect(client_id)


@router.websocket("/metrics")
async def websocket_metrics(
    websocket: WebSocket,
    interval: int = Query(5, ge=1, le=60, description="Metrics push interval in seconds"),
):
    """
    WebSocket endpoint for real-time metrics streaming.
    
    Automatically pushes metrics at the specified interval.
    Metrics include:
    - Active investigations
    - System health
    - Resource utilization
    - Response times
    """
    manager = get_connection_manager()
    client_id = f"metrics-{uuid.uuid4().hex[:8]}"
    
    try:
        client = await manager.connect(
            websocket=websocket,
            client_id=client_id,
            initial_subscriptions=[ChannelType.METRICS.value],
        )
        
        # Start metrics streaming task
        async def stream_metrics():
            while True:
                try:
                    # Import here to avoid circular imports
                    from autosre.dashboard.metrics import get_metrics_aggregator
                    aggregator = get_metrics_aggregator()
                    metrics = await aggregator.get_current_metrics()
                    
                    await manager.send_to_client(client_id, {
                        "type": "metrics_update",
                        "data": metrics,
                        "timestamp": datetime.now().isoformat(),
                    })
                    
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Metrics stream error: {e}")
                    await asyncio.sleep(interval)
        
        # Run metrics streaming and message handling concurrently
        metrics_task = asyncio.create_task(stream_metrics())
        
        try:
            while True:
                data = await websocket.receive_text()
                await manager.handle_message(client_id, data)
        finally:
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Metrics WebSocket error: {e}")
        await manager.disconnect(client_id)


@router.websocket("/events")
async def websocket_events(
    websocket: WebSocket,
    filter_types: str | None = Query(None, description="Comma-separated event types to filter"),
):
    """
    WebSocket endpoint for system event streaming.
    
    Streams system events in real-time. Optionally filter by event types.
    
    Event types:
    - investigation_started
    - investigation_completed
    - action_approved
    - action_rejected
    - action_executed
    - alert_triggered
    - system_error
    """
    manager = get_connection_manager()
    client_id = f"events-{uuid.uuid4().hex[:8]}"
    
    filter_set = set(filter_types.split(",")) if filter_types else None
    
    try:
        client = await manager.connect(
            websocket=websocket,
            client_id=client_id,
            initial_subscriptions=[ChannelType.EVENTS.value],
            metadata={"filter_types": list(filter_set) if filter_set else None},
        )
        
        # Connect to event stream
        from autosre.dashboard.events import get_event_stream
        event_stream = get_event_stream()
        
        # Stream events
        async def stream_events():
            async for event in event_stream.subscribe():
                # Apply filter if specified
                if filter_set and event.event_type not in filter_set:
                    continue
                
                await manager.send_to_client(client_id, {
                    "type": "event",
                    "event_type": event.event_type,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                })
        
        # Run event streaming and message handling concurrently
        events_task = asyncio.create_task(stream_events())
        
        try:
            while True:
                data = await websocket.receive_text()
                await manager.handle_message(client_id, data)
        finally:
            events_task.cancel()
            try:
                await events_task
            except asyncio.CancelledError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Events WebSocket error: {e}")
        await manager.disconnect(client_id)


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for alert notifications.
    
    Receives real-time alert notifications from monitoring systems.
    """
    manager = get_connection_manager()
    client_id = f"alerts-{uuid.uuid4().hex[:8]}"
    
    try:
        client = await manager.connect(
            websocket=websocket,
            client_id=client_id,
            initial_subscriptions=[ChannelType.ALERTS.value],
        )
        
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(client_id, data)
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Alerts WebSocket error: {e}")
        await manager.disconnect(client_id)


# REST endpoint to get WebSocket connection info
@router.get("/connections")
async def get_connections():
    """Get information about active WebSocket connections."""
    manager = get_connection_manager()
    return {
        "active_connections": manager.active_connections,
        "clients": manager.get_client_info(),
    }
