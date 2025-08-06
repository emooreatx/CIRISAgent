# CIRIS API Endpoints Quick Reference

## Agent Interaction

### Messages - Primary Interface
```bash
POST /v1/agent/messages           # Send message to agent
GET  /v1/agent/messages/{channel} # Get messages from channel
GET  /v1/agent/channels           # List active channels
GET  /v1/agent/channels/{id}      # Get channel info
GET  /v1/agent/status             # Agent status & identity
```

## Memory Observability (Read-Only)

### Graph Memory
```bash
GET /v1/memory/graph/nodes        # Browse nodes (?type=, ?scope=)
GET /v1/memory/graph/nodes/{id}   # Node details
GET /v1/memory/graph/relationships # Memory connections
GET /v1/memory/graph/search?q=    # Search graph
GET /v1/memory/identity           # Agent identity
```

### Memory Organization
```bash
GET /v1/memory/scopes             # Available scopes
GET /v1/memory/scopes/{scope}/nodes # Nodes in scope
GET /v1/memory/timeseries         # Time-series data
GET /v1/memory/timeline?hours=24  # Memory timeline
```

## Visibility - Agent Reasoning

### Current State
```bash
GET /v1/visibility/thoughts       # Current thoughts
GET /v1/visibility/tasks          # Active tasks
GET /v1/visibility/system-snapshot # System awareness
```

### Decision Tracking
```bash
GET /v1/visibility/decisions      # Recent DMA decisions
GET /v1/visibility/correlations   # Service interactions
GET /v1/visibility/tasks/{id}     # Task with thoughts
GET /v1/visibility/thoughts/{id}  # Thought details
```

## Telemetry - Monitoring

### System Metrics
```bash
GET  /v1/telemetry/overview       # Full telemetry
GET  /v1/telemetry/metrics        # Current metrics
GET  /v1/telemetry/metrics/{name} # Metric history
POST /v1/telemetry/metrics        # Record custom metric
```

### Resources & Health
```bash
GET /v1/telemetry/resources       # Resource usage
GET /v1/telemetry/resources/history # Resource history
GET /v1/telemetry/services        # All services health
GET /v1/telemetry/services/{type} # Service type details
```

### Audit
```bash
GET /v1/telemetry/audit           # Audit entries
GET /v1/telemetry/audit/stats     # Audit statistics
```

## Runtime Control

### Processor
```bash
POST /v1/runtime/processor/step   # Single-step
POST /v1/runtime/processor/pause  # Pause
POST /v1/runtime/processor/resume # Resume
GET  /v1/runtime/processor/queue  # Queue status
```

### System Management
```bash
GET  /v1/runtime/config           # Get config
PUT  /v1/runtime/config           # Update config
POST /v1/runtime/adapters         # Load adapter
GET  /v1/runtime/services         # Service registry
```

## Authentication

```bash
GET  /v1/auth/wa/status           # WA auth status
POST /v1/auth/wa/defer            # Submit deferral
GET  /v1/auth/oauth/providers     # OAuth providers
GET  /v1/auth/oauth/{provider}/login # Start OAuth
```

## Quick Testing Commands

### Send Message & Get Response
```bash
# Send message
curl -X POST http://localhost:8080/v1/agent/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello CIRIS!"}'

# Get messages from channel
curl http://localhost:8080/v1/agent/messages/api_default
```

### Explore Memory
```bash
# Search graph
curl "http://localhost:8080/v1/memory/graph/search?q=purpose"

# Get agent identity
curl http://localhost:8080/v1/memory/identity

# Browse nodes by type
curl "http://localhost:8080/v1/memory/graph/nodes?type=IDENTITY"
```

### View Agent Thinking
```bash
# Current thoughts
curl http://localhost:8080/v1/visibility/thoughts

# Active tasks
curl http://localhost:8080/v1/visibility/tasks

# Recent decisions
curl http://localhost:8080/v1/visibility/decisions?limit=10
```

### Monitor System
```bash
# Resource usage
curl http://localhost:8080/v1/telemetry/resources

# Service health
curl http://localhost:8080/v1/telemetry/services

# System overview
curl http://localhost:8080/v1/telemetry/overview
```

### Debug Session
```bash
# Pause processor
curl -X POST http://localhost:8080/v1/runtime/processor/pause

# Step through processing
curl -X POST http://localhost:8080/v1/runtime/processor/step

# Resume
curl -X POST http://localhost:8080/v1/runtime/processor/resume
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
