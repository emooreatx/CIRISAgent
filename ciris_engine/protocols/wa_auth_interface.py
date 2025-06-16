"""Protocol definitions for WA authentication system."""
from typing import Protocol, Optional, List, Dict, Any
from abc import abstractmethod
from datetime import datetime

from ciris_engine.schemas.wa_schemas_v1 import (
    WACertificate, ChannelIdentity, 
    AuthorizationContext
)


class WAStore(Protocol):
    """Protocol for WA certificate storage."""
    
    @abstractmethod
    async def get_wa(self, wa_id: str) -> Optional[WACertificate]:
        """Get WA certificate by ID."""
        ...
    
    @abstractmethod
    async def get_wa_by_kid(self, jwt_kid: str) -> Optional[WACertificate]:
        """Get WA certificate by JWT key ID."""
        ...
    
    @abstractmethod
    async def get_wa_by_oauth(self, provider: str, external_id: str) -> Optional[WACertificate]:
        """Get WA certificate by OAuth identity."""
        ...
    
    @abstractmethod
    async def get_wa_by_channel(self, channel_id: str) -> Optional[WACertificate]:
        """Get WA certificate by channel ID."""
        ...
    
    @abstractmethod
    async def create_wa(self, wa: WACertificate) -> None:
        """Store new WA certificate."""
        ...
    
    @abstractmethod
    async def create_channel_observer(self, channel_id: str, name: str) -> WACertificate:
        """Create or reactivate channel observer WA."""
        ...
    
    @abstractmethod
    async def update_wa(self, wa_id: str, **updates: Any) -> None:
        """Update WA certificate fields."""
        ...
    
    @abstractmethod
    async def revoke_wa(self, wa_id: str, revoked_by: str, reason: str) -> None:
        """Revoke WA certificate."""
        ...
    
    @abstractmethod
    async def list_all_was(self, active_only: bool = True) -> List[WACertificate]:
        """List all WA certificates."""
        ...
    
    @abstractmethod
    async def update_last_login(self, wa_id: str) -> None:
        """Update last login timestamp."""
        ...


class JWTService(Protocol):
    """Protocol for JWT token operations."""
    
    @abstractmethod
    def create_channel_token(self, wa: WACertificate) -> str:
        """Create non-expiring channel observer token."""
        ...
    
    @abstractmethod
    def create_gateway_token(self, wa: WACertificate, expires_hours: int = 8) -> str:
        """Create gateway-signed token (OAuth/password auth)."""
        ...
    
    @abstractmethod
    def create_authority_token(self, wa: WACertificate, private_key: bytes) -> str:
        """Create WA-signed authority token."""
        ...
    
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[AuthorizationContext]:
        """Verify any JWT token and return auth context."""
        ...


class WACrypto(Protocol):
    """Protocol for WA cryptographic operations."""
    
    @abstractmethod
    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate Ed25519 keypair (private, public)."""
        ...
    
    @abstractmethod
    def sign_data(self, data: bytes, private_key: bytes) -> str:
        """Sign data with Ed25519 private key."""
        ...
    
    @abstractmethod
    def verify_signature(self, data: bytes, signature: str, public_key: str) -> bool:
        """Verify Ed25519 signature."""
        ...
    
    @abstractmethod
    def generate_wa_id(self, timestamp: datetime) -> str:
        """Generate deterministic WA ID."""
        ...
    
    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash password using PBKDF2."""
        ...
    
    @abstractmethod
    def verify_password(self, password: str, hash: str) -> bool:
        """Verify password against hash."""
        ...
    
    @abstractmethod
    def generate_api_key(self, wa_id: str) -> str:
        """Generate API key for WA."""
        ...


class OAuthService(Protocol):
    """Protocol for OAuth operations."""
    
    @abstractmethod
    async def start_flow(self, provider: str, state: str) -> str:
        """Start OAuth flow, return authorization URL."""
        ...
    
    @abstractmethod
    async def handle_callback(self, provider: str, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback, return user info."""
        ...
    
    @abstractmethod
    async def add_provider(self, config: dict) -> None:
        """Add OAuth provider configuration."""
        ...
    
    @abstractmethod
    async def list_providers(self) -> List[str]:
        """List configured OAuth providers."""
        ...


class WAAuthMiddleware(Protocol):
    """Protocol for authentication middleware."""
    
    @abstractmethod
    async def authenticate(self, token: Optional[str]) -> Optional[AuthorizationContext]:
        """Authenticate request and return auth context."""
        ...
    
    @abstractmethod
    def require_scope(self, scope: str) -> Any:
        """Decorator to require specific scope for endpoint."""
        ...
    
    @abstractmethod
    def get_channel_token(self, channel_id: str) -> Optional[str]:
        """Get cached channel token."""
        ...