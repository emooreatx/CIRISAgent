#!/usr/bin/env python3
"""Simple SDK test to understand the actual methods available."""

import asyncio
import sys
sys.path.append('/home/emoore/CIRISAgent')
from ciris_sdk import CIRISClient


async def test_sdk():
    """Test basic SDK functionality."""
    async with CIRISClient(base_url="http://localhost:8080") as client:
        # Login
        print("Logging in...")
        await client.auth.login("admin", "ciris_admin_password")
        print("✓ Login successful")
        
        # Check what methods are available on each resource
        print("\n=== Available Methods ===")
        
        # Auth methods
        print("\nAuth methods:")
        auth_methods = [m for m in dir(client.auth) if not m.startswith('_')]
        for method in auth_methods:
            print(f"  - auth.{method}")
        
        # Agent methods
        print("\nAgent methods:")
        agent_methods = [m for m in dir(client.agent) if not m.startswith('_')]
        for method in agent_methods:
            print(f"  - agent.{method}")
        
        # System methods
        print("\nSystem methods:")
        system_methods = [m for m in dir(client.system) if not m.startswith('_')]
        for method in system_methods:
            print(f"  - system.{method}")
        
        # Memory methods
        print("\nMemory methods:")
        memory_methods = [m for m in dir(client.memory) if not m.startswith('_')]
        for method in memory_methods:
            print(f"  - memory.{method}")
        
        # Let's test a few methods to see what works
        print("\n=== Testing Methods ===")
        
        # Test get current user
        try:
            print("\nTesting auth.current_user()...")
            user = await client.auth.current_user()
            print(f"✓ Current user: {user}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test agent status
        try:
            print("\nTesting agent.status()...")
            status = await client.agent.status()
            print(f"✓ Agent status: {status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test system health
        try:
            print("\nTesting system.health()...")
            health = await client.system.health()
            print(f"✓ System health: {health}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test convenience methods on client
        print("\n=== Testing Convenience Methods ===")
        
        try:
            print("\nTesting client.status()...")
            status = await client.status()
            print(f"✓ Status: {status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        try:
            print("\nTesting client.interact()...")
            response = await client.interact("Hello from SDK test")
            print(f"✓ Response: {response}")
        except Exception as e:
            print(f"✗ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_sdk())