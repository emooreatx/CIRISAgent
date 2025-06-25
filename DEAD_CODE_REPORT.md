# Dead Code Analysis Report

Generated using Vulture static analysis tool.

## Summary

**Total findings with 90% confidence**: 63
- Unused imports: 33
- Unused variables: 30
- Unused functions/methods/classes: 0 (at 90% confidence)

## Key Findings

### 1. Unused Imports (33 total)

**Most common patterns**:
- Schema imports that were refactored but not cleaned up
- Service registry imports (suggesting direct injection is used instead)
- Result/Response types that may have been replaced

**Notable unused imports**:
- `ServiceRegistry` in multiple files (self_configuration.py, audit_service.py, etc.)
- OAuth-related schemas in wa_cli_oauth.py (5 unused imports)
- Various result types (TamperDetectionResult, SecretOperationResult, etc.)

### 2. Unused Variables (30 total)

**Protocol stub variables** (in protocol definitions - likely intentional):
- `middleware`, `input_text`, `reaction`, `websocket` in adapters/base.py
- `situation`, `agents` in dma/base.py
- `subscription_id`, `update_id`, `checkpoint_id` in infrastructure/base.py

**Actual unused variables**:
- `all_incidents` in incident_service.py (line 199)
- `is_monitored`, `is_deferral`, `is_home` in channel_utils.py

### 3. No Unused Functions/Methods/Classes

At 90% confidence, Vulture found no unused functions, methods, or classes. This suggests:
- Good code hygiene for function/class definitions
- Most dead code is limited to imports and variables
- Dynamic usage patterns may hide some dead code from static analysis

## Recommendations

### Safe to Remove (High Confidence)

1. **Unused imports in services/**:
   ```python
   # self_configuration.py
   - ServiceRegistry
   - AdaptationImpact
   - ObservabilitySignal
   - PatternRecord
   - SelfConfigProcessResult
   
   # audit_service.py
   - ServiceRegistry
   - AuditQueryResult
   - AuditLogEntry
   ```

2. **OAuth imports in wa_cli_oauth.py**:
   - All 5 OAuth-related imports appear unused
   - Suggests OAuth functionality may have been removed/refactored

3. **Unused variable in incident_service.py**:
   - Line 199: `all_incidents` (100% confidence)

### Requires Investigation

1. **Protocol stub variables**: These may be intentionally unused as they define protocol interfaces
2. **Result/Response types**: May be used in type annotations only
3. **ServiceRegistry imports**: Verify that direct injection is used everywhere

### Do NOT Remove

1. **TYPE_CHECKING imports**: Not detected by vulture but critical for type hints
2. **Protocol method parameters**: Even if unused, they define the interface
3. **__all__ exports**: May appear unused but define public API

## Action Items

1. **Quick wins** (15 minutes):
   - Remove the 33 unused imports
   - Remove `all_incidents` variable in incident_service.py
   - Remove unused variables in channel_utils.py

2. **Needs verification** (30 minutes):
   - Check if OAuth functionality is still needed
   - Verify ServiceRegistry is truly unused
   - Check if result types are used in type annotations

3. **Future improvements**:
   - Add vulture to CI/CD pipeline
   - Create vulture whitelist for intentional "dead" code
   - Regular dead code cleanup sprints

## Files with Most Dead Code

1. wa_cli_oauth.py (6 unused imports)
2. self_configuration.py (5 unused imports)
3. audit_service.py (3 unused imports)
4. memory_service.py (5 unused imports)
5. Protocol files (multiple unused parameters - likely intentional)

## Conclusion

The codebase has relatively little dead code:
- No unused functions or classes (good!)
- Mostly unused imports from refactoring
- Some protocol stubs that may be intentional

Total estimated cleanup time: 1-2 hours for safe removals