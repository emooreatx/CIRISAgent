"""
WebSocket streaming endpoints for CIRIS API v1.

Real-time data streams for rich user experiences.
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel, Field

from ciris_engine.api.dependencies.auth import AuthContext, UserRole
from ciris_engine.schemas.api.auth import APIKeyInfo, ROLE_PERMISSIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["streaming"])

# Stream message types
class StreamMessageType(str, Enum):
    """Types of messages that can be streamed."""
    MESSAGE = "message"          # Agent messages
    TELEMETRY = "telemetry"      # Telemetry updates
    REASONING = "reasoning"      # Reasoning traces
    LOG = "log"                  # System logs
    HEARTBEAT = "heartbeat"      # Keep-alive
    ERROR = "error"              # Error messages
    AUTH = "auth"                # Authentication status
    SUBSCRIBE = "subscribe"      # Subscription control
    UNSUBSCRIBE = "unsubscribe"  # Unsubscription control

class StreamMessage(BaseModel):
    """Base message for all stream communications."""
    type: StreamMessageType = Field(..., description="Message type")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = Field(..., description="Message payload")

class MessageStreamData(BaseModel):
    """Data for MESSAGE type streams."""
    message_id: str = Field(..., description="Unique message ID")
    channel_id: str = Field(..., description="Channel ID")
    author_id: str = Field(..., description="Author ID")
    content: str = Field(..., description="Message content")
    direction: str = Field(..., description="'incoming' or 'outgoing'")

class TelemetryStreamData(BaseModel):
    """Data for TELEMETRY type streams."""
    metric_name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Metric unit")
    tags: Dict[str, str] = Field(default_factory=dict)

class ReasoningStreamData(BaseModel):
    """Data for REASONING type streams."""
    reasoning_id: str = Field(..., description="Reasoning trace ID")
    step: str = Field(..., description="Reasoning step")
    thought: str = Field(..., description="Thought content")
    depth: int = Field(..., description="Reasoning depth")
    handler: Optional[str] = Field(None, description="Handler that generated this")

class LogStreamData(BaseModel):
    """Data for LOG type streams."""
    level: str = Field(..., description="Log level")
    logger_name: str = Field(..., description="Logger name")
    message: str = Field(..., description="Log message")
    context: Dict[str, Any] = Field(default_factory=dict)

class SubscriptionRequest(BaseModel):
    """Request to subscribe/unsubscribe from streams."""
    streams: List[StreamMessageType] = Field(..., description="Streams to subscribe to")

# Connection manager for WebSocket clients
class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[StreamMessageType]] = {}
        self.auth_contexts: Dict[str, Optional[AuthContext]] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket, auth_context: Optional[AuthContext] = None):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        self.auth_contexts[client_id] = auth_context
        
        # Send auth confirmation
        await self.send_personal_message(
            client_id,
            StreamMessage(
                type=StreamMessageType.AUTH,
                data={
                    "authenticated": auth_context is not None,
                    "user_id": auth_context.user_id if auth_context else None,
                    "role": auth_context.role.value if auth_context else None
                }
            )
        )
    
    def disconnect(self, client_id: str):
        """Remove WebSocket connection."""
        self.active_connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)
        self.auth_contexts.pop(client_id, None)
    
    async def send_personal_message(self, client_id: str, message: StreamMessage):
        """Send message to specific client."""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message.model_dump(mode='json'))
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: StreamMessage, stream_type: StreamMessageType, min_role: Optional[UserRole] = None):
        """Broadcast message to all subscribed clients."""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            # Check if client is subscribed to this stream type
            if stream_type not in self.subscriptions.get(client_id, set()):
                continue
            
            # Check role permissions if required
            if min_role:
                auth = self.auth_contexts.get(client_id)
                if not auth or not auth.role.has_permission(min_role):
                    continue
            
            try:
                await websocket.send_json(message.model_dump(mode='json'))
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    def subscribe(self, client_id: str, streams: List[StreamMessageType]):
        """Subscribe client to streams."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].update(streams)
    
    def unsubscribe(self, client_id: str, streams: List[StreamMessageType]):
        """Unsubscribe client from streams."""
        if client_id in self.subscriptions:
            for stream in streams:
                self.subscriptions[client_id].discard(stream)

# Global connection manager
manager = ConnectionManager()

# Helper function to validate WebSocket authentication
async def validate_ws_auth(websocket: WebSocket, token: Optional[str]) -> Optional[AuthContext]:
    """Validate WebSocket authentication token."""
    if not token:
        return None
    
    auth_service = getattr(websocket.app.state, 'auth_service', None)
    if not auth_service:
        return None
    
    key_info = await auth_service.validate_api_key(token)
    if not key_info:
        return None
    
    # Create auth context
    # Use created_by as user_id since APIKeyInfo doesn't have user_id
    return AuthContext(
        user_id=key_info.created_by,  # Using created_by as user_id
        role=key_info.role,
        permissions=ROLE_PERMISSIONS.get(key_info.role, set()),
        api_key_id=key_info.key_id,
        authenticated_at=datetime.now(timezone.utc)
    )

# WebSocket endpoints

@router.websocket("/messages")
async def stream_messages(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Real-time message stream.
    
    Stream agent messages as they are processed.
    """
    # Validate auth
    auth_context = await validate_ws_auth(websocket, token)
    if not auth_context:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    client_id = f"msg_{auth_context.user_id}_{datetime.now().timestamp()}"
    
    # Connect client
    await manager.connect(client_id, websocket, auth_context)
    
    # Auto-subscribe to message stream
    manager.subscribe(client_id, [StreamMessageType.MESSAGE])
    
    try:
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (mainly for heartbeat)
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle subscription requests
                if data.get('type') == 'subscribe':
                    # Messages stream is always subscribed
                    pass
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal_message(
                    client_id,
                    StreamMessage(
                        type=StreamMessageType.HEARTBEAT,
                        data={"status": "alive"}
                    )
                )
                
    except WebSocketDisconnect:
        logger.info(f"Message stream client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Message stream error: {e}")
    finally:
        manager.disconnect(client_id)

@router.websocket("/telemetry")
async def stream_telemetry(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Telemetry updates stream.
    
    Stream real-time telemetry data.
    """
    # Validate auth
    auth_context = await validate_ws_auth(websocket, token)
    if not auth_context:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    client_id = f"tel_{auth_context.user_id}_{datetime.now().timestamp()}"
    
    # Connect client
    await manager.connect(client_id, websocket, auth_context)
    
    # Auto-subscribe to telemetry stream
    manager.subscribe(client_id, [StreamMessageType.TELEMETRY])
    
    try:
        # Start telemetry streaming task
        async def stream_telemetry_data():
            """Background task to stream telemetry."""
            while client_id in manager.active_connections:
                try:
                    # Get telemetry service
                    telemetry_service = getattr(websocket.app.state, 'telemetry_service', None)
                    if telemetry_service:
                        # Get latest metrics
                        # This is a simplified example - real implementation would subscribe to telemetry events
                        await manager.send_personal_message(
                            client_id,
                            StreamMessage(
                                type=StreamMessageType.TELEMETRY,
                                data={
                                    "metric_name": "system.heartbeat",
                                    "value": 1.0,
                                    "unit": "count"
                                }
                            )
                        )
                    
                    await asyncio.sleep(5)  # Send updates every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Telemetry streaming error: {e}")
                    break
        
        # Start background task
        telemetry_task = asyncio.create_task(stream_telemetry_data())
        
        # Handle client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle metric filters
                if data.get('type') == 'filter':
                    # Update telemetry filters
                    pass
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal_message(
                    client_id,
                    StreamMessage(
                        type=StreamMessageType.HEARTBEAT,
                        data={"status": "alive"}
                    )
                )
                
    except WebSocketDisconnect:
        logger.info(f"Telemetry stream client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Telemetry stream error: {e}")
    finally:
        telemetry_task.cancel()
        manager.disconnect(client_id)

@router.websocket("/reasoning")
async def stream_reasoning(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Reasoning trace stream.
    
    Stream agent's reasoning process in real-time.
    """
    # Validate auth
    auth_context = await validate_ws_auth(websocket, token)
    if not auth_context:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    client_id = f"rsn_{auth_context.user_id}_{datetime.now().timestamp()}"
    
    # Connect client
    await manager.connect(client_id, websocket, auth_context)
    
    # Auto-subscribe to reasoning stream
    manager.subscribe(client_id, [StreamMessageType.REASONING])
    
    try:
        # Keep connection alive
        while True:
            try:
                # Wait for client messages
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle filter requests
                if data.get('type') == 'filter':
                    # Update reasoning filters (e.g., minimum depth)
                    pass
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal_message(
                    client_id,
                    StreamMessage(
                        type=StreamMessageType.HEARTBEAT,
                        data={"status": "alive"}
                    )
                )
                
    except WebSocketDisconnect:
        logger.info(f"Reasoning stream client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Reasoning stream error: {e}")
    finally:
        manager.disconnect(client_id)

@router.websocket("/logs")
async def stream_logs(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Log stream.
    
    Stream system logs in real-time. Requires ADMIN role.
    """
    # Validate auth
    auth_context = await validate_ws_auth(websocket, token)
    if not auth_context:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    # Check admin permission
    if not auth_context.role.has_permission(UserRole.ADMIN):
        await websocket.close(code=1008, reason="Admin role required")
        return
    
    client_id = f"log_{auth_context.user_id}_{datetime.now().timestamp()}"
    
    # Connect client
    await manager.connect(client_id, websocket, auth_context)
    
    # Auto-subscribe to log stream
    manager.subscribe(client_id, [StreamMessageType.LOG])
    
    try:
        # Keep connection alive
        while True:
            try:
                # Wait for client messages
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle log level filters
                if data.get('type') == 'filter':
                    log_levels = data.get('levels', ['INFO', 'WARNING', 'ERROR'])
                    # Update log filters
                    pass
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal_message(
                    client_id,
                    StreamMessage(
                        type=StreamMessageType.HEARTBEAT,
                        data={"status": "alive"}
                    )
                )
                
    except WebSocketDisconnect:
        logger.info(f"Log stream client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Log stream error: {e}")
    finally:
        manager.disconnect(client_id)

@router.websocket("/all")
async def stream_all(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    Multiplexed stream combining all streams.
    
    Subscribe to multiple stream types through a single connection.
    """
    # Validate auth
    auth_context = await validate_ws_auth(websocket, token)
    if not auth_context:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    client_id = f"all_{auth_context.user_id}_{datetime.now().timestamp()}"
    
    # Connect client
    await manager.connect(client_id, websocket, auth_context)
    
    try:
        # Wait for initial subscription request
        data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        
        if data.get('type') != 'subscribe':
            await websocket.send_json({
                "type": "error",
                "data": {"message": "First message must be subscription request"}
            })
            return
        
        # Process subscription
        requested_streams = data.get('streams', [])
        valid_streams = []
        
        for stream in requested_streams:
            try:
                stream_type = StreamMessageType(stream)
                
                # Check permissions
                if stream_type == StreamMessageType.LOG and not auth_context.role.has_permission(UserRole.ADMIN):
                    continue
                
                valid_streams.append(stream_type)
            except ValueError:
                pass
        
        # Subscribe to valid streams
        manager.subscribe(client_id, valid_streams)
        
        # Send subscription confirmation
        await manager.send_personal_message(
            client_id,
            StreamMessage(
                type=StreamMessageType.SUBSCRIBE,
                data={
                    "subscribed": [s.value for s in valid_streams],
                    "denied": list(set(requested_streams) - set(s.value for s in valid_streams))
                }
            )
        )
        
        # Handle ongoing communication
        while True:
            try:
                # Wait for client messages
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                msg_type = data.get('type')
                
                if msg_type == 'subscribe':
                    # Add new subscriptions
                    new_streams = []
                    for stream in data.get('streams', []):
                        try:
                            stream_type = StreamMessageType(stream)
                            if stream_type == StreamMessageType.LOG and not auth_context.role.has_permission(UserRole.ADMIN):
                                continue
                            new_streams.append(stream_type)
                        except ValueError:
                            pass
                    
                    manager.subscribe(client_id, new_streams)
                    
                    await manager.send_personal_message(
                        client_id,
                        StreamMessage(
                            type=StreamMessageType.SUBSCRIBE,
                            data={"added": [s.value for s in new_streams]}
                        )
                    )
                    
                elif msg_type == 'unsubscribe':
                    # Remove subscriptions
                    remove_streams = []
                    for stream in data.get('streams', []):
                        try:
                            stream_type = StreamMessageType(stream)
                            remove_streams.append(stream_type)
                        except ValueError:
                            pass
                    
                    manager.unsubscribe(client_id, remove_streams)
                    
                    await manager.send_personal_message(
                        client_id,
                        StreamMessage(
                            type=StreamMessageType.UNSUBSCRIBE,
                            data={"removed": [s.value for s in remove_streams]}
                        )
                    )
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal_message(
                    client_id,
                    StreamMessage(
                        type=StreamMessageType.HEARTBEAT,
                        data={"status": "alive"}
                    )
                )
                
    except WebSocketDisconnect:
        logger.info(f"Multiplexed stream client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Multiplexed stream error: {e}")
    finally:
        manager.disconnect(client_id)

# Integration functions for other parts of the system to send stream messages

async def broadcast_message(message_data: MessageStreamData):
    """Broadcast a message to all message stream subscribers."""
    await manager.broadcast(
        StreamMessage(
            type=StreamMessageType.MESSAGE,
            data=message_data.model_dump()
        ),
        StreamMessageType.MESSAGE
    )

async def broadcast_telemetry(telemetry_data: TelemetryStreamData):
    """Broadcast telemetry update to all telemetry subscribers."""
    await manager.broadcast(
        StreamMessage(
            type=StreamMessageType.TELEMETRY,
            data=telemetry_data.model_dump()
        ),
        StreamMessageType.TELEMETRY
    )

async def broadcast_reasoning(reasoning_data: ReasoningStreamData):
    """Broadcast reasoning trace to all reasoning subscribers."""
    await manager.broadcast(
        StreamMessage(
            type=StreamMessageType.REASONING,
            data=reasoning_data.model_dump()
        ),
        StreamMessageType.REASONING
    )

async def broadcast_log(log_data: LogStreamData, min_role: UserRole = UserRole.ADMIN):
    """Broadcast log message to authorized subscribers."""
    await manager.broadcast(
        StreamMessage(
            type=StreamMessageType.LOG,
            data=log_data.model_dump()
        ),
        StreamMessageType.LOG,
        min_role=min_role
    )