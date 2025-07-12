# CIRIS MyPy Error Fix Action Plan

## Overview
This action plan provides a systematic approach to fixing the 639 mypy errors in the CIRIS codebase using the `ciris_mypy_toolkit` and targeted manual fixes.

## Error Statistics
- **Total Errors**: 639 (mypy direct count)
- **Toolkit Detected**: 423 (likely excluding some error types)
- **Schema Issues**: 1,437
- **Protocol Violations**: 6
- **Unused Code**: 2,406 items

## Priority Fix Order

### Phase 1: Quick Wins (Day 1)
**Target: -150 errors**

1. **Remove Unreachable Code (109 errors)**
   ```bash
   # Find all unreachable code
   mypy ciris_engine/ --ignore-missing-imports --show-error-codes 2>&1 | grep "unreachable" > unreachable_errors.txt
   ```
   - Remove code after return statements
   - Fix control flow issues
   - Remove dead branches

2. **Remove Unused type:ignore Comments (15 errors)**
   ```bash
   # Find unused ignores
   mypy ciris_engine/ --ignore-missing-imports --show-error-codes 2>&1 | grep "unused-ignore" > unused_ignores.txt
   ```
   - Simply remove these comments

3. **Fix Simple Type Annotations (50 errors)**
   - Add `-> None` to functions without return
   - Add parameter types to __init__ methods
   - Fix obvious type annotations

### Phase 2: Import & Attribute Fixes (Day 1-2)
**Target: -200 errors**

1. **Fix Missing Imports (92 attr-defined errors)**
   Common patterns found:
   - `ResourceUsage` missing from resources_core
   - `NodeType.CORRELATION` doesn't exist
   - `EpistemicFaculty.evaluate` method missing
   - `Priority` enum import issues

2. **Fix Module References**
   - Update import paths
   - Add missing exports to __init__.py files
   - Fix circular import issues

### Phase 3: Type Safety (Day 2)
**Target: -150 errors**

1. **Fix Union Attribute Access (59 errors)**
   ```python
   # Before
   if optional_value:
       optional_value.method()  # Error: might be None
   
   # After
   if optional_value is not None:
       optional_value.method()  # Proper type narrowing
   ```

2. **Fix Function Arguments (61 errors)**
   - Align calls with signatures
   - Fix parameter order
   - Add missing required arguments

3. **Fix Assignment Issues (55 errors)**
   ```python
   # Common pattern - fix None assignments
   # Before
   created_at: datetime = None  # Error
   
   # After
   created_at: Optional[datetime] = None
   ```

### Phase 4: Schema Alignment (Day 2-3)
**Target: -1000+ schema issues**

1. **Update to V1 Schemas**
   ```bash
   python -m ciris_mypy_toolkit propose --categories schema_alignment
   ```

2. **Replace Dict[str, Any] Usage**
   - Convert to proper Pydantic models
   - Add validation everywhere
   - Use TypedDict where appropriate

### Phase 5: Cleanup (Day 3)
**Target: -2000+ unused items**

1. **Remove Unused Code**
   ```bash
   python -m ciris_mypy_toolkit propose --categories unused_code_removal
   ```

2. **Clean Imports**
   - Remove unused imports
   - Organize imports properly

## Automation Commands

### 1. Generate Complete Analysis
```bash
# Full compliance report
python -m ciris_mypy_toolkit report --output full_compliance_report.md

# Check protocol alignment
python -m ciris_mypy_toolkit check-protocols --output protocol_report.json
```

### 2. Generate Fix Proposals
```bash
# Type annotations
python -m ciris_mypy_toolkit propose --categories type_annotations --output type_fixes.json

# Schema alignment
python -m ciris_mypy_toolkit propose --categories schema_alignment --output schema_fixes.json

# All categories
python -m ciris_mypy_toolkit propose \
  --categories type_annotations \
  --categories schema_alignment \
  --categories protocol_compliance \
  --categories unused_code_removal \
  --output all_fixes.json
```

### 3. Apply Approved Fixes
```bash
# Review the proposal first!
cat all_fixes.json

# Apply after review
python -m ciris_mypy_toolkit execute --target all_fixes.json
```

## Manual Fix Patterns

### Pattern 1: Unreachable Code
```python
# Find pattern
if condition:
    return value
    unreachable_code()  # Remove this

# Or restructure
def method():
    if error:
        return None
    else:
        # Move code here
        pass
```

### Pattern 2: Optional Type Narrowing
```python
# Use type guards
from typing import Optional

def process(value: Optional[str]) -> str:
    if value is None:
        return "default"
    # mypy knows value is str here
    return value.upper()
```

### Pattern 3: Protocol Implementation
```python
# Ensure all protocol methods exist
class MyService(ServiceProtocol):
    async def initialize(self) -> None:  # Required by protocol
        pass
    
    async def shutdown(self) -> None:  # Required by protocol
        pass
```

## Verification Steps

After each phase:
```bash
# Count remaining errors
mypy ciris_engine/ --ignore-missing-imports 2>&1 | grep -c "error:"

# Check specific error types
mypy ciris_engine/ --ignore-missing-imports --show-error-codes 2>&1 | \
  grep -E "\[.*\]$" | sed 's/.*\[\(.*\)\]$/\1/' | sort | uniq -c | sort -rn

# Run tests to ensure nothing broke
pytest tests/ -v
```

## Success Criteria

1. **Phase 1**: 490 errors remaining (-150)
2. **Phase 2**: 290 errors remaining (-200)
3. **Phase 3**: 140 errors remaining (-150)
4. **Phase 4**: Near 0 mypy errors
5. **Phase 5**: Clean, maintainable codebase

## Notes

- The toolkit seems to have limitations in detecting all mypy errors
- Manual intervention required for complex type issues
- Schema alignment is the biggest task
- Consider running fixes in a separate branch
- Test thoroughly after each phase

## Emergency Rollback

If fixes break functionality:
```bash
# Revert all changes
git checkout -- ciris_engine/

# Or revert specific files
git checkout -- ciris_engine/path/to/file.py
```