# Multi-Service Transaction Manager (Sinks)

The sinks module implements a sophisticated multi-service transaction manager that serves as the central action dispatcher and service orchestrator for the CIRIS agent. It provides unified routing of actions to appropriate services with priority-based selection, configurable selection strategies (FALLBACK/ROUND_ROBIN), circuit breaker patterns, and comprehensive security filtering.

## Service Selection & Transaction Management

The transaction manager handles service selection strategy by service type, not by adapter, implementing the sophisticated service registry capabilities:

- **Priority Groups**: Services organized in groups (0, 1, 2, etc.) with lower numbers tried first
- **Selection Strategies**: FALLBACK (redundancy) or ROUND_ROBIN (load balancing) per service type
- **Circuit Breaker Integration**: Automatic fault tolerance with health monitoring
- **Transaction Coordination**: Ensures data consistency across multi-service operations

## Architecture

### Core Components

#### Base Sink Infrastructure (`base_sink.py`)

Provides the foundational framework for all sink implementations with essential service orchestration capabilities.

```python
class BaseMultiServiceSink(ABC):
    """Abstract base class for multi-service action routing"""
    
    def __init__(
        self,
        service_registry: ServiceRegistry,
        max_queue_size: int = 1000,
        fallback_channel_id: Optional[str] = None
    ):
        self.service_registry = service_registry
        self.action_queue = asyncio.Queue(maxsize=max_queue_size)
        self.fallback_channel_id = fallback_channel_id
```

#### Key Features
- **Asynchronous Queue Processing**: Configurable queue management with overflow protection
- **Circuit Breaker Integration**: Built-in fault tolerance for service failures
- **Service Registry Integration**: Automatic service discovery and capability matching
- **Graceful Shutdown**: Coordinated shutdown with global event management
- **Abstract Interface**: Defines contracts for extensible sink implementations

#### Multi-Service Action Sink (`multi_service_sink.py`)

Primary implementation handling all CIRIS action types with comprehensive service routing.

```python
class MultiServiceActionSink(BaseMultiServiceSink):
    """Universal action dispatcher with multi-service routing"""
    
    # Service routing configuration
    ACTION_TO_SERVICE_MAP = {
        ActionType.SEND_MESSAGE: 'communication',
        ActionType.FETCH_MESSAGES: 'communication',
        ActionType.FETCH_GUIDANCE: 'wise_authority', 
        ActionType.SEND_DEFERRAL: 'wise_authority',
        ActionType.MEMORIZE: 'memory',
        ActionType.RECALL: 'memory',
        ActionType.FORGET: 'memory',
        ActionType.SEND_TOOL: 'tool',
        ActionType.FETCH_TOOL: 'tool',
        ActionType.GENERATE_RESPONSE: 'llm',
        ActionType.GENERATE_STRUCTURED: 'llm'
    }
```

## Service Routing Architecture

### Action Processing Flow

#### 1. Action Enqueueing
```python
async def enqueue_action(self, action: ActionMessage) -> None:
    """Add action to processing queue with overflow protection"""
    try:
        await self.action_queue.put(action)
    except asyncio.QueueFull:
        logger.error("Action queue is full, dropping action")
        # Implement backpressure or fallback strategies
```

#### 2. Service Resolution with Priority Management
```python
async def _get_service(self, service_type: str, capabilities: List[str] = None) -> Any:
    """Resolve service through registry with priority-based selection"""
    service = await self.service_registry.get_service(
        handler="MultiServiceSink",
        service_type=service_type,
        required_capabilities=capabilities or []
    )
    # Registry automatically handles:
    # - Priority group selection (0, 1, 2, etc.)
    # - Strategy application (FALLBACK/ROUND_ROBIN)
    # - Circuit breaker health checks
    # - Load balancing for ROUND_ROBIN services
    return service
```

#### 3. Action Execution
```python
async def _process_action(self, action: ActionMessage) -> Any:
    """Route and execute action through appropriate service"""
    service_type = self.ACTION_TO_SERVICE_MAP.get(action.action_type)
    service = await self._get_service(service_type)
    
    if service:
        return await self._execute_action_on_service(service, action)
    else:
        return await self._handle_fallback(action)
```

### Service Integration Patterns

#### Communication Services
Handle message routing across different platforms (Discord, CLI, API):

```python
async def send_message(self, channel_id: str, content: str) -> bool:
    """Send message through best available communication service"""
    action = ActionMessage(
        action_type=ActionType.SEND_MESSAGE,
        channel_id=channel_id,
        content=content
    )
    
    result = await self.enqueue_action(action)
    return result.success if result else False
```

#### Memory Services  
Manage graph-based memory operations with automatic secrets handling:

```python
async def memorize(self, content: str, metadata: Dict[str, Any] = None) -> bool:
    """Store information in memory with automatic secrets detection"""
    action = ActionMessage(
        action_type=ActionType.MEMORIZE,
        content=content,
        metadata=metadata or {}
    )
    
    return await self.enqueue_action(action)
```

#### LLM Services
Generate responses with integrated security filtering:

```python
async def generate_response(
    self, 
    prompt: str, 
    context: Dict[str, Any] = None
) -> Optional[str]:
    """Generate LLM response with automatic security filtering"""
    action = ActionMessage(
        action_type=ActionType.GENERATE_RESPONSE,
        prompt=prompt,
        context=context or {},
        enable_filtering=True  # Automatic security filtering
    )
    
    result = await self.enqueue_action(action)
    return result.response if result else None
```

#### Tool Services
Execute external tools with result management:

```python
async def execute_tool(
    self, 
    tool_name: str, 
    parameters: Dict[str, Any]
) -> Optional[Any]:
    """Execute external tool and return results"""
    action = ActionMessage(
        action_type=ActionType.SEND_TOOL,
        tool_name=tool_name,
        parameters=parameters
    )
    
    return await self.enqueue_action(action)
```

## Data Flow Management

### Observer Integration

Observers use sinks for seamless data routing:

```python
class CLIObserver:
    def __init__(self, service_registry: ServiceRegistry):
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=service_registry,
            max_queue_size=1000,
            fallback_channel_id=self.startup_channel_id
        )
    
    async def process_message(self, message: str):
        # Route through sink for proper service coordination
        await self.multi_service_sink.send_message(
            channel_id=self.channel_id,
            content=f"Processed: {message}"
        )
```

### Runtime Coordination

Runtime systems initialize sinks as central coordinators:

```python
class CIRISRuntime:
    async def _initialize_services(self):
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            max_queue_size=1000,
            fallback_channel_id=self.startup_channel_id
        )
        
        # Make sink available to all components
        await self.service_registry.register_service(
            handler="*",
            service_type="action_sink",
            provider=self.multi_service_sink,
            priority=Priority.HIGH
        )
```

## Security and Filtering Integration

### Integrated Security Pipeline

All data flows through the sink include automatic security measures:

#### Input Filtering
```python
async def _filter_input(self, content: str) -> str:
    """Apply input filtering before processing"""
    if self.adaptive_filter_service:
        filtered_content, refs = await self.adaptive_filter_service.filter_message(
            content=content,
            context_id=f"sink_{uuid.uuid4()}"
        )
        return filtered_content
    return content
```

#### Output Filtering  
```python
async def _filter_llm_response(self, response: str) -> str:
    """Apply security filtering to LLM responses"""
    # Automatic filtering integrated with circuit breakers
    filtered_response = await self.security_filter.filter_response(response)
    
    # Trigger circuit breaker on security violations
    if self.security_filter.is_threat_detected(response):
        await self._trigger_security_circuit_breaker()
    
    return filtered_response
```

#### Circuit Breaker Integration
```python
async def _handle_security_violation(self, action: ActionMessage):
    """Handle security violations with circuit breaker patterns"""
    # Open circuit breaker for problematic services
    await self.circuit_breaker.open_circuit("security_violation")
    
    # Log security event
    await self.audit_service.log_security_event(
        event_type="sink_security_violation",
        action_type=action.action_type,
        details={"action_id": action.id}
    )
```

## Reliability and Fault Tolerance

### Circuit Breaker Patterns

#### Service Health Monitoring
```python
class ServiceHealthManager:
    async def monitor_service_health(self, service_type: str):
        """Continuous health monitoring for services"""
        service = await self._get_service(service_type)
        
        if hasattr(service, 'is_healthy'):
            healthy = await service.is_healthy()
            if not healthy:
                await self._trigger_circuit_breaker(service_type)
```

#### Automatic Fallback
```python
async def _handle_fallback(self, action: ActionMessage) -> Any:
    """Implement fallback strategies for failed actions"""
    # Try alternative services
    fallback_services = await self._get_fallback_services(action.action_type)
    
    for service in fallback_services:
        try:
            return await self._execute_action_on_service(service, action)
        except Exception as e:
            logger.warning(f"Fallback service failed: {e}")
            continue
    
    # Ultimate fallback - log and return safe response
    await self._log_action_failure(action)
    return self._create_safe_response(action)
```

### Queue Management

#### Overflow Protection
```python
async def _handle_queue_overflow(self, action: ActionMessage):
    """Handle queue overflow with priority-based dropping"""
    if action.priority == Priority.CRITICAL:
        # Make room for critical actions
        await self._drop_lowest_priority_action()
        await self.action_queue.put(action)
    else:
        # Log dropped action for monitoring
        await self._log_dropped_action(action)
```

#### Processing Optimization
```python
async def _process_queue_batch(self, batch_size: int = 10):
    """Process actions in batches for efficiency"""
    batch = []
    for _ in range(batch_size):
        if not self.action_queue.empty():
            action = await self.action_queue.get()
            batch.append(action)
    
    # Process batch concurrently
    if batch:
        await asyncio.gather(
            *[self._process_action(action) for action in batch],
            return_exceptions=True
        )
```

## Convenience Methods

### Synchronous Wrappers

For compatibility with synchronous code:

```python
def send_message_sync(self, channel_id: str, content: str) -> bool:
    """Synchronous wrapper for message sending"""
    return asyncio.run(self.send_message(channel_id, content))

def memorize_sync(self, content: str, metadata: Dict[str, Any] = None) -> bool:
    """Synchronous wrapper for memory operations"""
    return asyncio.run(self.memorize(content, metadata))

def execute_tool_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Synchronous wrapper for tool execution"""
    return asyncio.run(self.execute_tool(tool_name, parameters))
```

### High-Level Operations

```python
async def process_user_request(
    self, 
    user_message: str, 
    channel_id: str,
    context: Dict[str, Any] = None
) -> str:
    """High-level user request processing"""
    
    # 1. Filter input
    filtered_message = await self._filter_input(user_message)
    
    # 2. Recall relevant context
    context_data = await self.recall(f"context for {filtered_message}")
    
    # 3. Generate response
    response = await self.generate_response(
        prompt=filtered_message,
        context={**(context or {}), **context_data}
    )
    
    # 4. Send response
    await self.send_message(channel_id, response)
    
    return response
```

## Performance Optimization

### Asynchronous Processing
- **Concurrent Execution**: Multiple actions processed simultaneously
- **Queue-Based Buffering**: Smooth handling of burst traffic
- **Batch Processing**: Efficient bulk operation handling

### Resource Management
- **Connection Pooling**: Reused service connections
- **Memory Optimization**: Bounded queue sizes prevent memory leaks
- **Lazy Loading**: Services loaded only when needed

### Monitoring Integration
```python
async def _record_performance_metrics(self, action: ActionMessage, duration: float):
    """Record performance metrics for monitoring"""
    await self.telemetry_service.record_metric(
        metric_name="sink_action_duration",
        value=duration,
        tags={
            "action_type": action.action_type,
            "service_type": self.ACTION_TO_SERVICE_MAP.get(action.action_type)
        }
    )
```

## Usage Examples

### Basic Sink Usage
```python
# Initialize sink
sink = MultiServiceActionSink(
    service_registry=registry,
    max_queue_size=1000,
    fallback_channel_id="default_channel"
)

# Send message
success = await sink.send_message("channel_123", "Hello, world!")

# Store memory
await sink.memorize("Important information", {"priority": "high"})

# Execute tool
result = await sink.execute_tool("web_search", {"query": "CIRIS agent"})
```

### Advanced Integration
```python
class AgentController:
    def __init__(self, service_registry: ServiceRegistry):
        self.sink = MultiServiceActionSink(service_registry)
    
    async def handle_user_interaction(self, user_input: str, channel_id: str):
        # Multi-step processing through sink
        context = await self.sink.recall("user_preferences")
        response = await self.sink.generate_response(user_input, context)
        await self.sink.send_message(channel_id, response)
        await self.sink.memorize(f"User said: {user_input}")
```

## Service Strategy Management Examples

### Load-Balanced LLM Pool Configuration
```python
# Configure multiple LLM services with different strategies
class LLMServiceManager:
    async def setup_llm_services(self):
        # Primary production LLM (Group 0 - FALLBACK)
        await self.service_registry.register(
            handler="MultiServiceSink",
            service_type="llm",
            provider=openai_primary,
            priority=Priority.CRITICAL,
            priority_group=0,
            strategy=SelectionStrategy.FALLBACK
        )
        
        # Load-balanced backup pool (Group 1 - ROUND_ROBIN)
        backup_llms = [anthropic_claude, openai_backup, together_ai]
        for llm in backup_llms:
            await self.service_registry.register(
                handler="MultiServiceSink", 
                service_type="llm",
                provider=llm,
                priority=Priority.HIGH,
                priority_group=1,
                strategy=SelectionStrategy.ROUND_ROBIN
            )
        
        # Local fallback (Group 2 - FALLBACK)
        await self.service_registry.register(
            handler="MultiServiceSink",
            service_type="llm",
            provider=local_llm,
            priority=Priority.FALLBACK,
            priority_group=2,
            strategy=SelectionStrategy.FALLBACK
        )
```

### Multi-Service Transaction Example
```python
async def process_complex_user_request(self, user_input: str, channel_id: str):
    """Handle multi-step operation with transaction-like coordination"""
    
    # Step 1: Memory recall (uses configured memory service strategy)
    context = await self.sink.recall(f"context for user {channel_id}")
    
    # Step 2: LLM generation (uses priority group LLM selection)
    response = await self.sink.generate_response(
        prompt=user_input,
        context=context
    )
    
    # Step 3: Memory storage (transactional consistency)
    await self.sink.memorize(f"User: {user_input}\nResponse: {response}")
    
    # Step 4: Communication (uses communication service priority)
    await self.sink.send_message(channel_id, response)
    
    # All steps automatically benefit from:
    # - Service health monitoring
    # - Circuit breaker protection  
    # - Priority-based selection
    # - Load balancing where configured
```

### Runtime Service Management Integration
```python
# The transaction manager automatically adapts to runtime service changes
async def handle_service_reconfiguration(self):
    """Automatically adapt to runtime service priority changes"""
    
    # Service priorities can be updated via API without restart
    # curl -X PUT /v1/runtime/services/OpenAIProvider_123/priority \
    #   -d '{"priority": "HIGH", "priority_group": 1, "strategy": "ROUND_ROBIN"}'
    
    # Transaction manager automatically uses new configuration
    response = await self.sink.generate_response("test prompt")
    # Will now use updated priority/strategy settings
```

---

The Multi-Service Transaction Manager provides a robust, secure, and scalable foundation for coordinated multi-service operations throughout the CIRIS architecture. It implements service-level selection strategy management (not adapter-level), enabling sophisticated priority-based routing, load balancing, and fault tolerance while maintaining strong consistency guarantees across distributed service operations.