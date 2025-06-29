"""API Authentication endpoints v2.0.

Provides OAuth authentication and API key management.
"""
import logging
import secrets
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import RedirectResponse

from ciris_engine.schemas.api.auth import (
    UserRole,
    AuthContext,
    LoginRequest,
    LoginResponse,
    TokenResponse,
    OAuth2CallbackResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyListResponse
)
from ciris_engine.schemas.infrastructure.oauth import (
    OAuthProviderConfig,
    OAuthTokenResponse,
    OAuthUserInfo
)
from ciris_engine.api.dependencies.auth_v2 import get_auth_context, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth state storage (in production, use Redis or similar)
_oauth_states: Dict[str, Dict[str, Any]] = {}


def _get_oauth_config(provider: str, request: Request) -> OAuthProviderConfig:
    """Get OAuth provider configuration."""
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration service not available"
        )

    # Get OAuth provider configs
    oauth_configs = config_service.get_config("oauth_providers") or {}

    if provider not in oauth_configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' not configured"
        )

    provider_config = oauth_configs[provider]

    # Add provider-specific auth/token URLs
    auth_urls = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "discord": "https://discord.com/api/oauth2/authorize",
        "github": "https://github.com/login/oauth/authorize"
    }

    token_urls = {
        "google": "https://oauth2.googleapis.com/token",
        "discord": "https://discord.com/api/oauth2/token",
        "github": "https://github.com/login/oauth/access_token"
    }

    return OAuthProviderConfig(
        client_id=provider_config.get("client_id"),
        client_secret=provider_config.get("client_secret"),
        auth_url=provider_config.get("auth_url", auth_urls.get(provider, "")),
        token_url=provider_config.get("token_url", token_urls.get(provider, "")),
        scopes=provider_config.get("scopes", "openid email profile"),
        created=datetime.now(timezone.utc)
    )


async def _exchange_code_for_token(
    provider: str,
    code: str,
    provider_config: OAuthProviderConfig,
    redirect_uri: str
) -> OAuthTokenResponse:
    """Exchange authorization code for access token."""
    # Token endpoints by provider
    token_urls = {
        "google": "https://oauth2.googleapis.com/token",
        "discord": "https://discord.com/api/oauth2/token",
        "github": "https://github.com/login/oauth/access_token"
    }

    if provider not in token_urls:
        raise ValueError(f"Unsupported provider: {provider}")

    # Prepare token request
    token_request_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": provider_config.client_id,
        "client_secret": provider_config.client_secret,
        "redirect_uri": redirect_uri
    }

    # Make token request
    async with aiohttp.ClientSession() as session:
        async with session.post(
            token_urls[provider],
            data=token_request_data,
            headers={"Accept": "application/json"}
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise ValueError(f"Token exchange failed: {error}")

            token_json = await resp.json()
            token_data = OAuthTokenResponse(
                access_token=token_json['access_token'],
                token_type=token_json.get('token_type', 'Bearer'),
                expires_in=token_json.get('expires_in'),
                refresh_token=token_json.get('refresh_token'),
                scope=token_json.get('scope')
            )
            return token_data


async def _fetch_user_profile(
    provider: str,
    access_token: str
) -> OAuthUserInfo:
    """Fetch user profile from OAuth provider."""
    # User info endpoints by provider
    user_endpoints = {
        "google": "https://www.googleapis.com/oauth2/v2/userinfo",
        "discord": "https://discord.com/api/users/@me",
        "github": "https://api.github.com/user"
    }

    if provider not in user_endpoints:
        raise ValueError(f"Unsupported provider: {provider}")

    # Fetch user info
    async with aiohttp.ClientSession() as session:
        async with session.get(
            user_endpoints[provider],
            headers={"Authorization": f"Bearer {access_token}"}
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise ValueError(f"Failed to fetch user profile: {error}")

            profile = await resp.json()

            # Normalize profile data
            if provider == "google":
                return OAuthUserInfo(
                    id=profile.get("id", ""),
                    email=profile.get("email"),
                    name=profile.get("name"),
                    picture=profile.get("picture"),
                    provider_data=profile
                )
            elif provider == "discord":
                return OAuthUserInfo(
                    id=profile.get("id", ""),
                    email=profile.get("email"),
                    name=profile.get("username"),
                    provider_data={
                        "discriminator": profile.get("discriminator"),
                        "avatar": profile.get("avatar"),
                        **profile
                    }
                )
            elif provider == "github":
                return OAuthUserInfo(
                    id=str(profile.get("id", "")),
                    email=profile.get("email"),
                    name=profile.get("name") or profile.get("login"),
                    picture=profile.get("avatar_url"),
                    provider_data={
                        "login": profile.get("login"),
                        **profile
                    }
                )

            # Return raw profile for unhandled providers
            return OAuthUserInfo(
                id=str(profile.get("id", "")),
                email=profile.get("email"),
                name=profile.get("name"),
                provider_data=profile
            )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """Authenticate with username/password (ROOT only)."""
    config_service = getattr(req.app.state, 'config_service', None)
    auth_service = getattr(req.app.state, 'auth_service', None)

    if not config_service or not auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Services not available"
        )

    # Get ROOT credentials from config
    root_username = await config_service.get_config("root_username")
    root_password_hash = await config_service.get_config("root_password_hash")

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

    # Verify password (simplified - use proper password hashing in production)
    import hashlib
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
        expires_at=expires_at
    )

    return LoginResponse(
        access_token=api_key,
        token_type="Bearer",
        expires_in=86400,  # 24 hours
        role=UserRole.ROOT,
        user_id="ROOT"
    )


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, request: Request, redirect_uri: Optional[str] = None):
    """Start OAuth authentication flow."""
    # Validate provider
    if provider not in ["google", "discord", "github"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )

    # Get provider config
    provider_config = _get_oauth_config(provider, request)

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state with metadata for validation
    _oauth_states[state] = {
        "provider": provider,
        "created_at": datetime.now(timezone.utc),
        "redirect_uri": redirect_uri
    }

    # Clean up old states (older than 10 minutes)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    old_states = [k for k, v in _oauth_states.items() if v["created_at"] <= cutoff]
    for k in old_states:
        del _oauth_states[k]

    # Build callback URI
    if not redirect_uri:
        # Use our callback endpoint
        base_url = str(request.base_url).rstrip('/')
        redirect_uri = f"{base_url}/v2/auth/oauth/{provider}/callback"

    # Build authorization URL
    auth_params = {
        'client_id': provider_config.client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'state': state,
        'scope': provider_config.scopes
    }

    # Add provider-specific parameters
    if provider == 'discord':
        auth_params['prompt'] = 'consent'
    elif provider == 'google':
        auth_params['access_type'] = 'offline'
        auth_params['prompt'] = 'consent'

    auth_url = f"{provider_config.auth_url}?{urlencode(auth_params)}"

    # Redirect to provider
    return RedirectResponse(url=auth_url)


@router.get("/oauth/{provider}/callback", response_model=OAuth2CallbackResponse)
async def oauth_callback(
    provider: str,
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Handle OAuth callback from provider."""
    # Check for errors from provider
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error} - {error_description or 'No description'}"
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state"
        )

    # Validate state
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state"
        )

    state_data = _oauth_states.pop(state)
    if state_data["provider"] != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider mismatch in OAuth callback"
        )

    # Get provider config
    provider_config = _get_oauth_config(provider, request)

    # Exchange code for tokens
    token_data = await _exchange_code_for_token(
        provider=provider,
        code=code,
        provider_config=provider_config,
        redirect_uri=state_data.get("redirect_uri") or
                     f"{str(request.base_url).rstrip('/')}/v2/auth/oauth/{provider}/callback"
    )

    # Fetch user profile
    user_profile = await _fetch_user_profile(provider, token_data.access_token)

    # Create or update user
    auth_service = getattr(request.app.state, 'auth_service', None)
    if not auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available"
        )

    # Check if user exists
    user_id = f"{provider}:{user_profile.id}"
    existing_user = await auth_service.get_user_by_oauth(provider, user_profile.id)

    if not existing_user:
        # Create new OBSERVER user
        await auth_service.create_oauth_user(
            provider=provider,
            external_id=user_profile.id,
            email=user_profile.email,
            name=user_profile.name or user_profile.email.split('@')[0] if user_profile.email else f"{provider}_user",
            role=UserRole.OBSERVER
        )

    # Generate API key
    api_key = f"ciris_{provider}_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    # Store API key
    await auth_service.store_api_key(
        key=api_key,
        user_id=user_id,
        role=UserRole.OBSERVER,
        expires_at=expires_at
    )

    return OAuth2CallbackResponse(
        access_token=api_key,
        token_type="Bearer",
        expires_in=2592000,  # 30 days
        role=UserRole.OBSERVER,
        user_id=user_id,
        provider=provider,
        email=user_profile.email,
        name=user_profile.name
    )


@router.post("/apikeys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    auth: AuthContext = Depends(require_admin)
):
    """Create a new API key (ADMIN+ only)."""
    # Validate role assignment
    if request.role.value > auth.role.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create API key with higher role than your own"
        )

    # Generate API key
    api_key = f"ciris_{request.role.value.lower()}_{secrets.token_urlsafe(32)}"

    # Calculate expiration
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)
    else:
        expires_at = None  # No expiration

    # Get auth service from auth context's request
    auth_service = getattr(auth.request.app.state, 'auth_service', None)
    if not auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available"
        )

    await auth_service.store_api_key(
        key=api_key,
        user_id=auth.user_id,
        role=request.role,
        expires_at=expires_at,
        description=request.description,
        created_by=auth.user_id
    )

    return APIKeyResponse(
        api_key=api_key,
        role=request.role,
        expires_at=expires_at,
        description=request.description,
        created_at=datetime.now(timezone.utc),
        created_by=auth.user_id
    )


@router.get("/apikeys", response_model=APIKeyListResponse)
async def list_api_keys(auth: AuthContext = Depends(require_admin)):
    """List all API keys (ADMIN+ only)."""
    auth_service = getattr(auth.request.app.state, 'auth_service', None)
    if not auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available"
        )

    # Get all API keys
    keys = await auth_service.list_api_keys()

    # Filter based on role
    if auth.role != UserRole.ROOT:
        # Non-ROOT users can only see keys they created or with lower roles
        keys = [k for k in keys if k.created_by == auth.user_id or k.role.value < auth.role.value]

    return APIKeyListResponse(
        api_keys=keys,
        total=len(keys)
    )


@router.delete("/apikeys/{key_id}")
async def revoke_api_key(key_id: str, auth: AuthContext = Depends(require_admin)):
    """Revoke an API key (ADMIN+ only)."""
    auth_service = getattr(auth.request.app.state, 'auth_service', None)
    if not auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available"
        )

    # Get key details
    key_info = await auth_service.get_api_key_info(key_id)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Check permissions
    if auth.role != UserRole.ROOT:
        # Non-ROOT can only revoke keys they created or with lower roles
        if key_info.created_by != auth.user_id and key_info.role.value >= auth.role.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to revoke this key"
            )

    # Revoke the key
    await auth_service.revoke_api_key(key_id)

    return {"status": "success", "message": f"API key {key_id} revoked"}


@router.get("/me", response_model=TokenResponse)
async def get_current_user(auth: AuthContext = Depends(get_auth_context)):
    """Get current authenticated user information."""
    return TokenResponse(
        user_id=auth.user_id,
        role=auth.role,
        scopes=auth.scopes,
        expires_at=auth.expires_at
    )
