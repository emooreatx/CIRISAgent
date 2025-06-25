"""
Schemas for OAuth authentication flows.

These replace all Dict[str, Any] usage in wa_cli_oauth.py.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import Field

class OAuthProviderConfig(BaseModel):
    """Configuration for an OAuth provider."""
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    created: datetime = Field(..., description="When provider was configured")
    metadata: Optional[dict] = Field(None, description="Custom provider metadata")

class OAuthSetupRequest(BaseModel):
    """Request to setup OAuth provider."""
    provider: str = Field(..., description="OAuth provider name")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    custom_metadata: Optional[dict] = Field(None, description="Custom metadata")

class OAuthOperationResult(BaseModel):
    """Result of an OAuth operation."""
    status: str = Field(..., description="Operation status (success/error)")
    provider: Optional[str] = Field(None, description="OAuth provider name")
    callback_url: Optional[str] = Field(None, description="OAuth callback URL")
    error: Optional[str] = Field(None, description="Error message if failed")
    details: Optional[dict] = Field(None, description="Additional details")

class OAuthLoginResult(BaseModel):
    """Result of OAuth login attempt."""
    status: str = Field(..., description="Login status")
    provider: str = Field(..., description="OAuth provider used")
    auth_url: Optional[str] = Field(None, description="Authorization URL")
    certificate: Optional[dict] = Field(None, description="WA certificate if successful")
    error: Optional[str] = Field(None, description="Error message if failed")

class OAuthProviderList(BaseModel):
    """List of configured OAuth providers."""
    providers: List[str] = Field(..., description="List of provider names")
    count: int = Field(..., description="Number of providers")

class OAuthProviderDetails(BaseModel):
    """Details about a specific OAuth provider."""
    provider: str = Field(..., description="Provider name")
    client_id: str = Field(..., description="OAuth client ID")
    created: datetime = Field(..., description="When configured")
    has_metadata: bool = Field(..., description="Whether custom metadata exists")
    metadata: Optional[dict] = Field(None, description="Custom metadata if any")

class OAuthCallbackData(BaseModel):
    """Data received from OAuth callback."""
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="OAuth state parameter")
    error: Optional[str] = Field(None, description="Error from provider")
    error_description: Optional[str] = Field(None, description="Error details")

class OAuthTokenExchange(BaseModel):
    """OAuth token exchange request/response."""
    grant_type: str = Field("authorization_code", description="OAuth grant type")
    code: str = Field(..., description="Authorization code")
    redirect_uri: str = Field(..., description="Redirect URI")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")

class OAuthTokenResponse(BaseModel):
    """Response from OAuth token endpoint."""
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(..., description="Token type (e.g., Bearer)")
    expires_in: Optional[int] = Field(None, description="Token expiry in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    scope: Optional[str] = Field(None, description="Granted scopes")

class OAuthUserInfo(BaseModel):
    """User information from OAuth provider."""
    id: str = Field(..., description="User ID from provider")
    email: Optional[str] = Field(None, description="User email")
    name: Optional[str] = Field(None, description="User display name")
    picture: Optional[str] = Field(None, description="User avatar URL")
    provider_data: dict = Field(default_factory=dict, description="Raw provider data")