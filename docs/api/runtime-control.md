# CIRIS Runtime Control API

## Overview

The CIRIS Agent Runtime Control API provides comprehensive management capabilities for the agent system during operation. These endpoints enable dynamic reconfiguration, debugging, and monitoring without requiring system restarts.

**Note**: The adapter management system uses `adapter` to specify adapter types (cli, discord, api, etc.) throughout the API.

**Base URL**: `/v1/runtime/`

## Key Features

- **Hot-Swappable Adapters**: Load/unload platform adapters (Discord, CLI, API) at runtime with support for multiple instances
- **Live Configuration**: Update configuration values with validation and rollback support
- **Processor Control**: Single-stepping, pause/resume for debugging
- **Profile Management**: Switch between agent profiles dynamically
- **Comprehensive Auditing**: All operations logged with cryptographic audit trails
- **Configuration Backup/Restore**: Safe configuration management with backup support

---

## 1. Processor Control

### Single Step Execution
Execute a single processing step for debugging purposes.

```http
POST /v1/runtime/processor/step
```

**Response**:
```json
{
  "success": true,
  "action": "single_step",
  "timestamp": "2025-06-11T10:30:00Z",
  "result": {
    "round_number": 16,
    "execution_time_ms": 250,
    "thoughts_processed": 2
  }
}
```

### Pause Processing
Temporarily pause the processor for debugging or maintenance.

```http
POST /v1/runtime/processor/pause
```

**Response**:
```json
{
  "success": true,
  "action": "pause",
  "timestamp": "2025-06-11T10:30:00Z",
  "result": {"status": "paused"}
}
```

### Resume Processing
Resume a paused processor.

```http
POST /v1/runtime/processor/resume
```

**Response**:
```json
{
  "success": true,
  "action": "resume", 
  "timestamp": "2025-06-11T10:30:00Z",
  "result": {"status": "running"}
}
```

### Get Queue Status
Get current processor queue status and processing metrics.

```http
GET /v1/runtime/processor/queue
```

**Response**:
```json
{
  "queue_size": 3,
  "processing": true,
  "thoughts_pending": 2,
  "thoughts_processing": 1,
  "average_processing_time_ms": 180,
  "last_processed": "2025-06-11T10:44:30Z"
}
```

### Shutdown Runtime
Initiate graceful shutdown of the entire runtime system.

```http
POST /v1/runtime/processor/shutdown
Content-Type: application/json

{
  "reason": "Maintenance shutdown requested via API"
}
```

**Response**:
```json
{
  "success": true,
  "action": "shutdown",
  "timestamp": "2025-06-11T10:30:00Z",
  "result": {
    "status": "shutdown_initiated",
    "reason": "Maintenance shutdown requested via API"
  }
}
```

---

## 2. Adapter Management

### Load Adapter
Load a new adapter instance at runtime with specified configuration.

**Note**: Multiple instances of the same adapter type can run simultaneously with different IDs and configurations.

**Supported Adapter Types**:
- `cli` - Command-line interface adapter
- `discord` - Discord bot adapter  
- `api` - HTTP API server adapter

**Configuration Parameters**:

**Discord Adapter**:
- `bot_token` (required) - Discord bot token
- `channel_id` (required) - Home channel ID for the bot

**API Adapter**:
- `host` (optional) - Server host (default: 0.0.0.0)
- `port` (optional) - Server port (default: 8080)

**CLI Adapter**:
- No specific parameters required

**Auto-Generated Adapter IDs**: If `adapter_id` is not provided, it will be auto-generated as `{adapter_type}_{counter}` (e.g., "discord_1", "api_2").

```http
POST /v1/runtime/adapters
Content-Type: application/json

{
  "adapter_type": "discord",
  "adapter_id": "discord_bot_prod",
  "config": {
    "bot_token": "your_bot_token",
    "channel_id": "123456789012345678"
  },
  "auto_start": true
}
```

**Response**:
```json
{
  "success": true,
  "adapter_id": "discord_bot_prod",
  "adapter": "discord",
  "services_registered": 3,
  "loaded_at": "2025-06-11T10:30:00Z"
}
```

### Unload Adapter
Remove an adapter instance from the runtime.

```http
DELETE /v1/runtime/adapters/discord_bot_prod?force=true
```

**Query Parameters**:
- `force` (boolean) - Force unload even if adapter is busy

**Response**:
```json
{
  "success": true,
  "adapter_id": "discord_bot_prod",
  "adapter": "discord",
  "services_unregistered": 3,
  "was_running": true
}
```

### List Adapters
Get a list of all currently loaded adapters.

```http
GET /v1/runtime/adapters
```

**Response**:
```json
[
  {
    "adapter_id": "api_main",
    "adapter": "api",
    "is_running": true,
    "health_status": "healthy",
    "services_count": 2,
    "loaded_at": "2025-06-11T09:00:00Z",
    "config_params": {"host": "0.0.0.0", "port": 8080}
  },
  {
    "adapter_id": "discord_bot_prod", 
    "adapter": "discord",
    "is_running": true,
    "health_status": "healthy",
    "services_count": 3,
    "loaded_at": "2025-06-11T10:30:00Z",
    "config_params": {"bot_token": "[REDACTED]", "channel_id": "123456789012345678"}
  }
]
```

### Get Adapter Info
Get detailed information about a specific adapter.

```http
GET /v1/runtime/adapters/discord_bot_prod
```

**Response**:
```json
{
  "adapter_id": "discord_bot_prod",
  "adapter": "discord",
  "config": {
    "bot_token": "[REDACTED]",
    "channel_id": "123456789012345678"
  },
  "load_time": "2025-06-11T10:30:00Z",
  "is_running": true
}
```

---

## 3. Configuration Management

### Get Configuration
Retrieve configuration values using dot notation paths.

```http
GET /v1/runtime/config?path=llm_services.openai&include_sensitive=false
```

**Query Parameters**:
- `path` (string, optional) - Configuration path using dot notation
- `include_sensitive` (boolean) - Include sensitive values (requires auth)

**Response**:
```json
{
  "path": "llm_services.openai",
  "value": {
    "model_name": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2048
  },
  "scope": "runtime",
  "timestamp": "2025-06-11T10:30:00Z"
}
```

### Update Configuration
Update configuration values at runtime with validation.

```http
PUT /v1/runtime/config
Content-Type: application/json

{
  "path": "llm_services.openai.temperature",
  "value": 0.8,
  "scope": "runtime",
  "validation_level": "strict",
  "reason": "Adjusting temperature for more creative responses"
}
```

**Configuration Scopes**:
- `runtime` - Changes only affect current session (not persisted)
- `session` - Changes persist until restart
- `persistent` - Changes are written to configuration files

**Validation Levels**:
- `strict` - Full validation with type checking
- `basic` - Basic validation only
- `none` - No validation (dangerous)

**Response**:
```json
{
  "success": true,
  "operation": "update_config",
  "timestamp": "2025-06-11T10:30:00Z",
  "path": "llm_services.openai.temperature",
  "old_value": 0.7,
  "new_value": 0.8,
  "scope": "runtime",
  "message": "Configuration updated successfully"
}
```

### Validate Configuration
Validate configuration data before applying changes.

```http
POST /v1/runtime/config/validate
Content-Type: application/json

{
  "config_data": {
    "llm_services": {
      "openai": {
        "model_name": "gpt-4",
        "temperature": 1.5
      }
    }
  },
  "config_path": "llm_services.openai"
}
```

**Response**:
```json
{
  "valid": false,
  "errors": ["Temperature must be between 0.0 and 1.0"],
  "warnings": [],
  "suggestions": ["Consider using temperature between 0.3 and 0.9 for optimal results"]
}
```

### Reload Configuration
Reload configuration from files, discarding runtime changes.

```http
POST /v1/runtime/config/reload
```

**Response**:
```json
{
  "success": true,
  "operation": "reload_config",
  "timestamp": "2025-06-11T10:30:00Z",
  "changes_discarded": 3,
  "message": "Configuration reloaded from files"
}
```

---

## 4. Agent Profile Management

### List Profiles
Get a list of all available agent profiles.

```http
GET /v1/runtime/profiles
```

**Response**:
```json
[
  {
    "name": "default",
    "description": "Default CIRIS agent profile",
    "file_path": "/path/to/ciris_profiles/default.json",
    "is_active": true,
    "permitted_actions": ["OBSERVE", "SPEAK", "TOOL", "MEMORIZE"],
    "created_time": "2025-06-11T09:00:00Z"
  },
  {
    "name": "teacher",
    "description": "Educational assistant profile",
    "file_path": "/path/to/ciris_profiles/teacher.json", 
    "is_active": false,
    "permitted_actions": ["OBSERVE", "SPEAK", "DEFER"],
    "created_time": "2025-06-11T09:15:00Z"
  }
]
```

### Load Profile
Load an agent profile at runtime, switching the agent's behavior and configuration.

```http
POST /v1/runtime/profiles/teacher/load
Content-Type: application/json

{
  "config_path": "/custom/path/to/profile.json",
  "scope": "session"
}
```

**Response**:
```json
{
  "success": true,
  "operation": "reload_profile",
  "timestamp": "2025-06-11T10:30:00Z",
  "path": "profile:teacher",
  "previous_profile": "default",
  "adapters_reloaded": ["discord_bot_prod"],
  "message": "Profile 'teacher' loaded successfully"
}
```

### Get Profile Info
Get detailed information about a specific profile.

```http
GET /v1/runtime/profiles/teacher
```

**Response**:
```json
{
  "name": "teacher",
  "description": "Educational assistant profile",
  "file_path": "/path/to/ciris_profiles/teacher.json",
  "is_active": false,
  "permitted_actions": ["OBSERVE", "SPEAK", "DEFER"],
  "adapter_configs": {
    "discord": {"educational_mode": true},
    "api": {"rate_limit": 100}
  },
  "created_time": "2025-06-11T09:15:00Z",
  "modified_time": "2025-06-11T10:00:00Z"
}
```

---

## 5. Environment Variable Management

### List Environment Variables
Get current environment variables (with optional sensitive data).

```http
GET /v1/runtime/env?include_sensitive=false
```

**Query Parameters**:
- `include_sensitive` (boolean) - Include sensitive values (requires auth)

**Response**:
```json
{
  "CIRIS_API_HOST": "0.0.0.0",
  "CIRIS_API_PORT": "8080",
  "OPENAI_API_KEY": "[REDACTED]",
  "variables_count": 12,
  "sensitive_count": 3
}
```

### Set Environment Variable
Set an environment variable at runtime.

```http
PUT /v1/runtime/env/CUSTOM_SETTING
Content-Type: application/json

{
  "value": "new_value",
  "persist": false,
  "reload_config": true
}
```

**Request Parameters**:
- `persist` (boolean) - Also save to .env file
- `reload_config` (boolean) - Reload configuration after setting

**Response**:
```json
{
  "success": true,
  "operation": "set_env_var",
  "variable_name": "CUSTOM_SETTING",
  "timestamp": "2025-06-11T10:30:00Z",
  "persisted": false,
  "config_reloaded": true,
  "message": "Environment variable set successfully"
}
```

### Delete Environment Variable
Remove an environment variable.

```http
DELETE /v1/runtime/env/CUSTOM_SETTING?persist=false&reload_config=true
```

**Query Parameters**:
- `persist` (boolean) - Also remove from .env file
- `reload_config` (boolean) - Reload config after deletion

**Response**:
```json
{
  "success": true,
  "operation": "delete_env_var",
  "variable_name": "CUSTOM_SETTING",
  "timestamp": "2025-06-11T10:30:00Z",
  "removed_from_file": false,
  "config_reloaded": true,
  "message": "Environment variable deleted successfully"
}
```

---

## 6. Configuration Backup & Restore

### Create Backup
Create a backup of current configuration state.

```http
POST /v1/runtime/config/backup
Content-Type: application/json

{
  "include_profiles": true,
  "include_env_vars": false,
  "backup_name": "pre_upgrade_backup"
}
```

**Response**:
```json
{
  "success": true,
  "operation": "backup_config",
  "backup_name": "pre_upgrade_backup",
  "timestamp": "2025-06-11T10:30:00Z",
  "backup_path": "/path/to/backups/pre_upgrade_backup_20250611103000",
  "files_included": [
    "config.json",
    "ciris_profiles/default.json",
    "ciris_profiles/teacher.json"
  ],
  "total_size_bytes": 12584,
  "message": "Configuration backed up successfully"
}
```

### Restore Configuration
Restore configuration from a backup.

```http
POST /v1/runtime/config/restore
Content-Type: application/json

{
  "backup_name": "pre_upgrade_backup",
  "restore_profiles": true,
  "restore_env_vars": false,
  "restart_required": true
}
```

**Response**:
```json
{
  "success": true,
  "operation": "restore_config",
  "backup_name": "pre_upgrade_backup",
  "timestamp": "2025-06-11T10:30:00Z",
  "files_restored": [
    "config.json",
    "ciris_profiles/default.json"
  ],
  "requires_restart": true,
  "message": "Configuration restored successfully. Restart required for full effect."
}
```

### List Backups
Get a list of available configuration backups.

```http
GET /v1/runtime/config/backups
```

**Response**:
```json
[
  {
    "backup_name": "pre_upgrade_backup",
    "created_time": "2025-06-11T10:30:00Z",
    "files_count": 3,
    "size_bytes": 12584,
    "backup_path": "/path/to/backups/pre_upgrade_backup_20250611103000"
  },
  {
    "backup_name": "daily_backup_20250611",
    "created_time": "2025-06-11T00:00:00Z", 
    "files_count": 5,
    "size_bytes": 18392,
    "backup_path": "/path/to/backups/daily_backup_20250611_000000"
  }
]
```

---

## 7. Runtime Status & Monitoring

### Get Runtime Status
Get a summary of current runtime status.

```http
GET /v1/runtime/status
```

**Response**:
```json
{
  "processor_status": "running",
  "active_adapters": ["api_main", "discord_bot_prod"],
  "loaded_adapters": ["api_main", "discord_bot_prod", "cli_backup"],
  "current_profile": "teacher",
  "config_scope": "runtime",
  "uptime_seconds": 7200.5,
  "last_config_change": "2025-06-11T10:30:00Z",
  "health_status": "healthy"
}
```

### Get Runtime Snapshot
Get a complete detailed snapshot of runtime state.

```http
GET /v1/runtime/snapshot
```

**Response**:
```json
{
  "timestamp": "2025-06-11T10:45:00Z",
  "processor_status": "running",
  "adapters": [
    {
      "adapter_id": "api_main",
      "adapter": "api",
      "is_running": true,
      "health_status": "healthy",
      "config_params": {"host": "0.0.0.0", "port": 8080},
      "services_count": 2,
      "loaded_at": "2025-06-11T09:00:00Z"
    }
  ],
  "configuration": {
    "llm_services": {"openai": {"model_name": "gpt-4"}},
    "resources": {"memory": {"limit": 256.0}}
  },
  "active_profile": "teacher",
  "loaded_profiles": ["default", "teacher", "student"],
  "uptime_seconds": 7500.2,
  "memory_usage_mb": 256.8,
  "system_health": "healthy",
  "environment_variables_count": 12,
  "last_backup": "2025-06-11T10:30:00Z"
}
```

---

## Security & Authorization

### Current Security Model
- **Development Mode**: No authentication required when running locally
- **Production Recommendations**: 
  - Use API keys or JWT tokens for authentication
  - Run behind reverse proxy with TLS
  - Restrict network access to authorized clients
  - Enable audit logging for all operations

### Sensitive Data Handling
- Configuration values marked as sensitive are automatically redacted
- Use `include_sensitive=true` query parameter to access sensitive data (requires auth)
- All sensitive operations are logged in audit trails

### Rate Limiting
- Default rate limits apply to configuration update operations
- Adapter loading/unloading operations have built-in throttling
- Circuit breaker protection for external service dependencies

---

## Error Handling

### Standard Error Response
All endpoints return consistent error responses:

```json
{
  "error": "Detailed error description",
  "error_code": "CONFIG_VALIDATION_FAILED",
  "status": "error", 
  "timestamp": "2025-06-11T10:30:00Z",
  "details": {
    "validation_errors": ["Temperature must be between 0.0 and 1.0"],
    "suggestions": ["Use a value between 0.3 and 0.9"]
  }
}
```

### HTTP Status Codes
- **200 OK** - Successful operation
- **201 Created** - Resource created (adapter loaded)
- **202 Accepted** - Operation queued for processing
- **400 Bad Request** - Invalid request or validation error
- **404 Not Found** - Adapter, profile, or configuration path not found
- **409 Conflict** - Resource already exists or conflicting operation
- **500 Internal Server Error** - Server-side error
- **501 Not Implemented** - Feature planned but not yet available
- **503 Service Unavailable** - System overloaded or shutting down

---

## Audit Trail & Logging

### Automatic Auditing
All runtime control operations are automatically logged with:

- **Operation Type** - The specific action performed
- **Parameters** - Full request parameters and context
- **Outcome** - Success/failure status and detailed results
- **Timestamp** - Precise operation timing
- **Correlation ID** - For tracking related operations
- **User Context** - Authentication and authorization details

### Console Output
Real-time feedback is provided on the console:

```
[RUNTIME_CONTROL] processor_control.pause COMPLETED (status=paused)
[RUNTIME_CONTROL] adapter_control.load COMPLETED (adapter_type=discord, adapter_id=bot_prod, auto_start=true)
[RUNTIME_CONTROL] config_control.update COMPLETED (path=llm.temperature, scope=runtime)
```

### Audit Query API
Access audit logs through the main audit API endpoints:

```http
GET /v1/audit/query?action=runtime_control.*&start_time=2025-06-11T10:00:00Z
```

---

## Example Workflows

### 1. Hot-Swap Discord Bot Configuration

```bash
# Get current Discord adapter info
curl -X GET http://localhost:8080/v1/runtime/adapters/discord_main

# Unload existing Discord adapter
curl -X DELETE http://localhost:8080/v1/runtime/adapters/discord_main

# Load Discord adapter with new configuration
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "discord", 
    "adapter_id": "discord_main",
    "config": {
      "bot_token": "your_new_token",
      "channel_id": "987654321012345678"
    },
    "auto_start": true
  }'

# Verify the new adapter is running
curl -X GET http://localhost:8080/v1/runtime/adapters/discord_main
```

### 2. Debug Processor Issues

```bash
# Pause processing for debugging
curl -X POST http://localhost:8080/v1/runtime/processor/pause

# Check queue status
curl -X GET http://localhost:8080/v1/runtime/processor/queue

# Execute single steps while debugging
curl -X POST http://localhost:8080/v1/runtime/processor/step
curl -X POST http://localhost:8080/v1/runtime/processor/step

# Resume normal processing
curl -X POST http://localhost:8080/v1/runtime/processor/resume
```

### 2.5. Load Multiple Adapters

```bash
# Load multiple Discord bots for different servers
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "discord",
    "adapter_id": "discord_server1",
    "config": {"bot_token": "token1", "channel_id": "123456789"},
    "auto_start": true
  }'

curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "discord", 
    "adapter_id": "discord_server2",
    "config": {"bot_token": "token2", "channel_id": "987654321"},
    "auto_start": true
  }'

# Load API adapter on different port
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "api",
    "adapter_id": "api_alt",
    "config": {"host": "127.0.0.1", "port": 8081},
    "auto_start": true
  }'

# List all adapters to verify
curl -X GET http://localhost:8080/v1/runtime/adapters
```

### 3. Switch Agent Profiles

```bash
# List available profiles
curl -X GET http://localhost:8080/v1/runtime/profiles

# Load teacher profile for educational mode
curl -X POST http://localhost:8080/v1/runtime/profiles/teacher/load \
  -H "Content-Type: application/json" \
  -d '{"scope": "session"}'

# Verify profile switch
curl -X GET http://localhost:8080/v1/runtime/status
```

### 4. Configuration Backup & Restore

```bash
# Create backup before major changes
curl -X POST http://localhost:8080/v1/runtime/config/backup \
  -H "Content-Type: application/json" \
  -d '{
    "backup_name": "pre_update_backup",
    "include_profiles": true,
    "include_env_vars": false
  }'

# Make configuration changes...
# (various config updates)

# Restore if something goes wrong
curl -X POST http://localhost:8080/v1/runtime/config/restore \
  -H "Content-Type: application/json" \
  -d '{
    "backup_name": "pre_update_backup",
    "restore_profiles": true
  }'
```

---

## Integration with Service Architecture

### Service Registry Integration
The runtime control service integrates with the CIRIS service registry:

- **Telemetry Collector** - Processor control and monitoring
- **Adapter Manager** - Dynamic adapter lifecycle management  
- **Config Manager** - Configuration validation and persistence
- **Audit Service** - Comprehensive operation logging
- **Secrets Service** - Secure handling of sensitive configuration

### Multi-Service Coordination
Runtime control operations coordinate across multiple services:

1. **Configuration Updates** trigger service reloads
2. **Adapter Changes** update service registrations
3. **Profile Switches** reconfigure all affected services
4. **Shutdown Operations** coordinate graceful service termination

### Event Propagation
Runtime control events are propagated to:

- **Audit System** - For compliance and forensic analysis
- **Telemetry System** - For operational metrics and alerting
- **Service Registry** - For service discovery updates
- **Adapter Managers** - For coordination across platform adapters

This runtime control API provides comprehensive management capabilities while maintaining the CIRIS Agent's focus on ethical reasoning, security, and operational excellence.