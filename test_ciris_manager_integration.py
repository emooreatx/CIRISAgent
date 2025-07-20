#!/usr/bin/env python3
"""
Integration test for CIRISManager with real Docker containers.

This test requires Docker to be installed and running.
"""
import asyncio
import sys
import os
import tempfile
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ciris_manager.manager import CIRISManager
from ciris_manager.config.settings import CIRISManagerConfig


async def test_manager_integration():
    """Test CIRISManager with real containers."""
    print("Starting CIRISManager integration test...")
    
    # Create test config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config_data = {
            'manager': {
                'port': 9998,  # Different port to avoid conflicts
                'host': '127.0.0.1'
            },
            'docker': {
                'compose_file': str(Path(__file__).parent / 'deployment' / 'docker-compose.manager-test.yml')
            },
            'watchdog': {
                'check_interval': 5,
                'crash_threshold': 3,
                'crash_window': 60
            },
            'container_management': {
                'interval': 10,
                'pull_images': False  # Skip pulls for test
            }
        }
        yaml.dump(config_data, f)
        config_file = f.name
        
    try:
        # Load config
        config = CIRISManagerConfig.from_file(config_file)
        
        # Create manager
        manager = CIRISManager(config)
        
        # Start manager
        await manager.start()
        print("✓ Manager started successfully")
        
        # Run for 30 seconds to observe behavior
        print("Running for 30 seconds to observe container behavior...")
        await asyncio.sleep(30)
        
        # Check status
        status = manager.get_status()
        print(f"\nManager status: {status['running']}")
        print(f"Watchdog status: {status['watchdog_status']}")
        
        # Stop manager
        await manager.stop()
        print("✓ Manager stopped successfully")
        
    finally:
        # Cleanup
        os.unlink(config_file)
        
        # Stop test containers
        print("\nCleaning up test containers...")
        proc = await asyncio.create_subprocess_exec(
            'docker-compose',
            '-f', 'deployment/docker-compose.manager-test.yml',
            'down',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()


if __name__ == "__main__":
    try:
        asyncio.run(test_manager_integration())
        print("\n✓ Integration test completed successfully")
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        sys.exit(1)