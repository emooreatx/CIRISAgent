"""Epistemic Faculty Protocol for Conscience Integration."""

from typing import Protocol, Dict, Any, Optional, List
from abc import abstractmethod

class EpistemicFaculty(Protocol):
    """Protocol for epistemic faculties used in conscience bounce mechanism."""
    
    @abstractmethod
    async def analyze(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze content and return epistemic insights.
        
        Args:
            content: The content to analyze
            context: Optional context for deeper analysis
            
        Returns:
            Dictionary containing faculty-specific analysis results
        """
        ...
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this faculty."""
        ...
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get the capabilities of this faculty."""
        ...