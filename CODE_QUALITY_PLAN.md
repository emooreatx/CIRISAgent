# CIRIS Code Quality Improvement Plan

## Executive Summary

This plan outlines a systematic approach to improving code quality across the CIRIS codebase based on mypy and vulture analysis. The goal is to achieve full type safety and remove dead code before deploying to agents.ciris.ai.

## Current State Analysis

### Mypy Type Checking Results
- **Total Errors**: ~6,500 type errors detected
- **Error Distribution**:
  - Missing named arguments: 401 instances
  - Missing type annotations: 261 instances  
  - Unreachable code: 26 instances
  - Incompatible types: 18 instances
  - No-untyped-def: 54 instances

### Vulture Dead Code Analysis
- **Total Findings**: 19 unused variables (100% confidence)
- **Locations**: Primarily in protocol definitions and base classes
- **Pattern**: Mostly unused method parameters in abstract base classes

## Priority Areas

### Phase 1: Critical Type Safety (1-2 days)
1. **Fix Missing Required Arguments in Pydantic Models**
   - Priority: HIGH - Causes runtime failures
   - Files: `schemas/telemetry/collector.py`, `schemas/api/responses.py`
   - Action: Add default factories with proper arguments

2. **Fix Unreachable Code**
   - Priority: HIGH - Logic errors
   - Files: `logic/registries/base.py`, `schemas/adapters/registration.py`
   - Action: Review control flow and remove dead branches

3. **Fix Type Incompatibilities**
   - Priority: HIGH - Type safety violations
   - Example: `schemas/services/graph_typed_nodes.py:70` - dict assigned to str
   - Action: Correct type assignments

### Phase 2: Function Annotations (2-3 days)
1. **Add Return Type Annotations**
   - Priority: MEDIUM - Improves type checking coverage
   - Pattern: Functions missing `-> None` or proper return types
   - Action: Add annotations systematically by module

2. **Fix Method Signature Issues**
   - Priority: MEDIUM - API consistency
   - Focus on handler classes and service methods
   - Action: Ensure all overrides match base class signatures

### Phase 3: Clean Up Protocols (1 day)
1. **Remove Unused Protocol Parameters**
   - Priority: LOW - Code cleanliness
   - All 19 vulture findings are in protocol definitions
   - Action: Either implement the parameters or remove them
   - Note: May be intentional for future API compatibility

## Implementation Strategy

### Week 1: Type Safety Sprint
- **Day 1-2**: Fix all HIGH priority issues (Phases 1)
- **Day 3-4**: Add function annotations (Phase 2)
- **Day 5**: Protocol cleanup and testing

### Testing Requirements
- Run mypy after each module fix
- Ensure all tests pass after changes
- Add type tests for critical paths

### Success Metrics
- Reduce mypy errors from 6,500 to under 100
- Achieve 0 unreachable code warnings
- Maintain 100% test pass rate
- Zero runtime type errors in production

## Specific Fix Examples

### 1. Fix Missing Named Arguments
```python
# Before
metadata: ResponseMetadata = Field(default_factory=lambda: ResponseMetadata())

# After  
metadata: ResponseMetadata = Field(default_factory=lambda: ResponseMetadata(
    request_id="",
    duration_ms=0.0
))
```

### 2. Fix Unreachable Code
```python
# Before (in base.py:345)
if isinstance(service_type, str):
    service_type_enum = ServiceType[service_type.upper()]
else:
    service_type_enum = service_type  # Unreachable

# After
service_type_enum = ServiceType[service_type.upper()] if isinstance(service_type, str) else service_type
```

### 3. Add Type Annotations
```python
# Before
def allow_runtime_creation():
    global _allow_runtime_creation
    
# After
def allow_runtime_creation() -> None:
    global _allow_runtime_creation
```

## Automation Opportunities

1. **Type Stub Generation**
   - Use `stubgen` for external dependencies
   - Generate initial annotations for unannotated functions

2. **Progressive Type Checking**
   - Enable strict mode gradually by module
   - Use `# type: ignore` sparingly with explanations

3. **CI Integration**
   - Add mypy to CI pipeline
   - Fail builds on new type errors
   - Track type coverage metrics

## Risk Mitigation

1. **Backward Compatibility**
   - Type changes should not affect runtime behavior
   - Test thoroughly in staging environment
   - Keep type changes separate from logic changes

2. **Performance Impact**
   - Type annotations have no runtime overhead
   - Pydantic validation may have minimal impact
   - Profile critical paths after changes

## Next Steps

1. Review and approve this plan
2. Create tracking issues for each phase
3. Assign team members to specific modules
4. Set up type checking in CI/CD pipeline
5. Begin Phase 1 implementation

## Conclusion

The codebase shows good structure but needs systematic type safety improvements. The majority of issues are mechanical fixes that will significantly improve code reliability and developer experience. With focused effort, we can achieve full type safety within one week.