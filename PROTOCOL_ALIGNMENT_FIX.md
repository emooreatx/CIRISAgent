# Protocol Alignment Fix Plan

## Summary
- **Total Services**: 19
- **Aligned**: 5 (26%)
- **Misaligned**: 14 (74%)

## Key Issues

### 1. Extra Methods Not in Protocol
Many services have public methods that aren't defined in their protocols:
- **AuditService**: `query_audit_trail_legacy`
- **ShutdownService**: `wait_for_shutdown_async`, `wait_for_shutdown`, `emergency_shutdown`
- **TimeService**: `get_uptime`
- **RuntimeControlService**: `get_retry_config`, `health_check`, `retry_with_backoff`
- **TelemetryService**: `get_metric_count`, `get_telemetry_summary`

### 2. Dict[str, Any] Usage
Several services still use untyped dicts:
- **AuditService**: Line 484
- **RuntimeControlService**: Line 74

## Fix Strategy

### Option 1: Update Protocols (Recommended)
Add missing methods to protocols to match implementations:

```python
# Example: TelemetryServiceProtocol
class TelemetryServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for telemetry service."""
    
    # Existing methods...
    
    @abstractmethod
    async def get_metric_count(self) -> int:
        """Get total metric count."""
        ...
    
    @abstractmethod
    async def get_telemetry_summary(self) -> TelemetrySummary:
        """Get telemetry summary."""
        ...
```

### Option 2: Make Extra Methods Private
Prefix extra methods with `_` to make them private:
- `query_audit_trail_legacy` → `_query_audit_trail_legacy`
- `get_metric_count` → `_get_metric_count`

### Option 3: Remove Extra Methods
Delete methods not needed by protocol consumers.

## Mypy Errors Related to Protocols

### TelemetryService record_metric
The protocol expects:
```python
async def record_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
```

But implementations are missing the `handler_name` parameter that MemoryBus requires.

### Fix Implementation Plan

1. **Enhance Protocol Analyzer**
   - Add parameter signature checking
   - Validate return types match exactly
   - Check async/sync consistency

2. **Create Protocol Alignment Fixer**
   - Auto-add missing methods to protocols
   - Update method signatures to match
   - Convert Dict[str, Any] to proper schemas

3. **Systematic Fix Process**
   - Run analyzer to identify all mismatches
   - Generate protocol updates
   - Update implementations to match
   - Validate with mypy

## Quick Wins

1. **TelemetryService**
   - Add `handler_name` parameter to protocol
   - Add missing methods to protocol

2. **AuditService**
   - Replace Dict[str, Any] with proper schema
   - Add legacy method to protocol or make private

3. **ShutdownService**
   - Add async methods to protocol
   - Document emergency shutdown in protocol

## Implementation

### Step 1: Update TelemetryServiceProtocol
```python
@abstractmethod
async def record_metric(
    self, 
    metric_name: str, 
    value: float, 
    tags: Optional[Dict[str, str]] = None,
    handler_name: str = "telemetry"  # Add this
) -> None:
    """Record a telemetry metric."""
    ...
```

### Step 2: Fix Dict[str, Any] Usage
```python
# Instead of:
attrs: Dict[str, Any] = {}

# Use:
from ciris_engine.schemas.services.graph_core import GraphNodeAttributes
attrs = GraphNodeAttributes()
```

### Step 3: Protocol Compliance Script
Create a script to automatically:
1. Find all protocol mismatches
2. Generate protocol updates
3. Update implementations
4. Run mypy to verify

## Expected Results

After fixes:
- 100% protocol alignment
- Zero Dict[str, Any] usage
- All mypy protocol errors resolved
- Clear parameter alignment