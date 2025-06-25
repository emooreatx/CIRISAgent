# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CURRENT PRIORITY TASK: API & SDK Update

**Maximum Effort Required**: This is the PRIMARY and ONLY focus. ALL effort should be directed to completing the API and SDK updates according to the plans. Previous cleanup tasks are COMPLETE.

### Task Overview

1. **API Update** (See API_UPDATE_PLAN.md)
   - Re-architect API to align with protocol-based design
   - Expose all 19 service protocols appropriately
   - Respect "API is for interaction, not control" principle
   - Remove old telemetry patterns, use graph memory
   - Add missing endpoints for incident management, self-configuration, etc.

2. **SDK Update** (See SDK_UPDATE_PLAN.md)
   - Complete rewrite following "No Dicts" principle
   - Graph-native memory operations
   - Capability-based resource design
   - Full type safety with Pydantic models
   - Migration support for v1 users

### Implementation Priority

1. **Phase 1**: Core API refactoring (Week 1-2)
   - Telemetry refactor to use graph memory
   - Separate config API from runtime control
   - Fix design principle violations

2. **Phase 2**: New protocol endpoints (Week 2-3)
   - Incident management API
   - Self-configuration API
   - Task scheduler API
   - Adaptive filter API

3. **Phase 3**: SDK implementation (Week 2-3)
   - Core architecture with zero dicts
   - Resource implementations
   - Type-safe models
   - Testing and documentation

### Success Criteria

- All 19 protocols exposed via appropriate endpoints
- Zero `Dict[str, Any]` in API contracts and SDK
- Graph memory as single source of truth
- Clear separation of interaction vs control
- Comprehensive test coverage
- Migration guides for existing users

### Design Principles to Maintain

1. **API is for Interaction**: Most endpoints read-only, agent maintains autonomy
2. **RuntimeControl Exception**: Only RuntimeControl allows direct control with AUTHORITY role
3. **Graph Memory**: All data queries from graph, no direct service access
4. **Type Safety**: Pydantic models everywhere, no untyped data
5. **Security**: Authentication required, role-based access, audit trails

### Current Protocol-API Gaps

**Missing Endpoints**:
- IncidentManagementProtocol - No `/v1/incidents/*` endpoints
- SelfConfigurationProtocol - No `/v1/adaptation/*` endpoints  
- TaskSchedulerProtocol - No `/v1/scheduler/*` endpoints
- AdaptiveFilterProtocol - No `/v1/filters/*` endpoints
- TSDBConsolidationProtocol - Not properly exposed
- ResourceMonitorProtocol - No `/v1/resources/*` endpoints

**Misaligned Implementations**:
- Telemetry using old collector instead of graph memory
- Config mixed with runtime control
- Agent creation in auth endpoints

Refer to API_UPDATE_PLAN.md and SDK_UPDATE_PLAN.md for detailed implementation steps.

---

## Core Philosophy: No Dicts, No Strings, No Kings

The CIRIS codebase follows strict typing principles:

- **No Dicts**: ✅ ACHIEVED! Zero `Dict[str, Any]` in production code. All data uses Pydantic models/schemas.
- **No Strings**: Avoid magic strings. Use enums, typed constants, and schema fields instead.
- **No Kings**: No special cases or bypass patterns. Every component follows the same typed, validated patterns.
- **No Backwards Compatibility**: The codebase moves forward only. No legacy support code.

This ensures type safety, validation, and clear contracts throughout the system.

## Project Context

CIRIS is a moral reasoning platform designed for progressive deployment:
- **Current Production**: Discord community moderation (handling spam, fostering positive community)
- **Architecture Goals**: Resource-constrained environments (4GB RAM, offline-capable)
- **Target Deployments**: Rural clinics, educational settings, community centers
- **Design Philosophy**: Start simple (Discord bot), scale to critical (healthcare triage)

The over-engineered architecture (19 services, 6 buses) is intentional - it's a platform that starts as a Discord bot but is designed to scale to mission-critical applications in resource-constrained environments.

## Current Architecture Status

### Service Architecture: Exactly 19 services
- Graph Services (6): memory, audit, config, telemetry, incident_management, tsdb_consolidation
- Core Services (2): llm, secrets
- Infrastructure Services (7): time, shutdown, initialization, visibility, authentication, resource_monitor, runtime_control
- Governance Services (1): wise_authority
- Special Services (3): self_configuration, adaptive_filter, task_scheduler

### Message Bus Architecture (6 Buses)

**Bussed Services** (designed for multiple providers):
- CommunicationBus → Multiple adapters (Discord, API, CLI)
- MemoryBus → Multiple graph backends
- LLMBus → Multiple LLM providers
- ToolBus → Multiple tool providers from adapters
- RuntimeControlBus → Multiple control interfaces
- WiseBus → Multiple wisdom sources

**Direct Call Services** (single instance by design):
- All Graph Services except memory
- All Infrastructure Services except wise_authority
- All Special Services

### Testing Status
- All tests passing (355 passed, 61 skipped)
- Discord adapter fully implemented with vision support
- Zero MyPy errors in critical paths

## Development Commands

### Running the Agent
```bash
# Run with mock LLM in API mode (recommended for testing)
python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080

# Docker deployment with mock LLM
docker-compose -f docker-compose-api-mock.yml up -d
```

### Testing
```bash
# Run full test suite
pytest tests/ -v

# Run MyPy check
python -m mypy ciris_engine/ --config-file=mypy.ini
```

## Important Guidelines

### When Implementing API/SDK Updates
1. **Start with API telemetry refactor** - Critical path
2. **Test each endpoint thoroughly** - No assumptions
3. **Maintain type safety** - Zero dicts policy
4. **Document all changes** - Migration guides essential
5. **Respect agent autonomy** - Interaction over control

### Never Ask for Confirmation
- Make changes directly
- Implement decisively
- The goal is a clean, typed API and SDK