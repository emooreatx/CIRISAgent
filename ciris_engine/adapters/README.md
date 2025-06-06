# Adapters

The adapters module provides platform-specific implementations and service interfaces for the CIRIS engine. Adapters enable CIRIS to operate across different environments (CLI, Discord, API) while maintaining consistent service interfaces and advanced features like secrets management, adaptive filtering, and cryptographic audit trails.

## Architecture

### Base Service Framework (`base.py`)
All adapters inherit from the `Service` base class, providing:

- **Retry Logic**: Exponential backoff with jitter (±25% by default)
- **Operation-Specific Policies**: Configurable retry behavior per operation type
- **Health Monitoring**: Built-in status reporting and health checks
- **Lifecycle Management**: Graceful start/stop with resource cleanup
- **Exception Classification**: Retryable vs non-retryable error handling

```python
class Service(ABC):
    async def retry_with_backoff(self, operation, *args, **kwargs):
        # Sophisticated retry logic with exponential backoff
```

## Communication Adapters

### CLI Adapter (`cli/`)

#### Components
- **`CLIAdapter`**: Core communication service with message I/O
- **`CLIObserver`**: Advanced message processing with filtering and secrets
- **`CLIToolService`**: Local filesystem and shell command execution
- **`CLIWiseAuthorityService`**: Interactive guidance and deferral system

#### Key Features
- **Adaptive Filtering**: Priority-based message processing (critical/high vs medium/low)
- **Secrets Integration**: Automatic detection, encryption, and decryption
- **Context Memory**: Recent message history for conversation continuity
- **Local Tools**: File operations, shell commands, environment access
- **Interactive WA**: Real-time guidance through multi-service sink routing

```python
# CLI Observer with secrets processing
async def _process_message_secrets(self, msg: CLIMessage) -> CLIMessage:
    # Automatic secrets detection and secure replacement
    if self.secrets_service:
        processed_content = await self.secrets_service.encapsulate_secrets(msg.content)
        return msg._replace(content=processed_content)
```

### Discord Adapter (`discord/`)

#### Components
- **`DiscordAdapter`**: Full Discord.py integration with retry logic
- **`DiscordObserver`**: Message processing with secrets and filtering
- **`DiscordRuntime`**: Complete runtime coordination
- **`DiscordToolService`**: Discord-specific tools and operations

#### Advanced Capabilities
- **Multi-Protocol Service**: Implements `CommunicationService`, `WiseAuthorityService`, `ToolService`
- **Channel Management**: Guidance and deferral channel routing
- **Rate Limiting**: Built-in Discord API rate limit handling
- **Message Pagination**: Efficient message history retrieval
- **Connection Resilience**: Automatic reconnection with exponential backoff

#### Retry Configuration
```python
retry_config = {
    "http_operations": {
        "max_retries": 3,
        "retryable_exceptions": [HTTPException, ConnectionClosed, TimeoutError],
        "non_retryable": [Forbidden, NotFound, InvalidData]
    }
}
```

### API Adapter (`api/`)

#### Components
- **`APIAdapter`**: HTTP API communication with multi-service support
- **`APIObserver`**: RESTful message processing with secrets integration

#### Features
- **RESTful Patterns**: Standard HTTP API communication
- **Channel-Based Storage**: In-memory message organization
- **Tool Framework**: API-based tool execution
- **Memory Integration**: Graph memory operations via HTTP
- **Correlation Tracking**: Request/response correlation for debugging

## Service Adapters

### Local Graph Memory (`local_graph_memory/`)

#### Advanced Memory Service
- **SQLite Backend**: Efficient graph storage with full-text search
- **Automatic Secrets Processing**: Seamless encryption during memorization
- **Context-Aware Decryption**: Smart secret revelation during recall
- **WA Authorization**: Secure graph updates through wise authority
- **Reference Tracking**: Metadata for secret lifecycle management

#### Secrets Integration
```python
async def _process_secrets_for_memorize(self, node: GraphNode) -> GraphNode:
    # Automatically detect and encrypt secrets in node attributes
    processed_attributes = {}
    for key, value in node.attributes.items():
        if isinstance(value, str):
            processed_value = await self.secrets_service.encapsulate_secrets(value)
            processed_attributes[key] = processed_value
    return node._replace(attributes=processed_attributes)
```

#### Key Operations
- **Smart Recall**: Context-based secret decryption
- **Identity Management**: Environment and user graph separation
- **Cleanup**: Automatic secret reference removal on node deletion

### OpenAI Compatible LLM (`openai_compatible_llm.py`)

#### Comprehensive LLM Client
- **Async OpenAI Integration**: High-performance async client
- **Structured Parsing**: Instructor integration for Pydantic models
- **Token Tracking**: Telemetry integration for usage monitoring
- **Retry Policies**: API-specific error handling and backoff
- **Flexible Configuration**: Custom base URLs and authentication

#### Features
```python
async def generate_structured_response(self, model: str, messages: List[Dict], 
                                     response_model: Type[BaseModel]) -> BaseModel:
    # Structured response generation with automatic retry and token tracking
    try:
        response = await self.instructor_client.chat.completions.create(
            model=model, messages=messages, response_model=response_model
        )
        await self._record_token_usage(response)
        return response
    except Exception as e:
        await self._handle_llm_error(e)
```

### CIRISNode Client (`cirisnode_client.py`)

#### External Service Integration
- **Benchmark Execution**: SimpleBench and HE-300 test suites
- **Chaos Testing**: Controlled failure injection scenarios
- **WA Service Integration**: External wise authority consultation
- **Event Logging**: Comprehensive audit trail integration
- **HTTP Retry Logic**: Robust error handling for network operations

### Tool Registry (`tool_registry.py`)

#### Centralized Tool Management
- **Schema Validation**: Pydantic-based argument validation
- **Handler Mapping**: Function-based tool execution
- **Dynamic Registration**: Runtime tool addition and removal
- **Capability Querying**: Tool availability and capability discovery

## Audit Services

### Local Audit Log (`local_audit_log.py`)

#### File-Based Audit Trail
- **JSONL Format**: Structured logging with buffering
- **Log Rotation**: Automatic rotation by file size
- **Retry Logic**: Robust file operation handling
- **Correlation Tracking**: Event correlation across operations
- **Guardrail Logging**: Security event recording

### Signed Audit Service (`signed_audit_service.py`)

#### Cryptographic Audit Trail
- **Hash Chain Integrity**: Tamper-evident audit logging
- **Digital Signatures**: RSA-based non-repudiation
- **Dual Storage**: JSONL + signed SQLite database
- **Key Management**: Secure key rotation capabilities
- **Verification**: Comprehensive integrity checking

#### Security Features
```python
class SignedAuditService:
    async def log_action(self, action_type: str, context: Dict[str, Any], outcome: str = None):
        # Create tamper-evident audit entry with digital signature
        entry = self._create_audit_entry(action_type, context, outcome)
        chained_entry = await self.hash_chain.add_entry(entry)
        signed_entry = await self.signature_manager.sign_entry(chained_entry)
        await self._store_signed_entry(signed_entry)
```

## Integration Features

### Comprehensive Secrets Management

#### Automatic Processing
All adapters include automatic secrets processing:
- **Detection**: Pattern-based secret identification in messages and data
- **Encryption**: AES-256-GCM encryption with per-secret keys
- **Storage**: Secure storage with UUID reference replacement
- **Decryption**: Context-aware revelation based on operation type
- **Cleanup**: Automatic reference removal and key disposal

#### Cross-Adapter Consistency
```python
# Unified secrets processing across all adapters
async def _process_message_secrets(self, message):
    if self.secrets_service:
        processed_content = await self.secrets_service.encapsulate_secrets(
            message.content,
            context={"operation": "message_processing", "channel": message.channel_id}
        )
        return message._replace(content=processed_content)
```

### Adaptive Filtering System

#### Priority-Based Processing
- **Critical Priority**: Direct mentions, DMs, emergency keywords
- **High Priority**: Questions, help requests, known users
- **Medium Priority**: General conversation, regular activity
- **Low Priority**: Spam indicators, untrusted users

#### Filter Integration
```python
# Observer filtering pattern
filter_result = await self._apply_message_filtering(msg)
if filter_result.priority.value in ['critical', 'high']:
    await self._handle_priority_observation(msg, filter_result)
else:
    await self._handle_passive_observation(msg)
```

### Service Registry Integration

#### Dynamic Service Discovery
- **Capability-Based Selection**: Services selected by required features
- **Runtime Adaptation**: Dynamic service resolution and fallback
- **Health Monitoring**: Continuous service availability tracking
- **Multi-Service Support**: Single adapters implementing multiple service types

## Error Handling and Reliability

### Sophisticated Retry Logic

#### Service-Specific Policies
```python
retry_policies = {
    "http_operations": {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 60.0,
        "retryable_exceptions": [HTTPException, TimeoutError],
        "non_retryable": [Forbidden, InvalidData]
    },
    "file_operations": {
        "max_retries": 5,
        "base_delay": 0.5,
        "retryable_exceptions": [OSError, PermissionError]
    }
}
```

#### Features
- **Exponential Backoff**: Configurable backoff strategies
- **Jitter**: Random variation to prevent thundering herd
- **Exception Classification**: Smart handling of different error types
- **Operation Context**: Retry behavior adapted to operation type

### Circuit Breaker Integration
- **Service Protection**: Automatic service protection under load
- **Graceful Degradation**: Fallback mechanisms for service failures
- **Recovery**: Automatic service recovery detection
- **Monitoring**: Integration with telemetry for health tracking

## Configuration and Usage

### Runtime Mode Selection
```python
# Adapters selected based on runtime configuration
python main.py --mode cli        # CLI adapter stack
python main.py --mode discord    # Discord adapter stack
python main.py --mode api        # API adapter stack
```

### Service Registration Pattern
```python
# Services automatically registered based on runtime
await service_registry.register_service("communication", discord_adapter)
await service_registry.register_service("memory", local_graph_memory)
await service_registry.register_service("audit", signed_audit_service)
await service_registry.register_service("wise_authority", discord_adapter)
```

### Environment Configuration
- **Channel Routing**: Environment variable-based channel selection
- **Service Discovery**: Dynamic service capability negotiation
- **Profile Loading**: Configuration-driven adapter selection
- **Secrets Management**: Configurable encryption and detection patterns

## Testing and Validation

### Comprehensive Test Coverage
- **Unit Tests**: Individual adapter functionality
- **Integration Tests**: Cross-adapter service interaction
- **Live Tests**: Real-world Discord and API integration
- **Performance Tests**: Load testing and resource monitoring

### Test Categories
- Service registry integration validation
- Secrets management end-to-end testing
- Audit trail integrity verification
- Error handling and retry logic validation
- Multi-runtime compatibility testing

## Performance Considerations

### Optimization Features
- **Async Operations**: Full asynchronous implementation
- **Connection Pooling**: Efficient resource management
- **Caching**: Service discovery and configuration caching
- **Batching**: Efficient bulk operations where applicable
- **Resource Monitoring**: Integration with telemetry system

### Scalability
- **Horizontal Scaling**: Support for multiple adapter instances
- **Load Balancing**: Service registry-based load distribution
- **Resource Limits**: Built-in resource usage monitoring
- **Graceful Degradation**: Performance-aware service selection

---

The adapters module provides a robust, secure, and highly configurable foundation for CIRIS Agent operations across multiple platforms while maintaining consistent service interfaces and advanced security features.
