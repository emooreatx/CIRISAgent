#!/usr/bin/env python3
"""
Test script to demonstrate global shutdown functionality.
This can be used to test shutdown from anywhere in the codebase.
"""
import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ciris_engine.utils.shutdown_manager import (
    request_global_shutdown,
    request_shutdown_communication_failure,
    request_shutdown_critical_service_failure,
    is_global_shutdown_requested,
    get_global_shutdown_reason,
    wait_for_global_shutdown,
    register_global_shutdown_handler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_shutdown_handler():
    """Example synchronous shutdown handler."""
    logger.info("Sync shutdown handler executed!")

async def async_shutdown_handler():
    """Example asynchronous shutdown handler."""
    logger.info("Async shutdown handler executed!")
    await asyncio.sleep(0.1)  # Simulate cleanup work

async def test_global_shutdown():
    """Test the global shutdown manager functionality."""
    logger.info("Testing global shutdown manager...")
    
    # Register some shutdown handlers
    register_global_shutdown_handler(sync_shutdown_handler, is_async=False)
    register_global_shutdown_handler(async_shutdown_handler, is_async=True)
    
    # Test 1: Check initial state
    assert not is_global_shutdown_requested(), "Shutdown should not be requested initially"
    logger.info("✓ Initial state check passed")
    
    # Test 2: Request shutdown from different contexts
    logger.info("Testing shutdown requests...")
    
    # Simulate a communication failure (like from speak handler)
    request_shutdown_communication_failure("Unable to send Discord messages")
    
    # Check that shutdown was requested
    assert is_global_shutdown_requested(), "Shutdown should be requested after communication failure"
    reason = get_global_shutdown_reason()
    assert "Communication services unavailable" in reason, f"Unexpected reason: {reason}"
    logger.info(f"✓ Communication failure shutdown: {reason}")
    
    # Test 3: Wait for shutdown (would normally be done by runtime)
    logger.info("Waiting for shutdown signal...")
    try:
        await asyncio.wait_for(wait_for_global_shutdown(), timeout=1.0)
        logger.info("✓ Shutdown signal received")
    except asyncio.TimeoutError:
        logger.error("✗ Timeout waiting for shutdown signal")
        return False
    
    logger.info("✓ All tests passed!")
    return True

async def test_different_shutdown_types():
    """Test different types of shutdown requests."""
    logger.info("\nTesting different shutdown types...")
    
    # Reset for clean test
    from ciris_engine.utils.shutdown_manager import get_shutdown_manager
    get_shutdown_manager().reset()
    
    # Test critical service failure
    request_shutdown_critical_service_failure("DatabaseService", "Connection timeout")
    reason = get_global_shutdown_reason()
    assert "Critical service failure: DatabaseService" in reason
    logger.info(f"✓ Critical service failure: {reason}")
    
    # Reset again
    get_shutdown_manager().reset()
    
    # Test direct global shutdown
    request_global_shutdown("Manual shutdown request for testing")
    reason = get_global_shutdown_reason()
    assert "Manual shutdown request for testing" in reason
    logger.info(f"✓ Direct global shutdown: {reason}")
    
    logger.info("✓ Different shutdown types test passed!")

def demonstrate_usage_examples():
    """Show practical usage examples for different scenarios."""
    print("\n" + "="*60)
    print("GLOBAL SHUTDOWN USAGE EXAMPLES")
    print("="*60)
    
    print("\n1. From a handler when communication fails:")
    print("   request_shutdown_communication_failure('Discord API unreachable')")
    
    print("\n2. From any service when a critical error occurs:")
    print("   request_shutdown_critical_service_failure('LLMService', 'API key invalid')")
    
    print("\n3. From anywhere for manual shutdown:")
    print("   request_global_shutdown('User requested restart')")
    
    print("\n4. Check if shutdown was requested:")
    print("   if is_global_shutdown_requested():")
    print("       logger.info(f'Shutdown reason: {get_global_shutdown_reason()}')")
    
    print("\n5. Wait for shutdown in async code (like runtime):")
    print("   await wait_for_global_shutdown()")
    
    print("\n6. Register cleanup handlers:")
    print("   register_global_shutdown_handler(cleanup_function, is_async=True)")
    
    print("\n" + "="*60)
    print("Now you can request graceful shutdown from ANYWHERE in the codebase!")
    print("="*60)

async def main():
    """Main test function."""
    try:
        # Run basic functionality tests
        if not await test_global_shutdown():
            return 1
        
        # Test different shutdown types
        await test_different_shutdown_types()
        
        # Show usage examples
        demonstrate_usage_examples()
        
        return 0
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
