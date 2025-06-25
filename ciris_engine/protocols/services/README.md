# Service Protocols

This directory contains the protocol definitions for all 19 CIRIS services. Each protocol defines the exact interface that its corresponding service implementation must follow.

## Service Categories

### Graph Services (5)
Everything is memory - all state flows through these services:
- **[graph_memory.py](./graph_memory.py)** - Core memory operations (memorize, recall, forget)
- **[graph_audit.py](./graph_audit.py)** - Unified audit (graph + file + hash chain)
- **[graph_config.py](./graph_config.py)** - Configuration as versioned nodes
- **[graph_telemetry.py](./graph_telemetry.py)** - Metrics and telemetry data
- **[graph_gratitude.py](./graph_gratitude.py)** - Gratitude tracking and reciprocity

### Core Services (5)
Essential operations that cannot be stored in the graph:
- **[llm.py](./llm.py)** - Primary language model interactions
- **[mock_llm.py](./mock_llm.py)** - Deterministic LLM for testing
- **[tool.py](./tool.py)** - External tool execution
- **[secrets.py](./secrets.py)** - Secrets management and filtering
- **[runtime_control.py](./runtime_control.py)** - Runtime coordination

### Infrastructure Services (4)
System foundations:
- **[time.py](./time.py)** - Centralized time operations (no datetime.now()!)
- **[shutdown.py](./shutdown.py)** - Graceful shutdown coordination
- **[initialization.py](./initialization.py)** - Service initialization sequencing
- **[visibility.py](./visibility.py)** - API introspection and transparency

### Authority Services (1)
Human oversight:
- **[wise_authority.py](./wise_authority.py)** - All WA operations (auth, provisioning, deferrals)

### Special Services (4)
Unique capabilities:
- **[self_configuration.py](./self_configuration.py)** - Active adaptation intelligence (20% safeguard)
- **[adaptive_filter.py](./adaptive_filter.py)** - Message filtering and prioritization
- **[task_scheduler.py](./task_scheduler.py)** - Future task scheduling and DEFER support
- **[transaction_orchestrator.py](./transaction_orchestrator.py)** - Multi-service atomic operations

## Protocol Rules

1. **Exact Match**: Service implementations MUST implement every method in their protocol
2. **No Extras**: Service implementations MUST NOT have public methods outside the protocol
3. **Type Safety**: All parameters and returns must use typed schemas (no Dict[str, Any])
4. **Async First**: All operations that could be I/O bound must be async
5. **Health & Capabilities**: Every service must implement the base service methods

## Adding a New Service

1. Create the protocol file in this directory
2. Define the protocol interface extending from appropriate base
3. Update this README
4. Implement the service following the protocol exactly
5. Add protocol compliance tests

## Protocol Inheritance

All protocols inherit from base protocols in `ciris_engine/protocols/base.py`:
- `ServiceProtocol` - Base for all services (start, stop, is_healthy, get_capabilities)
- `GraphServiceProtocol` - Base for graph services (adds graph-specific methods)
- `CoreServiceProtocol` - Base for core services (adds core-specific methods)