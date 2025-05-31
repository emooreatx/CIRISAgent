# Service Registry System

The CIRIS Agent service registry provides a unified, resilient system for managing services across handlers with automatic fallback, circuit breaker patterns, and priority-based selection.

## Architecture

### Core Components

1. **ServiceRegistry** - Central registry for all services
2. **CircuitBreaker** - Prevents cascading failures
3. **Priority System** - Determines service selection order
4. **Protocol Contracts** - Type-safe service interfaces

### Service Types

- **CommunicationService** - Discord, Veilid, etc.
- **WiseAuthorityService** - CIRISNode, local WA, etc.
- **MemoryService** - Local graph, remote storage, etc.
- **ToolService** - Tool execution and result management

## Runtime Integration

### Base CIRISRuntime Setup

The base `CIRISRuntime` automatically:
1. Initializes the service registry
2. Registers core services (memory, etc.)
3. Passes registry to all handlers via `ActionHandlerDependencies`

### Subclass Extension Example

```python
# ciris_engine/runtime/discord_runtime.py
class DiscordRuntime(CIRISRuntime):
    async def _register_core_services(self):
        """Extend core service registration with Discord-specific services"""
        # Call parent to register memory service
        await super()._register_core_services()
        
        # Register Discord as primary communication service
        if self.discord_adapter:
            self.service_registry.register(
                handler="SpeakHandler",
                service_type="communication", 
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                capabilities=["send_message", "fetch_messages", "discord"]
            )
            
            # Also register for other handlers that need communication
            for handler in ["ObserveHandler", "ToolHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="communication",
                    provider=self.discord_adapter,
                    priority=Priority.HIGH,
                    capabilities=["send_message", "fetch_messages"]
                )
        
        # Register CIRISNode as WA service
        if self.cirisnode_client:
            for handler in ["DeferHandler", "SpeakHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="wise_authority",
                    provider=self.cirisnode_client, 
                    priority=Priority.NORMAL,
                    capabilities=["request_guidance", "submit_deferral"]
                )
        
        # Register fallback communication service (if available)
        if self.veilid_adapter:
            self.service_registry.register(
                handler="SpeakHandler",
                service_type="communication",
                provider=self.veilid_adapter,
                priority=Priority.NORMAL,  # Lower priority than Discord
                capabilities=["send_message", "veilid"]
            )
```

## Handler Usage

### Updated Handler Pattern

Handlers now use the service registry through the base class methods:

```python
class SpeakHandler(BaseActionHandler):
    async def handle(self, result, thought, dispatch_context):
        # Get best available communication service
        comm_service = await self.get_communication_service()
        
        if comm_service:
            success = await comm_service.send_message(channel_id, content)
            if success:
                await self._audit_log(HandlerActionType.SPEAK, dispatch_context, 
                                    {"status": "success", "service": type(comm_service).__name__})
            else:
                # Registry automatically tries fallback services
                await self._audit_log(HandlerActionType.SPEAK, dispatch_context,
                                    {"status": "failed", "service": type(comm_service).__name__})
        else:
            # log and exit
            return 1
```

### Available Service Methods

The `BaseActionHandler` provides these convenience methods:

```python
# Communication services
comm_service = await self.get_communication_service()

# WA services  
wa_service = await self.get_wa_service()

# Memory services
memory_service = await self.get_memory_service()

# Tool services
tool_service = await self.get_tool_service()

# Generic service access
service = await self.get_service("service_type", required_capabilities=["capability"])
```

## Circuit Breaker Integration

The registry automatically handles service failures:

1. **Failure Tracking** - Services that fail have their circuit breaker failure count incremented
2. **Automatic Cutoff** - After N failures, the service is temporarily disabled
3. **Recovery Testing** - After a timeout, the service is retested with limited requests
4. **Fallback Activation** - Lower priority services are automatically tried

## Multi-Service Sink

The `MultiServiceActionSink` provides unified action processing:

```python
# Create and start the sink
sink = MultiServiceActionSink(service_registry=registry)
await sink.start()

# Send actions via convenience methods
await sink.send_message("SpeakHandler", channel_id, "Hello world!")
await sink.submit_deferral("DeferHandler", thought_id, "Need more context")
await sink.execute_tool("ToolHandler", "search", {"query": "example"})

# Or queue actions directly
action = SendMessageAction(
    handler_name="SpeakHandler",
    metadata={},
    channel_id=channel_id,
    content="Direct action message"
)
await sink.enqueue_action(action)
```

## Migration Guide

### For Existing Handlers

1. **Add service registry calls** - Use `get_*_service()` methods for new features
2. **Update error handling** - Registry provides automatic fallback

### For Runtime Implementations

1. **Extend `_register_core_services()`** - Add your adapter registrations
2. **Use standard protocols** - Implement `CommunicationService`, etc.
3. **Set priorities appropriately** - Higher priority services are tried first

## Benefits

1. **Automatic Fallback** - No manual fallback logic needed
2. **Circuit Breaker Protection** - Prevents cascading failures  
3. **Type Safety** - Protocol contracts ensure correct usage
4. **Backward Compatibility** - Existing code continues to work
5. **Centralized Configuration** - All service routing in one place
6. **Testability** - Easy to mock services for testing

## Performance

- **Service Selection**: O(log n) for sorted priority lists
- **Circuit Breaker**: O(1) state checks
- **Registry Lookup**: O(1) hash map access
- **Memory Overhead**: Minimal, stores references only

The registry is designed for high-throughput production use with minimal latency impact.
