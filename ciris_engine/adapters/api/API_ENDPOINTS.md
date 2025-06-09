# CIRIS API Endpoints Quick Reference

## System Telemetry & Control

### Complete System State
```bash
GET /v1/system/telemetry          # Full telemetry snapshot
GET /v1/system/health             # System health status
```

### Component Information
```bash
GET /v1/system/adapters           # All registered adapters
GET /v1/system/services           # All registered services
GET /v1/system/configuration      # Complete system config
```

### Processor Control & Debugging
```bash
GET  /v1/system/processor         # Processor state
POST /v1/system/processor/step    # Single-step execution
POST /v1/system/processor/pause   # Pause processor
POST /v1/system/processor/resume  # Resume processor
GET  /v1/system/processor/queue   # Processing queue status
```

### Custom Metrics
```bash
POST /v1/system/metrics           # Record metric
GET  /v1/system/metrics/{name}    # Get metric history
```

## Core Services

### Communication
```bash
POST /v1/messages                 # Send message to agent
GET  /v1/messages                 # Get recent messages
GET  /v1/status                   # Communication status
```

### Memory Management
```bash
GET  /v1/memory/scopes            # Available memory scopes
GET  /v1/memory/{scope}/entries   # Entries in scope
POST /v1/memory/{scope}/store     # Store memory entry
```

### Tool Management
```bash
GET  /v1/tools                    # List available tools
POST /v1/tools/{tool_name}        # Execute tool
```

### Audit & Logging
```bash
GET /v1/audit                     # Get audit entries
GET /v1/logs/{filename}           # Stream log file
```

### Wise Authority
```bash
POST /v1/guidance                 # Request guidance
POST /v1/defer                    # Submit deferral
GET  /v1/wa/deferrals             # Get deferrals
GET  /v1/wa/deferrals/{id}        # Get specific deferral
POST /v1/wa/feedback              # Submit feedback
```

## Quick Testing Commands

### System Health Check
```bash
curl http://localhost:8080/v1/system/health
```

### Get All Registered Services
```bash
curl http://localhost:8080/v1/system/services | jq '.[] | {name, service_type, status}'
```

### Single Step Debug Session
```bash
# Pause processor
curl -X POST http://localhost:8080/v1/system/processor/pause

# Check current state
curl http://localhost:8080/v1/system/processor

# Execute one step
curl -X POST http://localhost:8080/v1/system/processor/step

# Resume normal operation
curl -X POST http://localhost:8080/v1/system/processor/resume
```

### Send Message to Agent
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello CIRIS", "channel_id": "api"}'
```

### Monitor System Resources
```bash
curl http://localhost:8080/v1/system/telemetry | jq '{
  uptime: .runtime_uptime_seconds,
  memory_mb: .memory_usage_mb,
  cpu_percent: .cpu_usage_percent,
  health: .overall_health
}'
```

### Check Failed Services
```bash
curl http://localhost:8080/v1/system/services | jq '.[] | select(.status != "healthy")'
```

## Error Responses

All endpoints return standard error format:
```json
{
  "error": "Description of the error",
  "status": "error",
  "timestamp": "2025-06-09T15:30:00Z"
}
```

## Status Codes
- `200` - Success
- `400` - Bad Request
- `404` - Not Found  
- `500` - Internal Server Error