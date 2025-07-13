# Graph Services Protocol Alignment Refactoring

## Summary of Changes

### 1. MemoryService (`ciris_engine/logic/services/graph/memory_service.py`)
- **Protocol Update**: Fixed `recall_timeseries` signature in MemoryServiceProtocol to include `start_time` and `end_time` parameters
- **File**: `ciris_engine/protocols/services/graph/memory.py`
  - Added `datetime` import
  - Updated method signature to match implementation

### 2. GraphConfigService (`ciris_engine/logic/services/graph/config_service.py`)
- **No changes needed**: Already properly aligned with protocol

### 3. TelemetryService (`ciris_engine/logic/services/graph/telemetry_service.py`)
- **No changes needed**: `_set_service_registry` is already private

### 4. AuditService (`ciris_engine/logic/services/graph/audit_service.py`)
- **Service Update**: Changed `set_service_registry` to `_set_service_registry` (made private)
- **Protocol Update**: Removed `set_service_registry` from AuditServiceProtocol
- **Caller Update**: Updated `service_initializer.py` to call `_set_service_registry`

### 5. IncidentManagementService (`ciris_engine/logic/services/graph/incident_service.py`)
- **Protocol Update**: Removed all private methods from IncidentManagementServiceProtocol
- **Service Update**: Added missing `get_service_type()` method returning `ServiceType.INCIDENT_MANAGEMENT`

### 6. TSDBConsolidationService (`ciris_engine/logic/services/graph/tsdb_consolidation/service.py`)
- **Service Update**: Added missing `get_service_type()` method returning `ServiceType.TSDB_CONSOLIDATION`
- **No protocol changes needed**: `_set_service_registry` is already private

## Files Modified

1. `/home/emoore/CIRISAgent/ciris_engine/protocols/services/graph/memory.py`
2. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/audit_service.py`
3. `/home/emoore/CIRISAgent/ciris_engine/protocols/services/graph/audit.py`
4. `/home/emoore/CIRISAgent/ciris_engine/protocols/services/graph/incident_management.py`
5. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/incident_service.py`
6. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/tsdb_consolidation/service.py`
7. `/home/emoore/CIRISAgent/ciris_engine/logic/runtime/service_initializer.py`

## Verification

All graph service specific mypy errors have been resolved. The refactoring ensures:
- All dependency injection methods are private (prefixed with `_`)
- All public methods in services are declared in their protocols
- No backwards compatibility concerns (pre-beta software)
- Type safety is maintained throughout