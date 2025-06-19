# Environment Variables Reference

This document provides a comprehensive reference for all environment variables supported by the CIRIS Agent configuration system.

## Core Configuration

### LLM Services
- `OPENAI_API_KEY` - **Required** - API key for OpenAI or compatible LLM service
- `OPENAI_API_BASE` / `OPENAI_BASE_URL` - Custom API base URL (e.g., Together.ai, local models)  
- `OPENAI_MODEL_NAME` - LLM model name override (default: gpt-4o-mini)

### Discord Integration
- `DISCORD_BOT_TOKEN` - **Required for Discord mode** - Discord bot token
- `DISCORD_CHANNEL_ID` - Discord channel ID for agent to monitor
- `DISCORD_DEFERRAL_CHANNEL_ID` - Channel ID for deferral reports
- `WA_USER_ID` - Discord User ID for Wise Authority mentions
- `WA_DISCORD_USER` - Fallback Discord username for WA (default: somecomputerguy)

### CIRISNode Integration
- `CIRISNODE_BASE_URL` - Base URL for CIRISNode service (default: https://localhost:8001)
- `CIRISNODE_AGENT_SECRET_JWT` - JWT token for CIRISNode authentication

## Security Configuration

### Secrets Management
- `SECRETS_MASTER_KEY` - **Highly Recommended** - Master encryption key for secrets storage
- `SECRETS_DB_PATH` - Path to secrets database file (default: secrets.db)
- `SECRETS_AUDIT_LOG` - Path to secrets audit log (default: secrets_audit.log)

### Telemetry Security  
- `TELEMETRY_ENCRYPTION_KEY` - Encryption key for telemetry data export
- `TELEMETRY_API_KEY` - API key for external telemetry endpoints
- `TELEMETRY_TLS_CERT` - TLS certificate path for secure telemetry export
- `TELEMETRY_TLS_KEY` - TLS private key path for secure telemetry export

## Operational Configuration

### Resource Management
- `RESOURCE_MEMORY_LIMIT` - Memory limit in MB (default: 256)
- `RESOURCE_CPU_LIMIT` - CPU usage limit percentage (default: 80)
- `RESOURCE_TOKENS_HOUR_LIMIT` - Hourly token usage limit (default: 10000)
- `RESOURCE_TOKENS_DAY_LIMIT` - Daily token usage limit (default: 100000)

### Database and Storage
- `CIRIS_DB_PATH` - Main database file path (default: ciris_engine.db)
- `CIRIS_DATA_DIR` - Data directory path (default: data)
- `CIRIS_ARCHIVE_DIR` - Archive directory path (default: data_archive)
- `GRAPH_MEMORY_PATH` - Graph memory file path (default: graph_memory.pkl)

### Audit and Logging
- `AUDIT_LOG_PATH` - Audit log file path (default: audit_logs.jsonl)
- `AUDIT_DB_PATH` - Signed audit database path (default: ciris_audit.db)
- `AUDIT_KEY_PATH` - Audit signing keys directory (default: audit_keys)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Advanced Configuration

### Network and Discovery
- `AGENT_IDENTITY_PATH` - Path to agent identity file for network participation
- `PEER_DISCOVERY_INTERVAL` - Peer discovery interval in seconds (default: 300)
- `REPUTATION_THRESHOLD` - Minimum reputation for peer trust (default: 30)

### Adaptive Filtering
- `FILTER_LEARNING_RATE` - Learning rate for adaptive filtering (default: 0.1)
- `FILTER_EFFECTIVENESS_THRESHOLD` - Effectiveness threshold for adjustments (default: 0.3)
- `FILTER_FALSE_POSITIVE_THRESHOLD` - False positive threshold (default: 0.2)

### Circuit Breaker Configuration
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` - Failure count to open circuit (default: 3)
- `CIRCUIT_BREAKER_RESET_TIMEOUT` - Reset timeout in seconds (default: 300)
- `CIRCUIT_BREAKER_TEST_INTERVAL` - Half-open test interval in seconds (default: 60)

### Performance Tuning
- `TELEMETRY_BUFFER_SIZE` - Main telemetry buffer size (default: 1000)
- `TELEMETRY_RETENTION_HOURS` - Telemetry data retention in hours (default: 1)
- `WORKFLOW_MAX_ROUNDS` - Maximum workflow processing rounds (default: 5)
- `DMA_TIMEOUT_SECONDS` - DMA evaluation timeout (default: 30.0)

## Development and Testing

### Mock Services
- `MOCK_LLM_ENABLED` - Enable mock LLM service for testing (true/false)
- `MOCK_NETWORK_ENABLED` - Enable mock network services for testing (true/false)
- `MOCK_WA_ENABLED` - Enable mock Wise Authority for testing (true/false)

### Debug Configuration
- `DEBUG_TELEMETRY` - Enable debug telemetry output (true/false)
- `DEBUG_SECRETS` - Enable debug secrets detection logging (true/false)
- `DEBUG_RESOURCE_MONITOR` - Enable debug resource monitoring (true/false)
- `DEBUG_ADAPTIVE_FILTER` - Enable debug adaptive filtering (true/false)

### Testing Overrides
- `TEST_MODE` - Enable test mode with relaxed security (true/false)
- `TEST_SECRETS_KEY` - Test encryption key for development
- `TEST_WA_TIMEOUT` - Shortened WA timeout for testing (seconds)

## Security Best Practices

### Required in Production
- `SECRETS_MASTER_KEY` - Use a strong, randomly generated key
- `TELEMETRY_ENCRYPTION_KEY` - Required if telemetry export is enabled
- `AUDIT_SIGNING_KEY` - Generated automatically but should be backed up

### Recommended Settings
- `LOG_LEVEL=INFO` - Production logging level
- `TELEMETRY_ENABLED=false` - Keep disabled unless needed
- `DEBUG_*=false` - Disable all debug flags in production
- `TEST_MODE=false` - Never enable in production

### Key Rotation
Environment variables that support automatic rotation:
- `SECRETS_MASTER_KEY` - Rotated every 90 days (configurable)
- `TELEMETRY_ENCRYPTION_KEY` - Manual rotation recommended every 90 days
- `CIRISNODE_AGENT_SECRET_JWT` - Managed by CIRISNode service

## Configuration Precedence

Configuration values are loaded in the following order (later values override earlier ones):

1. **Schema defaults** - Default values defined in configuration schemas
2. **base.yaml** - Base configuration file values
3. **Profile-specific config** - Agent profile configuration overrides  
4. **Environment variables** - Environment variable overrides
5. **Runtime arguments** - Command-line argument overrides

## Validation

The configuration system validates all values against the schema and will:
- **Fail to start** if required environment variables are missing
- **Log warnings** for deprecated or invalid configuration values
- **Use secure defaults** when optional security configurations are not provided
- **Require confirmation** for potentially dangerous configuration changes

## Examples

### Minimal Production Setup
```bash
export OPENAI_API_KEY="sk-your-key-here"
export DISCORD_BOT_TOKEN="your-bot-token"
export SECRETS_MASTER_KEY="$(openssl rand -base64 32)"
export LOG_LEVEL="INFO"
```

### Development Setup
```bash
export OPENAI_API_KEY="sk-your-dev-key"
export LOG_LEVEL="DEBUG"
export TEST_MODE="true"
export MOCK_LLM_ENABLED="true"
```

### High-Security Production
```bash
export OPENAI_API_KEY="sk-your-key-here"
export DISCORD_BOT_TOKEN="your-bot-token"
export SECRETS_MASTER_KEY="$(openssl rand -base64 32)"
export TELEMETRY_ENCRYPTION_KEY="$(openssl rand -base64 32)"
export LOG_LEVEL="WARNING"
export AUDIT_ENABLE_SIGNED="true"
export RESOURCE_MEMORY_LIMIT="128"
export CIRCUIT_BREAKER_FAILURE_THRESHOLD="2"
```

For more information on specific configuration sections, see the base.yaml file and the configuration schema documentation.