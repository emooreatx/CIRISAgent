"""WA CLI Service - Main coordinator for WA management CLI operations."""

from typing import Dict, Any, Optional, List, Tuple

from ciris_engine.protocols.wa_cli_interface import WACLIInterface
from ciris_engine.services.wa_auth_service import WAAuthService
from ciris_engine.services.wa_cli_bootstrap import WACLIBootstrapService
from ciris_engine.services.wa_cli_oauth import WACLIOAuthService
from ciris_engine.services.wa_cli_display import WACLIDisplayService
from ciris_engine.services.wa_cli_wizard import WACLIWizardService


class WACLIService(WACLIInterface):
    """Main CLI service that coordinates WA management operations."""
    
    def __init__(self, auth_service: WAAuthService):
        """Initialize CLI service with authentication service."""
        self.auth_service = auth_service
        
        # Initialize sub-services
        self.bootstrap_service = WACLIBootstrapService(auth_service)
        self.oauth_service = WACLIOAuthService(auth_service)
        self.display_service = WACLIDisplayService(auth_service)
        self.wizard_service = WACLIWizardService(
            auth_service,
            self.bootstrap_service,
            self.oauth_service,
            self.display_service
        )
    
    # Delegate methods to sub-services
    
    async def bootstrap_new_root(
        self, 
        name: str, 
        use_password: bool = False,
        shamir_shares: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """Bootstrap a new root WA."""
        return await self.bootstrap_service.bootstrap_new_root(
            name=name,
            use_password=use_password,
            shamir_shares=shamir_shares
        )
    
    async def mint_wa(
        self,
        parent_wa_id: str,
        parent_key_file: str,
        name: str,
        role: str = "authority",
        scopes: Optional[List[str]] = None,
        use_password: bool = False
    ) -> Dict[str, Any]:
        """Mint a new WA as a child of an existing WA."""
        return await self.bootstrap_service.mint_wa(
            parent_wa_id=parent_wa_id,
            parent_key_file=parent_key_file,
            name=name,
            role=role,
            scopes=scopes,
            use_password=use_password
        )
    
    async def generate_mint_request(
        self,
        name: str,
        requested_role: str = "authority",
        requested_scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a mint request code for approval by existing WA."""
        return await self.bootstrap_service.generate_mint_request(
            name=name,
            requested_role=requested_role,
            requested_scopes=requested_scopes
        )
    
    async def approve_mint_request(
        self,
        code: str,
        approver_wa_id: str,
        approver_key_file: str
    ) -> Dict[str, Any]:
        """Approve a mint request and create new WA."""
        return await self.bootstrap_service.approve_mint_request(
            code=code,
            approver_wa_id=approver_wa_id,
            approver_key_file=approver_key_file
        )
    
    async def oauth_setup(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Configure OAuth provider."""
        return await self.oauth_service.oauth_setup(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            custom_metadata=custom_metadata
        )
    
    async def oauth_login(self, provider: str) -> Dict[str, Any]:
        """Initiate OAuth login flow."""
        return await self.oauth_service.oauth_login(provider)
    
    async def list_was(self, tree_view: bool = False) -> None:
        """List all WAs in table or tree format."""
        await self.display_service.list_was(tree_view)
    
    async def show_wa_details(self, wa_id: str) -> None:
        """Display detailed information about a specific WA."""
        await self.display_service.show_wa_details(wa_id)
    
    async def onboard_wizard(self) -> Dict[str, Any]:
        """Interactive onboarding wizard for new operators."""
        return await self.wizard_service.onboard_wizard()
    
    # Additional methods can be added here as needed
    # For example: revoke_wa, rotate_key, link_discord, etc.