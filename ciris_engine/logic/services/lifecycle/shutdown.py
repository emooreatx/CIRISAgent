"""
Shutdown Service for CIRIS Trinity Architecture.

Manages graceful shutdown coordination across the system.
This replaces the shutdown_manager.py utility with a proper service.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional
from threading import Lock

from ciris_engine.protocols.services import ShutdownServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

logger = logging.getLogger(__name__)

class ShutdownService(ShutdownServiceProtocol, ServiceProtocol):
    """Service for coordinating graceful shutdown."""
    
    def __init__(self) -> None:
        """Initialize the shutdown service."""
        self._shutdown_requested = False
        self._shutdown_reason: Optional[str] = None
        self._shutdown_handlers: List[Callable[[], None]] = []
        self._async_shutdown_handlers: List[Callable[[], Awaitable[None]]] = []
        self._lock = Lock()
        self._shutdown_event: Optional[asyncio.Event] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the service."""
        self._running = True
        try:
            # Create shutdown event if in async context
            self._shutdown_event = asyncio.Event()
        except RuntimeError:
            # Not in async context yet
            pass
        logger.info("ShutdownService started")
    
    async def stop(self) -> None:
        """Stop the service."""
        self._running = False
        logger.info("ShutdownService stopped")
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="ShutdownService",
            actions=[
                "request_shutdown",
                "register_shutdown_handler",
                "is_shutdown_requested",
                "get_shutdown_reason"
            ],
            version="1.0.0",
            dependencies=[],
            metadata={"description": "Coordinates graceful system shutdown"}
        )
    
    def get_status(self) -> ServiceStatus:
        """Get service status."""
        with self._lock:
            handler_count = len(self._shutdown_handlers) + len(self._async_shutdown_handlers)
            
        return ServiceStatus(
            service_name="ShutdownService",
            service_type="core_service",
            is_healthy=self._running,
            uptime_seconds=0.0,  # Not tracked for this service
            metrics={
                "shutdown_requested": float(self._shutdown_requested),
                "registered_handlers": float(handler_count)
            },
            last_error=None,
            last_health_check=None
        )
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._running
    
    async def request_shutdown(self, reason: str) -> None:
        """
        Request system shutdown (async version).
        
        Args:
            reason: Human-readable reason for shutdown
        """
        # Call the sync version but ensure it's properly awaitable
        self._request_shutdown_sync(reason)
        # No need to return anything - this method is async void
    
    def _request_shutdown_sync(self, reason: str) -> None:
        """
        Request system shutdown (sync version).
        
        Args:
            reason: Human-readable reason for shutdown
        """
        with self._lock:
            if self._shutdown_requested:
                logger.debug(f"Shutdown already requested, ignoring duplicate: {reason}")
                return
                
            self._shutdown_requested = True
            self._shutdown_reason = reason
            
        logger.critical(f"SYSTEM SHUTDOWN REQUESTED: {reason}")
        
        # Set event if available
        if self._shutdown_event:
            self._shutdown_event.set()
        
        # Execute sync handlers
        self._execute_sync_handlers()
    
    def register_shutdown_handler(self, handler: Callable[[], None]) -> None:
        """
        Register a shutdown handler.
        
        Args:
            handler: Function to call during shutdown
        """
        with self._lock:
            self._shutdown_handlers.append(handler)
            logger.debug(f"Registered shutdown handler: {handler.__name__}")
    
    def _register_async_shutdown_handler(self, handler: Callable[[], Awaitable[None]]) -> None:
        """
        Register an async shutdown handler (internal method).
        
        Args:
            handler: Async function to call during shutdown
        """
        with self._lock:
            self._async_shutdown_handlers.append(handler)
            logger.debug(f"Registered async shutdown handler: {handler.__name__}")
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested
    
    async def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal (async) - internal method."""
        if not self._shutdown_event:
            # Create event if not exists
            self._shutdown_event = asyncio.Event()
            
            # If shutdown already requested, set the event
            if self._shutdown_requested:
                self._shutdown_event.set()
        
        await self._shutdown_event.wait()
    
    def get_shutdown_reason(self) -> Optional[str]:
        """Get the reason for shutdown."""
        return self._shutdown_reason
    
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
    
    async def _execute_async_handlers(self) -> None:
        """Execute all registered asynchronous shutdown handlers - internal method."""
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
    
    def wait_for_shutdown(self) -> None:
        """Wait for shutdown to be requested (blocking)."""
        import time
        while not self._shutdown_requested:
            time.sleep(0.1)
    
    async def wait_for_shutdown_async(self) -> None:
        """Wait for shutdown to be requested (async)."""
        await self._wait_for_shutdown()
    
    async def emergency_shutdown(
        self, 
        reason: str, 
        timeout_seconds: int = 5
    ) -> None:
        """
        Execute emergency shutdown without negotiation.
        
        This method is used by the emergency shutdown endpoint to force
        immediate system termination with minimal cleanup.
        
        Args:
            reason: Why emergency shutdown was triggered
            timeout_seconds: Grace period before force kill (default 5s)
        """
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")
        
        # Set emergency flags
        self._shutdown_requested = True
        self._shutdown_reason = f"EMERGENCY: {reason}"
        self._emergency_mode = True
        
        # Set shutdown event immediately
        if self._shutdown_event:
            self._shutdown_event.set()
        
        # Notify all handlers with timeout
        try:
            # Execute sync handlers first (quick)
            self._execute_sync_handlers()
            
            # Execute async handlers with timeout
            await asyncio.wait_for(
                self._execute_async_handlers(),
                timeout=timeout_seconds / 2  # Use half timeout for handlers
            )
        except asyncio.TimeoutError:
            logger.warning("Emergency shutdown handlers timed out")
        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}")
        
        # Force termination after timeout
        async def force_kill():
            await asyncio.sleep(timeout_seconds)
            logger.critical("Emergency shutdown timeout reached - forcing termination")
            import os
            import signal
            os.kill(os.getpid(), signal.SIGKILL)
        
        # Start force kill timer
        asyncio.create_task(force_kill())
        
        # Try graceful exit first
        logger.info("Attempting graceful exit...")
        import sys
        sys.exit(1)