"""WA Authentication Middleware for endpoint protection."""

from typing import Optional, Callable, Dict, Any, List
from functools import wraps
import logging

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ciris_engine.schemas.wa_schemas_v1 import AuthorizationContext, JWTSubType
from ciris_engine.protocols.endpoint_security import EndpointSecurity as EndpointSecurityProtocol
from ciris_engine.services.wa_auth_service import WAAuthService


logger = logging.getLogger(__name__)


class WAAuthMiddleware:
    """Authentication middleware for protecting API endpoints."""
    
    def __init__(self, auth_service: WAAuthService):
        """Initialize middleware with authentication service."""
        self.auth_service = auth_service
        self.bearer_scheme = HTTPBearer(auto_error=False)
        
        # Initialize endpoint security mappings
        self.endpoint_security = EndpointSecurityProtocol()
    
    async def __call__(self, request: Request) -> Optional[AuthorizationContext]:
        """Extract and validate authentication from request."""
        # Try to get bearer token
        credentials: Optional[HTTPAuthorizationCredentials] = await self.bearer_scheme(request)
        
        if credentials:
            # Verify JWT token
            auth_context = await self.auth_service.authenticate(credentials.credentials)
            if auth_context:
                # Store in request state for later use
                request.state.auth_context = auth_context
                return auth_context
        
        # Check for channel token in headers
        channel_token = request.headers.get("X-Channel-Token")
        if channel_token:
            auth_context = await self.auth_service.authenticate(channel_token)
            if auth_context:
                request.state.auth_context = auth_context
                return auth_context
        
        # No valid authentication found
        return None
    
    def require_auth(self, f: Callable) -> Callable:
        """Decorator that requires any valid authentication."""
        @wraps(f)
        async def decorated(request: Request, *args, **kwargs):
            auth_context = await self(request)
            if not auth_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await f(request, *args, **kwargs)
        return decorated
    
    def require_scope(self, scope: str) -> Callable:
        """Decorator that requires a specific scope."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def decorated(request: Request, *args, **kwargs):
                auth_context = await self(request)
                
                if not auth_context:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                if not auth_context.has_scope(scope):
                    logger.warning(
                        f"Access denied: {auth_context.wa_id} lacks scope '{scope}' "
                        f"(has: {auth_context.scopes})"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Requires scope: {scope}",
                    )
                
                return await f(request, *args, **kwargs)
            return decorated
        return decorator
    
    def require_scopes(self, scopes: List[str], require_all: bool = True) -> Callable:
        """Decorator that requires multiple scopes."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def decorated(request: Request, *args, **kwargs):
                auth_context = await self(request)
                
                if not auth_context:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                if require_all:
                    # Require ALL scopes
                    missing_scopes = [s for s in scopes if not auth_context.has_scope(s)]
                    if missing_scopes:
                        logger.warning(
                            f"Access denied: {auth_context.wa_id} lacks scopes {missing_scopes}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient permissions. Missing scopes: {missing_scopes}",
                        )
                else:
                    # Require ANY scope
                    if not any(auth_context.has_scope(s) for s in scopes):
                        logger.warning(
                            f"Access denied: {auth_context.wa_id} lacks any of scopes {scopes}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient permissions. Requires one of: {scopes}",
                        )
                
                return await f(request, *args, **kwargs)
            return decorated
        return decorator
    
    def require_role(self, minimum_role: str) -> Callable:
        """Decorator that requires a minimum role level."""
        role_hierarchy = {"observer": 0, "authority": 1, "root": 2}
        
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def decorated(request: Request, *args, **kwargs):
                auth_context = await self(request)
                
                if not auth_context:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                user_level = role_hierarchy.get(auth_context.role.value, -1)
                required_level = role_hierarchy.get(minimum_role, 999)
                
                if user_level < required_level:
                    logger.warning(
                        f"Access denied: {auth_context.wa_id} has role '{auth_context.role.value}' "
                        f"but '{minimum_role}' required"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient role. Requires: {minimum_role}",
                    )
                
                return await f(request, *args, **kwargs)
            return decorated
        return decorator
    
    def protect_endpoint(self, endpoint_path: str, method: str = "GET") -> Callable:
        """Protect an endpoint based on predefined security rules."""
        def decorator(f: Callable) -> Callable:
            # Get required scopes for this endpoint
            required_scopes = self.endpoint_security.get_required_scopes(method, endpoint_path)
            
            if not required_scopes:
                # No protection needed
                return f
            
            # Apply scope requirements
            return self.require_scopes(required_scopes)(f)
        return decorator
    
    async def validate_request(self, request: Request, endpoint_path: str, method: str = "GET") -> bool:
        """Validate a request against endpoint security rules."""
        auth_context = await self(request)
        
        # Get required scopes
        required_scopes = self.endpoint_security.get_required_scopes(method, endpoint_path)
        
        if not required_scopes:
            # No auth required
            return True
        
        if not auth_context:
            # Auth required but not provided
            return False
        
        # Check if user has all required scopes
        for scope in required_scopes:
            if not auth_context.has_scope(scope):
                return False
        
        return True
    
    def get_channel_token_for_adapter(self, channel_id: str) -> Optional[str]:
        """Get cached channel token for an adapter."""
        return self.auth_service.get_channel_token(channel_id)
    
    async def issue_channel_token(self, adapter_type: str, adapter_info: Dict[str, Any]) -> str:
        """Issue a new channel token for an adapter."""
        return await self.auth_service.create_channel_token_for_adapter(adapter_type, adapter_info)


# FastAPI dependency for getting auth context
async def get_current_wa(request: Request) -> Optional[AuthorizationContext]:
    """FastAPI dependency to get current authenticated WA."""
    return getattr(request.state, "auth_context", None)


async def require_wa(request: Request) -> AuthorizationContext:
    """FastAPI dependency that requires authentication."""
    auth_context = getattr(request.state, "auth_context", None)
    if not auth_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_context