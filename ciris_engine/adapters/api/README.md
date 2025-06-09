# CIRIS API Adapter Documentation

The CIRIS API Adapter provides a comprehensive HTTP REST API for interacting with the CIRIS Agent system. It exposes all major subsystems through a unified interface, enabling external applications, monitoring tools, and the CIRISGui to interact with the agent.

## Overview

The API adapter is built on `aiohttp` and provides:
- **Real-time system telemetry** and health monitoring
- **Complete configuration exposure** for debugging and introspection
- **Service registry inspection** with circuit breaker states
- **Processor control** including single-step debugging
- **Multi-service communication** with audit trails
- **Memory management** and tool execution
- **Log streaming** and audit trail access

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CIRISGui      │    │  External Tools  │    │  Monitoring     │
│   (Port 3000)   │    │                  │    │  Systems        │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    CIRIS API Adapter    │
                    │      (Port 8080)        │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
    ┌───────▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
    │ Multi-Service │   │ Telemetry       │   │ Agent       │
    │ Registry      │   │ Collector       │   │ Processor   │
    └───────────────┘   └─────────────────┘   └─────────────┘
```

## API Endpoints

### Core Communication

#### Messages
- **POST** `/v1/messages` - Send message to agent
- **GET** `/v1/messages?limit=N` - Get recent messages
- **GET** `/v1/status` - Get communication status

**Example: Send Message**
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello CIRIS", "channel_id": "api"}'
```

**Response:**
```json
{
  "status": "processed",
  "id": "276bf634-2419-42f1-bff2-4536d3874ef4"
}
```

### System Telemetry

#### Complete System State
- **GET** `/v1/system/telemetry` - Complete telemetry snapshot

**Response Structure:**
```json
{
  "timestamp": "2025-06-09T15:30:00Z",
  "schema_version": "v1.0",
  "basic_telemetry": {
    "thoughts_active": 0,
    "thoughts_24h": 15,
    "uptime_hours": 2.5,
    "messages_processed_24h": 8,
    "errors_24h": 0
  },
  "adapters": [...],
  "services": [...],
  "processor_state": {...},
  "configuration": {...},
  "runtime_uptime_seconds": 9000.0,
  "memory_usage_mb": 245.6,
  "cpu_usage_percent": 15.2,
  "overall_health": "healthy"
}
```

#### Component Information
- **GET** `/v1/system/adapters` - All registered platform adapters
- **GET** `/v1/system/services` - All registered services
- **GET** `/v1/system/processor` - Processor state
- **GET** `/v1/system/configuration` - System configuration
- **GET** `/v1/system/health` - System health status

**Example: Get Adapters**
```bash
curl http://localhost:8080/v1/system/adapters
```

**Response:**
```json
[
  {
    "name": "ApiPlatform",
    "type": "api",
    "status": "active",
    "capabilities": ["http_api", "rest_endpoints"],
    "metadata": {
      "class": "ApiPlatform",
      "instance_id": "140123456789"
    },
    "start_time": "2025-06-09T15:00:00Z"
  }
]
```

**Example: Get Services**
```bash
curl http://localhost:8080/v1/system/services
```

**Response:**
```json
[
  {
    "name": "APICommunicationService_136710555999488",
    "service_type": "communication",
    "handler": "SpeakHandler",
    "priority": "HIGH",
    "capabilities": ["send_message", "receive_message"],
    "status": "healthy",
    "circuit_breaker_state": "closed",
    "instance_id": "136710555999488"
  }
]
```

### Processor Control

#### Execution Control
- **POST** `/v1/system/processor/step` - Execute single processing step
- **POST** `/v1/system/processor/pause` - Pause processor
- **POST** `/v1/system/processor/resume` - Resume processor  
- **GET** `/v1/system/processor/state` - Get detailed processor state
- **GET** `/v1/system/processor/queue` - Get processing queue status

**Example: Single Step Debugging**
```bash
curl -X POST http://localhost:8080/v1/system/processor/step
```

**Response:**
```json
{
  "status": "completed",
  "round_number": 16,
  "execution_time_ms": 250,
  "before_state": {
    "thoughts_pending": 5,
    "current_round": 15
  },
  "after_state": {
    "thoughts_pending": 3,
    "current_round": 16
  },
  "summary": {
    "thoughts_processed": 2,
    "round_completed": true
  }
}
```

**Example: Pause/Resume Processor**
```bash
# Pause processor
curl -X POST http://localhost:8080/v1/system/processor/pause
# Response: {"success": true}

# Resume processor  
curl -X POST http://localhost:8080/v1/system/processor/resume
# Response: {"success": true}
```

**Example: Processor State**
```bash
curl http://localhost:8080/v1/system/processor/state
```

**Response:**
```json
{
  "is_running": true,
  "current_round": 44,
  "thoughts_pending": 2,
  "thoughts_processing": 1,
  "thoughts_completed_24h": 156,
  "last_activity": "2025-06-09T15:30:00Z",
  "processor_mode": "work",
  "idle_rounds": 0
}
```

### Memory Management

#### Memory Operations
- **GET** `/v1/memory/scopes` - Available memory scopes
- **GET** `/v1/memory/{scope}/entries` - Entries in a scope
- **POST** `/v1/memory/{scope}/store` - Store memory entry

**Example: Get Memory Scopes**
```bash
curl http://localhost:8080/v1/memory/scopes
```

**Response:**
```json
{
  "scopes": ["local", "identity", "environment", "community", "network"]
}
```

**Example: Store Memory**
```bash
curl -X POST http://localhost:8080/v1/memory/local/store \
  -H "Content-Type: application/json" \
  -d '{"key": "user_preference", "value": "dark_mode"}'
```

### Tool Management

#### Tool Operations
- **GET** `/v1/tools` - List available tools
- **POST** `/v1/tools/{tool_name}` - Execute tool

**Example: List Tools**
```bash
curl http://localhost:8080/v1/tools
```

**Response:**
```json
[
  {"name": "echo"},
  {"name": "web_search"},
  {"name": "file_read"}
]
```

**Example: Execute Tool**
```bash
curl -X POST http://localhost:8080/v1/tools/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello World"}'
```

### Audit & Logging

#### Audit Trail
- **GET** `/v1/audit?limit=N&event_type=TYPE` - Get audit entries

#### Log Streaming
- **GET** `/v1/logs/{filename}?tail=N` - Stream log files

**Example: Get Recent Logs**
```bash
curl "http://localhost:8080/v1/logs/latest.log?tail=50"
```

### Wise Authority

#### WA Operations
- **POST** `/v1/guidance` - Request guidance
- **POST** `/v1/defer` - Submit deferral
- **GET** `/v1/wa/deferrals` - Get deferrals
- **GET** `/v1/wa/deferrals/{id}` - Get specific deferral
- **POST** `/v1/wa/feedback` - Submit feedback

### Metrics & Time Series Database (TSDB)

#### Custom Metrics
- **POST** `/v1/system/metrics` - Record custom metric with tags
- **GET** `/v1/system/metrics/{name}/history?hours=N` - Get metric history

**Example: Record Metric with Tags**
```bash
curl -X POST http://localhost:8080/v1/system/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "metric_name": "api_response_time", 
    "value": 125.5, 
    "tags": {
      "endpoint": "/users",
      "method": "GET",
      "status": "200"
    }
  }'
```

**Example: Get Metric History**
```bash
curl "http://localhost:8080/v1/system/metrics/api_response_time/history?hours=24"
```

**Response:**
```json
{
  "metric_name": "api_response_time",
  "history": [
    {
      "timestamp": "2024-06-09T10:00:00Z",
      "value": 125.5,
      "tags": {"endpoint": "/users", "method": "GET", "status": "200"}
    },
    {
      "timestamp": "2024-06-09T10:15:00Z", 
      "value": 132.1,
      "tags": {"endpoint": "/users", "method": "GET", "status": "200"}
    }
  ]
}
```

#### TSDB Features
The CIRIS Agent now includes a built-in Time Series Database (TSDB) that stores:
- **Metrics**: Custom application metrics with tags
- **Logs**: Application logs with structured metadata
- **Audit Events**: Agent actions and decisions with full context

All TSDB data is stored as correlations in the database, enabling:
- Time-based queries and filtering
- Cross-correlation analysis between metrics, logs, and audit events
- Unified telemetry storage with backward compatibility
- Agent introspection and self-awareness capabilities

## Configuration

### Environment Variables
- `CIRIS_API_HOST` - API server host (default: 0.0.0.0)
- `CIRIS_API_PORT` - API server port (default: 8080)
- `NEXT_PUBLIC_CIRIS_API_URL` - Frontend API URL for CIRISGui

### Startup
The API adapter is automatically started when using `--modes api`:

```bash
python3 main.py --modes api
```

## Integration Examples

### CIRISGui Integration
The CIRISGui uses the `CIRISClient` TypeScript class to interact with all endpoints:

```typescript
const client = new CIRISClient('http://localhost:8080');

// Get system overview
const telemetry = await client.getTelemetrySnapshot();
const health = await client.getSystemHealth();

// Control processor
await client.pauseProcessing();
const result = await client.singleStep();
await client.resumeProcessing();

// Interact with agent
const response = await client.sendMessage("Hello CIRIS");
const messages = await client.getMessages(10);
```

### Monitoring Integration
External monitoring systems can use the health and telemetry endpoints:

```bash
# Health check
curl http://localhost:8080/v1/system/health

# Resource monitoring
curl http://localhost:8080/v1/system/telemetry | jq '.memory_usage_mb'

# Service status
curl http://localhost:8080/v1/system/services | jq '.[] | select(.status != "healthy")'
```

### Development & Debugging
Use processor control for development:

```bash
# Pause for debugging
curl -X POST http://localhost:8080/v1/system/processor/pause

# Execute one step at a time
curl -X POST http://localhost:8080/v1/system/processor/step

# Check queue status
curl http://localhost:8080/v1/system/processor/queue

# Resume normal operation
curl -X POST http://localhost:8080/v1/system/processor/resume
```

## Security Considerations

### Current Security Model
- **Local Network**: API runs on localhost by default
- **No Authentication**: Currently no auth layer (development mode)
- **Data Filtering**: Telemetry service includes security filters
- **Circuit Breakers**: Service-level protection against cascading failures

### Production Considerations
For production deployment, consider:
- **Authentication**: Add API key or JWT authentication
- **Rate Limiting**: Implement request rate limiting
- **HTTPS**: Use TLS encryption
- **Network Isolation**: Restrict network access
- **Input Validation**: Enhanced payload validation

## Error Handling

### Standard Error Responses
All endpoints return consistent error responses:

```json
{
  "error": "Description of the error",
  "status": "error",
  "timestamp": "2025-06-09T15:30:00Z"
}
```

### HTTP Status Codes
- **200** - Success
- **400** - Bad Request (invalid parameters)
- **404** - Not Found (invalid endpoint)
- **500** - Internal Server Error

### Circuit Breaker States
Services may be in different circuit breaker states:
- **closed** - Normal operation
- **open** - Service unavailable
- **half_open** - Testing recovery

## Performance Characteristics

### Response Times
- **System Health**: < 50ms
- **Telemetry Snapshot**: < 200ms
- **Service List**: < 100ms
- **Single Step**: 100ms - 5s (depends on processing)
- **Message Send**: < 100ms

### Resource Usage
- **Memory**: ~50MB additional for API adapter
- **CPU**: < 5% under normal load
- **Network**: Minimal overhead for telemetry collection

## Troubleshooting

### Common Issues

**API Server Not Responding**
```bash
# Check if server is running
curl http://localhost:8080/v1/system/health

# Check logs
curl http://localhost:8080/v1/logs/latest.log?tail=20
```

**Service Health Issues**
```bash
# Check individual service status
curl http://localhost:8080/v1/system/services | jq '.[] | select(.status != "healthy")'

# Check circuit breaker states
curl http://localhost:8080/v1/system/services | jq '.[] | select(.circuit_breaker_state != "closed")'
```

**Processor Issues**
```bash
# Check processor state
curl http://localhost:8080/v1/system/processor

# Check processing queue
curl http://localhost:8080/v1/system/processor/queue
```

### Debug Mode
Enable debug logging by starting with `--debug`:

```bash
python3 main.py --modes api --debug
```

## API Versioning

### Current Version
- **API Version**: v1
- **Schema Version**: v1.0
- **Endpoint Prefix**: `/v1/`

### Compatibility
- All v1 endpoints are stable
- New features added as new endpoints
- Breaking changes will increment version
- Legacy endpoints maintained for compatibility

## Contributing

### Adding New Endpoints
1. Create route handler in appropriate `/runtime/api/api_*.py` file
2. Register routes in `ApiPlatform._setup_routes()`
3. Update CIRISClient with new methods
4. Add tests for new functionality
5. Update this documentation

### Extending Telemetry
1. Add new fields to protocol models in `telemetry_interface.py`
2. Implement collection logic in `comprehensive_collector.py`
3. Update API response documentation
4. Add frontend UI components if needed

---

For more information, see:
- [CIRIS Engine Documentation](../../README.md)
- [Multi-Service Architecture](../../registries/README.md)
- [Telemetry System](../../telemetry/README.md)
- [CIRISGui Documentation](../../../CIRISGUI/README.md)