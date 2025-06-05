# ciris_engine/utils/shutdown_manager.py
"""
Global shutdown manager for graceful shutdown from anywhere in the codebase.
"""
import logging
import asyncio
from typing import Optional, Callable, List
from threading import Lock

logger = logging.getLogger(__name__)

class ShutdownManager:
    """
    Global manager for handling graceful shutdown requests from anywhere in the codebase.
    
    This provides a centralized way to:
    1. Register shutdown handlers from different parts of the system
    2. Request graceful shutdown from any code location
    3. Track shutdown state globally
    4. Execute cleanup callbacks in proper order
    """
    
    def __init__(self) -> None:
        self._shutdown_requested = False
        self._shutdown_reason: Optional[str] = None
        self._shutdown_handlers: List[Callable[[], None]] = []
        self._async_shutdown_handlers: List[Callable[[], None]] = []
        self._lock = Lock()
        self._shutdown_event = asyncio.Event() if asyncio._get_running_loop() else None
        
    def register_shutdown_handler(self, handler: Callable[[], None], is_async: bool = False) -> None:
        """
        Register a shutdown handler to be called during graceful shutdown.
        
        Args:
            handler: Function to call during shutdown (should be idempotent)
            is_async: Whether the handler is async
        """
        with self._lock:
            if is_async:
                self._async_shutdown_handlers.append(handler)
                logger.debug(f"Registered async shutdown handler: {handler.__name__}")
            else:
                self._shutdown_handlers.append(handler)
                logger.debug(f"Registered shutdown handler: {handler.__name__}")
    
    def request_shutdown(self, reason: str = "Global shutdown requested") -> None:
        """
        Request a graceful shutdown from anywhere in the codebase.
        
        Args:
            reason: Human-readable reason for the shutdown request
        """
        with self._lock:
            if self._shutdown_requested:
                logger.debug(f"Shutdown already requested, ignoring duplicate: {reason}")
                return
                
            self._shutdown_requested = True
            self._shutdown_reason = reason
            
        logger.critical(f"GLOBAL SHUTDOWN REQUESTED: {reason}")
        
        # Set the event if we're in an async context
        if self._shutdown_event:
            self._shutdown_event.set()
        
        # Execute synchronous shutdown handlers immediately
        self._execute_sync_handlers()
    
    def _execute_sync_handlers(self) -> None:
        """Execute all registered synchronous shutdown handlers."""
        with self._lock:
            handlers = self._shutdown_handlers.copy()
        
        for handler in handlers:
            try:
                handler()
                logger.debug(f"Executed shutdown handler: {handler.__name__}")
            except Exception as e:
                logger.error(f"Error in shutdown handler {handler.__name__}: {e}")
    
    async def execute_async_handlers(self) -> None:
        """Execute all registered asynchronous shutdown handlers."""
        with self._lock:
            handlers = self._async_shutdown_handlers.copy()
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                logger.debug(f"Executed async shutdown handler: {handler.__name__}")
            except Exception as e:
                logger.error(f"Error in async shutdown handler {handler.__name__}: {e}")
    
    def is_shutdown_requested(self) -> bool:
        """Check if a shutdown has been requested."""
        return self._shutdown_requested
    
    def get_shutdown_reason(self) -> Optional[str]:
        """Get the reason for the shutdown request."""
        return self._shutdown_reason
    
    async def wait_for_shutdown(self) -> None:
        """Wait for a shutdown request (async context only)."""
        if not self._shutdown_event:
            # Create event if we're now in async context
            try:
                self._shutdown_event = asyncio.Event()
                if self._shutdown_requested:
                    self._shutdown_event.set()
            except RuntimeError:
                logger.warning("Cannot create event outside of async context")
                return
        
        await self._shutdown_event.wait()
    
    def reset(self) -> None:
        """Reset the shutdown manager (for testing purposes)."""
        with self._lock:
            self._shutdown_requested = False
            self._shutdown_reason = None
            self._shutdown_handlers.clear()
            self._async_shutdown_handlers.clear()
            if self._shutdown_event:
                self._shutdown_event.clear()
        logger.debug("Shutdown manager reset")


# Global instance
_global_shutdown_manager: Optional[ShutdownManager] = None
_manager_lock = Lock()

def get_shutdown_manager() -> ShutdownManager:
    """Get or create the global shutdown manager instance."""
    global _global_shutdown_manager
    
    with _manager_lock:
        if _global_shutdown_manager is None:
            _global_shutdown_manager = ShutdownManager()
            logger.debug("Created global shutdown manager")
        return _global_shutdown_manager

def request_global_shutdown(reason: str = "Global shutdown requested") -> None:
    """
    Request a graceful shutdown from anywhere in the codebase.
    
    This is the main entry point for shutdown requests outside of the runtime.
    
    Args:
        reason: Human-readable reason for the shutdown request
    """
    manager = get_shutdown_manager()
    manager.request_shutdown(reason)

def register_global_shutdown_handler(handler: Callable[[], None], is_async: bool = False) -> None:
    """
    Register a global shutdown handler.
    
    Args:
        handler: Function to call during shutdown
        is_async: Whether the handler is async
    """
    manager = get_shutdown_manager()
    manager.register_shutdown_handler(handler, is_async)

def is_global_shutdown_requested() -> bool:
    """Check if a global shutdown has been requested."""
    manager = get_shutdown_manager()
    return manager.is_shutdown_requested()

async def wait_for_global_shutdown() -> None:
    """Wait for a global shutdown request (async context only)."""
    manager = get_shutdown_manager()
    await manager.wait_for_shutdown()

def get_global_shutdown_reason() -> Optional[str]:
    """Get the reason for the global shutdown request."""
    manager = get_shutdown_manager()
    return manager.get_shutdown_reason()

# Convenience function for critical service failures
def request_shutdown_critical_service_failure(service_name: str, error: str = "") -> None:
    """
    Request shutdown due to critical service failure.
    
    Args:
        service_name: Name of the service that failed
        error: Additional error details
    """
    reason = f"Critical service failure: {service_name}"
    if error:
        reason += f" - {error}"
    
    request_global_shutdown(reason)

# Convenience function for communication failures
def request_shutdown_communication_failure(details: str = "") -> None:
    """
    Request shutdown due to communication service failure.
    
    Args:
        details: Additional failure details
    """
    reason = "Communication services unavailable"
    if details:
        reason += f" - {details}"
    
    request_global_shutdown(reason)

# Convenience function for unrecoverable errors
def request_shutdown_unrecoverable_error(error_type: str, details: str = "") -> None:
    """
    Request shutdown due to unrecoverable error.
    
    Args:
        error_type: Type of error
        details: Additional error details
    """
    reason = f"Unrecoverable error: {error_type}"
    if details:
        reason += f" - {details}"
    
    request_global_shutdown(reason)
