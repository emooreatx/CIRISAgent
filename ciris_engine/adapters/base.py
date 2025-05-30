import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Service(ABC):
    """Abstract base class for pluggable services within the CIRIS Engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the service.

        Args:
            config: Optional configuration dictionary specific to the service.
        """
        self.config = config or {}
        self.service_name = self.__class__.__name__ # Default name
        logger.info(f"Initializing service: {self.service_name}")

    @abstractmethod
    async def start(self):
        """Starts the service and any background tasks it manages."""
        logger.info(f"Starting service: {self.service_name}")
        pass

    @abstractmethod
    async def stop(self):
        """Stops the service and cleans up resources."""
        logger.info(f"Stopping service: {self.service_name}")
        pass

    # Optional methods for health checks or status reporting could be added here later
    # async def health_check(self) -> bool: ...
    # async def get_status(self) -> Dict[str, Any]: ...

    def __repr__(self) -> str:
        return f"<{self.service_name}>"
