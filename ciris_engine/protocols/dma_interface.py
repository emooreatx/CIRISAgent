from abc import ABC, abstractmethod
from typing import Any
from ciris_engine.protocols.schemas import Thought, EthicalDMAResult

class DMAEvaluatorInterface(ABC):
    """Protocol for decision making algorithms."""

    @abstractmethod
    async def evaluate(self, thought: Thought) -> EthicalDMAResult:
        """Return an ethical analysis of the thought."""
