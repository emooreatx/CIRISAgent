"""
Agent interaction endpoints for CIRIS API v3.0 (Simplified).

Core endpoints for natural agent interaction.
"""
import asyncio
import logging
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.runtime.messages import IncomingMessage
from ..dependencies.auth import require_observer, AuthContext
from ciris_engine.schemas.api.agent import (
    MessageContext, AgentLineage, ServiceAvailability, ActiveTask
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Request/Response schemas

class InteractRequest(BaseModel):
    """Request to interact with the agent."""
    message: str = Field(..., description="Message to send to the agent")
    context: Optional[MessageContext] = Field(None, description="Optional context")

class InteractResponse(BaseModel):
    """Response from agent interaction."""
    message_id: str = Field(..., description="Unique message ID")
    response: str = Field(..., description="Agent's response")
    state: str = Field(..., description="Agent's cognitive state after processing")
    processing_time_ms: int = Field(..., description="Time taken to process")

class ConversationMessage(BaseModel):
    """Message in conversation history."""
    id: str = Field(..., description="Message ID")
    author: str = Field(..., description="Message author")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When sent")
    is_agent: bool = Field(..., description="Whether this was from the agent")

class ConversationHistory(BaseModel):
    """Conversation history."""
    messages: List[ConversationMessage] = Field(..., description="Message history")
    total_count: int = Field(..., description="Total messages")
    has_more: bool = Field(..., description="Whether more messages exist")

class AgentStatus(BaseModel):
    """Agent status and cognitive state."""
    # Core identity
    agent_id: str = Field(..., description="Agent identifier")
    name: str = Field(..., description="Agent name")

    # State information
    cognitive_state: str = Field(..., description="Current cognitive state")
    uptime_seconds: float = Field(..., description="Time since startup")

    # Activity metrics
    messages_processed: int = Field(..., description="Total messages processed")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    current_task: Optional[str] = Field(None, description="Current task description")

    # System state
    services_active: int = Field(..., description="Number of active services")
    memory_usage_mb: float = Field(..., description="Current memory usage in MB")

class AgentIdentity(BaseModel):
    """Agent identity and capabilities."""
    # Identity
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    purpose: str = Field(..., description="Agent's purpose")
    created_at: datetime = Field(..., description="When agent was created")
    lineage: AgentLineage = Field(..., description="Agent lineage information")
    variance_threshold: float = Field(..., description="Identity variance threshold")

    # Capabilities
    tools: List[str] = Field(..., description="Available tools")
    handlers: List[str] = Field(..., description="Active handlers")
    services: ServiceAvailability = Field(..., description="Service availability")
    permissions: List[str] = Field(..., description="Agent permissions")

# Message tracking for interact functionality
_message_responses: dict[str, str] = {}
_response_events: dict[str, asyncio.Event] = {}


async def store_message_response(message_id: str, response: str) -> None:
    """Store a response and notify waiting request."""
    _message_responses[message_id] = response
    event = _response_events.get(message_id)
    if event:
        event.set()


# Endpoints

@router.post("/interact", response_model=SuccessResponse[InteractResponse])
async def interact(
    request: Request,
    body: InteractRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Send message and get response.

    This endpoint combines the old send/ask functionality into a single interaction.
    It sends the message and waits for the agent's response (with a reasonable timeout).
    """
    # Create unique IDs
    message_id = str(uuid.uuid4())
    channel_id = f"api_{auth.user_id}"  # User-specific channel
    event = asyncio.Event()
    _response_events[message_id] = event

    # Create message
    msg = IncomingMessage(
        message_id=message_id,
        author_id=auth.user_id,
        author_name=auth.user_id,
        content=body.message,
        channel_id=channel_id,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    # Track timing
    start_time = datetime.now(timezone.utc)

    # Route message through adapter's handler
    if hasattr(request.app.state, 'on_message'):
        await request.app.state.on_message(msg)
    else:
        raise HTTPException(status_code=503, detail="Message handler not configured")

    # Wait for response with timeout (30 seconds default)
    try:
        await asyncio.wait_for(event.wait(), timeout=30.0)

        # Get response
        response_content = _message_responses.get(message_id, "I'm processing your request. Please check back shortly.")

        # Clean up
        _response_events.pop(message_id, None)
        _message_responses.pop(message_id, None)

        # Calculate processing time
        end_time = datetime.now(timezone.utc)
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Get current cognitive state
        cognitive_state = "WORK"
        runtime = getattr(request.app.state, 'runtime', None)
        if runtime and hasattr(runtime, 'state_manager'):
            cognitive_state = runtime.state_manager.current_state

        response = InteractResponse(
            message_id=message_id,
            response=response_content,
            state=cognitive_state,
            processing_time_ms=processing_time_ms
        )

        return SuccessResponse(data=response)

    except asyncio.TimeoutError:
        # Clean up
        _response_events.pop(message_id, None)
        _message_responses.pop(message_id, None)

        # Return a timeout response rather than error
        response = InteractResponse(
            message_id=message_id,
            response="I'm still processing your request. Please check the conversation history in a moment.",
            state="WORK",
            processing_time_ms=30000
        )

        return SuccessResponse(data=response)

@router.get("/history", response_model=SuccessResponse[ConversationHistory])
async def get_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Maximum messages to return"),
    before: Optional[datetime] = Query(None, description="Get messages before this time"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Conversation history.

    Get the conversation history for the current user.
    """
    # Use user-specific channel
    channel_id = f"api_{auth.user_id}"
    
    # For admin users and above, also include the default API channel (home)
    channels_to_query = [channel_id]
    if auth.role in ['ADMIN', 'AUTHORITY', 'SYSTEM_ADMIN']:
        # Get default API channel from config
        api_host = getattr(request.app.state, 'api_host', '0.0.0.0')
        api_port = getattr(request.app.state, 'api_port', '8080')
        default_channel = f"api_{api_host}_{api_port}"
        channels_to_query.append(default_channel)
    
    logger.info(f"History query for user {auth.user_id} with role {auth.role}, channels: {channels_to_query}")
    
    # Check for mock message history first
    message_history = getattr(request.app.state, 'message_history', None)
    if message_history is not None:
        # Filter messages for this user (including default channel for admins)
        user_messages = [m for m in message_history if m.get('channel_id') in channels_to_query]
        
        # Convert to response format
        messages = []
        
        # First, expand all messages (user + response pairs)
        all_messages = []
        for msg in user_messages:
            # Add user message
            all_messages.append(ConversationMessage(
                id=msg['message_id'],
                author=msg['author_id'],
                content=msg['content'],
                timestamp=datetime.fromisoformat(msg['timestamp']) if isinstance(msg['timestamp'], str) else msg['timestamp'],
                is_agent=False
            ))
            # Add agent response if exists
            if msg.get('response'):
                all_messages.append(ConversationMessage(
                    id=f"{msg['message_id']}_response",
                    author="Scout",
                    content=msg['response'],
                    timestamp=datetime.fromisoformat(msg['timestamp']) if isinstance(msg['timestamp'], str) else msg['timestamp'],
                    is_agent=True
                ))
        
        # Now take only the last 'limit' messages
        if len(all_messages) > limit:
            messages = all_messages[-limit:]
        else:
            messages = all_messages
        
        history = ConversationHistory(
            messages=messages,
            total_count=len(user_messages),
            has_more=len(user_messages) > len(messages)  # Fixed: has_more should be based on actual truncation
        )
        
        return SuccessResponse(data=history)

    # Get communication service
    comm_service = getattr(request.app.state, 'communication_service', None)
    if not comm_service:
        # Fallback: query from memory
        memory_service = getattr(request.app.state, 'memory_service', None)
        if memory_service:
            # Query conversation nodes from memory
            from ciris_engine.schemas.services.operations import MemoryQuery
            from ciris_engine.schemas.services.graph_core import GraphScope, NodeType

            # MemoryQuery expects node_id, not filters
            # For conversation history, we'll need to use a different approach
            # For now, create a placeholder query
            query = MemoryQuery(
                node_id=f"conversation_{channel_id}",
                scope=GraphScope.LOCAL,
                type=NodeType.CONVERSATION if hasattr(NodeType, 'CONVERSATION') else None,
                include_edges=True,
                depth=1
            )

            nodes = await memory_service.recall(query)

            # Convert to conversation messages
            messages = []
            for node in nodes:
                attrs = node.attributes
                messages.append(ConversationMessage(
                    id=attrs.get('message_id', node.id),
                    author=attrs.get('author', 'unknown'),
                    content=attrs.get('content', ''),
                    timestamp=datetime.fromisoformat(attrs.get('timestamp', node.created_at)),
                    is_agent=attrs.get('is_agent', False)
                ))

            history = ConversationHistory(
                messages=messages,
                total_count=len(messages),
                has_more=len(messages) == limit
            )

            return SuccessResponse(data=history)

    try:
        # Fetch messages from communication service (fetch more to allow filtering)
        fetch_limit = limit * 2 if before else limit
        
        # Fetch messages from all relevant channels
        all_messages = []
        for channel in channels_to_query:
            try:
                logger.info(f"Fetching messages from channel: {channel}")
                channel_messages = await comm_service.fetch_messages(channel, limit=fetch_limit)
                logger.info(f"Retrieved {len(channel_messages)} messages from {channel}")
                all_messages.extend(channel_messages)
            except Exception as e:
                # If a channel doesn't exist or has no messages, continue
                logger.warning(f"Failed to fetch from channel {channel}: {e}")
                continue
        
        # Sort messages by timestamp (newest first)
        messages = sorted(all_messages, 
                         key=lambda m: m["timestamp"] if isinstance(m["timestamp"], datetime) else datetime.fromisoformat(m["timestamp"]), 
                         reverse=True)

        # Filter by time if specified
        if before:
            messages = [m for m in messages if (m["timestamp"] if isinstance(m["timestamp"], datetime) else datetime.fromisoformat(m["timestamp"])) < before]

        # Convert to conversation messages
        conv_messages = []
        for msg in messages[:limit]:  # Apply limit after filtering
            msg_timestamp = msg["timestamp"] if isinstance(msg["timestamp"], datetime) else datetime.fromisoformat(msg["timestamp"])
            conv_messages.append(ConversationMessage(
                id=msg["message_id"],
                author=msg["author_name"] or msg["author_id"],
                content=msg["content"],
                timestamp=msg_timestamp,
                is_agent=msg.get("is_agent_message", False)
            ))

        # Build response
        history = ConversationHistory(
            messages=conv_messages,
            total_count=len(messages),  # Total before limiting
            has_more=len(messages) > limit
        )

        return SuccessResponse(data=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=SuccessResponse[AgentStatus])
async def get_status(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Agent status and cognitive state.

    Get comprehensive agent status including state, metrics, and current activity.
    """
    # Get runtime info
    runtime = getattr(request.app.state, 'runtime', None)
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    try:
        # Get cognitive state
        cognitive_state = "WORK"
        if hasattr(runtime, 'state_manager'):
            cognitive_state = runtime.state_manager.current_state

        # Get uptime
        time_service = getattr(request.app.state, 'time_service', None)
        uptime = 0.0
        if time_service and hasattr(time_service, 'get_uptime'):
            uptime = await time_service.get_uptime()

        # Get telemetry for metrics
        telemetry_service = getattr(request.app.state, 'telemetry_service', None)
        messages_processed = 0
        if telemetry_service:
            try:
                summary = await telemetry_service.get_telemetry_summary()
                # Look for message processing metrics
                for metric in summary.metrics:
                    if metric.name == "messages_processed":
                        messages_processed = int(metric.current_value)
                        break
            except Exception as e:
                logger.warning(f"Failed to retrieve telemetry summary: {e}. Messages processed metric will show 0.")

        # Get current task from task scheduler if available
        current_task = None
        task_scheduler = getattr(request.app.state, 'task_scheduler', None)
        if task_scheduler and hasattr(task_scheduler, 'get_current_task'):
            current_task = await task_scheduler.get_current_task()

        # Get resource usage
        resource_monitor = getattr(request.app.state, 'resource_monitor', None)
        memory_usage_mb = 0.0
        if resource_monitor and hasattr(resource_monitor, 'snapshot'):
            memory_usage_mb = float(resource_monitor.snapshot.memory_mb)

        # Count active services
        service_registry = getattr(request.app.state, 'service_registry', None)
        services_active = 0
        if service_registry:
            from ciris_engine.schemas.runtime.enums import ServiceType
            for service_type in ServiceType:
                services_active += len(service_registry.get_services_by_type(service_type))

        # Get agent identity
        agent_id = "ciris_agent"
        agent_name = "CIRIS"
        if hasattr(runtime, 'agent_identity') and runtime.agent_identity:
            agent_id = runtime.agent_identity.agent_id
            # Try to get name from various sources
            if hasattr(runtime.agent_identity, 'name'):
                agent_name = runtime.agent_identity.name
            elif hasattr(runtime.agent_identity, 'core_profile'):
                # Use first part of description or role as name
                agent_name = runtime.agent_identity.core_profile.description.split('.')[0][:50]

        status = AgentStatus(
            agent_id=agent_id,
            name=agent_name,
            cognitive_state=cognitive_state,
            uptime_seconds=uptime,
            messages_processed=messages_processed,
            last_activity=datetime.now(timezone.utc),
            current_task=current_task,
            services_active=services_active,
            memory_usage_mb=memory_usage_mb
        )

        return SuccessResponse(data=status)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/identity", response_model=SuccessResponse[AgentIdentity])
async def get_identity(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Agent identity and capabilities.

    Get comprehensive agent identity including capabilities, tools, and permissions.
    """
    # Get memory service to query identity
    memory_service = getattr(request.app.state, 'memory_service', None)
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")

    try:
        # Query identity from graph
        from ciris_engine.schemas.services.operations import MemoryQuery
        from ciris_engine.schemas.services.graph_core import GraphScope

        query = MemoryQuery(
            node_id="agent/identity",
            scope=GraphScope.IDENTITY,
            include_edges=False
        )

        nodes = await memory_service.recall(query)

        # Get identity data
        identity_data = {}
        if nodes:
            identity_node = nodes[0]
            identity_data = identity_node.attributes
        else:
            # Fallback to runtime identity
            runtime = getattr(request.app.state, 'runtime', None)
            if runtime and hasattr(runtime, 'agent_identity'):
                identity = runtime.agent_identity
                identity_data = {
                    'agent_id': identity.agent_id,
                    'name': identity.name,
                    'purpose': identity.purpose,
                    'created_at': identity.created_at.isoformat(),
                    'lineage': {
                        'model': identity.lineage.get('model', 'unknown'),
                        'version': identity.lineage.get('version', '1.0'),
                        'parent_id': identity.lineage.get('parent_id'),
                        'creation_context': identity.lineage.get('creation_context', 'default'),
                        'adaptations': identity.lineage.get('adaptations', [])
                    },
                    'variance_threshold': 0.2
                }

        # Get capabilities

        # Get tool service for available tools
        tool_service = getattr(request.app.state, 'tool_service', None)
        tools = []
        if tool_service:
            tools = await tool_service.list_tools()

        # Get handlers (these are the core action handlers)
        handlers = [
            "observe", "speak", "tool", "reject", "ponder",
            "defer", "memorize", "recall", "forget", "task_complete"
        ]

        # Get service availability
        services = ServiceAvailability()
        service_registry = getattr(request.app.state, 'service_registry', None)
        if service_registry:
            from ciris_engine.schemas.runtime.enums import ServiceType
            for service_type in ServiceType:
                providers = service_registry.get_services_by_type(service_type)
                count = len(providers)
                # Map to service categories
                if 'graph' in service_type.value.lower() or service_type.value == 'MEMORY':
                    services.graph += count
                elif service_type.value in ['LLM', 'SECRETS']:
                    services.core += count
                elif service_type.value in ['TIME', 'SHUTDOWN', 'INITIALIZATION', 'VISIBILITY', 
                                           'AUTHENTICATION', 'RESOURCE_MONITOR', 'RUNTIME_CONTROL']:
                    services.infrastructure += count
                elif service_type.value == 'WISE_AUTHORITY':
                    services.governance += count
                else:
                    services.special += count

        # Get permissions (agent's core capabilities)
        permissions = [
            "communicate", "use_tools", "access_memory",
            "observe_environment", "learn", "adapt"
        ]

        # Build response
        lineage_data = identity_data.get('lineage', {})
        lineage = AgentLineage(
            model=lineage_data.get('model', 'unknown'),
            version=lineage_data.get('version', '1.0'),
            parent_id=lineage_data.get('parent_id'),
            creation_context=lineage_data.get('creation_context', 'default'),
            adaptations=lineage_data.get('adaptations', [])
        )
        
        response = AgentIdentity(
            agent_id=identity_data.get('agent_id', 'ciris_agent'),
            name=identity_data.get('name', 'CIRIS'),
            purpose=identity_data.get('purpose', 'Autonomous AI agent'),
            created_at=datetime.fromisoformat(identity_data.get('created_at', datetime.now(timezone.utc).isoformat())),
            lineage=lineage,
            variance_threshold=identity_data.get('variance_threshold', 0.2),
            tools=tools,
            handlers=handlers,
            services=services,
            permissions=permissions
        )

        return SuccessResponse(data=response)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to notify interact responses
async def notify_interact_response(message_id: str, content: str):
    """Notify waiting interact requests of responses."""
    if message_id in _response_events:
        _message_responses[message_id] = content
        _response_events[message_id].set()


# WebSocket endpoint for streaming
from fastapi import WebSocket, WebSocketDisconnect
import json

@router.websocket("/stream")
async def websocket_stream(
    websocket: WebSocket,
    auth: Optional[AuthContext] = None  # TODO: Add WebSocket auth
):
    """
    WebSocket endpoint for real-time updates.
    
    Clients can subscribe to different channels:
    - messages: Agent messages and responses
    - telemetry: Real-time metrics
    - reasoning: Reasoning traces
    - logs: System logs
    """
    await websocket.accept()
    client_id = f"ws_{id(websocket)}"
    
    # Get communication service to register WebSocket
    comm_service = getattr(websocket.app.state, 'communication_service', None)
    if comm_service and hasattr(comm_service, 'register_websocket'):
        comm_service.register_websocket(client_id, websocket)
    
    subscribed_channels = set(["messages"])  # Default subscription
    
    try:
        while True:
            # Receive and process client messages
            data = await websocket.receive_json()
            
            if data.get("action") == "subscribe":
                channels = data.get("channels", [])
                subscribed_channels.update(channels)
                await websocket.send_json({
                    "type": "subscription_update",
                    "channels": list(subscribed_channels),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            elif data.get("action") == "unsubscribe":
                channels = data.get("channels", [])
                subscribed_channels.difference_update(channels)
                await websocket.send_json({
                    "type": "subscription_update", 
                    "channels": list(subscribed_channels),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            elif data.get("action") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
    except WebSocketDisconnect:
        # Clean up on disconnect
        if comm_service and hasattr(comm_service, 'unregister_websocket'):
            comm_service.unregister_websocket(client_id)
        logger.info(f"WebSocket client {client_id} disconnected")
