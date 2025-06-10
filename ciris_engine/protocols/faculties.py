from typing import Protocol, Optional, Dict, Any, runtime_checkable
from pydantic import BaseModel

@runtime_checkable
class EpistemicFaculty(Protocol):
    """Protocol for epistemic faculties."""

    async def evaluate(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> BaseModel:
        """Evaluate content through this faculty.
        
        Returns:
            BaseModel: A pydantic model containing evaluation results.
                      Typically an instance of FacultyResult or its subclasses.
        """
        ...
