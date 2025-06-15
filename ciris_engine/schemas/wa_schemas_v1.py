"""Wise Authority schemas for CIRIS v1.0-β."""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Literal, ClassVar, Dict, Any
from datetime import datetime
from enum import Enum


class WARole(str, Enum):
    """WA role levels."""
    ROOT = "root"
    AUTHORITY = "authority"
    OBSERVER = "observer"


class TokenType(str, Enum):
    """Token type classifications."""
    STANDARD = "standard"
    CHANNEL = "channel"
    OAUTH = "oauth"


class JWTSubType(str, Enum):
    """JWT sub_type values."""
    ANON = "anon"
    OAUTH = "oauth"
    USER = "user"
    AUTHORITY = "authority"


class WACertificate(BaseModel):
    """Wise Authority certificate record."""
    wa_id: str = Field(..., pattern="^wa-\\d{4}-\\d{2}-\\d{2}-[A-Z0-9]{6}$")
    name: str = Field(..., min_length=1, max_length=255)
    role: WARole
    
    # Cryptographic identity
    pubkey: str = Field(..., description="Base64url encoded Ed25519 public key")
    jwt_kid: str = Field(..., description="JWT key identifier")
    
    # Authentication methods
    password_hash: Optional[str] = None
    api_key_hash: Optional[str] = None
    
    # OAuth integration
    oauth_provider: Optional[str] = None
    oauth_external_id: Optional[str] = None
    auto_minted: bool = Field(default=False, description="True if auto-created via OAuth")
    
    # Veilid integration
    veilid_id: Optional[str] = None
    
    # Trust chain
    parent_wa_id: Optional[str] = None
    parent_signature: Optional[str] = None
    
    # Scopes and permissions
    scopes_json: str = Field(..., description="JSON array of scope strings")
    
    # Channel-based observers
    channel_id: Optional[str] = None
    token_type: TokenType = TokenType.STANDARD
    
    # Metadata
    created: datetime
    last_login: Optional[datetime] = None
    active: bool = True
    
    @field_validator('scopes_json')
    @classmethod
    def validate_scopes_json(cls, v: str) -> str:
        """Ensure scopes_json is valid JSON array."""
        import json
        try:
            scopes = json.loads(v)
            if not isinstance(scopes, list):
                raise ValueError("scopes_json must be a JSON array")
            return v
        except json.JSONDecodeError:
            raise ValueError("scopes_json must be valid JSON")
    
    @property
    def scopes(self) -> List[str]:
        """Get scopes as Python list."""
        import json
        scopes_list: List[str] = json.loads(self.scopes_json)
        return scopes_list
    
    def has_scope(self, scope: str) -> bool:
        """Check if WA has a specific scope."""
        return "*" in self.scopes or scope in self.scopes


class WAToken(BaseModel):
    """JWT token payload structure."""
    sub: str = Field(..., description="WA ID")
    sub_type: JWTSubType
    name: str
    scope: List[str]
    iat: int = Field(..., description="Issued at timestamp")
    exp: Optional[int] = Field(None, description="Expiration timestamp (None for anon)")
    
    # Optional claims
    channel: Optional[str] = Field(None, description="Channel ID for anon tokens")
    oauth_provider: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class ChannelIdentity(BaseModel):
    """Channel-based observer identity."""
    channel_id: str
    adapter_type: str
    instance_id: str
    
    @field_validator('channel_id')
    @classmethod
    def validate_channel_format(cls, v: str, info: Any) -> str:
        """Ensure channel_id matches expected format."""
        adapter_type = info.data.get('adapter_type')
        if adapter_type == 'cli' and not v.startswith('cli:'):
            raise ValueError("CLI channel must start with 'cli:'")
        elif adapter_type == 'http' and not v.startswith('http:'):
            raise ValueError("HTTP channel must start with 'http:'")
        elif adapter_type == 'discord' and not v.startswith('discord:'):
            raise ValueError("Discord channel must start with 'discord:'")
        return v
    
    @classmethod
    def from_adapter(cls, adapter_type: str, adapter_info: dict) -> "ChannelIdentity":
        """Create channel identity from adapter info."""
        if adapter_type == 'cli':
            import os
            import socket
            channel_id = f"cli:{os.getenv('USER', 'unknown')}@{socket.gethostname()}"
        elif adapter_type == 'http':
            host = adapter_info.get('host', 'localhost')
            port = adapter_info.get('port', 8080)
            channel_id = f"http:{host}:{port}"
        elif adapter_type == 'discord':
            guild = adapter_info.get('guild_id', 'unknown')
            member = adapter_info.get('member_id', 'bot')
            channel_id = f"discord:{guild}:{member}"
        else:
            channel_id = f"{adapter_type}:{adapter_info.get('instance_id', 'default')}"
        
        return cls(
            channel_id=channel_id,
            adapter_type=adapter_type,
            instance_id=adapter_info.get('instance_id', 'default')
        )


class WACreateRequest(BaseModel):
    """Request to create a new WA."""
    name: str
    role: WARole = WARole.AUTHORITY
    auth_type: Literal["key", "password", "both"] = "both"
    
    # For non-root WAs
    parent_wa_id: Optional[str] = None
    parent_signature: Optional[str] = None
    
    # OAuth linking
    oauth_provider: Optional[str] = None
    oauth_external_id: Optional[str] = None
    
    # Optional password (will be hashed)
    password: Optional[str] = Field(None, min_length=15)


class WAPromoteRequest(BaseModel):
    """Request to promote a WA to higher role."""
    wa_id: str
    new_role: Literal["authority", "root"]
    promoted_by: str = Field(..., description="WA ID of promoter")
    signature: str = Field(..., description="Signature from promoting WA")
    reason: Optional[str] = None


class OAuthProviderConfig(BaseModel):
    """OAuth provider configuration."""
    provider: str
    client_id: str
    client_secret: str = Field(..., repr=False)  # Hide in logs
    metadata_url: Optional[str] = None
    
    # Well-known metadata URLs
    KNOWN_PROVIDERS: ClassVar[Dict[str, Optional[str]]] = {
        "google": "https://accounts.google.com/.well-known/openid-configuration",
        "discord": None,  # Discord doesn't support OIDC discovery
        "github": None    # GitHub uses custom OAuth2 flow
    }
    
    @field_validator('metadata_url', mode='before')
    @classmethod
    def set_metadata_url(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Set metadata URL for known providers."""
        if not v and info.data.get('provider') in cls.KNOWN_PROVIDERS:
            return cls.KNOWN_PROVIDERS[info.data['provider']]
        return v


class AuthorizationContext(BaseModel):
    """Authorization context passed through middleware."""
    wa_id: str
    name: str
    role: WARole
    scopes: List[str]
    token_type: JWTSubType
    
    # Optional metadata
    channel_id: Optional[str] = None
    oauth_provider: Optional[str] = None
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if context has required scope."""
        return "*" in self.scopes or required_scope in self.scopes
    
    def require_scope(self, required_scope: str) -> None:
        """Raise exception if scope not present."""
        if not self.has_scope(required_scope):
            raise PermissionError(f"Scope '{required_scope}' required")