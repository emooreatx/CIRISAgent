# CIRIS Architecture Overview

## Core Design Pattern: Protocol-Module-Schema Trinity

```
Protocol (Contract) ←→ Module (Implementation) ←→ Schema (Types)
     ↑                         ↑                        ↑
     └─────────────────────────┴────────────────────────┘
                    Perfect Circular Alignment
```

## System Components

### 1. **Service Protocols**

The entire system is defined by just 12 protocol interfaces in `protocols/services.py`:

```python
CommunicationService  # How the agent speaks
MemoryService        # How the agent remembers  
ToolService          # How the agent acts
AuditService         # How the agent is accountable
LLMService           # How the agent thinks
TelemetryService     # How the agent monitors itself
WiseAuthorityService # How the agent seeks guidance
NetworkService       # How the agent connects
CommunityService     # How the agent participates
SecretsService       # How the agent keeps secrets
RuntimeControl       # How the agent controls execution
PersistenceInterface # How the agent persists state
```

Each protocol defines a contract with no implementation details.

### 2. **Action System**

The agent's behavior is organized into a 3×3×3 matrix plus one terminal action:

**External Actions (World)**
- OBSERVE - Perceive the environment
- SPEAK - Communicate with others
- TOOL - Manipulate the world

**Control Actions (Meta)**  
- REJECT - Decline inappropriate requests
- PONDER - Escalate for deeper consideration
- DEFER - Postpone for better timing

**Memory Actions (Self)**
- MEMORIZE - Store experiences
- RECALL - Retrieve knowledge
- FORGET - Remove information

**Terminal Action**
- TASK_COMPLETE - End gracefully

All agent behaviors map to these 10 actions.

### 3. **Data Schemas**

All data uses Pydantic schemas:

```python
# Not this:
data: Dict[str, Any]  # ❌ Attack surface

# But this:
data: MemoryQuery     # ✅ Type-safe contract
```

Key schemas form the vocabulary:
- `Thought` - The agent's cognition
- `Task` - The agent's purpose
- `GraphNode` - The agent's memory
- `ServiceCorrelation` - The agent's introspection
- `ActionSelectionResult` - The agent's decision

### 4. **Routing Through Message Buses**

No service talks directly to another. Everything flows through typed buses:

```python
BusManager
├── CommunicationBus → CommunicationService
├── MemoryBus → MemoryService  
├── ToolBus → ToolService
├── AuditBus → AuditService
├── LLMBus → LLMService
├── TelemetryBus → TelemetryService
└── WiseBus → WiseAuthorityService
```

This enables service substitution without modifying handlers.

### 5. **Decision Making Through DMAs**

The agent's ethical reasoning flows through Decision Making Algorithms:

```
Thought → EthicalDMA → CommonSenseDMA → DomainDMA → ActionSelectionDMA → Action
           ↓              ↓                ↓              ↓
        Principles    Practicality    Expertise      Integration
```

Each DMA handles a specific aspect of decision making.

### 6. **Persistence Through Correlations**

Everything is connected through the correlation system:

```python
ServiceCorrelation
├── correlation_id (unique)
├── service_name
├── correlation_type (THOUGHT_DMA, TASK_ACTION, etc.)
├── timestamp
├── request_data
├── response_data
└── thought_id → task_id → channel_id
```

This creates a complete audit trail - every decision traceable.

### 7. **Adaptability Through Guardrails**

Guardrails aren't hardcoded - they're pluggable filters:

```python
ContentFilterGuardrail    # Blocks harmful content
RateLimitGuardrail       # Prevents spam
ContextLengthGuardrail   # Manages resources
AdaptiveFilterGuardrail  # Learns from feedback
```

New guardrails can be added without changing core logic.

### 8. **Security Through Secrets Service**

All sensitive data flows through one service:

```python
SecretsService
├── detect_secrets()      # Find sensitive data
├── encrypt_secret()      # Store safely
├── decrypt_secret()      # Retrieve safely
└── filter_response()     # Clean outputs
```

No service handles encryption directly - single point of security.

### 9. **Observability Through Telemetry**

The system monitors itself at multiple levels:

```python
BasicTelemetryCollector     # Metrics collection
ComprehensiveTelemetryCollector # Full system view
LogCorrelationCollector     # Log integration
ResourceMonitor             # Resource tracking
```

All telemetry is non-blocking - failures don't affect operations.

### 10. **Authentication Through WA System**

Identity is cryptographic, not username/password:

```python
WACertificate
├── wa_id (deterministic)
├── public_key (Ed25519)
├── oauth_bindings
├── permissions
└── is_revoked
```

Every action tied to a cryptographic identity.

## Design Constraints

### No Dicts
No `Dict[str, Any]` - all data must use typed schemas.

### No Strings  
No magic strings - use enums for constants.

### No Kings
All services follow protocols equally. No special cases.

### No Legacy
No backwards compatibility requirements.

## Core Concepts Summary

The system consists of:
1. **10 Actions** - Agent behavior vocabulary
2. **12 Protocols** - Service contracts  
3. **7 Buses** - Message routing
4. **4 DMAs** - Decision algorithms
5. **1 Registry** - Service discovery

Total: 34 primary concepts.

## Request Flow

Typical request path:

```
API Request 
→ Adapter (protocol: CommunicationService)
→ Observer (creates Task)
→ Processor (creates Thoughts)
→ DMAs (protocol: DMAInterface)
→ Action Selection
→ Handler (protocol: uses BusManager)
→ Service (protocol: specific service)
→ Response
```

Every step has a protocol. Every data has a schema. Every decision has an audit trail.

## System Capabilities

The architecture supports:
- **Ethical reasoning** via the DMA pipeline
- **Memory persistence** via graph storage
- **Learning** via correlation tracking
- **Consistency** via protocol enforcement
- **Evolution** via type safety

The design prioritizes clarity, completeness, and maintainability.