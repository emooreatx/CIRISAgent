"""
Authentication dependencies for FastAPI routes.

Provides role-based access control through dependency injection.
"""
from fastapi import Depends, HTTPException, status, Request, Header
from typing import Optional, Callable
from datetime import datetime, timezone

from ciris_engine.schemas.api.auth import AuthContext, UserRole, ROLE_PERMISSIONS
from ..services.auth_service import APIAuthService

async def get_auth_service(request: Request) -> APIAuthService:
    """Get auth service from app state."""
    if not hasattr(request.app.state, 'auth_service'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    auth_service = request.app.state.auth_service
    if not isinstance(auth_service, APIAuthService):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid auth service type"
        )
    return auth_service

async def get_auth_context(
    request: Request,
    authorization: Optional[str] = Header(None),
    auth_service: APIAuthService = Depends(get_auth_service)
) -> AuthContext:
    """Extract and validate authentication from request."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format",
            headers={"WWW-Authenticate": "Bearer"}
        )

    api_key = authorization[7:]  # Remove "Bearer " prefix

    # Validate API key
    key_info = await auth_service.validate_api_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Get user to check for custom permissions
    user = await auth_service.get_user(key_info.user_id)
    
    # Start with role-based permissions
    permissions = set(ROLE_PERMISSIONS.get(key_info.role, set()))
    
    # Add any custom permissions if user exists and has them
    if user and hasattr(user, 'custom_permissions') and user.custom_permissions:
        for perm in user.custom_permissions:
            # Add custom permission string to the set
            permissions.add(perm)

    # Create auth context with request reference
    context = AuthContext(
        user_id=key_info.user_id,
        role=key_info.role,
        permissions=permissions,
        api_key_id=auth_service._get_key_id(api_key),
        authenticated_at=datetime.now(timezone.utc)
    )

    # Attach request to context for service access in routes
    context.request = request

    return context

async def optional_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
    auth_service: APIAuthService = Depends(get_auth_service)
) -> Optional[AuthContext]:
    """Optional authentication - returns None if no auth provided."""
    if not authorization:
        return None

    try:
        return await get_auth_context(request, authorization, auth_service)
    except HTTPException:
        return None

def require_role(minimum_role: UserRole) -> Callable:
    """
    Factory for role-based access control dependencies.

    Args:
        minimum_role: Minimum role required for access

    Returns:
        Dependency function that validates role
    """
    async def check_role(
        auth: AuthContext = Depends(get_auth_context)
    ) -> AuthContext:
        """Validate user has required role."""
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
require_system_admin = require_role(UserRole.SYSTEM_ADMIN)

def check_permissions(permissions: list[str]) -> Callable:
    """
    Factory for permission-based access control dependencies.
    
    Args:
        permissions: List of required permissions
    
    Returns:
        Dependency function that validates permissions
    """
    
    async def check(
        auth: AuthContext = Depends(get_auth_context),
        auth_service: APIAuthService = Depends(get_auth_service)
    ) -> None:
        """Validate user has required permissions."""
        # Get the user from auth service to get their API role
        user = await auth_service.get_user(auth.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found"
            )
        
        # Get permissions for user's API role
        user_permissions = set(auth_service.get_permissions_for_role(user.api_role))
        
        # Add any custom permissions
        if hasattr(user, 'custom_permissions') and user.custom_permissions:
            for perm in user.custom_permissions:
                user_permissions.add(perm)
        
        # Check if user has all required permissions
        missing = set(permissions) - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}"
            )
    
    return check
