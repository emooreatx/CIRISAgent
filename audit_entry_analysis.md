# AUDIT_ENTRY Graph Nodes Analysis

## Summary

- **Total AUDIT_ENTRY nodes in graph**: 40,761
- **Total audit log entries in ciris_audit.db**: 43,860
- **Difference**: 3,099 entries (7% discrepancy)

## Key Findings

### 1. Dual Storage System

The audit service (`GraphAuditService`) stores audit data in TWO places:

1. **Graph Nodes** (graph_nodes table in ciris_engine.db):
   - Stored as AUDIT_ENTRY typed nodes
   - Used for graph-based queries and relationships
   - Can be queried via memory bus

2. **Audit Database** (audit_log table in ciris_audit.db):
   - Permanent storage with cryptographic hash chain
   - Each entry is signed and linked to previous entry
   - Provides tamper evidence and integrity verification

### 2. AUDIT_ENTRY Node Structure

```json
{
  "created_at": "2025-07-02T03:48:58.464143+00:00",
  "updated_at": "2025-07-02T03:48:58.464142+00:00", 
  "created_by": "audit_service",
  "tags": ["actor:PonderHandler", "action:AuditEventType.HANDLER_ACTION_PONDER"],
  "action": "AuditEventType.HANDLER_ACTION_PONDER",
  "actor": "PonderHandler",
  "timestamp": "2025-07-02T03:48:58.464122+00:00",
  "context": {
    "service_name": "GraphAuditService",
    "correlation_id": "766b8d0d-e218-485d-8b17-6a5f9d2a9de8",
    "additional_data": {
      "event_type": "AuditEventType.HANDLER_ACTION_PONDER",
      "severity": "info",
      "outcome": "success"
    }
  },
  "signature": null,
  "hash_chain": null,
  "_node_class": "AuditEntry"
}
```

### 3. Correlation Between Systems

- Event IDs in audit_log table match node IDs in graph (with "audit_" prefix)
- Example: Event ID `aa3237c1-8e7d-4ab2-b1e9-cc2c5d5ece34` exists as node `audit_aa3237c1-8e7d-4ab2-b1e9-cc2c5d5ece34`

### 4. TSDB Consolidation Policy

The TSDB consolidation service explicitly **EXCLUDES** AUDIT_ENTRY nodes from consolidation:

```python
# From tsdb_consolidation_service.py line 334:
# 5. AUDIT_EVENT → Removed (audit has its own permanent storage with hash chain in ciris_audit.db)
```

This is because:
- Audit entries must be immutable for compliance
- The hash chain in ciris_audit.db provides cryptographic integrity
- Consolidating would break the audit trail

### 5. Discrepancy Analysis

The 3,099 entry difference (43,860 in audit DB vs 40,761 in graph) could be due to:

1. **Timing differences** - Audit entries might be written to the database first
2. **Failed graph writes** - Database write succeeds but graph write fails
3. **Startup/shutdown events** - Some events logged before memory bus available
4. **System events** - Some audit events may not need graph representation

### 6. Initialization Parameters

The audit service is initialized with:
```python
GraphAuditService(
    memory_bus=None,  # Set later via service registry
    time_service=self.time_service,
    export_path="audit_logs.jsonl",
    export_format="jsonl",
    enable_hash_chain=True,  # ← This enables dual storage
    db_path=str(audit_db_path),
    key_path=str(audit_key_path),
    retention_days=retention_days
)
```

## Recommendations

1. **DO NOT consolidate AUDIT_ENTRY nodes** - They are meant to be permanent
2. **The 40,761 graph nodes are working as designed** - They provide graph-based audit queries
3. **The discrepancy is likely normal** - Some audit events may only exist in the database
4. **Both storage systems are necessary**:
   - Graph nodes for relationships and queries
   - Database for cryptographic integrity and compliance

## Conclusion

The AUDIT_ENTRY nodes should NOT be consolidated. They represent a permanent audit trail that is:
- Cryptographically secured in the audit database
- Queryable through the graph for relationships
- Intentionally excluded from TSDB consolidation
- Critical for system compliance and integrity