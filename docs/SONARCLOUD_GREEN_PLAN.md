# SonarCloud Green Recovery Plan

## Current Status: Quality Gate FAILING ❌

### Failed Conditions:
1. **New Reliability Rating**: 3 (needs ≤ 1) - Due to 1 BUG
2. **New Security Rating**: 2 (needs ≤ 1) - Due to 1 VULNERABILITY
3. **New Coverage**: 52.5% (needs ≥ 80%)

### Passing Conditions: ✅
- New Maintainability Rating: 1
- New Duplicated Lines: 1.08%
- Security Hotspots Reviewed: 100%

## Priority 1: Fix BUG and VULNERABILITY (2 issues) - Est. 30 minutes

### 1.1 Fix Async Task Garbage Collection BUG
**File**: `ciris_engine/logic/adapters/api/routes/system.py:669`
**Issue**: Task not saved to variable, may be garbage collected
```python
# BEFORE:
asyncio.create_task(audit_service.log_event("system_shutdown_request", audit_event))

# AFTER:
# Store task reference to prevent GC
_audit_task = asyncio.create_task(audit_service.log_event("system_shutdown_request", audit_event))
# Note: Using _ prefix to indicate we're intentionally not awaiting
```

### 1.2 Fix Log Injection VULNERABILITY
**File**: `ciris_engine/logic/adapters/api/routes/wa.py:182`
**Issue**: User-controlled data in logs
```python
# BEFORE:
safe_deferral_id = ''.join(c if c.isprintable() and c not in '\n\r\t' else ' ' for c in deferral_id)
logger.error(f"Failed to resolve deferral {safe_deferral_id}: {e}")

# AFTER:
import hashlib
deferral_hash = hashlib.sha256(deferral_id.encode()).hexdigest()[:8]
logger.error(f"Failed to resolve deferral [id_hash:{deferral_hash}]: {e}")
```

## Priority 2: Improve Test Coverage (52.5% → 80%) - Est. 4-6 hours

### 2.1 Identify Uncovered Files
Run coverage analysis to find critical uncovered files:
```bash
pytest --cov=ciris_engine --cov-report=term-missing tests/ | grep "0%"
```

### 2.2 Focus Areas for Testing
Based on recent changes, prioritize:
1. **system_context.py** - Recently modified, needs tests
2. **config_security.py** - Security critical, recently modified
3. **tsdb_consolidation/** - New typed models need testing
4. **audit_dict_any_usage.py** - New tool needs tests

### 2.3 Test Implementation Strategy
Create test files:
- `tests/test_system_context.py`
- `tests/test_config_security.py`
- `tests/test_tsdb_models.py`
- `tests/tools/test_audit_dict_any.py`

## Priority 3: Fix Critical Code Smells (10 issues) - Est. 2-3 hours

### 3.1 Extract Constants (2 quick wins)
**Files to fix**:
- `auth.py:241` - Extract OAuth path constant
- `auth.py:512` - Extract provider template constant

### 3.2 Reduce Cognitive Complexity (8 issues)
**Strategy**: Extract methods pattern

#### Example Refactoring Pattern:
```python
# BEFORE: Complex single method
def process_request(self, request):
    # 50+ lines of nested logic
    if condition1:
        # complex logic block A
        if subcondition:
            # more logic
    elif condition2:
        # complex logic block B
    # etc...

# AFTER: Extracted methods
def process_request(self, request):
    if condition1:
        return self._handle_condition1(request)
    elif condition2:
        return self._handle_condition2(request)

def _handle_condition1(self, request):
    # logic block A

def _handle_condition2(self, request):
    # logic block B
```

### Files to Refactor (by priority):
1. `dependencies/auth.py:28` - Complexity 28 → 15
2. `discord_adapter.py:745` - Complexity 27 → 15
3. `routes/agent.py:127` - Complexity 22 → 15
4. `cli_adapter.py:201` - Complexity 26 → 15
5. `tsdb_consolidation/service.py:262` - Complexity 20 → 15

## Implementation Plan

### Phase 1: Quick Fixes (30 min) ✅
- [ ] Fix async task GC bug
- [ ] Fix log injection vulnerability
- [ ] Commit and push fixes

### Phase 2: Constants Extraction (30 min) ✅
- [ ] Extract OAuth path constant
- [ ] Extract provider template constant
- [ ] Extract other duplicate literals
- [ ] Commit and push fixes

### Phase 3: Test Coverage Sprint (4-6 hours) 📈
- [ ] Write tests for system_context.py
- [ ] Write tests for config_security.py
- [ ] Write tests for tsdb models
- [ ] Write tests for audit tool
- [ ] Run coverage report
- [ ] Commit and push tests

### Phase 4: Complexity Reduction (2-3 hours) 🔧
- [ ] Refactor auth dependencies
- [ ] Refactor Discord adapter methods
- [ ] Refactor API agent routes
- [ ] Commit and push refactors

## Success Metrics

### Immediate Goal (Phase 1-2):
- **Reliability Rating**: 3 → 1 ✅
- **Security Rating**: 2 → 1 ✅
- **Quality Gate**: Still failing (due to coverage)

### Short-term Goal (Phase 3):
- **Coverage**: 52.5% → 80%+ ✅
- **Quality Gate**: PASSING ✅

### Long-term Goal (Phase 4):
- **Code Smells**: 575 → <500
- **Cognitive Complexity**: All functions ≤ 15
- **Maintainability**: A rating

## Commands for Verification

```bash
# Check quality gate
python tools/sonar.py quality-gate

# Check specific issues
python tools/sonar.py list --severity CRITICAL --limit 10

# Check coverage
python tools/sonar.py coverage --new-code

# Run tests with coverage
pytest --cov=ciris_engine --cov-report=html tests/

# View coverage report
open htmlcov/index.html
```

## Expected Timeline

- **Phase 1-2**: 1 hour (immediate)
- **Phase 3**: 4-6 hours (same day)
- **Phase 4**: 2-3 hours (next day)

**Total**: 7-10 hours to GREEN quality gate

## Notes

1. The BUG and VULNERABILITY are the only issues affecting reliability/security ratings
2. Coverage is the main blocker for quality gate
3. Code smells don't affect quality gate but impact maintainability
4. Focus on NEW code coverage (files changed recently)
