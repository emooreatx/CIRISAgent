from abc import ABC, abstractmethod
from typing import Dict, Any
from ciris_engine.protocols.schemas import GuardrailCheckResult, ActionSelectionResult

class GuardrailInterface(ABC):
    """Contract for guardrail checks."""

    @abstractmethod
    def check(self, action: ActionSelectionResult, data: Dict[str, Any]) -> GuardrailCheckResult:
        """Return warnings or errors if guardrail is violated."""
