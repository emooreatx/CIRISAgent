"""Adaptive Filter Service Protocol."""

from typing import Protocol, Any
from abc import abstractmethod

from ...runtime.base import ServiceProtocol
from ciris_engine.schemas.services.filters_core import FilterResult, FilterHealth, FilterTrigger

class AdaptiveFilterServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for adaptive filter service."""
    
    @abstractmethod
    async def filter_message(
        self, 
        message: Any,
        adapter_type: str,
        is_llm_response: bool = False
    ) -> FilterResult:
        """Apply filters to determine message priority and processing.
        
        Args:
            message: The message object to filter
            adapter_type: The adapter type (discord, cli, api)
            is_llm_response: Whether this is an LLM-generated response
            
        Returns:
            FilterResult with priority, triggered filters, and processing decision
        """
        ...
    
    @abstractmethod
    def get_health(self) -> FilterHealth:
        """Get filter service health and statistics."""
        ...
    
    @abstractmethod
    def add_filter_trigger(self, trigger: FilterTrigger) -> None:
        """Add a new filter trigger."""
        ...
    
    @abstractmethod
    def remove_filter_trigger(self, pattern: str) -> bool:
        """Remove a filter trigger by pattern."""
        ...