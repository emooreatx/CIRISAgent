# Duplicate Cleanup Plan

## Critical Duplicates to Fix

### 1. ServiceRegistry
- **Primary**: `ciris_engine/logic/registries/base.py:51` (KEEP - this is the real implementation)
- **Duplicate**: `ciris_engine/schemas/infrastructure/base.py:179` (REMOVE - schemas shouldn't have logic)

### 2. CircuitBreaker
- **Primary**: `ciris_engine/logic/registries/circuit_breaker.py:32` (KEEP - this is the shared implementation)
- **Duplicate**: `ciris_engine/logic/buses/llm_bus.py:74` (REMOVE - should import from registries)

### 3. MessageDict
- **Primary**: `ciris_engine/protocols/services/runtime/llm.py:11` (KEEP - protocol definition)
- **Duplicate**: `ciris_engine/logic/buses/llm_bus.py:60` (REMOVE - should import from protocol)

### 4. Test Duplicates
- **TestDiscordAdapter**: Exists in both `tests/adapters/test_discord/` and `tests/ciris_engine/logic/adapters/discord/`
  - Keep the one that matches the project structure (likely `tests/ciris_engine/...`)
  - Remove the other

### 5. Request Classes (LLMRequest, MemorizeRequest, RecallRequest)
- **Primary**: Keep in `schemas/services/requests.py`
- **Duplicates**: Remove from individual bus files

### 6. Secret-related Classes
- **Primary**: Keep in `schemas/secrets/core.py`
- **Duplicates**: Remove from `logic/services/runtime/secrets_service.py`

## Action Steps

1. **Fix imports first** - Update all files that import from duplicate locations
2. **Remove duplicate definitions** - Delete the duplicate class definitions
3. **Run tests** - Ensure nothing breaks
4. **Update test structure** - Consolidate test files to match source structure

## Test Structure Recommendation

Tests should mirror source structure:
```
tests/
├── ciris_engine/
│   ├── logic/
│   │   ├── adapters/
│   │   │   └── discord/
│   │   │       └── test_discord_adapter.py
│   │   ├── registries/
│   │   │   └── test_circuit_breaker.py
│   │   └── buses/
│   │       └── test_llm_bus.py
│   └── schemas/
│       └── test_schemas.py
└── integration/
    └── test_full_system.py
```

Remove duplicate test directories like `tests/adapters/test_discord/`.