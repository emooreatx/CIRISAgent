import logging
from typing import Optional, Dict, Any

from .ciris_runtime import CIRISRuntime

logger = logging.getLogger(__name__)


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

