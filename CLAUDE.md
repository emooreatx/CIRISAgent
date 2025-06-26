# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

CIRIS is a moral reasoning platform designed for progressive deployment:
- **Current Production**: Discord community moderation (handling spam, fostering positive community)
- **Architecture Goals**: Resource-constrained environments (4GB RAM, offline-capable)
- **Target Deployments**: Rural clinics, educational settings, community centers
- **Design Philosophy**: Start simple (Discord bot), scale to critical (healthcare triage)

The over-engineered architecture (19 services, 6 buses) is intentional - it's a platform that starts as a Discord bot but is designed to scale to mission-critical applications in resource-constrained environments.

## Core Philosophy: No Dicts, No Strings, No Kings

The CIRIS codebase follows strict typing principles:

- **No Dicts**: ✅ ACHIEVED! Zero `Dict[str, Any]` in production code. All data uses Pydantic models/schemas.
- **No Strings**: Avoid magic strings. Use enums, typed constants, and schema fields instead.
- **No Kings**: No special cases or bypass patterns. Every component follows the same typed, validated patterns.
- **No Backwards Compatibility**: The codebase moves forward only. No legacy support code.

This ensures type safety, validation, and clear contracts throughout the system.

## Current Status (June 24, 2025)

### ✅ Major Achievements

1. **Dict[str, Any] Elimination**: COMPLETE! 
   - Started with 609 instances
   - Now have 0 in production code
   - Fixed lowercase `dict[str, Any]` as well

2. **Service Architecture**: Exactly 19 services (production only!)
   - Graph Services (6): memory, audit, config, telemetry, incident_management, tsdb_consolidation
   - Core Services (2): llm, secrets (mock_llm is test-only)
   - Infrastructure Services (7): time, shutdown, initialization, visibility, authentication, resource_monitor, runtime_control
   - Governance Services (1): wise_authority
   - Special Services (3): self_configuration, adaptive_filter, task_scheduler

3. **Schema Reorganization**:
   - Created `schemas/actions/` for shared action parameters
   - All handlers, DMAs, and services now use shared action schemas
   - Tool schemas properly located in `schemas/services/tools_core.py`

4. **Positivity Integration**:
   - Added `positive_moment` field to TaskCompleteParams
   - Integrated into task completion flow
   - No new services needed - uses existing MEMORIZE

5. **Time Utils Migration**: COMPLETE!
   - Deleted time_utils.py entirely
   - All time operations now use injected TimeService
   - Zero direct datetime.now() calls in production code

6. **Processor Protocols**: NEW!
   - Created AgentProcessorProtocol for main coordinator
   - Created ProcessorProtocol for state processors
   - Deleted orphaned DreamProcessorProtocol
   - Clean separation between processors and services

7. **Service Count Finalized**: 19 services locked in!
   - Removed CoreToolService (was only for SELF_HELP)
   - SELF_HELP now part of Memory service (recalling capabilities)
   - Tool and Communication provided ONLY by adapters
   - Cleaner, more reliable architecture

8. **Typed Node System**: FULLY IMPLEMENTED!
   - Created TypedGraphNode base class with to_graph_node()/from_graph_node() pattern
   - GraphNode accepts Union[GraphNodeAttributes, Dict] for flexibility
   - All graph nodes migrated to typed pattern
   - Node registry for automatic type registration
   - All nodes have required created_at, updated_at, created_by fields
   - Memory service stores generic GraphNode, services use typed nodes
   - Full type safety with Pydantic validation
   - **11 Active TypedGraphNode Classes**:
     - IdentityNode (agent identity at "agent/identity")
     - ConfigNode, AuditEntry (core)
     - IncidentNode, ProblemNode, IncidentInsightNode (incident management)
     - TSDBSummary (telemetry consolidation)
     - SystemSnapshot (replaces IdentitySnapshot - monitors system state changes)
     - DiscordDeferralNode, DiscordApprovalNode, DiscordWANode (Discord-specific)

9. **Graph-Based Telemetry**: COMPLETE & SIMPLIFIED!
   - Telemetry stored via memorize_metric() → correlations → TSDBSummary
   - Follows "Graph Memory as Identity Architecture" patent
   - **Simplified Flow**: Removed orphaned TelemetryNode and NodeType.TELEMETRY
   - All adapters use memorize_metric() directly:
     - API adapter: adapter lifecycle, host/port info
     - CLI adapter: adapter lifecycle, message processing, tool execution
     - Discord adapter: adapter lifecycle, message send/receive, tool execution
   - API telemetry routes query from correlations/TSDB nodes:
     - `/v1/telemetry/overview` - Summary of all telemetry
     - `/v1/telemetry/metrics` - Current metrics with timeseries data
     - `/v1/telemetry/metrics/{name}` - Detailed history for specific metric
     - `/v1/telemetry/resources` - Resource usage aggregation
     - `/v1/telemetry/resources/history` - Historical resource data
   - TSDBConsolidationService creates 6-hour summaries for permanent memory

10. **Complete Architectural Refactor**: COMPLETE!
   - Deleted 500+ files of legacy code
   - Removed all action handlers (replaced by API design)
   - Moved from handlers to RESTful API endpoints
   - Clean protocol-module-schema architecture
   - All logic under `logic/` directory
   - Perfect separation of concerns

11. **Pytest Green**: ACHIEVED!
   - Fixed ConfigurationFeedbackLoop to implement ServiceProtocol
   - Updated DreamProcessor tests to use search API
   - Fixed all insight processing tests
   - Removed process_experience method
   - All tests passing (295 passed, 58 skipped)

12. **SystemSnapshot and Identity Monitoring**: REFACTORED!
   - Renamed IdentitySnapshot to SystemSnapshot for clarity
   - SystemSnapshot now monitors all system state changes, not just identity
   - Improved field names for better understanding:
     - `variant_identity` → `identity_state` (current identity information)
     - `invariant_identity` → `identity_reference` (reference identity for comparison)
     - `deviation_context` → `change_context` (reason for snapshot)
   - Used throughout the system for tracking important state changes:
     - Cognitive state transitions (WORK → PLAY, etc.)
     - Configuration changes
     - Service modifications
     - Critical system events
   - Stored as typed graph nodes with full validation
   - Enables temporal analysis of system evolution

### 🚨 Current Focus: Documentation and Polish

**Status as of June 24, 2025**: Major refactor COMPLETE! All tests green!

## Cleanup Action Plan

### Phase 1: Get It Running ✅ COMPLETE

1. **Fix ConfigNode Migration** ✅ COMPLETE
   - Created TypedGraphNode base class with serialization pattern
   - ConfigNode now properly extends TypedGraphNode
   - GraphNode accepts Union[GraphNodeAttributes, Dict] for flexibility
   - All nodes have required created_at, updated_at, created_by fields
   - Fixed Path object serialization in set_config

2. **Remove DatabaseMaintenanceService** ✅ COMPLETE
   - Removed `_perform_startup_maintenance` call from runtime
   - Confirmed it's just a utility, not one of the 19 services

3. **Complete Telemetry Collector Removal** ✅ COMPLETE
   - Replaced BasicTelemetryCollector with GraphTelemetryService
   - Removed telemetry_collector from APIAdapter parameters
   - Updated APITelemetryRoutes to indicate telemetry in graph
   - Telemetry now follows "Graph Memory as Identity Architecture" patent
   - Adapters will emit telemetry through memory bus as TSDBGraphNodes

### Phase 2: Careful Cleanup ✅ COMPLETE

#### Task 4: Manual System Verification First
**Goal**: Verify system still starts and runs basic operations

**Steps**:
1. Start with mock LLM:
   ```bash
   python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080
   ```
2. Verify it reaches WAKEUP state
3. Try basic API calls:
   ```bash
   curl http://localhost:8080/v1/health
   curl http://localhost:8080/v1/telemetry/overview
   ```
4. Document current working state as baseline

**Success Criteria**:
- System starts without errors
- Reaches WAKEUP state
- API responds to health checks

#### Task 5: Inventory Dead Code (ANALYSIS ONLY)
**Goal**: Create detailed inventory of potentially dead code WITHOUT deleting yet

**Steps**:
1. Run vulture with high confidence:
   ```bash
   vulture ciris_engine/ --min-confidence 95 > dead_code_high_confidence.txt
   ```
2. Run with medium confidence:
   ```bash
   vulture ciris_engine/ --min-confidence 80 > dead_code_medium_confidence.txt
   ```
3. Categorize findings:
   - SAFE TO DELETE: Obvious dead imports, unused variables
   - MAYBE SAFE: Unused methods in non-critical paths
   - DANGEROUS: Protocol methods, handlers, core services
   - UNKNOWN: Needs investigation

4. Create priority list starting with safest deletions

#### Task 6: Remove Only OBVIOUS Dead Imports
**Goal**: Start with the absolute safest cleanup

**Steps**:
1. Find unused imports:
   ```bash
   # Find import statements that vulture flagged
   grep "unused import" dead_code_high_confidence.txt
   ```
2. For each unused import:
   - Verify it's truly unused (grep for usage)
   - Remove ONLY the import line
   - Test system still starts
3. Commit after each file's imports are cleaned

**DO NOT REMOVE**:
- TYPE_CHECKING imports
- Protocol imports
- __all__ exports

#### Task 7: Fix Service Initialization Order
**Goal**: Document and verify correct initialization order

**Steps**:
1. Map current initialization order in ServiceInitializer
2. Identify dependencies:
   - TimeService → needed by ALL
   - SecretsService → needed by Memory
   - Memory → needed by Graph services
   - etc.
3. Check for violations:
   - Services creating other services
   - Circular dependencies
   - Missing dependencies
4. Document findings - DO NOT CHANGE CODE YET

#### Task 8: Remove Commented-Out Code
**Goal**: Clean up obvious clutter

**Safe to remove**:
- Old commented code blocks
- TODO comments referencing completed work
- Debug print statements (commented)
- Alternative implementations (commented)

**Process**:
1. Search for comment patterns:
   ```bash
   # Find commented code blocks
   grep -n "^[ ]*#.*=" ciris_engine/**/*.py
   grep -n "^[ ]*# TODO.*DONE" ciris_engine/**/*.py
   ```
2. Review each instance
3. Delete only if obviously obsolete
4. Test system still starts after each batch

#### Task 9: Document What CAN'T Be Deleted
**Goal**: Create allowlist of critical code vulture doesn't understand

**Document**:
1. Protocol methods (must keep even if "unused")
2. Handler methods called dynamically
3. Schema fields used in serialization
4. Service registry entries
5. Lifecycle methods (start, stop, etc.)

**Format**:
```python
# vulture_allowlist.py
# Protocol methods
_ = ServiceProtocol.start
_ = ServiceProtocol.stop
# Dynamic dispatch
_ = SpeakHandler.handle
# etc...
```

#### Task 10: Identify Duplicate/Redundant Code
**Goal**: Find code doing the same thing in multiple places

**Steps**:
1. Look for duplicate functionality:
   - Multiple telemetry collectors
   - Duplicate config systems
   - Similar utility functions
2. Document duplicates but DO NOT merge yet
3. Plan consolidation strategy

#### Task 11: Clean Up Empty/Trivial Files
**Goal**: Remove files that add no value

**Safe to remove**:
- Empty __init__.py files (unless needed for packages)
- Files with only imports
- Files with only comments
- Test files with no actual tests

**Process**:
1. Find empty/trivial files:
   ```bash
   find ciris_engine -name "*.py" -size -100c
   ```
2. Review each file
3. Delete only if truly empty/useless
4. Update imports if needed

#### Task 12: Create Cleanup Verification Script
**Goal**: Automate basic "is it still working" check

**Create simple script**:
```python
# verify_cleanup.py
# 1. Try to import all major modules
# 2. Try to instantiate key services
# 3. Check critical paths work
# NO full testing, just "does it crash?"
```

### CRITICAL RULES:
1. **Test after EVERY change** - Start system and verify it reaches WAKEUP
2. **Commit frequently** - Small commits we can revert
3. **When in doubt, DON'T DELETE** - Better to keep dead code than break system
4. **NO NEW CODE** - Only delete and rewire
5. **Document everything** - Keep notes on what was removed and why

### Order of Operations:
1. Verify current state works (Task 4)
2. Analyze what's dead (Task 5)
3. Remove safest items first (Tasks 6, 8, 11)
4. Document critical code (Task 9)
5. Plan harder changes (Tasks 7, 10)
6. Create safety net (Task 12)

### Phase 3: Deep Clean (DETAILED PLAN)

#### Task 7: Complete Config Migration
**Goal**: Full migration to graph-based configuration

**Steps**:
1. Search for old config patterns:
   ```bash
   grep -r "ConfigManager\|AppConfig\|config\." --include="*.py" ciris_engine/
   ```
2. Update each reference:
   - `ConfigManager` → `ConfigAccessor`
   - `AppConfig` → `EssentialConfig`
   - Direct config access → Use ConfigAccessor methods
3. Verify graph storage:
   - All config stored as ConfigNode in graph
   - No file-based config except bootstrap
4. Remove old files:
   - Delete legacy config modules
   - Remove config file templates
   - Clean up config utilities

#### Task 8: Bus Architecture Consistency
**Goal**: Enforce proper bus vs direct service access

**Audit checklist**:
1. Bussed services (MUST use bus):
   - Memory → via MemoryBus
   - LLM → via LLMBus
   - WiseAuthority → via WiseBus
   - Tool → via ToolBus (adapter-provided)
   - Communication → via CommunicationBus (adapter-provided)
   - RuntimeControl → via RuntimeControlBus (if available)

2. Direct services (MUST use direct reference):
   - All graph services (except memory)
   - TimeService, SecretsService
   - All infrastructure services
   - All special services

**Fix violations**:
- Replace `service_registry.get_service()` with direct injection
- Update constructors to accept dependencies
- Remove runtime service lookups

#### Task 9: Import Cleanup
**Goal**: Clean, consistent, circular-import-free codebase

**Steps**:
1. Run import analysis:
   ```bash
   python -m pyflakes ciris_engine/ | grep "import"
   python -m isort --check-only --diff ciris_engine/
   ```
2. Fix import order (each file):
   - Standard library
   - Third-party
   - CIRIS protocols
   - CIRIS schemas  
   - CIRIS logic
   - Relative imports
3. Break circular imports:
   - Use TYPE_CHECKING for type hints
   - Move shared types to common modules
   - Use late imports in methods if needed
4. Remove unused imports:
   ```bash
   autoflake --remove-all-unused-imports -i -r ciris_engine/
   ```

### Phase 4: Validation (DETAILED PLAN)

#### Task 10: MyPy Zero
**Goal**: ZERO type errors across entire codebase

**Current status**: ~1800 errors

**Strategy**:
1. Fix by error type (most common first):
   - `call-arg` (584) - Wrong function arguments
   - `attr-defined` (413) - Missing attributes
   - `import-not-found` (250) - Missing imports
   - `arg-type` (174) - Wrong argument types

2. Fix by module (critical first):
   - Runtime and initialization
   - Core services
   - Handlers and processors
   - Adapters
   - Tests

3. Common fixes:
   - Add type annotations
   - Fix Optional types
   - Add Protocol inheritance
   - Fix generic types
   - Add missing imports

#### Task 11: Test Suite Update
**Goal**: Tests that match new architecture

**Steps**:
1. Remove ALL dict-based mocks:
   ```python
   # Bad
   mock_config = {"key": "value"}
   
   # Good  
   mock_config = ConfigNode(key="test", value=ConfigValue(...))
   ```

2. Update fixtures:
   - Use real schemas
   - Inject real services
   - Mock only external dependencies

3. Fix test categories:
   - Unit tests → Test single methods
   - Integration tests → Test service interactions
   - E2E tests → Test full workflows

4. Target: 100% pass rate

#### Task 12: Documentation Update
**Goal**: Accurate, helpful documentation

**Deliverables**:
1. Architecture diagram showing:
   - 19 services and their relationships
   - 6 buses and their providers
   - Initialization flow
   
2. Service documentation:
   - Each service's purpose
   - Protocol it implements
   - Dependencies
   - Usage examples

3. Developer guide:
   - How to add new services
   - How to extend handlers
   - How to add new node types
   - Testing guidelines

### Architecture Guidelines

- **Services**: All in `logic/services/`
- **Schemas**: Mirror structure in `schemas/`
- **Protocols**: Mirror structure in `protocols/`
- **Shared Types**: Use `schemas/actions/` for parameters used across modules

### Why This Architecture?

The seemingly complex architecture serves specific deployment needs:
- **SQLite + Threading**: Offline-first for clinics without reliable internet
- **19 Services**: Modular so deployments can pick what they need
- **Graph Memory**: Builds local knowledge that can sync when connected
- **Ubuntu Philosophy**: Culturally appropriate for African deployments
- **Mock LLM Mode**: Critical for offline operation in remote areas
- **Llama/4o-mini**: Chosen for speed and cost in resource-constrained settings

### Message Bus Architecture (6 Buses)

Buses are used for services designed to support multiple providers, even if currently single-provider. This future-proofs the architecture.

**Bussed Services** (designed for multiple providers):
- CommunicationBus → Multiple adapters (Discord, API, CLI) - NO standalone service
- MemoryBus → Multiple graph backends (Neo4j, ArangoDB, in-memory, etc.)
- LLMBus → Multiple LLM providers (OpenAI, Anthropic, local models, fallbacks)
- ToolBus → Multiple tool providers from adapters - NO standalone service
- RuntimeControlBus → Multiple control interfaces (API, CLI, emergency stop)
- WiseBus → Multiple wisdom sources (distributed WAs, consensus)

**Direct Call Services** (single instance by design):
- All Graph Services except memory: audit, config, telemetry, incident_management, tsdb_consolidation
- Core Services: secrets (single security boundary)
- All Infrastructure Services except wise_authority: time, shutdown, initialization, visibility, authentication, resource_monitor
- All Special Services: self_configuration, adaptive_filter, task_scheduler

**Service Dependencies for Buses**:
- All buses need: TimeService (for timestamps)
- LLMBus needs: TelemetryService (for resource tracking)
- MemoryBus needs: AuditService (for change tracking)

### ServiceRegistry Usage (Critical)

ServiceRegistry is used ONLY for these multi-provider services:
1. **LLM** - Multiple providers (OpenAI, Anthropic, Mock) - ALWAYS registered
2. **Memory** - Multiple graph backends possible - ALWAYS registered
3. **WiseAuthority** - Multiple wisdom sources possible - ALWAYS registered
4. **RuntimeControl** - Adapter-provided ONLY (API/CLI provide it, Discord doesn't) - OPTIONAL

Note: 
- Tool and Communication are provided ONLY by adapters through their respective buses. There are NO standalone Tool or Communication services. 
- SELF_HELP functionality is part of Memory service (recalling capabilities).
- RuntimeControl is NOT a core service. It only exists if an adapter provides it (e.g., API adapter for REST control, CLI for command-line control). Discord-only deployments have no RuntimeControl service - use OS signals (Ctrl-C, SIGTERM) instead.

All other services (Time, Shutdown, Audit, Telemetry, etc.) are single-instance and should use direct references, NOT ServiceRegistry. No handler-specific or adapter-specific service instances - that violates "No Kings".

### Cognitive States (6)
- **WAKEUP** - Identity confirmation ritual
- **WORK** - Normal task processing
- **PLAY** - Creative and experimental mode
- **SOLITUDE** - Reflection and maintenance
- **DREAM** - Deep introspection
- **SHUTDOWN** - Graceful termination

### Test Refactoring Plan (After MyPy Zero)

1. Mirror the new structure - tests follow code organization
2. Use proper fixtures - no dict-based mocks
3. Test through interfaces - protocols, not implementations
4. Integration over unit tests
5. Use real schemas - no mock dictionaries

## Known Issues & Solutions

### ConfigNode Migration Failure
- **Error**: `Field required [type=missing, input_value={'key':...`
- **Cause**: Mismatch between config migration and ConfigNode schema
- **Solution**: Update `_migrate_config_to_graph` to include all required fields

### DatabaseMaintenanceService Not Found
- **Error**: `No maintenance service available`
- **Cause**: It's not one of the 19 services, just a utility
- **Solution**: Remove startup maintenance requirement

### Initialization Order
- **Current Flow**:
  1. INFRASTRUCTURE → TimeService, ShutdownService, InitializationService, ResourceMonitor
  2. DATABASE → Initialize SQLite
  3. MEMORY → SecretsService, MemoryService, GraphConfigService
  4. IDENTITY → Load agent identity
  5. SECURITY → WiseAuthorityService
  6. SERVICES → All remaining services
  7. COMPONENTS → Build components
  8. VERIFICATION → Final checks

## Critical Principles

1. **Service Count is Sacred**: Exactly 19 services. No more, no less.
2. **No Service Creates Services**: Only ServiceInitializer creates services
3. **Buses for Multi-Provider**: Memory, LLM, WiseAuthority use ServiceRegistry
4. **Direct for Single-Instance**: All others use direct references
5. **Utilities Are Not Services**: DatabaseMaintenanceService, helpers, etc. are NOT services

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

### Type Safety
- ✅ Zero Dict[str, Any] achieved!
- All data structures use Pydantic schemas
- Maintain strict typing throughout

### Testing
- Tests must use typed schemas
- No dict-based mocking
- Test through protocols

### Never Ask for Confirmation
- Make changes directly
- Break things if needed
- The goal is clean, typed code