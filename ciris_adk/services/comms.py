"""CommunicationService protocol for external messaging channels."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Protocol


class CommunicationService(Protocol):
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send a message to the specified channel."""
        ...

    async def fetch_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Dict[str, Any]]:
        """Retrieve messages from a channel."""
        ...

