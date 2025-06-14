"""Protocol for WA CLI operations."""
from typing import Protocol, Optional, Dict, Any
from abc import abstractmethod


class WACLIInterface(Protocol):
    """Protocol for WA command-line operations."""
    
    @abstractmethod
    async def bootstrap_new_root(
        self, 
        name: str, 
        use_password: bool = False,
        shamir_shares: Optional[tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """Bootstrap a new root WA."""
        ...
    
    @abstractmethod
    async def mint_wa(
        self,
        name: str,
        role: str,
        auth_type: str,
        parent_wa_id: Optional[str],
        parent_key_file: Optional[str]
    ) -> Dict[str, Any]:
        """Mint a new WA certificate."""
        ...
    
    @abstractmethod
    async def generate_mint_request(
        self,
        name: str,
        auth_type: str
    ) -> str:
        """Generate one-time code for mint request."""
        ...
    
    @abstractmethod
    async def approve_mint_request(
        self,
        request_code: str,
        signer_wa_id: str,
        signer_key_file: str
    ) -> Dict[str, Any]:
        """Approve a mint request with signature."""
        ...
    
    @abstractmethod
    async def oauth_setup(
        self,
        provider: str,
        client_id: str,
        client_secret: str
    ) -> None:
        """Configure OAuth provider."""
        ...
    
    @abstractmethod
    async def oauth_login(
        self,
        provider: str,
        callback_port: int = 8888
    ) -> Dict[str, Any]:
        """Perform OAuth login flow."""
        ...