# Services Module

The services module provides essential standalone service implementations that support core CIRIS agent functionality. These services integrate with the multi-service architecture through the service registry and sink patterns, providing specialized capabilities for adaptive filtering, configuration management, and transaction orchestration.

## Architecture Overview

### Service Integration Pattern

All services in this module inherit from the base `Service` class and integrate with the CIRIS multi-service architecture:

```python
from ciris_engine.adapters.base import Service
from ciris_engine.registries.base import ServiceRegistry, Priority

class ExampleService(Service):
    async def start(self):
        await super().start()
        # Service initialization
    
    async def stop(self):
        await super().stop()
        # Cleanup logic
```

### Core Service Components

The services module contains three primary service implementations:

1. **Adaptive Filter Service** - Intelligent message filtering with ML-based priority detection
2. **Agent Configuration Service** - Configuration management through graph memory (agent-initiated)
3. **Multi-Service Transaction Orchestrator** - Coordinated multi-service operations

## Service Implementations

### Adaptive Filter Service (`adaptive_filter_service.py`)

Provides sophisticated message filtering capabilities with machine learning-based priority detection and user trust tracking.

#### Core Features

- **Intelligent Priority Detection**: Automatically classifies messages by urgency and importance
- **User Trust Tracking**: Maintains trust profiles for users based on interaction history  
- **Graph Memory Integration**: Persists filter configuration and learning data
- **Pattern-Based Updates**: Agent can update filtering rules based on discovered patterns
- **Multi-Adapter Support**: Works with CLI, Discord, and API adapters

#### Configuration Structure

```python
from ciris_engine.schemas.filter_schemas_v1 import AdaptiveFilterConfig

config = AdaptiveFilterConfig(
    enabled=True,
    learning_rate=0.1,
    trust_decay_hours=24,
    max_trust_score=100,
    priority_keywords={
        FilterPriority.CRITICAL: ["urgent", "emergency", "help"],
        FilterPriority.HIGH: ["important", "asap", "priority"],
        FilterPriority.MEDIUM: ["question", "request", "please"]
    },
    spam_patterns=[
        r"\b(click here|act now|limited time)\b",
        r"\b(free money|easy cash|guaranteed)\b"
    ]
)
```

#### Usage Examples

```python
# Initialize service
filter_service = AdaptiveFilterService(
    memory_service=memory_service,
    llm_service=llm_service  # Optional for enhanced detection
)

# Start service (loads configuration from graph memory)
await filter_service.start()

# Filter incoming message
filter_result = await filter_service.filter_message(
    message=incoming_message,
    adapter_type="discord"
)

if filter_result.should_process:
    # Process high-priority message immediately
    if filter_result.priority == FilterPriority.CRITICAL:
        await priority_handler.handle(message)
    else:
        await normal_handler.handle(message)
else:
    # Message filtered out (spam, malicious, etc.)
    logger.info(f"Filtered message: {filter_result.reasoning}")
```

#### Filter Result Processing

```python
from ciris_engine.schemas.filter_schemas_v1 import FilterResult, FilterPriority

# Example filter result
result = FilterResult(
    message_id="msg_123",
    priority=FilterPriority.HIGH,
    triggered_filters=["urgency_detector", "trust_booster"],
    should_process=True,
    reasoning="High-priority message from trusted user",
    confidence=0.87,
    context_hints={
        "user_trust_score": 85,
        "urgency_indicators": ["urgent", "help"],
        "threat_level": "none"
    }
)
```

#### Trust Profile Management

```python
# Update user trust based on interaction outcomes
await filter_service.update_user_trust(
    user_id="user_123",
    interaction_outcome="positive",  # positive, negative, neutral
    context={"message_type": "question", "resolution": "helpful"}
)

# Get current trust profile
trust_profile = await filter_service.get_user_trust("user_123")
print(f"Trust score: {trust_profile.trust_score}/100")
print(f"Interaction count: {trust_profile.interaction_count}")
```

### Agent Configuration Service (`agent_config_service.py`)

Manages agent self-configuration through graph memory with support for LOCAL vs IDENTITY scope handling and Wise Authority approval workflows.

#### Scope-Based Configuration

The service handles two primary configuration scopes:

- **LOCAL Scope**: Runtime settings that can be changed immediately
- **IDENTITY Scope**: Core identity settings requiring WA approval

```python
from ciris_engine.schemas.graph_schemas_v1 import ConfigNodeType, GraphScope

# Get local configuration (immediate access)
local_config = await config_service.get_config(
    config_type=ConfigNodeType.FILTER_CONFIG,
    scope=GraphScope.LOCAL
)

# Request identity configuration change (requires WA approval)
identity_update = await config_service.request_identity_update(
    config_type=ConfigNodeType.AGENT_PROFILE,
    changes={"personality_traits": ["helpful", "analytical", "cautious"]},
    justification="Adjusting personality for better user interactions"
)
```

#### Configuration Management Workflow

```python
class AgentConfigService(Service):
    async def update_config(
        self,
        config_type: ConfigNodeType,
        config_data: Dict[str, Any],
        scope: GraphScope = GraphScope.LOCAL
    ) -> bool:
        """Update configuration based on scope (identity changes require WA approval)"""
        
        if scope == GraphScope.IDENTITY:
            # Identity changes require WA approval
            return await self._request_wa_approval(config_type, config_data)
        else:
            # Local changes can be applied immediately
            return await self._apply_local_config(config_type, config_data)
    
    async def _request_wa_approval(self, config_type: ConfigNodeType, changes: Dict[str, Any]) -> bool:
        """Request Wise Authority approval for identity changes"""
        approval_request = {
            "request_id": f"identity_update_{datetime.now().isoformat()}",
            "config_type": config_type.value,
            "proposed_changes": changes,
            "current_config": await self._get_current_identity_config(config_type),
            "impact_assessment": await self._assess_change_impact(config_type, changes)
        }
        
        if self.wa_service:
            return await self.wa_service.request_approval(approval_request)
        else:
            logger.warning("No WA service available for identity update approval")
            return False
```

#### Configuration Examples

```python
# Agent decides to update filter based on discovered insights
# (Not automatic - agent reads insights from DREAM state pattern detection)
filter_config = await config_service.get_config(ConfigNodeType.FILTER_CONFIG)
filter_config["spam_threshold"] = 0.85  # Agent chooses to increase sensitivity

await config_service.update_config(
    ConfigNodeType.FILTER_CONFIG,
    filter_config,
    scope=GraphScope.LOCAL
)

# Request personality adjustment (requires WA approval)
identity_changes = {
    "personality_traits": ["helpful", "analytical", "security-conscious"],
    "response_style": "formal",
    "expertise_areas": ["cybersecurity", "data analysis"]
}

approval_pending = await config_service.update_config(
    ConfigNodeType.AGENT_PROFILE,
    identity_changes,
    scope=GraphScope.IDENTITY
)
```

### Multi-Service Transaction Orchestrator (`multi_service_transaction_orchestrator.py`)

Coordinates complex multi-service operations through the MultiServiceActionSink, ensuring atomic transactions and proper rollback handling.

#### Transaction Coordination

The orchestrator manages sequences of actions across multiple services as atomic units:

```python
from ciris_engine.schemas.service_actions_v1 import ActionMessage, ActionType

# Define a complex transaction
transaction_actions = [
    ActionMessage(
        action_type=ActionType.MEMORIZE,
        content="User requested data analysis",
        metadata={"priority": "high", "category": "analysis"}
    ),
    ActionMessage(
        action_type=ActionType.SEND_TOOL,
        tool_name="data_analyzer",
        parameters={"dataset": "user_data.csv", "analysis_type": "statistical"}
    ),
    ActionMessage(
        action_type=ActionType.SEND_MESSAGE,
        channel_id="user_channel",
        content="Analysis complete. Preparing results..."
    )
]

# Execute as atomic transaction
tx_id = "analysis_workflow_001"
await orchestrator.orchestrate(tx_id, transaction_actions)
```

#### Rollback and Error Handling

```python
class MultiServiceTransactionOrchestrator(Service):
    async def orchestrate(self, tx_id: str, actions: List[ActionMessage]) -> None:
        """Execute actions as atomic transaction with rollback on failure"""
        completed_actions = []
        
        try:
            for action in actions:
                # Execute action through sink
                result = await self.sink.enqueue_action(action)
                completed_actions.append((action, result))
                
                # Update transaction status
                self.transactions[tx_id] = {
                    "status": "in_progress",
                    "completed": len(completed_actions),
                    "total": len(actions)
                }
            
            # Mark transaction as successful
            self.transactions[tx_id]["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Transaction {tx_id} failed: {e}")
            
            # Rollback completed actions
            await self.rollback(tx_id, completed_actions)
            
            self.transactions[tx_id] = {
                "status": "failed",
                "error": str(e),
                "rollback_completed": True
            }
            raise
    
    async def rollback(self, tx_id: str, completed_actions: List[Tuple[ActionMessage, Any]]) -> None:
        """Rollback completed actions in reverse order"""
        for action, result in reversed(completed_actions):
            try:
                rollback_action = self._create_rollback_action(action, result)
                if rollback_action:
                    await self.sink.enqueue_action(rollback_action)
            except Exception as e:
                logger.error(f"Rollback failed for action {action.action_type}: {e}")
```

#### Transaction Monitoring

```python
# Monitor transaction status
tx_status = orchestrator.get_transaction_status("analysis_workflow_001")

if tx_status["status"] == "completed":
    print("Transaction completed successfully")
elif tx_status["status"] == "failed":
    print(f"Transaction failed: {tx_status['error']}")
    if tx_status.get("rollback_completed"):
        print("Rollback completed successfully")
elif tx_status["status"] == "in_progress":
    progress = tx_status["completed"] / tx_status["total"] * 100
    print(f"Transaction progress: {progress:.1f}%")
```

## Service Registry Integration

### Registration Patterns

Services integrate with the CIRIS service registry for discovery and dependency injection:

```python
from ciris_engine.registries.base import ServiceRegistry, Priority

# Register services in runtime initialization
service_registry = ServiceRegistry()

# Register adaptive filter service
filter_service = AdaptiveFilterService(memory_service, llm_service)
await filter_service.start()

service_registry.register_global(
    service_type="filter",
    provider=filter_service,
    priority=Priority.HIGH,
    capabilities=["filter_message", "update_user_trust", "get_filter_stats"]
)

# Register configuration service  
config_service = AgentConfigService(memory_service, wa_service, filter_service)
await config_service.start()

service_registry.register_global(
    service_type="config",
    provider=config_service,
    priority=Priority.HIGH,
    capabilities=["get_config", "update_config", "request_identity_update"]
)

# Register transaction orchestrator
orchestrator = MultiServiceTransactionOrchestrator(service_registry, multi_service_sink)
await orchestrator.start()

service_registry.register_global(
    service_type="transaction_orchestrator",
    provider=orchestrator,
    priority=Priority.MEDIUM,
    capabilities=["orchestrate", "rollback", "get_transaction_status"]
)
```

### Service Discovery and Usage

```python
# Components can discover and use services through registry
class ExampleHandler:
    def __init__(self, service_registry: ServiceRegistry):
        self.registry = service_registry
    
    async def process_message(self, message: IncomingMessage):
        # Get filter service
        filter_service = await self.registry.get_service(
            handler="ExampleHandler",
            service_type="filter",
            required_capabilities=["filter_message"]
        )
        
        if filter_service:
            # Apply filtering
            filter_result = await filter_service.filter_message(message)
            
            if filter_result.should_process:
                # Get config service for processing parameters
                config_service = await self.registry.get_service(
                    handler="ExampleHandler",
                    service_type="config",
                    required_capabilities=["get_config"]
                )
                
                if config_service:
                    processing_config = await config_service.get_config(
                        ConfigNodeType.PROCESSING_CONFIG
                    )
                    
                    # Process message with configuration
                    await self._process_with_config(message, processing_config)
```

## Integration with Multi-Service Sink

### Sink-Based Service Coordination

Services integrate with the multi-service sink for unified action routing:

```python
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

class ServiceIntegratedHandler:
    def __init__(self, service_registry: ServiceRegistry, multi_service_sink: MultiServiceActionSink):
        self.registry = service_registry
        self.sink = multi_service_sink
    
    async def handle_complex_workflow(self, user_request: str):
        # Step 1: Filter and prioritize request
        filter_service = await self.registry.get_service("Handler", "filter")
        filter_result = await filter_service.filter_message(user_request)
        
        if filter_result.priority == FilterPriority.HIGH:
            # Step 2: Create transaction for high-priority workflow
            orchestrator = await self.registry.get_service("Handler", "transaction_orchestrator")
            
            workflow_actions = [
                # Memory operation
                ActionMessage(
                    action_type=ActionType.MEMORIZE,
                    content=f"High priority request: {user_request}",
                    metadata={"priority": "high", "user_trust": filter_result.context_hints.get("user_trust_score")}
                ),
                # Tool execution
                ActionMessage(
                    action_type=ActionType.SEND_TOOL,
                    tool_name="priority_processor",
                    parameters={"request": user_request, "urgency": "high"}
                ),
                # Response generation
                ActionMessage(
                    action_type=ActionType.GENERATE_RESPONSE,
                    prompt=f"Respond to high-priority request: {user_request}",
                    context={"user_priority": "high", "processing_mode": "immediate"}
                )
            ]
            
            # Execute as coordinated transaction
            await orchestrator.orchestrate(f"priority_workflow_{datetime.now().timestamp()}", workflow_actions)
```

## Performance and Monitoring

### Service Health Monitoring

```python
# Health check integration
class ServiceHealthMonitor:
    def __init__(self, service_registry: ServiceRegistry):
        self.registry = service_registry
    
    async def check_service_health(self) -> Dict[str, Any]:
        health_report = {}
        
        # Check filter service health
        filter_service = await self.registry.get_service("Monitor", "filter")
        if filter_service and hasattr(filter_service, 'get_health_status'):
            health_report["filter"] = await filter_service.get_health_status()
        
        # Check config service health  
        config_service = await self.registry.get_service("Monitor", "config")
        if config_service and hasattr(config_service, 'is_healthy'):
            health_report["config"] = await config_service.is_healthy()
        
        # Check orchestrator health
        orchestrator = await self.registry.get_service("Monitor", "transaction_orchestrator")
        if orchestrator:
            health_report["orchestrator"] = {
                "active_transactions": len(orchestrator.transactions),
                "failed_transactions": sum(
                    1 for tx in orchestrator.transactions.values() 
                    if tx.get("status") == "failed"
                )
            }
        
        return health_report
```

### Performance Optimization

```python
# Service performance optimization patterns
class OptimizedServiceUsage:
    def __init__(self, service_registry: ServiceRegistry):
        self.registry = service_registry
        self._service_cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def get_cached_service(self, service_type: str, handler: str = "Default"):
        """Get service with caching to reduce registry lookups"""
        cache_key = f"{handler}:{service_type}"
        
        if cache_key in self._service_cache:
            cached_entry = self._service_cache[cache_key]
            if (datetime.now() - cached_entry["timestamp"]).seconds < self._cache_ttl:
                return cached_entry["service"]
        
        # Cache miss - fetch from registry
        service = await self.registry.get_service(handler, service_type)
        self._service_cache[cache_key] = {
            "service": service,
            "timestamp": datetime.now()
        }
        
        return service
```

## Troubleshooting

### Common Issues and Solutions

#### Service Initialization Failures

```python
# Robust service initialization with fallbacks
async def initialize_services_with_fallbacks(memory_service, llm_service=None):
    services = {}
    
    try:
        # Initialize filter service
        filter_service = AdaptiveFilterService(memory_service, llm_service)
        await filter_service.start()
        services["filter"] = filter_service
        logger.info("Filter service initialized successfully")
    except Exception as e:
        logger.error(f"Filter service initialization failed: {e}")
        # Create fallback filter service with basic functionality
        services["filter"] = BasicFilterService()
    
    try:
        # Initialize config service
        config_service = AgentConfigService(memory_service)
        await config_service.start()
        services["config"] = config_service
        logger.info("Config service initialized successfully")
    except Exception as e:
        logger.error(f"Config service initialization failed: {e}")
        # Use static configuration as fallback
        services["config"] = StaticConfigService()
    
    return services
```

#### Memory Service Integration Issues

```python
# Handle memory service connection issues
class ResilientMemoryIntegration:
    def __init__(self, memory_service):
        self.memory = memory_service
        self._connection_retries = 3
        self._retry_delay = 1.0
    
    async def safe_memory_operation(self, operation_func, *args, **kwargs):
        """Execute memory operation with retry logic"""
        for attempt in range(self._connection_retries):
            try:
                return await operation_func(*args, **kwargs)
            except ConnectionError as e:
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Memory operation failed (attempt {attempt + 1}), retrying: {e}")
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Memory operation failed after {self._connection_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in memory operation: {e}")
                raise
```

#### Configuration Validation

```python
# Validate service configurations
def validate_service_config(config: Dict[str, Any], service_type: str) -> bool:
    """Validate service configuration before initialization"""
    
    required_fields = {
        "filter": ["enabled", "learning_rate", "priority_keywords"],
        "config": ["cache_ttl_minutes", "scope_map"],
        "orchestrator": ["max_concurrent_transactions", "rollback_timeout"]
    }
    
    if service_type not in required_fields:
        logger.warning(f"Unknown service type for validation: {service_type}")
        return True
    
    missing_fields = []
    for field in required_fields[service_type]:
        if field not in config:
            missing_fields.append(field)
    
    if missing_fields:
        logger.error(f"Missing required configuration fields for {service_type}: {missing_fields}")
        return False
    
    return True
```

---

The services module provides essential infrastructure services that enhance the CIRIS agent's capabilities through intelligent filtering, flexible configuration management, and reliable transaction coordination. These services integrate seamlessly with the multi-service architecture while maintaining clear separation of concerns and robust error handling.
