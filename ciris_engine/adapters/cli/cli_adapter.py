import logging
import uuid
from datetime import datetime, timezone
from typing import List
from ciris_engine.protocols.services import CommunicationService
from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

logger = logging.getLogger(__name__)


class CLIAdapter(CommunicationService):
    """Simple CLI adapter implementing CommunicationService."""

    def __init__(self) -> None:
        """Initialize the adapter with no interactive input handling."""

    async def start(self) -> None:
        """CLI adapter has no startup actions."""
        pass

    async def stop(self) -> None:
        """CLI adapter has no background tasks to stop."""
        pass

    async def send_message(self, channel_id: str, content: str) -> bool:
        correlation_id = ServiceCorrelationStatus.PENDING
        print(f"[CLI][{channel_id}] {content}")
        corr = ServiceCorrelation(
            correlation_id=ServiceCorrelationStatus.PENDING,
            service_type=ServiceCorrelationStatus.PENDING,
            handler_name=ServiceCorrelationStatus.PENDING,
            action_type=ServiceCorrelationStatus.PENDING,
            request_data={"channel_id": channel_id, "content": content},
            response_data={"sent": True},
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        persistence.add_correlation(corr)
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        return []

    def get_capabilities(self) -> list[str]:
        return ["send_message", "fetch_messages"]
