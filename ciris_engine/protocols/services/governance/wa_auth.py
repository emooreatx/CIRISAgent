"""
WA Authentication Protocol Interfaces.

As specified in FSD/AUTHENTICATION.md section 11.
These protocols define the contracts for WA authentication components.
"""
from typing import Protocol, Optional, Dict, List, Tuple, Any
from abc import abstractmethod

from ciris_engine.schemas.services.authority_core import (
    WACertificate, AuthorizationContext
)
from ciris_engine.schemas.services.authority.jwt import (
    JWTClaims, JWTToken, JWTValidationResult
)
from ciris_engine.schemas.services.authority.wa_updates import (
    WACertificateUpdate
)
from ciris_engine.schemas.infrastructure.oauth import (
    OAuthProviderConfig, OAuthUserProfile,
    OAuthCallbackResponse
)

class WAStore(Protocol):
    """Protocol for WA certificate storage operations."""

    @abstractmethod
    async def get_wa_cert(self, wa_id: str) -> Optional[WACertificate]:
        """Get WA certificate by ID."""
        ...

    @abstractmethod
    async def get_wa_cert_by_pubkey(self, pubkey: str) -> Optional[WACertificate]:
        """Get WA certificate by public key."""
        ...

    @abstractmethod
    async def get_wa_cert_by_channel(self, channel_id: str) -> Optional[WACertificate]:
        """Get WA certificate by channel ID."""
        ...

    @abstractmethod
    async def create_wa_cert(self, _: WACertificate) -> bool:
        """Create new WA certificate."""
        ...

    @abstractmethod
    async def update_wa_cert(self, wa_id: str, updates: WACertificateUpdate) -> bool:
        """Update existing WA certificate."""
        ...

    @abstractmethod
    async def list_wa_certs(self, active_only: bool = True) -> List[WACertificate]:
        """List all WA certificates."""
        ...

    @abstractmethod
    async def revoke_wa_cert(self, wa_id: str) -> bool:
        """Revoke a WA certificate."""
        ...

class JWTService(Protocol):
    """Protocol for JWT operations."""

    @abstractmethod
    def issue_token(self, sub: str, sub_type: str, name: str, scope: List[str], **kwargs: Any) -> str:
        """Issue a JWT token."""
        ...

    @abstractmethod
    def verify_token(self, token: str) -> Optional[JWTClaims]:
        """Verify and decode a JWT token."""
        ...

    @abstractmethod
    def get_gateway_secret(self) -> bytes:
        """Get or generate gateway secret for HS256 signing."""
        ...

class WACrypto(Protocol):
    """Protocol for cryptographic operations."""

    @abstractmethod
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate Ed25519 keypair (private, public)."""
        ...

    @abstractmethod
    def sign_message(self, message: bytes, private_key: bytes) -> bytes:
        """Sign a message with Ed25519 private key."""
        ...

    @abstractmethod
    def verify_signature(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify Ed25519 signature."""
        ...

    @abstractmethod
    def save_private_key(self, wa_id: str, private_key: bytes) -> bool:
        """Save private key to secure storage."""
        ...

    @abstractmethod
    def load_private_key(self, wa_id: str) -> Optional[bytes]:
        """Load private key from secure storage."""
        ...

    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash password using PBKDF2."""
        ...

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        ...

    @abstractmethod
    def generate_api_key(self, wa_id: str) -> str:
        """Generate API key for WA."""
        ...

class WAAuthMiddleware(Protocol):
    """Protocol for authentication middleware operations."""

    @abstractmethod
    async def authenticate(self, token: Optional[str]) -> Optional[AuthorizationContext]:
        """Authenticate request and return auth context."""
        ...

    @abstractmethod
    async def authorize(self, context: AuthorizationContext, _: List[str]) -> bool:
        """Check if context has required scopes."""
        ...

    @abstractmethod
    def extract_token(self, authorization: Optional[str]) -> Optional[str]:
        """Extract token from Authorization header."""
        ...

class OAuthService(Protocol):
    """Protocol for OAuth operations."""

    @abstractmethod
    async def get_oauth_providers(self) -> Dict[str, OAuthProviderConfig]:
        """Get configured OAuth providers."""
        ...

    @abstractmethod
    async def save_oauth_provider(self, provider: str, config: OAuthProviderConfig) -> bool:
        """Save OAuth provider configuration."""
        ...

    @abstractmethod
    async def get_oauth_url(self, provider: str, state: str) -> str:
        """Get OAuth authorization URL."""
        ...

    @abstractmethod
    async def handle_oauth_callback(
        self,
        provider: str,
        code: str,
        state: str
    ) -> Optional[OAuthCallbackResponse]:
        """Handle OAuth callback and return token + profile."""
        ...

    @abstractmethod
    async def create_oauth_wa(
        self,
        provider: str,
        external_id: str,
        profile: Dict[str, Any]
    ) -> Optional[WACertificate]:
        """Create WA certificate from OAuth profile."""
        ...

__all__ = [
    "WAStore",
    "JWTService",
    "WACrypto",
    "WAAuthMiddleware",
    "OAuthService",
]
