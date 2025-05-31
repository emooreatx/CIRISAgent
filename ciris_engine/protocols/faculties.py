from typing import Protocol, Optional, Dict, Any
from pydantic import BaseModel

class EpistemicFaculty(Protocol):
    """Protocol for epistemic faculties."""

    async def evaluate(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> BaseModel:
        """Evaluate content through this faculty."""
        ...
