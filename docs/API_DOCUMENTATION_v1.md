# CIRIS API v1.0 Documentation

## Overview

The CIRIS API provides comprehensive access to an autonomous AI agent system with advanced runtime control, service management, and observability features. This documentation covers all 57 endpoints across 11 route modules.

## Base URL

```
http://localhost:8080/v1
```

## Authentication

All endpoints except `/emergency/*` require authentication via Bearer token.

### Login
```bash
POST /v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "ciris_admin_password"
}

Response:
{
  "access_token": "ciris_admin_xxx...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "admin",
  "role": "ADMIN"
}
```

Use the token in subsequent requests:
```bash
Authorization: Bearer ciris_admin_xxx...
```

### Roles
- **OBSERVER**: Read-only access
- **ADMIN**: System management and control
- **AUTHORITY**: Wisdom authority functions
- **SYSTEM_ADMIN**: Full system access

## API Endpoints

### 1. Agent Interaction (`/v1/agent/*`)

#### Send Message to Agent
```
POST /v1/agent/interact
Body: {
  "message": "Hello",
  "channel_id": "api_0.0.0.0_8080"
}
```

#### Get Agent Status
```
GET /v1/agent/status
```

#### Get Agent Identity
```
GET /v1/agent/identity
```

#### Get Conversation History
```
GET /v1/agent/history?channel_id=xxx&limit=50
```

### 2. Authentication (`/v1/auth/*`)

#### Login
```
POST /v1/auth/login
Body: {"username": "xxx", "password": "xxx"}
```

#### Logout
```
POST /v1/auth/logout
```

#### Get Current User
```
GET /v1/auth/me
```

#### Refresh Token
```
POST /v1/auth/refresh
```

### 3. Memory Operations (`/v1/memory/*`)

#### Query Memory
```
POST /v1/memory/query
Body: {
  "query": "search text",
  "type": "OBSERVATION",
  "scope": "LOCAL",
  "limit": 10
}
```

#### Store Memory Node
```
POST /v1/memory/store
Body: {
  "type": "OBSERVATION",
  "scope": "LOCAL",
  "attributes": {...}
}
```

#### Get Specific Node
```
GET /v1/memory/{node_id}
GET /v1/memory/recall/{node_id}  # Alternative
```

#### Update Node
```
PATCH /v1/memory/{node_id}
Body: {"attributes": {...}}
```

#### Delete Node
```
DELETE /v1/memory/{node_id}
```

#### Get Memory Timeline
```
GET /v1/memory/timeline?since=2025-01-01&until=2025-01-31
```

#### Visualize Memory Graph
```
GET /v1/memory/visualize/graph
Query Parameters:
  - node_type: Filter by node type (e.g., "concept", "observation")
  - scope: Memory scope (LOCAL, IDENTITY, SYSTEM)
  - hours: Hours to look back for timeline view (1-168)
  - layout: Graph layout algorithm ("force", "timeline", "hierarchical")
  - width: SVG width in pixels (400-4000, default: 1200)
  - height: SVG height in pixels (300-3000, default: 800)
  - limit: Maximum nodes to visualize (1-200, default: 50)

Returns: SVG image as text/svg+xml
```

### 4. System Management (`/v1/system/*`)

#### Health & Resources
```
GET /v1/system/health              # System health
GET /v1/system/resources           # Resource usage
GET /v1/system/time               # System time
GET /v1/system/services           # All services status
```

#### Runtime Control
```
POST /v1/system/runtime/{action}   # Actions: pause, resume, state
POST /v1/system/runtime/single-step # Execute single processing step
GET /v1/system/runtime/queue       # Processing queue status
```

#### Extended System Management (NEW)
```
GET /v1/system/services/health     # Detailed service health
GET /v1/system/services/selection-logic  # Service selection explanation
PUT /v1/system/services/{provider}/priority  # Update service priority
POST /v1/system/services/circuit-breakers/reset  # Reset circuit breakers
GET /v1/system/processors          # Get all processor states
```

#### Adapter Management
```
GET /v1/system/adapters            # List all adapters
GET /v1/system/adapters/{id}       # Get specific adapter
POST /v1/system/adapters/{type}    # Register new adapter
DELETE /v1/system/adapters/{id}    # Unregister adapter
PUT /v1/system/adapters/{id}/reload # Reload adapter
```

#### System Shutdown
```
POST /v1/system/shutdown
Body: {"reason": "Maintenance"}
```

### 5. Configuration (`/v1/config/*`)

#### Manage Configuration
```
GET /v1/config                     # Get all config
POST /v1/config                    # Update all config
GET /v1/config/{key}              # Get specific key
PUT /v1/config/{key}              # Set specific key
DELETE /v1/config/{key}           # Delete specific key
```

### 6. Telemetry (`/v1/telemetry/*`)

#### Metrics & Logs
```
GET /v1/telemetry/metrics          # All metrics
GET /v1/telemetry/metrics/{name}   # Specific metric detail
GET /v1/telemetry/logs            # System logs
GET /v1/telemetry/overview        # Telemetry overview
POST /v1/telemetry/query          # Query telemetry data
```

#### Resources
```
GET /v1/telemetry/resources        # Current resource usage
GET /v1/telemetry/resources/history # Historical resource data
```

#### Traces
```
GET /v1/telemetry/traces          # Distributed traces
```

### 7. Audit Trail (`/v1/audit/*`)

#### Audit Operations
```
GET /v1/audit/entries              # List audit entries
GET /v1/audit/entries/{id}         # Get specific entry
POST /v1/audit/search              # Search audit entries
GET /v1/audit/export              # Export audit data
GET /v1/audit/verify/{id}         # Verify entry integrity
```

### 8. Wise Authority (`/v1/wa/*`)

#### Deferral Management
```
GET /v1/wa/deferrals               # List deferrals
POST /v1/wa/deferrals/{id}/resolve # Resolve deferral
```

#### Guidance & Permissions
```
POST /v1/wa/guidance               # Request guidance
GET /v1/wa/permissions             # Get permissions
GET /v1/wa/status                  # WA status
```

### 9. Emergency Operations (`/emergency/*`)

**Note**: These endpoints bypass normal authentication and require signed requests.

```
POST /emergency/shutdown           # Emergency shutdown
GET /emergency/test               # Test emergency system
```

## WebSocket Support

Real-time updates via WebSocket:
```
ws://localhost:8080/v1/ws
```

Subscribe to channels:
```json
{"type": "subscribe", "channel": "agent_thoughts"}
```

## Response Format

All responses follow this structure:
```json
{
  "data": {...},
  "metadata": {
    "timestamp": "2025-01-03T21:00:00Z",
    "request_id": "xxx",
    "duration_ms": 100
  }
}
```

Error responses:
```json
{
  "detail": "Error message",
  "status": 400,
  "type": "validation_error"
}
```

## Rate Limiting

- Default: 100 requests per minute
- Burst: 20 requests
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## SDK Support

TypeScript SDK available with full type safety:
```typescript
import { CIRISClient } from '@ciris/sdk';

const client = new CIRISClient({
  baseURL: 'http://localhost:8080',
  apiKey: 'your-api-key'
});

// All 78+ methods available
const status = await client.agent.getStatus();
const health = await client.system.getServiceHealthDetails();
```

## Complete Endpoint List

Total: 78 endpoints across 12 modules

1. **Agent** (6 endpoints)
2. **Auth** (8 endpoints)  
3. **Memory** (10 endpoints)
4. **System** (19 endpoints including extensions)
5. **Config** (4 endpoints)
6. **Telemetry** (9 endpoints including metrics)
7. **Audit** (5 endpoints)
8. **Wise Authority** (5 endpoints)
9. **Users** (10 endpoints)
10. **Emergency** (2 endpoints)
11. **WebSocket** (1 endpoint)
12. **OpenAPI** (1 endpoint at `/openapi.json`)