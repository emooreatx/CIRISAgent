# CIRIS API Reference

## Overview

CIRIS provides a comprehensive REST API with 78 endpoints across 12 modules for agent interaction, system management, and observability.

**Base URL**: `http://localhost:8080`  
**API Version**: `v1` (stable)  
**Authentication**: JWT Bearer tokens (except `/emergency/*` endpoints)

## Quick Start

### 1. Authentication

```bash
# Login
curl -X POST http://localhost:8080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "ciris_admin_password"}'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1Q...",
  "token_type": "bearer",
  "user": {
    "user_id": "admin",
    "username": "admin",
    "api_role": "SYSTEM_ADMIN"
  }
}
```

### 2. Send a Message

```bash
# Use the token from login
curl -X POST http://localhost:8080/v1/agent/interact \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello CIRIS!", "channel_id": "api_user"}'
```

## API Modules

### 1. Agent Interaction (`/v1/agent`)
Core endpoints for interacting with the CIRIS agent.

- `POST /interact` - Send message to agent
- `GET /status` - Get agent status
- `GET /identity` - Get agent identity
- `GET /history` - Get conversation history
- `GET /channels` - List active channels

### 2. System Management (`/v1/system`)
System control, health monitoring, and adapter management.

- `GET /health` - System health status
- `GET /services` - Status of all 19 services
- `GET /adapters` - List registered adapters
- `POST /adapters/{type}` - Register adapter
- `DELETE /adapters/{id}` - Unregister adapter
- `POST /runtime/{action}` - Runtime control (pause/resume)
- `GET /runtime/queue` - Processing queue status
- `POST /runtime/single-step` - Debug single step
- `GET /processors` - Cognitive processor states

### 3. Memory Operations (`/v1/memory`)
Graph-based memory storage and retrieval.

- `POST /store` - Create memory node
- `POST /query` - Query memory graph
- `GET /search` - Full-text search
- `GET /visualize/graph` - Generate visualization
- `GET /stats` - Memory statistics
- `GET /timeline` - Chronological view

### 4. User Management (`/v1/users`)
User accounts, roles, and Wise Authority management.

- `GET /` - List users
- `POST /` - Create user
- `GET /{userId}` - Get user details
- `PUT /{userId}` - Update user
- `PUT /{userId}/password` - Change password
- `GET /{userId}/api-keys` - List API keys
- `POST /{userId}/mint-wa` - Mint as Wise Authority

### 5. Telemetry (`/v1/telemetry`)
Metrics, logs, traces, and resource monitoring.

- `GET /overview` - Metrics summary
- `GET /metrics` - All metrics
- `GET /logs` - System logs
- `GET /traces` - Request traces
- `GET /resources/history` - Historical usage

### 6. Configuration (`/v1/config`)
Dynamic configuration management.

- `GET /` - Get all config
- `GET /{key}` - Get specific value
- `PUT /{key}` - Set value
- `DELETE /{key}` - Delete value

### 7. Audit Trail (`/v1/audit`)
Comprehensive audit logging.

- `GET /entries` - List audit entries
- `POST /search` - Search entries
- `GET /export` - Export audit data
- `POST /verify` - Verify integrity

### 8. Wise Authority (`/v1/wa`)
Moral guidance and decision deferral.

- `GET /status` - WA system status
- `GET /permissions` - List permissions
- `GET /deferrals` - Pending deferrals
- `POST /guidance` - Request guidance
- `POST /defer` - Defer decision

### 9. Authentication (`/v1/auth`)
Authentication and authorization.

- `POST /login` - Login
- `GET /me` - Current user
- `POST /refresh` - Refresh token
- `POST /logout` - Logout

### 10. Emergency (`/emergency`)
Emergency endpoints (no auth required).

- `GET /health` - Basic health check
- `POST /shutdown` - Emergency shutdown (Ed25519 signature required)

### 11. WebSocket (`/v1/ws`)
Real-time bidirectional communication.

```javascript
// Connect with token
const ws = new WebSocket('ws://localhost:8080/v1/ws?token=<your-token>');

// Subscribe to events
ws.send(JSON.stringify({
  type: 'subscribe',
  events: ['agent.message', 'system.status']
}));
```

## Authentication & Roles

### API Roles
- `OBSERVER` - Read-only access
- `ADMIN` - System administration
- `AUTHORITY` - Wise Authority member
- `SYSTEM_ADMIN` - Full system access

### Wise Authority Roles
- `ORACLE` - Knowledge keeper
- `STEWARD` - Resource guardian
- `HARBINGER` - Change agent
- `ROOT` - Supreme authority

## TypeScript SDK

```typescript
import { CIRISClient } from '@ciris/sdk';

const client = new CIRISClient({ 
  baseURL: 'http://localhost:8080' 
});

// Login
await client.auth.login('admin', 'password');

// Interact with agent
const response = await client.agent.interact('Hello!');

// Query memory
const memories = await client.memory.search('important');

// Get system status
const health = await client.system.getHealth();
```

## Rate Limiting

- Default: 100 requests per minute per user
- Burst: 20 requests
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

## Error Responses

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "message",
      "reason": "Required field missing"
    }
  }
}
```

### Common Error Codes
- `UNAUTHORIZED` - Invalid or missing token
- `FORBIDDEN` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `VALIDATION_ERROR` - Invalid input
- `RATE_LIMITED` - Too many requests
- `INTERNAL_ERROR` - Server error

## Advanced Features

### 1. Runtime Control
Control agent processing in real-time:

```bash
# Pause processing
curl -X POST http://localhost:8080/v1/system/runtime/pause \
  -H "Authorization: Bearer <token>" \
  -d '{"duration": 60}'

# Single-step debugging
curl -X POST http://localhost:8080/v1/system/runtime/single-step \
  -H "Authorization: Bearer <token>"
```

### 2. Service Management
Manage the 19 CIRIS services:

```bash
# Update service priority
curl -X PUT http://localhost:8080/v1/system/services/memory_provider/priority \
  -H "Authorization: Bearer <token>" \
  -d '{"priority": 1, "priority_group": 0}'

# Reset circuit breakers
curl -X POST http://localhost:8080/v1/system/services/circuit-breakers/reset \
  -H "Authorization: Bearer <token>"
```

### 3. Adapter Registration
Register communication adapters dynamically:

```bash
# Register Discord adapter
curl -X POST http://localhost:8080/v1/system/adapters/discord \
  -H "Authorization: Bearer <token>" \
  -d '{
    "config": {
      "bot_token": "...",
      "server_id": "...",
      "enabled": true
    }
  }'
```

### 4. Memory Visualization
Generate interactive graph visualizations:

```bash
# Get timeline visualization
curl -X GET "http://localhost:8080/v1/memory/visualize/graph?layout=timeline&hours=24" \
  -H "Authorization: Bearer <token>"
```

### 5. Emergency Shutdown
Shutdown with Ed25519 signature:

```bash
# Generate signature with private key
SIGNATURE=$(echo -n "EMERGENCY_SHUTDOWN:reason" | \
  openssl dgst -sha256 -sign private_key.pem | base64)

# Shutdown
curl -X POST http://localhost:8080/emergency/shutdown \
  -d "{
    \"reason\": \"Critical error\",
    \"signature\": \"$SIGNATURE\",
    \"public_key\": \"<base64-public-key>\"
  }"
```

## Best Practices

1. **Authentication**: Store tokens securely, refresh before expiry
2. **Rate Limiting**: Implement exponential backoff
3. **Error Handling**: Check response codes and error details
4. **Pagination**: Use page/page_size for large datasets
5. **WebSocket**: Handle reconnection logic
6. **Monitoring**: Track X-Request-ID for debugging

## Support

- GitHub Issues: https://github.com/CIRISAI/CIRISAgent/issues
- Documentation: https://docs.ciris.ai
- Community: Discord server (link in README)