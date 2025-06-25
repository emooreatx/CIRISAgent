# MyPy Zero Plan

## Current Status
- Total errors: 2150 (down from 2193)
- Fixed so far:
  - ✅ Added missing 'Any' imports (54 files)
  - ✅ Fixed duplicate imports
  - ✅ Fixed Field default_factory issues
  - ✅ Fixed AdapterConfig/AdapterStatus imports
  - ✅ Created factory functions for complex defaults

## Major Issues by Category

### 1. Pydantic Field Issues (High Priority)
**Problem**: MyPy expects all fields to be passed to constructors even if they have defaults
**Examples**:
```python
# Current (failing):
default_factory=lambda: DatabaseConfig()

# MyPy expects:
default_factory=lambda: DatabaseConfig(
    main_db=Path("data/ciris_engine.db"),
    secrets_db=Path("data/secrets.db"),
    audit_db=Path("data/ciris_audit.db")
)
```
**Files affected**: 
- schemas/config/essential.py
- schemas/services/graph_core.py
- Many schema files with nested models

### 2. Missing Type Annotations (Medium Priority)
**Problem**: Functions missing return type annotations
**Solution**: Add `-> None`, `-> str`, etc. to all functions
**Affected files**: ~100+ files

### 3. Protocol Import Issues (High Priority)
**Problem**: Circular imports and missing protocol definitions
**Examples**:
- AdapterConfig/AdapterStatus not found in schemas.adapters.core
- Many "Module has no attribute" errors
**Solution**: 
- Move shared types to dedicated modules
- Use TYPE_CHECKING imports for circular dependencies

### 4. Unreachable Code (Low Priority)
**Problem**: Code after return/raise statements
**Solution**: Remove or restructure unreachable code
**Files**: ~20 files

### 5. Incompatible Type Assignments (High Priority)
**Problem**: Type mismatches in assignments
**Examples**:
```python
# self.config is dict but assigning APIAdapterConfig
self.config = APIAdapterConfig()
```
**Solution**: Fix type declarations or use proper casts

## Recommended Approach

### Phase 1: Fix Critical Schema Issues
1. Fix all Pydantic Field default_factory issues
2. Add missing required fields to model constructors
3. Fix circular imports in schemas

### Phase 2: Fix Protocol/Type Issues
1. Add missing type annotations to functions
2. Fix protocol compliance issues
3. Resolve "Module has no attribute" errors

### Phase 3: Code Cleanup
1. Remove unreachable code
2. Fix type mismatches
3. Add proper type casts where needed

### Phase 4: Final Polish
1. Fix remaining edge cases
2. Add type: ignore comments only where absolutely necessary
3. Run full test suite to ensure no regressions

## Top Files to Fix First (by error count)
1. logic/services/runtime/control_service.py (146 errors)
2. logic/services/adaptation/self_configuration.py (110 errors)
3. logic/telemetry/comprehensive_collector.py (66 errors)
4. logic/adapters/discord/discord_adapter.py (65 errors)
5. logic/services/graph/audit_service.py (61 errors)

## Estimated Effort
- Phase 1: 2-3 hours
- Phase 2: 3-4 hours  
- Phase 3: 2-3 hours
- Phase 4: 1-2 hours

Total: 8-12 hours of focused work