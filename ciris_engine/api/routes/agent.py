"""
Agent interaction endpoints for CIRIS API v1.

High-level endpoints for natural agent interaction.
"""
import asyncio
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.runtime.messages import IncomingMessage, FetchedMessage
from ciris_engine.schemas.runtime.states import CognitiveState
from ciris_engine.api.dependencies.auth import require_observer, optional_auth, AuthContext

router = APIRouter(prefix="/agent", tags=["agent"])

# Request/Response schemas

class SendMessageRequest(BaseModel):
    """Request to send a message to the agent."""
    content: str = Field(..., description="Message content")
    channel_id: str = Field("api_default", description="Channel identifier")
    author_id: Optional[str] = Field(None, description="Author ID (defaults to user ID)")
    author_name: Optional[str] = Field(None, description="Author display name")
    reference_message_id: Optional[str] = Field(None, description="ID of message being replied to")

class MessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: str = Field(..., description="Unique message ID")
    channel_id: str = Field(..., description="Channel the message was sent to")
    status: str = Field(..., description="Processing status")
    timestamp: datetime = Field(..., description="When message was received")

class AskRequest(BaseModel):
    """Request to ask and wait for response."""
    question: str = Field(..., description="Question to ask the agent")
    timeout: int = Field(30, ge=1, le=300, description="Timeout in seconds")
    channel_id: str = Field("api_ask", description="Channel for conversation")

class AskResponse(BaseModel):
    """Response to ask request."""
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Agent's response")
    message_id: str = Field(..., description="Message ID of response")
    processing_time_ms: int = Field(..., description="Time taken to process")

class AgentStatus(BaseModel):
    """Agent status information."""
    agent_id: str = Field(..., description="Agent identifier")
    name: str = Field(..., description="Agent name")
    state: CognitiveState = Field(..., description="Current cognitive state")
    uptime_seconds: float = Field(..., description="Time since startup")
    messages_processed: int = Field(..., description="Total messages processed")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class AgentIdentity(BaseModel):
    """Agent identity information."""
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    purpose: str = Field(..., description="Agent's purpose")
    created_at: datetime = Field(..., description="When agent was created")
    lineage: Dict[str, Any] = Field(..., description="Agent lineage information")
    variance_threshold: float = Field(..., description="Identity variance threshold")

class AgentCapabilities(BaseModel):
    """Agent capability information."""
    tools: List[str] = Field(..., description="Available tools")
    handlers: List[str] = Field(..., description="Active handlers")
    services: Dict[str, int] = Field(..., description="Service availability")
    permissions: List[str] = Field(..., description="Agent permissions")

class ConversationHistory(BaseModel):
    """Conversation history."""
    channel_id: str = Field(..., description="Channel identifier")
    messages: List[FetchedMessage] = Field(..., description="Message history")
    total_messages: int = Field(..., description="Total messages in channel")
    has_more: bool = Field(..., description="Whether more messages exist")

# Message tracking for ask/wait functionality
_message_responses: Dict[str, str] = {}
_response_events: Dict[str, asyncio.Event] = {}

# Endpoints

@router.post("/messages", response_model=SuccessResponse[MessageResponse])
async def send_message(
    request: Request,
    body: SendMessageRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Send message to agent.
    
    The agent will process the message asynchronously.
    Use WebSocket connection for real-time responses.
    """
    # Get communication service from adapter
    comm_service = getattr(request.app.state, 'communication_service', None)
    if not comm_service:
        raise HTTPException(status_code=503, detail="Communication service not available")
    
    # Create message
    message_id = str(uuid.uuid4())
    msg = IncomingMessage(
        message_id=message_id,
        author_id=body.author_id or auth.user_id,
        author_name=body.author_name or auth.user_id,
        content=body.content,
        channel_id=body.channel_id,
        reference_message_id=body.reference_message_id,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    # Route message through adapter's handler
    if hasattr(request.app.state, 'on_message'):
        await request.app.state.on_message(msg)
    else:
        raise HTTPException(status_code=503, detail="Message handler not configured")
    
    response = MessageResponse(
        message_id=message_id,
        channel_id=body.channel_id,
        status="accepted",
        timestamp=datetime.now(timezone.utc)
    )
    
    return SuccessResponse(data=response)

@router.get("/messages", response_model=SuccessResponse[ConversationHistory])
async def get_messages(
    request: Request,
    channel_id: str = Query("api_default", description="Channel to get messages from"),
    limit: int = Query(50, ge=1, le=200, description="Maximum messages to return"),
    after: Optional[str] = Query(None, description="Get messages after this message ID"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get conversation history.
    
    Retrieve messages from a specific channel.
    """
    # Get communication service
    comm_service = getattr(request.app.state, 'communication_service', None)
    if not comm_service:
        raise HTTPException(status_code=503, detail="Communication service not available")
    
    try:
        # Fetch messages
        messages = await comm_service.fetch_messages(channel_id, limit)
        
        # Filter if after is specified
        if after:
            found = False
            filtered = []
            for msg in messages:
                if found:
                    filtered.append(msg)
                elif msg.id == after:
                    found = True
            messages = filtered
        
        # Build response
        history = ConversationHistory(
            channel_id=channel_id,
            messages=messages,
            total_messages=len(messages),
            has_more=len(messages) == limit
        )
        
        return SuccessResponse(data=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask", response_model=SuccessResponse[AskResponse])
async def ask_and_wait(
    request: Request,
    body: AskRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Ask and wait for response.
    
    Send a message and wait for the agent's response.
    This is a convenience endpoint for simple Q&A interactions.
    """
    # Create unique IDs
    message_id = str(uuid.uuid4())
    event = asyncio.Event()
    _response_events[message_id] = event
    
    # Send message
    msg = IncomingMessage(
        message_id=message_id,
        author_id=auth.user_id,
        author_name=auth.user_id,
        content=body.question,
        channel_id=body.channel_id,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    # Track timing
    start_time = datetime.now(timezone.utc)
    
    # Route message
    if hasattr(request.app.state, 'on_message'):
        await request.app.state.on_message(msg)
    else:
        raise HTTPException(status_code=503, detail="Message handler not configured")
    
    # Wait for response with timeout
    try:
        await asyncio.wait_for(event.wait(), timeout=body.timeout)
        
        # Get response
        response_content = _message_responses.get(message_id, "No response received")
        
        # Clean up
        _response_events.pop(message_id, None)
        _message_responses.pop(message_id, None)
        
        # Calculate processing time
        end_time = datetime.now(timezone.utc)
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        response = AskResponse(
            question=body.question,
            answer=response_content,
            message_id=message_id,
            processing_time_ms=processing_time_ms
        )
        
        return SuccessResponse(data=response)
        
    except asyncio.TimeoutError:
        # Clean up
        _response_events.pop(message_id, None)
        _message_responses.pop(message_id, None)
        
        raise HTTPException(
            status_code=408,
            detail=f"Response timeout after {body.timeout} seconds"
        )

@router.get("/status", response_model=SuccessResponse[AgentStatus])
async def get_agent_status(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Agent status and state.
    
    Get current agent status including cognitive state.
    """
    # Get runtime info
    runtime = getattr(request.app.state, 'runtime', None)
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")
    
    try:
        # Get cognitive state
        cognitive_state = CognitiveState.WORK
        if hasattr(runtime, 'state_manager'):
            cognitive_state = runtime.state_manager.current_state
        
        # Get uptime
        time_service = getattr(request.app.state, 'time_service', None)
        uptime = 0.0
        if time_service and hasattr(time_service, 'get_uptime'):
            uptime = await time_service.get_uptime()
        
        # Get message count (simplified)
        messages_processed = 0
        if hasattr(runtime, 'metrics'):
            messages_processed = runtime.metrics.get('messages_processed', 0)
        
        # Get agent identity
        agent_id = "ciris_agent"
        agent_name = "CIRIS"
        if hasattr(runtime, 'agent_identity'):
            agent_id = runtime.agent_identity.agent_id
            agent_name = runtime.agent_identity.name
        
        status = AgentStatus(
            agent_id=agent_id,
            name=agent_name,
            state=cognitive_state,
            uptime_seconds=uptime,
            messages_processed=messages_processed,
            last_activity=datetime.now(timezone.utc)
        )
        
        return SuccessResponse(data=status)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/identity", response_model=SuccessResponse[AgentIdentity])
async def get_agent_identity(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Agent identity info.
    
    Get detailed agent identity information.
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
        
        if not nodes:
            # Fallback to runtime identity
            runtime = getattr(request.app.state, 'runtime', None)
            if runtime and hasattr(runtime, 'agent_identity'):
                identity = runtime.agent_identity
                response = AgentIdentity(
                    agent_id=identity.agent_id,
                    name=identity.name,
                    purpose=identity.purpose,
                    created_at=identity.created_at,
                    lineage=identity.lineage,
                    variance_threshold=0.2
                )
                return SuccessResponse(data=response)
            else:
                raise HTTPException(status_code=404, detail="Agent identity not found")
        
        # Extract identity from node
        identity_node = nodes[0]
        attributes = identity_node.attributes
        
        response = AgentIdentity(
            agent_id=attributes.get('agent_id', 'ciris_agent'),
            name=attributes.get('name', 'CIRIS'),
            purpose=attributes.get('purpose', 'Autonomous AI agent'),
            created_at=datetime.fromisoformat(attributes.get('created_at', datetime.now(timezone.utc).isoformat())),
            lineage=attributes.get('lineage', {}),
            variance_threshold=attributes.get('variance_threshold', 0.2)
        )
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities", response_model=SuccessResponse[AgentCapabilities])
async def get_agent_capabilities(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Agent capabilities.
    
    Get information about agent's available tools and services.
    """
    # Get tool service
    tool_service = getattr(request.app.state, 'tool_service', None)
    
    # Get available tools
    tools = []
    if tool_service:
        tools = await tool_service.list_tools()
    
    # Get handlers (simplified)
    handlers = [
        "observe", "speak", "tool", "reject", "ponder", 
        "defer", "memorize", "recall", "forget", "task_complete"
    ]
    
    # Get service availability
    services = {}
    if hasattr(request.app.state, 'service_registry'):
        service_registry = request.app.state.service_registry
        from ciris_engine.schemas.runtime.enums import ServiceType
        for service_type in ServiceType:
            providers = service_registry.get_services_by_type(service_type)
            services[service_type.value] = len(providers)
    
    # Get permissions
    permissions = [
        "communicate", "use_tools", "access_memory",
        "observe_environment", "learn", "adapt"
    ]
    
    capabilities = AgentCapabilities(
        tools=tools,
        handlers=handlers,
        services=services,
        permissions=permissions
    )
    
    return SuccessResponse(data=capabilities)

@router.websocket("/connect")
async def websocket_connect(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="API key for authentication")
):
    """
    WebSocket connection.
    
    Real-time bidirectional communication with the agent.
    """
    # Validate authentication if provided
    auth_context = None
    if token:
        auth_service = getattr(websocket.app.state, 'auth_service', None)
        if auth_service:
            key_info = await auth_service.validate_api_key(token)
            if not key_info:
                await websocket.close(code=1008, reason="Invalid authentication")
                return
            auth_context = auth_context  # Create auth context
    
    await websocket.accept()
    
    # Create channel for this connection
    channel_id = f"ws_{uuid.uuid4().hex[:8]}"
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Validate message
            if 'content' not in data:
                await websocket.send_json({
                    "error": "Missing required field: content"
                })
                continue
            
            # Create and route message
            message_id = str(uuid.uuid4())
            msg = IncomingMessage(
                message_id=message_id,
                author_id=data.get('author_id', 'websocket_user'),
                author_name=data.get('author_name', 'WebSocket User'),
                content=data['content'],
                channel_id=channel_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "ack",
                "message_id": message_id,
                "timestamp": msg.timestamp
            })
            
            # Route to agent
            if hasattr(websocket.app.state, 'on_message'):
                await websocket.app.state.on_message(msg)
            
            # TODO: Set up response streaming back to websocket
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {channel_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")

# Helper function to notify ask/wait responses
async def notify_ask_response(message_id: str, content: str):
    """Notify waiting ask requests of responses."""
    if message_id in _response_events:
        _message_responses[message_id] = content
        _response_events[message_id].set()

import logging
logger = logging.getLogger(__name__)