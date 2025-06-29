# Service Registry Attribute Fixes

## Summary
Fixed all `attr-defined` errors related to `_set_service_registry` and `_service_registry` attributes.

## Changes Made

### 1. Fixed IncidentService Memory Bus Access
**File**: `ciris_engine/logic/services/graph/incident_service.py`
- Changed `self._memory_bus._service_registry` to `self._memory_bus.service_registry`
- Buses expose `service_registry` as a public property, not `_service_registry`

### 2. Fixed GraphTelemetryService Registry Method Calls
**Files**: 
- `ciris_engine/logic/processors/states/dream_processor.py`
- `ciris_engine/logic/services/adaptation/self_configuration.py`

- Changed `telemetry_service.set_service_registry()` to `telemetry_service._set_service_registry()`
- GraphTelemetryService has `_set_service_registry` as a private method

### 3. Fixed SelfConfigurationService Registry Method Call
**File**: `ciris_engine/logic/processors/states/dream_processor.py`
- Changed `self_config_service.set_service_registry()` to `self_config_service._set_service_registry()`
- SelfConfigurationService has `_set_service_registry` as a private method

### 4. Fixed AuditService Type Override
**File**: `ciris_engine/logic/services/graph/audit_service.py`
- Changed parameter type from `registry: 'ServiceRegistry'` to `registry: object`
- Added runtime type check to match protocol definition
- Protocol defines `registry: object` for flexibility

## Results
- All `_service_registry` related mypy errors fixed
- No more "has no attribute '_service_registry'" errors
- No more "has no attribute 'set_service_registry'" errors
- Audit service now properly implements its protocol

## Key Learnings
1. Buses expose `service_registry` as a public property
2. Some services use `_set_service_registry` (private) instead of `set_service_registry`
3. Protocol compliance requires matching parameter types exactly
4. Runtime type checks can be used when protocols use `object` type