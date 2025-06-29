"""
Authentication dependencies for FastAPI routes.

Provides role-based access control through dependency injection.
"""
from fastapi import Depends, HTTPException, status, Request, WebSocket, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import hashlib
from datetime import datetime, timezone

from ciris_engine.schemas.api.auth import AuthContext, UserRole, APIKey, ROLE_PERMISSIONS
from ciris_engine.logic.services.graph.config import GraphConfigService

# Bearer token security scheme
security = HTTPBearer(auto_error=False)

async def get_config_service(request: Request) -> GraphConfigService:
    """Get config service from app state."""
    if not hasattr(request.app.state, 'config_service'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Config service not initialized"
        )
    return request.app.state.config_service

async def validate_api_key(
    key: str,
    config_service: GraphConfigService
) -> Optional[APIKey]:
    """
    Validate API key against stored keys.

    Args:
        key: Raw API key
        config_service: Config service for key lookup

    Returns:
        APIKey if valid, None otherwise
    """
    try:
        # Get API keys from config
        api_keys_config = await config_service.get_config("api_keys") or {}

        # Hash the provided key
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Find matching key
        for key_id, key_data in api_keys_config.items():
            if not isinstance(key_data, dict):
                continue

            if key_data.get("key_hash") == key_hash:
                # Check if key is active
                if not key_data.get("is_active", True):
                    return None

                # Check expiration
                expires_at = key_data.get("expires_at")
                if expires_at:
                    exp_time = datetime.fromisoformat(expires_at)
                    if exp_time < datetime.now(timezone.utc):
                        return None

                # Create APIKey object
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

    except Exception as e:
        # Log error but don't expose details
        import logging
        logging.error(f"Error validating API key: {e}")
        return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    config_service: GraphConfigService = Depends(get_config_service)
) -> Optional[AuthContext]:
    """
    Get current user from bearer token.

    Returns None if no credentials provided (allows optional auth).
    """
    if not credentials:
        return None

    # Validate API key
    api_key = await validate_api_key(credentials.credentials, config_service)
    if not api_key:
        return None

    # Update last used timestamp
    try:
        await config_service.set_config(
            f"api_keys.{api_key.id}.last_used",
            datetime.now(timezone.utc).isoformat(),
            updated_by="auth_system"
        )
    except Exception as e:
        # Don't fail auth if update fails
        import logging
        logging.warning(f"Failed to update API key last_used timestamp: {e}")

    # Create auth context
    return AuthContext(
        user_id=api_key.user_id,
        role=api_key.role,
        permissions=ROLE_PERMISSIONS.get(api_key.role, set()),
        api_key_id=api_key.id,
        authenticated_at=datetime.now(timezone.utc)
    )

def require_role(minimum_role: UserRole):
    """
    Factory for role-based access control dependencies.

    Args:
        minimum_role: Minimum role required for access

    Returns:
        Dependency function that validates role
    """
    async def check_role(
        auth: Optional[AuthContext] = Depends(get_current_user)
    ) -> AuthContext:
        """Validate user has required role."""
        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if not auth.role.has_permission(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires {minimum_role.value} role or higher."
            )

        return auth

    # Set function name for better error messages
    check_role.__name__ = f"require_{minimum_role.value.lower()}"
    return check_role

# Convenience dependencies for common roles
require_observer = require_role(UserRole.OBSERVER)
require_admin = require_role(UserRole.ADMIN)
require_authority = require_role(UserRole.AUTHORITY)
require_root = require_role(UserRole.ROOT)

# Optional auth (returns None if not authenticated)
optional_auth = get_current_user

async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
) -> Optional[AuthContext]:
    """
    Get current user for WebSocket connections.

    WebSockets can't use Authorization header, so we use query parameter.
    """
    if not token:
        return None

    # Get config service from app state
    config_service = websocket.app.state.config_service

    # Validate API key
    api_key = await validate_api_key(token, config_service)
    if not api_key:
        await websocket.close(code=1008, reason="Invalid authentication")
        return None

    # Create auth context
    return AuthContext(
        user_id=api_key.user_id,
        role=api_key.role,
        permissions=ROLE_PERMISSIONS.get(api_key.role, set()),
        api_key_id=api_key.id,
        authenticated_at=datetime.now(timezone.utc)
    )

def require_role_ws(minimum_role: UserRole):
    """
    Factory for WebSocket role-based access control.

    Args:
        minimum_role: Minimum role required

    Returns:
        Dependency function for WebSocket auth
    """
    async def check_role_ws(
        auth: Optional[AuthContext] = Depends(get_current_user_ws)
    ) -> AuthContext:
        """Validate WebSocket user has required role."""
        if not auth:
            # Can't raise HTTPException in WebSocket
            # Connection should already be closed by get_current_user_ws
            raise ValueError("Authentication required")

        if not auth.role.has_permission(minimum_role):
            raise ValueError(f"Requires {minimum_role.value} role")

        return auth

    return check_role_ws

# WebSocket convenience dependencies
require_observer_ws = require_role_ws(UserRole.OBSERVER)
require_admin_ws = require_role_ws(UserRole.ADMIN)
require_authority_ws = require_role_ws(UserRole.AUTHORITY)
require_root_ws = require_role_ws(UserRole.ROOT)
