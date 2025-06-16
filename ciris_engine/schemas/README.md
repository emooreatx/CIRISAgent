# Schemas

The schemas module contains all Pydantic data models used throughout the CIRIS Engine. These schemas provide strict type safety, validation, and serialization for all data structures in the system.

## Core Schema Files

### Foundational Schemas (`foundational_schemas_v1.py`)
- **HandlerActionType**: The 3×3×3 action enumeration (OBSERVE, SPEAK, TOOL, REJECT, PONDER, DEFER, MEMORIZE, RECALL, FORGET, TASK_COMPLETE)
- **TaskStatus**: Task lifecycle states (PENDING, ACTIVE, COMPLETED, FAILED, DEFERRED)
- **ThoughtStatus**: Thought processing states (PENDING, PROCESSING, COMPLETED, FAILED, DEFERRED)
- **ServiceType**: Service categories (COMMUNICATION, MEMORY, AUDIT, LLM, TOOL, WISE_AUTHORITY)
- **DispatchContext**: ✨ Complete action execution context (ALL fields required - no Optional)
- **IncomingMessage**: Base schema for all incoming messages
- **ResourceUsage**: LLM token and cost tracking

### Core Agent Schemas (`agent_core_schemas_v1.py`)
- **Task**: Core task representation with context and lifecycle management
- **Thought**: Individual thought objects with DMA processing results

### Identity Schemas (`identity_schemas_v1.py`) ✨ NEW
- **AgentIdentityRoot**: Core identity stored in graph (identity IS the graph)
- **CoreProfile**: Behavioral configuration within identity
- **IdentityMetadata**: Tracking creation and modifications with WA approval
- **ScheduledTask**: Self-directed agent goals integrated with TaskSchedulerService
- **IdentityEvolutionRequest**: WA-approved identity change requests

### Action Parameters (`action_params_v1.py`)
Action-specific parameter schemas for all 10 handler types:
- **ObserveParams, SpeakParams, ToolParams**
- **RejectParams, PonderParams, DeferParams** (✨ DeferParams now includes `defer_until` timestamp)
- **MemorizeParams, RecallParams, ForgetParams**
- **TaskCompleteParams**: Task completion with optional notes

### Context Schemas (`context_schemas_v1.py`)
- **ThoughtContext**: Rich context for thought processing
- **SystemSnapshot**: Complete system state including ✨ agent identity loaded once at snapshot
- **UserProfile**: User-specific configuration and preferences
- **ChannelContext**: Communication channel metadata

### Specialized Schemas

#### Decision Making & Results
- **DMA Results** (`dma_results_v1.py`): Decision making architecture outputs
  - ActionSelectionResult: Selected action with typed parameters
  - EthicalAssessment: Beneficence, non-maleficence evaluations
  - CommonSenseCheck: Plausibility and coherence checks

#### Memory & Knowledge Graph
- **Graph Schemas** (`graph_schemas_v1.py`): Universal graph structure
  - GraphNode: Nodes with type, scope, and attributes
  - GraphEdge: Typed relationships between nodes
  - GraphScope: LOCAL, SHARED, IDENTITY, ENVIRONMENT scopes
  - MemoryOperation: Results of memory operations
- **Memory Schemas** (`memory_schemas_v1.py`): Memory operation metadata

#### Security & Audit
- **WA Schemas** (`wa_schemas_v1.py`): Wise Authority authentication
  - WACertificate: Authority credentials and permissions
  - WAToken: JWT token payloads
  - OAuthConfig: OAuth provider configurations
- **WA Audit** (`wa_audit_schemas_v1.py`): Security audit events
- **Audit** (`audit_schemas_v1.py`): Cryptographic audit trail schemas
- **Secrets** (`secrets_schemas_v1.py`): Secrets detection and encryption

#### Infrastructure
- **Telemetry** (`telemetry_schemas_v1.py`): System observability
  - TelemetryEvent: Metrics with ✨ HOT/COLD path classification
  - MetricType: Counter, gauge, histogram types
- **Processing** (`processing_schemas_v1.py`): Thought processing pipeline
- **Service Actions** (`service_actions_v1.py`): Service operation definitions
- **DB Tables** (`db_tables_v1.py`): SQLAlchemy table definitions

#### Community & Collaboration
- **Community** (`community_schemas_v1.py`): ✨ Post-scarcity economy
  - GratitudeMetrics: Tracking flow of appreciation
  - CommunityConnection: Agent relationships
  - KnowledgeDomain: Expertise mapping
- **Wisdom** (`wisdom_schemas_v1.py`): Human wisdom integration
- **Deferral** (`deferral_schemas_v1.py`): Task deferral to authorities

#### Configuration
- **Config** (`config_schemas_v1.py`): Complete application configuration
  - AppConfig: Master configuration object
  - AgentProfile: Personality and behavior settings
  - LLMConfig: Language model settings
  - DiscordConfig: Discord adapter configuration
- **Guardrails Config** (`guardrails_config_v1.py`): Safety thresholds

## Schema Architecture

### Identity System Design ✨
- **Identity IS the Graph**: No separate identity service or database
- **MEMORIZE for Changes**: All identity modifications use standard MEMORIZE action
- **WA Approval Required**: Identity changes need wise authority approval
- **20% Variance Threshold**: Large changes trigger reconsideration guidance

### Version Management
- **VersionedSchema**: Base class with `schema_version` field for evolution
- **SchemaRegistry**: Central registry for all schema types with validation
- **Version Compatibility**: Forward/backward compatibility support

### Type Safety Features
- **Strict Validation**: All data validated at model boundaries
- **Required Fields**: Mission-critical schemas avoid Optional types
- **CaseInsensitiveEnum**: Flexible enum handling for user inputs
- **Custom Validators**: Domain-specific validation logic

### Key Design Principles
- **Mission-Critical Type Safety**: No dicts, strict Pydantic models everywhere
- **Schema Evolution**: Versioned schemas for safe upgrades
- **Runtime Validation**: Schema registry for dynamic validation
- **Serialization**: JSON-compatible serialization for all schemas

## Usage Examples

### Basic Model Usage
```python
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus

# Create and validate a task
task = Task(
    task_id="task_123",
    description="Example task",
    status=TaskStatus.PENDING,
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat()
)
```

### Identity System Usage ✨
```python
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot, CoreProfile
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

# Identity is stored as a graph node
identity_node = GraphNode(
    id="agent/identity",
    type=NodeType.AGENT,
    scope=GraphScope.IDENTITY,
    attributes={
        "identity": AgentIdentityRoot(
            agent_id="teacher-001",
            identity_hash="sha256...",
            core_profile=CoreProfile(
                description="A helpful teaching assistant",
                role_description="Guides students through learning",
                dsdma_identifier="teaching"
            ),
            allowed_capabilities=["communication", "memory", "observation"],
            restricted_capabilities=["identity_change_without_approval"]
        ).model_dump()
    }
)
```

### Action Parameters with Deferred Scheduling ✨
```python
from ciris_engine.schemas.action_params_v1 import DeferParams
from datetime import datetime, timedelta

# Defer with specific timestamp
defer_params = DeferParams(
    reason="Complex ethical question requiring human wisdom",
    defer_until=(datetime.now() + timedelta(hours=2)).isoformat(),
    context={"urgency": "low", "topic": "philosophy"}
)
```

### Required DispatchContext ✨
```python
from ciris_engine.schemas.foundational_schemas_v1 import DispatchContext, HandlerActionType
import uuid

# ALL fields are required - no Optional allowed
context = DispatchContext(
    # Core identification
    channel_id="discord-123456",
    author_id="user-789",
    author_name="Alice",
    
    # Service references
    origin_service="discord",
    handler_name="SpeakHandler",
    
    # Action context
    action_type=HandlerActionType.SPEAK,
    thought_id=str(uuid.uuid4()),
    task_id="task-001",
    source_task_id="task-001",
    
    # Event details
    event_summary="User greeting",
    event_timestamp=datetime.now(timezone.utc).isoformat(),
    
    # Security
    wa_authorized=False,
    
    # Correlation
    correlation_id=str(uuid.uuid4()),
    round_number=1
)
```

### Schema Registry
```python
from ciris_engine.schemas.schema_registry import validate_schema

# Runtime validation
result = validate_schema("Task", task_data)
```

## Recent Updates

### June 2025
- **Identity System**: Identity IS the graph, changes via MEMORIZE action
- **DeferParams Enhancement**: Added `defer_until` for scheduled deferrals
- **DispatchContext**: Made ALL fields required for type safety
- **SystemSnapshot**: Added agent identity loaded once at generation
- **HOT/COLD Telemetry**: Path-aware metric classification
- **Community Schemas**: Post-scarcity economy tracking

The schemas module ensures complete type safety across the entire CIRIS system while providing flexibility for evolution and extension.

---

*Copyright © 2025 Eric Moore and CIRIS L3C - Apache 2.0 License*
