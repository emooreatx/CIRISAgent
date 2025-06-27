"""
Authentication API routes for CIRIS.

Implements session management endpoints:
- POST /v1/auth/login - Authenticate user
- POST /v1/auth/logout - End session  
- GET /v1/auth/me - Current user info
- GET /v1/auth/permissions - User permissions
- POST /v1/auth/token/refresh - Refresh access token

Note: OAuth endpoints are in api_auth_v2.py
"""
import hashlib
import secrets
import logging
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Request, Depends

from ciris_engine.schemas.api.auth import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    TokenResponse,
    TokenRefreshRequest,
    Permission,
    UserRole,
    ROLE_PERMISSIONS,
)
from ciris_engine.api.dependencies.auth import (
    get_auth_context,
    get_auth_service,
    optional_auth,
)
from ciris_engine.schemas.api.auth import AuthContext
from ciris_engine.api.services.auth_service import APIAuthService

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
    
    Currently supports ROOT user only. In production, this would
    integrate with a proper user database.
    """
    config_service = getattr(req.app.state, 'config_service', None)
    
    if not config_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration service not available"
        )
    
    # Get ROOT credentials from config
    try:
        root_username = await config_service.get_config("root_username")
        root_password_hash = await config_service.get_config("root_password_hash")
    except Exception as e:
        logger.error(f"Failed to get root credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve authentication configuration"
        )
    
    if not root_username or not root_password_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ROOT credentials not configured"
        )
    
    # Verify credentials
    if request.username != root_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Hash the provided password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if password_hash != root_password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Generate API key for ROOT
    api_key = f"ciris_root_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Store API key
    await auth_service.store_api_key(
        key=api_key,
        user_id="ROOT",
        role=UserRole.ROOT,
        expires_at=expires_at,
        description="ROOT login session"
    )
    
    logger.info(f"ROOT user logged in successfully")
    
    return LoginResponse(
        access_token=api_key,
        token_type="Bearer",
        expires_in=86400,  # 24 hours
        role=UserRole.ROOT,
        user_id="ROOT"
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
    their role and permissions.
    """
    # Convert permissions set to list of strings
    permissions = [p.value for p in auth.permissions]
    
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


@router.get("/auth/permissions", response_model=List[str])
async def get_user_permissions(
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get the current user's permissions.
    
    Returns a list of permission strings that the authenticated user has
    based on their role.
    """
    # For ROOT, return all permissions
    if auth.role == UserRole.ROOT:
        return [p.value for p in Permission]
    
    # Otherwise return role-based permissions
    permissions = ROLE_PERMISSIONS.get(auth.role, set())
    return [p.value for p in permissions]


@router.post("/auth/token/refresh", response_model=LoginResponse)
async def refresh_token(
    request: TokenRefreshRequest,
    auth: Optional[AuthContext] = Depends(optional_auth),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    Refresh access token.
    
    This endpoint allows refreshing an access token. In this implementation,
    we create a new API key and revoke the old one if the user is authenticated.
    
    Note: Full refresh token functionality would require storing refresh tokens
    separately from access tokens.
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
    if auth.role == UserRole.ROOT:
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