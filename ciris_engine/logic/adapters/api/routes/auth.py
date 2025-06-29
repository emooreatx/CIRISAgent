"""
Authentication API routes for CIRIS.

Implements session management endpoints:
- POST /v1/auth/login - Authenticate user
- POST /v1/auth/logout - End session
- GET /v1/auth/me - Current user info (includes permissions)
- POST /v1/auth/refresh - Refresh token

Note: OAuth endpoints are in api_auth_v2.py
"""
import hashlib
import secrets
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Request, Depends

from ciris_engine.schemas.api.auth import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    TokenRefreshRequest,
    Permission,
    UserRole,
    ROLE_PERMISSIONS,
)
from ..dependencies.auth import (
    get_auth_context,
    get_auth_service,
    optional_auth,
)
from ciris_engine.schemas.api.auth import AuthContext
from ..services.auth_service import APIAuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    Authenticate with username/password.

    Currently supports system admin user only. In production, this would
    integrate with a proper user database.
    """
    config_service = getattr(req.app.state, 'config_service', None)

    # Default credentials for testing/development
    admin_username = "admin"
    admin_password_hash = hashlib.sha256("ciris_admin_password".encode()).hexdigest()
    
    if config_service:
        # Try to get admin credentials from config
        try:
            configured_username = await config_service.get_config("admin_username")
            configured_password_hash = await config_service.get_config("admin_password_hash")
            
            if configured_username:
                admin_username = configured_username
            if configured_password_hash:
                admin_password_hash = configured_password_hash
                
        except Exception as e:
            logger.warning(f"Using default credentials, config not available: {e}")
    else:
        logger.warning("Config service not available, using default credentials")

    # Verify credentials
    if request.username != admin_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Hash the provided password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if password_hash != admin_password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Generate API key for SYSTEM_ADMIN
    api_key = f"ciris_admin_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Store API key
    await auth_service.store_api_key(
        key=api_key,
        user_id="SYSTEM_ADMIN",
        role=UserRole.SYSTEM_ADMIN,
        expires_at=expires_at,
        description="System admin login session"
    )

    logger.info("System admin user logged in successfully")

    return LoginResponse(
        access_token=api_key,
        token_type="Bearer",
        expires_in=86400,  # 24 hours
        role=UserRole.SYSTEM_ADMIN,
        user_id="SYSTEM_ADMIN"
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    End the current session by revoking the API key.

    This endpoint invalidates the current authentication token,
    effectively logging out the user.
    """
    if auth.api_key_id:
        await auth_service.revoke_api_key(auth.api_key_id)
        logger.info(f"User {auth.user_id} logged out, API key {auth.api_key_id} revoked")

    return None


@router.get("/auth/me", response_model=UserInfo)
async def get_current_user(
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get current authenticated user information.

    Returns details about the currently authenticated user including
    their role and all permissions based on that role.
    """
    # Get all permissions for the user's role
    if auth.role == UserRole.SYSTEM_ADMIN:
        # SYSTEM_ADMIN has all permissions
        permissions = [p.value for p in Permission]
    else:
        # Get role-based permissions
        role_permissions = ROLE_PERMISSIONS.get(auth.role, set())
        permissions = [p.value for p in role_permissions]

    # For API key auth, we don't have a traditional username
    # Use the user_id as username
    username = auth.user_id

    return UserInfo(
        user_id=auth.user_id,
        username=username,
        role=auth.role,
        permissions=permissions,
        created_at=auth.authenticated_at,  # Use auth time as proxy
        last_login=auth.authenticated_at
    )


@router.post("/auth/refresh", response_model=LoginResponse)
async def refresh_token(
    request: TokenRefreshRequest,
    auth: Optional[AuthContext] = Depends(optional_auth),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    Refresh access token.

    Creates a new access token and revokes the old one. Supports both
    API key and OAuth refresh flows. The user must be authenticated
    to refresh their token.
    """
    # For now, we require the user to be authenticated to refresh
    # In a full implementation, we'd validate the refresh token separately
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to refresh token"
        )

    # Generate new API key
    new_api_key = f"ciris_{auth.role.value.lower()}_{secrets.token_urlsafe(32)}"

    # Set expiration based on role
    if auth.role == UserRole.SYSTEM_ADMIN:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        expires_in = 86400  # 24 hours
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        expires_in = 2592000  # 30 days

    # Store new API key
    await auth_service.store_api_key(
        key=new_api_key,
        user_id=auth.user_id,
        role=auth.role,
        expires_at=expires_at,
        description="Refreshed token"
    )

    # Revoke old API key if it exists
    if auth.api_key_id:
        await auth_service.revoke_api_key(auth.api_key_id)

    logger.info(f"Token refreshed for user {auth.user_id}")

    return LoginResponse(
        access_token=new_api_key,
        token_type="Bearer",
        expires_in=expires_in,
        role=auth.role,
        user_id=auth.user_id
    )
