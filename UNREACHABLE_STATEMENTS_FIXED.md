# Fixed "Statement is unreachable" mypy Errors

## Summary
Successfully fixed all "Statement is unreachable" mypy errors in the ciris_engine codebase by removing dead code.

## Files Fixed

### 1. `/home/emoore/CIRISAgent/ciris_engine/logic/persistence/models/graph.py`
- **Issue**: Unreachable `else` branch after exhaustive type checks for `node.attributes`
- **Fix**: Removed unreachable `else` block since `Union[GraphNodeAttributes, Dict[str, Any]]` covers all cases

### 2. `/home/emoore/CIRISAgent/ciris_engine/logic/persistence/models/correlations.py`
- **Issue**: Unreachable `else` branch setting `timestamp_str = None` after checking if timestamp exists
- **Fix**: Removed redundant else block

### 3. `/home/emoore/CIRISAgent/ciris_engine/logic/buses/communication_bus.py`
- **Issue**: Unreachable `else` branch - messages from adapters are always dicts
- **Fix**: Removed isinstance check and else branch, directly convert all messages to FetchedMessage

### 4. `/home/emoore/CIRISAgent/ciris_engine/logic/services/lifecycle/scheduler.py`
- **Issue**: String handling code unreachable because type annotations specify datetime types
- **Fix**: Removed string parsing code for `defer_until`, `created_at`, and `last_triggered_at`

### 5. `/home/emoore/CIRISAgent/ciris_engine/logic/services/governance/wise_authority.py`
- **Issue**: Unreachable else branch after exhaustive enum checks
- **Fix**: Removed unreachable warning/return block, converted to else comment

### 6. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/telemetry_service.py`
- **Issue**: String check unreachable because TimeSeriesDataPoint.timestamp is always datetime
- **Fix**: Removed string parsing code, use datetime directly

### 7. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/incident_service.py`
- **Issue**: mypy false positive on conditional assignment
- **Fix**: Refactored to use ternary operator

### 8. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/memory_service.py`
- **Issue**: Unreachable else branch after exhaustive type checks (2 occurrences)
- **Fix**: Removed unreachable else blocks for attributes dict conversion

### 9. `/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/config_service.py`
- **Issue**: Unreachable else branch after exhaustive type checks for config value types
- **Fix**: Removed warning code for unexpected types

### 10. `/home/emoore/CIRISAgent/ciris_engine/logic/context/system_snapshot.py`
- **Issue**: Unreachable fallback in attrs.model_dump() ternary
- **Fix**: Removed fallback to empty dict since GraphNodeAttributes always has model_dump

### 11. `/home/emoore/CIRISAgent/ciris_engine/logic/runtime/service_initializer.py`
- **Issue**: Redundant None check after truthy check
- **Fix**: Removed duplicate None check for wa_auth_system

### 12. `/home/emoore/CIRISAgent/ciris_engine/logic/adapters/discord/adapter.py`
- **Issue**: Redundant isinstance check for typed parameter
- **Fix**: Removed isinstance check for DiscordMessage

### 13. `/home/emoore/CIRISAgent/ciris_engine/logic/adapters/cli/adapter.py`
- **Issue**: Redundant isinstance check for typed parameter
- **Fix**: Removed isinstance check for IncomingMessage

### 14. `/home/emoore/CIRISAgent/ciris_engine/logic/adapters/api/adapter.py`
- **Issue**: Redundant hasattr check after attribute assignment
- **Fix**: Removed hasattr check for message_channel_map

## Result
All "Statement is unreachable" mypy errors have been resolved. The codebase is now cleaner with no dead code paths.