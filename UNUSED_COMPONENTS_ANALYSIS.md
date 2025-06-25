# Unused Components Analysis

Based on coverage analysis, these components have 0% coverage and appear to be unused.

## 1. Entire Discord Adapter (UNUSED)
All Discord-related files have 0% coverage:
- `ciris_engine/logic/adapters/discord/` - entire directory
- This makes sense - the focus is on API and CLI adapters

**Recommendation**: Keep for future use but document as "not currently active"

## 2. Unused API Routes (CANDIDATES FOR REMOVAL)
These API endpoint files are completely unused:
- `api_agent.py` - agent management endpoints
- `api_audit.py` - audit log endpoints  
- `api_auth.py` - authentication endpoints
- `api_comms.py` - communication endpoints
- `api_logs.py` - log viewing endpoints
- `api_system.py` - system info endpoints
- `api_telemetry.py` - telemetry endpoints
- `api_tools.py` - tool execution endpoints
- `api_visibility.py` - visibility service endpoints
- `api_wa.py` - wise authority endpoints

**Recommendation**: These seem like planned features. Either implement minimal versions or remove.

## 3. Obsolete Telemetry System (REMOVE)
- `ciris_engine/logic/telemetry/collectors.py` - 0% coverage
- `ciris_engine/logic/telemetry/comprehensive_collector.py` - 0% coverage
- `ciris_engine/logic/telemetry/metrics_aggregator.py` - likely unused

**Recommendation**: REMOVE - replaced by graph-based telemetry

## 4. Unused Module Loading (REMOVE)
- `ciris_engine/logic/runtime/modular_service_loader.py` - 0% coverage
- `ciris_engine/logic/runtime/module_loader.py` - 0% coverage

**Recommendation**: REMOVE - not part of current architecture

## 5. Unused DMA Components
- `ciris_engine/logic/dma/action_selection/action_instruction_generator.py` - 0% coverage

**Recommendation**: Check if this is needed for action selection

## 6. CLI Components with Low Coverage
- `cli_tools.py` - 0% coverage
- `cli_wa_service.py` - 0% coverage
- `core_tools.py` - 0% coverage

**Recommendation**: These might be needed for CLI functionality

## 7. Unused Utilities
- `api/dependencies.py` - 0% coverage

## Summary of Immediate Removal Candidates

### High Priority Removals (Obsolete):
1. `ciris_engine/logic/telemetry/` directory (except __init__.py)
2. `ciris_engine/logic/runtime/modular_service_loader.py`
3. `ciris_engine/logic/runtime/module_loader.py`

### Medium Priority (Unused API endpoints):
Consider removing or implementing minimal versions of:
- api_agent.py
- api_audit.py
- api_auth.py
- api_comms.py
- api_logs.py
- api_system.py
- api_telemetry.py
- api_tools.py
- api_visibility.py
- api_wa.py

### Keep for Now:
- Discord adapter (future use)
- CLI tools (may be needed)

## Next Steps
1. Remove obsolete telemetry system
2. Remove unused module loaders
3. Decide on unused API endpoints
4. Run tests to ensure nothing breaks