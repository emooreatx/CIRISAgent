# Zero Dict[str, Any] and MyPy Errors Plan

## Current State
- **Files with Dict[str, Any]**: 113
- **Total Dict[str, Any] occurrences**: 184
- **MyPy errors**: 524

## Execution Plan

### Phase 1: Categorize and Prioritize (Day 1)
1. **Group Dict[str, Any] by category:**
   - Request/Response models
   - Configuration objects
   - Internal state/context
   - Database/Query results
   - External API interactions

2. **Prioritize by impact:**
   - High: Core services, handlers, buses
   - Medium: Adapters, utilities
   - Low: Scripts, tools, examples

### Phase 2: Create Base Models (Day 1-2)
1. **Common patterns:**
   ```python
   # Generic response model
   class TypedResponse(BaseModel, Generic[T]):
       data: T
       metadata: ResponseMetadata
   
   # Configuration base
   class TypedConfig(BaseModel):
       class Config:
           extra = "forbid"
   
   # Context base
   class TypedContext(BaseModel):
       trace_id: str
       timestamp: datetime
   ```

2. **Domain-specific models:**
   - ServiceContext
   - QueryResult
   - HandlerParams
   - AdapterConfig

### Phase 3: Systematic Replacement (Day 2-4)
1. **Order of replacement:**
   - Core services first
   - Then handlers
   - Then adapters
   - Finally utilities

2. **For each file:**
   - Identify Dict[str, Any] usage
   - Create appropriate model
   - Update code
   - Fix resulting errors
   - Test

### Phase 4: MyPy Error Resolution (Day 4-5)
1. **Common error patterns:**
   - Missing type parameters
   - Incompatible overrides
   - Missing annotations
   - Any usage

2. **Resolution strategy:**
   - Fix errors by category
   - Use proper generics
   - Add missing annotations
   - Remove unnecessary Any

### Phase 5: Validation (Day 5)
1. **Ensure:**
   - Zero Dict[str, Any]
   - Zero mypy errors
   - All tests pass
   - No performance regression

## Success Metrics
- `grep -r "Dict\[str, Any\]" ciris_engine/ | wc -l` returns 0
- `python -m mypy ciris_engine/` returns "Success: no issues found"
- All tests pass
- No # type: ignore comments added

## Let's Begin!