# CIRIS Agent Secrets Management System

## Overview

The CIRIS Agent features a comprehensive secrets management system that automatically detects, encrypts, and securely manages sensitive information throughout the agent's operations. This system ensures that secrets like API keys, passwords, and tokens are never exposed in logs, memory, or communications while remaining accessible when needed.

## Architecture

The secrets management system consists of four main components:

### 1. Secrets Detection Engine (`ciris_engine/secrets/filter.py`)
- **Automatic Detection**: Uses regex patterns to identify secrets in text
- **Built-in Patterns**: Recognizes AWS keys, GitHub tokens, API keys, passwords, etc.
- **Custom Patterns**: Agents can define and manage their own detection rules
- **Sensitivity Levels**: LOW, MEDIUM, HIGH, CRITICAL classification

### 2. Encrypted Storage (`ciris_engine/secrets/store.py`)
- **AES-256-GCM Encryption**: Each secret encrypted with unique key
- **SQLite Backend**: Persistent storage with metadata
- **Access Logging**: Complete audit trail of all secret access
- **Rate Limiting**: Protection against brute force attempts

### 3. Secrets Service (`ciris_engine/secrets/service.py`)
- **Orchestration**: Coordinates detection, storage, and retrieval
- **Auto-Decapsulation**: Intelligent secret revealing based on action type
- **Context Processing**: Handles secrets in various data formats
- **Task Lifecycle**: Automatic cleanup after task completion

### 4. Agent Tools (`ciris_engine/secrets/tools.py`)
- **RECALL_SECRET**: Explicit secret retrieval with audit logging
- **UPDATE_SECRETS_FILTER**: Manage detection patterns and configuration
- **LIST_SECRETS**: Inventory and audit capabilities

## Key Features

### 🔍 **Automatic Detection**
```python
# Input message
"Here's my API key: sk-1234567890abcdef"

# Automatically becomes
"Here's my API key: SECRET_550e8400-e29b-41d4-a716-446655440000"
```

### 🔐 **Secure Storage**
- Per-secret encryption keys
- Cryptographic salts and nonces
- Complete audit trails
- SQLite database with proper schemas

### 🔄 **Natural Integration**
Secrets work seamlessly with existing agent operations:

- **MEMORIZE**: Automatically detects and encrypts secrets in memories
- **RECALL**: Auto-decrypts secrets when appropriate for the action type
- **FORGET**: Cleans up secret references when forgetting memories
- **Message Processing**: All incoming messages scanned automatically
- **Action Handlers**: Secrets decapsulated automatically when needed

### 🛠️ **Agent Tools**
The agent can manage secrets through natural tool calls:

```json
{
  "selected_action": "tool",
  "action_parameters": {
    "name": "recall_secret",
    "parameters": {
      "secret_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "purpose": "Need API key for external service call",
      "decrypt": true
    }
  }
}
```

## Integration Points

### Message Pipeline
All observers (Discord, CLI, API) automatically process incoming messages:

```python
# In DiscordObserver.handle_incoming_message()
processed_msg = await self._process_message_secrets(msg)
```

### Memory Operations
Graph memory automatically handles secrets:

```python
# LocalGraphMemoryService.memorize()
processed_node = await self._process_secrets_for_memorize(node)
```

### Action Handlers
Handlers automatically decapsulate secrets when needed:

```python
# In SpeakHandler.handle()
processed_result = await self._decapsulate_secrets_in_params(result, "speak")
```

### Context System
SystemSnapshot includes secrets information for agent introspection:

```python
class SystemSnapshot(BaseModel):
    detected_secrets: List[SecretReference] = Field(default_factory=list)
    secrets_filter_version: int = 0
    total_secrets_stored: int = 0
```

## Security Model

### Detection Patterns
Built-in patterns for common secrets:
- AWS Access Keys (`AKIA[0-9A-Z]{16}`)
- GitHub Tokens (`ghp_[a-zA-Z0-9]{36}`)
- API Keys (`sk-[a-zA-Z0-9]{48}`)
- Discord Tokens (`[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}`)
- Credit Cards, SSNs, and more

### Encryption Details
- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Management**: Per-secret encryption keys stored securely
- **Salt/Nonce**: Unique cryptographic parameters per secret
- **Integrity**: Built-in authentication prevents tampering

### Access Control
- **Purpose Tracking**: Every access requires stated purpose
- **Action-Based**: Decryption rules based on action type (speak, tool, etc.)
- **Audit Logging**: Complete trail of who accessed what and when
- **Rate Limiting**: Protection against excessive access attempts

### Auto-Decapsulation Rules
Default configuration automatically decrypts secrets for:
- `speak` actions (when agent needs to communicate secrets)
- `tool` actions (when tools need actual secret values)
- `memorize` actions (when storing in long-term memory)

## Configuration

### Filter Configuration
```python
class SecretsFilterConfig(BaseModel):
    filter_id: str
    version: int
    builtin_patterns_enabled: bool = True
    custom_patterns: List[SecretPattern] = []
    disabled_patterns: List[str] = []
    sensitivity_overrides: Dict[str, str] = {}
    require_confirmation_for: List[str] = ["CRITICAL"]
    auto_decrypt_for_actions: List[str] = ["speak", "tool"]
```

### Custom Pattern Example
```python
{
  "name": "slack_webhook",
  "regex": "https://hooks\\.slack\\.com/services/[A-Z0-9]{9}/[A-Z0-9]{11}/[a-zA-Z0-9]{24}",
  "description": "Slack Webhook URL",
  "sensitivity": "HIGH",
  "context_hint": "Slack integration webhook"
}
```

## Usage Examples

### Basic Detection and Storage
```python
secrets_service = SecretsService()

# Process text with potential secrets
processed_text, secret_refs = await secrets_service.process_incoming_text(
    "My API key is sk-1234567890abcdef",
    source_context={"operation": "user_message"}
)

# Text is now: "My API key is SECRET_550e8400-e29b-41d4-a716-446655440000"
# secret_refs contains metadata about detected secret
```

### Explicit Secret Retrieval
```python
from ciris_engine.secrets.tools import SecretsTools

tools = SecretsTools(secrets_service)

# Retrieve secret with audit logging
result = await tools.recall_secret(
    RecallSecretParams(
        secret_uuid="550e8400-e29b-41d4-a716-446655440000",
        purpose="Making API call to external service",
        decrypt=True
    )
)

# result.result_data["decrypted_value"] contains actual secret
```

### Pattern Management
```python
# Add custom detection pattern
await tools.update_secrets_filter(
    UpdateSecretsFilterParams(
        operation="add_pattern",
        pattern=SecretPattern(
            name="custom_token",
            regex="cust_[a-f0-9]{32}",
            description="Custom service token",
            sensitivity="HIGH",
            context_hint="Custom service authentication"
        )
    )
)
```

## Testing

Comprehensive test coverage includes:

### Unit Tests
- `tests/ciris_engine/secrets/test_filter.py` - Detection engine
- `tests/ciris_engine/secrets/test_store.py` - Encrypted storage
- `tests/ciris_engine/secrets/test_service.py` - Service orchestration
- `tests/ciris_engine/secrets/test_tools.py` - Agent tools

### Integration Tests
- `tests/ciris_engine/secrets/test_pipeline_integration.py` - End-to-end flow
- Message processing pipeline
- Memory operations integration
- Action handler decapsulation
- Context builder integration

### Security Tests
- Encryption/decryption validation
- Access control enforcement
- Audit trail verification
- Pattern matching accuracy

## Monitoring and Observability

### Telemetry Integration
The secrets system integrates with CIRIS telemetry:
- Secret detection rates
- Storage metrics
- Access patterns
- Performance metrics

### Audit Trails
Complete logging of:
- Secret detection events
- Access attempts (successful and failed)
- Configuration changes
- Pattern additions/modifications

### SystemSnapshot
Agent introspection includes:
- Recent secrets (non-sensitive metadata)
- Filter configuration version
- Total secrets count
- Detection statistics

## Best Practices

### For Users
1. **Trust the System**: Let automatic detection handle most cases
2. **Explicit Recall**: Use `RECALL_SECRET` tool only when necessary
3. **Purpose Documentation**: Always provide clear purpose for secret access
4. **Pattern Management**: Add custom patterns for domain-specific secrets

### For Developers
1. **Integration**: Use provided helper methods in BaseActionHandler
2. **Context**: Provide rich context in `source_context` parameters
3. **Error Handling**: Always handle encryption/decryption failures gracefully
4. **Testing**: Include secrets scenarios in integration tests

## Troubleshooting

### Common Issues

**Secret Not Detected**
- Check if pattern exists for secret type
- Verify pattern is enabled in configuration
- Consider adding custom pattern

**Decryption Failures**
- Verify secret UUID is correct
- Check action type is in `auto_decrypt_for_actions`
- Ensure sufficient permissions

**Performance Issues**
- Monitor pattern complexity (regex performance)
- Check storage database size
- Verify rate limiting isn't triggered

### Debug Information
Enable debug logging:
```python
import logging
logging.getLogger('ciris_engine.secrets').setLevel(logging.DEBUG)
```

## Future Enhancements

- **Key Rotation**: Automatic rotation of encryption keys
- **External Storage**: Integration with HashiCorp Vault, AWS Secrets Manager
- **Machine Learning**: ML-based secret detection for unknown patterns
- **Compliance**: GDPR, SOX, HIPAA compliance features
- **Federation**: Cross-agent secret sharing capabilities

---

*This secrets management system provides enterprise-grade security while maintaining the agent's natural language processing capabilities. All secrets are protected while remaining accessible when legitimately needed.*
