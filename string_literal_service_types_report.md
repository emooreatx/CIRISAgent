# Service Type String Literal Usage Report

This report identifies all locations where `service_type` is being passed as a string literal instead of using the `ServiceType` enum from `ciris_engine.schemas.foundational_schemas_v1`.

## ServiceType Enum Values

The `ServiceType` enum has the following values:
- `COMMUNICATION = "communication"`
- `TOOL = "tool"`
- `WISE_AUTHORITY = "wise_authority"`
- `MEMORY = "memory"`
- `AUDIT = "audit"`
- `LLM = "llm"`
- `TELEMETRY = "telemetry"`
- `ORCHESTRATOR = "orchestrator"`
- `SECRETS = "secrets"`
- `FILTER = "filter"`
- `CONFIG = "config"`
- `MAINTENANCE = "maintenance"`

## Files with String Literal Usage

### 1. `/home/emoore/CIRISAgent/ciris_engine/faculties/faculty_manager.py`
- **Lines 24, 54, 84, 135**: Uses `"llm"` instead of `ServiceType.LLM`
  ```python
  # Line 24
  return await self.service_registry.get_service(self.__class__.__name__, "llm")
  ```

### 2. `/home/emoore/CIRISAgent/ciris_engine/action_handlers/ponder_handler.py`
- **Line 84**: Uses `"action_handler"` (Note: This is not a valid ServiceType enum value)
  ```python
  defer_handler = await self.service_registry.get_service(
      self.__class__.__name__,
      "action_handler"
  )
  ```

### 3. `/home/emoore/CIRISAgent/ciris_engine/adapters/cirisnode_client.py`
- **Line 60**: Uses `"audit"` instead of `ServiceType.AUDIT`
  ```python
  self._audit_service = await self.service_registry.get_service(
      self.__class__.__name__,
      "audit",
      required_capabilities=["log_action"],
      fallback_to_global=True,
  )
  ```

## Pattern Analysis

Based on the grep results, there are approximately:
- 33 files with `service_type="..."` patterns
- 4 files with `get_service(..., "...")` patterns
- 80 files with string literals matching service type values

## Recommended Fix

All occurrences should be updated to use the `ServiceType` enum:

```python
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType

# Instead of:
await self.service_registry.get_service(self.__class__.__name__, "llm")

# Use:
await self.service_registry.get_service(self.__class__.__name__, ServiceType.LLM)
```

## Special Cases

1. **"action_handler"** in `ponder_handler.py` - This is not a valid `ServiceType` enum value. This needs investigation to determine the correct service type or if a new enum value needs to be added.

2. Test files may need special consideration as they might be testing the string literal handling intentionally.
