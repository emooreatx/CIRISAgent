# Duplicate Class Analysis - June 2025

## Summary
Found 67 duplicate class names in the codebase:
- 6 classes with 3 definitions each
- 61 classes with 2 definitions each

## High Priority Duplicates (3+ occurrences)

### 1. ConfigValue (3 locations)
- `api/routes/config.py` - API route model with key/value/updated_at
- `schemas/runtime/protocols_core.py` - Core schema with path/value  
- `schemas/services/nodes.py` - Typed wrapper with string/int/float/bool/dict values

**Issue**: Three different representations of configuration values
**Recommendation**: Consolidate to single ConfigValue in schemas/services/nodes.py (most complete)

### 2. IdentitySnapshot (3 locations)
- `schemas/infrastructure/identity_variance.py` - BaseModel with snapshot_id/timestamp
- `schemas/runtime/core.py` - BaseModel with snapshot_id/agent_id
- `schemas/services/nodes.py` - TypedGraphNode version (most complete)

**Issue**: Multiple versions, only nodes.py extends TypedGraphNode
**Recommendation**: Use only the TypedGraphNode version, remove others

### 3. UserProfile (3 locations)
- `schemas/runtime/system_context.py` - Core user with id/display_name/created_at
- `schemas/adapters/graphql_core.py` - GraphQL enriched with nick/channel/attributes
- `schemas/services/graph/telemetry.py` - Telemetry version with id/name/role

**Issue**: Different fields for different contexts
**Recommendation**: Create base UserProfile and context-specific extensions

### 4. ConscienceResult (3 locations)
- `schemas/runtime/system_context.py` - Basic with passed/conscience_name
- `schemas/processors/core.py` - Complex with original/final actions
- `schemas/conscience/results.py` - Standard with name/passed/reasoning

**Issue**: Different levels of detail for same concept
**Recommendation**: Use conscience/results.py as base, extend for processors

### 5. AuditEntry (3 locations)  
- `schemas/runtime/audit.py` - BaseModel with entry_id/timestamp
- `schemas/audit/hash_chain.py` - Hash chain version with event_id
- `schemas/services/nodes.py` - TypedGraphNode version

**Issue**: Different storage mechanisms
**Recommendation**: Use TypedGraphNode version, deprecate others

### 6. ProcessorMetrics (3 locations)
- `schemas/processors/base.py` - BaseModel with start/end times
- `schemas/processors/main.py` - Detailed with processor_name/rounds
- `protocols/processors/agent.py` - Protocol with thoughts/tasks counts

**Issue**: Schema vs Protocol confusion
**Recommendation**: Merge schemas, keep protocol separate

## Medium Priority Duplicates (2 occurrences)

### Key Issues:
1. **ServiceStatus** - Appears in multiple service contexts
2. **RuntimeStatus/RuntimeMetrics** - Split between runtime and API schemas
3. **StreamMessage** - Different versions for different streaming contexts
4. **ThoughtContext** - Runtime vs processor versions
5. **ResourceUsage** - Runtime vs service versions

## Recommendations

### Immediate Actions:
1. **Remove TypedGraphNode duplicates** - Use only node versions for:
   - IdentitySnapshot
   - AuditEntry
   - ConfigValue

2. **Consolidate Result types** - Many XxxResult classes can be merged

3. **Fix import paths** - Many duplicates are due to cross-module imports

### Structural Changes:
1. **Create common schema modules**:
   - `schemas/common/users.py` - Single UserProfile
   - `schemas/common/config.py` - Single ConfigValue
   - `schemas/common/metrics.py` - Unified metrics

2. **Establish clear boundaries**:
   - API schemas only in `api/schemas/`
   - Runtime schemas only in `schemas/runtime/`
   - Service schemas only in `schemas/services/`

3. **Remove cross-imports** - No schema should be defined in:
   - API routes
   - Logic modules
   - Protocol files

## Impact Analysis
- **High Risk**: ConfigValue, AuditEntry (used extensively)
- **Medium Risk**: UserProfile, ConscienceResult
- **Low Risk**: ProcessorMetrics, IdentitySnapshot

## Next Steps
1. Start with low-risk duplicates
2. Update imports progressively
3. Add deprecation warnings
4. Remove duplicates after testing