# CIRIS API Specification v3.0 - Simplified

## Overview

The CIRIS API provides a streamlined interface to interact with an autonomous AI agent. The API reflects the agent's natural capabilities through a simplified structure that groups related functionality while maintaining clear boundaries between observation, operation, and authority.

## Core Principles

1. **Interaction Over Control**: The API enables observation and interaction with the agent, not direct control
2. **Graph Memory as Truth**: All data flows through the universal memory system
3. **Simplified Service Groups**: Related services grouped under logical endpoints
4. **Security by Design**: Four-role model with clear boundaries
5. **Emergency Access**: Dedicated emergency endpoint bypasses normal auth

## Authentication & Authorization

### Roles (Keeping all 4 roles)

- **OBSERVER**: Read-only access to observe agent behavior and state
- **ADMIN**: Can manage system operations, configuration, runtime control
- **AUTHORITY**: Can approve deferrals and provide guidance (wisdom role)
- **ROOT**: Full system access including sensitive operations

### Authentication Methods

- **API Key**: Bearer token authentication for programmatic access
- **OAuth 2.0**: For human users via web interface

## API Structure

### 1. Agent Interaction (`/v1/agent`)

Primary interface for interacting with the agent.

```
POST   /v1/agent/interact           - Send message and get response
GET    /v1/agent/history            - Conversation history
GET    /v1/agent/status             - Agent status and cognitive state
GET    /v1/agent/identity           - Agent identity and capabilities
WS     /v1/stream                   - WebSocket for real-time updates
```

### 2. Memory Service (`/v1/memory`)

Universal graph memory with simplified query interface.

```
POST   /v1/memory/store             - Store typed nodes (MEMORIZE)
POST   /v1/memory/query             - Flexible query interface (RECALL)
DELETE /v1/memory/{id}              - Remove specific memories (FORGET)
GET    /v1/memory/{id}              - Get specific node
GET    /v1/memory/timeline          - Temporal view of memories
```

### 3. System Operations (`/v1/system`)

Consolidated system management endpoints.

```
GET    /v1/system/health            - Overall system health
GET    /v1/system/time              - System time, agent time, uptime, sync
GET    /v1/system/resources         - Resource usage and limits
POST   /v1/system/runtime/{action}  - Runtime control (pause/resume/state)
GET    /v1/system/services          - Service status
POST   /v1/system/shutdown          - Graceful shutdown (ADMIN)
```

### 4. Configuration (`/v1/config`)

Simplified configuration management.

```
GET    /v1/config                   - List all config (filtered by role)
GET    /v1/config/{key}             - Get specific config
PUT    /v1/config/{key}             - Update config (ADMIN, ROOT for sensitive)
DELETE /v1/config/{key}             - Delete config (ADMIN)
```

### 5. Telemetry & Observability (`/v1/telemetry`)

Unified metrics and observability.

```
GET    /v1/telemetry/overview       - System metrics summary
GET    /v1/telemetry/metrics        - Detailed metrics
GET    /v1/telemetry/traces         - Reasoning traces
GET    /v1/telemetry/logs           - System logs
POST   /v1/telemetry/query          - Custom queries
```

### 6. Audit Trail (`/v1/audit`)

Immutable action history.

```
GET    /v1/audit                    - Query audit entries
GET    /v1/audit/{id}               - Specific entry with verification
GET    /v1/audit/export             - Export audit data
```

### 7. Wise Authority (`/v1/wa`)

Human-in-the-loop deferrals and guidance.

```
GET    /v1/wa/deferrals             - Pending deferrals
POST   /v1/wa/deferrals/{id}/resolve - Resolve deferral (AUTHORITY)
GET    /v1/wa/permissions           - WA permission status
```

### 8. Authentication (`/v1/auth`)

User authentication and session management.

```
POST   /v1/auth/login               - Authenticate user
POST   /v1/auth/logout              - End session
GET    /v1/auth/me                  - Current user info
POST   /v1/auth/refresh             - Refresh token
```

## Emergency Shutdown Endpoint

**Critical**: This endpoint bypasses normal authentication to ensure remote ROOT/AUTHORITY can always execute emergency shutdown even if the main API auth is compromised or unavailable.

```
POST   /emergency/shutdown          - Emergency shutdown (signed command only)
```

**Security**:
- Requires cryptographically signed command
- Signature must be from ROOT or AUTHORITY key
- Timestamp must be within 5-minute window
- Executes immediate shutdown without negotiation
- Separate from `/v1/system/shutdown` to avoid auth dependencies

**Payload**:
```json
{
  "command": "EMERGENCY_SHUTDOWN",
  "reason": "Security incident detected",
  "timestamp": "2025-01-01T12:00:00Z",
  "signature": "base64-encoded-signature"
}
```

## WebSocket Streaming

Single multiplexed WebSocket endpoint with subscription model:

```
WS     /v1/stream                   - Real-time updates
```

**Subscribe to channels**:
```json
{
  "action": "subscribe",
  "channels": ["messages", "telemetry", "reasoning", "logs"]
}
```

## Response Formats

Simplified response structure without nested metadata:

### Success Response
```json
{
  "data": <typed-response-object>,
  "timestamp": "2025-01-01T12:00:00Z",
  "request_id": "req_123",
  "duration_ms": 45
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
  "timestamp": "2025-01-01T12:00:00Z",
  "request_id": "req_123"
}
```

## Common Operations

### Send a message to the agent
```bash
POST /v1/agent/interact
{
  "message": "Hello, can you help me understand quantum computing?"
}
```

### Query memory
```bash
POST /v1/memory/query
{
  "type": "CONCEPT",
  "filters": {
    "tags": ["quantum"],
    "since": "2025-01-01T00:00:00Z"
  },
  "limit": 10
}
```

### Check system health
```bash
GET /v1/system/health
```

### Get time information
```bash
GET /v1/system/time

Response:
{
  "system_time": "2025-01-01T12:00:00Z",      // Host system time
  "agent_time": "2025-01-01T12:00:01.234Z",  // Agent's TimeService time
  "uptime_seconds": 3600,
  "time_sync": {
    "synchronized": true,
    "drift_ms": 1234,
    "last_sync": "2025-01-01T11:00:00Z"
  }
}
```

### Emergency shutdown (requires signed payload)
```bash
POST /emergency/shutdown
{
  "command": "EMERGENCY_SHUTDOWN",
  "reason": "Critical security event",
  "timestamp": "2025-01-01T12:00:00Z",
  "signature": "..."
}
```

## Rate Limiting

- **OBSERVER**: 1000 requests/hour
- **ADMIN**: 5000 requests/hour
- **AUTHORITY**: 5000 requests/hour
- **ROOT**: 10000 requests/hour
- **WebSocket**: 10 concurrent connections
- **Emergency endpoint**: No rate limit (signature validation only)

## Security

- HTTPS required for all endpoints (except emergency in critical situations)
- API keys rotated every 90 days
- All mutations logged to audit trail
- Sensitive data filtered by role
- Emergency endpoint uses cryptographic signatures

## Migration from v2.0

### Endpoint Mapping
- `/v1/llm/*` → Removed (use `/v1/telemetry` for usage)
- `/v1/incidents/*` → Part of `/v1/telemetry`
- `/v1/tsdb/*` → Internal, removed from API
- `/v1/secrets/*` → Part of `/v1/config` (filtered)
- `/v1/time/*` → `/v1/system/time`
- `/v1/shutdown/*` → `/v1/system/shutdown`
- `/v1/init/*` → Removed (internal)
- `/v1/visibility/*` → Part of `/v1/telemetry/traces`
- `/v1/resources/*` → `/v1/system/resources`
- `/v1/runtime/*` → `/v1/system/runtime`
- `/v1/adaptation/*` → Part of `/v1/telemetry`
- `/v1/filters/*` → Part of `/v1/config`
- `/v1/scheduler/*` → Part of `/v1/system/runtime`
- `/v1/tools/*` → Part of `/v1/agent/identity`
- `/v1/observe/*` → Merged into `/v1/telemetry`

### Role Mapping
- All roles remain unchanged from v2.0:
  - **OBSERVER** → **OBSERVER**
  - **ADMIN** → **ADMIN**
  - **ROOT** → **ROOT**
  - **AUTHORITY** → **AUTHORITY**

## Summary

This simplified API reduces ~140 endpoints to ~35 core endpoints while maintaining all essential functionality. The emergency shutdown endpoint remains separate to ensure it can bypass any authentication issues in the main API. The three-role model is clearer, and the grouped structure makes the API more intuitive to use while preserving the agent's autonomous nature.
