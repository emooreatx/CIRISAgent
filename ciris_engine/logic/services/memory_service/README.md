# Graph Memory Service

The memory service is the heart of CIRIS's "Identity as Graph" architecture. It provides a unified interface for storing, retrieving, and managing all agent memories, with the fundamental principle that **identity IS the graph**.

## Overview

The memory service implements three core operations - MEMORIZE, RECALL, and FORGET - with sophisticated scope-based permissions and integrated audit trails. All agent knowledge, from simple facts to complex relationships, is stored as nodes and edges in a graph structure.

## Key Concepts

### Everything is a Memory

In CIRIS, there's no distinction between:
- Configuration settings
- Learned knowledge  
- User preferences
- Behavioral patterns
- Identity attributes
- Temporal data (TSDB)

All are memories in the graph, differentiated only by their node types and relationships.

### Scope-Based Access Control

| Scope | Description | WA Approval Required | Use Cases |
|-------|-------------|---------------------|-----------|
| LOCAL | Agent-private memories | No | Personal learning, task context |
| ENVIRONMENT | Deployment-specific | Yes | Credentials, API endpoints |
| IDENTITY | Core identity changes | Yes | Capabilities, purpose, traits |

### Node Types

The system supports multiple typed nodes (see schemas/services/nodes.py):
- **IdentityNode**: Core agent identity (agent/identity)
- **ConfigNode**: Configuration values
- **AuditEntry**: Immutable audit records
- **TSDBSummary**: Time-series data summaries
- **IncidentNode**: Problems and resolutions
- **IdentitySnapshot**: Identity variance tracking

## Core Operations

### MEMORIZE

Adds new knowledge to the graph:

```python
# Store a user preference
await memory_service.memorize(
    MemorizeParams(
        concept="user_preference_language",
        content="User prefers formal communication style",
        scope=GraphScope.LOCAL,
        metadata={"confidence": 0.9, "observed_count": 5},
        associations=[
            Association(
                target_concept="user_profile",
                relationship="PREFERENCE_OF",
                metadata={"strength": "strong"}
            )
        ]
    )
)

# Store critical configuration (requires WA approval)
await memory_service.memorize(
    MemorizeParams(
        concept="medical_protocol_override",
        content="Allow emergency medication suggestions",
        scope=GraphScope.IDENTITY,  # Triggers WA approval
        associations=[
            Association(
                target_concept="safety_protocols",
                relationship="MODIFIES"
            )
        ]
    )
)
```

### RECALL

Retrieves memories with semantic search and graph traversal:

```python
# Simple concept recall
result = await memory_service.recall(
    SearchParams(
        query="user communication preferences",
        max_results=5,
        scope=GraphScope.LOCAL
    )
)

# Complex graph traversal
result = await memory_service.recall(
    SearchParams(
        query="medical decisions last week",
        include_associations=True,
        max_depth=3,  # Follow relationships 3 hops
        filters={
            "node_type": "decision",
            "risk_level": "high"
        }
    )
)

# Time-based recall
result = await memory_service.recall(
    SearchParams(
        query="my resource usage today",
        node_type=NodeType.TSDB_SUMMARY,
        time_range=TimeRange(
            start=datetime.now() - timedelta(days=1),
            end=datetime.now()
        )
    )
)
```

### FORGET

Removes or archives memories (with audit trail):

```python
# Forget with reason
await memory_service.forget(
    ForgetParams(
        concept="outdated_medical_protocol",
        reason="Replaced by updated 2025 guidelines",
        scope=GraphScope.LOCAL,
        cascade=False  # Don't delete related nodes
    )
)

# Compliance-driven forgetting
await memory_service.forget(
    ForgetParams(
        concept="patient_data_*",
        reason="GDPR deletion request",
        scope=GraphScope.LOCAL,
        cascade=True,  # Remove all related data
        no_audit=False  # Always audit deletions
    )
)
```

## Implementation Details

### LocalGraphMemoryService

The default implementation backed by SQLite:

```python
class LocalGraphMemoryService(MemoryServiceProtocol):
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    async def memorize(self, params: MemorizeParams) -> MemoryOpStatus:
        # Create node with proper type
        node = self._create_node(params)
        
        # Check WA approval if needed
        if params.scope in [GraphScope.IDENTITY, GraphScope.ENVIRONMENT]:
            if not await self._check_wa_approval(params):
                return MemoryOpStatus.PERMISSION_DENIED
        
        # Store in database
        await self._store_node(node)
        
        # Create associations
        await self._create_associations(node, params.associations)
        
        # Update audit trail
        await self._audit_memorize(node, params)
        
        return MemoryOpStatus.OK
```

### Graph Storage Schema

```sql
-- Nodes table
CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    attributes TEXT NOT NULL,  -- JSON with node data
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    updated_by TEXT
);

-- Edges table  
CREATE TABLE graph_edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    properties TEXT,  -- JSON with edge metadata
    created_at TIMESTAMP,
    PRIMARY KEY (source_id, target_id, relationship)
);
```

## Advanced Features

### Identity Variance Monitoring

The system tracks changes to agent identity and triggers review when variance exceeds 20%:

```python
# Variance calculation weights
VARIANCE_WEIGHTS = {
    "agent_id": 5.0,  # Name changes are major
    "domain_knowledge": 4.0,
    "description": 3.0,
    "capabilities": 2.0,
    "preferences": 1.0
}

# Automatic monitoring on identity changes
if params.scope == GraphScope.IDENTITY:
    variance = calculate_identity_variance(
        current_identity,
        new_identity,
        VARIANCE_WEIGHTS
    )
    
    if variance > 0.20:
        await defer_to_wise_authority(
            reason=f"Identity variance {variance:.2%} exceeds threshold",
            changes=identity_diff
        )
```

### Time Series Integration

TSDB data is stored as graph correlations:

```python
# Agent introspection of metrics
my_metrics = await memory_service.recall(
    SearchParams(
        query="my performance metrics",
        node_type=NodeType.TSDB_SUMMARY,
        include_associations=True
    )
)

# Returns correlated data
{
    "tokens_used_today": 125000,
    "decisions_made": 342,
    "deferrals": 12,
    "avg_response_time_ms": 1250,
    "carbon_footprint_g": 2.5
}
```

### Graph Traversal Patterns

```python
# Find all memories related to a concept
related = await memory_service.traverse(
    start_concept="diabetes_management",
    relationship_types=["RELATES_TO", "PART_OF", "UPDATES"],
    max_depth=3,
    direction="BOTH"
)

# Build knowledge graph for visualization
graph = await memory_service.get_subgraph(
    root_concepts=["medical_knowledge", "patient_interactions"],
    depth=2,
    include_properties=True
)
```

## Best Practices

### 1. Use Semantic Concepts

```python
# Good - semantic concept name
await memorize(concept="user_prefers_metric_units", ...)

# Bad - implementation detail
await memorize(concept="pref_metric_flag_true", ...)
```

### 2. Create Rich Associations

```python
# Good - multiple relationships
associations=[
    Association("user_profile", "PREFERENCE_OF"),
    Association("measurement_system", "USES"),
    Association("interaction_style", "INFLUENCES")
]

# Bad - isolated memory
associations=[]
```

### 3. Include Metadata

```python
# Good - rich metadata
metadata={
    "confidence": 0.85,
    "source": "observed_behavior",
    "observed_count": 10,
    "last_confirmed": "2025-06-25T10:00:00Z"
}

# Bad - no context
metadata={}
```

### 4. Respect Scopes

```python
# Good - appropriate scope
# User preference = LOCAL
await memorize(
    concept="preferred_language",
    scope=GraphScope.LOCAL
)

# Configuration = ENVIRONMENT (needs approval)
await memorize(
    concept="api_endpoint_override", 
    scope=GraphScope.ENVIRONMENT
)
```

## Integration with Other Services

### Audit Service
- Every memory operation creates audit entries
- Deletions are logged with reasons
- WA approvals are recorded

### Telemetry Service
- Memory operations are tracked for performance
- Graph size and complexity metrics
- Query performance analysis

### Config Service
- Configuration stored as ConfigNode memories
- Version tracking for config changes
- Rollback capabilities

## Performance Considerations

### Indexing Strategy
- Primary index on node ID
- Secondary indexes on type and scope
- Full-text search on content fields
- Relationship indexes for traversal

### Query Optimization
- Use specific node types when possible
- Limit traversal depth for large graphs
- Cache frequently accessed paths
- Batch related operations

### Storage Efficiency
- Nodes: ~1-5KB each typically
- Edges: ~200 bytes each
- Automatic compression for large content
- Periodic cleanup of orphaned nodes

## Future Enhancements

### Planned Features
- Distributed graph support (Neo4j, ArangoDB)
- Graph partitioning by scope
- Real-time graph streaming
- ML-based relationship discovery
- Quantum-ready graph algorithms

### Research Areas
- Homomorphic encryption for private memories
- Federated learning across agent graphs
- Emergent behavior from graph patterns
- Consciousness emergence metrics

## Troubleshooting

### Common Issues

**Permission Denied**
- Check if scope requires WA approval
- Verify WA authentication token
- Review audit logs for denial reason

**Node Not Found**
- Verify concept name spelling
- Check scope permissions
- Confirm node wasn't deleted

**Traversal Timeout**
- Reduce max_depth parameter
- Add relationship type filters
- Use more specific start concepts

### Debugging

```python
# Enable debug logging
import logging
logging.getLogger('memory_service').setLevel(logging.DEBUG)

# Inspect graph structure
graph_stats = await memory_service.get_statistics()
print(f"Total nodes: {graph_stats['node_count']}")
print(f"Total edges: {graph_stats['edge_count']}")
print(f"Node types: {graph_stats['node_types']}")

# Trace query execution
result = await memory_service.recall(
    SearchParams(query="test", debug=True)
)
print(result.debug_info)
```

## Summary

The graph memory service implements the revolutionary principle that identity IS the graph. By unifying all agent data into a single graph structure with proper access controls, CIRIS creates agents with true persistence, self-awareness, and the ability to learn and evolve while maintaining ethical boundaries.

This isn't just a database - it's the agent's mind, memories, and identity in one coherent system.

---

*Copyright © 2025 Eric Moore and CIRIS L3C - Apache 2.0 License*