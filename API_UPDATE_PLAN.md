# API Update Plan

## Overview

This document outlines the comprehensive plan to re-architect the CIRIS API to align with the post-refactor protocol architecture while respecting the core design principle: **"API is for interaction, not control, except RuntimeControl protocol which requires AUTHORITY role"**.

## Current State Analysis

### Existing API Structure
The API currently has 13 route modules exposing various endpoints:
- `api_agent.py` - Agent interaction endpoints
- `api_memory.py` - Memory observability endpoints  
- `api_system.py` - System telemetry (uses old patterns)
- `api_runtime_control.py` - Runtime control endpoints
- `api_telemetry.py` - Telemetry monitoring
- `api_audit.py` - Audit trail access
- `api_auth.py` - Authentication and OAuth
- `api_tools.py` - Tool execution
- `api_visibility.py` - Agent reasoning visibility
- `api_wa.py` - Wise Authority endpoints
- `api_comms.py` - Communication endpoints
- `api_logs.py` - Log streaming
- `api_observer.py` - Observer implementation

### Protocol Coverage Gaps

#### Missing Protocol Exposures
1. **IncidentManagementProtocol** - No incident tracking endpoints
2. **SelfConfigurationProtocol** - No adaptation/learning endpoints
3. **TaskSchedulerProtocol** - No scheduled task management
4. **AdaptiveFilterProtocol** - No filter configuration endpoints
5. **TSDBConsolidationProtocol** - Not properly exposed
6. **ShutdownServiceProtocol** - Limited shutdown control
7. **ResourceMonitorProtocol** - No direct resource endpoints

#### Misaligned Implementations
1. Telemetry using `telemetry_collector` instead of graph memory
2. Config management mixed with runtime control
3. Agent creation in auth endpoints (out of scope)
4. Direct service access instead of capability exposure

## Update Strategy

### Phase 1: Core Refactoring (Week 1-2)

#### 1.1 Telemetry Refactor
**Goal**: Remove old telemetry collector, use graph-based telemetry

**Changes**:
```python
# OLD: api_telemetry.py
/v1/telemetry/overview → Uses telemetry_collector
/v1/telemetry/metrics → Direct metric access

# NEW: api_telemetry.py  
/v1/telemetry/overview → Query TSDBSummary nodes from graph
/v1/telemetry/metrics → Aggregate from correlation nodes
/v1/telemetry/resources → Resource usage from graph
/v1/telemetry/resources/history → Historical TSDB data
```

**Implementation**:
- Query memory service for NodeType.TSDB_SUMMARY
- Aggregate metrics from correlation nodes
- Remove all references to telemetry_collector
- Use ConfigurationFeedbackLoop insights

#### 1.2 Config API Separation
**Goal**: Separate configuration from runtime control

**New Endpoints**:
```python
# NEW: api_config.py
/v1/config/list → List all configurations
/v1/config/get/{key} → Get specific config
/v1/config/set → Set configuration (AUTHORITY required)
/v1/config/update → Update configuration (AUTHORITY required)
/v1/config/delete/{key} → Delete configuration (AUTHORITY required)
/v1/config/history/{key} → Config change history
```

**Implementation**:
- Use GraphConfigService directly
- Enforce AUTHORITY role for write operations
- Track all changes in audit trail

### Phase 2: New Protocol Endpoints (Week 2-3)

#### 2.1 Incident Management API
**Goal**: Expose incident tracking and analysis

**Endpoints**:
```python
# NEW: api_incidents.py
/v1/incidents → List recent incidents
/v1/incidents/{id} → Incident details
/v1/incidents/patterns → Detected patterns
/v1/incidents/insights → Generated insights
/v1/incidents/problems → Current problems
/v1/incidents/recommendations → Recommendations
```

**Implementation**:
- Query IncidentNode, ProblemNode, IncidentInsightNode
- Read-only access (interaction, not control)
- Include pattern analysis from feedback loop

#### 2.2 Self-Configuration API  
**Goal**: Expose adaptation and learning capabilities

**Endpoints**:
```python
# NEW: api_adaptation.py
/v1/adaptation/patterns → Detected behavioral patterns
/v1/adaptation/proposals → Current adaptation proposals
/v1/adaptation/history → Past adaptations
/v1/adaptation/learning → Learning state
/v1/adaptation/analysis → Trigger analysis (AUTHORITY required)
```

**Implementation**:
- Query AdaptationProposal and IdentitySnapshot nodes
- Expose ConfigurationFeedbackLoop insights
- Read-only except for manual analysis trigger

#### 2.3 Task Scheduler API
**Goal**: Expose scheduled task management

**Endpoints**:
```python
# NEW: api_scheduler.py
/v1/scheduler/tasks → List scheduled tasks
/v1/scheduler/tasks/{id} → Task details
/v1/scheduler/schedule → Create schedule (AUTHORITY required)
/v1/scheduler/cancel/{id} → Cancel task (AUTHORITY required)
/v1/scheduler/history → Task execution history
```

**Implementation**:
- Expose TaskSchedulerService capabilities
- Enforce permissions for task management
- Audit all scheduling operations

#### 2.4 Adaptive Filter API
**Goal**: Expose message filtering configuration

**Endpoints**:
```python
# NEW: api_filters.py
/v1/filters/rules → Current filter rules
/v1/filters/test → Test message against filters
/v1/filters/config → Filter configuration
/v1/filters/update → Update filters (AUTHORITY required)
/v1/filters/stats → Filter statistics
```

**Implementation**:
- Read filter config from graph
- Test endpoint for debugging
- Statistics from telemetry

### Phase 3: Enhanced Capabilities (Week 3-4)

#### 3.1 Enhanced Memory API
**Goal**: Full graph memory capabilities

**New Endpoints**:
```python
# ENHANCED: api_memory.py
/v1/memory/graph/nodes → List nodes with filtering
/v1/memory/graph/edges → List relationships
/v1/memory/graph/query → GraphQL-like query
/v1/memory/graph/path → Find paths between nodes
/v1/memory/correlations → Correlation search
/v1/memory/timeline → Temporal view
```

**Implementation**:
- Advanced graph querying
- Correlation-based search
- Timeline visualization support

#### 3.2 Enhanced Visibility API
**Goal**: Deep agent introspection

**New Endpoints**:
```python
# ENHANCED: api_visibility.py
/v1/visibility/reasoning → Current reasoning trace
/v1/visibility/decisions → Decision history
/v1/visibility/thoughts → Thought process
/v1/visibility/state → Cognitive state
/v1/visibility/explanations → Action explanations
```

**Implementation**:
- Integrate with processor state
- Include pattern insights
- Real-time reasoning updates

#### 3.3 Resource Monitor API
**Goal**: System resource visibility

**Endpoints**:
```python
# NEW: api_resources.py
/v1/resources/limits → Resource limits
/v1/resources/usage → Current usage
/v1/resources/history → Usage history
/v1/resources/alerts → Resource alerts
/v1/resources/predictions → Usage predictions
```

**Implementation**:
- Query resource telemetry
- Predictive analytics
- Alert configuration

### Phase 4: Security & Polish (Week 4)

#### 4.1 Authentication Enhancement
- Move agent creation out of auth endpoints
- Implement proper OAuth2 flows
- Add API key management
- Integrate with WiseAuthority

#### 4.2 Rate Limiting & Quotas
- Implement per-user rate limits
- Add quota management
- Track usage in graph memory
- Provide usage endpoints

#### 4.3 API Documentation
- OpenAPI 3.0 specification
- Interactive documentation
- Example requests/responses
- Migration guide from old API

## Design Principles

### 1. Interaction Over Control
- Most endpoints are read-only
- Write operations require explicit permissions
- Agent maintains autonomy in decision-making
- No direct manipulation of internal state

### 2. Graph Memory as Truth
- All data queries from graph memory
- No direct service state access
- Consistent data model across endpoints
- Correlation-based relationships

### 3. Security by Design
- Authentication required for all endpoints
- Role-based access (OBSERVER, AUTHORITY)
- Audit trail for all mutations
- Encrypted sensitive data

### 4. Type Safety
- All responses use Pydantic models
- No Dict[str, Any] in API contracts
- Versioned schemas for compatibility
- Clear error responses

## Migration Strategy

### Deprecation Plan
1. Mark old endpoints as deprecated
2. Add warnings in responses
3. Provide migration endpoints
4. 6-month deprecation window

### Compatibility Layer
- Route old endpoints to new implementations
- Transform responses for compatibility
- Log usage of deprecated endpoints
- Gradual feature flags

### Documentation
- Migration guide with examples
- Endpoint mapping table
- Common pattern translations
- SDK update instructions

## Success Metrics

1. **Coverage**: All 19 protocols exposed appropriately
2. **Type Safety**: Zero Dict[str, Any] in API contracts
3. **Performance**: <100ms p95 latency for read operations
4. **Security**: 100% authenticated endpoints
5. **Adoption**: 80% migration within 3 months

## Timeline

- **Week 1-2**: Core refactoring (telemetry, config)
- **Week 2-3**: New protocol endpoints
- **Week 3-4**: Enhanced capabilities
- **Week 4**: Security and polish
- **Week 5-6**: Testing and documentation
- **Week 7-8**: Gradual rollout

## Risk Mitigation

1. **Breaking Changes**: Compatibility layer for 6 months
2. **Performance**: Caching layer for graph queries
3. **Complexity**: Phased rollout with feature flags
4. **Adoption**: Clear migration guides and support

## Next Steps

1. Review and approve plan
2. Set up development environment
3. Create API specification
4. Begin Phase 1 implementation
5. Establish testing framework

This plan ensures the API becomes a true interaction layer for CIRIS, exposing agent capabilities while respecting autonomy and maintaining security.