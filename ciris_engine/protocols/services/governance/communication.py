"""Communication Service Protocol."""

from typing import Protocol, List, Any, Optional, Dict
from abc import abstractmethod
from datetime import datetime

from ...runtime.base import ServiceProtocol

class CommunicationServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for communication service."""

    @abstractmethod
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send a message to the specified channel."""
        ...

    @abstractmethod
    async def fetch_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve messages from a channel."""
        ...

    @abstractmethod
    def get_home_channel_id(self) -> Optional[str]:
        """Get the home channel ID for this communication adapter.
        
        Returns:
            The formatted channel ID (e.g., 'discord_123456', 'cli_user@host', 'api_0.0.0.0_8080')
            or None if no home channel is configured.
        """
        ...
