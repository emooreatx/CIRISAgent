# CIRIS API v2.0 Implementation Plan

## Overview
This plan details the step-by-step implementation of the CIRIS API v2.0, transforming the existing API to match our final specification with role-based access, config security, and natural service exposure.

## Phase 1: Core Infrastructure (Days 1-2)

### 1.1 Authentication Schema
```python
# ciris_engine/schemas/api/auth.py
from enum import Enum
from typing import Set, Optional, Dict, Any
from datetime import datetime, timezone
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
    VIEW_CONFIG = "view_config"
    
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

class AuthContext(BaseModel):
    """Authentication context for API requests."""
    user_id: str
    role: UserRole
    permissions: Set[Permission]
    api_key_id: Optional[str] = None
    session_id: Optional[str] = None
    authenticated_at: datetime

class APIKey(BaseModel):
    """API key model."""
    id: str
    key_hash: str
    user_id: str
    role: UserRole
    description: str
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
```

### 1.2 Config Security Schema
```python
# ciris_engine/schemas/api/config_security.py
import re
from typing import Set, Dict, Any, List
from ..auth import UserRole

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
        "openai_api_key",
        "anthropic_api_key",
    }
    
    @classmethod
    def is_sensitive(cls, key: str) -> bool:
        """Check if a configuration key is sensitive."""
        if key in cls.SENSITIVE_KEYS:
            return True
        
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
            return config
        
        filtered = {}
        for key, value in config.items():
            if cls.is_sensitive(key):
                if role == UserRole.OBSERVER:
                    filtered[key] = "[REDACTED]"
                elif role == UserRole.ADMIN and key == "admin_users":
                    filtered[key] = value  # Admins can see admin list
                elif role == UserRole.AUTHORITY and key == "wa_authority_keys":
                    filtered[key] = value  # Authorities can see authority keys
                else:
                    filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value
        
        return filtered
```

### 1.3 Emergency Shutdown Schema
```python
# ciris_engine/schemas/api/emergency.py
from pydantic import BaseModel, Field
from datetime import datetime

class EmergencyShutdownCommand(BaseModel):
    """Emergency shutdown command."""
    action: str = Field("emergency_shutdown", const=True)
    reason: str = Field(..., description="Reason for emergency shutdown")
    timestamp: str = Field(..., description="ISO timestamp of command")
    force: bool = Field(True, description="Force immediate shutdown")
    signature: str = Field(..., description="Cryptographic signature")

class EmergencyShutdownResponse(BaseModel):
    """Response to emergency shutdown."""
    status: str = Field("accepted", description="Command status")
    message: str = Field(..., description="Status message")
    authority: str = Field(..., description="Who issued the command")
    timestamp: datetime = Field(..., description="When command was received")
```

### 1.4 Auth Dependencies
```python
# ciris_engine/api/dependencies/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import hashlib
import hmac

from ciris_engine.schemas.api.auth import AuthContext, UserRole, APIKey
from ciris_engine.logic.services.graph.config import GraphConfigService

security = HTTPBearer(auto_error=False)

async def get_config_service(request: Request) -> GraphConfigService:
    """Get config service from app state."""
    return request.app.state.config_service

async def validate_api_key(
    key: str,
    config_service: GraphConfigService
) -> Optional[APIKey]:
    """Validate API key against stored keys."""
    # Get API keys from config
    api_keys_config = await config_service.get_config("api_keys") or {}
    
    # Hash the provided key
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    
    # Find matching key
    for key_id, key_data in api_keys_config.items():
        if isinstance(key_data, dict) and key_data.get("key_hash") == key_hash:
            # Check if key is active and not expired
            if not key_data.get("is_active", True):
                return None
                
            expires_at = key_data.get("expires_at")
            if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                return None
            
            return APIKey(
                id=key_id,
                key_hash=key_hash,
                user_id=key_data["user_id"],
                role=UserRole(key_data["role"]),
                description=key_data.get("description", ""),
                created_at=datetime.fromisoformat(key_data["created_at"]),
                last_used=datetime.fromisoformat(key_data["last_used"]) if key_data.get("last_used") else None,
                expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
                is_active=key_data.get("is_active", True)
            )
    
    return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    config_service: GraphConfigService = Depends(get_config_service)
) -> Optional[AuthContext]:
    """Get current user from bearer token."""
    if not credentials:
        return None
        
    api_key = await validate_api_key(credentials.credentials, config_service)
    if not api_key:
        return None
    
    # Update last used
    await config_service.set_config(
        f"api_keys.{api_key.id}.last_used",
        datetime.now(timezone.utc).isoformat(),
        updated_by="auth_system"
    )
    
    return AuthContext.from_api_key(api_key)

def require_role(minimum_role: UserRole):
    """Factory for role-based dependencies."""
    async def check_role(
        auth: Optional[AuthContext] = Depends(get_current_user)
    ) -> AuthContext:
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
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

## Phase 2: Route Refactoring (Days 3-5)

### 2.1 Config Route Updates
```python
# ciris_engine/api/routes/api_config.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from ciris_engine.schemas.api.auth import AuthContext, UserRole
from ciris_engine.schemas.api.config_security import ConfigSecurity
from ciris_engine.api.dependencies.auth import require_observer, require_admin, require_root
from ciris_engine.logic.services.graph.config import GraphConfigService

router = APIRouter(prefix="/v1/config", tags=["config"])

@router.get("/values")
async def list_config_values(
    auth: AuthContext = Depends(require_observer),
    config_service: GraphConfigService = Depends(get_config_service)
) -> Dict[str, Any]:
    """List all configuration values (filtered by role)."""
    # Get all config
    all_config = await config_service.get_all_config()
    
    # Filter based on role
    filtered_config = ConfigSecurity.filter_config(all_config, auth.role)
    
    # Add metadata
    redacted_count = sum(1 for v in filtered_config.values() if v == "[REDACTED]")
    
    return {
        "data": filtered_config,
        "metadata": {
            "total_keys": len(all_config),
            "visible_keys": len(filtered_config) - redacted_count,
            "redacted_keys": redacted_count,
            "role": auth.role.value
        }
    }

@router.get("/values/{key}")
async def get_config_value(
    key: str,
    auth: AuthContext = Depends(require_observer),
    config_service: GraphConfigService = Depends(get_config_service)
) -> Dict[str, Any]:
    """Get specific config value (filtered by role)."""
    value = await config_service.get_config(key)
    
    if value is None:
        raise HTTPException(404, f"Configuration key '{key}' not found")
    
    # Check if sensitive and filter
    is_sensitive = ConfigSecurity.is_sensitive(key)
    if is_sensitive and auth.role != UserRole.ROOT:
        # Special cases for ADMIN and AUTHORITY
        if not (auth.role == UserRole.ADMIN and key == "admin_users") and \
           not (auth.role == UserRole.AUTHORITY and key == "wa_authority_keys"):
            value = "[REDACTED]"
    
    return {
        "data": {
            "key": key,
            "value": value,
            "is_sensitive": is_sensitive
        }
    }

@router.put("/values/{key}")
async def update_config_value(
    key: str,
    value: Any,
    auth: AuthContext = Depends(require_admin),
    config_service: GraphConfigService = Depends(get_config_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> Dict[str, Any]:
    """Update configuration value (requires ADMIN, ROOT for sensitive)."""
    # Check if sensitive
    if ConfigSecurity.is_sensitive(key) and auth.role != UserRole.ROOT:
        raise HTTPException(
            403, 
            "Only ROOT can update sensitive configuration"
        )
    
    # Update config
    success = await config_service.set_config(
        key=key,
        value=value,
        updated_by=auth.user_id
    )
    
    # Audit log
    await audit_service.log_action(
        action="config_update",
        actor=auth.user_id,
        context={
            "key": key,
            "is_sensitive": ConfigSecurity.is_sensitive(key),
            "role": auth.role.value
        }
    )
    
    return {
        "data": {
            "success": success,
            "key": key,
            "message": "Configuration updated" if success else "Update failed"
        }
    }
```

### 2.2 Emergency Shutdown Route
```python
# ciris_engine/api/routes/api_emergency.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from ciris_engine.schemas.api.emergency import EmergencyShutdownCommand, EmergencyShutdownResponse
from ciris_engine.logic.services.lifecycle.shutdown import ShutdownService

router = APIRouter(prefix="/emergency", tags=["emergency"])

class EmergencyShutdownVerifier:
    """Verify emergency shutdown commands."""
    
    def __init__(self, trusted_keys: Dict[str, str]):
        self.trusted_keys = trusted_keys
    
    def verify_command(
        self,
        command: EmergencyShutdownCommand
    ) -> tuple[bool, Optional[str]]:
        """Verify command signature and timestamp."""
        # Check timestamp (5 minute window)
        try:
            cmd_time = datetime.fromisoformat(command.timestamp)
            if abs((datetime.now(timezone.utc) - cmd_time).total_seconds()) > 300:
                return False, None
        except:
            return False, None
        
        # Verify signature
        message = json.dumps({
            "action": command.action,
            "reason": command.reason,
            "timestamp": command.timestamp,
            "force": command.force
        }, sort_keys=True)
        
        for authority_id, public_key in self.trusted_keys.items():
            expected = hmac.new(
                public_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(expected, command.signature):
                return True, authority_id
        
        return False, None

@router.post("/shutdown", response_model=EmergencyShutdownResponse)
async def emergency_shutdown(
    command: EmergencyShutdownCommand,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Emergency shutdown endpoint - NO AUTHENTICATION REQUIRED.
    
    Accepts signed shutdown commands from ROOT or AUTHORITY.
    Executes immediate shutdown without negotiation.
    """
    # Get verifier from app state
    verifier: EmergencyShutdownVerifier = request.app.state.emergency_verifier
    audit_service = request.app.state.audit_service
    shutdown_service = request.app.state.shutdown_service
    
    # Verify signature
    is_valid, authority_id = verifier.verify_command(command)
    
    if not is_valid:
        # Log failed attempt
        await audit_service.log_action(
            action="emergency_shutdown_failed",
            actor="unknown",
            context={"reason": "invalid_signature", "timestamp": command.timestamp}
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
    
    # Execute shutdown in background
    async def execute_shutdown():
        try:
            await shutdown_service.emergency_shutdown(
                reason=f"Emergency shutdown by {authority_id}: {command.reason}",
                timeout_seconds=5
            )
        except Exception as e:
            # Force kill if graceful fails
            import os
            import signal
            os.kill(os.getpid(), signal.SIGKILL)
    
    background_tasks.add_task(execute_shutdown)
    
    return EmergencyShutdownResponse(
        status="accepted",
        message="Emergency shutdown initiated",
        authority=authority_id,
        timestamp=datetime.now(timezone.utc)
    )
```

### 2.3 Self-Configuration Route Updates
```python
# ciris_engine/api/routes/api_adaptation.py
from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from ciris_engine.schemas.api.auth import AuthContext
from ciris_engine.api.dependencies.auth import require_observer
from ciris_engine.logic.infrastructure.sub_services.configuration_feedback_loop import ConfigurationFeedbackLoop

router = APIRouter(prefix="/v1/adaptation", tags=["adaptation"])

@router.get("/patterns")
async def get_detected_patterns(
    pattern_type: Optional[str] = None,
    hours: int = 24,
    auth: AuthContext = Depends(require_observer),
    feedback_loop: ConfigurationFeedbackLoop = Depends(get_feedback_loop)
) -> Dict[str, Any]:
    """Get detected behavioral patterns."""
    patterns = await feedback_loop.get_detected_patterns(
        pattern_type=pattern_type,
        hours=hours
    )
    
    return {
        "data": {
            "patterns": [p.model_dump() for p in patterns],
            "count": len(patterns),
            "analysis_window_hours": hours
        }
    }

@router.get("/insights")
async def get_pattern_insights(
    limit: int = 50,
    auth: AuthContext = Depends(require_observer),
    feedback_loop: ConfigurationFeedbackLoop = Depends(get_feedback_loop)
) -> Dict[str, Any]:
    """Get pattern-based insights stored in memory."""
    insights = await feedback_loop.get_pattern_insights(limit=limit)
    
    return {
        "data": {
            "insights": insights,
            "count": len(insights)
        }
    }

@router.get("/effectiveness")
async def get_pattern_effectiveness(
    pattern_id: Optional[str] = None,
    auth: AuthContext = Depends(require_observer),
    feedback_loop: ConfigurationFeedbackLoop = Depends(get_feedback_loop)
) -> Dict[str, Any]:
    """Get effectiveness metrics for patterns."""
    if pattern_id:
        effectiveness = await feedback_loop.get_pattern_effectiveness(pattern_id)
        return {
            "data": {
                "pattern_id": pattern_id,
                "effectiveness": effectiveness
            }
        }
    else:
        # Get summary of all pattern effectiveness
        summary = await feedback_loop.get_learning_summary()
        return {
            "data": summary
        }
```

### 2.4 Tool Discovery Updates (No Execution)
```python
# ciris_engine/api/routes/api_tools.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ciris_engine.schemas.api.auth import AuthContext
from ciris_engine.api.dependencies.auth import require_observer

router = APIRouter(prefix="/v1/tools", tags=["tools"])

@router.get("/")
async def list_tools(
    auth: AuthContext = Depends(require_observer),
    tool_services: List[ToolService] = Depends(get_tool_services)
) -> Dict[str, Any]:
    """List all available tools."""
    all_tools = []
    
    for service in tool_services:
        tools = await service.get_available_tools()
        for tool_name in tools:
            info = await service.get_tool_info(tool_name)
            if info:
                all_tools.append({
                    "name": tool_name,
                    "adapter": service.adapter_name,
                    "category": info.category,
                    "description": info.description
                })
    
    return {
        "data": {
            "tools": all_tools,
            "count": len(all_tools),
            "note": "Tools are executed by the agent during reasoning, not via API"
        }
    }

@router.get("/{tool_name}")
async def get_tool_details(
    tool_name: str,
    auth: AuthContext = Depends(require_observer),
    tool_services: List[ToolService] = Depends(get_tool_services)
) -> Dict[str, Any]:
    """Get detailed information about a specific tool."""
    for service in tool_services:
        info = await service.get_tool_info(tool_name)
        if info:
            return {
                "data": {
                    "tool": info.model_dump(),
                    "adapter": service.adapter_name,
                    "note": "Execute by sending a message to the agent requesting this tool"
                }
            }
    
    raise HTTPException(404, f"Tool '{tool_name}' not found")

# NO EXECUTION ENDPOINT - Tools are agent-controlled
```

## Phase 3: WebSocket Support (Days 6-7)

### 3.1 WebSocket Manager
```python
# ciris_engine/api/websocket/manager.py
from typing import Dict, Set, Optional
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        # Track connections by type and auth
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "messages": set(),
            "telemetry": set(),
            "reasoning": set(),
            "logs": set(),
            "all": set()
        }
        self.auth_info: Dict[WebSocket, AuthContext] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        stream_type: str,
        auth: AuthContext
    ):
        """Accept new connection."""
        await websocket.accept()
        self.active_connections[stream_type].add(websocket)
        self.auth_info[websocket] = auth
    
    def disconnect(self, websocket: WebSocket, stream_type: str):
        """Remove connection."""
        self.active_connections[stream_type].discard(websocket)
        self.auth_info.pop(websocket, None)
    
    async def broadcast(
        self, 
        message: dict, 
        stream_type: str,
        min_role: Optional[UserRole] = None
    ):
        """Broadcast to all connections of a type."""
        dead_connections = set()
        
        for connection in self.active_connections[stream_type]:
            # Check role if required
            if min_role:
                auth = self.auth_info.get(connection)
                if not auth or not auth.role.has_permission(min_role):
                    continue
            
            try:
                await connection.send_json(message)
            except:
                dead_connections.add(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn, stream_type)
```

### 3.2 WebSocket Routes
```python
# ciris_engine/api/routes/api_websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio

from ciris_engine.api.websocket.manager import ConnectionManager
from ciris_engine.api.dependencies.auth import get_current_user_ws

router = APIRouter(prefix="/v1/stream", tags=["websocket"])
manager = ConnectionManager()

@router.websocket("/reasoning")
async def stream_reasoning(
    websocket: WebSocket,
    auth: AuthContext = Depends(get_current_user_ws)
):
    """Stream real-time reasoning traces."""
    await manager.connect(websocket, "reasoning", auth)
    
    try:
        # Subscribe to reasoning events
        async with reasoning_bus.subscribe() as subscriber:
            while True:
                event = await subscriber.get()
                
                # Filter sensitive data based on role
                if auth.role == UserRole.OBSERVER:
                    event = filter_reasoning_event(event)
                
                await websocket.send_json({
                    "type": "reasoning",
                    "data": event,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "reasoning")
```

## Phase 4: Testing (Days 8-10)

### 4.1 Auth Tests
```python
# tests/api/test_auth.py
import pytest
from httpx import AsyncClient
from ciris_engine.schemas.api.auth import UserRole

@pytest.mark.asyncio
async def test_role_hierarchy(client: AsyncClient):
    """Test role permission hierarchy."""
    # Create tokens for each role
    tokens = {
        "observer": create_test_token(UserRole.OBSERVER),
        "admin": create_test_token(UserRole.ADMIN),
        "authority": create_test_token(UserRole.AUTHORITY),
        "root": create_test_token(UserRole.ROOT)
    }
    
    # Test observer can't access admin endpoints
    response = await client.post(
        "/v1/runtime/pause",
        headers={"Authorization": f"Bearer {tokens['observer']}"}
    )
    assert response.status_code == 403
    
    # Test admin can access runtime control
    response = await client.post(
        "/v1/runtime/pause",
        headers={"Authorization": f"Bearer {tokens['admin']}"}
    )
    assert response.status_code == 200
    
    # Test authority can resolve deferrals
    response = await client.post(
        "/v1/wa/deferrals/test-id/resolve",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {tokens['authority']}"}
    )
    assert response.status_code in [200, 404]  # 404 if no deferral exists

@pytest.mark.asyncio
async def test_config_filtering(client: AsyncClient):
    """Test sensitive config filtering."""
    # Set up test config
    await setup_test_config({
        "normal_key": "visible",
        "api_key": "secret123",
        "admin_users": ["admin1", "admin2"]
    })
    
    # Observer sees redacted
    response = await client.get(
        "/v1/config/values",
        headers={"Authorization": f"Bearer {observer_token}"}
    )
    data = response.json()["data"]
    assert data["normal_key"] == "visible"
    assert data["api_key"] == "[REDACTED]"
    assert data["admin_users"] == "[REDACTED]"
    
    # Admin sees admin list
    response = await client.get(
        "/v1/config/values",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    data = response.json()["data"]
    assert data["admin_users"] == ["admin1", "admin2"]
    assert data["api_key"] == "[REDACTED]"
    
    # Root sees everything
    response = await client.get(
        "/v1/config/values",
        headers={"Authorization": f"Bearer {root_token}"}
    )
    data = response.json()["data"]
    assert data["api_key"] == "secret123"

@pytest.mark.asyncio
async def test_emergency_shutdown(client: AsyncClient):
    """Test emergency shutdown with signature."""
    # Create valid signed command
    command = create_signed_shutdown_command(
        reason="Test emergency",
        private_key=test_authority_key
    )
    
    # Should accept valid signature
    response = await client.post("/emergency/shutdown", json=command)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    # Should reject invalid signature
    command["signature"] = "invalid"
    response = await client.post("/emergency/shutdown", json=command)
    assert response.status_code == 403
    
    # Should reject old timestamp
    command = create_signed_shutdown_command(
        reason="Test",
        private_key=test_authority_key,
        timestamp=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    )
    response = await client.post("/emergency/shutdown", json=command)
    assert response.status_code == 403
```

### 4.2 Service Endpoint Tests
```python
# tests/api/test_service_endpoints.py

@pytest.mark.asyncio
async def test_memory_service_endpoints(client: AsyncClient, auth_headers):
    """Test memory service API endpoints."""
    # Memorize
    node = create_test_node()
    response = await client.post(
        "/v1/memory/memorize",
        json={"node": node.model_dump()},
        headers=auth_headers["observer"]
    )
    assert response.status_code == 200
    node_id = response.json()["data"]["node_id"]
    
    # Recall
    response = await client.get(
        f"/v1/memory/nodes/{node_id}",
        headers=auth_headers["observer"]
    )
    assert response.status_code == 200
    assert response.json()["data"]["node"]["id"] == node_id
    
    # Search
    response = await client.post(
        "/v1/memory/search",
        json={"query": "test"},
        headers=auth_headers["observer"]
    )
    assert response.status_code == 200

@pytest.mark.asyncio  
async def test_adaptation_endpoints(client: AsyncClient, auth_headers):
    """Test self-configuration observation endpoints."""
    # Get patterns
    response = await client.get(
        "/v1/adaptation/patterns",
        headers=auth_headers["observer"]
    )
    assert response.status_code == 200
    assert "patterns" in response.json()["data"]
    
    # Get insights
    response = await client.get(
        "/v1/adaptation/insights",
        headers=auth_headers["observer"]
    )
    assert response.status_code == 200
    
    # No control endpoints should exist
    response = await client.post(
        "/v1/adaptation/approve",
        json={"changes": []},
        headers=auth_headers["admin"]
    )
    assert response.status_code == 404
```

## Phase 5: SDK Updates (Days 11-12)

### 5.1 New Client Structure
```python
# ciris_sdk/client.py
from typing import Optional
import httpx

from .auth import Auth, UserRole
from .resources import (
    MemoryResource, AgentResource, TelemetryResource,
    ConfigResource, AdaptationResource, ToolResource
)

class CIRISClient:
    """CIRIS API client with role-based access."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        role: Optional[UserRole] = None
    ):
        self.base_url = base_url
        self.auth = Auth(api_key=api_key, role=role)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=self.auth.headers,
            timeout=30.0
        )
        
        # Initialize resources
        self.memory = MemoryResource(self._http)
        self.agent = AgentResource(self._http)
        self.telemetry = TelemetryResource(self._http)
        self.config = ConfigResource(self._http, self.auth.role)
        self.adaptation = AdaptationResource(self._http)
        self.tools = ToolResource(self._http)
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http.aclose()
```

### 5.2 Config Resource with Filtering Awareness
```python
# ciris_sdk/resources/config.py
class ConfigResource:
    """Config management with role awareness."""
    
    def __init__(self, http: httpx.AsyncClient, role: UserRole):
        self._http = http
        self._role = role
    
    async def get_all(self) -> Dict[str, Any]:
        """Get all config (filtered by server based on role)."""
        response = await self._http.get("/v1/config/values")
        response.raise_for_status()
        data = response.json()["data"]
        
        # Warn about redacted values
        if self._role == UserRole.OBSERVER:
            redacted = sum(1 for v in data.values() if v == "[REDACTED]")
            if redacted > 0:
                warnings.warn(
                    f"{redacted} config values redacted. Use higher role for access.",
                    UserWarning
                )
        
        return data
    
    async def update(self, key: str, value: Any) -> bool:
        """Update config value (requires ADMIN+)."""
        if self._role < UserRole.ADMIN:
            raise PermissionError("Config updates require ADMIN role or higher")
        
        response = await self._http.put(
            f"/v1/config/values/{key}",
            json={"value": value}
        )
        
        if response.status_code == 403:
            raise PermissionError("Sensitive config requires ROOT role")
        
        response.raise_for_status()
        return response.json()["data"]["success"]
```

## Implementation Schedule

### Week 1
- **Day 1-2**: Core infrastructure (auth, config security, emergency)
- **Day 3-5**: Route refactoring for all 19 services
- **Day 6-7**: WebSocket streaming implementation

### Week 2  
- **Day 8-10**: Comprehensive testing
- **Day 11-12**: SDK updates
- **Day 13-14**: Documentation and final testing

## Success Criteria

1. ✅ All endpoints require authentication
2. ✅ Role-based access enforced consistently
3. ✅ Sensitive config filtered for non-ROOT users
4. ✅ Emergency shutdown works with valid signatures
5. ✅ No tool execution via API
6. ✅ Self-configuration is observation only
7. ✅ All responses use typed models
8. ✅ WebSocket streams work with role filtering
9. ✅ SDK supports new auth model
10. ✅ 100% test coverage for auth paths

## Risk Mitigation

1. **Breaking Changes**: Version API as v2, maintain v1 for transition
2. **Auth Complexity**: Simple role hierarchy, clear permission model
3. **Config Security**: Whitelist approach for sensitive keys
4. **Emergency Access**: Cryptographic signatures prevent abuse
5. **Performance**: Cache auth lookups, efficient role checks

This implementation plan transforms the CIRIS API into a secure, role-based system that naturally reflects the capabilities of the 19 services while maintaining the agent's autonomy.