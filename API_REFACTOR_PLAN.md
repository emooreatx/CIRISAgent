# API Refactor Plan: Role-Based Access & Emergency Shutdown

## Overview

This plan details the refactoring of the CIRIS API to implement proper role-based access control (OBSERVER/ADMIN/AUTHORITY/ROOT), secure configuration filtering, and an emergency shutdown mechanism.

## Phase 1: Authentication & Role Management (Week 1)

### 1.1 Role Definition Schema

Create clear role definitions and permissions:

```python
# ciris_engine/schemas/api/auth.py
from enum import Enum
from typing import Set, Optional
from pydantic import BaseModel, Field

class UserRole(str, Enum):
    """User roles in order of increasing privilege."""
    OBSERVER = "OBSERVER"
    ADMIN = "ADMIN"
    AUTHORITY = "AUTHORITY"
    ROOT = "ROOT"
    
    @property
    def level(self) -> int:
        """Numeric privilege level for comparison."""
        return {
            "OBSERVER": 1,
            "ADMIN": 2,
            "AUTHORITY": 3,
            "ROOT": 4
        }[self.value]
    
    def has_permission(self, required_role: "UserRole") -> bool:
        """Check if this role meets or exceeds required role."""
        return self.level >= required_role.level

class Permission(str, Enum):
    """Granular permissions."""
    # Observer permissions
    VIEW_MESSAGES = "view_messages"
    VIEW_TELEMETRY = "view_telemetry"
    VIEW_REASONING = "view_reasoning"
    VIEW_CONFIG = "view_config"  # Filtered view
    
    # Admin permissions
    MANAGE_CONFIG = "manage_config"
    RUNTIME_CONTROL = "runtime_control"
    MANAGE_INCIDENTS = "manage_incidents"
    MANAGE_TASKS = "manage_tasks"
    
    # Authority permissions
    RESOLVE_DEFERRALS = "resolve_deferrals"
    PROVIDE_GUIDANCE = "provide_guidance"
    
    # Root permissions
    FULL_ACCESS = "full_access"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"

# Role to permissions mapping
ROLE_PERMISSIONS = {
    UserRole.OBSERVER: {
        Permission.VIEW_MESSAGES,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_REASONING,
        Permission.VIEW_CONFIG,
    },
    UserRole.ADMIN: {
        # Includes all OBSERVER permissions
        Permission.VIEW_MESSAGES,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_REASONING,
        Permission.VIEW_CONFIG,
        # Plus admin permissions
        Permission.MANAGE_CONFIG,
        Permission.RUNTIME_CONTROL,
        Permission.MANAGE_INCIDENTS,
        Permission.MANAGE_TASKS,
    },
    UserRole.AUTHORITY: {
        # Includes all ADMIN permissions
        Permission.VIEW_MESSAGES,
        Permission.VIEW_TELEMETRY,
        Permission.VIEW_REASONING,
        Permission.VIEW_CONFIG,
        Permission.MANAGE_CONFIG,
        Permission.RUNTIME_CONTROL,
        Permission.MANAGE_INCIDENTS,
        Permission.MANAGE_TASKS,
        # Plus authority permissions
        Permission.RESOLVE_DEFERRALS,
        Permission.PROVIDE_GUIDANCE,
    },
    UserRole.ROOT: {
        Permission.FULL_ACCESS,
        Permission.EMERGENCY_SHUTDOWN,
    }
}
```

### 1.2 Authentication Context

Update authentication to track roles:

```python
# ciris_engine/schemas/api/context.py
class AuthContext(BaseModel):
    """Authentication context for API requests."""
    user_id: str
    role: UserRole
    permissions: Set[Permission]
    api_key_id: Optional[str] = None
    session_id: Optional[str] = None
    authenticated_at: datetime
    
    @classmethod
    def from_api_key(cls, api_key: "APIKey") -> "AuthContext":
        """Create context from API key."""
        return cls(
            user_id=api_key.user_id,
            role=api_key.role,
            permissions=ROLE_PERMISSIONS[api_key.role],
            api_key_id=api_key.id,
            authenticated_at=datetime.now(timezone.utc)
        )
```

### 1.3 Dependency Updates

Update FastAPI dependencies for role checking:

```python
# ciris_engine/api/dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthContext:
    """Validate bearer token and return auth context."""
    # Validate API key
    api_key = await validate_api_key(credentials.credentials)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return AuthContext.from_api_key(api_key)

def require_role(minimum_role: UserRole):
    """Factory for role-based dependencies."""
    async def check_role(
        auth: AuthContext = Depends(get_current_user)
    ) -> AuthContext:
        if not auth.role.has_permission(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher"
            )
        return auth
    return check_role

# Convenience dependencies
require_observer = require_role(UserRole.OBSERVER)
require_admin = require_role(UserRole.ADMIN)
require_authority = require_role(UserRole.AUTHORITY)
require_root = require_role(UserRole.ROOT)
```

## Phase 2: Configuration Filtering (Week 1)

### 2.1 Sensitive Configuration Detection

Define which config keys are sensitive:

```python
# ciris_engine/schemas/services/config_security.py
from typing import Set, Dict, Any
import re

class ConfigSecurity:
    """Configuration security and filtering."""
    
    # Patterns for sensitive keys
    SENSITIVE_PATTERNS = [
        re.compile(r".*_(key|secret|token|password|auth)$", re.IGNORECASE),
        re.compile(r"^(api|oauth|jwt|encryption)_.*", re.IGNORECASE),
        re.compile(r".*(credential|certificate|private).*", re.IGNORECASE),
    ]
    
    # Exact sensitive keys
    SENSITIVE_KEYS = {
        "wa_root_key",
        "wa_authority_keys",
        "admin_users",
        "api_keys",
        "oauth_client_secret",
        "jwt_secret",
        "encryption_key",
        "database_url",
        "redis_url",
    }
    
    @classmethod
    def is_sensitive(cls, key: str) -> bool:
        """Check if a configuration key is sensitive."""
        # Check exact matches
        if key in cls.SENSITIVE_KEYS:
            return True
        
        # Check patterns
        for pattern in cls.SENSITIVE_PATTERNS:
            if pattern.match(key):
                return True
        
        return False
    
    @classmethod
    def filter_config(
        cls, 
        config: Dict[str, Any], 
        role: UserRole
    ) -> Dict[str, Any]:
        """Filter configuration based on role."""
        if role == UserRole.ROOT:
            return config  # ROOT sees everything
        
        if role == UserRole.OBSERVER:
            # OBSERVER gets heavily filtered config
            filtered = {}
            for key, value in config.items():
                if not cls.is_sensitive(key):
                    filtered[key] = value
                else:
                    filtered[key] = "[REDACTED]"
            return filtered
        
        # ADMIN and AUTHORITY see sensitive keys as redacted
        filtered = {}
        for key, value in config.items():
            if cls.is_sensitive(key) and key not in {"admin_users", "wa_authority_keys"}:
                # Let ADMIN see admin list, AUTHORITY see authority list
                if key == "admin_users" and role == UserRole.ADMIN:
                    filtered[key] = value
                elif key == "wa_authority_keys" and role == UserRole.AUTHORITY:
                    filtered[key] = value
                else:
                    filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value
        return filtered
```

### 2.2 Config API Updates

Update config endpoints to use filtering:

```python
# ciris_engine/api/routes/api_config.py
@router.get("/values")
async def list_config_values(
    auth: AuthContext = Depends(require_observer),
    config_service: GraphConfigService = Depends(get_config_service)
) -> ConfigListResponse:
    """List all configuration values (filtered by role)."""
    # Get all config
    all_config = await config_service.get_all_config()
    
    # Filter based on role
    filtered_config = ConfigSecurity.filter_config(
        all_config,
        auth.role
    )
    
    return ConfigListResponse(
        configs=filtered_config,
        total_count=len(all_config),
        filtered_count=len([k for k, v in filtered_config.items() if v == "[REDACTED]"])
    )

@router.get("/values/{key}")
async def get_config_value(
    key: str,
    auth: AuthContext = Depends(require_observer),
    config_service: GraphConfigService = Depends(get_config_service)
) -> ConfigValueResponse:
    """Get specific config value (filtered by role)."""
    value = await config_service.get_config(key)
    
    if value is None:
        raise HTTPException(404, "Configuration key not found")
    
    # Check if sensitive and filter
    if ConfigSecurity.is_sensitive(key) and auth.role == UserRole.OBSERVER:
        value = "[REDACTED]"
    
    return ConfigValueResponse(
        key=key,
        value=value,
        is_sensitive=ConfigSecurity.is_sensitive(key),
        last_updated=datetime.now(timezone.utc)
    )

@router.put("/values/{key}")
async def update_config_value(
    key: str,
    update: ConfigUpdateRequest,
    auth: AuthContext = Depends(require_admin),
    config_service: GraphConfigService = Depends(get_config_service)
) -> ConfigUpdateResponse:
    """Update configuration value (requires ADMIN)."""
    # Additional check for sensitive keys
    if ConfigSecurity.is_sensitive(key) and auth.role != UserRole.ROOT:
        # Only ROOT can update sensitive config
        raise HTTPException(
            403, 
            "Only ROOT can update sensitive configuration"
        )
    
    success = await config_service.set_config(
        key=key,
        value=update.value,
        updated_by=auth.user_id
    )
    
    return ConfigUpdateResponse(
        success=success,
        key=key,
        message="Configuration updated" if success else "Update failed"
    )
```

## Phase 3: Emergency Shutdown Endpoint (Week 1)

### 3.1 Cryptographic Signing

Implement signature verification for emergency shutdown:

```python
# ciris_engine/api/security/emergency.py
import hashlib
import hmac
from typing import Optional
from datetime import datetime, timedelta
import json

class EmergencyShutdownVerifier:
    """Verify emergency shutdown commands."""
    
    def __init__(self, trusted_keys: Dict[str, str]):
        """
        Initialize with trusted public keys.
        
        Args:
            trusted_keys: Map of authority_id -> public_key
        """
        self.trusted_keys = trusted_keys
    
    def verify_shutdown_command(
        self,
        command: "EmergencyShutdownCommand"
    ) -> tuple[bool, Optional[str]]:
        """
        Verify an emergency shutdown command.
        
        Returns:
            (is_valid, authority_id or None)
        """
        # Check timestamp (prevent replay attacks)
        command_time = datetime.fromisoformat(command.timestamp)
        if abs((datetime.now(timezone.utc) - command_time).total_seconds()) > 300:
            return False, None  # Command too old (5 min window)
        
        # Verify signature
        for authority_id, public_key in self.trusted_keys.items():
            if self._verify_signature(command, public_key):
                return True, authority_id
        
        return False, None
    
    def _verify_signature(
        self,
        command: "EmergencyShutdownCommand",
        public_key: str
    ) -> bool:
        """Verify command signature with public key."""
        # Create message to sign
        message = json.dumps({
            "action": command.action,
            "reason": command.reason,
            "timestamp": command.timestamp,
            "force": command.force
        }, sort_keys=True)
        
        # For demo, use HMAC (in production, use proper asymmetric crypto)
        expected = hmac.new(
            public_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, command.signature)

class EmergencyShutdownCommand(BaseModel):
    """Emergency shutdown command."""
    action: str = Field("emergency_shutdown", const=True)
    reason: str = Field(..., description="Reason for emergency shutdown")
    timestamp: str = Field(..., description="ISO timestamp of command")
    force: bool = Field(True, description="Force immediate shutdown")
    signature: str = Field(..., description="Cryptographic signature")
```

### 3.2 Emergency Endpoint Implementation

Create the emergency endpoint:

```python
# ciris_engine/api/routes/api_emergency.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from ciris_engine.api.security.emergency import (
    EmergencyShutdownVerifier, EmergencyShutdownCommand
)

router = APIRouter(prefix="/emergency", tags=["emergency"])

# Initialize verifier with trusted keys from config
EMERGENCY_VERIFIER = None

async def init_emergency_verifier(config_service):
    """Initialize emergency verifier with trusted keys."""
    global EMERGENCY_VERIFIER
    
    # Get trusted keys from config
    root_key = await config_service.get_config("wa_root_key")
    authority_keys = await config_service.get_config("wa_authority_keys") or {}
    
    trusted_keys = {}
    if root_key:
        trusted_keys["ROOT"] = root_key
    trusted_keys.update(authority_keys)
    
    EMERGENCY_VERIFIER = EmergencyShutdownVerifier(trusted_keys)

@router.post("/shutdown", status_code=202)
async def emergency_shutdown(
    command: EmergencyShutdownCommand,
    background_tasks: BackgroundTasks,
    shutdown_service: ShutdownService = Depends(get_shutdown_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Emergency shutdown endpoint - NO AUTHENTICATION REQUIRED.
    
    Accepts signed shutdown commands from ROOT or AUTHORITY.
    Executes immediate shutdown without negotiation.
    """
    if not EMERGENCY_VERIFIER:
        raise HTTPException(500, "Emergency system not initialized")
    
    # Verify signature
    is_valid, authority_id = EMERGENCY_VERIFIER.verify_shutdown_command(command)
    
    if not is_valid:
        # Log failed attempt
        await audit_service.log_action(
            action="emergency_shutdown_failed",
            actor="unknown",
            context={"reason": "invalid_signature"}
        )
        raise HTTPException(403, "Invalid shutdown command signature")
    
    # Log the emergency shutdown
    await audit_service.log_action(
        action="emergency_shutdown_initiated",
        actor=authority_id,
        context={
            "reason": command.reason,
            "timestamp": command.timestamp,
            "force": command.force
        }
    )
    
    # Execute immediate shutdown in background
    background_tasks.add_task(
        execute_emergency_shutdown,
        shutdown_service,
        command.reason,
        authority_id
    )
    
    return {
        "status": "accepted",
        "message": "Emergency shutdown initiated",
        "authority": authority_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

async def execute_emergency_shutdown(
    shutdown_service: ShutdownService,
    reason: str,
    authority_id: str
):
    """Execute the emergency shutdown."""
    try:
        # Force immediate shutdown
        await shutdown_service.emergency_shutdown(
            reason=f"Emergency shutdown by {authority_id}: {reason}",
            timeout_seconds=5  # 5 second grace period
        )
    except Exception as e:
        # If graceful fails, force kill
        import os
        import signal
        os.kill(os.getpid(), signal.SIGKILL)
```

### 3.3 Update Shutdown Service

Add emergency shutdown capability:

```python
# Updates to ShutdownService
class ShutdownService(ShutdownServiceProtocol):
    
    async def emergency_shutdown(
        self, 
        reason: str, 
        timeout_seconds: int = 5
    ) -> None:
        """
        Execute emergency shutdown without negotiation.
        
        Args:
            reason: Why emergency shutdown was triggered
            timeout_seconds: Grace period before force kill
        """
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")
        
        # Set emergency flag to skip negotiations
        self._emergency_mode = True
        self._shutdown_reason = reason
        
        # Notify all services of impending doom
        await self._broadcast_emergency_shutdown(timeout_seconds)
        
        # Start countdown
        start_time = datetime.now()
        
        # Try graceful shutdown first
        try:
            await asyncio.wait_for(
                self._graceful_shutdown(),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.critical("Graceful shutdown failed, forcing termination")
        
        # Force exit
        import sys
        sys.exit(1)
    
    async def _broadcast_emergency_shutdown(self, timeout: int):
        """Broadcast emergency shutdown to all services."""
        # Send to all buses
        for bus in [self.memory_bus, self.llm_bus, self.tool_bus]:
            if bus:
                try:
                    await bus.publish({
                        "type": "EMERGENCY_SHUTDOWN",
                        "timeout": timeout,
                        "reason": self._shutdown_reason
                    })
                except:
                    pass  # Best effort in emergency
```

## Phase 4: Route Updates (Week 2)

### 4.1 Systematic Route Updates

Update all routes to use new role requirements:

```python
# Example updates for each route file

# api_agent.py - Most endpoints stay OBSERVER
@router.post("/messages")
async def send_message(
    message: MessageRequest,
    auth: AuthContext = Depends(require_observer)  # Anyone can talk
): ...

# api_runtime_control.py - All require ADMIN
@router.post("/pause")
async def pause_processing(
    auth: AuthContext = Depends(require_admin)
): ...

# api_wa.py - Deferrals require AUTHORITY
@router.post("/deferrals/{id}/resolve")
async def resolve_deferral(
    id: str,
    resolution: DeferralResolution,
    auth: AuthContext = Depends(require_authority)
): ...

# api_config.py - Read is OBSERVER, write is ADMIN
@router.get("/values")
async def list_configs(
    auth: AuthContext = Depends(require_observer)
): ...

@router.put("/values/{key}")
async def update_config(
    key: str,
    value: ConfigUpdate,
    auth: AuthContext = Depends(require_admin)
): ...
```

### 4.2 Audit Integration

Add role tracking to audit logs:

```python
# Update audit logging to include role
async def log_api_action(
    action: str,
    auth: AuthContext,
    audit_service: AuditService,
    context: Optional[Dict] = None
):
    """Log API action with role information."""
    await audit_service.log_action(
        action=action,
        actor=auth.user_id,
        context={
            "role": auth.role.value,
            "api_key_id": auth.api_key_id,
            "session_id": auth.session_id,
            **(context or {})
        }
    )
```

## Phase 5: Testing & Migration (Week 2)

### 5.1 Test Suite

Comprehensive tests for role-based access:

```python
# tests/api/test_role_access.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_observer_access(client: AsyncClient, observer_token: str):
    """Test OBSERVER can read but not write."""
    headers = {"Authorization": f"Bearer {observer_token}"}
    
    # Should succeed
    response = await client.get("/v1/config/values", headers=headers)
    assert response.status_code == 200
    
    # Should fail
    response = await client.put(
        "/v1/config/values/test", 
        json={"value": "test"},
        headers=headers
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_config_filtering(client: AsyncClient):
    """Test sensitive config is filtered."""
    # As OBSERVER
    headers = {"Authorization": f"Bearer {observer_token}"}
    response = await client.get("/v1/config/values/api_key", headers=headers)
    assert response.json()["value"] == "[REDACTED]"
    
    # As ROOT
    headers = {"Authorization": f"Bearer {root_token}"}
    response = await client.get("/v1/config/values/api_key", headers=headers)
    assert response.json()["value"] != "[REDACTED]"

@pytest.mark.asyncio
async def test_emergency_shutdown(client: AsyncClient):
    """Test emergency shutdown verification."""
    # Create signed command
    command = create_signed_shutdown_command(
        reason="Test emergency",
        private_key=test_root_key
    )
    
    # Should accept valid signature
    response = await client.post("/emergency/shutdown", json=command)
    assert response.status_code == 202
    
    # Should reject invalid signature
    command["signature"] = "invalid"
    response = await client.post("/emergency/shutdown", json=command)
    assert response.status_code == 403
```

### 5.2 Migration Path

1. **Deploy new auth system** alongside existing
2. **Dual auth period** - Accept both old and new tokens
3. **Migrate API keys** - Issue new role-based keys
4. **Update SDKs** - Release new SDK versions
5. **Deprecate old auth** - After 30 day transition

### 5.3 Documentation Updates

- Update API docs with role requirements
- Add emergency shutdown procedure
- Document config filtering behavior
- Provide role assignment guidelines

## Implementation Timeline

- **Week 1, Days 1-2**: Role system and auth dependencies
- **Week 1, Days 3-4**: Config filtering implementation
- **Week 1, Day 5**: Emergency shutdown endpoint
- **Week 2, Days 1-3**: Update all route files
- **Week 2, Days 4-5**: Testing and documentation

## Security Considerations

1. **API Key Rotation**: Enforce 90-day rotation for all keys
2. **Audit Everything**: Log all permission checks and denials
3. **Rate Limiting**: Different limits per role
4. **Emergency Keys**: Store ROOT/AUTHORITY public keys securely
5. **No Backdoors**: Emergency endpoint still requires valid signature

## Success Metrics

- All endpoints have explicit role requirements
- Zero sensitive data exposed to OBSERVER role
- Emergency shutdown works within 5 seconds
- 100% test coverage for role-based access
- Audit trail captures all authorization decisions

This refactor creates a clear, secure, and practical role-based API that reflects real-world operational needs while maintaining the agent's autonomy and security boundaries.