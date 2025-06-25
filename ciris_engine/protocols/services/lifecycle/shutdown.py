"""Shutdown Service Protocol."""

from typing import Protocol, Optional, Callable
from abc import abstractmethod

from ...runtime.base import ServiceProtocol

class ShutdownServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for shutdown service."""
    
    @abstractmethod
    async def request_shutdown(self, reason: str) -> None:
        """Request system shutdown."""
        ...
    
    @abstractmethod
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        ...
    
    @abstractmethod
    def get_shutdown_reason(self) -> Optional[str]:
        """Get the reason for shutdown."""
        ...
    
    @abstractmethod
    def register_shutdown_handler(self, handler: Callable[[], None]) -> None:
        """Register a shutdown handler."""
        ...