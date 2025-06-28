"""
Base Processor Protocol - Interface for all state processors.

This protocol defines the interface that all state processors
(WorkProcessor, PlayProcessor, DreamProcessor, etc.) must implement.
"""

from typing import Protocol, List, Dict, Any, Optional, TYPE_CHECKING
from abc import abstractmethod

if TYPE_CHECKING:
    from ciris_engine.schemas.processors.results import ProcessingResult

class ProcessorProtocol(Protocol):
    """
    Protocol for individual state processors.
    
    Each processor handles a specific AgentState and must implement
    these methods for the AgentProcessor to coordinate them.
    
    Note: Processors are NOT services - they don't implement ServiceProtocol.
    They are components managed by the AgentProcessor.
    """
    
    @abstractmethod
    def get_supported_states(self) -> List[str]:  # List[AgentState]
        """
        Get the states this processor handles.
        
        Most processors handle one state, but some may handle multiple.
        
        Returns:
            List of AgentState values this processor supports
        """
        ...
    
    @abstractmethod
    async def process(self, round_number: int) -> "ProcessingResult":
        """
        Main processing method for the state.
        
        Args:
            round_number: Current processing round
            
        Returns:
            ProcessingResult - A state-specific result (WakeupResult, WorkResult, etc.)
        """
        ...
    
    @abstractmethod
    async def can_process(self) -> bool:
        """
        Check if processor can currently process items.
        
        This checks preconditions like:
        - Required services available
        - No blocking errors
        - State-specific requirements met
        
        Returns:
            True if ready to process
        """
        ...
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize processor for its state.
        
        Called when entering the processor's state.
        Used for setup like loading state-specific data.
        """
        ...
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup when leaving the processor's state.
        
        Called before transitioning to another state.
        Used for saving state, releasing resources, etc.
        """
        ...
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get processor-specific metrics.
        
        Returns:
            Metrics relevant to this processor's state
        """
        ...
    
    @abstractmethod
    def should_transition(self) -> Optional[str]:  # Optional[AgentState]
        """
        Check if processor thinks it's time to transition states.
        
        Returns:
            Target state if transition recommended, None otherwise
        """
        ...
    
    @abstractmethod
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        Handle processing errors.
        
        Args:
            error: The exception that occurred
            context: Context about what was being processed
            
        Returns:
            True if error was handled and processing can continue,
            False if processing should stop
        """
        ...
    
    @abstractmethod
    def get_processor_config(self) -> Dict[str, Any]:
        """
        Get processor configuration.
        
        Returns:
            Configuration specific to this processor
        """
        ...