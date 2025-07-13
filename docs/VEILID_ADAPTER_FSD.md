# Veilid Adapter Developer's Guide

## Overview

This guide provides detailed implementation instructions for integrating Veilid with CIRIS. The Veilid adapter will provide three services: CommunicationService, WiseAuthorityService, and ToolService, following the patterns established by existing adapters.

## Project Structure

```
ciris_engine/logic/adapters/veilid/
├── __init__.py
├── adapter.py              # VeilidPlatform - main entry point
├── veilid_adapter.py       # VeilidAdapter - implements all 3 services
├── veilid_observer.py      # Handles incoming Veilid messages
├── veilid_routing.py       # Route management utilities
├── veilid_dht.py          # DHT operations
├── veilid_tools.py        # Tool implementations
├── veilid_wise_authority.py # WA service for Veilid
└── config.py              # Configuration schemas
```

## 1. Platform Adapter (adapter.py)

Following the pattern from `cli/adapter.py` and `discord/adapter.py`:

```python
"""Veilid platform adapter for CIRIS."""
import logging
from typing import List, Optional, Any
from ciris_engine.protocols.runtime.base import BaseAdapterProtocol
from ciris_engine.schemas.adapters.registration import AdapterServiceRegistration
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.logic.registries.base import Priority
from .veilid_adapter import VeilidAdapter
from .veilid_observer import VeilidObserver
from .config import VeilidAdapterConfig

logger = logging.getLogger(__name__)

class VeilidPlatform(BaseAdapterProtocol):
    """Platform adapter for Veilid network integration."""
    
    def __init__(self, runtime: Any, **kwargs: Any) -> None:
        self.runtime = runtime
        self.config = VeilidAdapterConfig(**kwargs)
        
        # Initialize the main adapter service
        self.veilid_adapter = VeilidAdapter(
            runtime=runtime,
            config=self.config,
            time_service=self._get_time_service(),
            bus_manager=runtime.bus_manager if hasattr(runtime, 'bus_manager') else None
        )
        
        # Initialize observer
        self.veilid_observer = VeilidObserver(
            adapter=self.veilid_adapter,
            on_message=self._handle_incoming_message
        )
    
    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Register services following CLI and Discord patterns."""
        return [
            # Communication service (like all adapters)
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.veilid_adapter,
                priority=Priority.HIGH,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "fetch_messages", "veilid_routing"]
            ),
            # Wise Authority service (like Discord)
            AdapterServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.veilid_adapter,
                priority=Priority.NORMAL,
                handlers=["DeferHandler", "SpeakHandler"],
                capabilities=["fetch_guidance", "send_deferral", "distributed_consensus"]
            ),
            # Tool service (like all adapters)
            AdapterServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.veilid_adapter,
                priority=Priority.NORMAL,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "list_tools", "get_tool_info"]
            )
        ]
    
    async def start(self) -> None:
        """Start the Veilid platform."""
        logger.info("Starting Veilid platform adapter")
        await self.veilid_adapter.start()
        await self.veilid_observer.start()
    
    async def stop(self) -> None:
        """Stop the Veilid platform."""
        logger.info("Stopping Veilid platform adapter")
        await self.veilid_observer.stop()
        await self.veilid_adapter.stop()
    
    async def run_lifecycle(self, agent_task: Any) -> None:
        """Run adapter lifecycle (required by BaseAdapterProtocol)."""
        # Veilid doesn't need special lifecycle like Discord
        await agent_task
```

## 2. Main Adapter Service (veilid_adapter.py)

Following patterns from `cli/cli_adapter.py` and `discord/discord_adapter.py`:

```python
"""Veilid adapter implementing all three service protocols."""
import logging
import uuid
import veilid
from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime

from ciris_engine.protocols.services import (
    CommunicationService, WiseAuthorityService, ToolService
)
from ciris_engine.schemas.runtime.messages import IncomingMessage
from ciris_engine.schemas.adapters.tools import (
    ToolExecutionResult, ToolInfo, ToolParameterSchema, ToolExecutionStatus
)
from ciris_engine.schemas.services.authority_core import (
    DeferralRequest, GuidanceRequest, GuidanceResponse
)
from ciris_engine.schemas.services.context import GuidanceContext
from ciris_engine.logic.adapters.base import Service
from ciris_engine.logic import persistence
from .veilid_tools import VeilidToolHandler
from .veilid_wise_authority import VeilidWiseAuthority

logger = logging.getLogger(__name__)

class VeilidAdapter(Service, CommunicationService, WiseAuthorityService, ToolService):
    """
    Veilid adapter implementing all three service protocols.
    Pattern follows Discord adapter's multi-service approach.
    """
    
    def __init__(
        self,
        runtime: Optional[Any] = None,
        config: Optional[Any] = None,
        time_service: Optional[Any] = None,
        bus_manager: Optional[Any] = None,
        on_message: Optional[Callable[[IncomingMessage], Awaitable[None]]] = None
    ) -> None:
        super().__init__()
        
        self.runtime = runtime
        self.config = config
        self._time_service = time_service
        self.bus_manager = bus_manager
        self.on_message = on_message
        
        # Veilid node instance
        self._node: Optional[veilid.VeilidAPI] = None
        self._routing_context: Optional[veilid.RoutingContext] = None
        
        # Component handlers (like Discord)
        self._tool_handler = VeilidToolHandler(self)
        self._wise_authority = VeilidWiseAuthority(self, time_service)
        
        # Active routes and channels
        self._routes: Dict[str, veilid.RouteId] = {}
        self._channels: Dict[str, Dict[str, Any]] = {}
        
        self._running = False
        self._start_time: Optional[datetime] = None
    
    # ===== CommunicationService Implementation =====
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send message through Veilid network (like cli_adapter.py:122)."""
        correlation_id = str(uuid.uuid4())
        try:
            # Parse channel_id format: veilid_<node_id>_<route_id>
            parts = channel_id.split('_', 2)
            if len(parts) != 3 or parts[0] != 'veilid':
                logger.error(f"Invalid Veilid channel ID format: {channel_id}")
                return False
            
            node_id, route_id = parts[1], parts[2]
            
            # Get or create route
            if route_id not in self._routes:
                # Create new route to target
                route = await self._create_route_to_node(node_id)
                self._routes[route_id] = route
            
            # Send via Veilid
            route = self._routes[route_id]
            await self._send_via_route(route, content)
            
            # Create correlation (following CLI pattern)
            await self._create_correlation(
                correlation_id=correlation_id,
                action_type="speak",
                channel_id=channel_id,
                parameters={"content": content}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Veilid message: {e}")
            return False
    
    async def fetch_messages(
        self, 
        channel_id: str, 
        *, 
        limit: int = 50, 
        before: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch messages from correlations (like api_communication.py:142)."""
        from ciris_engine.logic.persistence import get_correlations_by_channel
        
        try:
            correlations = get_correlations_by_channel(
                channel_id=channel_id,
                limit=limit
            )
            
            messages = []
            for corr in correlations:
                if corr.action_type == "speak" and corr.request_data:
                    # Outgoing message
                    content = corr.request_data.parameters.get("content", "")
                    messages.append({
                        "id": corr.correlation_id,
                        "author_id": "veilid_self",
                        "author_name": "CIRIS",
                        "content": content,
                        "timestamp": corr.timestamp.isoformat(),
                        "channel_id": channel_id,
                        "is_bot": True
                    })
                elif corr.action_type == "observe" and corr.request_data:
                    # Incoming message
                    params = corr.request_data.parameters
                    messages.append({
                        "id": corr.correlation_id,
                        "author_id": params.get("author_id", "unknown"),
                        "author_name": params.get("author_name", "Unknown"),
                        "content": params.get("content", ""),
                        "timestamp": corr.timestamp.isoformat(),
                        "channel_id": channel_id,
                        "is_bot": False
                    })
            
            return sorted(messages, key=lambda m: m["timestamp"])
            
        except Exception as e:
            logger.error(f"Failed to fetch Veilid messages: {e}")
            return []
    
    # ===== WiseAuthorityService Implementation =====
    
    async def send_deferral(self, deferral: DeferralRequest) -> str:
        """Send deferral through Veilid consensus (like discord_adapter.py:544)."""
        return await self._wise_authority.send_deferral(deferral)
    
    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """Fetch guidance via distributed consensus."""
        return await self._wise_authority.fetch_guidance(context)
    
    # ===== ToolService Implementation =====
    
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """Execute Veilid tool (like cli_adapter.py:270)."""
        return await self._tool_handler.execute_tool(tool_name, parameters)
    
    async def list_tools(self) -> List[str]:
        """List available Veilid tools."""
        return await self._tool_handler.list_tools()
    
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed tool information."""
        return await self._tool_handler.get_tool_info(tool_name)
    
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get info for all tools."""
        return await self._tool_handler.get_all_tool_info()
    
    # ===== Lifecycle Methods =====
    
    async def start(self) -> None:
        """Start Veilid node and services."""
        logger.info("Starting Veilid adapter")
        self._start_time = self._time_service.now()
        
        # Initialize Veilid node
        config = self._build_veilid_config()
        self._node = await veilid.api_startup_json(config)
        
        # Attach to network
        await self._node.attach()
        
        # Create routing context
        self._routing_context = await self._node.routing_context()
        
        self._running = True
        
        # Start components
        await self._tool_handler.start()
        await self._wise_authority.start()
        
        # Emit telemetry
        await self._emit_telemetry("adapter_started", 1.0, {
            "adapter_type": "veilid",
            "node_id": await self._get_node_id()
        })
    
    async def stop(self) -> None:
        """Stop Veilid node and services."""
        logger.info("Stopping Veilid adapter")
        self._running = False
        
        # Stop components
        await self._wise_authority.stop()
        await self._tool_handler.stop()
        
        # Cleanup Veilid
        if self._routing_context:
            del self._routing_context
        
        if self._node:
            await self._node.detach()
            await veilid.api_shutdown()
        
        await self._emit_telemetry("adapter_stopped", 1.0, {
            "adapter_type": "veilid"
        })
```

## 3. Tool Handler (veilid_tools.py)

Following the pattern from CLI tools:

```python
"""Veilid-specific tools implementation."""
import logging
from typing import Dict, List, Optional, Any
import veilid

from ciris_engine.schemas.adapters.tools import (
    ToolInfo, ToolExecutionResult, ToolParameterSchema, ToolExecutionStatus
)

logger = logging.getLogger(__name__)

class VeilidToolHandler:
    """Handles Veilid-specific tool execution."""
    
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self._tools = {
            # Route management
            "create_private_route": self._tool_create_private_route,
            "list_routes": self._tool_list_routes,
            "inspect_route": self._tool_inspect_route,
            
            # DHT operations
            "publish_to_dht": self._tool_publish_to_dht,
            "read_from_dht": self._tool_read_from_dht,
            
            # Network discovery
            "find_peer": self._tool_find_peer,
            "list_peers": self._tool_list_peers,
            
            # Identity & crypto
            "create_identity": self._tool_create_identity,
            "verify_identity": self._tool_verify_identity,
            
            # Network health
            "network_status": self._tool_network_status,
            "ping_peer": self._tool_ping_peer,
        }
    
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """Execute a Veilid tool."""
        if tool_name not in self._tools:
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data={"available_tools": list(self._tools.keys())},
                error=f"Unknown tool: {tool_name}"
            )
        
        try:
            result = await self._tools[tool_name](parameters)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.COMPLETED,
                success=result.get("success", True),
                data=result,
                error=result.get("error")
            )
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data=None,
                error=str(e)
            )
    
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get information about a specific tool."""
        tool_schemas = {
            "create_private_route": ToolParameterSchema(
                type="object",
                properties={
                    "hop_count": {"type": "integer", "minimum": 1, "maximum": 5},
                    "stability": {"type": "string", "enum": ["low", "med", "high"]},
                    "sequencing": {"type": "boolean", "default": True}
                },
                required=["hop_count"]
            ),
            "list_routes": ToolParameterSchema(
                type="object",
                properties={
                    "include_stats": {"type": "boolean", "default": False}
                },
                required=[]
            ),
            # ... more schemas ...
        }
        
        tool_descriptions = {
            "create_private_route": "Create a new private route with configurable privacy",
            "list_routes": "List all active Veilid routes",
            "publish_to_dht": "Store data in the Veilid DHT",
            "find_peer": "Locate a peer by their Veilid ID",
            "network_status": "Get overall Veilid network health",
            # ... more descriptions ...
        }
        
        if tool_name not in self._tools:
            return None
        
        return ToolInfo(
            name=tool_name,
            description=tool_descriptions.get(tool_name, f"Veilid tool: {tool_name}"),
            parameters=tool_schemas.get(tool_name, ToolParameterSchema(type="object", properties={}, required=[])),
            category="veilid",
            cost=0.0
        )
    
    # Tool implementations following CLI pattern
    async def _tool_create_private_route(self, params: dict) -> dict:
        """Create a private route."""
        try:
            hop_count = params.get("hop_count", 2)
            stability = params.get("stability", "med")
            sequencing = params.get("sequencing", True)
            
            # Use Veilid API to create route
            route_id = await self.adapter._routing_context.new_private_route(
                hop_count=hop_count,
                stability=veilid.Stability[stability.upper()],
                sequencing=veilid.Sequencing.ENSURE_ORDERED if sequencing else veilid.Sequencing.NO_PREFERENCE
            )
            
            # Get route blob for sharing
            route_blob = await self.adapter._routing_context.export_route(route_id)
            
            return {
                "success": True,
                "route_id": str(route_id),
                "route_blob": route_blob,
                "hop_count": hop_count,
                "stability": stability
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
```

## 4. Wise Authority Service (veilid_wise_authority.py)

Following Discord's WA pattern but using distributed consensus:

```python
"""Veilid Wise Authority implementation using distributed consensus."""
import logging
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime

from ciris_engine.schemas.services.authority_core import (
    DeferralRequest, GuidanceRequest, GuidanceResponse
)
from ciris_engine.schemas.services.context import GuidanceContext

logger = logging.getLogger(__name__)

class VeilidWiseAuthority:
    """
    Implements WiseAuthorityService using Veilid's distributed consensus.
    Instead of Discord reactions, uses DHT voting mechanism.
    """
    
    def __init__(self, adapter: Any, time_service: Any) -> None:
        self.adapter = adapter
        self.time_service = time_service
        self._pending_deferrals: Dict[str, DeferralRequest] = {}
        self._consensus_threshold = 0.66  # 2/3 majority
    
    async def send_deferral(self, deferral: DeferralRequest) -> str:
        """Publish deferral to DHT for distributed consensus."""
        deferral_id = str(uuid.uuid4())
        
        try:
            # Create DHT record for deferral
            dht_key = f"deferral:{deferral_id}"
            deferral_data = {
                "deferral_id": deferral_id,
                "thought_id": deferral.thought_id,
                "task_id": deferral.task_id,
                "reason": deferral.reason,
                "timestamp": self.time_service.now().isoformat(),
                "votes": {},  # peer_id -> decision
                "status": "pending"
            }
            
            # Publish to DHT
            await self.adapter._publish_to_dht(dht_key, deferral_data, ttl=3600)
            
            # Notify peers via broadcast channel
            await self._broadcast_deferral_request(deferral_id, deferral)
            
            self._pending_deferrals[deferral_id] = deferral
            
            logger.info(f"Published deferral {deferral_id} to Veilid network")
            return deferral_id
            
        except Exception as e:
            logger.error(f"Failed to send Veilid deferral: {e}")
            raise
    
    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """Fetch guidance through distributed consensus."""
        guidance_id = str(uuid.uuid4())
        
        try:
            # Create guidance request in DHT
            dht_key = f"guidance:{guidance_id}"
            guidance_data = {
                "guidance_id": guidance_id,
                "question": context.question,
                "task_id": context.task_id,
                "ethical_considerations": context.ethical_considerations,
                "timestamp": self.time_service.now().isoformat(),
                "responses": {},  # peer_id -> guidance
                "status": "pending"
            }
            
            # Publish and wait for responses
            await self.adapter._publish_to_dht(dht_key, guidance_data, ttl=1800)
            
            # Wait for consensus or timeout
            guidance = await self._wait_for_consensus(dht_key, timeout=30)
            
            return guidance
            
        except Exception as e:
            logger.error(f"Failed to fetch Veilid guidance: {e}")
            return None
```

## 5. Observer Pattern (veilid_observer.py)

Following CLI observer pattern:

```python
"""Veilid message observer."""
import logging
import uuid
from typing import Callable, Awaitable, Optional
from datetime import datetime

from ciris_engine.schemas.runtime.messages import IncomingMessage
from ciris_engine.logic import persistence

logger = logging.getLogger(__name__)

class VeilidObserver:
    """Observes incoming Veilid messages and converts to CIRIS format."""
    
    def __init__(
        self, 
        adapter: Any,
        on_message: Optional[Callable[[IncomingMessage], Awaitable[None]]] = None
    ) -> None:
        self.adapter = adapter
        self.on_message = on_message
        self._running = False
    
    async def handle_veilid_message(self, sender_id: str, route_id: str, content: bytes) -> None:
        """Handle incoming Veilid message."""
        try:
            # Decode message
            message_content = content.decode('utf-8')
            
            # Create IncomingMessage
            channel_id = f"veilid_{sender_id}_{route_id}"
            msg = IncomingMessage(
                message_id=str(uuid.uuid4()),
                author_id=sender_id,
                author_name=f"Veilid:{sender_id[:8]}",
                content=message_content,
                channel_id=channel_id,
                timestamp=datetime.utcnow().isoformat()
            )
            
            # Create observe correlation
            await self._create_observe_correlation(msg)
            
            # Forward to handler
            if self.on_message:
                await self.on_message(msg)
            
        except Exception as e:
            logger.error(f"Error handling Veilid message: {e}")
```

## 6. Configuration Schema (config.py)

```python
"""Veilid adapter configuration."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class VeilidAdapterConfig(BaseModel):
    """Configuration for Veilid adapter."""
    
    # Network settings
    bootstrap_nodes: List[str] = Field(
        default_factory=lambda: ["bootstrap.veilid.net:5150"],
        description="Bootstrap nodes for network entry"
    )
    
    # Storage
    storage_path: str = Field(
        default="./veilid_storage",
        description="Path for Veilid state storage"
    )
    
    # Privacy settings
    default_route_privacy: str = Field(
        default="high",
        description="Default privacy level: low, med, high"
    )
    
    # DHT settings
    dht_default_ttl: int = Field(
        default=3600,
        description="Default TTL for DHT records in seconds"
    )
    
    # Identity
    node_identity: Optional[str] = Field(
        default=None,
        description="Persistent node identity (auto-generated if not provided)"
    )
    
    class Config:
        extra = "forbid"  # No Dict[str, Any]!
```

## Key Implementation Guidelines

### 1. **Channel ID Format**
Always use: `veilid_<node_id>_<route_id>`
- node_id: Target node's Veilid identity
- route_id: Specific route identifier

### 2. **Correlation Creation**
Follow CLI/Discord patterns:
- Create "speak" correlations for outgoing messages
- Create "observe" correlations for incoming messages
- Include all relevant metadata

### 3. **Tool Return Format**
Always return dict with:
- `success`: bool
- `error`: Optional[str] (if failed)
- Tool-specific data fields

### 4. **Telemetry Emission**
Use `memorize_metric()` for:
- adapter_started/stopped
- message_sent/received
- route_created/expired
- dht_operation_completed

### 5. **Error Handling**
- Log errors with context
- Return graceful failures
- Maintain adapter health even on partial failures

### 6. **Testing**
Create mock Veilid client for testing:
```python
class MockVeilidAPI:
    """Mock Veilid API for testing."""
    async def attach(self) -> None: pass
    async def detach(self) -> None: pass
    # ... implement other methods
```

## Integration Checklist

- [ ] Implement all three services (Communication, WiseAuthority, Tool)
- [ ] Register services with correct ServiceType enums
- [ ] Create proper ServiceCorrelations for all operations
- [ ] Use Pydantic models exclusively (no Dict[str, Any])
- [ ] Implement health check (`is_healthy()`)
- [ ] Add telemetry for all major operations
- [ ] Support runtime loading via adapter manager
- [ ] Handle graceful shutdown
- [ ] Create comprehensive tests
- [ ] Document all tools with schemas

This implementation follows CIRIS's typed, protocol-driven architecture while leveraging Veilid's privacy-preserving capabilities. The adapter can be loaded at runtime and provides full integration with CIRIS's bus system, memory graph, and audit trail.