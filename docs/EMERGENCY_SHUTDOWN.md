# Emergency Shutdown Endpoint

## Overview

The Emergency Shutdown endpoint provides a cryptographically secure way to immediately shutdown CIRIS agents without requiring API authentication. Instead, the signature itself serves as authentication.

## Endpoint

```
POST /emergency/shutdown
```

Note: This endpoint is mounted at the root level, NOT under `/v1/`.

## Security Model

The endpoint implements multiple layers of security:

1. **Ed25519 Signature Verification**: Commands must be signed with a valid Ed25519 private key
2. **Timestamp Validation**: Commands must be issued within a 5-minute window
3. **Authority Verification**: Only pre-authorized public keys can issue shutdown commands
4. **Command Type Restriction**: Only `SHUTDOWN_NOW` commands are accepted

## Request Format

```json
{
  "command_id": "cmd_unique_id",
  "command_type": "SHUTDOWN_NOW",
  "wa_id": "wa_authority_001",
  "wa_public_key": "base64_encoded_public_key",
  "issued_at": "2025-01-01T12:00:00Z",
  "expires_at": null,
  "reason": "Emergency maintenance required",
  "target_agent_id": null,
  "target_tree_path": null,
  "signature": "base64_encoded_signature",
  "parent_command_id": null,
  "relay_chain": []
}
```

## Response Format

### Success (200)
```json
{
  "data": {
    "command_received": "2025-01-01T12:00:00Z",
    "command_verified": true,
    "verification_error": null,
    "shutdown_initiated": "2025-01-01T12:00:01Z",
    "services_stopped": ["service1", "service2"],
    "data_persisted": true,
    "final_message_sent": true,
    "shutdown_completed": "2025-01-01T12:00:05Z",
    "exit_code": 0
  },
  "metadata": {
    "timestamp": "2025-01-01T12:00:05Z",
    "request_id": "req_123"
  }
}
```

### Failure (400/403)
```json
{
  "detail": "Invalid signature"
}
```

## Signature Generation

The signature must be generated over a specific subset of the command data:

```python
sign_data = {
    "command_id": command_id,
    "command_type": "SHUTDOWN_NOW",
    "wa_id": wa_id,
    "issued_at": issued_at.isoformat(),
    "reason": reason,
    "target_agent_id": target_agent_id,
}
message = json.dumps(sign_data, sort_keys=True).encode()
signature = private_key.sign(message)
```

## Testing

A test endpoint is available to verify the emergency routes are accessible:

```
GET /emergency/test
```

Returns:
```json
{
  "status": "ok",
  "message": "Emergency endpoint accessible",
  "crypto_available": true,
  "timestamp": "2025-01-01T12:00:00Z"
}
```

## Example Usage

See `/examples/emergency_shutdown_example.py` for a complete example of:
- Generating Ed25519 keypairs
- Creating signed shutdown commands
- Sending commands to the API

## Configuration

In production, authorized public keys should be configured through:
- Environment variables
- Secure configuration service
- Hardware security modules (HSM)

Never hardcode private keys in the application code.

## Integration with Runtime Control

The emergency endpoint will:
1. First attempt to use RuntimeControlService if available
2. Fall back to direct shutdown service access if RuntimeControl is not available
3. Ensure immediate shutdown regardless of system state

## Audit Trail

All emergency shutdown attempts are:
- Logged at CRITICAL level
- Recorded in the audit trail (if available)
- Include full command details and verification results
