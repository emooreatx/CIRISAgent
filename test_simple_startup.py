#!/usr/bin/env python3
"""Simple test to debug startup channel issue."""
import asyncio
import sys
import logging

# Add the project root to Python path
sys.path.insert(0, '/home/emoore/CIRISAgent')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_simple_startup():
    """Test simple agent startup."""
    print("\n=== Testing Simple Startup ===\n")
    
    from ciris_engine.runtime.ciris_runtime import CIRISRuntime
    from ciris_engine.config.config_loader import ConfigLoader
    
    # Load config
    config = await ConfigLoader.load_config(config_path=None, template_name="default")
    config.mock_llm = True  # Use mock LLM
    
    # Create runtime
    print("Creating runtime...")
    runtime = CIRISRuntime(
        adapter_types=["cli"],
        app_config=config,
        startup_channel_id=None,  # Let it auto-generate
        adapter_configs={},
        interactive=False,
    )
    
    print("Initializing runtime...")
    await runtime.initialize()
    
    print(f"Runtime startup_channel_id: {runtime.startup_channel_id}")
    
    # Check what channel the wakeup processor has
    if hasattr(runtime, 'agent_processor') and runtime.agent_processor:
        if hasattr(runtime.agent_processor, 'wakeup_processor'):
            print(f"Wakeup processor startup_channel_id: {runtime.agent_processor.wakeup_processor.startup_channel_id}")
    
    # Run for just a couple rounds
    print("\nStarting agent processing for 2 rounds...")
    await runtime.start_agent(num_rounds=2)
    
    # Shutdown
    print("\nShutting down...")
    await runtime.shutdown()
    
    print("\n✓ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_simple_startup())