# CIRIS API Specification v2.0 - FINAL

## Overview

The CIRIS API provides a rich interface to interact with an autonomous AI agent built on 19 essential services working in harmony. The API reflects the agent's natural capabilities rather than imposing external control structures. It exposes the traces, logs, metrics, reasoning, and memories that flow through the system organically.

## Core Principles

1. **Interaction Over Control**: The API enables observation and interaction with the agent, not direct control
2. **Graph Memory as Truth**: All data flows through the universal memory system using MEMORIZE/RECALL/FORGET
3. **Natural Service Boundaries**: Endpoints reflect the actual capabilities of the 19 services
4. **Rich Observability**: Full access to reasoning traces, decisions, metrics, and insights
5. **Security by Design**: Role-based access (OBSERVER/ADMIN/AUTHORITY) with clear boundaries

## Authentication & Authorization

### Roles

- **OBSERVER**: Read-only access to observe agent behavior and state
- **ADMIN**: Can manage runtime control, configuration, and system operations (but cannot resolve deferrals)
- **AUTHORITY**: Can approve deferrals and provide guidance (wise authority role)
- **ROOT**: Full system access (only in isolated deployments)

### Role Distinctions

- **ADMIN vs AUTHORITY**: ADMIN handles system operations (runtime, config, monitoring) while AUTHORITY handles wisdom/guidance (deferrals, ethical decisions). Most deployments will have many ADMINs but few AUTHORITYs.

### Authentication Methods

- **API Key**: Bearer token authentication for programmatic access
- **OAuth 2.0**: For human users via web interface
- **Basic Auth**: For RuntimeControl endpoints (requires ADMIN or higher)

## Service-Based API Structure

The API naturally organizes around the 19 essential services:

### 1. Memory Service (Graph-Based Universal Memory)

The memory service implements the three universal verbs: MEMORIZE, RECALL, FORGET.

```
POST   /v1/memory/memorize          - Store any typed node in graph memory
POST   /v1/memory/recall            - Query memories with rich filtering
POST   /v1/memory/forget            - Remove specific memories
GET    /v1/memory/search            - Text-based memory search
GET    /v1/memory/correlations      - Find related memories
GET    /v1/memory/timeline          - Temporal view of memories
POST   /v1/memory/graph/query       - Advanced graph queries
GET    /v1/memory/nodes/{id}        - Direct node access
GET    /v1/memory/edges             - Relationship exploration
```

### 2. LLM Service (Language Model Integration)

Exposes the agent's language capabilities and resource usage.

```
GET    /v1/llm/usage                - Token usage and costs
GET    /v1/llm/models               - Available models
GET    /v1/llm/capabilities         - Model capabilities
```

Note: Direct generation is not exposed - use agent messages for all interactions.

### 3. Audit Service (Immutable Action Trail)

Complete audit trail of all agent actions.

```
GET    /v1/audit/entries            - Query audit log
GET    /v1/audit/entries/{id}       - Specific audit entry
GET    /v1/audit/search             - Search audit trails
GET    /v1/audit/verify/{id}        - Verify entry integrity
GET    /v1/audit/export             - Export audit data
```

### 4. Config Service (Dynamic Configuration)

Graph-based configuration management with role-based filtering.

```
GET    /v1/config/values            - List all configurations (filtered by role)
GET    /v1/config/values/{key}      - Get specific config (filtered by role)
PUT    /v1/config/values/{key}      - Update config (ADMIN, ROOT for sensitive)
DELETE /v1/config/values/{key}      - Delete config (ADMIN)
GET    /v1/config/history/{key}     - Configuration history
POST   /v1/config/validate          - Validate config changes
```

Note: Sensitive configuration (keys, secrets, credentials) is automatically redacted for OBSERVER role and requires ROOT to modify.

### 5. Telemetry Service (Metrics & Time-Series)

Rich telemetry data from graph-based TSDB.

```
GET    /v1/telemetry/overview       - System telemetry summary
GET    /v1/telemetry/metrics        - Current metrics
GET    /v1/telemetry/metrics/{name} - Specific metric history
GET    /v1/telemetry/resources      - Resource usage
GET    /v1/telemetry/resources/history - Historical usage
POST   /v1/telemetry/query          - Custom telemetry queries
WS     /v1/telemetry/stream         - Real-time metric stream
```

### 6. Incident Management Service (Self-Improvement)

ITIL-aligned incident tracking and pattern detection.

```
GET    /v1/incidents                - Recent incidents
GET    /v1/incidents/{id}           - Incident details
GET    /v1/incidents/patterns       - Detected patterns
GET    /v1/incidents/problems       - Current problems
GET    /v1/incidents/insights       - Generated insights
POST   /v1/incidents/analyze        - Trigger analysis (ADMIN)
GET    /v1/incidents/recommendations - Improvement recommendations
```

### 7. TSDB Consolidation Service (Long-Term Memory)

Manages time-series data consolidation.

```
GET    /v1/tsdb/summaries           - Consolidated summaries
GET    /v1/tsdb/summaries/{period}  - Specific period summary
GET    /v1/tsdb/retention           - Retention policies
POST   /v1/tsdb/consolidate         - Manual consolidation (ADMIN)
```

### 8. Secrets Service (Sensitive Data Protection)

Manages secrets detection and storage.

```
GET    /v1/secrets/stats            - Secrets service statistics
GET    /v1/secrets/filters          - Active filter patterns
PUT    /v1/secrets/filters          - Update filters (ADMIN)
POST   /v1/secrets/test             - Test secret detection
GET    /v1/secrets/audit            - Secrets access audit
```

### 9. Time Service (Temporal Consistency)

Ensures consistent time across the system.

```
GET    /v1/time/current             - Current system time
GET    /v1/time/uptime              - Service uptime
GET    /v1/time/sync                - Time sync status
```

### 10. Shutdown Service (Graceful Termination)

Manages system shutdown procedures.

```
GET    /v1/shutdown/status          - Shutdown readiness
POST   /v1/shutdown/prepare         - Prepare for shutdown (ADMIN)
POST   /v1/shutdown/execute         - Execute shutdown (ADMIN)
POST   /v1/shutdown/abort           - Abort shutdown (ADMIN)
```

### 11. Initialization Service (Startup Orchestration)

System initialization status.

```
GET    /v1/init/status              - Initialization status
GET    /v1/init/sequence            - Init sequence details
GET    /v1/init/health              - Component health
```

### 12. Visibility Service (Agent Transparency)

Deep introspection into agent reasoning.

```
GET    /v1/visibility/reasoning     - Current reasoning trace
GET    /v1/visibility/thoughts      - Recent thoughts
GET    /v1/visibility/decisions     - Decision history
GET    /v1/visibility/state         - Cognitive state
GET    /v1/visibility/explanations  - Action explanations
WS     /v1/visibility/stream        - Real-time reasoning stream
```

### 13. Authentication Service (Identity & Access)

Manages authentication and authorization.

```
POST   /v1/auth/login               - Authenticate user
POST   /v1/auth/logout              - End session
GET    /v1/auth/me                  - Current user info
GET    /v1/auth/permissions         - User permissions
POST   /v1/auth/token/refresh       - Refresh access token
```

### 14. Resource Monitor Service (System Resources)

Monitors system resource usage and limits.

```
GET    /v1/resources/limits         - Resource limits
GET    /v1/resources/usage          - Current usage
GET    /v1/resources/alerts         - Resource alerts
GET    /v1/resources/predictions    - Usage predictions
POST   /v1/resources/alerts/config  - Configure alerts (ADMIN)
```

### 15. Runtime Control Service (Execution Control)

Controls agent runtime behavior (requires ADMIN).

```
GET    /v1/runtime/status           - Runtime status
POST   /v1/runtime/pause            - Pause processing
POST   /v1/runtime/resume           - Resume processing
POST   /v1/runtime/state            - Change cognitive state
GET    /v1/runtime/tasks            - Active tasks
POST   /v1/runtime/emergency-stop   - Emergency stop
GET    /v1/runtime/events           - Runtime events history
GET    /v1/runtime/health           - Service health status
GET    /v1/runtime/snapshot         - Runtime state snapshot
POST   /v1/runtime/state/{state}    - Force state transition (AUTHORITY)
GET    /v1/runtime/queue            - Processing queue status
POST   /v1/runtime/speed            - Set processing speed multiplier
POST   /v1/runtime/single-step      - Execute single processing step
```

### 16. Wise Authority Service (Deferral & Guidance)

Manages human-in-the-loop deferrals and wisdom.

```
GET    /v1/wa/deferrals             - Pending deferrals
GET    /v1/wa/deferrals/{id}        - Deferral details
POST   /v1/wa/deferrals/{id}/resolve - Resolve deferral (AUTHORITY)
POST   /v1/wa/guidance              - Request guidance
GET    /v1/wa/permissions           - WA permissions
POST   /v1/wa/permissions/grant     - Grant permission (AUTHORITY)
POST   /v1/wa/permissions/revoke    - Revoke permission (AUTHORITY)
```

### 17. Self-Configuration Service (Autonomous Adaptation)

Observes the agent's self-improvement patterns and adaptations.

```
GET    /v1/adaptation/patterns      - Detected behavioral patterns
GET    /v1/adaptation/insights      - Pattern-based insights
GET    /v1/adaptation/history       - Adaptation history
GET    /v1/adaptation/effectiveness - Effectiveness metrics
GET    /v1/adaptation/correlations  - Pattern correlations
GET    /v1/adaptation/report        - Improvement report
```

Note: The agent adapts autonomously based on its observations. This API provides visibility into that process, not control over it.

### 18. Adaptive Filter Service (Message Filtering)

Configurable message filtering system.

```
GET    /v1/filters/rules            - Current filter rules
POST   /v1/filters/test             - Test message filtering
GET    /v1/filters/stats            - Filter statistics
PUT    /v1/filters/config           - Update filters (ADMIN)
GET    /v1/filters/effectiveness    - Filter performance
```

### 19. Task Scheduler Service (Scheduled Operations)

Manages scheduled and recurring tasks.

```
GET    /v1/scheduler/tasks          - List scheduled tasks
GET    /v1/scheduler/tasks/{id}     - Task details
POST   /v1/scheduler/tasks          - Create task (ADMIN)
DELETE /v1/scheduler/tasks/{id}     - Cancel task (ADMIN)
GET    /v1/scheduler/history        - Execution history
GET    /v1/scheduler/upcoming       - Upcoming executions
```

## Emergency Shutdown Endpoint

A special endpoint that requires no authentication but accepts cryptographically signed commands:

```
POST   /emergency/shutdown          - Emergency shutdown (signed command only)
```

Accepts signed shutdown commands from ROOT or AUTHORITY keys. Executes immediate shutdown without negotiation. Signature must be valid and timestamp within 5-minute window.

## Agent Interaction Endpoints

High-level endpoints for natural agent interaction:

```
POST   /v1/agent/messages           - Send message to agent
GET    /v1/agent/messages           - Get conversation history
POST   /v1/agent/ask                - Ask and wait for response
GET    /v1/agent/status             - Agent status and state
GET    /v1/agent/identity           - Agent identity info
GET    /v1/agent/capabilities       - Agent capabilities
WS     /v1/agent/connect            - WebSocket connection
```

## Tool Discovery

Tool information for understanding agent capabilities:

```
GET    /v1/tools                    - List available tools
GET    /v1/tools/{name}             - Tool details and schema
GET    /v1/tools/categories         - Tool categories
GET    /v1/tools/usage              - Tool usage statistics
```

Note: Tools are executed by the agent during its reasoning process, not directly via API. To use tools, send messages to the agent requesting specific actions.

## Observability Aggregation

Cross-service observability views:

```
GET    /v1/observe/dashboard        - Unified dashboard data
GET    /v1/observe/traces           - Distributed traces
GET    /v1/observe/metrics          - Aggregated metrics
GET    /v1/observe/logs             - Centralized logs
POST   /v1/observe/query            - Custom observability queries
WS     /v1/observe/stream           - Real-time observability
```

## WebSocket Streaming

Real-time data streams for rich UX:

```
WS     /v1/stream/messages          - Message stream
WS     /v1/stream/telemetry         - Telemetry updates
WS     /v1/stream/reasoning         - Reasoning trace
WS     /v1/stream/logs              - Log stream
WS     /v1/stream/all               - Multiplexed stream
```

## Response Formats

All responses use typed Pydantic models - NO Dict[str, Any]:

### Success Response
```json
{
  "data": <typed-response-object>,
  "metadata": {
    "timestamp": "2025-01-01T12:00:00Z",
    "request_id": "req_123",
    "duration_ms": 45
  }
}
```

### Error Response
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found",
    "details": {
      "resource_type": "node",
      "resource_id": "memory_123"
    }
  },
  "metadata": {
    "timestamp": "2025-01-01T12:00:00Z",
    "request_id": "req_123"
  }
}
```

## Rate Limiting

- **OBSERVER**: 1000 requests/hour
- **ADMIN**: 5000 requests/hour
- **AUTHORITY**: 5000 requests/hour
- **Streaming**: 10 concurrent connections

## Versioning

- API version in URL: `/v1/`
- Breaking changes require new version
- Deprecation notices 6 months in advance
- Version negotiation via headers

## Security

- HTTPS required for all endpoints
- API keys must be rotated every 90 days
- All mutations logged to audit trail
- Sensitive data automatically filtered by role
- CORS configured per deployment

## SDK Support

Official SDKs available for:
- Python (async/await native)
- TypeScript/JavaScript
- Go
- Rust

All SDKs follow the same typed, no-dicts philosophy.

## Deployment Patterns

The API adapts to deployment context:

- **Local Development**: Full access, mock services available
- **Cloud Deployment**: OAuth flow, rate limiting enforced
- **Edge Deployment**: Offline mode, local auth
- **Multi-Agent Mesh**: Federated auth, cross-agent communication

## Practical Role Usage

In typical deployments:

- **Most users are OBSERVER**: Can interact with the agent, view its reasoning, and monitor its behavior
- **System operators are ADMIN**: Can manage configuration, control runtime, handle incidents, but cannot make wisdom decisions
- **Selected humans are AUTHORITY**: The few trusted to resolve ethical deferrals and provide guidance
- **Developer/Owner might have ROOT**: Full access in development or isolated deployments

This separation ensures that system administration (ADMIN) doesn't require the wisdom role (AUTHORITY), making the system practical to operate while maintaining appropriate boundaries for ethical decisions.

## Summary

This API specification reflects the natural capabilities of CIRIS's 19 services working in harmony. Rather than imposing external control structures, it provides rich observability and interaction patterns that emerge from the agent's graph-based memory and typed architecture. The API serves as a window into the agent's reasoning and state, enabling Observers to understand, Admins to operate, and Authorities to guide the agent's behavior within its autonomous boundaries.