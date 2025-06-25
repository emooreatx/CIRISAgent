# SDK Update Plan

## Overview

This document outlines the comprehensive plan to redesign the CIRIS SDK from the ground up, following the **"No Dicts, No Strings, No Kings"** principles and aligning with the new protocol-based architecture.

## Current State Analysis

### Existing SDK Issues
1. **Type Safety Violations**:
   - Extensive use of `Dict[str, Any]`
   - Untyped responses in many places
   - String-based constants instead of enums

2. **Architectural Misalignment**:
   - Resource design mirrors old handler architecture
   - Direct service access patterns
   - Scope-based memory model (deprecated)
   - Assumes internal implementation details

3. **Maintenance Burden**:
   - Complex error handling
   - Inconsistent async patterns
   - Tight coupling to API implementation
   - No clear versioning strategy

## SDK V2 Design Principles

### 1. Zero Dicts Policy
```python
# ❌ OLD: Untyped dictionaries
response = await client.memory.store({"key": "value", "data": {...}})

# ✅ NEW: Fully typed models
node = GraphNode(
    type=NodeType.MEMORY,
    attributes=MemoryAttributes(key="value", data=TypedData(...))
)
response = await client.memory.memorize(node)
```

### 2. Capability-Based Architecture
```python
# ❌ OLD: Service-oriented
await client.services.telemetry.get_metrics()
await client.services.config.update_value()

# ✅ NEW: Capability-oriented  
await client.telemetry.get_overview()
await client.runtime.update_config(updates)
```

### 3. Graph-Native Memory
```python
# ❌ OLD: Key-value scopes
await client.memory.set_value("preferences", "theme", "dark")

# ✅ NEW: Graph nodes
preference_node = PreferenceNode(
    id="user_theme_preference",
    value=ThemePreference.DARK,
    user_id="current_user"
)
await client.memory.memorize(preference_node.to_graph_node())
```

## Implementation Plan

### Phase 1: Core Architecture (Week 1)

#### 1.1 Project Structure
```
ciris_sdk/
├── __init__.py          # Version, exports
├── client.py            # Main client class
├── transport/
│   ├── __init__.py
│   ├── http.py          # HTTP transport layer
│   ├── websocket.py     # WebSocket for streaming
│   └── auth.py          # Authentication handling
├── resources/
│   ├── __init__.py
│   ├── agent.py         # Agent interaction
│   ├── memory.py        # Graph memory operations
│   ├── runtime.py       # Runtime control
│   ├── telemetry.py     # Metrics and monitoring
│   ├── tools.py         # Tool discovery/execution
│   ├── incidents.py     # Incident management
│   ├── adaptation.py    # Self-configuration
│   └── visibility.py    # Agent introspection
├── models/
│   ├── __init__.py
│   ├── common.py        # Shared models
│   ├── graph.py         # Graph node models
│   ├── agent.py         # Agent-specific models
│   ├── runtime.py       # Runtime models
│   └── telemetry.py     # Telemetry models
├── exceptions.py        # Typed exceptions
├── typing.py            # Type definitions
└── utils.py             # Utilities
```

#### 1.2 Base Client Implementation
```python
# ciris_sdk/client.py
from typing import Optional, Dict, Any
from httpx import AsyncClient
import httpx

from .transport import HTTPTransport, AuthHandler
from .resources import (
    AgentResource, MemoryResource, RuntimeResource,
    TelemetryResource, ToolsResource, IncidentsResource,
    AdaptationResource, VisibilityResource
)
from .models import ClientConfig


class CIRISClient:
    """Async client for CIRIS API interaction."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        config: Optional[ClientConfig] = None
    ):
        self.config = config or ClientConfig()
        self.transport = HTTPTransport(
            base_url=base_url,
            timeout=self.config.timeout,
            auth=AuthHandler(api_key=api_key)
        )
        
        # Initialize resources
        self.agent = AgentResource(self.transport)
        self.memory = MemoryResource(self.transport)
        self.runtime = RuntimeResource(self.transport)
        self.telemetry = TelemetryResource(self.transport)
        self.tools = ToolsResource(self.transport)
        self.incidents = IncidentsResource(self.transport)
        self.adaptation = AdaptationResource(self.transport)
        self.visibility = VisibilityResource(self.transport)
    
    async def __aenter__(self):
        await self.transport.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.transport.disconnect()
    
    async def health_check(self) -> HealthStatus:
        """Check API health."""
        return await self.transport.get("/v1/health", response_model=HealthStatus)
```

### Phase 2: Resource Implementation (Week 1-2)

#### 2.1 Agent Resource
```python
# ciris_sdk/resources/agent.py
from typing import Optional, List
from datetime import datetime

from ..models.agent import (
    Message, Author, MessageResponse, 
    Channel, AgentStatus, ConversationOptions
)
from ..transport import Transport


class AgentResource:
    """Agent interaction capabilities."""
    
    def __init__(self, transport: Transport):
        self._transport = transport
    
    async def send_message(
        self,
        content: str,
        channel_id: str = "api_default",
        author: Optional[Author] = None,
        correlation_id: Optional[str] = None
    ) -> MessageResponse:
        """Send a message to the agent."""
        payload = SendMessageRequest(
            content=content,
            channel_id=channel_id,
            author=author or Author(),
            correlation_id=correlation_id
        )
        
        return await self._transport.post(
            "/v1/agent/messages",
            data=payload,
            response_model=MessageResponse
        )
    
    async def get_messages(
        self,
        channel_id: str,
        after: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get messages from a channel."""
        params = GetMessagesParams(
            channel_id=channel_id,
            after_timestamp=after,
            limit=limit
        )
        
        response = await self._transport.get(
            "/v1/agent/messages",
            params=params,
            response_model=MessageListResponse
        )
        return response.messages
    
    async def ask(
        self,
        question: str,
        timeout: float = 30.0,
        channel_id: str = "api_default"
    ) -> Optional[str]:
        """Ask a question and wait for response."""
        # Send question
        msg_response = await self.send_message(
            content=question,
            channel_id=channel_id
        )
        
        # Wait for response
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            messages = await self.get_messages(
                channel_id=channel_id,
                after=msg_response.timestamp
            )
            
            agent_messages = [
                msg for msg in messages 
                if msg.author.id == "ciris_agent"
            ]
            
            if agent_messages:
                return agent_messages[0].content
            
            await asyncio.sleep(0.5)
        
        return None
    
    async def get_status(self) -> AgentStatus:
        """Get agent status."""
        return await self._transport.get(
            "/v1/agent/status",
            response_model=AgentStatus
        )
```

#### 2.2 Memory Resource (Graph-Based)
```python
# ciris_sdk/resources/memory.py
from typing import Optional, List, Dict
from datetime import datetime

from ..models.graph import (
    GraphNode, NodeType, GraphScope,
    SearchRequest, SearchResponse,
    RecallRequest, GraphQuery
)
from ..transport import Transport


class MemoryResource:
    """Graph memory operations."""
    
    def __init__(self, transport: Transport):
        self._transport = transport
    
    async def memorize(
        self,
        node: GraphNode,
        handler_name: str = "sdk_client",
        metadata: Optional[MemoryMetadata] = None
    ) -> MemorizeResponse:
        """Store a memory node in the graph."""
        request = MemorizeRequest(
            node=node,
            handler_name=handler_name,
            metadata=metadata or MemoryMetadata()
        )
        
        return await self._transport.post(
            "/v1/memory/memorize",
            data=request,
            response_model=MemorizeResponse
        )
    
    async def recall(
        self,
        node_id: str
    ) -> Optional[GraphNode]:
        """Recall a specific memory node."""
        response = await self._transport.get(
            f"/v1/memory/nodes/{node_id}",
            response_model=GraphNodeResponse
        )
        return response.node if response.found else None
    
    async def search(
        self,
        query: str,
        node_types: Optional[List[NodeType]] = None,
        scopes: Optional[List[GraphScope]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> SearchResponse:
        """Search graph memory."""
        request = SearchRequest(
            query=query,
            node_types=node_types,
            scopes=scopes,
            limit=limit,
            offset=offset
        )
        
        return await self._transport.post(
            "/v1/memory/search",
            data=request,
            response_model=SearchResponse
        )
    
    async def query_graph(
        self,
        query: GraphQuery
    ) -> GraphQueryResponse:
        """Execute a graph query."""
        return await self._transport.post(
            "/v1/memory/graph/query",
            data=query,
            response_model=GraphQueryResponse
        )
    
    async def get_correlations(
        self,
        node_id: str,
        correlation_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Correlation]:
        """Get correlations for a node."""
        params = CorrelationParams(
            node_id=node_id,
            types=correlation_types,
            limit=limit
        )
        
        response = await self._transport.get(
            "/v1/memory/correlations",
            params=params,
            response_model=CorrelationResponse
        )
        return response.correlations
```

### Phase 3: Type-Safe Models (Week 2)

#### 3.1 Common Models
```python
# ciris_sdk/models/common.py
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Author(BaseModel):
    """Message author."""
    id: str = Field(default="api_user")
    name: str = Field(default="API User")
    role: Optional[str] = None


class CognitiveState(str, Enum):
    """Agent cognitive states."""
    WAKEUP = "WAKEUP"
    WORK = "WORK" 
    PLAY = "PLAY"
    SOLITUDE = "SOLITUDE"
    DREAM = "DREAM"
    SHUTDOWN = "SHUTDOWN"


class Permission(str, Enum):
    """Permission levels."""
    OBSERVER = "OBSERVER"
    AUTHORITY = "AUTHORITY"


class HealthStatus(BaseModel):
    """System health status."""
    healthy: bool
    version: str
    uptime_seconds: float
    current_state: CognitiveState
    service_health: Dict[str, bool]  # Service name -> healthy


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
```

#### 3.2 Graph Models
```python
# ciris_sdk/models/graph.py
from enum import Enum
from typing import Optional, List, Dict, Union
from datetime import datetime
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Graph node types."""
    AGENT = "agent"
    USER = "user"
    MEMORY = "memory"
    CONCEPT = "concept"
    CONFIG = "config"
    TSDB_DATA = "tsdb_data"
    TSDB_SUMMARY = "tsdb_summary"
    AUDIT_ENTRY = "audit_entry"
    INCIDENT = "incident"
    PROBLEM = "problem"
    INSIGHT = "insight"
    IDENTITY_SNAPSHOT = "identity_snapshot"


class GraphScope(str, Enum):
    """Node visibility scopes."""
    LOCAL = "local"
    IDENTITY = "identity"
    ENVIRONMENT = "environment"
    COMMUNITY = "community"


class GraphNodeAttributes(BaseModel):
    """Base attributes for all nodes."""
    created_at: datetime
    updated_at: datetime
    created_by: str
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "forbid"  # No arbitrary fields


class GraphNode(BaseModel):
    """Graph node representation."""
    id: str
    type: NodeType
    scope: GraphScope
    attributes: GraphNodeAttributes
    version: int = 1
    
    class Config:
        extra = "forbid"


class MemoryAttributes(GraphNodeAttributes):
    """Memory-specific attributes."""
    content: str
    importance: float = Field(ge=0.0, le=1.0)
    context: Optional[str] = None


class GraphEdge(BaseModel):
    """Edge between nodes."""
    source: str
    target: str
    relationship: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime
```

### Phase 4: Advanced Features (Week 2-3)

#### 4.1 Streaming Support
```python
# ciris_sdk/transport/websocket.py
import asyncio
from typing import AsyncIterator, Optional
import websockets
import json

from ..models import StreamEvent, StreamOptions


class WebSocketTransport:
    """WebSocket transport for streaming."""
    
    async def stream_messages(
        self,
        channel_id: str,
        options: Optional[StreamOptions] = None
    ) -> AsyncIterator[Message]:
        """Stream messages from a channel."""
        url = f"{self.ws_url}/v1/agent/messages/stream"
        params = {"channel_id": channel_id}
        
        async with websockets.connect(url) as websocket:
            await websocket.send(json.dumps(params))
            
            while True:
                data = await websocket.recv()
                event = StreamEvent.parse_raw(data)
                
                if event.type == "message":
                    yield Message.parse_obj(event.data)
                elif event.type == "error":
                    raise StreamError(event.data["error"])
    
    async def stream_telemetry(
        self
    ) -> AsyncIterator[TelemetryUpdate]:
        """Stream telemetry updates."""
        url = f"{self.ws_url}/v1/telemetry/stream"
        
        async with websockets.connect(url) as websocket:
            while True:
                data = await websocket.recv()
                yield TelemetryUpdate.parse_raw(data)
```

#### 4.2 Batch Operations
```python
# ciris_sdk/resources/memory.py
class MemoryResource:
    
    async def memorize_batch(
        self,
        nodes: List[GraphNode],
        handler_name: str = "sdk_client"
    ) -> BatchMemorizeResponse:
        """Store multiple nodes efficiently."""
        request = BatchMemorizeRequest(
            nodes=nodes,
            handler_name=handler_name
        )
        
        return await self._transport.post(
            "/v1/memory/batch/memorize",
            data=request,
            response_model=BatchMemorizeResponse
        )
    
    async def recall_batch(
        self,
        node_ids: List[str]
    ) -> Dict[str, Optional[GraphNode]]:
        """Recall multiple nodes efficiently."""
        request = BatchRecallRequest(node_ids=node_ids)
        
        response = await self._transport.post(
            "/v1/memory/batch/recall",
            data=request,
            response_model=BatchRecallResponse
        )
        
        return {
            node_id: node
            for node_id, node in zip(node_ids, response.nodes)
        }
```

#### 4.3 Convenience Methods
```python
# ciris_sdk/client.py
class CIRISClient:
    
    async def quick_ask(self, question: str) -> str:
        """Ask a question and get response."""
        response = await self.agent.ask(question)
        return response or "No response received"
    
    async def remember(
        self,
        content: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> str:
        """Simple memory storage."""
        node = GraphNode(
            id=f"memory_{datetime.now().timestamp()}",
            type=NodeType.MEMORY,
            scope=GraphScope.LOCAL,
            attributes=MemoryAttributes(
                content=content,
                importance=importance,
                tags=tags or [],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by="sdk_user"
            )
        )
        
        response = await self.memory.memorize(node)
        return response.node_id
    
    async def find_memories(
        self,
        query: str,
        limit: int = 10
    ) -> List[str]:
        """Simple memory search."""
        results = await self.memory.search(
            query=query,
            node_types=[NodeType.MEMORY],
            limit=limit
        )
        
        return [
            node.attributes.get("content", "")
            for node in results.nodes
            if hasattr(node.attributes, "content")
        ]
```

### Phase 5: Testing & Documentation (Week 3)

#### 5.1 Test Suite
```python
# tests/test_client.py
import pytest
from ciris_sdk import CIRISClient
from ciris_sdk.models import GraphNode, NodeType


@pytest.mark.asyncio
async def test_agent_interaction():
    """Test basic agent interaction."""
    async with CIRISClient("http://localhost:8080") as client:
        # Send message
        response = await client.agent.send_message("Hello!")
        assert response.status == "sent"
        
        # Get response
        reply = await client.agent.ask("How are you?")
        assert reply is not None


@pytest.mark.asyncio
async def test_memory_operations():
    """Test graph memory operations."""
    async with CIRISClient("http://localhost:8080") as client:
        # Store memory
        memory_id = await client.remember(
            "User prefers dark theme",
            importance=0.8,
            tags=["preference", "ui"]
        )
        
        # Search memories
        results = await client.find_memories("theme")
        assert len(results) > 0
        assert "dark theme" in results[0]
```

#### 5.2 Documentation
- Comprehensive API documentation
- Usage examples for each resource
- Migration guide from v1
- Best practices guide
- Type reference documentation

### Phase 6: Migration Support (Week 3-4)

#### 6.1 Compatibility Layer
```python
# ciris_sdk/compat/v1.py
"""Compatibility layer for SDK v1 users."""

class LegacyClient:
    """Wrapper providing v1-compatible interface."""
    
    def __init__(self, v2_client: CIRISClient):
        self._client = v2_client
    
    async def set_memory(self, scope: str, key: str, value: Any):
        """Legacy memory storage."""
        # Convert to graph node
        node = self._legacy_to_node(scope, key, value)
        await self._client.memory.memorize(node)
    
    async def get_memory(self, scope: str, key: str) -> Any:
        """Legacy memory retrieval."""
        # Search for node
        results = await self._client.memory.search(
            query=f"{scope}:{key}",
            limit=1
        )
        
        if results.nodes:
            return self._node_to_legacy(results.nodes[0])
        return None
```

#### 6.2 Migration Guide
- Side-by-side examples
- Common pattern translations
- Gradual migration strategy
- Deprecation warnings

## Success Criteria

1. **Type Safety**: 100% typed, zero Dict[str, Any]
2. **Coverage**: All API endpoints accessible
3. **Performance**: <50ms overhead for operations
4. **Usability**: Intuitive API design
5. **Compatibility**: Smooth migration path

## Timeline

- **Week 1**: Core architecture and base resources
- **Week 2**: Complete resource implementation
- **Week 2-3**: Advanced features and conveniences
- **Week 3**: Testing and documentation
- **Week 3-4**: Migration support and rollout

## Risk Mitigation

1. **Breaking Changes**: Compatibility layer for gradual migration
2. **API Changes**: Version detection and adaptation
3. **Type Complexity**: Progressive type disclosure
4. **Performance**: Connection pooling and caching

## Next Steps

1. Set up new SDK repository
2. Implement core architecture
3. Create type definitions
4. Build test framework
5. Begin resource implementation

This SDK will provide a clean, typed, and intuitive interface to CIRIS while maintaining the flexibility to evolve with the agent's capabilities.