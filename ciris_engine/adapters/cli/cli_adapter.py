import logging

from ciris_engine.protocols.services import CommunicationService

logger = logging.getLogger(__name__)


class CLIAdapter(CommunicationService):
    """Simple CLI adapter implementing CommunicationService.

    Incoming message handling is delegated entirely to ``CLIObserver`` so this
    adapter only implements send and fetch operations.
    """

    def __init__(self):
        pass

    async def start(self):
        logger.info("CLIAdapter started - delegate input to CLIObserver")

    async def stop(self):
        logger.info("CLIAdapter stopped")

    async def send_message(self, channel_id: str, content: str) -> bool:
        print(f"[CLI][{channel_id}] {content}")
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100):
        # CLI adapter does not maintain history; return empty list
        return []

    def get_capabilities(self) -> list[str]:
        # Support both sending and fetching messages so the service
        # can satisfy communication requests via the registry
        return ["send_message", "fetch_messages"]
