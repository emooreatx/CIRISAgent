# Bussed vs Unbussed Services in CIRIS

## The Distinction

**Bussed Services** are those that:
1. Are accessed indirectly through the BusManager
2. Can have multiple implementations registered
3. Support automatic failover and load balancing
4. Are used by action handlers and core processing logic

**Unbussed Services** are those that:
1. Are accessed directly by the runtime or platform layer
2. Have a single implementation
3. Are infrastructure services that buses themselves depend on
4. Handle cross-cutting concerns

## Current Service Mapping

### Bussed Services (9 services)
These are accessed through `BusManager` and represent core agent capabilities:

```python
BusManager
├── CommunicationBus → CommunicationService  # How agent speaks
├── MemoryBus → MemoryService               # How agent remembers
├── ToolBus → ToolService                   # How agent acts
├── AuditBus → AuditService                 # How agent is accountable
├── LLMBus → LLMService                     # How agent thinks
├── TelemetryBus → TelemetryService         # How agent monitors
├── WiseBus → WiseAuthorityService          # How agent seeks guidance
├── SecretsBus → SecretsService             # How agent keeps secrets
└── RuntimeControlBus → RuntimeControlService # How agent controls execution
```

### Unbussed Services (3 services)
These are protocol-defined but not routed through buses:

```python
NetworkService      # P2P connectivity (Veilid) - infrastructure layer
CommunityService    # Community context - platform specific
PersistenceInterface # Database operations - used by buses themselves
```

## Why The Distinction?

### Architectural Reasons

1. **Dependency Hierarchy**: 
   - Buses need persistence → PersistenceInterface can't be bussed
   - Buses need network for distributed ops → NetworkService can't be bussed
   - Community context is platform-specific → CommunityService is adapter-specific

2. **Service Discovery**:
   - Bussed services can be discovered and substituted at runtime
   - Unbussed services are wired at initialization time

3. **Failure Isolation**:
   - Bussed services can fail independently with graceful degradation
   - Unbussed service failures are infrastructure failures

### Practical Implications

**For Bussed Services:**
```python
# Handler accesses through BusManager
memory_result = await self.bus_manager.memory.memorize(node)
# Bus handles: service discovery, failover, telemetry, correlation
```

**For Unbussed Services:**
```python
# Platform/Runtime accesses directly
network_status = await self.network_service.get_status()
# Direct call: no routing, no failover, single implementation
```

## The Clean API Surface

The trinity (Protocol-Module-Schema) exposes these capabilities exhaustively:

### Core Agent Actions (via Bussed Services)
- **Perception**: CommunicationService.fetch_messages()
- **Expression**: CommunicationService.send_message()
- **Memory**: MemoryService.memorize(), recall(), forget()
- **Tools**: ToolService.execute_tool()
- **Reasoning**: LLMService.call_llm()
- **Guidance**: WiseAuthorityService.fetch_guidance()
- **Monitoring**: TelemetryService.record_metric()
- **Security**: SecretsService.detect_secrets()
- **Accountability**: AuditService.log_action()
- **Control**: RuntimeControlService.pause_processing()

### Infrastructure Support (via Unbussed Services)
- **Connectivity**: NetworkService (future Veilid integration)
- **Community**: CommunityService (platform-specific context)
- **Storage**: PersistenceInterface (database operations)

## Design Principle

The distinction follows a simple rule:
- **If handlers need it** → Bussed (goes through BusManager)
- **If buses need it** → Unbussed (direct dependency)
- **If it's platform-specific** → Unbussed (adapter concern)

This creates a clean separation between:
1. **Agent Capabilities** (what the agent can do) - Bussed
2. **Infrastructure** (what the system needs to run) - Unbussed