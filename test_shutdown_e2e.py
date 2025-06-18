#!/usr/bin/env python3
"""End-to-end test of shutdown negotiation with proper agent startup."""
import asyncio
import sys
import os
import signal
import time
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, '/home/emoore/CIRISAgent')

async def test_shutdown_negotiation():
    """Test the full shutdown negotiation flow."""
    print("\n=== Testing E2E Shutdown Negotiation ===\n")
    
    # Start the agent in a subprocess
    proc = await asyncio.create_subprocess_exec(
        sys.executable, 'main.py', '--adapter', 'cli', '--mock-llm', '--no-interactive',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    print(f"Started agent process (PID: {proc.pid})")
    print("Waiting for agent to reach WORK state...")
    
    # Wait for agent to be ready (look for specific output)
    start_time = time.time()
    agent_ready = False
    
    async def read_output():
        nonlocal agent_ready
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            line_str = line.decode().strip()
            print(f"[AGENT] {line_str}")
            if "STATE] Transition: WAKEUP -> WORK" in line_str:
                agent_ready = True
                print("\n✓ Agent reached WORK state!")
                break
    
    # Read output with timeout
    try:
        await asyncio.wait_for(read_output(), timeout=30)
    except asyncio.TimeoutError:
        print("✗ Timeout waiting for agent to reach WORK state")
        proc.terminate()
        await proc.wait()
        return
    
    if not agent_ready:
        print("✗ Agent did not reach WORK state")
        proc.terminate()
        await proc.wait()
        return
    
    # Wait a bit more for agent to stabilize
    await asyncio.sleep(2)
    
    # Send SIGTERM to trigger shutdown
    print(f"\nSending SIGTERM to agent (PID: {proc.pid})...")
    proc.terminate()
    
    # Monitor shutdown negotiation
    shutdown_start = time.time()
    shutdown_complete = False
    
    # Continue reading output
    async def monitor_shutdown():
        nonlocal shutdown_complete
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            line_str = line.decode().strip()
            print(f"[SHUTDOWN] {line_str}")
            
            # Look for shutdown negotiation indicators
            if "STATE] Transition:" in line_str and "-> SHUTDOWN" in line_str:
                print("✓ Transitioned to SHUTDOWN state")
            elif "Created shutdown task:" in line_str:
                print("✓ Shutdown task created")
            elif "SPEAK" in line_str and "shutdown" in line_str.lower():
                print("✓ Agent responded to shutdown request")
            elif "TASK_COMPLETE" in line_str:
                print("✓ Agent accepted shutdown")
                shutdown_complete = True
            elif "REJECT" in line_str:
                print("⚠️  Agent rejected shutdown")
            elif "DEFER" in line_str:
                print("⚠️  Agent deferred shutdown")
    
    # Monitor with timeout
    try:
        await asyncio.wait_for(monitor_shutdown(), timeout=10)
    except asyncio.TimeoutError:
        print("⏱️  Shutdown monitoring timed out")
    
    # Wait for process to exit
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
        print(f"\n✓ Agent process exited with code: {proc.returncode}")
    except asyncio.TimeoutError:
        print("\n✗ Agent did not exit within timeout, forcing kill")
        proc.kill()
        await proc.wait()
    
    # Calculate timing
    shutdown_duration = time.time() - shutdown_start
    total_duration = time.time() - start_time
    
    print(f"\n=== Summary ===")
    print(f"Total test duration: {total_duration:.1f}s")
    print(f"Shutdown duration: {shutdown_duration:.1f}s")
    print(f"Shutdown negotiation: {'✓ COMPLETED' if shutdown_complete else '✗ INCOMPLETE'}")
    
    # Expected: ~2 seconds for negotiation
    if 1.5 <= shutdown_duration <= 3.0:
        print(f"✓ Shutdown duration within expected range (1.5-3.0s)")
    else:
        print(f"⚠️  Shutdown duration outside expected range: {shutdown_duration:.1f}s")

if __name__ == "__main__":
    asyncio.run(test_shutdown_negotiation())