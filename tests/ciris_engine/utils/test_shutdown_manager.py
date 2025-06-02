"""
Test global shutdown manager functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock

from ciris_engine.utils.shutdown_manager import (
    request_global_shutdown,
    request_shutdown_communication_failure,
    request_shutdown_critical_service_failure,
    is_global_shutdown_requested,
    get_global_shutdown_reason,
    wait_for_global_shutdown,
    register_global_shutdown_handler,
    get_shutdown_manager
)


class TestGlobalShutdownManager:
    """Test the global shutdown manager functionality."""
    
    def setup_method(self):
        """Reset the shutdown manager before each test."""
        manager = get_shutdown_manager()
        manager.reset()
    
    def test_initial_state(self):
        """Test that shutdown is not requested initially."""
        assert not is_global_shutdown_requested()
        assert get_global_shutdown_reason() is None
    
    def test_register_sync_shutdown_handler(self):
        """Test registering a synchronous shutdown handler."""
        handler1 = Mock()
        handler1.__name__ = "test_handler1"
        handler2 = Mock()
        handler2.__name__ = "test_handler2"
        
        # Register handlers
        register_global_shutdown_handler(handler1, is_async=False)
        register_global_shutdown_handler(handler2, is_async=False)
        
        # Request shutdown
        request_global_shutdown("Test shutdown")
        
        # Handlers should be called immediately for sync handlers
        handler1.assert_called_once()
        handler2.assert_called_once()
    
    def test_register_async_shutdown_handler(self):
        """Test registering an asynchronous shutdown handler."""
        handler = Mock()
        handler.__name__ = "test_async_handler"
        
        # Register async handler
        register_global_shutdown_handler(handler, is_async=True)
        
        # Request shutdown
        request_global_shutdown("Test async shutdown")
        
        # Async handlers are not called automatically on request
        handler.assert_not_called()
    
    def test_communication_failure_shutdown(self):
        """Test requesting shutdown due to communication failure."""
        request_shutdown_communication_failure("Test communication failure")
        
        assert is_global_shutdown_requested()
        reason = get_global_shutdown_reason()
        assert "communication" in reason.lower()
        assert "test communication failure" in reason.lower()
    
    def test_critical_service_failure_shutdown(self):
        """Test requesting shutdown due to critical service failure."""
        request_shutdown_critical_service_failure("TestService", "Test service failure")
        
        assert is_global_shutdown_requested()
        reason = get_global_shutdown_reason()
        assert "critical service failure" in reason.lower()
        assert "testservice" in reason.lower()
    
    def test_general_shutdown_request(self):
        """Test general shutdown request."""
        request_global_shutdown("Test general shutdown")
        
        assert is_global_shutdown_requested()
        reason = get_global_shutdown_reason()
        assert reason == "Test general shutdown"
    
    @pytest.mark.asyncio
    async def test_wait_for_shutdown_immediate(self):
        """Test waiting for shutdown when already requested."""
        # Request shutdown first
        request_global_shutdown("Test immediate shutdown")
        
        # This should return immediately since shutdown was already requested
        try:
            await asyncio.wait_for(wait_for_global_shutdown(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("wait_for_global_shutdown() should have returned immediately")
    
    @pytest.mark.asyncio
    async def test_wait_for_shutdown_with_delay(self):
        """Test waiting for shutdown with a delay."""
        async def delayed_shutdown():
            await asyncio.sleep(0.1)
            request_global_shutdown("Delayed shutdown")
        
        # Start the delayed shutdown task
        shutdown_task = asyncio.create_task(delayed_shutdown())
        
        # Wait for shutdown (should complete when delayed_shutdown calls request_global_shutdown)
        try:
            await asyncio.wait_for(wait_for_global_shutdown(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("wait_for_global_shutdown() should have completed when shutdown was requested")
        
        # Clean up
        await shutdown_task
    
    def test_duplicate_shutdown_requests(self):
        """Test that duplicate shutdown requests are handled gracefully."""
        request_global_shutdown("First shutdown")
        first_reason = get_global_shutdown_reason()
        
        # Second request should be ignored
        request_global_shutdown("Second shutdown")
        second_reason = get_global_shutdown_reason()
        
        assert first_reason == second_reason
        assert "First shutdown" in first_reason
    
    @pytest.mark.asyncio
    async def test_async_handler_execution(self):
        """Test execution of async shutdown handlers."""
        handler = Mock()
        handler.__name__ = "test_async_execution_handler"
        
        # Register async handler
        register_global_shutdown_handler(handler, is_async=True)
        
        # Request shutdown
        request_global_shutdown("Test async handler execution")
        
        # Manually execute async handlers
        manager = get_shutdown_manager()
        await manager.execute_async_handlers()
        
        # Handler should now be called
        handler.assert_called_once()
