# Schemas

The schemas module contains all Pydantic data models used throughout the CIRIS Engine. These schemas provide strict type safety, validation, and serialization for all data structures in the system.

## Core Schema Files

### Foundational Schemas (`foundational_schemas_v1.py`)
- **HandlerActionType**: The 3×3×3 action enumeration (OBSERVE, SPEAK, TOOL, REJECT, PONDER, DEFER, MEMORIZE, RECALL, FORGET, TASK_COMPLETE)
- **TaskStatus**: Task lifecycle states (PENDING, ACTIVE, COMPLETED, FAILED, DEFERRED)
- **ThoughtStatus**: Thought processing states (PENDING, PROCESSING, COMPLETED, FAILED, DEFERRED)
- **ObservationSourceType**: Sources of observations (CHAT_MESSAGE, FEEDBACK_PACKAGE, USER_REQUEST, etc.)
- **IncomingMessage**: Base schema for all incoming messages
- **ResourceUsage**: LLM token and cost tracking

### Core Agent Schemas (`agent_core_schemas_v1.py`)
- **Task**: Core task representation with context and lifecycle management
- **Thought**: Individual thought objects with DMA processing results

### Action Parameters (`action_params_v1.py`)
Action-specific parameter schemas for all 10 handler types:
- **ObserveParams, SpeakParams, ToolParams**
- **RejectParams, PonderParams, DeferParams** 
- **MemorizeParams, RecallParams, ForgetParams**

### Context Schemas (`context_schemas_v1.py`)
- **ThoughtContext**: Rich context for thought processing
- **SystemSnapshot**: Complete system state for agent introspection
- **UserProfile**: User-specific configuration and preferences

### Specialized Schemas
- **DMA Results** (`dma_results_v1.py`): Decision making architecture outputs
- **Memory/Graph** (`memory_schemas_v1.py`, `graph_schemas_v1.py`): Graph-based memory structures
- **Processing** (`processing_schemas_v1.py`): Thought processing pipeline schemas
- **Audit** (`audit_schemas_v1.py`): Cryptographic audit trail schemas
- **Telemetry** (`telemetry_schemas_v1.py`): System observability metrics
- **Security** (`secrets_schemas_v1.py`): Secrets management and encryption

## Schema Architecture

### Version Management
- **VersionedSchema**: Base class with `schema_version` field for evolution
- **SchemaRegistry**: Central registry for all schema types with validation
- **Version Compatibility**: Forward/backward compatibility support

### Type Safety Features
- **Strict Validation**: All data validated at model boundaries
- **CaseInsensitiveEnum**: Flexible enum handling for user inputs
- **Field Aliases**: Support for backward compatibility
- **Custom Validators**: Domain-specific validation logic

### Key Design Principles
- **Mission-Critical Type Safety**: No dicts, strict Pydantic models everywhere
- **Schema Evolution**: Versioned schemas for safe upgrades
- **Runtime Validation**: Schema registry for dynamic validation
- **Serialization**: JSON-compatible serialization for all schemas

## Usage

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

### Schema Registry
```python
from ciris_engine.schemas.schema_registry import validate_schema

# Runtime validation
result = validate_schema("Task", task_data)
```

### Action Parameters
```python
from ciris_engine.schemas.action_params_v1 import SpeakParams

speak_params = SpeakParams(
    content="Hello, user!",
    channel_id="channel_123"
)
```

The schemas module ensures complete type safety across the entire CIRIS system while providing flexibility for evolution and extension.
