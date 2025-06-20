# API Trinity Design: Clean Capability Exposure

## Design Philosophy

The API should expose the complete set of agent capabilities defined by the Protocol-Module-Schema trinity, making the agent's abilities exhaustively clear and elegantly accessible.

## Core Capability Endpoints

### 1. Communication Capabilities
**Protocol**: `CommunicationService`
```http
POST /v1/communicate/send         # Send message (SPEAK action)
GET  /v1/communicate/messages     # Fetch messages (OBSERVE action) 
GET  /v1/communicate/status       # Channel status
```

### 2. Memory Capabilities  
**Protocol**: `MemoryService`
```http
POST /v1/memory/memorize          # Store memory (MEMORIZE action)
POST /v1/memory/recall            # Retrieve memory (RECALL action)
POST /v1/memory/forget            # Remove memory (FORGET action)
GET  /v1/memory/search            # Search memories
GET  /v1/memory/timeseries        # Time-based recall
```

### 3. Tool Capabilities
**Protocol**: `ToolService`
```http
GET  /v1/tools                    # List available tools
GET  /v1/tools/{name}/info        # Tool details
POST /v1/tools/{name}/execute     # Execute tool (TOOL action)
GET  /v1/tools/{id}/result        # Get execution result
```

### 4. Reasoning Capabilities
**Protocol**: `LLMService`
```http
POST /v1/reasoning/think          # Process thought
POST /v1/reasoning/ponder         # Deep reflection (PONDER action)
GET  /v1/reasoning/status         # LLM service status
```

### 5. Guidance Capabilities
**Protocol**: `WiseAuthorityService`
```http
POST /v1/guidance/request         # Request guidance
POST /v1/guidance/defer           # Defer decision (DEFER action)
GET  /v1/guidance/deferrals       # List deferrals
POST /v1/guidance/feedback        # Provide feedback
```

### 6. Monitoring Capabilities
**Protocol**: `TelemetryService`
```http
POST /v1/telemetry/metric         # Record metric
GET  /v1/telemetry/metrics/{name} # Get metric history
GET  /v1/telemetry/snapshot       # Full system telemetry
GET  /v1/telemetry/health         # Health status
```

### 7. Security Capabilities
**Protocol**: `SecretsService`
```http
POST /v1/security/detect          # Detect secrets in content
POST /v1/security/filter          # Filter sensitive data
GET  /v1/security/stats           # Security service stats
```

### 8. Accountability Capabilities
**Protocol**: `AuditService`
```http
GET  /v1/audit/trail              # Get audit trail
GET  /v1/audit/actions/{type}     # Filter by action type
POST /v1/audit/query              # Complex audit queries
```

### 9. Control Capabilities
**Protocol**: `RuntimeControlService`
```http
GET  /v1/control/status           # Runtime status
POST /v1/control/pause            # Pause processing
POST /v1/control/resume           # Resume processing
POST /v1/control/step             # Single-step execution
GET  /v1/control/queue            # Queue status
```

## Composite Operations

These endpoints combine multiple capabilities to perform complete agent actions:

```http
# Complete message handling (OBSERVE → THINK → SPEAK)
POST /v1/agent/process-message
{
  "message": "Hello CIRIS",
  "channel_id": "api",
  "context": {}
}

# Complete task execution (RECALL → TOOL → MEMORIZE)
POST /v1/agent/execute-task
{
  "task": "analyze logs",
  "parameters": {}
}

# Complete decision flow (PONDER → DEFER/REJECT/ACCEPT)
POST /v1/agent/make-decision
{
  "question": "Should I proceed?",
  "context": {}
}
```

## Schema-Driven Responses

Every endpoint returns typed, validated responses:

```typescript
// Not this:
response: { [key: string]: any }  // ❌

// But this:
response: MessageResponse         // ✅
response: MemoryOpResult         // ✅
response: ToolExecutionResult    // ✅
```

## Capability Discovery

```http
GET /v1/capabilities
```

Returns the complete capability matrix:
```json
{
  "actions": {
    "external": ["OBSERVE", "SPEAK", "TOOL"],
    "control": ["REJECT", "PONDER", "DEFER"],
    "memory": ["MEMORIZE", "RECALL", "FORGET"],
    "terminal": ["TASK_COMPLETE"]
  },
  "services": {
    "communication": {...},
    "memory": {...},
    "tool": {...},
    "llm": {...},
    "wise_authority": {...},
    "telemetry": {...},
    "secrets": {...},
    "audit": {...},
    "runtime_control": {...}
  },
  "schemas": {
    "input": [...],
    "output": [...]
  }
}
```

## Implementation Notes

1. **Unified Resource Model**: Each capability is a resource with standard operations
2. **Consistent Naming**: Endpoints match protocol method names
3. **Type Safety**: All inputs/outputs use Pydantic schemas
4. **Correlation IDs**: Every operation returns a correlation ID for tracing
5. **Async by Default**: All operations are non-blocking

## Benefits

1. **Clarity**: API structure mirrors the agent's actual capabilities
2. **Completeness**: Every protocol method is exposed
3. **Consistency**: Same patterns across all endpoints
4. **Discoverability**: Self-documenting through capability endpoint
5. **Type Safety**: Schema validation at every boundary

This design makes the trinity's power accessible through a clean, RESTful interface that directly reflects the agent's fundamental capabilities.