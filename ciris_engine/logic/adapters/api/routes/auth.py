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
from typing import Optional, Dict, Any
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
from ciris_engine.schemas.runtime.api import APIRole
from ..dependencies.auth import (
    get_auth_context,
    get_auth_service,
    optional_auth,
    check_permissions,
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
) -> LoginResponse:
    """
    Authenticate with username/password.

    Currently supports system admin user only. In production, this would
    integrate with a proper user database.
    """
    getattr(req.app.state, 'config_service', None)

    # Try to find user by username in auth service
    users = await auth_service.list_users(search=request.username)
    user = None
    for u in users:
        if u.name == request.username and u.auth_type == "password":
            user = u
            break
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if user.password_hash != password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Generate API key based on user's role
    api_key = f"ciris_{user.api_role.value.lower()}_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Map APIRole to UserRole for API key storage
    user_role_map = {
        APIRole.OBSERVER: UserRole.OBSERVER,
        APIRole.ADMIN: UserRole.ADMIN,
        APIRole.AUTHORITY: UserRole.AUTHORITY,
        APIRole.SYSTEM_ADMIN: UserRole.SYSTEM_ADMIN
    }
    
    # Store API key
    await auth_service.store_api_key(
        key=api_key,
        user_id=user.wa_id,
        role=user_role_map[user.api_role],
        expires_at=expires_at,
        description="Login session"
    )

    logger.info(f"User {user.name} logged in successfully")

    return LoginResponse(
        access_token=api_key,
        token_type="Bearer",
        expires_in=86400,  # 24 hours
        role=user_role_map[user.api_role],
        user_id=user.wa_id
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service)
) -> None:
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
) -> UserInfo:
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
) -> LoginResponse:
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


# ========== OAuth Management Endpoints ==========

@router.get("/auth/oauth/providers")
async def list_oauth_providers(
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(check_permissions(["users.write"]))  # SYSTEM_ADMIN only
) -> Dict[str, Any]:
    """
    List configured OAuth providers.
    
    Requires: users.write permission (SYSTEM_ADMIN only)
    """
    import json
    from pathlib import Path
    
    oauth_config_file = Path.home() / ".ciris" / "oauth.json"
    
    if not oauth_config_file.exists():
        return {"providers": []}
    
    try:
        config = json.loads(oauth_config_file.read_text())
        providers = []
        
        for provider, settings in config.items():
            providers.append({
                "provider": provider,
                "client_id": settings.get("client_id"),
                "created": settings.get("created"),
                "callback_url": f"http://localhost:3000/auth/oauth/{provider}/callback",
                "metadata": settings.get("metadata", {})
            })
        
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Failed to read OAuth config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read OAuth configuration"
        )


@router.post("/auth/oauth/providers")
async def configure_oauth_provider(
    provider: str,
    client_id: str,
    client_secret: str,
    metadata: Optional[Dict[str, str]] = None,
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(check_permissions(["users.write"]))  # SYSTEM_ADMIN only
) -> Dict[str, Any]:
    """
    Configure an OAuth provider.
    
    Requires: users.write permission (SYSTEM_ADMIN only)
    """
    import json
    from pathlib import Path
    
    oauth_config_file = Path.home() / ".ciris" / "oauth.json"
    oauth_config_file.parent.mkdir(exist_ok=True, mode=0o700)
    
    # Load existing config
    config = {}
    if oauth_config_file.exists():
        try:
            config = json.loads(oauth_config_file.read_text())
        except:
            pass
    
    # Add/update provider
    config[provider] = {
        "client_id": client_id,
        "client_secret": client_secret,
        "created": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {}
    }
    
    # Save config
    try:
        oauth_config_file.write_text(json.dumps(config, indent=2))
        oauth_config_file.chmod(0o600)
        
        logger.info(f"OAuth provider '{provider}' configured by {auth.user_id}")
        
        return {
            "provider": provider,
            "callback_url": f"http://localhost:3000/auth/oauth/{provider}/callback",
            "message": "OAuth provider configured successfully"
        }
    except Exception as e:
        logger.error(f"Failed to save OAuth config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save OAuth configuration"
        )


@router.get("/auth/oauth/{provider}/login")
async def oauth_login(
    provider: str,
    redirect_uri: Optional[str] = None
) -> Dict[str, str]:
    """
    Initiate OAuth login flow.
    
    Redirects to the OAuth provider's authorization URL.
    """
    import json
    from pathlib import Path
    import urllib.parse
    
    oauth_config_file = Path.home() / ".ciris" / "oauth.json"
    
    if not oauth_config_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider}' not configured"
        )
    
    try:
        config = json.loads(oauth_config_file.read_text())
        if provider not in config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OAuth provider '{provider}' not configured"
            )
        
        provider_config = config[provider]
        client_id = provider_config["client_id"]
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in a temporary location (in production, use Redis or similar)
        # For now, we'll include it in the redirect_uri
        
        callback_url = redirect_uri or f"http://localhost:3000/auth/oauth/{provider}/callback"
        
        # Build authorization URL based on provider
        if provider == "google":
            auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
            params = {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "offline",
                "prompt": "consent"
            }
        elif provider == "github":
            auth_url = "https://github.com/login/oauth/authorize"
            params = {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state
            }
        elif provider == "discord":
            auth_url = "https://discord.com/api/oauth2/authorize"
            params = {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": "identify email",
                "state": state
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth provider: {provider}"
            )
        
        # Build full URL
        full_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
        
        return {
            "authorization_url": full_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"OAuth login initiation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OAuth login"
        )


@router.post("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    auth_service: APIAuthService = Depends(get_auth_service)
) -> LoginResponse:
    """
    Handle OAuth callback.
    
    Exchanges authorization code for tokens and creates/updates user.
    """
    import json
    import httpx
    from pathlib import Path
    
    # Load OAuth configuration
    oauth_config_file = Path.home() / ".ciris" / "oauth.json"
    
    if not oauth_config_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider}' not configured"
        )
    
    try:
        config = json.loads(oauth_config_file.read_text())
        if provider not in config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OAuth provider '{provider}' not configured"
            )
        
        provider_config = config[provider]
        client_id = provider_config["client_id"]
        client_secret = provider_config["client_secret"]
        
        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            if provider == "google":
                # Exchange code for token
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": f"http://localhost:3000/auth/oauth/{provider}/callback",
                        "grant_type": "authorization_code"
                    }
                )
                
                if token_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to exchange code for token: {token_response.text}"
                    )
                
                token_data = token_response.json()
                access_token = token_data["access_token"]
                
                # Get user info
                user_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if user_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to fetch user info"
                    )
                
                user_info = user_response.json()
                external_id = user_info["id"]
                email = user_info.get("email")
                name = user_info.get("name", email)
                
            elif provider == "github":
                # Exchange code for token
                token_response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": f"http://localhost:3000/auth/oauth/{provider}/callback"
                    }
                )
                
                if token_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to exchange code for token: {token_response.text}"
                    )
                
                token_data = token_response.json()
                access_token = token_data["access_token"]
                
                # Get user info
                user_response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"token {access_token}"}
                )
                
                if user_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to fetch user info"
                    )
                
                user_info = user_response.json()
                external_id = str(user_info["id"])
                email = user_info.get("email")
                name = user_info.get("name", user_info.get("login"))
                
                # If email is private, fetch from emails endpoint
                if not email:
                    emails_response = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"token {access_token}"}
                    )
                    if emails_response.status_code == 200:
                        emails = emails_response.json()
                        for e in emails:
                            if e.get("primary"):
                                email = e["email"]
                                break
                
            elif provider == "discord":
                # Exchange code for token
                token_response = await client.post(
                    "https://discord.com/api/oauth2/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": f"http://localhost:3000/auth/oauth/{provider}/callback",
                        "grant_type": "authorization_code"
                    }
                )
                
                if token_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to exchange code for token: {token_response.text}"
                    )
                
                token_data = token_response.json()
                access_token = token_data["access_token"]
                
                # Get user info
                user_response = await client.get(
                    "https://discord.com/api/users/@me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if user_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to fetch user info"
                    )
                
                user_info = user_response.json()
                external_id = user_info["id"]
                email = user_info.get("email")
                name = user_info.get("username", email)
                
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported OAuth provider: {provider}"
                )
        
        # Create or update OAuth user
        oauth_user = await auth_service.create_oauth_user(
            provider=provider,
            external_id=external_id,
            email=email,
            name=name,
            role=UserRole.OBSERVER  # Default role for new OAuth users
        )
        
        # Generate API key for the user
        api_key = f"ciris_observer_{secrets.token_urlsafe(32)}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        await auth_service.store_api_key(
            key=api_key,
            user_id=oauth_user.user_id,
            role=oauth_user.role,
            expires_at=expires_at,
            description=f"OAuth login via {provider}"
        )
        
        logger.info(f"OAuth user {oauth_user.user_id} logged in successfully via {provider}")
        
        return LoginResponse(
            access_token=api_key,
            token_type="Bearer",
            expires_in=2592000,  # 30 days
            role=oauth_user.role,
            user_id=oauth_user.user_id
        )
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )
