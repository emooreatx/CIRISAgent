#!/usr/bin/env python3
"""Test script to verify the ObserveHandler fix works correctly."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from unittest.mock import Mock
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.registries.base import ServiceRegistry

def test_observe_handler_fix():
    """Test that ObserveHandler can access multi_service_sink after our fix."""
    
    # Create mock dependencies
    service_registry = ServiceRegistry()
    io_adapter = Mock()  # Mock IO adapter
    secrets_service = Mock()  # Mock secrets service
    multi_service_sink = MultiServiceActionSink(service_registry=service_registry)
    
    # Build action dispatcher with multi_service_sink
    action_dispatcher = build_action_dispatcher(
        service_registry=service_registry,
        io_adapter=io_adapter,
        shutdown_callback=lambda: None,
        secrets_service=secrets_service,
        multi_service_sink=multi_service_sink
    )
    
    # Build action dispatcher with multi_service_sink
    action_dispatcher = build_action_dispatcher(
        service_registry=service_registry,
        io_adapter=io_adapter,
        shutdown_callback=lambda: None,
        secrets_service=secrets_service,
        multi_service_sink=multi_service_sink
    )
    
    # Get the ObserveHandler
    observe_handler = action_dispatcher.handlers.get('ObserveHandler')
    
    if observe_handler is None:
        print("❌ ObserveHandler not found in action dispatcher")
        return False
    
    # Test that get_multi_service_sink() returns the correct sink
    retrieved_sink = observe_handler.get_multi_service_sink()
    
    if retrieved_sink is None:
        print("❌ get_multi_service_sink() returned None")
        return False
    
    if retrieved_sink is not multi_service_sink:
        print("❌ get_multi_service_sink() returned wrong sink")
        return False
    
    # Test that the sink has the required method
    if not hasattr(retrieved_sink, 'fetch_messages_sync'):
        print("❌ Multi service sink missing fetch_messages_sync method")
        return False
    
    print("✅ ObserveHandler fix verified successfully!")
    print(f"   - ObserveHandler found: {observe_handler}")
    print(f"   - Multi service sink accessible: {retrieved_sink}")
    print(f"   - fetch_messages_sync method available: {hasattr(retrieved_sink, 'fetch_messages_sync')}")
    
    return True

if __name__ == "__main__":
    success = test_observe_handler_fix()
    sys.exit(0 if success else 1)
