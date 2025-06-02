from abc import ABC, abstractmethod
from typing import Any, Dict

class ProcessorInterface(ABC):
    """Contract for main agent processors."""

    @abstractmethod
    async def handle_observation(self, observation: Dict[str, Any]) -> None:
        """Given an incoming observation, run the full pipeline."""

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanly tear down processor resources."""
