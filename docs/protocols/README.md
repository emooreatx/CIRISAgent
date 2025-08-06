# CIRIS Agent Protocol Architecture

## Overview

The CIRIS Agent implements a sophisticated **Service-Oriented Architecture (SOA)** using Python protocols and abstract base classes. This design enables hot-swappable modularity, comprehensive observability, and robust security while maintaining the agent's core ethical reasoning capabilities.

## Protocol Design Principles

### 1. **Interface Segregation**
Each protocol defines a specific contract with minimal, cohesive responsibilities. Services implement only the protocols they need.

### 2. **Type Safety**
Generic typing and Pydantic models ensure compile-time type checking and runtime validation throughout the system.

### 3. **Hot-Swappable Modularity**
All major components can be loaded, unloaded, and reconfigured at runtime without system restart.

### 4. **Service Discovery**
Components register their capabilities through a unified service registry with priority and capability metadata.

### 5. **Security by Design**
Security protocols are integrated at the architecture level, ensuring consistent handling of sensitive data across all components.

## Core Protocol Categories

### Runtime Control Protocols

#### `RuntimeControlInterface`
**Location**: `ciris_engine/protocols/runtime_control_interface.py`

The primary interface for runtime system management, enabling live debugging and configuration changes.

**Key Capabilities**:
```python
# Processor Control
async def single_step() -> ProcessorControlResponse
async def pause_processing() -> ProcessorControlResponse
async def resume_processing() -> ProcessorControlResponse
async def get_processor_queue_status() -> Dict[str, Any]

# Adapter Management
async def load_adapter(adapter_type: str, adapter_id: str, config: Dict[str, Any]) -> AdapterOperationResponse
async def unload_adapter(adapter_id: str, force: bool = False) -> AdapterOperationResponse
async def list_adapters() -> List[Dict[str, Any]]

# Configuration Management
async def get_config(path: Optional[str] = None) -> Dict[str, Any]
async def update_config(path: str, value: Any, scope: ConfigScope) -> ConfigOperationResponse
async def reload_profile(profile_name: str) -> ConfigOperationResponse
async def validate_config(config_data: Dict[str, Any]) -> ConfigValidationResponse

# Status & Monitoring
async def get_runtime_status() -> RuntimeStatusResponse
async def get_runtime_snapshot() -> RuntimeStateSnapshot
```

**Usage Example**:
```python
# Hot-swap a Discord adapter configuration
response = await runtime_control.update_config(
    "discord.home_channel",
    "new-channel-id",
    ConfigScope.SESSION
)

# Load additional adapter instance
await runtime_control.load_adapter(
    "discord",
    "discord_admin",
    {"token": "admin_bot_token", "home_channel": "admin-alerts"}
)
```

### Platform Adapter Protocols

#### `PlatformAdapter`
**Location**: `ciris_engine/protocols/adapter_interface.py`

Unified contract for all platform adapters (Discord, CLI, API, etc.).

**Interface**:
```python
class PlatformAdapter(Protocol):
    def get_services_to_register(self) -> List[ServiceRegistration]
    async def start(self) -> None
    async def run_lifecycle(self, agent_run_task: asyncio.Task) -> None
    async def stop(self) -> None
```

**Service Registration Pattern**:
```python
def get_services_to_register(self) -> List[ServiceRegistration]:
    return [
        ServiceRegistration(
            service_type=ServiceType.COMMUNICATION,
            service_instance=self.communication_service,
            priority=Priority.HIGH,
            handlers=["SpeakHandler", "ObserveHandler"],
            capabilities=["send_message", "receive_message"]
        )
    ]
```

### Service Protocols

#### Core Service Types
**Location**: `ciris_engine/protocols/services.py`

Eight standardized service interfaces ensure consistent behavior across all implementations:

##### 1. **CommunicationService**
```python
async def send_message(channel_id: str, content: str) -> bool
async def fetch_messages(channel_id: str, limit: int = 50) -> List[Message]
async def health_check() -> bool
```

##### 2. **WiseAuthorityService**
```python
async def fetch_guidance(request: GuidanceRequest) -> GuidanceResponse
async def send_deferral(deferral: Deferral) -> DeferralResponse
```

##### 3. **MemoryService**
```python
async def memorize(content: GraphNode, context: MemoryContext) -> str
async def recall(query: str, context: MemoryContext) -> List[GraphNode]
async def forget(memory_id: str, context: MemoryContext) -> bool
async def get_memory_timeseries(query: TimeSeriesQuery) -> TimeSeriesResult
```

##### 4. **ToolService**
```python
async def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> ToolResult
async def get_available_tools() -> List[ToolInfo]
async def validate_tool_request(tool_name: str, parameters: Dict[str, Any]) -> ValidationResult
```

##### 5. **AuditService**
```python
async def log_action(action: str, context: Dict[str, Any], outcome: str) -> str
async def log_event(event: AuditEvent) -> str
async def query_audit_trail(query: AuditQuery) -> AuditResult
```

### Decision Making Algorithm (DMA) Protocols

#### `BaseDMAInterface<InputT, DMAResultT>`
**Location**: `ciris_engine/protocols/dma_interface.py`

Type-safe interface for the agent's 3×3×3 ethical reasoning pipeline.

**Generic Structure**:
```python
class BaseDMAInterface(Protocol, Generic[InputT, DMAResultT]):
    async def evaluate(
        self,
        input_data: InputT,
        faculty: Optional[EpistemicFaculty] = None
    ) -> DMAResultT

    async def evaluate_with_recursive_faculties(
        self,
        input_data: InputT,
        available_faculties: List[EpistemicFaculty]
    ) -> DMAResultT
```

**Specialized DMA Types**:

##### **EthicalDMAInterface**
```python
async def evaluate(
    input_data: ActionRequest,
    faculty: Optional[EpistemicFaculty] = None
) -> EthicalDMAResult
```
Applies foundational ethical principles (beneficence, non-maleficence, justice, autonomy).

##### **CSDMAInterface**
```python
async def evaluate(
    input_data: ActionRequest,
    faculty: Optional[EpistemicFaculty] = None
) -> CSDMAResult
```
Performs common sense reasoning and plausibility checking.

##### **DSDMAInterface**
```python
async def evaluate(
    input_data: ActionRequest,
    faculty: Optional[EpistemicFaculty] = None
) -> DSDMAResult
```
Domain-specific analysis with specialized knowledge.

##### **ActionSelectionDMAInterface**
```python
async def evaluate(
    input_data: ActionRequest,
    faculty: Optional[EpistemicFaculty] = None
) -> ActionSelectionResult
```
Final action selection with recursive evaluation capabilities.

### Telemetry & Monitoring Protocols

#### `TelemetryInterface`
**Location**: `ciris_engine/protocols/telemetry_interface.py`

Comprehensive system observability and processor control.

**Key Methods**:
```python
# System Snapshots
async def get_system_snapshot() -> SystemSnapshot
async def get_processing_queue_status() -> Dict[str, Any]

# Health Monitoring
async def health_check() -> HealthCheckResult
async def get_service_health() -> Dict[str, ServiceHealth]

# Processor Control
async def single_step() -> Dict[str, Any]
async def pause_processing() -> None
async def resume_processing() -> None

# Metrics Collection
async def collect_metrics(tags: Optional[Dict[str, str]] = None) -> MetricsSnapshot
async def query_time_series(query: TimeSeriesQuery) -> TimeSeriesResult
```

### Security Protocols

#### Secrets Management
**Location**: `ciris_engine/protocols/secrets_interface.py`

Four-layer security architecture:

##### **SecretsFilterInterface**
```python
async def scan_content(content: str) -> SecretsScanResult
async def filter_secrets(content: str) -> FilteredContent
```

##### **SecretsStoreInterface**
```python
async def store_secret(secret_data: str, metadata: SecretMetadata) -> str
async def retrieve_secret(secret_id: str, context: AccessContext) -> str
async def delete_secret(secret_id: str) -> bool
```

##### **SecretsEncryptionInterface**
```python
async def encrypt(plaintext: str, context: EncryptionContext) -> EncryptedData
async def decrypt(encrypted_data: EncryptedData, context: DecryptionContext) -> str
```

##### **SecretsServiceInterface**
```python
async def encapsulate_secrets_in_content(content: str) -> ProcessedContent
async def decapsulate_secrets_in_parameters(params: Dict[str, Any]) -> Dict[str, Any]
```

## Protocol Implementation Patterns

### 1. **Service Registration Pattern**

All services use consistent registration:

```python
class MyAdapter(PlatformAdapter):
    def get_services_to_register(self) -> List[ServiceRegistration]:
        return [
            ServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                service_instance=self.comm_service,
                priority=Priority.HIGH,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "receive_message"]
            )
        ]
```

### 2. **Circuit Breaker Pattern**

Services implement fault tolerance:

```python
class MyService:
    async def operation(self):
        if self.circuit_breaker.is_open():
            raise ServiceUnavailableError("Circuit breaker open")

        try:
            result = await self._do_operation()
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
```

### 3. **Health Check Pattern**

All services provide health status:

```python
async def health_check(self) -> HealthCheckResult:
    return HealthCheckResult(
        service_name=self.__class__.__name__,
        status=HealthStatus.HEALTHY,
        details={"connections": self.connection_count},
        timestamp=datetime.now(timezone.utc)
    )
```

### 4. **Type-Safe DMA Pattern**

DMAs use generic typing for safety:

```python
class MyDMA(EthicalDMAInterface):
    async def evaluate(
        self,
        input_data: ActionRequest,
        faculty: Optional[EpistemicFaculty] = None
    ) -> EthicalDMAResult:
        # Type-safe evaluation logic
        return EthicalDMAResult(...)
```

## Configuration Integration

### Template-Based Configuration

Protocols use configuration templates (formerly profiles) for initial setup:

```python
# Template definition (used only during agent creation)
{
    "name": "production",
    "discord_config": {
        "token": "...",
        "home_channel": "general"
    },
    "api_config": {
        "host": "0.0.0.0",
        "port": 8000
    }
}
```

### Runtime Configuration Management

```python
# Update configuration at runtime
await runtime_control.update_config(
    path="discord.home_channel",
    value="new-channel",
    scope=ConfigScope.SESSION,
    validation_level=ConfigValidationLevel.STRICT
)
```

## Error Handling & Resilience

### 1. **Graceful Degradation**
Services continue operating with reduced functionality when dependencies fail.

### 2. **Circuit Breaker Protection**
Automatic failure detection and recovery for external service dependencies.

### 3. **Audit Trail Preservation**
All failures are logged with cryptographic audit trails for forensic analysis.

### 4. **Resource Protection**
Automatic throttling and deferral when resource limits are approached.

## Testing & Validation

### 1. **Protocol Compliance Testing**
```python
def test_service_implements_protocol():
    assert isinstance(my_service, CommunicationService)
    # Protocol method verification
```

### 2. **Mock Implementations**
All protocols have mock implementations for testing:
```python
class MockCommunicationService(CommunicationService):
    async def send_message(self, channel_id: str, content: str) -> bool:
        self.sent_messages.append((channel_id, content))
        return True
```

### 3. **Integration Testing**
End-to-end tests verify protocol interactions across component boundaries.

## Migration & Versioning

### 1. **Backward Compatibility**
New protocol versions maintain compatibility with existing implementations.

### 2. **Deprecation Strategy**
Old protocol methods are deprecated gradually with clear migration paths.

### 3. **Version Negotiation**
Services can negotiate protocol versions during registration.

## Best Practices

### 1. **Protocol Design**
- Keep protocols focused and cohesive
- Use generic typing for type safety
- Define clear error handling contracts
- Include health checking capabilities

### 2. **Implementation**
- Implement circuit breaker patterns
- Provide comprehensive logging
- Use structured error responses
- Support graceful degradation

### 3. **Testing**
- Test protocol compliance
- Mock external dependencies
- Verify error handling paths
- Test resource limit scenarios

### 4. **Documentation**
- Document all protocol methods
- Provide usage examples
- Explain error conditions
- Include performance characteristics

## Future Extensions

The protocol architecture supports future enhancements:

1. **Multi-Agent Protocols**: Network service protocols for agent collaboration
2. **External Integration**: Standardized protocols for third-party service integration
3. **Performance Optimization**: Protocol-level caching and optimization hints
4. **Security Enhancement**: Advanced authentication and authorization protocols

This protocol architecture provides a solid foundation for the CIRIS Agent's modular, observable, and secure operation while maintaining flexibility for future growth and integration needs.
