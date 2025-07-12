# Config Service Type Safety Fix

## Summary
Fixed validation errors in the config service by removing incorrect usage of `MemoryQuery` objects. The config service was attempting to use a non-existent `filters` attribute on `MemoryQuery`, which was causing validation errors.

## Changes Made

### 1. **test_config_service.py**
- Added import for `MemoryQuery` from `ciris_engine.schemas.services.operations`

### 2. **config_service.py**
- Added import for `ConfigValue` from `ciris_engine.schemas.services.nodes`
- Removed misuse of `MemoryQuery` with non-existent `filters` attribute
- Simplified `query_graph()` method to just search for config nodes
- Added new `query_config_by_key()` method for key-based config queries
- Updated `get_config()` to use the new `query_config_by_key()` method
- Updated `list_configs()` to:
  - Return `Dict[str, ConfigValue]` instead of raw values
  - Use direct memory search instead of `query_graph()`
  - Properly handle node conversion and filtering

## Type Safety Improvements
This fix aligns with the "No Dicts" philosophy by:
- Removing attempts to add dynamic attributes to Pydantic models
- Using proper typed methods for querying configurations
- Ensuring all return types are properly typed (ConfigValue instead of Any)

## Test Results
All 17 tests in test_config_service.py are now passing, with no validation errors.