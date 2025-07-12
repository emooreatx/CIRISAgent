# Audit Service Test Fix Summary

## Issue
Two tests were failing in the audit service test files:
- `test_audit_service_export_data` in `test_audit_service.py`
- `test_export_audit_data` in `test_audit_service_unit.py`

Both tests were failing with: `ValueError: Export path not configured`

## Root Cause
The `GraphAuditService.export_audit_data()` method requires an `export_path` to be configured during service initialization. This is a safety feature that prevents accidental exports to undefined locations.

In production, the service is initialized with `export_path="audit_logs.jsonl"`, but the test fixtures were not providing this parameter.

## Solution
Updated both test fixtures to provide a proper export path using temporary directories:

1. In `test_audit_service.py`:
   - Added `export_path` parameter to the fixture using a temporary directory
   - Fixed the test to use `"jsonl"` format instead of unsupported `"json"`

2. In `test_audit_service_unit.py`:
   - Added `export_path` parameter to the fixture

## Key Changes
```python
# Before
service = GraphAuditService(
    memory_bus=memory_bus,
    time_service=time_service,
    db_path=temp_db,
    enable_hash_chain=False
)

# After
export_path = os.path.join(temp_dir, "audit_export.jsonl")
service = GraphAuditService(
    memory_bus=memory_bus,
    time_service=time_service,
    db_path=temp_db,
    export_path=export_path,  # Now properly configured
    enable_hash_chain=False
)
```

## Benefits
- No backwards compatibility issues - this is a safety improvement
- Tests now properly validate the export functionality
- Prevents accidental exports to undefined locations in production
- Maintains the principle of explicit configuration

## Test Results
All 30 tests across both files are now passing successfully.