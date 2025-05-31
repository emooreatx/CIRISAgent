"""API runtime implementation for REST or GraphQL interfaces."""
from typing import Optional

from .ciris_runtime import CIRISRuntime



class APIRuntime(CIRISRuntime):
    """Runtime for REST/GraphQL API mode."""

    def __init__(self, profile_name: str = "default") -> None:
        super().__init__(profile_name=profile_name)

    async def initialize(self) -> None:
        await super().initialize()
        await self._register_api_services()

    async def _register_api_services(self) -> None:
        """Register API-specific services."""
        if not self.service_registry:
            return
        logger.info("API services registered")

    def __init__(self, profile_name: str = "default", startup_channel_id: Optional[str] = None):
        super().__init__(profile_name=profile_name, io_adapter=None, startup_channel_id=startup_channel_id)
        self.api_server = None  # Placeholder for future HTTP adapter

    async def _register_api_services(self):
        """Register API-specific services."""
        if not self.service_registry:
            return
        # Register HTTP adapter, webhook handlers and response formatters here
        # This is currently a stub until API components are implemented
        return

    async def initialize(self):
        await super().initialize()
        await self._register_api_services()

