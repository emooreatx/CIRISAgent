# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

CIRIS is a moral reasoning platform designed for progressive deployment:
- **Current Production**: Discord community moderation (handling spam, fostering positive community)
- **Architecture Goals**: Resource-constrained environments (4GB RAM, offline-capable)
- **Target Deployments**: Rural clinics, educational settings, community centers
- **Design Philosophy**: Start simple (Discord bot), scale to critical (healthcare triage)

The sophisticated architecture (19 services, 6 buses) is intentional - it's a platform that starts as a Discord bot but is designed to scale to mission-critical applications in resource-constrained environments.

## Core Philosophy: No Dicts, No Strings, No Kings

The CIRIS codebase follows strict typing principles:

- **No Dicts**: ✅ ACHIEVED! Zero `Dict[str, Any]` in production code. All data uses Pydantic models/schemas.
- **No Strings**: Avoid magic strings. Use enums, typed constants, and schema fields instead.
- **No Kings**: No special cases or bypass patterns. Every component follows the same typed, validated patterns.
- **No Backwards Compatibility**: The codebase moves forward only. No legacy support code.

This ensures type safety, validation, and clear contracts throughout the system.

## Current Status (July 1, 2025)

### 🎉 Major Achievements

1. **Complete Type Safety**
   - Zero `Dict[str, Any]` in production code
   - All data structures use Pydantic schemas
   - Full type validation throughout the system

2. **Service Architecture**: Exactly 19 services ✅
   - Graph Services (6): memory, audit, config, telemetry, incident_management, tsdb_consolidation
   - Core Services (2): llm, secrets
   - Infrastructure Services (7): time, shutdown, initialization, visibility, authentication, resource_monitor, runtime_control
   - Governance Services (1): wise_authority
   - Special Services (3): self_observation, adaptive_filter, task_scheduler
   - **All 19 services healthy and operational**

3. **API v1.0**: Fully Operational
   - All 35 endpoints implemented and tested
   - 100% test pass rate (35/35 endpoints) ✅
   - Role-based access control (OBSERVER/ADMIN/AUTHORITY/SYSTEM_ADMIN)
   - Emergency shutdown with Ed25519 signatures
   - Default dev credentials: admin/ciris_admin_password
   - WebSocket support for real-time streaming
   - Runtime control service fully integrated

4. **Typed Graph Node System**
   - 11 active TypedGraphNode classes with full validation
   - Automatic type registration via node registry
   - Clean serialization pattern with to_graph_node()/from_graph_node()
   - All nodes include required metadata fields

5. **Graph-Based Telemetry**
   - All telemetry flows through memory graph
   - Real-time metrics via memorize_metric()
   - 6-hour consolidation for long-term storage
   - Full resource tracking with model-specific pricing

6. **Clean Architecture**
   - Protocol-first design with clear interfaces
   - Services separated by concern
   - No circular dependencies
   - All logic under `logic/` directory
   - SelfConfiguration renamed to SelfObservation (complete refactor)

7. **Test Suite Health**
   - 661 tests passing (was 658)
   - Only 12 warnings (down from 128)
   - Fixed Pydantic v2 deprecations
   - Fixed SQLite datetime adapter warnings
   - All SDK endpoint tests passing

## Recent Achievements (July 1, 2025)

### Mock LLM Handler Testing Infrastructure
1. **Standardized Passive Observation Format**
   - All adapters now use: "You observed @{author} (ID: {id}) in channel {channel} say: {message}"
   - Simple string-based command extraction without regex tricks
   - Reliable command parsing from passive observation prefix

2. **Fixed ASPDMA Template Variables**
   - Discovered root cause: context_builder.py was sending literal `{original_thought.content}` instead of actual values
   - Fixed all template variable formatting in ActionSelectionDMAResult prompts
   - Mock LLM now receives properly formatted context from ASPDMA

3. **Complete Handler Coverage in Mock LLM**
   - Added missing handlers: TOOL, OBSERVE, DEFER, REJECT
   - Fixed MEMORIZE validation using tags instead of content/description
   - All 9 main handlers + TASK_COMPLETE now fully operational
   - Tested with 10 parallel containers successfully

4. **Mock LLM Purpose Clarification**
   - Mock LLM is TEST INFRASTRUCTURE ONLY - not production code
   - Performance is not a concern - it's for deterministic testing
   - Channel isolation in mock LLM is not a security issue
   - Designed for offline testing and development

5. **Parallel Testing Capability**
   - Use Claude Code Task tool to spawn concurrent sub-agents
   - NOT Python scripts - leverage Claude Code's native parallelism
   - Successfully tested 10 containers in parallel
   - Each container tests different handlers concurrently

## Architecture Overview

### Message Bus Architecture (6 Buses)

Buses enable multiple providers for scalability:

**Bussed Services**:
- CommunicationBus → Multiple adapters (Discord, API, CLI)
- MemoryBus → Multiple graph backends (Neo4j, ArangoDB, in-memory)
- LLMBus → Multiple LLM providers (OpenAI, Anthropic, local models)
- ToolBus → Multiple tool providers from adapters
- RuntimeControlBus → Multiple control interfaces
- WiseBus → Multiple wisdom sources

**Direct Call Services**:
- All Graph Services (except memory)
- Core Services: secrets
- Infrastructure Services (except wise_authority)
- All Special Services

### Service Registry Usage

Only for multi-provider services:
1. **LLM** - Multiple providers
2. **Memory** - Multiple graph backends
3. **WiseAuthority** - Multiple wisdom sources
4. **RuntimeControl** - Adapter-provided only

### Cognitive States (6)
- **WAKEUP** - Identity confirmation
- **WORK** - Normal task processing
- **PLAY** - Creative mode
- **SOLITUDE** - Reflection
- **DREAM** - Deep introspection
- **SHUTDOWN** - Graceful termination

## Development

### Running the Agent
```bash
# Docker deployment (API mode)
docker-compose -f docker-compose-api-mock.yml up -d

# CLI mode with mock LLM
python main.py --mock-llm --timeout 15 --adapter cli
```

### Testing
```bash
# Run full test suite
pytest tests/ -v

# Run API tests
python test_api_v1_comprehensive.py

# Run parallel handler testing (10 containers)
docker-compose -f docker-compose-multi-mock.yml up -d
python test_10_containers_parallel.py
```

### API Authentication
```python
# Default development credentials
username = "admin"
password = "ciris_admin_password"

# Authentication flow for API v1:
# 1. Login to get token
response = requests.post(
    "http://localhost:8080/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
token = response.json()["access_token"]

# 2. Use token in Authorization header
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    "http://localhost:8080/v1/agent/interact",
    headers=headers,
    json={"message": "Hello", "channel_id": "api_0.0.0.0_8080"}
)

# Note: Some endpoints accept Bearer admin:ciris_admin_password directly
# Example: GET /v1/system/health -H "Authorization: Bearer admin:ciris_admin_password"
```

## Key Principles

1. **Service Count is Sacred**: Exactly 19 services
2. **No Service Creates Services**: Only ServiceInitializer creates services
3. **Type Safety First**: All data uses Pydantic schemas
4. **Protocol-Driven**: All services implement clear protocols
5. **Forward Only**: No backwards compatibility

## Why This Architecture?

- **SQLite + Threading**: Offline-first for remote deployments
- **19 Services**: Modular for selective deployment
- **Graph Memory**: Builds local knowledge base
- **Mock LLM**: Critical for offline operation
- **Resource Constraints**: Designed for 4GB RAM environments

## Verified Development Truths

### Mock LLM System
- **Location**: External module in `ciris_modular_services/mock_llm/`
- **Commands**: All mock LLM commands use `$` prefix (e.g., `$speak`, `$recall`, `$memorize`)
- **API Interaction**: Use `/v1/agent/interact` endpoint with `{"message": "...", "channel_id": "..."}` format
- **Response Format**: Mock responses should use `[MOCK LLM] ` prefix for clarity
- **Testing**: Mock LLM provides deterministic responses for offline testing
- **Purpose**: TEST INFRASTRUCTURE ONLY - not production code, performance not critical
- **Command Extraction**: Uses simple string operations to extract commands from "You observed @" prefix
- **All Handlers Implemented**: SPEAK, RECALL, MEMORIZE, TOOL, OBSERVE, PONDER, DEFER, REJECT, TASK_COMPLETE

### Container Management
- **Incidents Log**: ALWAYS check container incidents logs with `docker exec <container> tail /app/logs/incidents_latest.log`
- **Multi-Container**: Use `docker-compose-multi-mock.yml` for 10-container parallel testing
- **Ports**: Containers use ports 8080-8089 (container0 through container9)
- **Health Check**: Wait for containers to be healthy before testing
- **Parallel Testing**: Use Claude Code Task tool for concurrent testing, NOT Python scripts
- **Rebuild Required**: ALWAYS rebuild containers after code changes for endpoints to appear

### API Structure
- **Adapter Management**: Runtime adapter management endpoints are available at `/v1/system/adapters/*` (requires container rebuild after code changes)
- **Service Registration**: AdapterServiceRegistration doesn't have priority_group or strategy attributes - use getattr() for optional attributes
- **Auth Field**: API uses `"message"` field not `"content"` for interact endpoint
- **Channel Format**: Channel IDs follow pattern `<adapter>_<identifier>` (e.g., `discord_1234567890`, `api_0.0.0.0_8080`)

### Testing Best Practices
- **Parallel Testing**: Use Claude Code Task tool to spawn concurrent sub-agents for parallel testing
- **Container Logs**: Check logs INSIDE containers with `docker exec`, not local logs
- **Rebuild Frequency**: ALWAYS rebuild containers after ANY code changes - endpoints won't appear without rebuild
- **Container Age**: Check container uptime in health endpoint - if it shows hours when you just started, you forgot to rebuild
- **Error Patterns**: ServiceCorrelation validation errors are non-critical (missing response_timestamp field)
- **Handler Testing**: Test all 9 main handlers plus runtime control in parallel containers
- **Mock LLM Debug**: Check context extraction in responses.py and action selection in responses_action_selection.py

### Debug Tool Usage

The `debug_tools.py` provides essential commands for troubleshooting production issues:

#### Available Commands
```python
# Show recent service correlations with trace hierarchy
show_correlations(limit=20)           # Show last 20 correlations
show_correlations(trace_id="...")     # Show all correlations for a specific trace

# List recent unique trace IDs with span counts
list_traces(limit=20)                 # Show last 20 traces

# Show thoughts by status
show_thoughts(status='PENDING')       # Show pending thoughts
show_thoughts(status='PROCESSING')    # Show processing thoughts
show_thoughts(status='COMPLETED')     # Show completed thoughts

# Show tasks and their thoughts
show_tasks(limit=10)                  # Show recent tasks with thought counts

# Show handler metrics
show_handler_metrics()                # Display handler execution counts and timings
```

#### Debug Process for Handler Issues
1. **Check container incidents log**:
   ```bash
   docker exec container0 tail -n 100 /app/logs/incidents_latest.log
   ```

2. **Use debug tool to analyze traces**:
   ```bash
   docker exec container0 python debug_tools.py
   ```
   ```python
   # In the Python shell:
   from debug_tools import *
   
   # Find recent traces
   list_traces(limit=10)
   
   # Examine a specific trace hierarchy
   show_correlations(trace_id="your-trace-id")
   
   # Check for stuck thoughts
   show_thoughts(status='PENDING')
   show_thoughts(status='PROCESSING')
   ```

3. **Understanding trace hierarchies**:
   - Each API request creates a root trace
   - Handlers create child spans under the trace
   - Parent-child relationships show execution flow
   - Timing data helps identify bottlenecks

4. **Common debugging patterns**:
   - **"Thought not found" errors**: Check if thoughts are being completed before creating follow-ups
   - **Stuck thoughts**: Look for PENDING/PROCESSING thoughts that aren't progressing
   - **Handler failures**: Use trace hierarchy to see which handler failed
   - **Performance issues**: Check handler metrics and trace timings