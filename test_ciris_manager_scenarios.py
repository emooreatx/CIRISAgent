#!/usr/bin/env python3
"""
Comprehensive test scenarios for CIRISManager deployment.

Tests various real-world scenarios:
1. Clean shutdown and restart
2. Crash loop detection
3. Update deployment
4. Multiple agent management
"""
import asyncio
import subprocess
import sys
import os
import time
import tempfile
import yaml
import shutil
from pathlib import Path
from datetime import datetime

# Test configuration
TEST_COMPOSE_FILE = "deployment/docker-compose.manager-test.yml"
TEST_CONFIG_FILE = "/tmp/ciris-manager-test.yml"
TEST_LOG_FILE = "/tmp/ciris-manager-test.log"


class TestScenario:
    """Base class for test scenarios."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error_message = None
        
    async def setup(self):
        """Setup the test scenario."""
        pass
        
    async def run(self):
        """Run the test scenario."""
        raise NotImplementedError
        
    async def cleanup(self):
        """Clean up after the test."""
        pass
        
    async def execute(self):
        """Execute the complete test."""
        print(f"\n{'='*60}")
        print(f"Running: {self.name}")
        print('='*60)
        
        try:
            await self.setup()
            await self.run()
            self.passed = True
            print(f"✅ {self.name} - PASSED")
        except Exception as e:
            self.passed = False
            self.error_message = str(e)
            print(f"❌ {self.name} - FAILED: {e}")
        finally:
            await self.cleanup()


class Scenario1_CleanRestart(TestScenario):
    """Test clean shutdown and restart behavior."""
    
    def __init__(self):
        super().__init__("Clean Shutdown and Restart")
        
    async def setup(self):
        """Create a test container that exits cleanly."""
        compose_content = """
version: '3.8'
services:
  agent-clean-test:
    image: alpine:latest
    container_name: ciris-agent-clean-test
    command: ["sh", "-c", "echo 'Starting...' && sleep 30 && echo 'Shutting down cleanly' && exit 0"]
    restart: unless-stopped
"""
        with open(TEST_COMPOSE_FILE, 'w') as f:
            f.write(compose_content)
            
    async def run(self):
        """Test that clean exit keeps container stopped."""
        # Start container
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        # Verify it's running
        running = await is_container_running("ciris-agent-clean-test")
        assert running, "Container should be running"
        
        # Wait for clean exit
        print("Waiting for container to exit cleanly...")
        await asyncio.sleep(35)
        
        # Verify it's stopped
        running = await is_container_running("ciris-agent-clean-test")
        assert not running, "Container should be stopped after clean exit"
        
        # Run docker-compose up -d (simulating CIRISManager)
        print("Simulating CIRISManager docker-compose up -d...")
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        # Verify it started again
        running = await is_container_running("ciris-agent-clean-test")
        assert running, "Container should restart with docker-compose up -d"
        
    async def cleanup(self):
        """Stop and remove test containers."""
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} down")


class Scenario2_CrashLoop(TestScenario):
    """Test crash loop detection."""
    
    def __init__(self):
        super().__init__("Crash Loop Detection")
        
    async def setup(self):
        """Create a container that crashes repeatedly."""
        compose_content = """
version: '3.8'
services:
  agent-crash-test:
    image: alpine:latest
    container_name: ciris-agent-crash-test
    command: ["sh", "-c", "echo 'Crashing!' && exit 1"]
    restart: unless-stopped
"""
        with open(TEST_COMPOSE_FILE, 'w') as f:
            f.write(compose_content)
            
    async def run(self):
        """Test that crash loops are detected."""
        # Start container
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        
        # Monitor crashes
        crash_count = 0
        start_time = time.time()
        
        print("Monitoring for crashes...")
        while time.time() - start_time < 30:  # Monitor for 30 seconds
            exit_code = await get_container_exit_code("ciris-agent-crash-test")
            if exit_code == 1:
                crash_count += 1
                print(f"Crash detected #{crash_count}")
                
            await asyncio.sleep(2)
            
        # Should have multiple crashes
        assert crash_count >= 3, f"Expected 3+ crashes, got {crash_count}"
        print(f"Detected {crash_count} crashes - watchdog should intervene")
        
    async def cleanup(self):
        """Stop and remove test containers."""
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} down")


class Scenario3_UpdateDeployment(TestScenario):
    """Test update deployment scenario."""
    
    def __init__(self):
        super().__init__("Update Deployment")
        self.v1_file = "/tmp/ciris-test-v1"
        self.v2_file = "/tmp/ciris-test-v2"
        
    async def setup(self):
        """Create versioned test files."""
        # Create v1 and v2 marker files
        with open(self.v1_file, 'w') as f:
            f.write("version 1")
        with open(self.v2_file, 'w') as f:
            f.write("version 2")
            
        # Initial compose with v1
        compose_content = f"""
version: '3.8'
services:
  agent-update-test:
    image: alpine:latest
    container_name: ciris-agent-update-test
    command: ["sh", "-c", "cat /version.txt && sleep 3600"]
    restart: unless-stopped
    volumes:
      - {self.v1_file}:/version.txt:ro
"""
        with open(TEST_COMPOSE_FILE, 'w') as f:
            f.write(compose_content)
            
    async def run(self):
        """Test update deployment process."""
        # Start with v1
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        # Verify v1 is running
        logs = await get_container_logs("ciris-agent-update-test")
        assert "version 1" in logs, "Should be running v1"
        print("✓ Running version 1")
        
        # Update compose to v2
        compose_content = f"""
version: '3.8'
services:
  agent-update-test:
    image: alpine:latest
    container_name: ciris-agent-update-test
    command: ["sh", "-c", "cat /version.txt && sleep 3600"]
    restart: unless-stopped
    volumes:
      - {self.v2_file}:/version.txt:ro
"""
        with open(TEST_COMPOSE_FILE, 'w') as f:
            f.write(compose_content)
            
        # Simulate graceful shutdown
        print("Simulating graceful shutdown...")
        await run_command("docker stop ciris-agent-update-test")
        await asyncio.sleep(2)
        
        # Run docker-compose up -d (CIRISManager behavior)
        print("Running docker-compose up -d to deploy update...")
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        # Verify v2 is running
        logs = await get_container_logs("ciris-agent-update-test")
        assert "version 2" in logs, "Should be running v2"
        print("✓ Successfully updated to version 2")
        
    async def cleanup(self):
        """Clean up test files and containers."""
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} down")
        for f in [self.v1_file, self.v2_file]:
            if os.path.exists(f):
                os.unlink(f)


class Scenario4_MultiAgent(TestScenario):
    """Test multiple agent management."""
    
    def __init__(self):
        super().__init__("Multi-Agent Management")
        
    async def setup(self):
        """Create multiple test agents."""
        compose_content = """
version: '3.8'
services:
  agent-stable:
    image: alpine:latest
    container_name: ciris-agent-stable
    command: ["sh", "-c", "while true; do echo 'Stable agent running' && sleep 30; done"]
    restart: unless-stopped
    
  agent-crasher:
    image: alpine:latest
    container_name: ciris-agent-crasher
    command: ["sh", "-c", "echo 'Will crash' && sleep 5 && exit 1"]
    restart: unless-stopped
    
  agent-stopper:
    image: alpine:latest
    container_name: ciris-agent-stopper
    command: ["sh", "-c", "echo 'Will stop cleanly' && sleep 10 && exit 0"]
    restart: unless-stopped
"""
        with open(TEST_COMPOSE_FILE, 'w') as f:
            f.write(compose_content)
            
    async def run(self):
        """Test managing multiple agents with different behaviors."""
        # Start all agents
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        # Initial status
        print("Initial agent status:")
        await print_agent_status()
        
        # Wait for behaviors to manifest
        print("\nWaiting 15 seconds for agent behaviors...")
        await asyncio.sleep(15)
        
        # Check status
        print("\nAgent status after 15 seconds:")
        await print_agent_status()
        
        # Stable should be running
        stable_running = await is_container_running("ciris-agent-stable")
        assert stable_running, "Stable agent should still be running"
        
        # Stopper should be stopped
        stopper_running = await is_container_running("ciris-agent-stopper")
        assert not stopper_running, "Stopper agent should be stopped"
        
        # Crasher should have restarted
        crasher_exit = await get_container_exit_code("ciris-agent-crasher")
        assert crasher_exit == 1, "Crasher should have non-zero exit code"
        
        # Run docker-compose up -d
        print("\nRunning docker-compose up -d...")
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
        await asyncio.sleep(2)
        
        print("\nFinal agent status:")
        await print_agent_status()
        
    async def cleanup(self):
        """Stop all test agents."""
        await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} down")


async def print_agent_status():
    """Print status of all test agents."""
    agents = ["ciris-agent-stable", "ciris-agent-crasher", "ciris-agent-stopper"]
    for agent in agents:
        running = await is_container_running(agent)
        exit_code = await get_container_exit_code(agent)
        status = "running" if running else f"stopped (exit {exit_code})"
        print(f"  {agent}: {status}")


async def run_command(cmd: str) -> str:
    """Run a shell command."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and "No such container" not in stderr.decode():
        raise RuntimeError(f"Command failed: {cmd}\n{stderr.decode()}")
    return stdout.decode()


async def is_container_running(name: str) -> bool:
    """Check if a container is running."""
    try:
        output = await run_command(f"docker inspect -f '{{{{.State.Running}}}}' {name}")
        return output.strip() == "true"
    except:
        return False


async def get_container_exit_code(name: str) -> int:
    """Get container exit code."""
    try:
        output = await run_command(f"docker inspect -f '{{{{.State.ExitCode}}}}' {name}")
        return int(output.strip())
    except:
        return -1


async def get_container_logs(name: str) -> str:
    """Get container logs."""
    try:
        return await run_command(f"docker logs {name}")
    except:
        return ""


async def test_with_manager():
    """Test CIRISManager with real scenarios."""
    print("\n" + "="*60)
    print("Testing CIRISManager Integration")
    print("="*60)
    
    # Create test config
    config = {
        'docker': {
            'compose_file': str(Path.cwd() / TEST_COMPOSE_FILE)
        },
        'watchdog': {
            'check_interval': 5,
            'crash_threshold': 3,
            'crash_window': 60
        },
        'container_management': {
            'interval': 10,
            'pull_images': False
        }
    }
    
    with open(TEST_CONFIG_FILE, 'w') as f:
        yaml.dump(config, f)
        
    # Import and run manager
    sys.path.insert(0, str(Path.cwd()))
    from ciris_manager.manager import CIRISManager
    from ciris_manager.config.settings import CIRISManagerConfig
    
    config_obj = CIRISManagerConfig.from_file(TEST_CONFIG_FILE)
    manager = CIRISManager(config_obj)
    
    # Start manager
    await manager.start()
    print("✓ CIRISManager started")
    
    # Run crash loop test with manager
    scenario = Scenario2_CrashLoop()
    await scenario.setup()
    
    print("\nStarting crash loop test with manager watching...")
    await run_command(f"docker-compose -f {TEST_COMPOSE_FILE} up -d")
    
    # Let manager detect crash loop
    await asyncio.sleep(30)
    
    # Check watchdog status
    status = manager.get_status()
    watchdog_status = status['watchdog_status']
    print(f"\nWatchdog status: {watchdog_status}")
    
    # Cleanup
    await scenario.cleanup()
    await manager.stop()
    os.unlink(TEST_CONFIG_FILE)


async def main():
    """Run all test scenarios."""
    print("CIRIS Manager Deployment Test Suite")
    print("===================================")
    
    # Run individual scenarios
    scenarios = [
        Scenario1_CleanRestart(),
        Scenario2_CrashLoop(),
        Scenario3_UpdateDeployment(),
        Scenario4_MultiAgent()
    ]
    
    results = []
    for scenario in scenarios:
        await scenario.execute()
        results.append((scenario.name, scenario.passed, scenario.error_message))
        
    # Test with actual manager
    try:
        await test_with_manager()
        manager_test_passed = True
    except Exception as e:
        print(f"❌ Manager integration test failed: {e}")
        manager_test_passed = False
        
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed, error in results:
        status = "✅ PASSED" if passed else f"❌ FAILED: {error}"
        print(f"{name}: {status}")
        
    manager_status = "✅ PASSED" if manager_test_passed else "❌ FAILED"
    print(f"Manager Integration: {manager_status}")
    
    # Overall result
    all_passed = all(r[1] for r in results) and manager_test_passed
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)