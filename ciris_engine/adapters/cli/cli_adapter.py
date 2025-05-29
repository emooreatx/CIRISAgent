import logging

logger = logging.getLogger(__name__)

class CLIAdapter:
    """Adapter for CLI-based agent IO and event handling."""
    def __init__(self):
        self.client = self  # For interface compatibility

    async def start(self):
        """Start the CLI adapter."""
        pass

    async def stop(self):
        """Stop the CLI adapter."""
        pass

    async def send_message(self, channel_id: str, content: str) -> None:
        print(f"[CLI][{channel_id}] {content}")
    async def fetch_channel(self, channel_id: str):
        return self  # Dummy for compatibility
    def get_channel(self, channel_id: str):
        return self  # Dummy for compatibility
