# Unused Schemas and Modules Analysis

Based on vulture analysis of unused imports, this report identifies schemas and modules that may be candidates for removal.

## Schema Categories Analysis

### 1. OAuth/Authentication Schemas (HIGHEST CONFIDENCE FOR REMOVAL)

**Location**: `ciris_engine/logic/infrastructure/sub_services/wa_cli_oauth.py`

**Unused imports**:
- `OAuthProviderConfig`
- `OAuthProviderDetails`
- `OAuthProviderList`
- `OAuthSetupRequest`
- `OAuthTokenExchange`

**Analysis**: 
- All 5 OAuth-related schemas are unused in their primary file
- No OAuth functionality appears to be implemented
- Likely a planned feature that was never completed
- **Recommendation**: Safe to remove entire OAuth schema module if it exists

### 2. Result/Response Schemas (MEDIUM CONFIDENCE)

**Unused result types across codebase**:
- `TamperDetectionResult` (audit/verifier.py)
- `SecretOperationResult` (services/runtime/secrets_service.py)
- `SelfConfigProcessResult` (services/adaptation/self_configuration.py)
- `AuditQueryResult` (services/graph/audit_service.py)
- `ConsolidationResult` (services/graph/telemetry_service.py)

**Analysis**:
- These appear to be legacy result types from an older API design
- May have been replaced by more generic response types
- Check if used in type annotations before removing
- **Recommendation**: Investigate each individually

### 3. Request/Query Schemas (MEDIUM CONFIDENCE)

**Unused request types**:
- `EventQueryRequest`, `EventQueryResult` (adapters/cirisnode_client.py)
- `EnvironmentUpdateRequest`, `IdentityUpdateRequest` (services/graph/memory_service.py)
- `WACertificateRequest`, `WARoleMintRequest` (services/governance/wise_authority.py)

**Analysis**:
- Suggests these APIs were redesigned or never implemented
- CIRISNode client appears to have unused event query functionality
- WA certificate/role minting may have been simplified
- **Recommendation**: Check if these represent unimplemented features

### 4. Context/State Schemas (LOW CONFIDENCE)

**Unused context types**:
- `ProcessorContext`, `ProcessorServices` (processors/core/base_processor.py)
- `MemoryOperationContext` (services/graph/memory_service.py)
- `NodeAttributes` (services/graph/memory_service.py)

**Analysis**:
- May be used in type annotations or inheritance
- Could be base classes or protocols
- **Recommendation**: Verify usage before removing

### 5. Monitoring/Analytics Schemas (MEDIUM CONFIDENCE)

**Unused monitoring types**:
- `VarianceAnalysis` (identity_variance_monitor.py)
- `TaskTypeStats` (solitude_processor.py)
- `DMAOrchestratorStatus` (dma_orchestrator.py)

**Analysis**:
- Suggests simplified monitoring/analytics
- May indicate over-engineering in initial design
- **Recommendation**: Safe to remove if no implementation exists

## Complete List of Potentially Unused Schemas

### High Confidence (90%+ likely unused)
1. **OAuth Schemas Module** - All OAuth-related schemas
2. **OnboardingChoice** - wa_cli_wizard.py
3. **SystemInfoToolResult** - cli_adapter.py

### Medium Confidence (70-89% likely unused)
1. **Result Types**:
   - TamperDetectionResult
   - SecretOperationResult
   - SelfConfigProcessResult
   - AuditQueryResult
   - ConsolidationResult

2. **Request Types**:
   - EventQueryRequest/Result
   - EnvironmentUpdateRequest
   - IdentityUpdateRequest
   - WACertificateRequest
   - WARoleMintRequest

3. **Service Types**:
   - AdapterListResponse
   - ServiceRegistrationInfo (multiple files)
   - AuditLogEntry

### Low Confidence (50-69% likely unused)
1. **Context Types**:
   - ProcessorContext
   - ProcessorServices
   - MemoryOperationContext

2. **Analytics Types**:
   - VarianceAnalysis
   - TaskTypeStats
   - DMAOrchestratorStatus

## Schema Files to Investigate

Based on the unused imports, these schema files may contain dead code:

### CONFIRMED FINDINGS:

1. **schemas/infrastructure/oauth.py** - EXISTS with 10+ OAuth schemas
   - File exists with full OAuth schema definitions
   - Only used by wa_cli_wizard.py (which itself may be unused)
   - Contains: OAuthProviderConfig, OAuthSetupRequest, OAuthOperationResult, etc.

2. **CIRISNodeClient** - PARTIALLY USED
   - Used only in dream_processor.py
   - EventQueryRequest/Result schemas are unused
   - May be over-engineered for current needs

3. **schemas/audit/verification.py** - Contains TamperDetectionResult
   - Schema exists but import is unused
   - May indicate incomplete tamper detection feature

4. **schemas/services/core/secrets.py** - Contains SecretOperationResult
   - Schema exists but not imported where expected
   - Secrets service may use different result type

## Recommended Investigation Process

### Step 1: Find Schema Definitions
```bash
# For each unused import, find where it's defined
grep -r "class OAuthProviderConfig" ciris_engine/schemas/
grep -r "class TamperDetectionResult" ciris_engine/schemas/
# etc...
```

### Step 2: Check Usage Beyond Imports
```bash
# Check if used in type annotations or docstrings
grep -r "OAuthProviderConfig" ciris_engine/ --include="*.py"
# Check if used in TYPE_CHECKING blocks
grep -r "TYPE_CHECKING" -A 10 ciris_engine/ | grep "OAuthProviderConfig"
```

### Step 3: Check for Related Code
```bash
# Look for implementation code that would use these schemas
grep -r "oauth" ciris_engine/ --include="*.py" -i
grep -r "tamper.*detection" ciris_engine/ --include="*.py" -i
```

## Impact Analysis

### Safe to Remove (High Impact, Low Risk):
1. **OAuth Module** - 5+ schemas, no implementation
2. **CIRISNode Event Queries** - 2 schemas, client appears unused
3. **Onboarding Schemas** - No wizard implementation visible

### Requires Careful Review (Medium Impact, Medium Risk):
1. **Result Types** - May affect API contracts
2. **Request Types** - Could break type hints
3. **WA Certificate/Role** - May be future features

### Keep For Now (Low Impact, High Risk):
1. **ServiceRegistry** imports - Being replaced by direct injection
2. **Context types** - May be used in inheritance
3. **Base types** - Could break type system

## Next Steps

1. **Immediate Actions**:
   - Search for OAuth schema definitions
   - Check if cirisnode_client.py is used at all
   - Look for onboarding/wizard implementation

2. **Investigation Needed**:
   - Map each unused import to its schema definition
   - Check for TYPE_CHECKING usage
   - Look for inheritance/protocol usage

3. **Documentation**:
   - Document why schemas were created
   - Mark deprecated schemas clearly
   - Add comments for future features

## Estimated Cleanup Impact

- **Potential schema files to remove**: 5-10
- **Potential lines of code to remove**: 500-1000
- **Risk level**: Low to Medium
- **Time estimate**: 2-4 hours for full investigation and cleanup

## Conclusion

The unused imports suggest significant over-engineering in several areas:
1. OAuth system was designed but never implemented
2. Multiple result/response types could be consolidated
3. Some monitoring/analytics features were planned but not built
4. The codebase has evolved to be simpler than originally designed

This is actually a positive sign - the system has been simplified over time, but the cleanup hasn't been completed.

## URGENT RECOMMENDATIONS

### Definitely Remove (High Confidence):
1. **Entire OAuth Module** (`schemas/infrastructure/oauth.py`)
   - 10+ unused schemas
   - wa_cli_oauth.py service appears unused
   - wa_cli_wizard.py also appears unused
   - **Impact**: Remove ~200+ lines of dead code

2. **Unused Result Types**:
   - TamperDetectionResult (audit/verification.py)
   - SecretOperationResult (services/core/secrets.py)
   - Various other Result schemas
   - **Impact**: Simplify API surface

3. **CIRISNode Event Query Schemas**:
   - EventQueryRequest/EventQueryResult
   - Client is barely used
   - **Impact**: Simplify external integrations

### Investigation Required:
1. Check if wa_cli_wizard.py has any entry points
2. Verify dream_processor's use of CIRISNodeClient
3. Look for TYPE_CHECKING imports of these schemas

### Quick Win Cleanup Script:
```bash
# Find all truly unused schema files
for schema in OAuthProviderConfig TamperDetectionResult EventQueryRequest; do
  echo "=== Checking $schema ==="
  grep -r "$schema" ciris_engine/ --include="*.py" | grep -v "class $schema"
done
```