from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class ProcessorInterface(ABC):
    """Contract for main agent processors."""

    @abstractmethod
    async def start_processing(self, num_rounds: Optional[int] = None) -> None:
        """Start the main agent processing loop."""

    @abstractmethod
    async def stop_processing(self) -> None:
        """Stop processing and clean up resources."""

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current processor status and metrics."""

    @abstractmethod
    async def process(self, round_number: int) -> Dict[str, Any]:
        """Execute one round of processing."""
