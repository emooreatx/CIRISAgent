"""
Test script for CIRISManager core functionality.
"""
import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from ciris_manager.core.watchdog import CrashLoopWatchdog, CrashEvent, ContainerTracker
from ciris_manager.core.container_manager import ContainerManager
from ciris_manager.config.settings import CIRISManagerConfig


class TestCrashLoopWatchdog(unittest.TestCase):
    """Test crash loop detection."""
    
    def setUp(self):
        self.watchdog = CrashLoopWatchdog(
            check_interval=1,
            crash_threshold=3,
            crash_window=300
        )
        
    def test_crash_tracking(self):
        """Test that crashes are tracked correctly."""
        tracker = ContainerTracker(container="test-agent")
        
        # Add crashes
        for i in range(3):
            crash = CrashEvent(
                container="test-agent",
                timestamp=datetime.now(),
                exit_code=1
            )
            tracker.crashes.append(crash)
            
        self.assertEqual(len(tracker.crashes), 3)
        
    def test_crash_window(self):
        """Test that old crashes are removed."""
        tracker = ContainerTracker(container="test-agent")
        
        # Add old crash
        old_crash = CrashEvent(
            container="test-agent",
            timestamp=datetime.now() - timedelta(minutes=10),
            exit_code=1
        )
        tracker.crashes.append(old_crash)
        
        # Add recent crashes
        for i in range(2):
            crash = CrashEvent(
                container="test-agent",
                timestamp=datetime.now(),
                exit_code=1
            )
            tracker.crashes.append(crash)
            
        # Filter old crashes
        cutoff = datetime.now() - timedelta(seconds=300)
        tracker.crashes = [
            c for c in tracker.crashes
            if c.timestamp > cutoff
        ]
        
        # Should only have 2 recent crashes
        self.assertEqual(len(tracker.crashes), 2)
        
        
class TestContainerManager(unittest.TestCase):
    """Test container management."""
    
    @patch('ciris_manager.core.container_manager.Path.exists')
    def test_init_validates_compose_file(self, mock_exists):
        """Test that compose file existence is validated."""
        mock_exists.return_value = False
        
        with self.assertRaises(FileNotFoundError):
            ContainerManager("/fake/path/docker-compose.yml")
            
            
class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CIRISManagerConfig()
        
        self.assertEqual(config.manager.port, 9999)
        self.assertEqual(config.watchdog.crash_threshold, 3)
        self.assertEqual(config.container_management.interval, 60)
        
    def test_config_serialization(self):
        """Test config can be serialized."""
        config = CIRISManagerConfig()
        data = config.model_dump()
        
        self.assertIn('manager', data)
        self.assertIn('watchdog', data)
        self.assertIn('container_management', data)


# Async test runner
async def async_test_container_loop():
    """Test container management loop behavior."""
    with patch('ciris_manager.core.container_manager.Path.exists', return_value=True):
        manager = ContainerManager("/fake/docker-compose.yml", interval=1)
        
        # Mock the compose command
        manager._run_compose_command = AsyncMock(return_value="")
        manager._get_agents_status = AsyncMock(return_value=[])
        
        # Start and run briefly
        await manager.start()
        await asyncio.sleep(2)
        await manager.stop()
        
        # Should have called compose commands
        assert manager._run_compose_command.called
        

def run_async_tests():
    """Run async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(async_test_container_loop())
        print("✓ Async tests passed")
    finally:
        loop.close()


if __name__ == "__main__":
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run async tests
    print("\nRunning async tests...")
    run_async_tests()