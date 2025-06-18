#!/usr/bin/env python3
"""Test graceful shutdown with timeout."""
import subprocess
import sys
import time

def test_shutdown():
    """Run agent with 5 second timeout and measure shutdown time."""
    print("Starting agent with 5 second timeout...")
    start_time = time.time()
    
    cmd = [sys.executable, "main.py", "--adapter", "cli", "--mock-llm", "--timeout", "5", "--no-interactive"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nAgent ran for {duration:.1f} seconds")
    print(f"Expected: ~7 seconds (5s work + 2s shutdown negotiation)")
    print(f"Actual vs expected difference: {abs(duration - 7):.1f}s")
    
    # Check output for shutdown negotiation
    if "SHUTDOWN PROCESSOR" in proc.stdout or "shutdown task" in proc.stdout.lower():
        print("✓ Shutdown negotiation detected in output")
    else:
        print("✗ No shutdown negotiation detected")
        
    if "Agent acknowledged shutdown" in proc.stdout or "shutdown_accepted" in proc.stdout:
        print("✓ Agent accepted shutdown")
    else:
        print("✗ Agent shutdown acceptance not detected")
    
    print("\n--- Last 20 lines of output ---")
    lines = proc.stdout.strip().split('\n')
    for line in lines[-20:]:
        print(line)
    
    if proc.stderr:
        print("\n--- Errors ---")
        print(proc.stderr)

if __name__ == "__main__":
    test_shutdown()