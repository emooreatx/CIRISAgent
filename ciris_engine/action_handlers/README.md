# Action Handlers

Collection of handlers that execute actions selected by the Decision Making Architecture (DMA). Each handler is responsible for carrying out a specific type of action while maintaining proper audit trails, error handling, and service integration.

## Architecture

### Base Handler (`base_handler.py`)
The `BaseActionHandler` provides a foundation for all action handlers with:

- **Service Registry Integration**: Automatic service discovery and fallback mechanisms
- **Secrets Management**: Built-in automatic secrets decapsulation for secure operations
- **Error Handling**: Centralized error management with audit logging
- **Communication Services**: Unified interface for Discord, CLI, and API communications
- **Shutdown Management**: Graceful shutdown coordination across the system
- **Audit Logging**: Comprehensive logging of all handler operations

### Handler Dependencies (`ActionHandlerDependencies`)
Provides handlers with:
- Service registry for dynamic service discovery
- IO adapters for communication
- Secrets service for automatic secret management
- Shutdown callbacks for coordinated system shutdown

## Available Handlers

### Core Actions
- **`speak_handler.py`**: Send messages to users through appropriate channels
- **`observe_handler.py`**: Process observations and trigger appropriate responses
- **`tool_handler.py`**: Execute external tools and handle results
- **`ponder_handler.py`**: Perform deep thinking and analysis operations

### Memory Operations
- **`memorize_handler.py`**: Store information in graph memory with automatic secrets detection
- **`recall_handler.py`**: Retrieve information from graph memory with automatic decryption
- **`forget_handler.py`**: Remove information from graph memory with cleanup

### Task Management
- **`task_complete_handler.py`**: Mark tasks as completed and handle follow-up actions
- **`defer_handler.py`**: Defer decisions to wise authority when needed
- **`reject_handler.py`**: Handle rejection of inappropriate requests

## Key Features

### Automatic Secrets Management
All handlers automatically process secrets in action parameters:

```python
# In any handler
async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: Dict[str, Any]):
    # Auto-decapsulate secrets based on action type
    processed_result = await self._decapsulate_secrets_in_params(result, "speak")
    # Now proceed with decrypted parameters
```

### Service Registry Integration
Handlers automatically discover appropriate services:

```python
# Get best available communication service
comm_service = await self.get_communication_service(required_capabilities=["send_message"])

# Get memory service with fallback
memory_service = await self.get_memory_service()

# Get tool service for external operations
tool_service = await self.get_tool_service()
```

### Comprehensive Audit Logging
Every handler operation is logged:

```python
await self._audit_log(HandlerActionType.SPEAK, dispatch_context, outcome="success")
```

### Error Handling and Recovery
Centralized error management with proper failure modes:

```python
try:
    # Handler logic
    await perform_action()
except Exception as e:
    await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, e)
    # Proper failure state management
```

### Multi-Runtime Compatibility
Same handlers work across different runtimes:
- **Discord Runtime**: Uses Discord-specific communication services
- **CLI Runtime**: Uses console-based I/O services  
- **API Runtime**: Uses HTTP-based communication services

## Handler Lifecycle

1. **Initialization**: Handler receives ActionSelectionResult from DMA
2. **Secrets Processing**: Automatic decapsulation of any secrets in parameters
3. **Service Discovery**: Locate required services through registry
4. **Execution**: Perform the actual action
5. **Follow-up**: Create follow-up thoughts if needed
6. **Audit**: Log completion status and outcomes
7. **Cleanup**: Update thought status and handle failures

## Usage Examples

### Creating a Custom Handler
```python
class CustomHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: Dict[str, Any]):
        # Auto-process secrets
        processed_result = await self._decapsulate_secrets_in_params(result, "custom")
        
        # Validate parameters
        params = await self._validate_and_convert_params(processed_result.action_parameters, CustomParams)
        
        # Get required services
        comm_service = await self.get_communication_service()
        
        # Perform action with error handling
        try:
            await self.perform_custom_action(params)
            await self._audit_log(HandlerActionType.CUSTOM, dispatch_context, outcome="success")
        except Exception as e:
            await self._handle_error(HandlerActionType.CUSTOM, dispatch_context, thought.thought_id, e)
```

### Service Integration
```python
# Handlers automatically work with different service providers
# Discord runtime provides Discord-specific services
# CLI runtime provides console-specific services
# API runtime provides HTTP-specific services

# Service registry handles the complexity
service = await self.get_communication_service(required_capabilities=["send_message"])
success = await service.send_message(channel_id, content)
```

## Registry Integration

Handlers are registered through the `handler_registry.py`:

```python
def build_action_dispatcher(service_registry: ServiceRegistry, **kwargs) -> ActionDispatcher:
    handlers = {
        HandlerActionType.SPEAK: SpeakHandler(dependencies),
        HandlerActionType.MEMORIZE: MemorizeHandler(dependencies),
        HandlerActionType.RECALL: RecallHandler(dependencies),
        # ... other handlers
    }
    return ActionDispatcher(handlers)
```

## Error Handling Patterns

### Communication Failures
Handlers automatically trigger shutdown on critical communication failures:

```python
if not await self._send_notification(channel_id, content):
    # Critical failure - agent cannot communicate
    self.dependencies.request_graceful_shutdown("Communication failure")
```

### Service Unavailability
Graceful degradation when services are unavailable:

```python
memory_service = await self.get_memory_service()
if not memory_service:
    # Handle gracefully - maybe defer or use alternative
    return await self._create_deferral("Memory service unavailable")
```

### Parameter Validation
Robust parameter validation with helpful error messages:

```python
try:
    params = await self._validate_and_convert_params(raw_params, SpeakParams)
except ValidationError as e:
    await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, e)
    return
```

## Testing

Each handler includes comprehensive tests:
- Unit tests for individual handler logic
- Integration tests for service interaction
- Error condition testing
- Multi-runtime compatibility testing

Example test structure:
```python
@pytest.mark.asyncio
async def test_speak_handler_success():
    # Test successful message sending
    
async def test_speak_handler_communication_failure():
    # Test handling of communication failures
    
async def test_speak_handler_secrets_decapsulation():
    # Test automatic secrets processing
```

## Performance Considerations

- **Async Operations**: All handlers are fully asynchronous
- **Service Caching**: Service registry provides efficient service lookup
- **Resource Management**: Integration with resource monitoring and throttling
- **Circuit Breakers**: Built-in protection against service failures

## Security Features

- **Secrets Management**: Automatic detection and decapsulation of sensitive data
- **Audit Trails**: Complete logging of all operations for security compliance
- **Input Validation**: Robust parameter validation using Pydantic models
- **Service Isolation**: Clean separation between different service types

---

The action handlers provide the execution layer for the CIRIS Agent, ensuring reliable, secure, and monitored execution of all agent actions across different runtime environments.
