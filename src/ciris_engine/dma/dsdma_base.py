# src/ciris_engine/dma/dsdma_base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional # Added Optional
from ciris_engine.core.data_schemas import ThoughtQueueItem, DSDMAResult # Use the new DSDMAResult

class BaseDSDMA(ABC):
    """
    Abstract Base Class for Domain-Specific Decision-Making Algorithms.
    """

    def __init__(self, domain_name: str, domain_specific_knowledge: Optional[Dict[str, Any]] = None): # Made knowledge optional and Dict
        self.domain_name = domain_name
        self.domain_specific_knowledge = domain_specific_knowledge if domain_specific_knowledge else {}
        super().__init__()

    @abstractmethod
    async def evaluate_thought(self, thought_item: ThoughtQueueItem, current_context: Dict[str, Any]) -> DSDMAResult: # Changed to async def, Return DSDMAResult
        """
        Evaluate a thought within the DSDMA's specific domain.
        """
        pass

    def __repr__(self) -> str:
        return f"<BaseDSDMA domain='{self.domain_name}'>"
