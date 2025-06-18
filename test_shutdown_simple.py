#!/usr/bin/env python3
"""Simple test of shutdown negotiation."""
import asyncio
import sys
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, '/home/emoore/CIRISAgent')

from ciris_engine.processor.shutdown_processor import ShutdownProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig, WorkflowConfig
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine import persistence

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_shutdown_processor():
    """Test the shutdown processor directly."""
    print("\n=== Testing Shutdown Processor ===\n")
    
    # Initialize database
    persistence.initialize_database()
    
    # Create minimal config
    config = AppConfig(workflow=WorkflowConfig())
    
    # Create shutdown processor (with minimal dependencies)
    processor = ShutdownProcessor(
        app_config=config,
        thought_processor=None,  # Not needed for basic test
        action_dispatcher=None,  # Not needed for basic test
        services={},
        runtime=None
    )
    
    # Test that it supports SHUTDOWN state
    assert processor.get_supported_states() == [AgentState.SHUTDOWN]
    assert await processor.can_process(AgentState.SHUTDOWN)
    
    print("✓ Shutdown processor created successfully")
    print("✓ Supports SHUTDOWN state")
    
    # Process one round
    print("\nProcessing round 1...")
    result = await processor.process(1)
    print(f"Result: {result}")
    
    # Check that task was created
    assert processor.shutdown_task is not None
    print(f"✓ Created shutdown task: {processor.shutdown_task.task_id}")
    
    # Process another round to see seed thought generation
    print("\nProcessing round 2...")
    result = await processor.process(2)
    print(f"Result: {result}")
    
    # Check thoughts
    thoughts = persistence.get_thoughts_by_task_id(processor.shutdown_task.task_id)
    print(f"✓ Generated {len(thoughts)} thoughts")
    
    if thoughts:
        for thought in thoughts:
            print(f"  - Thought {thought.thought_id}: {thought.status.value}")
    
    print("\n✓ Shutdown processor test complete!")

if __name__ == "__main__":
    asyncio.run(test_shutdown_processor())