# TSDB Consolidation Testing Plan

## Overview
This document outlines a comprehensive testing strategy for the TSDB consolidation system, which is critical for long-term operations and data integrity.

## Test Categories

### 1. Unit Tests for Daily Summary Creation

#### Test: Basic to Daily Consolidation
- **Purpose**: Verify that 4 basic summaries (00:00, 06:00, 12:00, 18:00) consolidate into 1 daily summary
- **Scenarios**:
  - Full day with all 4 summaries
  - Partial day with 2-3 summaries
  - Single summary day
  - Missing summaries (gaps in data)
- **Validation**:
  - Correct aggregation of metrics (sum, min, max, avg)
  - Proper resource totals (tokens, cost, carbon, energy)
  - Action counts are summed correctly
  - Period labels are accurate

#### Test: Multi-Type Consolidation
- **Purpose**: Verify all summary types are consolidated
- **Types**: tsdb_summary, audit_summary, trace_summary, conversation_summary, task_summary
- **Validation**:
  - Each type gets its own daily summary
  - Type-specific attributes are preserved
  - Node IDs follow pattern: `{type}_daily_{YYYYMMDD}`

### 2. Unit Tests for Edge Creation

#### Test: Temporal Edge Creation
- **Purpose**: Verify previous/next day edges
- **Scenarios**:
  - Sequential days (Mon→Tue→Wed)
  - Gap in days (Mon→Wed, missing Tue)
  - Single day (no prev/next)
  - Week boundaries
- **Validation**:
  - TEMPORAL_PREV points to previous day
  - TEMPORAL_NEXT points to next day
  - `days_apart` attribute is correct
  - No duplicate edges (INSERT OR IGNORE works)

#### Test: Same-Day Cross-Type Edges
- **Purpose**: Verify edges between different summary types on same day
- **Scenarios**:
  - All 5 types present (10 edges: 5C2)
  - Partial types (2-3 types)
  - Single type (no cross edges)
- **Validation**:
  - SAME_DAY_SUMMARY relationship
  - Correct source/target types in attributes
  - Date attribute matches
  - No self-edges

### 3. Unit Tests for Cleanup Logic

#### Test: Basic Summary Cleanup
- **Purpose**: Verify basic summaries are deleted after retention period
- **Scenarios**:
  - Summaries older than 7 days with daily consolidation
  - Summaries without consolidation (should not delete)
  - Mixed consolidated/unconsolidated periods
- **Validation**:
  - Only consolidated periods are cleaned
  - Count verification (claimed vs actual)
  - Audit graph nodes cleaned (audit_log preserved)

#### Test: Raw Data Cleanup
- **Purpose**: Verify raw nodes are deleted after 24 hours
- **Scenarios**:
  - TSDB data nodes with summary
  - Service correlations with summary
  - Nodes without summary (should not delete)
- **Validation**:
  - Only summarized data is deleted
  - Non-summarized data is preserved
  - Cleanup respects retention periods

### 4. Integration Tests

#### Test: End-to-End Consolidation Flow
- **Purpose**: Test complete consolidation cycle
- **Flow**:
  1. Create test data for a week
  2. Run basic consolidation (6-hour)
  3. Run extensive consolidation (daily)
  4. Verify cleanup
  5. Check edges
- **Validation**:
  - Correct number of summaries created
  - All edges properly linked
  - Old data cleaned up
  - No data loss

#### Test: Calendar Alignment
- **Purpose**: Verify calendar-bound scheduling
- **Scenarios**:
  - Week crossing month boundary
  - Partial weeks at month start/end
  - Leap year handling
- **Validation**:
  - Monday-Sunday alignment
  - Correct period labels
  - No overlap or gaps

### 5. Edge Case Tests

#### Test: Duplicate Prevention
- **Purpose**: Verify no duplicate consolidations
- **Scenarios**:
  - Multiple consolidation runs
  - Concurrent consolidation attempts
  - Test vs production node conflicts
- **Validation**:
  - check_period_consolidated works
  - INSERT OR IGNORE prevents duplicate edges
  - Node IDs are unique

#### Test: Error Recovery
- **Purpose**: Test resilience to failures
- **Scenarios**:
  - Database connection failure mid-consolidation
  - Partial consolidation completion
  - Invalid data in summaries
- **Validation**:
  - Transaction rollback works
  - Partial data doesn't corrupt state
  - Next run recovers properly

## Test Implementation Strategy

### Phase 1: Unit Test Setup
1. Create test fixtures for different node types
2. Mock database connections
3. Create helper functions for data generation

### Phase 2: Core Logic Tests
1. Test period management (calendar calculations)
2. Test query manager (data retrieval)
3. Test consolidators (aggregation logic)
4. Test edge manager (relationship creation)

### Phase 3: Integration Tests
1. Set up test database
2. Create realistic test data
3. Run full consolidation cycles
4. Verify results

### Phase 4: Performance Tests
1. Test with large data volumes (100k+ nodes)
2. Measure consolidation time
3. Verify memory usage
4. Check database query performance

## Success Criteria

1. **Data Integrity**
   - No data loss during consolidation
   - All metrics accurately aggregated
   - Audit trail preserved

2. **Edge Correctness**
   - All temporal edges connect properly
   - Same-day relationships established
   - No orphaned nodes
   - No duplicate edges

3. **Performance**
   - Consolidation completes within 5 minutes
   - Memory usage under 1GB
   - Database queries optimized

4. **Reliability**
   - Handles edge cases gracefully
   - Recovers from failures
   - Idempotent operations

## Test Data Requirements

### Week of Data (July 7-13, 2025)
- 35,894 total nodes
- 19 basic summaries already created
- Mix of all node types
- Realistic metric values
- Complete audit trail

### Expected Results
- 7 daily summaries per type (35 total)
- 6 temporal edges per type (30 total)
- ~70 same-day cross-type edges
- Basic summaries cleaned after consolidation
- Raw data cleaned where appropriate

## Risk Mitigation

1. **Backup Strategy**
   - Full backup of data/ directory
   - Export audit log separately
   - Document current state

2. **Rollback Plan**
   - Restore from backup if issues
   - Identify failed consolidations
   - Manual cleanup if needed

3. **Monitoring**
   - Watch logs during consolidation
   - Check database size changes
   - Verify edge counts
   - Monitor memory usage

## Validation Tools

1. **db_status_tool.py**
   - Check consolidation summaries
   - Verify data coverage
   - Audit integrity check

2. **debug_tools.py**
   - Trace consolidation execution
   - Check handler metrics
   - Verify correlations

3. **SQL Queries**
   - Node counts by type
   - Edge relationships
   - Data gaps analysis

This comprehensive testing plan ensures the TSDB consolidation system is robust, reliable, and ready for production use.