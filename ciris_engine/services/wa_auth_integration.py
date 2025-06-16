"""WA Authentication System Integration Module."""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from ciris_engine.services.wa_auth_service import WAAuthService
from ciris_engine.services.wa_cli_service import WACLIService
from ciris_engine.services.wa_auth_middleware import WAAuthMiddleware
from ciris_engine.config.config_manager import get_sqlite_db_full_path


logger = logging.getLogger(__name__)


class WAAuthenticationSystem:
    """Main integration point for the WA authentication system."""
    
    def __init__(self, db_path: Optional[str] = None, key_dir: Optional[str] = None):
        """Initialize the complete authentication system.
        
        Args:
            db_path: Database path (defaults to config)
            key_dir: Key directory (defaults to ~/.ciris/)
        """
        # Use configured database if not specified
        self.db_path = db_path or get_sqlite_db_full_path()
        self.key_dir = key_dir
        
        # Initialize core services
        self.auth_service = WAAuthService(self.db_path, self.key_dir)
        self.cli_service = WACLIService(self.auth_service)
        self.middleware = WAAuthMiddleware(self.auth_service)
        
        logger.info(f"WA Authentication System initialized with database: {self.db_path}")
    
    async def bootstrap(self) -> None:
        """Bootstrap the authentication system on first run."""
        try:
            # Check if bootstrap is needed
            await self.auth_service.bootstrap_if_needed()
            
            # Get all WAs to verify bootstrap
            was = await self.auth_service.list_all_was()
            
            if was:
                logger.info(f"Found {len(was)} WA certificates in database")
                for wa in was:
                    logger.info(f"  - {wa.name} ({wa.wa_id}): {wa.role.value}")
            else:
                logger.warning("No WA certificates found - system needs onboarding")
            
        except Exception as e:
            logger.error(f"Error during authentication bootstrap: {e}")
            raise
    
    async def create_adapter_token(self, adapter_type: str, adapter_info: Dict[str, Any]) -> str:
        """Create a channel token for an adapter.
        
        Args:
            adapter_type: Type of adapter (cli, http, discord)
            adapter_info: Adapter-specific information
            
        Returns:
            JWT token for the adapter
        """
        return await self.auth_service.create_channel_token_for_adapter(adapter_type, adapter_info)
    
    async def onboard_interactive(self) -> Dict[str, Any]:
        """Run interactive onboarding wizard."""
        return await self.cli_service.onboard_wizard()
    
    def get_auth_service(self) -> WAAuthService:
        """Get the core authentication service."""
        return self.auth_service
    
    def get_cli_service(self) -> WACLIService:
        """Get the CLI service for command handling."""
        return self.cli_service
    
    def get_middleware(self) -> WAAuthMiddleware:
        """Get the authentication middleware for FastAPI."""
        return self.middleware
    
    def get_oauth_service(self) -> Any:
        """Get the OAuth service from CLI service."""
        # The OAuth functionality is in wa_cli_oauth module
        from ciris_engine.services.wa_cli_oauth import WACLIOAuthService
        if not hasattr(self, '_oauth_service'):
            self._oauth_service = WACLIOAuthService(self.auth_service)
        return self._oauth_service


# Singleton instance
_auth_system: Optional[WAAuthenticationSystem] = None


def get_auth_system(db_path: Optional[str] = None, key_dir: Optional[str] = None) -> WAAuthenticationSystem:
    """Get or create the authentication system singleton.
    
    Args:
        db_path: Database path (only used on first call)
        key_dir: Key directory (only used on first call)
        
    Returns:
        WAAuthenticationSystem instance
    """
    global _auth_system
    
    if _auth_system is None:
        _auth_system = WAAuthenticationSystem(db_path, key_dir)
    
    return _auth_system


async def initialize_authentication(db_path: Optional[str] = None, key_dir: Optional[str] = None) -> WAAuthenticationSystem:
    """Initialize and bootstrap the authentication system.
    
    Args:
        db_path: Database path
        key_dir: Key directory
        
    Returns:
        Initialized WAAuthenticationSystem
    """
    auth_system = get_auth_system(db_path, key_dir)
    await auth_system.bootstrap()
    return auth_system