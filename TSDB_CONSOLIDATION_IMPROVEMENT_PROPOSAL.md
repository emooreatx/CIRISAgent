# TSDB Consolidation Service Improvement Proposal

## Executive Summary

The TSDB Consolidation Service failed at the midnight UTC window due to a parameter mismatch between the service implementation and the MemoryBus interface. This proposal outlines systematic improvements to ensure reliable operation at the next 06:00 UTC window.

## Current Issues

### 1. Critical: Parameter Mismatch
- **Issue**: MemoryBus methods (`recall`, `memorize`, `forget`) require a `handler_name` parameter
- **Impact**: TypeError prevents consolidation from running
- **Root Cause**: Removed `handler_name` parameters without understanding the MemoryBus interface

### 2. Type Safety Issues (from mypy)
- Missing positional arguments in 22 locations
- Type mismatches with GraphNode attributes indexing
- Return type mismatches (GraphNode vs TSDBSummary)

### 3. No Integration Tests
- Unit tests use mocks extensively
- No tests verify actual MemoryBus integration
- No tests for the 6-hour scheduling mechanism

### 4. Insufficient Logging
- No pre-consolidation health checks
- Limited error context when failures occur
- No metrics on consolidation performance

## Proposed Improvements

### Phase 1: Immediate Fix (Before 06:00 UTC)

#### 1.1 Restore handler_name Parameters
```python
# Add back handler_name to all MemoryBus calls
summaries = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
result = await self._memory_bus.memorize(node=summary.to_graph_node(), handler_name="tsdb_consolidation")
result = await self._memory_bus.forget(node=node, handler_name="tsdb_consolidation")
```

#### 1.2 Add Pre-consolidation Health Check
```python
async def _verify_consolidation_ready(self) -> bool:
    """Verify all dependencies are ready before consolidation."""
    if not self._memory_bus:
        logger.error("Memory bus not available")
        return False
    
    if not self._time_service:
        logger.error("Time service not available")
        return False
    
    # Test memory bus operations
    try:
        test_query = MemoryQuery(
            node_id="health_check_*",
            type=NodeType.TSDB_SUMMARY,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )
        await self._memory_bus.recall(test_query, handler_name="tsdb_consolidation")
        logger.info("Memory bus health check passed")
        return True
    except Exception as e:
        logger.error(f"Memory bus health check failed: {e}")
        return False
```

#### 1.3 Enhanced Error Handling
```python
async def _run_consolidation(self) -> None:
    """Run a single consolidation cycle with enhanced error handling."""
    try:
        logger.info("Starting TSDB consolidation cycle")
        
        # Pre-flight checks
        if not await self._verify_consolidation_ready():
            logger.error("Pre-consolidation checks failed, skipping cycle")
            return
        
        # Log consolidation parameters
        logger.info(f"Consolidation parameters: interval={self._consolidation_interval}, retention={self._raw_retention}")
        
        # Existing consolidation logic with detailed logging...
```

### Phase 2: Type Safety Improvements

#### 2.1 Fix GraphNode Attribute Access
```python
# Replace direct indexing with safe access
if isinstance(node.attributes, dict):
    content_preview = f": {node.attributes.get('value', 'N/A')}..."
elif hasattr(node.attributes, 'value'):
    content_preview = f": {node.attributes.value}..."
else:
    content_preview = ""
```

#### 2.2 Fix Return Type Mismatches
```python
async def _consolidate_metrics(self, period_start: datetime, period_end: datetime) -> Optional[TSDBSummary]:
    # ... existing logic ...
    if self._memory_bus:
        result = await self._memory_bus.memorize(
            node=summary.to_graph_node(), 
            handler_name="tsdb_consolidation"
        )
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store summary: {result.error}")
            return None
        return summary  # Return TSDBSummary, not GraphNode
```

### Phase 3: Testing Improvements

#### 3.1 Integration Test Suite
```python
# tests/integration/test_tsdb_consolidation_integration.py
@pytest.mark.integration
async def test_tsdb_consolidation_with_real_memory_bus():
    """Test TSDB consolidation with actual MemoryBus."""
    # Setup real services
    time_service = TimeService()
    memory_service = LocalGraphMemoryService(time_service=time_service)
    service_registry = ServiceRegistry()
    service_registry.register(memory_service)
    
    memory_bus = MemoryBus(service_registry, time_service)
    tsdb_service = TSDBConsolidationService(
        memory_bus=memory_bus,
        time_service=time_service
    )
    
    # Create test data
    # Run consolidation
    # Verify results
```

#### 3.2 Scheduling Test
```python
async def test_consolidation_scheduling():
    """Test that consolidation runs at correct 6-hour boundaries."""
    mock_time = MockTimeService()
    # Set time to 23:55 UTC
    mock_time.set_time(datetime(2025, 7, 8, 23, 55, 0, tzinfo=timezone.utc))
    
    service = TSDBConsolidationService(time_service=mock_time)
    next_run = service._calculate_next_run_time()
    
    assert next_run == datetime(2025, 7, 9, 0, 0, 0, tzinfo=timezone.utc)
```

### Phase 4: Monitoring & Observability

#### 4.1 Consolidation Metrics
```python
async def _emit_consolidation_metrics(self, success: bool, duration_ms: float, nodes_processed: int):
    """Emit metrics about consolidation performance."""
    await self._memory_bus.memorize_metric(
        metric_name="tsdb.consolidation.completed",
        value=1.0 if success else 0.0,
        tags={
            "success": str(success),
            "duration_ms": str(duration_ms),
            "nodes_processed": str(nodes_processed)
        },
        scope="local",
        handler_name="tsdb_consolidation"
    )
```

#### 4.2 Health Endpoint
Add consolidation status to `/v1/system/health`:
```json
{
  "tsdb_consolidation": {
    "last_run": "2025-07-08T00:01:20Z",
    "last_status": "failed",
    "last_error": "TypeError: Missing handler_name",
    "next_scheduled": "2025-07-08T06:00:00Z",
    "nodes_pending": 1523,
    "summaries_created_today": 0
  }
}
```

### Phase 5: Operational Procedures

#### 5.1 Manual Consolidation Trigger
Add API endpoint for manual consolidation:
```python
@router.post("/v1/system/tsdb/consolidate")
async def trigger_consolidation(auth: AuthRequired):
    """Manually trigger TSDB consolidation."""
    if auth.role != "SYSTEM_ADMIN":
        raise HTTPException(403, "System admin required")
    
    result = await tsdb_service.consolidate_now()
    return {"status": "started", "task_id": result.task_id}
```

#### 5.2 Consolidation Status Query
```python
@router.get("/v1/system/tsdb/status")
async def get_consolidation_status():
    """Get detailed TSDB consolidation status."""
    return {
        "service_healthy": await tsdb_service.is_healthy(),
        "last_consolidation": tsdb_service.get_last_consolidation_info(),
        "pending_periods": await tsdb_service.get_pending_periods(),
        "next_scheduled": tsdb_service.get_next_scheduled_time()
    }
```

## Implementation Plan

### Immediate Actions (Before 06:00 UTC)
1. **Fix handler_name parameters** (30 minutes)
   - Add back all handler_name parameters
   - Test with mock to verify signatures
   
2. **Add health checks** (20 minutes)
   - Implement _verify_consolidation_ready()
   - Add to _run_consolidation()
   
3. **Deploy and monitor** (10 minutes)
   - Rebuild container
   - Deploy
   - Monitor logs for successful start

### Follow-up Actions (After successful consolidation)
1. Fix all mypy type errors
2. Implement integration tests
3. Add monitoring metrics
4. Create operational runbook

## Success Criteria

1. **Immediate**: Consolidation successfully runs at 06:00 UTC
2. **Short-term**: Zero mypy errors in tsdb_consolidation_service.py
3. **Medium-term**: 90% test coverage including integration tests
4. **Long-term**: 99.9% consolidation success rate over 30 days

## Risk Mitigation

1. **Rollback Plan**: Keep current container running until new one is verified
2. **Data Safety**: Consolidation only marks nodes, doesn't delete immediately
3. **Manual Recovery**: Document SQL queries to manually consolidate if needed

## Appendix: Quick Fix Script

```bash
#!/bin/bash
# quick_fix_tsdb.sh
# Restore handler_name parameters to all MemoryBus calls

cd /home/emoore/CIRISAgent

# Backup current file
cp ciris_engine/logic/services/graph/tsdb_consolidation_service.py{,.backup}

# Fix recall calls
sed -i 's/await self\._memory_bus\.recall(query)/await self._memory_bus.recall(query, handler_name="tsdb_consolidation")/g' ciris_engine/logic/services/graph/tsdb_consolidation_service.py

# Fix memorize calls
sed -i 's/await self\._memory_bus\.memorize(node=/await self._memory_bus.memorize(node=/g' ciris_engine/logic/services/graph/tsdb_consolidation_service.py
sed -i 's/memorize(node=\([^)]*\))/memorize(node=\1, handler_name="tsdb_consolidation")/g' ciris_engine/logic/services/graph/tsdb_consolidation_service.py

# Fix forget calls
sed -i 's/await self\._memory_bus\.forget(node=/await self._memory_bus.forget(node=/g' ciris_engine/logic/services/graph/tsdb_consolidation_service.py
sed -i 's/forget(node=\([^)]*\))/forget(node=\1, handler_name="tsdb_consolidation")/g' ciris_engine/logic/services/graph/tsdb_consolidation_service.py

# Run mypy to verify
mypy ciris_engine/logic/services/graph/tsdb_consolidation_service.py | grep "Missing positional argument"
```