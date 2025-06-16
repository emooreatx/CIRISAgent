# CIRIS Agent API Reference (v1.0-beta)

The CIRIS Agent provides a comprehensive REST API for interacting with the agent system. All endpoints use JSON for request/response bodies.

## Base URL
```
http://localhost:8080
```

## Authentication

The CIRIS API uses JWT-based authentication for protected endpoints. Authentication tokens can be obtained through:

1. **OAuth Authentication** - Login via Google, Discord, or GitHub
2. **WA CLI Authentication** - Using Wise Authority certificates
3. **Anonymous Access** - Limited read-only access for observers

See [OAuth Authentication Endpoints](api/oauth_endpoints.md) for detailed OAuth documentation.

### Using Authentication Tokens

Include the JWT token in the Authorization header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## API Categories

The CIRIS API is organized into the following categories:

1. **[Authentication Endpoints](api/oauth_endpoints.md)** - OAuth login and JWT session management ⭐ **NEW**
2. **[Communication Endpoints](#communication-endpoints)** - Message sending and conversation management
3. **[Runtime Control Endpoints](#runtime-control-endpoints)** - Live system management and debugging ⭐ **NEW**
4. **[Memory Service Endpoints](#memory-service-endpoints)** - Agent memory storage and retrieval
5. **[Wise Authority Endpoints](#wise-authority-endpoints)** - Ethical guidance and deferral management
6. **[Tool Service Endpoints](#tool-service-endpoints)** - Tool execution and validation
7. **[Audit Service Endpoints](#audit-service-endpoints)** - Audit trail and compliance logging
8. **[Log Streaming Endpoints](#log-streaming-endpoints)** - Real-time log access
9. **[System Telemetry Endpoints](#system-telemetry-endpoints)** - System monitoring and metrics

---

## API Endpoints

### Communication Endpoints

#### Send Message
```http
POST /v1/messages
```
Send a message to the CIRIS agent for processing.

**Request Body:**
```json
{
  "content": "Hello, CIRIS!",
  "author_id": "user123",        // Optional, defaults to "api_user"
  "author_name": "John Doe",     // Optional, defaults to "API User"
  "channel_id": "general"        // Optional, defaults to "api"
}
```

**Response:**
```json
{
  "status": "processed",
  "id": "59c30930-d68f-41bd-8721-aa5d6b01ae1c"
}
```

#### Get Messages
```http
GET /v1/messages?limit=20&channel_id=api
```
Retrieve conversation history including both user messages and agent responses.

**Query Parameters:**
- `limit` (integer, optional): Maximum number of messages to return (default: 20)
- `channel_id` (string, optional): Filter messages by channel (default: "api")

**Response:**
```json
{
  "messages": [
    {
      "id": "msg-123",
      "content": "Hello, CIRIS!",
      "author_id": "user123",
      "author_name": "John Doe",
      "timestamp": "2025-06-15T12:00:00Z",
      "is_outgoing": false
    },
    {
      "id": "resp-456",
      "content": "Hello! How can I help you today?",
      "author_id": "ciris_agent",
      "author_name": "CIRIS Agent",
      "timestamp": "2025-06-15T12:00:01Z",
      "is_outgoing": true
    }
  ]
}
```

#### Get Status
```http
GET /v1/status
```
Get the current status of the API and the last response.

**Response:**
```json
{
  "status": "ok",
  "last_response": {
    "content": "Hello! How can I help you?",
    "timestamp": "2025-06-15T12:00:01Z"
  }
}
```

---

## Runtime Control Endpoints

⭐ **NEW**: The runtime control endpoints enable dynamic management of the CIRIS Agent system without requiring restarts. These endpoints provide comprehensive control over processor execution, adapter management, configuration updates, and system monitoring.

> **📖 Detailed Documentation**: For complete runtime control API documentation with examples and workflows, see [Runtime Control API Guide](./api/runtime-control.md).

### Key Features

- **Hot-Swappable Adapters**: Load/unload Discord, CLI, and API adapters at runtime
- **Live Configuration**: Update configuration with validation and rollback support  
- **Processor Control**: Single-stepping, pause/resume for debugging
- **Agent Creation**: Create new agents with identity management
- **Configuration Backup/Restore**: Safe configuration management

### Quick Reference

#### Processor Control
```http
POST /v1/runtime/processor/step      # Execute single processing step
POST /v1/runtime/processor/pause     # Pause processor
POST /v1/runtime/processor/resume    # Resume processor
GET  /v1/runtime/processor/queue     # Get queue status
POST /v1/runtime/processor/shutdown  # Graceful shutdown
```

#### Adapter Management
```http
POST   /v1/runtime/adapters                    # Load adapter
DELETE /v1/runtime/adapters/{adapter_id}       # Unload adapter
GET    /v1/runtime/adapters                    # List adapters
GET    /v1/runtime/adapters/{adapter_id}       # Get adapter info
```

#### Configuration Management
```http
GET  /v1/runtime/config                        # Get configuration
PUT  /v1/runtime/config                        # Update configuration
POST /v1/runtime/config/validate               # Validate config
POST /v1/runtime/config/reload                 # Reload from files
```

#### Agent Management ⚠️ **UPDATED**
```http
POST /v1/agents/create                         # Create new agent (WA required)
POST /v1/agents/{agent_id}/initialize          # Initialize agent identity
# Note: Profile switching removed - identity is now graph-based
```

#### Environment Variables
```http
GET    /v1/runtime/env                         # List env vars
PUT    /v1/runtime/env/{var_name}              # Set env var
DELETE /v1/runtime/env/{var_name}              # Delete env var
```

#### Backup & Restore
```http
POST /v1/runtime/config/backup                 # Create backup
POST /v1/runtime/config/restore                # Restore backup
GET  /v1/runtime/config/backups                # List backups
```

#### Status & Monitoring
```http
GET /v1/runtime/status                         # Runtime status
GET /v1/runtime/snapshot                       # Complete snapshot
```

### Example: Hot-Swap Discord Bot

Load a new Discord adapter instance:
```bash
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "discord",
    "adapter_id": "discord_prod",
    "config": {
      "token": "your_bot_token",
      "home_channel": "general"
    },
    "auto_start": true
  }'
```

### Example: Debug Processor

Pause processor and execute single steps:
```bash
curl -X POST http://localhost:8080/v1/runtime/processor/pause
curl -X POST http://localhost:8080/v1/runtime/processor/step
curl -X POST http://localhost:8080/v1/runtime/processor/resume
```

---

### Memory Service Endpoints

#### List Memory Scopes
```http
GET /v1/memory/scopes
```
Get available memory scopes.

**Response:**
```json
{
  "scopes": ["identity", "personal", "interpersonal", "environmental", "physical", "global", "local"]
}
```

#### List Memory Entries
```http
GET /v1/memory/{scope}/entries
```
List all entries in a specific memory scope.

**Response:**
```json
{
  "entries": [
    {
      "id": "concept_123",
      "type": "CONCEPT",
      "attributes": {"value": "Important information"}
    }
  ]
}
```

#### Store Memory
```http
POST /v1/memory/{scope}/store
```
Store a new memory entry.

**Request Body:**
```json
{
  "key": "user_preference_theme",
  "value": "dark_mode"
}
```

**Response:**
```json
{
  "result": "ok"
}
```

#### Search Memories
```http
POST /v1/memory/search
```
Search memories by query.

**Request Body:**
```json
{
  "query": "user preferences",
  "scope": "local",
  "limit": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "user_preference_theme",
      "type": "CONCEPT",
      "scope": "local",
      "attributes": {"value": "dark_mode"},
      "relevance": 0.95
    }
  ]
}
```

#### Recall Memory Node
```http
POST /v1/memory/recall
```
Recall a specific memory node.

**Request Body:**
```json
{
  "node_id": "user_preference_theme",
  "scope": "local",
  "node_type": "CONCEPT"
}
```

**Response:**
```json
{
  "data": {
    "id": "user_preference_theme",
    "type": "CONCEPT",
    "scope": "local",
    "attributes": {"value": "dark_mode"}
  }
}
```

#### Forget Memory
```http
DELETE /v1/memory/{scope}/{node_id}
```
Remove a specific memory node.

**Response:**
```json
{
  "result": "forgotten"
}
```

#### Get Memory Timeseries
```http
GET /v1/memory/timeseries?scope=local&hours=24&correlation_types=metric_datapoint
```
Get time-series memory data.

**Query Parameters:**
- `scope` (string, optional): Memory scope (default: "local")
- `hours` (integer, optional): Hours of history (default: 24)
- `correlation_types` (array, optional): Types of correlations to include

**Response:**
```json
{
  "timeseries": [
    {
      "timestamp": "2025-06-15T12:00:00Z",
      "metric_name": "response_time",
      "value": 1.23
    }
  ]
}
```

### Wise Authority Endpoints

#### Fetch Guidance
```http
POST /v1/guidance
```
Request guidance from the Wise Authority system.

**Request Body:**
```json
{
  "context": "User is asking about ethical implications of AI"
}
```

**Response:**
```json
{
  "guidance": "Consider the principles of beneficence and non-maleficence...",
  "result": "Consider the principles of beneficence and non-maleficence..."
}
```

#### Submit Deferral
```http
POST /v1/defer
```
Defer a decision to human authority.

**Request Body:**
```json
{
  "thought_id": "thought_123",
  "reason": "This decision requires human judgment due to ethical complexity"
}
```

**Response:**
```json
{
  "result": "deferred"
}
```

#### List Deferrals
```http
GET /v1/wa/deferrals
```
Get list of all deferrals.

**Response:**
```json
[
  {
    "id": "deferral-1",
    "thought_id": "thought_123",
    "reason": "Ethical complexity",
    "timestamp": "2025-06-15T12:00:00Z"
  }
]
```

#### Get Deferral Detail
```http
GET /v1/wa/deferrals/{deferral_id}
```
Get details of a specific deferral.

**Response:**
```json
{
  "id": "deferral-1",
  "thought_id": "thought_123",
  "reason": "Ethical complexity",
  "timestamp": "2025-06-15T12:00:00Z",
  "status": "pending"
}
```

#### Submit Feedback
```http
POST /v1/wa/feedback
```
Submit feedback on a deferral.

**Request Body:**
```json
{
  "thought_id": "thought_123",
  "feedback": "Approved with modifications..."
}
```

**Response:**
```json
{
  "result": "submitted"
}
```

### Tool Service Endpoints

#### List Tools
```http
GET /v1/tools
```
Get list of available tools.

**Response:**
```json
[
  {"name": "echo"},
  {"name": "calculator"},
  {"name": "web_search"}
]
```

#### Execute Tool
```http
POST /v1/tools/{tool_name}
```
Execute a specific tool.

**Request Body:**
```json
{
  "text": "Hello, world!"  // Parameters depend on the tool
}
```

**Response:**
```json
{
  "result": "Hello, world!"
}
```

#### Validate Tool Parameters
```http
POST /v1/tools/{tool_name}/validate
```
Validate parameters for a tool without executing it.

**Request Body:**
```json
{
  "text": "Hello, world!"
}
```

**Response:**
```json
{
  "valid": true
}
```

### Audit Service Endpoints

#### Get Audit Trail
```http
GET /v1/audit
```
Get the last 100 audit log entries.

**Response:**
```json
[
  {
    "id": "audit_123",
    "action_type": "send_message",
    "timestamp": "2025-06-15T12:00:00Z",
    "context": {...}
  }
]
```

#### Query Audit Trail
```http
POST /v1/audit/query
```
Query audit trail with filters.

**Request Body:**
```json
{
  "start_time": "2025-06-15T00:00:00Z",
  "end_time": "2025-06-15T23:59:59Z",
  "action_types": ["send_message", "defer"],
  "thought_id": "thought_123",
  "task_id": "task_456",
  "limit": 50
}
```

**Response:**
```json
{
  "entries": [
    {
      "id": "audit_123",
      "action_type": "send_message",
      "timestamp": "2025-06-15T12:00:00Z",
      "thought_id": "thought_123",
      "task_id": "task_456",
      "context": {...}
    }
  ]
}
```

#### Log Audit Event
```http
POST /v1/audit/log
```
Log a custom audit event.

**Request Body:**
```json
{
  "event_type": "custom_action",
  "event_data": {
    "user": "admin",
    "action": "config_change",
    "details": "Updated memory retention policy"
  }
}
```

**Response:**
```json
{
  "status": "logged"
}
```

### Log Streaming Endpoints

#### Get Log File
```http
GET /v1/logs/{filename}?tail=100
```
Stream the contents of a log file.

**Path Parameters:**
- `filename`: Name of the log file (e.g., "ciris.log")

**Query Parameters:**
- `tail` (integer, optional): Number of lines from the end (default: 100)

**Response:**
```
2025-06-15 12:00:00 INFO Starting CIRIS agent...
2025-06-15 12:00:01 INFO Agent initialized successfully
...
```

### System Telemetry Endpoints

#### Get Telemetry Snapshot
```http
GET /v1/system/telemetry
```
Get complete system telemetry data.

**Response:**
```json
{
  "timestamp": "2025-06-15T12:00:00Z",
  "schema_version": "v1.0",
  "basic_telemetry": {
    "thoughts_active": 5,
    "thoughts_24h": 150,
    "avg_latency_ms": 250,
    "uptime_hours": 24.5,
    "resources": {
      "memory_mb": 512,
      "cpu_percent": 15.5
    }
  },
  "adapters": [...],
  "services": [...],
  "processor_state": {...},
  "configuration": {...}
}
```

#### Get System Health
```http
GET /v1/system/health
```
Get system health status.

**Response:**
```json
{
  "overall": "healthy",
  "details": {
    "adapters": "all_healthy",
    "services": "all_healthy",
    "processor": "running"
  }
}
```

#### Get Adapters Info
```http
GET /v1/system/adapters
```
Get information about active adapters.

**Response:**
```json
[
  {
    "name": "ApiPlatform",
    "type": "api",
    "status": "active",
    "capabilities": ["send_message", "receive_message"],
    "metadata": {...}
  }
]
```

#### Get Services Info
```http
GET /v1/system/services
```
Get information about registered services.

**Response:**
```json
[
  {
    "name": "APICommunicationService",
    "service_type": "communication",
    "handler": "SpeakHandler",
    "priority": "HIGH",
    "capabilities": ["send_message", "receive_message"],
    "status": "healthy"
  }
]
```

#### Get Processor State
```http
GET /v1/system/processor/state
```
Get current processor state.

**Response:**
```json
{
  "is_running": true,
  "current_round": 42,
  "thoughts_pending": 3,
  "thoughts_processing": 1,
  "thoughts_completed_24h": 150,
  "processor_mode": "work",
  "idle_rounds": 0
}
```

#### Get Configuration
```http
GET /v1/system/configuration
```
Get current system configuration.

**Response:**
```json
{
  "agent_identity": "default",  // From graph, not profile
  "startup_channel_id": "0.0.0.0:8000",
  "llm_model": "gpt-4o-mini",
  "llm_base_url": null,
  "database_path": null,
  "telemetry_enabled": true,
  "debug_mode": false,
  "adapter_modes": ["ApiPlatform"]
}
```

#### Single Step Processor
```http
POST /v1/system/processor/step
```
Execute a single processing step (useful for debugging).

**Response:**
```json
{
  "thoughts_processed": 1,
  "new_thoughts_created": 2
}
```

#### Pause Processor
```http
POST /v1/system/processor/pause
```
Pause the thought processor.

**Response:**
```json
{
  "success": true
}
```

#### Resume Processor
```http
POST /v1/system/processor/resume
```
Resume the thought processor.

**Response:**
```json
{
  "success": true
}
```

#### Get Processing Queue
```http
GET /v1/system/processor/queue
```
Get current processing queue status.

**Response:**
```json
{
  "pending_thoughts": 3,
  "pending_tasks": 5,
  "oldest_pending": "2025-06-15T11:55:00Z"
}
```

#### Record Metric
```http
POST /v1/system/metrics
```
Record a custom metric.

**Request Body:**
```json
{
  "metric_name": "custom_metric",
  "value": 42.5,
  "tags": {
    "source": "api",
    "user": "admin"
  }
}
```

**Response:**
```json
{
  "status": "recorded"
}
```

#### Get Metrics History
```http
GET /v1/system/metrics/{metric_name}/history?hours=24
```
Get historical data for a specific metric.

**Query Parameters:**
- `hours` (integer, optional): Hours of history to retrieve (default: 24)

**Response:**
```json
{
  "metric_name": "response_time",
  "history": [
    {
      "timestamp": "2025-06-15T11:00:00Z",
      "value": 250.5,
      "tags": {"source": "api"}
    },
    {
      "timestamp": "2025-06-15T12:00:00Z",
      "value": 245.2,
      "tags": {"source": "api"}
    }
  ]
}
```

## Error Responses

All endpoints return standard HTTP status codes and JSON error responses:

```json
{
  "error": "Description of the error"
}
```

Common status codes:
- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error
- `501 Not Implemented` - Feature not available

## Rate Limiting

Currently, there are no rate limits on the API. This will be added in future versions.

## Versioning

The API uses URL versioning. All v1 endpoints are prefixed with `/v1/`.

## Legacy Endpoints

For backward compatibility, the following legacy endpoint is still supported:

```http
POST /api/v1/message
```

This works identically to `POST /v1/messages` but is deprecated and will be removed in v2.0.

---

*Copyright © 2025 Eric Moore and CIRIS L3C - Apache 2.0 License*